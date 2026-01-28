"""
Unified Context Builder - 统一上下文构建器

负责构建发送给 LLM 的完整消息结构，采用分层方式：

消息结构：
1. System Prompt（包含人设 + 长期记忆 + 对话策略）
2. 短期对话历史（最近 3-5 轮完整内容）
3. 当前用户消息

功能：
- 分割历史（短期 vs 中期）
- 生成中期摘要（支持缓存）
- 整合所有上下文
- 构建最终消息列表
- Token 预算管理
"""
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from loguru import logger

from .summary_service import ConversationSummaryService, ConversationSummary
from .proactive_strategy import (
    ProactiveDialogueStrategyAnalyzer,
    ProactiveAction,
    UserProfile,
    TopicAnalysis
)


@dataclass
class ContextConfig:
    """
    上下文配置
    
    用于控制上下文构建的各项参数
    """
    # 对话历史分层
    short_term_rounds: int = 5  # 短期历史轮数（最近 N 轮）
    mid_term_start: int = 3  # 中期历史开始轮次
    mid_term_end: int = 20  # 中期历史结束轮次
    
    # 长期记忆
    max_memories: int = 8  # 最多包含的长期记忆数量
    
    # Token 预算
    max_total_tokens: int = 8000  # 总 token 预算
    reserved_output_tokens: int = 1000  # 为输出保留的 token
    
    # 摘要选项
    use_llm_summary: bool = False  # 是否使用 LLM 摘要（消耗 token）
    max_summary_length: int = 200  # 摘要最大长度
    
    # 主动策略
    enable_proactive_strategy: bool = True  # 是否启用主动策略


@dataclass
class BuilderResult:
    """
    构建器结果
    
    包含构建好的消息列表和元数据
    """
    messages: List[Dict[str, str]]  # 完整的消息列表
    token_estimate: int  # 估算的 token 数
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据


class UnifiedContextBuilder:
    """
    统一上下文构建器
    
    核心职责：
    1. 将对话历史分层（短期、中期、长期）
    2. 生成中期对话摘要
    3. 构建增强的 System Prompt
    4. 整合所有组件到最终消息列表
    5. 管理 token 预算
    """
    
    def __init__(
        self,
        summary_service: Optional[ConversationSummaryService] = None,
        proactive_analyzer: Optional[ProactiveDialogueStrategyAnalyzer] = None,
        config: Optional[ContextConfig] = None
    ):
        """
        初始化构建器
        
        Args:
            summary_service: 摘要服务（可选，默认创建）
            proactive_analyzer: 主动策略分析器（可选，默认创建）
            config: 配置（可选，使用默认配置）
        """
        self.summary_service = summary_service or ConversationSummaryService()
        self.proactive_analyzer = proactive_analyzer or ProactiveDialogueStrategyAnalyzer()
        self.config = config or ContextConfig()
        
        logger.debug("UnifiedContextBuilder 初始化完成")
    
    async def build_context(
        self,
        bot_system_prompt: str,
        conversation_history: List[Dict[str, str]],
        current_message: str,
        user_memories: Optional[List[Dict[str, Any]]] = None,
        dialogue_strategy: Optional[str] = None
    ) -> BuilderResult:
        """
        构建完整的对话上下文
        
        Args:
            bot_system_prompt: Bot 的原始人设
            conversation_history: 完整对话历史（不包含 system prompt）
            current_message: 当前用户消息
            user_memories: 用户长期记忆列表（可选）
            dialogue_strategy: 已生成的对话策略（可选，如果提供则不重新生成）
            
        Returns:
            BuilderResult: 包含消息列表和元数据
        """
        logger.debug(f"开始构建上下文，历史消息数: {len(conversation_history)}")
        
        # 1. 分割对话历史
        short_term, mid_term = self._split_history(conversation_history)
        logger.debug(f"历史分割: 短期={len(short_term)}条, 中期={len(mid_term)}条")
        
        # 2. 生成中期摘要（如果有中期对话）
        mid_term_summary = None
        if mid_term:
            mid_term_summary = await self.summary_service.summarize_conversations(
                mid_term,
                use_llm=self.config.use_llm_summary,
                max_summary_length=self.config.max_summary_length
            )
            logger.debug(f"中期摘要: {mid_term_summary.summary_text[:50]}...")
        
        # 3. 格式化长期记忆
        memory_context = self._format_memories(user_memories)
        
        # 4. 生成主动策略（如果启用）
        proactive_guidance = ""
        if self.config.enable_proactive_strategy:
            proactive_guidance = await self._generate_proactive_guidance(
                conversation_history, user_memories
            )
        
        # 5. 构建增强的 System Prompt
        enhanced_system_prompt = self._build_enhanced_system_prompt(
            bot_system_prompt=bot_system_prompt,
            memory_context=memory_context,
            mid_term_summary=mid_term_summary,
            dialogue_strategy=dialogue_strategy,
            proactive_guidance=proactive_guidance
        )
        
        # 6. 构建最终消息列表
        messages = self._build_messages(
            enhanced_system_prompt,
            short_term,
            current_message
        )
        
        # 7. 估算 token 使用
        token_estimate = self._estimate_tokens(messages)
        
        # 8. 检查 token 预算
        if token_estimate > (self.config.max_total_tokens - self.config.reserved_output_tokens):
            logger.warning(f"Token 使用 ({token_estimate}) 超过预算，进行截断")
            messages = self._truncate_messages(messages)
            token_estimate = self._estimate_tokens(messages)
        
        logger.info(f"上下文构建完成: {len(messages)}条消息, 估算token={token_estimate}")
        
        return BuilderResult(
            messages=messages,
            token_estimate=token_estimate,
            metadata={
                "short_term_count": len(short_term),
                "mid_term_count": len(mid_term),
                "has_mid_term_summary": mid_term_summary is not None,
                "memory_count": len(user_memories) if user_memories else 0,
                "has_proactive_guidance": bool(proactive_guidance)
            }
        )
    
    def _split_history(
        self,
        conversation_history: List[Dict[str, str]]
    ) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
        """
        分割对话历史为短期和中期
        
        短期：最近 N 轮（config.short_term_rounds）
        中期：第 M 到 N 轮（config.mid_term_start 到 config.mid_term_end）
        
        Returns:
            (short_term, mid_term): 短期历史和中期历史
        """
        if not conversation_history:
            return [], []
        
        # 短期：取最后 N 条
        short_term = conversation_history[-self.config.short_term_rounds * 2:]  # *2 因为包含user和assistant
        
        # 中期：取中间部分
        # 先排除短期部分
        remaining = conversation_history[:-len(short_term)] if len(short_term) > 0 else conversation_history
        
        # 计算中期范围（基于用户消息轮数）
        # 找到第 mid_term_start 轮到 mid_term_end 轮的消息
        user_turn_indices = []
        for i, msg in enumerate(remaining):
            if msg.get("role") == "user":
                user_turn_indices.append(i)
        
        # 如果有足够的历史，提取中期
        if len(user_turn_indices) >= self.config.mid_term_start:
            start_idx = user_turn_indices[self.config.mid_term_start - 1] if self.config.mid_term_start > 0 else 0
            end_idx = user_turn_indices[min(self.config.mid_term_end - 1, len(user_turn_indices) - 1)]
            mid_term = remaining[start_idx:end_idx + 1]
        else:
            mid_term = []
        
        return short_term, mid_term
    
    def _format_memories(self, user_memories: Optional[List[Dict[str, Any]]]) -> str:
        """
        格式化长期记忆为文本
        
        Args:
            user_memories: 用户记忆列表
            
        Returns:
            格式化的记忆文本
        """
        if not user_memories:
            return ""
        
        # 最多取 max_memories 条
        memories_to_use = user_memories[:self.config.max_memories]
        
        memory_lines = ["【关于这位用户的记忆】"]
        for memory in memories_to_use:
            summary = memory.get("event_summary", "")
            event_date = memory.get("event_date")
            
            if event_date:
                memory_lines.append(f"- 用户在{event_date}表示{summary}")
            else:
                memory_lines.append(f"- {summary}")
        
        return "\n".join(memory_lines)
    
    async def _generate_proactive_guidance(
        self,
        conversation_history: List[Dict[str, str]],
        user_memories: Optional[List[Dict[str, Any]]]
    ) -> str:
        """
        生成主动对话策略指导
        
        Args:
            conversation_history: 对话历史
            user_memories: 用户记忆
            
        Returns:
            主动策略文本
        """
        try:
            # 构建用户画像
            user_profile = self.proactive_analyzer.analyze_user_profile(
                conversation_history, user_memories
            )
            
            # 分析话题
            topic_analysis = self.proactive_analyzer.analyze_topic(
                conversation_history, user_profile
            )
            
            # 生成主动策略
            proactive_action = self.proactive_analyzer.generate_proactive_strategy(
                user_profile, topic_analysis, conversation_history, user_memories
            )
            
            # 格式化为文本
            guidance = self.proactive_analyzer.format_proactive_guidance(proactive_action)
            
            # 添加用户画像信息
            profile_info = f"""
【当前对话情境】
- 用户参与度：{user_profile.engagement_level.value}
- 用户情绪：{user_profile.emotional_state}
- 关系深度：{user_profile.relationship_depth}/5
- 用户兴趣：{', '.join(user_profile.interests[:3]) if user_profile.interests else '待探索'}
- 可探索话题：{', '.join(topic_analysis.topics_to_explore[:3]) if topic_analysis.topics_to_explore else '无'}
"""
            
            return profile_info + "\n" + guidance
            
        except Exception as e:
            logger.warning(f"生成主动策略失败: {e}")
            return ""
    
    def _build_enhanced_system_prompt(
        self,
        bot_system_prompt: str,
        memory_context: str,
        mid_term_summary: Optional[ConversationSummary],
        dialogue_strategy: Optional[str],
        proactive_guidance: str
    ) -> str:
        """
        构建增强的 System Prompt
        
        结构：
        1. 原始人设
        2. 长期记忆
        3. 中期对话摘要
        4. 对话策略
        5. 主动策略
        
        Args:
            bot_system_prompt: 原始人设
            memory_context: 长期记忆文本
            mid_term_summary: 中期摘要
            dialogue_strategy: 对话策略
            proactive_guidance: 主动策略
            
        Returns:
            增强后的 system prompt
        """
        components = [bot_system_prompt]
        
        # 添加长期记忆
        if memory_context:
            components.append(memory_context)
        
        # 添加中期对话摘要
        if mid_term_summary:
            summary_text = f"""
【本次对话回顾】
{mid_term_summary.summary_text}
讨论话题：{', '.join(mid_term_summary.key_topics[:3])}
"""
            if mid_term_summary.emotion_trajectory:
                summary_text += f"情绪变化：{mid_term_summary.emotion_trajectory}\n"
            
            components.append(summary_text.strip())
        
        # 添加主动策略（在对话策略之前）
        if proactive_guidance:
            components.append(proactive_guidance)
        
        # 添加对话策略（如果提供）
        if dialogue_strategy:
            components.append(dialogue_strategy)
        
        # 用双换行符连接所有组件
        enhanced_prompt = "\n\n".join(components)
        
        return enhanced_prompt
    
    def _build_messages(
        self,
        system_prompt: str,
        short_term_history: List[Dict[str, str]],
        current_message: str
    ) -> List[Dict[str, str]]:
        """
        构建最终消息列表
        
        结构：
        1. System message (enhanced prompt)
        2. Short-term history
        3. Current user message
        
        Args:
            system_prompt: 增强的 system prompt
            short_term_history: 短期历史
            current_message: 当前消息
            
        Returns:
            完整的消息列表
        """
        messages = []
        
        # 1. System prompt
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # 2. Short-term history
        messages.extend(short_term_history)
        
        # 3. Current message
        messages.append({
            "role": "user",
            "content": current_message
        })
        
        return messages
    
    def _estimate_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        估算消息列表的 token 数
        
        简单估算：中文约1.5字符/token，英文约4字符/token
        """
        total_tokens = 0
        
        for msg in messages:
            content = msg.get("content", "")
            
            # 统计中文字符
            chinese_chars = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
            other_chars = len(content) - chinese_chars
            
            # 估算
            tokens = int(chinese_chars / 1.5 + other_chars / 4)
            
            # 消息格式开销
            total_tokens += tokens + 4
        
        return total_tokens
    
    def _truncate_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        截断消息以适应 token 预算
        
        策略：
        1. 保留 system prompt
        2. 保留当前用户消息
        3. 从短期历史中移除最早的消息
        
        Args:
            messages: 原始消息列表
            
        Returns:
            截断后的消息列表
        """
        if len(messages) <= 2:
            # 只有 system 和当前消息，无法再截断
            return messages
        
        # 分离组件
        system_msg = messages[0] if messages[0].get("role") == "system" else None
        current_msg = messages[-1] if messages[-1].get("role") == "user" else None
        history = messages[1:-1] if len(messages) > 2 else []
        
        # 逐步移除历史消息直到满足预算
        budget = self.config.max_total_tokens - self.config.reserved_output_tokens
        
        while history and self._estimate_tokens([system_msg] + history + [current_msg]) > budget:
            history.pop(0)
            logger.debug(f"移除一条历史消息，剩余: {len(history)}")
        
        # 重新组合
        result = []
        if system_msg:
            result.append(system_msg)
        result.extend(history)
        if current_msg:
            result.append(current_msg)
        
        return result
    
    def get_token_budget_info(self, result: BuilderResult) -> Dict[str, Any]:
        """
        获取 token 预算使用情况
        
        Args:
            result: 构建结果
            
        Returns:
            预算信息字典
        """
        return {
            "estimated_tokens": result.token_estimate,
            "max_tokens": self.config.max_total_tokens,
            "reserved_for_output": self.config.reserved_output_tokens,
            "available_for_context": self.config.max_total_tokens - self.config.reserved_output_tokens,
            "usage_percentage": (result.token_estimate / (self.config.max_total_tokens - self.config.reserved_output_tokens)) * 100
        }
