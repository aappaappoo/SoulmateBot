"""
Dialogue Strategy Configuration - 对话策略配置文件

集中存储所有对话策略、立场规则和相关配置常量。

包含：
1. 对话类型分类 (ConversationType)
2. 立场表达策略 (StanceStrategy)
3. 对话阶段 (DialoguePhase)
4. 回应类型 (ResponseType)
5. 情绪关键词配置 (EMOTION_KEYWORDS)
6. 策略指导模板 (STRATEGY_TEMPLATES)
7. 立场策略模板 (STANCE_STRATEGY_TEMPLATES)
8. 对话类型信号词 (CONVERSATION_TYPE_SIGNALS)
"""

from enum import Enum


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
