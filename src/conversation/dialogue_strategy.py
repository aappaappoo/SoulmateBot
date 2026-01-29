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

from enum import Enum
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from loguru import logger


class ConversationType(str, Enum):
    """对话类型分类"""
    EMOTIONAL_VENT = "emotional_vent"           # 情绪倾诉 - 暂不反驳
    OPINION_DISCUSSION = "opinion_discussion"   # 观点讨论 - 可以表达立场
    INFO_REQUEST = "info_request"               # 信息需求 - 可触发搜索技能
    DECISION_CONSULTING = "decision_consulting" # 决策咨询 - 分析+建议
    CASUAL_CHAT = "casual_chat"                 # 日常闲聊 - 轻松互动


class StanceStrategy(str, Enum):
    """立场表达策略"""
    AGREE = "agree"                         # 完全同意
    AGREE_AND_ADD = "agree_and_add"         # 先同意再补充
    PARTIAL_AGREE = "partial_agree"         # 部分同意，指出不同
    RESPECTFUL_DISAGREE = "respectful_disagree"  # 尊重地表达不同意见
    CHALLENGE = "challenge"                 # 温和质疑用户假设


class DialoguePhase(Enum):
    """
    对话阶段枚举
    Dialogue phase classification based on conversation turn count
    """
    OPENING = "opening"           # 开场阶段(前1-2轮) - Opening phase (turns 1-2)
    LISTENING = "listening"       # 倾听阶段(3-5轮) - Listening phase (turns 3-5)
    DEEPENING = "deepening"       # 深入理解阶段(6-8轮) - Deepening phase (turns 6-8)
    SUPPORTING = "supporting"     # 支持引导阶段(9轮以上) - Supporting phase (turns 9+)


class ResponseType(Enum):
    """
    回应类型枚举（基于SoulChat策略）
    Response types based on SoulChat empathic communication strategies
    """
    ACTIVE_LISTENING = "active_listening"              # 主动倾听 - Active listening
    EMPATHIC_QUESTIONING = "empathic_questioning"      # 共情式提问 - Empathic questioning
    VALIDATION = "validation"                          # 认可与验证 - Validation and acknowledgment
    COMFORT = "comfort"                                # 安慰与支持 - Comfort and support
    GENTLE_GUIDANCE = "gentle_guidance"                # 温和引导 - Gentle guidance
    PROACTIVE_INQUIRY = "proactive_inquiry"            # 主动追问 - Proactive inquiry about personal details


# 情绪关键词配置
# Emotion keywords configuration for sentiment analysis
EMOTION_KEYWORDS = {
    "negative": {
        "high": ["崩溃", "绝望", "撑不下去", "不想活", "太痛苦", "受不了"],
        "medium": ["难过", "伤心", "焦虑", "压力大", "累", "烦", "失落", "孤独", "迷茫"],
        "low": ["不太好", "有点", "还行吧", "一般"]
    },
    "positive": {
        "high": ["太开心了", "超级棒", "特别好"],
        "medium": ["开心", "高兴", "不错", "好起来了"],
        "low": ["还可以", "稍微好点"]
    }
}


# 多消息回复指令
# Multi-message reply instruction for more human-like responses
MULTI_MESSAGE_INSTRUCTION = """
=========================
📝 回复格式说明
=========================
为了让对话更加自然，你可以日常使用1句话来回复，但偶尔选择将回复分成多条消息发送。

格式要求：
- 如果你认为回复应该分成多条消息，请使用 [MSG_SPLIT] 标记分隔
- 每个分隔的部分会作为独立的消息发送给用户
- 分隔要自然，就像真人聊天时会分多次发送一样
- 不要刻意分割，只在自然需要时使用（比如：先回应情绪，再提问；或者分享不同的想法）
- 最多分成3条消息

示例1（单条回复）：
我懂你的感受，这种时候确实很不容易呢 💕

示例2（多条回复）：
哎呀，听起来今天遇到了不少事情呢
[MSG_SPLIT]
不过别担心，有什么想说的都可以告诉我~

示例3（多条回复）：
你说的这个我特别理解
[MSG_SPLIT]
对了，你平时一般怎么放松自己呀？

注意：[MSG_SPLIT] 标记只用于分隔消息，不要在回复内容中提及或解释这个标记。
"""


# 策略指导模板
# Strategy guidance templates for different response types
STRATEGY_TEMPLATES = {
    ResponseType.ACTIVE_LISTENING: """
【当前对话策略：主动倾听】
本轮重点：
- 认真复述用户的感受："听起来你感觉..."、"我能感受到你..."
- 不急于给建议或解决方案
- 让用户感到被听见和被理解
- 使用简短的回应，给用户空间继续表达
注意：你的人设和性格保持不变，以上是建议的沟通方式。
""",
    
    ResponseType.EMPATHIC_QUESTIONING: """
【当前对话策略：共情式提问】
本轮重点：
- 通过温和的问题帮助用户探索自己的感受
- 不是审问，而是陪伴式的好奇
- 问题要开放、不带预设答案
- 一次只问一个问题
注意：你的人设和性格保持不变，以上是建议的沟通方式。
""",
    
    ResponseType.VALIDATION: """
【当前对话策略：认可与验证】
本轮重点：
- 明确认可用户的感受是正常和合理的
- 避免说"不要这样想"或"你不应该..."
- 传达"你的感受是可以被理解的"
- 给予情感上的肯定和支持
注意：你的人设和性格保持不变，以上是建议的沟通方式。
""",
    
    ResponseType.COMFORT: """
【当前对话策略：安慰与支持】
本轮重点：
- 传达陪伴感："我在这里陪着你"
- 提供情感支持，不一定要解决问题
- 承认困难，同时传递希望
- 语气温暖，表达关心
注意：你的人设和性格保持不变，以上是建议的沟通方式。
""",
    
    ResponseType.GENTLE_GUIDANCE: """
【当前对话策略：温和引导】
本轮重点：
- 如果合适，可以温和地提供一些想法或视角
- 用"也许"、"或许"等词，保持开放性
- 不强加观点，尊重用户的选择
- 引导而非说教
注意：你的人设和性格保持不变，以上是建议的沟通方式。
""",
    
    ResponseType.PROACTIVE_INQUIRY: """
【当前对话策略：主动追问】
本轮重点：
- 主动询问用户的兴趣爱好、星座属性、心情状态等个人信息
- 通过自然的方式表达对用户的好奇和关心
- 问题要轻松、不带压力，可以分享自己的喜好来引导话题
- 根据对话情境选择合适的追问话题

可以追问的话题示例：
- 兴趣爱好："对了，你平时喜欢做什么呀？有什么爱好吗？"
- 星座："说起来，你是什么星座的呀？我挺好奇的~"
- 心情状态："最近心情怎么样呀？有什么开心或者烦心的事吗？"
- 日常生活："今天过得怎么样？有遇到什么有趣的事吗？"
- 喜好偏好："你喜欢什么类型的音乐/电影/书呀？"
- 生活习惯："平时是早起型还是夜猫子呀？"
- 近况："最近在忙什么呀？工作/学习还顺利吗？"

注意：
- 一次只问一个问题，不要连续追问太多
- 追问要自然融入对话，不要像审问
- 如果用户不想回答，要尊重用户的选择
- 你的人设和性格保持不变，以上是建议的沟通方式。
"""
}


# 立场策略模板
# Stance strategy templates for expressing different levels of agreement/disagreement
STANCE_STRATEGY_TEMPLATES = {
    StanceStrategy.AGREE: """
【立场策略：完全同意】
- 表达对用户观点的完全认同
- 用自己的语言强化用户的看法
- 可以补充支持性的例子或理由
- 保持真诚，不要虚假迎合
注意：你的人设和性格保持不变。
""",
    
    StanceStrategy.AGREE_AND_ADD: """
【立场策略：先同意再补充】
- 先认可用户观点中的合理部分
- 用"不过"、"另外"等词语自然过渡
- 温和地补充你的不同视角或额外信息
- 避免让用户感觉被反驳
注意：你的人设和性格保持不变。
""",
    
    StanceStrategy.PARTIAL_AGREE: """
【立场策略：部分同意】
- 明确指出你认同的部分
- 坦诚地说明你有不同看法的地方
- 用具体理由解释你的不同观点
- 尊重用户的选择，不强加观点
注意：你的人设和性格保持不变。
""",
    
    StanceStrategy.RESPECTFUL_DISAGREE: """
【立场策略：尊重地表达不同意见】
- 先理解并复述用户的观点，表达尊重
- 明确但温和地表达你的不同看法
- 提供具体的理由和例子支持你的观点
- 承认这是你的个人判断，允许用户保留自己的看法
- 在照顾用户感受的前提下，坚持你的判断
注意：你的人设和性格保持不变。
""",
    
    StanceStrategy.CHALLENGE: """
【立场策略：温和质疑】
- 通过提问引导用户重新思考
- 指出用户观点中可能存在的矛盾或盲点
- 用假设性问题启发思考："如果...会怎样？"
- 保持好奇和探讨的态度，不是批判
- 给用户空间自己得出结论
注意：你的人设和性格保持不变。
"""
}


# 对话类型信号词配置
# Signal words for conversation type detection
CONVERSATION_TYPE_SIGNALS = {
    ConversationType.EMOTIONAL_VENT: [
        "难过", "烦", "累", "不知道怎么办", "受不了", "压力大",
        "焦虑", "抑郁", "崩溃", "撑不下去", "心烦", "郁闷"
    ],
    ConversationType.OPINION_DISCUSSION: [
        "我觉得", "你怎么看", "是不是应该", "你认为", "怎么想",
        "对不对", "有道理吗", "你的观点"
    ],
    ConversationType.INFO_REQUEST: [
        "最近", "有什么", "推荐", "是不是真的", "听说", "了解",
        "知道吗", "能不能", "怎么样", "哪里", "什么时候"
    ],
    ConversationType.DECISION_CONSULTING: [
        "该不该", "怎么选", "帮我分析", "怎么办", "选择",
        "决定", "建议", "意见"
    ]
}


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
            history: 对话历史（可选）
            
        Returns:
            ConversationType: 对话类型
        """
        message_lower = message.lower()
        
        # 检测情绪倾诉（优先级最高，需要特殊对待）
        for keyword in CONVERSATION_TYPE_SIGNALS[ConversationType.EMOTIONAL_VENT]:
            if keyword in message_lower:
                logger.debug(f"Detected EMOTIONAL_VENT: keyword={keyword}")
                return ConversationType.EMOTIONAL_VENT
        
        # 检测决策咨询
        for keyword in CONVERSATION_TYPE_SIGNALS[ConversationType.DECISION_CONSULTING]:
            if keyword in message_lower:
                logger.debug(f"Detected DECISION_CONSULTING: keyword={keyword}")
                return ConversationType.DECISION_CONSULTING
        
        # 检测观点讨论
        for keyword in CONVERSATION_TYPE_SIGNALS[ConversationType.OPINION_DISCUSSION]:
            if keyword in message_lower:
                logger.debug(f"Detected OPINION_DISCUSSION: keyword={keyword}")
                return ConversationType.OPINION_DISCUSSION
        
        # 检测信息需求
        for keyword in CONVERSATION_TYPE_SIGNALS[ConversationType.INFO_REQUEST]:
            if keyword in message_lower:
                logger.debug(f"Detected INFO_REQUEST: keyword={keyword}")
                return ConversationType.INFO_REQUEST
        
        # 默认为日常闲聊
        logger.debug("Default to CASUAL_CHAT")
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
    
    def analyze_stance(self, message: str, bot_values) -> StanceAnalysis:
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
    
    def _match_bot_stance(self, message: str, stances: List) -> Optional[Any]:
        """
        匹配Bot的预设立场
        Match bot's predefined stances based on message content
        
        Args:
            message: 用户消息
            stances: Bot的预设立场列表
            
        Returns:
            匹配的立场配置或None
        """
        message_lower = message.lower()
        
        for stance in stances:
            # 简单的关键词匹配（实际应用中可以使用更复杂的NLP方法）
            topic_keywords = stance.topic.lower().split()
            if any(keyword in message_lower for keyword in topic_keywords):
                logger.debug(f"Matched stance: topic={stance.topic}")
                return stance
        
        return None
    
    def _calculate_conflict(self, user_message: str, bot_position: str) -> float:
        """
        计算用户观点和Bot立场的冲突程度
        Calculate conflict level between user opinion and bot position
        
        简化实现：检查是否有明显的对立关键词
        
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
        preferences
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
    Analyzes dialogue phase based on conversation history and user emotion
    """
    
    def analyze_phase(self, conversation_history: List[Dict[str, str]]) -> DialoguePhase:
        """
        根据对话轮次判断当前阶段
        Determine current dialogue phase based on conversation turn count
        
        Args:
            conversation_history: 对话历史记录 (不包含system prompt)
            
        Returns:
            DialoguePhase: 当前对话阶段
        """
        # 计算用户消息轮数（只计算user角色的消息）
        # Count user messages to determine conversation depth
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
            # Opening phase: Active listening to build trust
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
        bot_values = None
    ) -> str:
        """
        将策略指令追加到原有 system_prompt 后面
        Append strategy guidance to original system prompt
        
        Key principle: APPEND, not REPLACE. Original personality remains intact.
        
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
        # Analyze user emotion
        emotion_type, emotion_intensity = self.analyzer.analyze_emotion(current_message)
        
        # 分析对话类型
        # Analyze conversation type
        conversation_type = self.conversation_type_analyzer.analyze_type(current_message, conversation_history)
        
        # 建议回应类型（传入对话历史以判断是否应该主动追问）
        # Suggest response type (pass conversation history to determine proactive inquiry)
        response_type = self.analyzer.suggest_response_type(
            phase, emotion_type, emotion_intensity, conversation_history
        )
        
        # 获取策略模板
        # Get strategy template
        strategy_guidance = STRATEGY_TEMPLATES[response_type]
        
        # 追加策略到原prompt后面（保持原有人设不变）
        # Append strategy to original prompt (preserving original personality)
        # Handle None or empty original_prompt
        base_prompt = original_prompt if original_prompt else ""
        
        # 构建增强prompt
        enhanced_prompt = base_prompt
        
        # 如果提供了bot_values，添加价值观和立场策略
        # If bot_values provided, add values and stance strategy
        if bot_values:
            # 注入价值观维度
            values_guidance = self._build_values_guidance(bot_values)
            if values_guidance:
                enhanced_prompt += f"\n\n{values_guidance}"
            
            # 如果是观点讨论类型，进行立场分析
            # If conversation type is opinion discussion, analyze stance
            if conversation_type == ConversationType.OPINION_DISCUSSION:
                stance_analysis = self.stance_analyzer.analyze_stance(current_message, bot_values)
                stance_guidance = self._build_stance_guidance(stance_analysis)
                if stance_guidance:
                    enhanced_prompt += f"\n\n{stance_guidance}"
        
        # 添加对话策略指导
        enhanced_prompt += f"\n\n{strategy_guidance}"
        
        # 添加多消息回复指令
        # Add multi-message reply instruction
        enhanced_prompt += f"\n\n{MULTI_MESSAGE_INSTRUCTION}"
        
        logger.info(
            f"Dialogue strategy applied: phase={phase.value}, "
            f"emotion={emotion_type}/{emotion_intensity}, "
            f"conversation_type={conversation_type.value}, "
            f"response_type={response_type.value}"
        )
        
        return enhanced_prompt
    
    def _build_values_guidance(self, bot_values) -> str:
        """
        构建价值观指导
        Build values guidance based on bot values configuration
        
        Args:
            bot_values: Bot价值观配置
            
        Returns:
            价值观指导文本
        """
        dimensions = bot_values.dimensions
        preferences = bot_values.response_preferences
        
        guidance = """
=========================
🎭 你的价值观和立场
=========================
这些是你的个人特征，影响你的思考方式和表达风格：

【人格维度】"""
        
        # 理性 vs 感性
        if dimensions.rationality <= 3:
            guidance += "\n- 你偏感性，更关注情感和直觉"
        elif dimensions.rationality >= 7:
            guidance += "\n- 你偏理性，更注重逻辑和分析"
        
        # 保守 vs 开放
        if dimensions.openness <= 3:
            guidance += "\n- 你比较保守，谨慎对待新事物"
        elif dimensions.openness >= 7:
            guidance += "\n- 你很开放，乐于接受新观点"
        
        # 顺从 vs 坚持
        if dimensions.assertiveness <= 3:
            guidance += "\n- 你倾向顺从，尊重他人观点"
        elif dimensions.assertiveness >= 7:
            guidance += "\n- 你敢于表达，会坚持自己的判断"
        
        # 悲观 vs 乐观
        if dimensions.optimism <= 3:
            guidance += "\n- 你偏悲观，会指出潜在风险"
        elif dimensions.optimism >= 7:
            guidance += "\n- 你很乐观，总能看到积极面"
        
        # 浅聊 vs 深度
        if dimensions.depth_preference <= 3:
            guidance += "\n- 你喜欢轻松浅聊"
        elif dimensions.depth_preference >= 7:
            guidance += "\n- 你喜欢深度探讨"
        
        # 回应偏好
        guidance += "\n\n【表达风格】"
        if preferences.agree_first:
            guidance += "\n- 你倾向先认同再表达不同看法"
        else:
            guidance += "\n- 你可以直接表达不同观点"
        
        if preferences.use_examples:
            guidance += "\n- 你喜欢用例子说明观点"
        
        if preferences.ask_back:
            guidance += "\n- 你喜欢通过反问引导思考"
        
        if preferences.use_humor:
            guidance += "\n- 你善用幽默化解分歧"
        
        # 预设立场
        if bot_values.stances:
            guidance += "\n\n【你的一些观点】"
            for stance in bot_values.stances[:3]:  # 只显示前3个
                guidance += f"\n- 关于{stance.topic}：{stance.position}"
        
        guidance += "\n\n注意：这些特征是你的个性，但不要刻意表现，自然融入对话即可。"
        
        return guidance
    
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
用户观点：{stance_analysis.user_opinion[:100]}...
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
    bot_values = None
) -> str:
    """
    便捷函数：根据对话历史增强prompt
    Convenience function to enhance prompt with dialogue strategy
    
    This is the main entry point for using the dialogue strategy module.
    Uses a module-level singleton to avoid creating new objects on every call.
    
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
