"""
Dynamic Dialogue Strategy Module
动态对话策略模块

Based on academic research:
1. Human-AI Collaboration Enables More Empathic Conversations in Text-based Peer-to-Peer Mental Health Support (Nature Machine Intelligence 2022)
2. SoulChat: Improving LLMs' Empathy, Listening, and Comfort Abilities through Fine-tuning with Multi-turn Empathy Conversations (EMNLP 2023)

Core principles:
- Strategy is APPENDED to system_prompt, not replacing it
- Maintains the bot's original personality
- Focuses on companionship rather than problem-solving
"""

from typing import List, Dict, Tuple, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass
from loguru import logger

# 从对话策略配置文件导入所有策略规则和常量
from .dialogue_strategy_config import (
    ConversationType,
    StanceStrategy,
    DialoguePhase,
    ResponseType,
    EMOTION_KEYWORDS,
    STRATEGY_TEMPLATES,
    STANCE_STRATEGY_TEMPLATES,
    CONVERSATION_TYPE_SIGNALS,
)

# Type checking imports to avoid circular dependencies
if TYPE_CHECKING:
    from src.bot.config_loader import ValuesConfig, ResponsePreferencesConfig, StanceConfig


class ConversationTypeAnalyzer:
    """
    对话类型分析器
    Analyzes conversation type based on message content
    """
    
    def analyze_type(self, message: str, history: List[Dict[str, str]] = None) -> ConversationType:
        """
        根据消息内容和历史判断对话类型
        Determine conversation type based on message content and history
        
        Args:
            message: 当前用户消息
            history: 对话历史（可选，保留用于未来扩展）
            
        Returns:
            ConversationType: 对话类型
        """
        # 检测情绪倾诉（优先级最高，需要特殊对待）
        for keyword in CONVERSATION_TYPE_SIGNALS[ConversationType.EMOTIONAL_VENT]:
            if keyword in message:
                logger.debug(f"🫙 [Dialogue-Strategy] Detected EMOTIONAL_VENT: keyword={keyword}")
                return ConversationType.EMOTIONAL_VENT
        
        # 检测决策咨询
        for keyword in CONVERSATION_TYPE_SIGNALS[ConversationType.DECISION_CONSULTING]:
            if keyword in message:
                logger.debug(f"🫙 [Dialogue-Strategy] Detected DECISION_CONSULTING: keyword={keyword}")
                return ConversationType.DECISION_CONSULTING
        
        # 检测观点讨论
        for keyword in CONVERSATION_TYPE_SIGNALS[ConversationType.OPINION_DISCUSSION]:
            if keyword in message:
                logger.debug(f"🫙 [Dialogue-Strategy] Detected OPINION_DISCUSSION: keyword={keyword}")
                return ConversationType.OPINION_DISCUSSION
        
        # 检测信息需求
        for keyword in CONVERSATION_TYPE_SIGNALS[ConversationType.INFO_REQUEST]:
            if keyword in message:
                logger.debug(f"🫙 [Dialogue-Strategy] Detected INFO_REQUEST: keyword={keyword}")
                return ConversationType.INFO_REQUEST
        
        # 默认为日常闲聊
        logger.debug("🫙 [Dialogue-Strategy] Not Detected Using Default CASUAL_CHATT")
        return ConversationType.CASUAL_CHAT


@dataclass
class StanceAnalysis:
    """立场分析结果"""
    user_opinion: str                    # 用户观点
    bot_stance: Optional[str] = None     # Bot的预设立场
    conflict_level: float = 0.0          # 冲突程度 0-1
    suggested_strategy: StanceStrategy = StanceStrategy.AGREE  # 建议策略
    topic: Optional[str] = None          # 匹配的话题


class StanceAnalyzer:
    """
    立场分析器
    Analyzes user opinion and determines bot's stance strategy
    """
    
    def analyze_stance(self, message: str, bot_values: 'ValuesConfig') -> StanceAnalysis:
        """
        分析用户观点并确定Bot的立场策略
        Analyze user opinion and determine bot's stance strategy
        
        Args:
            message: 用户消息
            bot_values: Bot的价值观配置
            
        Returns:
            StanceAnalysis: 立场分析结果
        """
        # 提取用户观点（简化实现：使用整个消息作为观点）
        user_opinion = message
        
        # 匹配Bot的预设立场
        matched_stance = self._match_bot_stance(message, bot_values.stances)
        
        if not matched_stance:
            # 没有匹配的预设立场，使用默认行为
            if bot_values.default_behavior == "curious":
                return StanceAnalysis(
                    user_opinion=user_opinion,
                    suggested_strategy=StanceStrategy.AGREE_AND_ADD
                )
            else:  # neutral or avoid
                return StanceAnalysis(
                    user_opinion=user_opinion,
                    suggested_strategy=StanceStrategy.AGREE
                )
        
        # 有匹配的立场，根据assertiveness和confidence决定策略
        conflict_level = self._calculate_conflict(message, matched_stance.position)
        strategy = self._determine_strategy(
            conflict_level,
            bot_values.dimensions.assertiveness,
            matched_stance.confidence,
            bot_values.response_preferences
        )
        
        return StanceAnalysis(
            user_opinion=user_opinion,
            bot_stance=matched_stance.position,
            conflict_level=conflict_level,
            suggested_strategy=strategy,
            topic=matched_stance.topic
        )
    
    def _match_bot_stance(self, message: str, stances: List['StanceConfig']) -> Optional['StanceConfig']:
        """
        匹配Bot的预设立场
        Match bot's predefined stances based on message content
        
        简化的关键词匹配实现。对于中文文本，直接检查话题词是否在消息中。
        
        Args:
            message: 用户消息
            stances: Bot的预设立场列表
            
        Returns:
            匹配的立场配置或None
        """
        for stance in stances:
            # 简单的关键词匹配：检查话题是否在消息中
            # 对于中文，直接substring匹配即可
            if stance.topic in message:
                logger.debug(f"Matched stance: topic={stance.topic}")
                return stance
        
        return None
    
    def _calculate_conflict(self, user_message: str, bot_position: str) -> float:
        """
        计算用户观点和Bot立场的冲突程度
        Calculate conflict level between user opinion and bot position
        
        简化实现：检查是否有明显的对立关键词
        注意：这是一个基础实现，可能在某些语境下不够准确（如"不要担心"包含"不要"但实际是安抚）。
        未来可考虑使用更复杂的NLP方法或情感分析。
        
        Args:
            user_message: 用户消息
            bot_position: Bot的立场
            
        Returns:
            冲突程度 0-1
        """
        # 简化实现：如果用户消息包含否定词，冲突程度较高
        negative_words = ["不", "别", "不要", "不应该", "反对", "不同意"]
        conflict_count = sum(1 for word in negative_words if word in user_message)
        
        # 归一化到0-1
        conflict_level = min(conflict_count / 3.0, 1.0)
        
        return conflict_level
    
    def _determine_strategy(
        self,
        conflict_level: float,
        assertiveness: int,
        confidence: float,
        preferences: 'ResponsePreferencesConfig'
    ) -> StanceStrategy:
        """
        根据冲突程度、Bot的assertiveness和立场confidence决定策略
        Determine stance strategy based on conflict, assertiveness, and confidence
        
        Args:
            conflict_level: 冲突程度 0-1
            assertiveness: Bot的坚持程度 1-10
            confidence: 立场的confidence 0-1
            preferences: 回应偏好
            
        Returns:
            StanceStrategy: 建议的立场策略
        """
        # 低冲突情况
        if conflict_level < 0.3:
            if preferences.agree_first:
                return StanceStrategy.AGREE_AND_ADD
            else:
                return StanceStrategy.AGREE
        
        # 中等冲突情况
        if conflict_level < 0.6:
            if assertiveness >= 7 and confidence >= 0.7:
                return StanceStrategy.PARTIAL_AGREE
            else:
                return StanceStrategy.AGREE_AND_ADD
        
        # 高冲突情况
        if assertiveness >= 7 and confidence >= 0.7:
            if assertiveness >= 8:
                return StanceStrategy.RESPECTFUL_DISAGREE
            else:
                return StanceStrategy.PARTIAL_AGREE
        else:
            return StanceStrategy.PARTIAL_AGREE


class DialoguePhaseAnalyzer:
    """
    对话阶段分析器
    """
    
    def analyze_phase(self, conversation_history: List[Dict[str, str]]) -> DialoguePhase:
        """
        根据对话轮次判断当前阶段
        Args:
            conversation_history: 对话历史记录 (不包含system prompt)
        Returns:
            DialoguePhase: 当前对话阶段
        """
        # 计算用户消息轮数（只计算user角色的消息）
        user_turn_count = sum(1 for msg in conversation_history if msg.get("role") == "user")
        
        if user_turn_count <= 2:
            return DialoguePhase.OPENING
        elif user_turn_count <= 5:
            return DialoguePhase.LISTENING
        elif user_turn_count <= 8:
            return DialoguePhase.DEEPENING
        else:
            return DialoguePhase.SUPPORTING
    
    def analyze_emotion(self, message: str) -> Tuple[str, str]:
        """
        识别用户情绪及强度
        Analyze user emotion and intensity from message content
        
        Args:
            message: 用户消息文本
            
        Returns:
            Tuple[str, str]: (情绪类型, 强度级别) - (emotion_type, intensity_level)
                            情绪类型: "positive", "negative", "neutral"
                            强度级别: "high", "medium", "low"
        """
        message_lower = message.lower()
        
        # 检查负面情绪（优先级更高，因为需要更多关注）
        # Check negative emotions first (higher priority for mental health support)
        for intensity in ["high", "medium", "low"]:
            for keyword in EMOTION_KEYWORDS["negative"][intensity]:
                if keyword in message_lower:
                    logger.debug(f"Detected negative emotion: intensity={intensity}, keyword={keyword}")
                    return ("negative", intensity)
        
        # 检查正面情绪
        # Check positive emotions
        for intensity in ["high", "medium", "low"]:
            for keyword in EMOTION_KEYWORDS["positive"][intensity]:
                if keyword in message_lower:
                    logger.debug(f"Detected positive emotion: intensity={intensity}, keyword={keyword}")
                    return ("positive", intensity)
        
        # 默认为中性情绪
        # Default to neutral emotion
        return ("neutral", "medium")
    
    def suggest_response_type(
        self,
        phase: DialoguePhase,
        emotion_type: str,
        emotion_intensity: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> ResponseType:
        """
        根据阶段和情绪建议回应类型
        Suggest appropriate response type based on phase and emotion
        
        Args:
            phase: 当前对话阶段
            emotion_type: 情绪类型 ("positive", "negative", "neutral")
            emotion_intensity: 情绪强度 ("high", "medium", "low")
            conversation_history: 对话历史（可选，用于判断是否应该主动追问）
            
        Returns:
            ResponseType: 建议的回应类型
        """
        # 紧急情况：高强度负面情绪，优先安慰
        # Emergency: High-intensity negative emotions require immediate comfort
        if emotion_type == "negative" and emotion_intensity == "high":
            return ResponseType.COMFORT
        
        # 检查是否应该主动追问（在情绪稳定时适当穿插）
        # Check if proactive inquiry should be suggested (when emotions are stable)
        should_inquire = self._should_proactive_inquiry(phase, emotion_type, conversation_history)
        
        # 根据对话阶段选择策略
        # Select strategy based on dialogue phase
        if phase == DialoguePhase.OPENING:
            # 开场阶段：主动倾听，建立信任
            return ResponseType.ACTIVE_LISTENING
            
        elif phase == DialoguePhase.LISTENING:
            # 倾听阶段：根据情绪选择倾听或验证
            # Listening phase: Choose between listening and validation
            if emotion_type == "negative":
                return ResponseType.VALIDATION  # 验证负面情绪
            elif should_inquire:
                return ResponseType.PROACTIVE_INQUIRY  # 适时主动追问
            else:
                return ResponseType.ACTIVE_LISTENING
                
        elif phase == DialoguePhase.DEEPENING:
            # 深入阶段：共情式提问，帮助探索
            # Deepening phase: Empathic questioning for exploration
            if emotion_type == "negative" and emotion_intensity in ["high", "medium"]:
                return ResponseType.COMFORT  # 中高强度负面情绪需要安慰
            elif should_inquire and emotion_type == "neutral":
                return ResponseType.PROACTIVE_INQUIRY  # 中性情绪时主动追问
            else:
                return ResponseType.EMPATHIC_QUESTIONING
                
        else:  # DialoguePhase.SUPPORTING
            # 支持阶段：可以适当引导
            # Supporting phase: Gentle guidance when appropriate
            if emotion_type == "positive":
                if should_inquire:
                    return ResponseType.PROACTIVE_INQUIRY  # 积极情绪时主动追问
                return ResponseType.EMPATHIC_QUESTIONING  # 积极情绪时继续探索
            elif emotion_type == "negative":
                if emotion_intensity == "low":
                    return ResponseType.GENTLE_GUIDANCE  # 低强度负面可以引导
                else:
                    return ResponseType.COMFORT  # 中高强度负面需要安慰
            else:
                if should_inquire:
                    return ResponseType.PROACTIVE_INQUIRY  # 中性情绪时主动追问
                return ResponseType.GENTLE_GUIDANCE
    
    def _should_proactive_inquiry(
        self,
        phase: DialoguePhase,
        emotion_type: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> bool:
        """
        判断是否应该主动追问用户个人信息
        Determine if proactive inquiry about personal details should be suggested
        
        这个方法用于在适当的时机穿插主动追问，使对话更加拟人化。
        追问时机：
        - 对话已经进行了几轮（不在开场阶段）
        - 用户情绪稳定（非负面情绪）
        - 最近几轮没有连续追问过
        
        Args:
            phase: 当前对话阶段
            emotion_type: 情绪类型
            conversation_history: 对话历史
            
        Returns:
            bool: 是否应该主动追问
        """
        # 开场阶段不追问，先建立信任
        # Don't inquire in opening phase, build trust first
        if phase == DialoguePhase.OPENING:
            return False
        
        # 负面情绪时不追问，优先关注情绪
        # Don't inquire when negative emotions, focus on emotions first
        if emotion_type == "negative":
            return False
        
        # 如果没有对话历史，不追问
        if not conversation_history:
            return False
        
        # 计算用户消息轮数
        user_turns = sum(1 for msg in conversation_history if msg.get("role") == "user")
        
        # 每隔一定轮次考虑追问（例如每3-4轮）
        # Consider inquiry every few turns (e.g., every 3-4 turns)
        # 使用简单的规则：用户消息轮数能被3整除时考虑追问
        if user_turns > 0 and user_turns % 3 == 0:
            return True
        
        return False


class DialogueStrategyInjector:
    """
    对话策略注入器
    Injects strategy guidance into system prompt while preserving original personality
    """
    
    def __init__(self):
        self.analyzer = DialoguePhaseAnalyzer()
        self.conversation_type_analyzer = ConversationTypeAnalyzer()
        self.stance_analyzer = StanceAnalyzer()
    
    def inject_strategy(
        self,
        original_prompt: str,
        conversation_history: List[Dict[str, str]],
        current_message: str,
        bot_values: Optional['ValuesConfig'] = None
    ) -> str:
        """
        将策略指令追加到原有 system_prompt 后面
        关键原则：添加，而非替换。保持原有个性不变。
        Args:
            original_prompt: 原始system prompt（包含完整人设）
            conversation_history: 对话历史（不包含system prompt）
            current_message: 当前用户消息
            bot_values: Bot价值观配置（可选）
            
        Returns:
            str: 增强后的system prompt
        """
        # 分析对话阶段
        # Analyze dialogue phase
        phase = self.analyzer.analyze_phase(conversation_history)
        
        # 分析用户情绪
        emotion_type, emotion_intensity = self.analyzer.analyze_emotion(current_message)
        
        # 分析对话类型
        conversation_type = self.conversation_type_analyzer.analyze_type(current_message, conversation_history)
        
        # 建议回应类型（传入对话历史以判断是否应该主动追问）
        response_type = self.analyzer.suggest_response_type(
            phase, emotion_type, emotion_intensity, conversation_history
        )
        
        # 获取策略模板
        strategy_guidance = STRATEGY_TEMPLATES[response_type]
        
        # 追加策略到原prompt后面（保持原有人设不变）
        base_prompt = original_prompt if original_prompt else ""
        
        # 构建增强prompt
        enhanced_prompt = base_prompt
        
        # 如果提供了bot_values，添加价值观和立场策略
        if bot_values:
            # 注入价值观维度
            values_guidance = self._build_values_guidance(bot_values)
            if values_guidance:
                enhanced_prompt += f"\n\n{values_guidance}"
            
            # 如果是观点讨论类型，进行立场分析
            if conversation_type == ConversationType.OPINION_DISCUSSION:
                stance_analysis = self.stance_analyzer.analyze_stance(current_message, bot_values)
                stance_guidance = self._build_stance_guidance(stance_analysis)
                if stance_guidance:
                    enhanced_prompt += f"\n\n{stance_guidance}"
        
        # 添加对话策略指导
        enhanced_prompt += f"\n\n{strategy_guidance}"

        logger.info(
            f"🫙 [Dialogue-Strategy] applied: phase={phase.value}, "
            f"emotion={emotion_type}/{emotion_intensity}, "
            f"conversation_type={conversation_type.value}, "
            f"response_type={response_type.value}"
        )
        
        return enhanced_prompt
    
    @staticmethod
    def _format_list(items: list) -> str:
        """格式化列表为换行文本"""
        return '\n -'.join(items)

    def _build_values_guidance(self, bot_values: 'ValuesConfig') -> str:
        """
        构建价值观、情绪应对和安全策略指导
        Build values, emotional response and safety policy guidance

        Args:
            bot_values: Bot价值观配置

        Returns:
            价值观和策略指导文本
        """
        sections = []

        # 情绪应对策略
        emotional_response = bot_values.emotional_response
        if emotional_response:
            parts = ["\n【情绪应对策略】"]
            field_labels = {
                "user_sad": "当用户难过时",
                "user_angry": "当用户生气时",
                "user_happy": "当用户开心时",
                "priority": "优先级",
                "avoid_actions": "避免行为",
            }
            for key, label in field_labels.items():
                items = emotional_response.get(key)
                if items:
                    parts.append(f"{label}：\n -{self._format_list(items)}")
            # parts[0] 是标题，只有存在实际内容时才添加
            if len(parts) > 1:
                sections.append("\n".join(parts))

        # 安全策略
        safety_policy = bot_values.safety_policy
        if safety_policy:
            safety_parts = []
            safety_fields = {
                "avoid_topics": "\n**需要主动回避的话题**",
                "high_risk_keywords": "**高度警惕不能正常聊关键词**",
                "response_strategy": "**特殊的响应策略**",
            }
            for key, label in safety_fields.items():
                items = safety_policy.get(key)
                if items:
                    safety_parts.append(f"{label}：\n -{self._format_list(items)}")
            if safety_parts:
                sections.append(f"\n【安全对话策略】" + "\n".join(safety_parts))

        return "\n".join(sections)
    
    def _build_stance_guidance(self, stance_analysis: StanceAnalysis) -> str:
        """
        构建立场策略指导
        Build stance strategy guidance based on stance analysis
        
        Args:
            stance_analysis: 立场分析结果
            
        Returns:
            立场策略指导文本
        """
        if not stance_analysis.bot_stance:
            return ""
        
        guidance = f"""
=========================
💭 关于当前话题的立场
=========================
用户观点：{stance_analysis.user_opinion[:100]}{'...' if len(stance_analysis.user_opinion) > 100 else ''}
你的观点：{stance_analysis.bot_stance}

"""
        
        # 添加对应的立场策略模板
        guidance += STANCE_STRATEGY_TEMPLATES[stance_analysis.suggested_strategy]
        
        return guidance


# Module-level singleton to avoid unnecessary object allocation
_injector_instance: Optional[DialogueStrategyInjector] = None


def enhance_prompt_with_strategy(
    original_prompt: str,
    conversation_history: List[Dict[str, str]],
    current_message: str,
    bot_values: Optional['ValuesConfig'] = None
) -> str:
    """
    便捷函数：根据对话历史增强prompt，它使用模块级单例模式，避免每次调用都创建新对象。
    
    Args:
        original_prompt: 原始system prompt
        conversation_history: 对话历史记录（不包含system prompt）
        current_message: 当前用户消息
        bot_values: Bot价值观配置（可选）
        
    Returns:
        str: 增强后的system prompt
        
    Example:
        ```python
        enhanced_prompt = enhance_prompt_with_strategy(
            original_prompt=bot.system_prompt,
            conversation_history=history,
            current_message=message_text,
            bot_values=bot.values
        )
        history.insert(0, {"role": "system", "content": enhanced_prompt})
        ```
    """
    global _injector_instance
    if _injector_instance is None:
        _injector_instance = DialogueStrategyInjector()
    return _injector_instance.inject_strategy(original_prompt, conversation_history, current_message, bot_values)
