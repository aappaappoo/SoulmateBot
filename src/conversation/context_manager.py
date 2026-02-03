"""
Context Manager - 上下文窗口管理

管理对话的上下文窗口，包括：
- Token限制管理
- 智能截断
- 重要信息保留
"""
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class ContextWindow:
    """
    上下文窗口
    
    管理LLM的上下文窗口大小，智能截断历史消息
    
    Attributes:
        max_tokens: 最大token数
        reserved_tokens: 为输出保留的token数
        system_prompt: 系统提示词
        messages: 对话消息列表
    """
    max_tokens: int = 4096
    reserved_tokens: int = 1000
    system_prompt: str = ""
    messages: List[Dict[str, str]] = field(default_factory=list)

    @property
    def available_tokens(self) -> int:
        """可用于对话的token数"""
        return self.max_tokens - self.reserved_tokens

    def _estimate_tokens(self, text: str) -> int:
        """估算文本的token数"""
        # 简单估算：中文约1.5字符/token，英文约4字符/token
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)

    def _estimate_message_tokens(self, message: Dict[str, str]) -> int:
        """估算消息的token数"""
        # 消息格式开销 + 内容
        content = message.get("content", "")
        return self._estimate_tokens(content) + 4  # 4 tokens for message format overhead

    def get_total_tokens(self) -> int:
        """计算当前上下文的总token数"""
        total = self._estimate_tokens(self.system_prompt) if self.system_prompt else 0
        for msg in self.messages:
            total += self._estimate_message_tokens(msg)
        return total

    def add_message(self, role: str, content: str) -> bool:
        """
        添加消息到上下文
        
        Args:
            role: 消息角色
            content: 消息内容
            
        Returns:
            True如果成功添加，False如果需要截断
        """
        message = {"role": role, "content": content}
        message_tokens = self._estimate_message_tokens(message)

        # 检查是否需要截断
        while self.get_total_tokens() + message_tokens > self.available_tokens:
            if len(self.messages) <= 1:
                # 只剩最后一条消息，无法再截断
                logger.warning("Context window full, cannot add message")
                return False

            # 移除最早的非系统消息
            self.messages.pop(0)
            logger.debug("Removed oldest message to fit context window")

        self.messages.append(message)
        return True

    def set_system_prompt(self, prompt: str) -> None:
        """设置系统提示词"""
        self.system_prompt = prompt

    def get_messages_for_llm(self, include_system: bool = True) -> List[Dict[str, str]]:
        """
        获取适用于LLM API的消息列表

        Args:
            include_system: 是否包含 system prompt（默认 True，兼容旧代码）
        """
        messages = []

        if include_system and self.system_prompt:
            messages.append({
                "role": "system",
                "content": self.system_prompt
            })

        # 只返回 user 和 assistant 消息
        for msg in self.messages:
            if msg.get("role") in ("user", "assistant"):
                messages.append(msg)

        return messages

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """
        获取纯对话历史（不包含 system prompt）
        """
        return [msg for msg in self.messages if msg.get("role") in ("user", "assistant")]

    def clear(self) -> None:
        """清空消息"""
        self.messages = []

    def truncate_to_fit(self, target_tokens: Optional[int] = None) -> int:
        """
        截断消息以适应token限制
        
        Args:
            target_tokens: 目标token数（默认使用available_tokens）
            
        Returns:
            移除的消息数
        """
        target = target_tokens or self.available_tokens
        removed = 0

        while self.get_total_tokens() > target and len(self.messages) > 1:
            self.messages.pop(0)
            removed += 1

        if removed > 0:
            logger.info(f"Truncated {removed} messages to fit context window")

        return removed


class ContextManager:
    """
    上下文管理器
    
    管理多个用户/会话的上下文窗口
    """

    def __init__(
            self,
            default_max_tokens: int = 4096,
            default_reserved_tokens: int = 1000
    ):
        """
        初始化上下文管理器
        
        Args:
            default_max_tokens: 默认最大token数
            default_reserved_tokens: 默认保留token数
        """
        self.default_max_tokens = default_max_tokens
        self.default_reserved_tokens = default_reserved_tokens

        # 上下文存储: context_id -> ContextWindow
        self._contexts: Dict[str, ContextWindow] = {}

        # 模型上下文限制表
        self._model_limits = {
            "gpt-4": 8192,
            "gpt-4-turbo": 128000,
            "gpt-4o": 128000,
            "gpt-4o-mini": 128000,
            "gpt-3.5-turbo": 16385,
            "claude-3-opus": 200000,
            "claude-3-sonnet": 200000,
            "claude-3-haiku": 200000,
            "default": 4096
        }

    def _generate_context_id(self, user_id: str, bot_id: str) -> str:
        """生成上下文ID"""
        return f"{user_id}:{bot_id}"

    def get_model_limit(self, model: str) -> int:
        """获取模型的上下文限制"""
        model_lower = model.lower()

        # Sort keys by length (longest first) to prioritize more specific matches
        sorted_keys = sorted(self._model_limits.keys(), key=len, reverse=True)

        for key in sorted_keys:
            if key in model_lower:
                return self._model_limits[key]

        return self._model_limits.get("default", 4096)

    def create_context(
            self,
            user_id: str,
            bot_id: str,
            model: Optional[str] = None,
            system_prompt: str = ""
    ) -> ContextWindow:
        """
        创建上下文窗口
        
        Args:
            user_id: 用户ID
            bot_id: Bot ID
            model: 模型名称（用于确定上下文大小）
            system_prompt: 系统提示词
            
        Returns:
            新创建的上下文窗口
        """
        context_id = self._generate_context_id(user_id, bot_id)

        max_tokens = self.get_model_limit(model) if model else self.default_max_tokens

        context = ContextWindow(
            max_tokens=max_tokens,
            reserved_tokens=self.default_reserved_tokens,
            system_prompt=system_prompt
        )

        self._contexts[context_id] = context
        logger.debug(f"Created context: {context_id} (max_tokens={max_tokens})")

        return context

    def get_context(self, user_id: str, bot_id: str) -> Optional[ContextWindow]:
        """获取上下文窗口"""
        context_id = self._generate_context_id(user_id, bot_id)
        return self._contexts.get(context_id)

    def get_or_create_context(
            self,
            user_id: str,
            bot_id: str,
            model: Optional[str] = None,
            system_prompt: str = ""
    ) -> ContextWindow:
        """获取或创建上下文窗口"""
        context = self.get_context(user_id, bot_id)
        if context is None:
            context = self.create_context(user_id, bot_id, model, system_prompt)
        return context

    def delete_context(self, user_id: str, bot_id: str) -> bool:
        """删除上下文窗口"""
        context_id = self._generate_context_id(user_id, bot_id)
        if context_id in self._contexts:
            del self._contexts[context_id]
            logger.debug(f"Deleted context: {context_id}")
            return True
        return False

    def add_message(
            self,
            user_id: str,
            bot_id: str,
            role: str,
            content: str,
            model: Optional[str] = None,
            system_prompt: str = ""
    ) -> bool:
        """
        向上下文添加消息
        
        自动创建上下文（如果不存在）
        
        Returns:
            True如果成功添加
        """
        context = self.get_or_create_context(user_id, bot_id, model, system_prompt)
        return context.add_message(role, content)

    def get_messages_for_llm(
            self,
            user_id: str,
            bot_id: str,
            include_new_message: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        获取适用于LLM的消息列表
        
        Args:
            user_id: 用户ID
            bot_id: Bot ID
            include_new_message: 如果提供，会添加这条新消息
            
        Returns:
            消息列表
        """
        context = self.get_context(user_id, bot_id)
        if context is None:
            if include_new_message:
                return [{"role": "user", "content": include_new_message}]
            return []

        if include_new_message:
            context.add_message("user", include_new_message)

        return context.get_messages_for_llm()

    def clear_context(self, user_id: str, bot_id: str) -> None:
        """清空上下文消息"""
        context = self.get_context(user_id, bot_id)
        if context:
            context.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_contexts = len(self._contexts)
        total_messages = sum(len(c.messages) for c in self._contexts.values())
        total_tokens = sum(c.get_total_tokens() for c in self._contexts.values())

        return {
            "total_contexts": total_contexts,
            "total_messages": total_messages,
            "total_tokens_estimated": total_tokens
        }


# 全局上下文管理器实例
_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """获取全局上下文管理器"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
