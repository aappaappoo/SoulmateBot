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
- 历史对话过滤（URL、简单寒暄等）
"""
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from loguru import logger

from .summary_service import ConversationSummaryService, ConversationSummary
from .proactive_strategy import (
    ProactiveDialogueStrategyAnalyzer,
)
from src.utils.history_filter import HistoryFilter, get_history_filter

@dataclass
class ContextConfig:
    """
    上下文配置
    
    用于控制上下文构建的各项参数
    """
    # 对话历史分层
    short_term_rounds: int = 5  # 短期历史轮数（最近 N 轮）
    mid_term_start: int = 5  # 中期历史开始轮次
    mid_term_end: int = 20  # 中期历史结束轮次

    # 长期记忆
    max_memories: int = 10  # 最多包含的长期记忆数量

    # Token 预算
    max_total_tokens: int = 8000  # 总 token 预算
    reserved_output_tokens: int = 1000  # 为输出保留的 token

    # 摘要选项
    use_llm_summary: bool = False  # 是否使用 LLM 摘要（消耗 token）
    max_summary_length: int = 200  # 摘要最大长度

    # 主动策略
    enable_proactive_strategy: bool = True  # 是否启用主动策略

    # 历史过滤选项
    enable_history_filter: bool = True  # 是否启用历史过滤（过滤URL、简单寒暄等）


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
    6. 过滤不重要的历史内容（URL、简单寒暄等）
    """

    def __init__(
            self,
            summary_service: Optional[ConversationSummaryService] = None,
            proactive_analyzer: Optional[ProactiveDialogueStrategyAnalyzer] = None,
            history_filter: Optional[HistoryFilter] = None,
            config: Optional[ContextConfig] = None
    ):
        """
        初始化构建器
        
        Args:
            summary_service: 摘要服务（可选，默认创建）
            proactive_analyzer: 主动策略分析器（可选，默认创建）
            history_filter: 历史过滤器（可选，默认使用全局实例）
            config: 配置（可选，使用默认配置）
        """
        self.summary_service = summary_service or ConversationSummaryService()
        self.proactive_analyzer = proactive_analyzer or ProactiveDialogueStrategyAnalyzer()
        self.config = config or ContextConfig()

        # 初始化历史过滤器
        if history_filter:
            self.history_filter = history_filter
        elif self.config.enable_history_filter:
            self.history_filter = get_history_filter()
        else:
            self.history_filter = None

    async def build_context(
            self,
            bot_system_prompt: str,
            conversation_history: List[Dict[str, str]],
            current_message: str,
            user_memories: Optional[List[Dict[str, Any]]] = None,
            dialogue_strategy: Optional[str] = None,
            llm_generated_summary: Optional[Dict] = None,  # 新增参数
            chat_id: Optional[str] = None,  # 用于历史过滤存储
            user_id: Optional[str] = None,  # 用于历史过滤存储
            persona: Optional[Any] = None  # ← 新增
    ) -> BuilderResult:
        """
        构建完整的对话上下文
        
        Args:
            bot_system_prompt: Bot 的原始人设
            conversation_history: 完整对话历史（不包含 system prompt）
            current_message: 当前用户消息
            user_memories: 用户长期记忆列表（可选）
            dialogue_strategy: 已生成的对话策略（可选，如果提供则不重新生成）
            llm_generated_summary: LLM 生成的对话摘要（可选）
            chat_id: 对话ID（可选，用于历史过滤存储）
            user_id: 用户ID（可选，用于历史过滤存储）
            
        Returns:
            BuilderResult: 包含消息列表和元数据
        """
        logger.debug(f"🔍 开始构建上下文，历史消息数: {len(conversation_history)}")

        # 0. 应用历史过滤（过滤URL、简单寒暄等）
        filtered_count = 0
        if self.history_filter and self.config.enable_history_filter:
            filter_result = self.history_filter.filter_history(
                conversation_history,
                chat_id=chat_id,
                user_id=user_id
            )
            conversation_history = filter_result.filtered_history
            filtered_count = len(filter_result.filtered_out)
            if filtered_count > 0:
                logger.debug(f"🔍 过滤了 {filtered_count} 条不重要的历史消息")

        # 1. 分割对话历史
        short_term, mid_term = self._split_history(conversation_history)
        logger.debug(f"分割对话历史: 短期={len(short_term)}条, 中期={len(mid_term)}条")

        # 2. 生成中期摘要（如果有中期对话）
        mid_term_summary = None
        if mid_term:
            mid_term_summary = await self.summary_service.summarize_conversations(
                mid_term,
                use_llm=self.config.use_llm_summary,
                max_summary_length=self.config.max_summary_length
            )
            logger.debug(f"生成中期摘要: {mid_term_summary.summary_text[:50]}...")

        # 3. 格式化长期记忆
        memory_context = self._format_memories(user_memories)

        # 4. 生成主动策略（如果启用）
        proactive_guidance = ""
        if self.config.enable_proactive_strategy:
            proactive_guidance = await self._generate_proactive_guidance(
                conversation_history, user_memories
            )

        # 5. 构建增强的 System Prompt（包含对话历史）
        enhanced_system_prompt = self._build_enhanced_system_prompt(
            bot_system_prompt=bot_system_prompt,
            memory_context=memory_context,
            mid_term_summary=mid_term_summary,
            llm_generated_summary=llm_generated_summary,  # 传递 LLM 摘要
            dialogue_strategy=dialogue_strategy,
            proactive_guidance=proactive_guidance,
            short_term_history=short_term,
            persona=persona
        )
        # 6. 构建最终消息列表（仅 system + user 两条消息）
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

        logger.info(f"上下文构建完成: {len(messages)}条消息, 估算token={token_estimate}, 过滤了{filtered_count}条")

        return BuilderResult(
            messages=messages,
            token_estimate=token_estimate,
            metadata={
                "short_term_count": len(short_term),
                "mid_term_count": len(mid_term),
                "has_mid_term_summary": mid_term_summary is not None,
                "memory_count": len(user_memories) if user_memories else 0,
                "has_proactive_guidance": bool(proactive_guidance),
                "filtered_history_count": filtered_count,
                "history_filter_enabled": self.config.enable_history_filter
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

        # 计算短期历史的消息数量
        # 注意：一轮对话通常包含一条用户消息和一条助手消息
        # 但我们按实际消息数计算，不假设每轮恰好两条
        user_messages = [msg for msg in conversation_history if msg.get("role") == "user"]
        num_user_messages = len(user_messages)

        # 短期：取最近 N 轮对话（基于用户消息数）
        if num_user_messages <= self.config.short_term_rounds:
            # 所有历史都是短期
            return conversation_history, []

        # 找到倒数第 N 条用户消息的位置
        user_msg_indices = [i for i, msg in enumerate(conversation_history) if msg.get("role") == "user"]
        short_term_start_idx = user_msg_indices[-self.config.short_term_rounds]

        # 短期历史从该位置到结尾
        short_term = conversation_history[short_term_start_idx:]

        # 剩余的历史（不包括短期部分）
        remaining = conversation_history[:short_term_start_idx]

        if not remaining:
            return short_term, []
        remaining_user_indices = [i for i, msg in enumerate(remaining) if msg.get("role") == "user"]
        num_remaining_users = len(remaining_user_indices)
        # 我们应该从 remaining 的末尾开始
        # 简化理解：中期就是 remaining 中最近的 (mid_term_end - short_term_rounds) 轮
        mid_term_rounds = min(
            self.config.mid_term_end - self.config.short_term_rounds,
            num_remaining_users
        )

        if mid_term_rounds > 0:
            mid_term_start_idx = remaining_user_indices[-mid_term_rounds]
            mid_term = remaining[mid_term_start_idx:]
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

        # 长期记忆提取逻辑
        memories_to_use = user_memories[:self.config.max_memories]
        memory_lines = ["【关于这位用户的记忆】"]
        for memory in memories_to_use:
            summary = memory.get("event_summary", "")
            event_date = memory.get("event_date")
            if event_date:
                event_summary = f"- 用户在{event_date}时间表示{summary}"
            else:
                event_summary = f"- {summary}"
            if event_summary not in memory_lines:
                memory_lines.append(event_summary)
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

    #
    def _build_enhanced_system_prompt(
            self,
            bot_system_prompt: str,
            memory_context: str,
            mid_term_summary: Optional[ConversationSummary],
            llm_generated_summary: Optional[Dict] = None,  # 新增：LLM 生成的摘要
            dialogue_strategy: Optional[str] = None,
            proactive_guidance: str = "",
            short_term_history: Optional[List[Dict[str, str]]] = None,
            persona: Optional[Any] = None
    ) -> str:
        """
        构建增强的 System Prompt
        """
        components = [bot_system_prompt]

        # ====================  整合所有记忆到一个块 ====================
        memory_sections = []

        # 1. 长期历史重要记忆
        if memory_context:
            # memory_context 已经是 "【关于这位用户的记忆】\n- xxx\n- xxx" 格式
            # 去掉原有标题，只保留内容
            memory_lines = memory_context.split('\n')
            if memory_lines and memory_lines[0].startswith('【'):
                memory_lines = memory_lines[1:]  # 去掉第一行标题
            if memory_lines:
                memory_sections.append("【历史重要记忆】\n" + '\n'.join(memory_lines))

        # 2. 中期摘要记忆
        summary_text = ""
        if llm_generated_summary and isinstance(llm_generated_summary, dict):
            key_elements = llm_generated_summary.get('key_elements', {})
            if not isinstance(key_elements, dict):
                key_elements = {}

            def format_list(items):
                return ', '.join(items) if items else '无'

            summary_text = f"""【中期摘要记忆】
{llm_generated_summary.get('summary_text', '')}
关键要素：时间={format_list(key_elements.get('time', []))}，地点={format_list(key_elements.get('place', []))}，人物={format_list(key_elements.get('people', []))}
话题：{format_list(llm_generated_summary.get('topics', []))}
用户状态：{llm_generated_summary.get('user_state', '')}"""
        elif mid_term_summary:
            summary_text = f"""【中期摘要记忆】
{mid_term_summary.summary_text}
讨论话题：{', '.join(mid_term_summary.key_topics[:3])}"""
            if mid_term_summary.emotion_trajectory:
                summary_text += f"\n情绪变化：{mid_term_summary.emotion_trajectory}"
        if summary_text:
            memory_sections.append(summary_text.strip())

        # 3. 近期对话记录
        if short_term_history:
            history_text = self._format_history_for_system_prompt(short_term_history)
            if history_text:
                # 替换原有标题为统一格式
                history_text = history_text.replace(
                    "【历史对话 - 仅参考，禁止模仿格式】",
                    "【近期对话记录｜由下往上对应的时间是从远到近】"
                )
                memory_sections.append(history_text)

        # 整合所有记忆到一个块
        if memory_sections:
            unified_memory_block = """
=========================
对话相关记忆
=========================
""" + "\n\n".join(memory_sections)
            components.append(unified_memory_block)

        # ==================== 对话策略管理（整合块） ====================
        strategy_sections = []

        # 1. 当前对话情境（从 proactive_guidance 中提取）
        if proactive_guidance:
            strategy_sections.append(proactive_guidance.strip())

        if dialogue_strategy:
            strategy_sections.append(dialogue_strategy.strip())
        if persona and hasattr(persona, 'emotional_response') and persona.emotional_response:
            p = persona
            emotion_sections = []
            emotion_sections.append("【情绪应对策略】")
            if p.emotional_response.get("user_sad"):
                lines = '\n - '.join(p.emotional_response['user_sad'])
                emotion_sections.append(f"当用户难过时：\n - {lines}")
            if p.emotional_response.get("user_angry"):
                lines = '\n - '.join(p.emotional_response['user_angry'])
                emotion_sections.append(f"当用户生气时：\n - {lines}")
            if p.emotional_response.get("user_happy"):
                lines = '\n - '.join(p.emotional_response['user_happy'])
                emotion_sections.append(f"当用户开心时：\n - {lines}")
            if len(emotion_sections) > 1:
                strategy_sections.append('\n'.join(emotion_sections))

        if strategy_sections:
            unified_strategy_block = """
=========================
对话策略管理
=========================
'【安全对话策略】\n'
'**需要主动回避的话题**：'
'-政治话题'
'-歧视内容'
'-暴力内容'
'-未成年性内容'
'-人身攻击'
'**高度警惕要求主动关闭话题的关键词**：'
'-自杀'
'-抑郁'
'-谋杀'
'**特殊的响应策略**：'
'-遇到严肃问题收起幽默'
'-表达真诚的关心'
'-不用幽默掩盖严重问题\n'
"""
            unified_strategy_block += "\n\n".join(strategy_sections)
            components.append(unified_strategy_block)
        json_format_instruction = self._get_json_format_instruction()
        components.append(json_format_instruction)
        enhanced_prompt = "\n\n".join(components)
        return enhanced_prompt

    def _format_history_for_system_prompt(
            self,
            short_term_history: List[Dict[str, str]]
    ) -> str:
        """
        将短期对话历史格式化为嵌入 system prompt 的文本
        使用特殊标记防止 LLM 模仿此格式输出
        Args:
            short_term_history: 短期对话历史
        Returns:
            格式化的历史文本
        """
        if not short_term_history:
            return ""

        history_lines = []
        for msg in short_term_history:
            role = msg.get("role", "").lower()
            content = msg.get("content", "")
            if role == "user":
                history_lines.append(f"User: {content}")
            elif role == "assistant":
                content = content.replace("[MSG_SPLIT]", "")
                history_lines.append(f"Assistant: {content}")
        if not history_lines:
            return ""

        history_text = """
【历史对话 - 仅参考，禁止模仿格式】
<history>
""" + "\n".join(history_lines) + """
</history>
⚠️ 注意：上方历史仅用于理解上下文，你的输出必须是JSON"""
        return history_text

    def _get_json_format_instruction(self) -> str:
        """
        获取强制 JSON 格式输出指令
        
        Returns:
            JSON 格式指令文本
        """
        return """
=========================
强制输出格式
=========================   
你必须且只能返回以下JSON格式，不要添加任何其他文本：
```json
    {{
    "intent": "direct_response" | "single_agent" | "multi_agent",
    "agents": [],
    "reasoning": "判断理由",
    
    "conversation_summary": {{
        "summary_text": "综合整个对话的摘要文本（100字以内）",
        "key_elements": {{
            "time": ["时间点1", "时间点2"],
            "place": ["地点1", "地点2"],
            "people": ["人物1", "人物2"],
            "events": ["事件1", "事件2"],
            "emotions": ["情绪1", "情绪2"]
        }},
        "topics": ["话题1", "话题2", "话题3"],
        "user_state": "用户当前状态描述"
    }},
    
    "direct_reply": "纯文本回复内容，按照上面回复内容格式说明进行",
    "emotion": "happy" | "gentle" | "sad" | "excited" | "angry" | "crying" | null,
    "emotion_description": "详细的语气描述，如：开心、轻快，语速稍快，语调上扬" | null,
    "memory": {{
        "is_important": false,
        "importance_level": "low" | "medium" | "high" | null,
        "event_type": "preference" | "birthday" | "goal" | "emotion" | "life_event" | null,
        "event_summary": "事件摘要" | null,
        "keywords": [],
        "event_date": "YYYY-MM-DD" | null,
        "raw_date_expression": "原始时间表达" | null
    }}
}}
```
"""

    def _build_messages(
            self,
            system_prompt: str,
            short_term_history: List[Dict[str, str]],  # 保留此参数用于向后兼容和接口一致性
            current_message: str
    ) -> List[Dict[str, str]]:
        """
        构建最终消息列表（简化版本，仅2条消息）
        
        结构：
        1. System message (包含所有上下文：人设、记忆、摘要、对话历史、JSON格式指令)
        2. 当前 user message（仅当前输入）
        
        注意：短期历史已经嵌入到 system_prompt 中，不再作为单独消息。
        short_term_history 参数保留用于：
        1. 向后兼容 - 避免修改所有调用方代码
        2. 接口一致性 - 与 build_context 调用模式保持一致
        
        Args:
            system_prompt: 增强的 system prompt（已包含对话历史）
            short_term_history: 短期历史（保留用于向后兼容，历史已嵌入 system_prompt）
            current_message: 当前消息
            
        Returns:
            仅包含2条消息的列表：[system, user]
        """
        # short_term_history 在此不使用，历史已嵌入 system_prompt
        _ = short_term_history  # 显式标记为已知未使用

        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": current_message
            }
        ]

        return messages

    def _estimate_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        估算消息列表的 token 数
        
        简单估算：中文约1.5字符/token，英文约4字符/token
        使用 round() 以避免截断导致的低估
        """
        total_tokens = 0

        for msg in messages:
            content = msg.get("content", "")

            # 统计中文字符
            chinese_chars = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
            other_chars = len(content) - chinese_chars

            # 估算（使用 round 避免截断）
            tokens = round(chinese_chars / 1.5 + other_chars / 4)

            # 消息格式开销
            total_tokens += tokens + 4

        return total_tokens

    def _truncate_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        截断消息以适应 token 预算
        
        注意：在简化结构（仅 system + user 两条消息）下，历史已嵌入 system prompt，
        无法在消息层面进行截断。如需更严格的 token 控制，请调整 short_term_rounds 配置。
        
        Args:
            messages: 原始消息列表
            
        Returns:
            截断后的消息列表（在简化结构下返回原始消息）
        """
        # 简化结构下，只有 system 和当前消息，无法在消息层面截断
        # 历史已嵌入 system prompt，需要通过调整 short_term_rounds 配置来控制 token
        if len(messages) <= 2:
            logger.debug("简化结构下无法截断消息，请通过调整 short_term_rounds 配置来控制 token")
        return messages

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
            "usage_percentage": (result.token_estimate / (
                    self.config.max_total_tokens - self.config.reserved_output_tokens)) * 100
        }
