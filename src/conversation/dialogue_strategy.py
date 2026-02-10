"""
动态对话策略模块 - 统一的对话策略生成入口

两层架构：
第 1 层：统一分析层 — 构建用户画像与对话状态
  - 对话阶段分析 (DialoguePhaseAnalyzer.analyze_phase) — 回复长度 + 对话轮数
  - 情绪分析 (DialoguePhaseAnalyzer.analyze_emotion) — 情绪类型 + 情绪强度
  - 对话类型分析 (ConversationTypeAnalyzer.analyze_type) — 倾诉/表达立场/探索技能/要求建议/轻松互动
  - 用户兴趣分析 (ConversationTypeAnalyzer.analyze_interests) — 兴趣偏好 + 可能感兴趣的点
  - 讨论立场分析 (StanceAnalyzer) — 当用户表达立场时匹配机器人预设立场

第 2 层：生成策略层 — 基于分析结果生成应对策略
  - 根据对话阶段给出回应策略
  - 根据用户情绪给出应对策略
  - 根据用户兴趣点给出应对策略
  - 根据冲突程度给出机器人应对策略
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
from .proactive_strategy import (
    ProactiveDialogueStrategyAnalyzer, ProactiveMode,
    INTEREST_CATEGORIES, _analysis_keywords,
)

# Type checking imports to avoid circular dependencies
if TYPE_CHECKING:
    from src.bot.config_loader import ValuesConfig, ResponsePreferencesConfig, StanceConfig


class ConversationTypeAnalyzer:
    """
    对话类型分析器
    分析对话类型和用户兴趣
    """

    def analyze_type(self, message: str, history: List[Dict[str, str]] = None) -> ConversationType:
        """
        根据消息内容和历史判断对话类型
        Args:
            message: 当前用户消息
            history: 对话历史（可选，保留用于未来扩展）
            
        Returns:
            ConversationType: 对话类型
        """
        # 检测情绪倾诉（优先级最高，需要特殊对待）
        for keyword in CONVERSATION_TYPE_SIGNALS[ConversationType.EMOTIONAL_VENT]:
            if keyword in message:
                logger.debug(f"🫙 [Dialogue-Strategy] 情绪发现检测: keyword={keyword}")
                return ConversationType.EMOTIONAL_VENT

        # 检测决策咨询
        for keyword in CONVERSATION_TYPE_SIGNALS[ConversationType.DECISION_CONSULTING]:
            if keyword in message:
                logger.debug(f"🫙 [Dialogue-Strategy] 决策咨询检测: keyword={keyword}")
                return ConversationType.DECISION_CONSULTING

        # 检测观点讨论
        for keyword in CONVERSATION_TYPE_SIGNALS[ConversationType.OPINION_DISCUSSION]:
            if keyword in message:
                logger.debug(f"🫙 [Dialogue-Strategy] 观点讨论检测: keyword={keyword}")
                return ConversationType.OPINION_DISCUSSION

        # 检测信息需求
        for keyword in CONVERSATION_TYPE_SIGNALS[ConversationType.INFO_REQUEST]:
            if keyword in message:
                logger.debug(f"🫙 [Dialogue-Strategy] 信息请求检测: keyword={keyword}")
                return ConversationType.INFO_REQUEST

        # 默认为日常闲聊
        logger.debug("🫙 [Dialogue-Strategy] 检测到无特殊情况，默认使用闲聊模式")
        return ConversationType.CASUAL_CHAT

    def identify_current_topic(self, recent_messages: List[Dict[str, str]]) -> Optional[str]:
        """
        识别当前话题
        Args:
            recent_messages: 最近的消息列表
        Returns:
            当前话题或None
        """
        if not recent_messages:
            return None
        basic_topics = _analysis_keywords.get("basic_topics", [])
        for msg in reversed(recent_messages):
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "")
            for interest, keywords in INTEREST_CATEGORIES.items():
                if any(kw in content for kw in keywords):
                    return interest
            for topic in basic_topics:
                if topic in content:
                    return topic
        return None

    def analyze_interests(
            self,
            conversation_history: List[Dict[str, str]],
            current_message: str = ""
    ) -> Dict[str, List[str]]:
        """
        分析用户兴趣偏好和可能感兴趣的点
        Args:
            conversation_history: 对话历史
            current_message: 当前用户消息
        Returns:
            Dict 包含:
              - interests: 已识别的用户兴趣列表
              - potential_interests: 可能感兴趣的探索方向
        """
        interest_counts: Dict[str, int] = {}
        # 分析对话历史中的兴趣
        messages_to_scan = list(conversation_history)
        if current_message:
            messages_to_scan.append({"role": "user", "content": current_message})
        for msg in messages_to_scan:
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "").lower()
            for interest, keywords in INTEREST_CATEGORIES.items():
                for keyword in keywords:
                    if keyword in content:
                        interest_counts[interest] = interest_counts.get(interest, 0) + 1
                        break
        # 按频次排序
        sorted_interests = sorted(interest_counts.items(), key=lambda x: x[1], reverse=True)
        interests = [interest for interest, _ in sorted_interests[:5]]
        # 找出用户可能感兴趣但未深入的点
        all_categories = list(INTEREST_CATEGORIES.keys())
        potential_interests = [cat for cat in all_categories if cat not in interests][:3]
        logger.debug(f"🫙 [Dialogue-Strategy] 兴趣分析: interests={interests}, potential={potential_interests}")
        return {
            "interests": interests,
            "potential_interests": potential_interests
        }


@dataclass
class StanceAnalysis:
    """立场分析结果"""
    user_opinion: str  # 用户观点
    bot_stance: Optional[str] = None  # Bot的预设立场
    conflict_level: float = 0.0  # 冲突程度 0-1
    suggested_strategy: StanceStrategy = StanceStrategy.AGREE  # 建议策略
    topic: Optional[str] = None  # 匹配的话题


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
            else:
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
    分析对话阶段（基于对话轮数和回复长度）和用户情绪
    """

    def analyze_phase(self, conversation_history: List[Dict[str, str]]) -> Tuple[DialoguePhase, Dict[str, Any]]:
        """
        根据对话轮次和回复长度判断当前阶段
        Args:
            conversation_history: 对话历史记录 (不包含system prompt)
        Returns:
            Tuple[DialoguePhase, Dict]: (当前对话阶段, 阶段分析详情)
                详情包含: user_turn_count, avg_reply_length
        """
        # 计算用户消息轮数（只计算user角色的消息）
        user_messages = [msg for msg in conversation_history if msg.get("role") == "user"]
        user_turn_count = len(user_messages)
        # 分析回复长度
        avg_reply_length = 0
        if user_messages:
            avg_reply_length = sum(len(msg.get("content", "")) for msg in user_messages) / len(user_messages)

        if user_turn_count <= 2:
            phase = DialoguePhase.OPENING
        elif user_turn_count <= 5:
            phase = DialoguePhase.LISTENING
        elif user_turn_count <= 8:
            phase = DialoguePhase.DEEPENING
        else:
            phase = DialoguePhase.SUPPORTING

        phase_details = {
            "user_turn_count": user_turn_count,
            "avg_reply_length": round(avg_reply_length, 1)
        }
        return phase, phase_details

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
    整合回应策略 + 主动策略 + 立场策略
    """

    def __init__(self):
        self.analyzer = DialoguePhaseAnalyzer()
        self.conversation_type_analyzer = ConversationTypeAnalyzer()
        self.stance_analyzer = StanceAnalyzer()
        self.proactive_analyzer = ProactiveDialogueStrategyAnalyzer()

    def inject_strategy(
            self,
            original_prompt: str,
            conversation_history: List[Dict[str, str]],
            current_message: str,
            bot_values: Optional['ValuesConfig'] = None,
            user_memories: Optional[List[Dict[str, Any]]] = None,
            enable_proactive: bool = True
    ) -> str:
        """
        将策略指令追加到原有 system_prompt 后面
        关键原则：添加，而非替换。保持原有个性不变。

        第 1 层：统一分析层 — 只做一次，产出共享上下文
          - 对话阶段分析（回复长度 + 对话轮数）
          - 情绪分析（情绪类型 + 强度）
          - 对话类型分析（倾诉/表达立场/探索技能/要求建议/轻松互动）
          - 用户兴趣分析（兴趣偏好 + 可能感兴趣的点）
          - 讨论立场分析（用户立场与机器人立场的交集）

        第 2 层：生成策略层 — 基于分析结果生成应对策略
          - 根据对话阶段给出回应策略
          - 根据用户情绪给出应对策略
          - 根据用户兴趣点给出应对策略
          - 根据冲突程度给出机器人应对策略

        Args:
            original_prompt: 原始system prompt（包含完整人设）
            conversation_history: 对话历史（不包含system prompt）
            current_message: 当前用户消息
            bot_values: Bot价值观配置（可选）
            user_memories: 用户记忆（可选）
            enable_proactive: 是否启用主动策略

        Returns:
            str: 增强后的system prompt
        """
        # ================================================================
        # 第 1 层：统一分析层（只做一次，产出共享上下文）
        # ================================================================
        # 1.1 对话阶段分析（回复长度 + 对话轮数）
        phase, phase_details = self.analyzer.analyze_phase(conversation_history)
        # 1.2 情绪分析（情绪类型 + 强度）
        emotion_type, emotion_intensity = self.analyzer.analyze_emotion(current_message)
        # 1.3 对话类型分析（倾诉/表达立场/探索技能/要求建议/轻松互动）
        conversation_type = self.conversation_type_analyzer.analyze_type(current_message, conversation_history)
        # 1.4 用户兴趣分析（兴趣偏好 + 可能感兴趣的点）
        interest_analysis = self.conversation_type_analyzer.analyze_interests(
            conversation_history, current_message
        )
        # 1.5 讨论立场分析（用户表达立场时匹配机器人预设立场）
        stance_analysis = None
        if bot_values and conversation_type == ConversationType.OPINION_DISCUSSION:
            stance_analysis = self.stance_analyzer.analyze_stance(current_message, bot_values)

        # ================================================================
        # 第 2 层：生成策略层（基于分析结果生成应对策略）
        # ================================================================
        base_prompt = original_prompt if original_prompt else ""
        enhanced_prompt = base_prompt
        strategy_parts = []

        # 2.1 根据对话阶段给出回应策略
        response_type = self.analyzer.suggest_response_type(
            phase, emotion_type, emotion_intensity, conversation_history
        )
        phase_strategy = STRATEGY_TEMPLATES[response_type]
        strategy_parts.append(phase_strategy)

        # 2.2 根据用户情绪给出应对策略（已融合在 response_type 中，
        #     当情绪为负面时 response_type 会自动选择 COMFORT/VALIDATION）

        # 2.3 根据用户兴趣点给出应对策略
        interests = interest_analysis.get("interests", [])
        potential_interests = interest_analysis.get("potential_interests", [])
        if interests or potential_interests:
            interest_guidance = self._build_interest_guidance(interests, potential_interests)
            if interest_guidance:
                strategy_parts.append(interest_guidance)

        # 2.4 根据冲突程度给出机器人应对策略
        if stance_analysis and stance_analysis.bot_stance:
            stance_guidance = self._build_stance_guidance(stance_analysis)
            if stance_guidance:
                strategy_parts.append(stance_guidance)

        # 合并所有策略到增强 prompt
        if strategy_parts:
            enhanced_prompt += "\n\n" + "\n\n".join(strategy_parts)

        # 主动策略层（基于统一分析结果生成主动互动建议）
        if enable_proactive and conversation_history:
            proactive_guidance = self._generate_proactive_guidance(
                conversation_history,
                user_memories,
                interest_analysis=interest_analysis,
                response_type=response_type
            )
            if proactive_guidance:
                enhanced_prompt += f"\n\n{proactive_guidance}"

        logger.info(
            f"🫙 [Dialogue-Strategy] applied: phase={phase.value}, "
            f"turns={phase_details['user_turn_count']}, avg_len={phase_details['avg_reply_length']}, "
            f"emotion={emotion_type}/{emotion_intensity}, "
            f"conversation_type={conversation_type.value}, "
            f"response_type={response_type.value}, "
            f"interests={interests[:3]}, "
            f"stance={'yes' if stance_analysis and stance_analysis.bot_stance else 'no'}, "
            f"proactive={'enabled' if enable_proactive else 'disabled'}"
        )
        return enhanced_prompt

    def _build_interest_guidance(
            self,
            interests: List[str],
            potential_interests: List[str]
    ) -> str:
        """
        构建用户兴趣策略指导
        Args:
            interests: 已识别的用户兴趣
            potential_interests: 可能感兴趣的方向
        Returns:
            兴趣策略指导文本
        """
        if not interests and not potential_interests:
            return ""

        lines = ["【用户兴趣策略】"]
        if interests:
            lines.append(f"- 用户已知兴趣：{', '.join(interests[:3])}")
            lines.append("- 可以围绕这些兴趣展开话题，表达共鸣和好奇")
        if potential_interests:
            lines.append(f"- 可探索方向：{', '.join(potential_interests[:3])}")
            lines.append("- 可以自然地引出新话题，了解用户更多喜好")
        lines.append("注意：你的人设和性格保持不变，以上是建议的沟通方式。")
        return "\n".join(lines)

    def _generate_proactive_guidance(
            self,
            conversation_history: List[Dict[str, str]],
            user_memories: Optional[List[Dict[str, Any]]],
            interest_analysis: Optional[Dict[str, List[str]]] = None,
            response_type: Optional[ResponseType] = None
    ) -> str:
        """
        生成主动对话策略指导（基于统一分析层结果）
        Args:
            conversation_history: 对话历史
            user_memories: 用户记忆
            interest_analysis: 统一分析层的兴趣分析结果
            response_type: 回应策略层已选择的回应类型，用于去重
        Returns:
            主动策略文本
        """
        try:
            # 从统一分析层获取兴趣结果，直接传入用户画像构建
            interests = interest_analysis.get("interests", []) if interest_analysis else []
            # 构建用户画像（复用统一分析层的兴趣结果）
            user_profile = self.proactive_analyzer.analyze_user_profile(
                conversation_history, user_memories, interests=interests
            )

            # 从统一分析层获取当前话题
            recent_messages = conversation_history[-3:] if conversation_history else []
            current_topic = self.conversation_type_analyzer.identify_current_topic(recent_messages)

            # 分析话题（复用统一分析层的当前话题结果）
            topic_analysis = self.proactive_analyzer.analyze_topic(
                conversation_history, user_profile, current_topic=current_topic
            )
            # 生成主动策略
            proactive_action = self.proactive_analyzer.generate_proactive_strategy(
                user_profile, topic_analysis, conversation_history, user_memories
            )
            # 去重：如果回应策略已选 PROACTIVE_INQUIRY，主动策略不再重复输出通用追问模板
            if (response_type == ResponseType.PROACTIVE_INQUIRY
                    and proactive_action.mode == ProactiveMode.EXPLORE_INTEREST):
                logger.debug(
                    "🫙 [Dialogue-Strategy] 回应策略已选 PROACTIVE_INQUIRY，"
                    "跳过主动策略中的 EXPLORE_INTEREST 模板以避免重复"
                )
                proactive_action = None

            if proactive_action is None:
                return ""

            # 格式化为文本
            guidance = self.proactive_analyzer.format_proactive_guidance(proactive_action)
            # 添加用户画像信息
            interests_str = ', '.join(user_profile.interests[:3]) if user_profile.interests else '待探索'
            explore_str = ', '.join(topic_analysis.topics_to_explore[:3]) if topic_analysis.topics_to_explore else '无'
            profile_info = f"""
【当前对话情境】
- 用户参与度：{user_profile.engagement_level.value}
- 用户情绪：{user_profile.emotional_state}
- 关系深度：{user_profile.relationship_depth}/5
- 用户兴趣：{interests_str}
- 可探索话题：{explore_str}
"""
            return profile_info + "\n" + guidance

        except Exception as e:
            logger.warning(f"生成主动策略失败: {e}")
            return ""

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
        bot_values: Optional['ValuesConfig'] = None,
        user_memories: Optional[List[Dict[str, Any]]] = None,
        enable_proactive: bool = True
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
    """
    global _injector_instance
    if _injector_instance is None:
        _injector_instance = DialogueStrategyInjector()
    return _injector_instance.inject_strategy(
        original_prompt, conversation_history, current_message,
        bot_values, user_memories, enable_proactive
    )
