from enum import Enum
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from loguru import logger
from pathlib import Path

import yaml


# ========== Enum & dataclass 定义保持不变 ==========
class ProactiveMode(str, Enum):
    """主动对话模式"""
    EXPLORE_INTEREST = "explore_interest"
    DEEPEN_TOPIC = "deepen_topic"
    SHARE_AND_ASK = "share_and_ask"
    FIND_COMMON = "find_common"
    SHOW_CURIOSITY = "show_curiosity"
    RECALL_MEMORY = "recall_memory"
    SUPPORTIVE = "supportive"
    GENTLE_GUIDE = "gentle_guide"


class ConversationStage(str, Enum):
    """对话阶段"""
    OPENING = "opening"  # 开场阶段（1-2轮）
    EXPLORING = "exploring"  # 探索阶段（3-5轮）
    DEEPENING = "deepening"  # 深入阶段（6-10轮）
    ESTABLISHED = "established"  # 已建立关系（11轮+）


class UserEngagement(str, Enum):
    """用户参与度"""
    HIGH = "高参与度"
    MEDIUM = "中等参与度"
    LOW = "低参与度"


@dataclass
class UserProfile:
    """
    用户画像
    
    基于对话历史构建的用户画像，用于主动策略生成
    """
    interests: List[str] = field(default_factory=list)  # 用户兴趣
    personality_traits: List[str] = field(default_factory=list)  # 性格特征
    recent_topics: List[str] = field(default_factory=list)  # 近期讨论话题
    emotional_state: str = "无情绪波动"  # 当前情绪状态
    engagement_level: UserEngagement = UserEngagement.MEDIUM  # 参与度
    relationship_depth: int = 1  # 关系深度（1-5）


@dataclass
class TopicAnalysis:
    """
    话题分析
    
    分析当前对话中的话题深度和待探索方向
    """
    current_topic: Optional[str] = None  # 当前话题
    topic_depth: int = 1  # 话题深度（1-5）
    topics_to_explore: List[str] = field(default_factory=list)  # 待探索话题
    common_interests: List[str] = field(default_factory=list)  # 共同兴趣点


@dataclass
class ProactiveAction:
    """
    主动行动
    Bot 的主动对话建议
    """
    mode: ProactiveMode  # 主动模式
    suggestion: str  # 具体建议
    example_questions: List[str] = field(default_factory=list)  # 示例问题
    tone_guidance: str = ""  # 语气指导


# ========== 从 YAML 加载配置数据 ==========
_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "dialogue_strategy.yaml"


def _load_proactive_config():
    """从统一 YAML 加载主动策略相关配置"""
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError) as e:
        logger.error(f"❌ 主动策略配置加载失败: {e}")
        config = {}
    return config


_config = _load_proactive_config()

# 兴趣关键词库（原 INTEREST_CATEGORIES）
INTEREST_CATEGORIES: Dict[str, List[str]] = _config.get("interest_categories", {})

# 主动提问模板（原 PROACTIVE_QUESTIONS，需要从 YAML string key → ProactiveMode enum）
PROACTIVE_QUESTIONS: Dict[ProactiveMode, List[str]] = {
    ProactiveMode(k): v
    for k, v in _config.get("proactive_questions", {}).items()
}

# 主动分析关键词
_analysis_keywords = _config.get("proactive_analysis_keywords", {})


class ProactiveDialogueStrategyAnalyzer:
    """
    主动对话策略分析器
    
    分析对话上下文，生成主动对话策略
    """

    def __init__(self):
        self.interest_categories = INTEREST_CATEGORIES
        self.question_templates = PROACTIVE_QUESTIONS
        # 从 YAML 加载内联关键词
        self._emotional_positive = _analysis_keywords.get("emotional_state", {}).get("positive", [])
        self._emotional_negative = _analysis_keywords.get("emotional_state", {}).get("negative", [])
        self._topic_keywords = _analysis_keywords.get("topic_extraction", {})
        self._basic_topics = _analysis_keywords.get("basic_topics", [])
        self._default_explore = _analysis_keywords.get("default_explore_topics", [])

    def analyze_user_profile(
            self,
            conversation_history: List[Dict[str, str]],
            user_memories: Optional[List[Dict[str, Any]]] = None
    ) -> UserProfile:
        """
        构建用户画像
        
        Args:
            conversation_history: 对话历史
            user_memories: 用户长期记忆（可选）
            
        Returns:
            UserProfile: 用户画像
        """
        profile = UserProfile()

        # 提取用户兴趣
        profile.interests = self._extract_interests(conversation_history)
        # 分析参与度
        profile.engagement_level = self._analyze_engagement(conversation_history)
        # 分析情绪状态
        profile.emotional_state = self._analyze_emotional_state(conversation_history)
        # 计算关系深度
        user_turns = sum(1 for msg in conversation_history if msg.get("role") == "user")
        if user_turns <= 2:
            profile.relationship_depth = 1
        elif user_turns <= 5:
            profile.relationship_depth = 2
        elif user_turns <= 10:
            profile.relationship_depth = 3
        elif user_turns <= 20:
            profile.relationship_depth = 4
        else:
            profile.relationship_depth = 5
        # 提取近期话题
        profile.recent_topics = self._extract_recent_topics(conversation_history)
        logger.debug(f"用户画像: 兴趣={profile.interests}, 参与度={profile.engagement_level}, "
                     f"情绪={profile.emotional_state}, 关系深度={profile.relationship_depth}")
        return profile

    def analyze_topic(
            self,
            conversation_history: List[Dict[str, str]],
            user_profile: UserProfile
    ) -> TopicAnalysis:
        """
        分析话题
        
        Args:
            conversation_history: 对话历史
            user_profile: 用户画像
            
        Returns:
            TopicAnalysis: 话题分析
        """
        history_limit = 3  # 最近3条
        topic_limit = 3  # 最近3条
        analysis = TopicAnalysis()

        # 识别当前话题
        if conversation_history:
            recent_messages = conversation_history[-history_limit:]
            analysis.current_topic = self._identify_current_topic(recent_messages)

        # 计算话题深度（计算最长连续相同话题的次数）
        analysis.topic_depth = self._calculate_topic_depth(conversation_history)

        # 识别待探索话题
        analysis.topics_to_explore = self._identify_topics_to_explore(
            user_profile, conversation_history
        )

        # 识别共同兴趣
        analysis.common_interests = user_profile.interests[:topic_limit]  # 简化：前3个兴趣
        logger.debug(f"话题分析: 当前话题={analysis.current_topic}, 深度={analysis.topic_depth}, "
                     f"待探索={analysis.topics_to_explore}")

        return analysis

    def generate_proactive_strategy(
            self,
            user_profile: UserProfile,
            topic_analysis: TopicAnalysis,
            conversation_history: List[Dict[str, str]],
            user_memories: Optional[List[Dict[str, Any]]] = None
    ) -> ProactiveAction:
        """
        生成主动对话策略
        Args:
            user_profile: 用户画像
            topic_analysis: 话题分析
            conversation_history: 对话历史
            user_memories: 用户记忆（可选）
        Returns:
            ProactiveAction: 主动行动建议
        """
        # 确定对话阶段
        stage = self._determine_stage(user_profile.relationship_depth)
        # 根据情绪和阶段选择模式
        mode = self._select_proactive_mode(stage, user_profile, topic_analysis, user_memories)
        # 生成具体建议
        action = self._build_proactive_action(mode, user_profile, topic_analysis, user_memories)
        logger.info(f"生成主动策略: 模式={mode.value}, 阶段={stage.value}")
        return action

    def _extract_interests(self, conversation_history: List[Dict[str, str]]) -> List[str]:
        """从对话中提取用户兴趣"""
        interest_counts = {}
        for msg in conversation_history:
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "").lower()
            for interest, keywords in self.interest_categories.items():
                for keyword in keywords:
                    if keyword in content:
                        interest_counts[interest] = interest_counts.get(interest, 0) + 1
                        break
        # 按频次排序
        sorted_interests = sorted(interest_counts.items(), key=lambda x: x[1], reverse=True)
        interests = [interest for interest, _ in sorted_interests[:5]]
        return interests

    def _analyze_engagement(self, conversation_history: List[Dict[str, str]]) -> UserEngagement:
        """分析用户参与度"""
        if not conversation_history:
            return UserEngagement.MEDIUM

        # 获取最近的用户消息
        recent_user_msgs = [
            msg for msg in conversation_history[-6:]  # 最近6条
            if msg.get("role") == "user"
        ]

        if not recent_user_msgs:
            return UserEngagement.LOW

        # 计算平均长度
        avg_length = sum(len(msg.get("content", "")) for msg in recent_user_msgs) / len(recent_user_msgs)

        # 根据长度判断参与度
        if avg_length > 50:
            return UserEngagement.HIGH
        elif avg_length > 20:
            return UserEngagement.MEDIUM
        else:
            return UserEngagement.LOW

    def _analyze_emotional_state(self, conversation_history: List[Dict[str, str]]) -> str:
        """分析用户情绪状态"""
        if not conversation_history:
            return "无情绪波动"
        positive_keywords = self._emotional_positive
        negative_keywords = self._emotional_negative
        # 检查最近消息
        recent_user_msgs = [
            msg.get("content", "") for msg in conversation_history[-3:]
            if msg.get("role") == "user"
        ]
        if not recent_user_msgs:
            return "neutral"
        recent_text = " ".join(recent_user_msgs).lower()
        # 检测情绪
        has_positive = any(kw in recent_text for kw in positive_keywords)
        has_negative = any(kw in recent_text for kw in negative_keywords)
        if has_negative and not has_positive:
            return "积极情绪"
        elif has_positive and not has_negative:
            return "消极情绪"
        elif has_positive and has_negative:
            return "情绪转变中"
        else:
            return "无情绪波动"

    def _extract_recent_topics(self, conversation_history: List[Dict[str, str]]) -> List[str]:
        """提取近期讨论话题"""
        topic_keywords = dict(self._topic_keywords)
        topic_keywords["兴趣"] = list(self.interest_categories.keys())
        topics = set()
        for msg in conversation_history[-10:]:  # 最近10条
            content = msg.get("content", "").lower()
            for topic, keywords in topic_keywords.items():
                if any(kw in content for kw in keywords):
                    topics.add(topic)
        return list(topics)

    def _identify_current_topic(self, recent_messages: List[Dict[str, str]]) -> Optional[str]:
        """识别当前话题"""
        if not recent_messages:
            return None
        # 简化：使用最后一条用户消息的主要话题
        for msg in reversed(recent_messages):
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "")
            # 检查兴趣类别
            for interest, keywords in self.interest_categories.items():
                if any(kw in content for kw in keywords):
                    return interest
            # 检查基础话题
            for topic in self._basic_topics:
                if topic in content:
                    return topic
        return None

    def _calculate_topic_depth(self, conversation_history: List[Dict[str, str]]) -> int:
        """计算话题深度"""
        if not conversation_history:
            return 1

        # 简化实现：检查最近消息中话题的连续性
        recent_topics = []
        for msg in conversation_history[-6:]:
            topic = self._identify_current_topic([msg])
            if topic:
                recent_topics.append(topic)

        if not recent_topics:
            return 1

        # 计算最长连续相同话题
        max_depth = 1
        current_depth = 1
        for i in range(1, len(recent_topics)):
            if recent_topics[i] == recent_topics[i - 1]:
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            else:
                current_depth = 1

        return min(max_depth, 5)  # 最大深度5

    def _identify_topics_to_explore(
            self,
            user_profile: UserProfile,
            conversation_history: List[Dict[str, str]]
    ) -> List[str]:
        """识别待探索话题"""
        # 已讨论的话题
        discussed_topics = set(user_profile.recent_topics)
        # 用户兴趣中未深入讨论的
        topics_to_explore = []
        for interest in user_profile.interests:
            if interest not in discussed_topics:
                topics_to_explore.append(interest)
        # 如果用户兴趣未知，建议探索常见兴趣
        if not topics_to_explore and not user_profile.interests:
            topics_to_explore = list(self._default_explore)
        return topics_to_explore[:3]  # 最多3个

    def _determine_stage(self, relationship_depth: int) -> ConversationStage:
        """确定对话阶段"""
        if relationship_depth <= 1:
            return ConversationStage.OPENING
        elif relationship_depth <= 2:
            return ConversationStage.EXPLORING
        elif relationship_depth <= 3:
            return ConversationStage.DEEPENING
        else:
            return ConversationStage.ESTABLISHED

    def _select_proactive_mode(
            self,
            stage: ConversationStage,
            user_profile: UserProfile,
            topic_analysis: TopicAnalysis,
            user_memories: Optional[List[Dict[str, Any]]]
    ) -> ProactiveMode:
        """选择主动模式"""
        # 情绪低落时优先支持
        if user_profile.emotional_state == "negative":
            return ProactiveMode.SUPPORTIVE

        # 参与度低时温和引导
        if user_profile.engagement_level == UserEngagement.LOW:
            return ProactiveMode.GENTLE_GUIDE

        # 根据阶段选择
        if stage == ConversationStage.OPENING:
            return ProactiveMode.EXPLORE_INTEREST

        elif stage == ConversationStage.EXPLORING:
            # 如果发现话题，深入探索
            if topic_analysis.current_topic and topic_analysis.topic_depth < 3:
                return ProactiveMode.DEEPEN_TOPIC
            # 否则继续探索兴趣
            return ProactiveMode.EXPLORE_INTEREST

        elif stage == ConversationStage.DEEPENING:
            # 发现共同兴趣时表达共鸣
            if topic_analysis.common_interests:
                return ProactiveMode.FIND_COMMON
            # 用户积极时表达好奇
            if user_profile.engagement_level == UserEngagement.HIGH:
                return ProactiveMode.SHOW_CURIOSITY
            # 深入当前话题
            return ProactiveMode.DEEPEN_TOPIC

        else:  # ESTABLISHED
            # 有记忆可以追问
            if user_memories and len(user_memories) > 0:
                return ProactiveMode.RECALL_MEMORY
            # 分享观点并提问
            if topic_analysis.current_topic:
                return ProactiveMode.SHARE_AND_ASK
            # 寻找共同点
            return ProactiveMode.FIND_COMMON

    def _build_proactive_action(
            self,
            mode: ProactiveMode,
            user_profile: UserProfile,
            topic_analysis: TopicAnalysis,
            user_memories: Optional[List[Dict[str, Any]]]
    ) -> ProactiveAction:
        """构建主动行动"""
        action = ProactiveAction(mode=mode, suggestion="")

        if mode == ProactiveMode.EXPLORE_INTEREST:
            action.suggestion = "主动询问用户的兴趣爱好、星座、心情等个人信息"
            action.example_questions = self._fill_question_templates(
                mode, {"category": "游戏、电影、音乐"}
            )
            action.tone_guidance = "轻松、好奇、不带压力"

        elif mode == ProactiveMode.DEEPEN_TOPIC:
            topic = topic_analysis.current_topic or "这个话题"
            action.suggestion = f"深入探索用户对 {topic} 的兴趣"
            action.example_questions = self._fill_question_templates(
                mode, {"topic": topic}
            )
            action.tone_guidance = "感兴趣、追问细节、表达共鸣"

        elif mode == ProactiveMode.SHARE_AND_ASK:
            topic = topic_analysis.current_topic or "这个话题"
            action.suggestion = f"分享自己对 {topic} 的看法，然后提问"
            action.example_questions = self._fill_question_templates(
                mode, {"topic": topic, "interest": "喜欢", "detail": "相关内容", "opinion": "某个观点"}
            )
            action.tone_guidance = "分享个人观点、引导互动"

        elif mode == ProactiveMode.FIND_COMMON:
            interests = topic_analysis.common_interests
            if interests:
                interest = interests[0]
                action.suggestion = f"发现共同兴趣 {interest}，积极表达共鸣"
                action.example_questions = self._fill_question_templates(
                    mode, {"interest": interest, "activity": "一起玩", "specific_activity": "玩"}
                )
            else:
                action.suggestion = "寻找与用户的共同点"
                action.example_questions = ["我也喜欢！", "咱们想到一起去了~"]
            action.tone_guidance = "兴奋、建立连接、表达'我也是'"

        elif mode == ProactiveMode.SHOW_CURIOSITY:
            action.suggestion = "对用户分享的内容表达好奇，鼓励继续"
            action.example_questions = self.question_templates[mode]
            action.tone_guidance = "好奇、鼓励、积极回应"

        elif mode == ProactiveMode.RECALL_MEMORY:
            if user_memories and len(user_memories) > 0:
                memory = user_memories[0]
                memory_topic = memory.get("event_summary", "")[:20]
                action.suggestion = f"回忆用户之前提到的：{memory_topic}"
                action.example_questions = self._fill_question_templates(
                    mode, {"memory_topic": memory_topic, "memory_content": memory_topic, "activity": "做"}
                )
            else:
                action.suggestion = "回忆之前的对话内容并追问"
                action.example_questions = ["对了，你之前提到...", "记得你说过..."]
            action.tone_guidance = "记得细节、表达关心"

        elif mode == ProactiveMode.SUPPORTIVE:
            action.suggestion = "倾听支持，少主动，多回应"
            action.example_questions = [
                "我在这里陪着你",
                "你的感受是可以理解的",
                "有什么想说的都可以告诉我"
            ]
            action.tone_guidance = "温暖、支持、不施压"

        elif mode == ProactiveMode.GENTLE_GUIDE:
            action.suggestion = "简短回应，不施压，保持温和"
            action.example_questions = [
                "嗯嗯~",
                "我懂的",
                "有需要随时跟我说~"
            ]
            action.tone_guidance = "温和、不追问、给空间"

        return action

    def _fill_question_templates(
            self,
            mode: ProactiveMode,
            context: Dict[str, str]
    ) -> List[str]:
        """填充问题模板"""
        templates = self.question_templates.get(mode, [])
        filled_questions = []
        for template in templates:
            try:
                filled = template.format(**context)
                filled_questions.append(filled)
            except KeyError:
                # 如果模板中的变量不在 context 中，使用原模板
                filled_questions.append(template)
        return filled_questions[:3]  # 最多3个示例

    def format_proactive_guidance(self, action: ProactiveAction) -> str:
        """
        格式化主动策略为提示词
        
        Args:
            action: 主动行动
            
        Returns:
            格式化的策略文本
        """
        guidance = f"""【主动互动建议】
- 模式：{action.mode.value}
- 策略：{action.suggestion}
- 语气：{action.tone_guidance}

【可以这样回复】
"""
        for i, question in enumerate(action.example_questions, 1):
            guidance += f"{i}. {question}\n"

        return guidance.strip()
