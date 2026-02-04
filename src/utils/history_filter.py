"""
History Filter Utility - 对话历史过滤工具

提供对话历史的过滤功能：
1. 过滤URL链接
2. 过滤不重要的对话内容
3. 将过滤的内容存储到磁盘供后续检索

用于优化token使用，减少发送给LLM的历史对话内容
"""
import re
import os
import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from loguru import logger


@dataclass
class FilteredContent:
    """被过滤的内容记录"""
    original_content: str
    filter_reason: str  # "url", "repetitive", "trivial"
    extracted_urls: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    placeholder: str = ""  # 用于替换原内容的占位符


@dataclass 
class FilterResult:
    """过滤结果"""
    filtered_history: List[Dict[str, str]]  # 过滤后的对话历史
    filtered_out: List[FilteredContent]  # 被过滤的内容
    storage_path: Optional[str] = None  # 存储路径


class HistoryFilter:
    """
    对话历史过滤器
    
    功能：
    1. 检测并过滤URL链接
    2. 检测并过滤简单寒暄（如"好的"、"谢谢"等）
    3. 检测并过滤重复内容
    4. 将过滤内容存储到磁盘
    """
    
    # URL正则表达式模式 - 使用非捕获组避免空匹配
    URL_PATTERN = re.compile(
        r'(?:https?://[^\s<>"{}|\\^`\[\]]+)|'  # http/https URLs
        r'(?:www\.[^\s<>"{}|\\^`\[\]]+)|'       # www URLs
        r'(?:[a-zA-Z0-9.-]+\.(?:com|org|net|io|cn|co|info|edu|gov|app|dev)[^\s]*)'  # Domain-like patterns
    )
    
    # 简单寒暄关键词（完全匹配或主要内容为这些）
    TRIVIAL_PATTERNS = [
        r'^好的[。！]?$',
        r'^好[。！]?$',
        r'^嗯[。！]?$',
        r'^嗯嗯[。！]?$',
        r'^哦[。！]?$',
        r'^哦哦[。！]?$',
        r'^谢谢[。！]?$',
        r'^谢谢[你您][。！]?$',
        r'^感谢[。！]?$',
        r'^收到[。！]?$',
        r'^明白[。！]?$',
        r'^知道了[。！]?$',
        r'^了解[。！]?$',
        r'^行[。！]?$',
        r'^可以[。！]?$',
        r'^没问题[。！]?$',
        r'^OK[。！]?$',
        r'^ok[。！]?$',
    ]
    
    def __init__(
        self, 
        storage_dir: str = "data/filtered_history",
        enable_url_filter: bool = True,
        enable_trivial_filter: bool = True,
        enable_disk_storage: bool = True,
        min_content_length: int = 5,  # 低于此长度的内容可能被视为不重要
        url_content_threshold: float = 0.7  # URL占内容比例超过此值时过滤
    ):
        """
        初始化过滤器
        
        Args:
            storage_dir: 过滤内容存储目录
            enable_url_filter: 是否启用URL过滤
            enable_trivial_filter: 是否启用简单寒暄过滤
            enable_disk_storage: 是否启用磁盘存储
            min_content_length: 最小内容长度阈值
            url_content_threshold: URL占比阈值，超过此值时过滤
        """
        self.storage_dir = Path(storage_dir)
        self.enable_url_filter = enable_url_filter
        self.enable_trivial_filter = enable_trivial_filter
        self.enable_disk_storage = enable_disk_storage
        self.min_content_length = min_content_length
        self.url_content_threshold = url_content_threshold
        
        # 预编译简单寒暄模式
        self._trivial_compiled = [re.compile(p, re.IGNORECASE) for p in self.TRIVIAL_PATTERNS]
        
        # 确保存储目录存在
        if enable_disk_storage:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def filter_history(
        self,
        conversation_history: List[Dict[str, str]],
        chat_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> FilterResult:
        """
        过滤对话历史
        
        Args:
            conversation_history: 原始对话历史
            chat_id: 对话ID（用于存储）
            user_id: 用户ID（用于存储）
            
        Returns:
            FilterResult: 过滤结果
        """
        filtered_history = []
        filtered_out = []
        
        for msg in conversation_history:
            content = msg.get("content", "")
            role = msg.get("role", "user")
            
            # 检查是否需要过滤
            should_filter, filter_reason, extracted_data = self._should_filter(content, role)
            
            if should_filter:
                # 创建过滤记录
                filtered_content = FilteredContent(
                    original_content=content,
                    filter_reason=filter_reason,
                    extracted_urls=extracted_data.get("urls", []),
                    placeholder=self._generate_placeholder(filter_reason, extracted_data)
                )
                filtered_out.append(filtered_content)
                
                # 如果有占位符，用占位符替换原内容
                if filtered_content.placeholder:
                    filtered_history.append({
                        "role": role,
                        "content": filtered_content.placeholder
                    })
                # 否则完全过滤（不添加到历史）
            else:
                # 对于未完全过滤的内容，可能需要清理URL但保留其他内容
                cleaned_content = content
                if self.enable_url_filter:
                    cleaned_content = self._clean_urls_from_content(content)
                
                filtered_history.append({
                    "role": role,
                    "content": cleaned_content if cleaned_content.strip() else content
                })
        
        # 存储过滤的内容到磁盘
        storage_path = None
        if self.enable_disk_storage and filtered_out:
            storage_path = self._store_filtered_content(
                filtered_out, chat_id, user_id
            )
        
        logger.info(
            f"📁 [HistoryFilter] Filtered {len(filtered_out)} messages from "
            f"{len(conversation_history)} total. Remaining: {len(filtered_history)}"
        )
        
        return FilterResult(
            filtered_history=filtered_history,
            filtered_out=filtered_out,
            storage_path=storage_path
        )
    
    def _should_filter(
        self, 
        content: str, 
        role: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        判断内容是否应该被过滤
        
        Returns:
            (should_filter, reason, extracted_data)
        """
        if not content or not content.strip():
            return True, "empty", {}
        
        content_stripped = content.strip()
        
        # 1. 检查简单寒暄（仅对短内容）
        if self.enable_trivial_filter and len(content_stripped) <= 20:
            for pattern in self._trivial_compiled:
                if pattern.match(content_stripped):
                    return True, "trivial", {}
        
        # 2. 检查URL占比
        if self.enable_url_filter:
            urls = self.URL_PATTERN.findall(content)
            if urls:
                # 计算URL在内容中的占比
                url_total_length = sum(len(url) for url in urls)
                content_length = len(content_stripped)
                
                if content_length > 0:
                    url_ratio = url_total_length / content_length
                    
                    # 如果URL占比超过阈值，过滤该消息
                    if url_ratio >= self.url_content_threshold:
                        return True, "url_dominated", {"urls": urls}
        
        # 3. 检查内容长度（非常短的内容可能不重要）
        if len(content_stripped) < self.min_content_length:
            # 但不过滤助手的回复
            if role == "user":
                return True, "too_short", {}
        
        return False, "", {}
    
    def _generate_placeholder(
        self, 
        filter_reason: str, 
        extracted_data: Dict[str, Any]
    ) -> str:
        """
        生成占位符文本
        
        对于某些过滤的内容，生成简短的占位符而不是完全删除
        """
        if filter_reason == "url_dominated":
            urls = extracted_data.get("urls", [])
            if urls:
                return f"[用户分享了{len(urls)}个链接]"
        elif filter_reason == "trivial":
            return ""  # 简单寒暄完全删除
        elif filter_reason == "too_short":
            return ""  # 太短的内容完全删除
        elif filter_reason == "empty":
            return ""
        
        return ""
    
    def _clean_urls_from_content(self, content: str) -> str:
        """
        从内容中清理URL，但保留其他文本
        
        对于URL占比不高的内容，只清理URL部分
        """
        cleaned = self.URL_PATTERN.sub("[链接]", content)
        return cleaned
    
    def _store_filtered_content(
        self,
        filtered_out: List[FilteredContent],
        chat_id: Optional[str],
        user_id: Optional[str]
    ) -> Optional[str]:
        """
        将过滤的内容存储到磁盘
        
        Returns:
            存储文件路径
        """
        try:
            # 生成文件名 - 使用单一时间戳确保一致性
            current_time = datetime.now(timezone.utc)
            timestamp = current_time.strftime("%Y%m%d_%H%M%S")
            identifier = f"{chat_id or 'unknown'}_{user_id or 'unknown'}"
            hash_suffix = hashlib.md5(identifier.encode()).hexdigest()[:8]
            filename = f"filtered_{timestamp}_{hash_suffix}.json"
            
            filepath = self.storage_dir / filename
            
            # 准备存储数据
            storage_data = {
                "chat_id": chat_id,
                "user_id": user_id,
                "timestamp": current_time.isoformat(),
                "filtered_count": len(filtered_out),
                "items": [asdict(item) for item in filtered_out]
            }
            
            # 写入文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(storage_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"📁 [HistoryFilter] Stored filtered content to: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.warning(f"⚠️ [HistoryFilter] Failed to store filtered content: {e}")
            return None
    
    def retrieve_filtered_content(
        self,
        chat_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        检索之前过滤的内容
        
        Args:
            chat_id: 对话ID过滤条件
            user_id: 用户ID过滤条件
            limit: 返回结果数量限制
            
        Returns:
            过滤内容记录列表
        """
        if not self.storage_dir.exists():
            return []
        
        results = []
        
        try:
            # 获取所有存储文件，按时间倒序
            files = sorted(
                self.storage_dir.glob("filtered_*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            for filepath in files[:limit * 2]:  # 多读一些以便过滤
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 检查过滤条件
                    if chat_id and data.get("chat_id") != chat_id:
                        continue
                    if user_id and data.get("user_id") != user_id:
                        continue
                    
                    results.append(data)
                    
                    if len(results) >= limit:
                        break
                        
                except Exception as e:
                    logger.warning(f"⚠️ Failed to read filtered content file {filepath}: {e}")
                    continue
            
        except Exception as e:
            logger.warning(f"⚠️ [HistoryFilter] Failed to retrieve filtered content: {e}")
        
        return results
    
    def extract_urls(self, content: str) -> List[str]:
        """
        从内容中提取所有URL
        
        Args:
            content: 文本内容
            
        Returns:
            URL列表
        """
        return self.URL_PATTERN.findall(content)
    
    def is_url_dominated(self, content: str) -> bool:
        """
        检查内容是否主要由URL组成
        
        Args:
            content: 文本内容
            
        Returns:
            是否URL主导
        """
        if not content or not content.strip():
            return False
        
        urls = self.extract_urls(content)
        if not urls:
            return False
        
        url_length = sum(len(url) for url in urls)
        return url_length / len(content.strip()) >= self.url_content_threshold


# 全局过滤器实例
_history_filter: Optional[HistoryFilter] = None


def get_history_filter() -> HistoryFilter:
    """获取全局历史过滤器实例"""
    global _history_filter
    
    if _history_filter is None:
        _history_filter = HistoryFilter()
    
    return _history_filter
