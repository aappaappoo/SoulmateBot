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
from typing import List, Dict, Tuple, Optional
from loguru import logger


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
"""
}


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
        emotion_intensity: str
    ) -> ResponseType:
        """
        根据阶段和情绪建议回应类型
        Suggest appropriate response type based on phase and emotion
        
        Args:
            phase: 当前对话阶段
            emotion_type: 情绪类型 ("positive", "negative", "neutral")
            emotion_intensity: 情绪强度 ("high", "medium", "low")
            
        Returns:
            ResponseType: 建议的回应类型
        """
        # 紧急情况：高强度负面情绪，优先安慰
        # Emergency: High-intensity negative emotions require immediate comfort
        if emotion_type == "negative" and emotion_intensity == "high":
            return ResponseType.COMFORT
        
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
            else:
                return ResponseType.ACTIVE_LISTENING
                
        elif phase == DialoguePhase.DEEPENING:
            # 深入阶段：共情式提问，帮助探索
            # Deepening phase: Empathic questioning for exploration
            if emotion_type == "negative" and emotion_intensity in ["high", "medium"]:
                return ResponseType.COMFORT  # 中高强度负面情绪需要安慰
            else:
                return ResponseType.EMPATHIC_QUESTIONING
                
        else:  # DialoguePhase.SUPPORTING
            # 支持阶段：可以适当引导
            # Supporting phase: Gentle guidance when appropriate
            if emotion_type == "positive":
                return ResponseType.EMPATHIC_QUESTIONING  # 积极情绪时继续探索
            elif emotion_type == "negative":
                if emotion_intensity == "low":
                    return ResponseType.GENTLE_GUIDANCE  # 低强度负面可以引导
                else:
                    return ResponseType.COMFORT  # 中高强度负面需要安慰
            else:
                return ResponseType.GENTLE_GUIDANCE


class DialogueStrategyInjector:
    """
    对话策略注入器
    Injects strategy guidance into system prompt while preserving original personality
    """
    
    def __init__(self):
        self.analyzer = DialoguePhaseAnalyzer()
    
    def inject_strategy(
        self,
        original_prompt: str,
        conversation_history: List[Dict[str, str]],
        current_message: str
    ) -> str:
        """
        将策略指令追加到原有 system_prompt 后面
        Append strategy guidance to original system prompt
        
        Key principle: APPEND, not REPLACE. Original personality remains intact.
        
        Args:
            original_prompt: 原始system prompt（包含完整人设）
            conversation_history: 对话历史（不包含system prompt）
            current_message: 当前用户消息
            
        Returns:
            str: 增强后的system prompt
        """
        # 分析对话阶段
        # Analyze dialogue phase
        phase = self.analyzer.analyze_phase(conversation_history)
        
        # 分析用户情绪
        # Analyze user emotion
        emotion_type, emotion_intensity = self.analyzer.analyze_emotion(current_message)
        
        # 建议回应类型
        # Suggest response type
        response_type = self.analyzer.suggest_response_type(phase, emotion_type, emotion_intensity)
        
        # 获取策略模板
        # Get strategy template
        strategy_guidance = STRATEGY_TEMPLATES[response_type]
        
        # 追加策略到原prompt后面（保持原有人设不变）
        # Append strategy to original prompt (preserving original personality)
        # Handle None or empty original_prompt
        base_prompt = original_prompt if original_prompt else ""
        enhanced_prompt = f"{base_prompt}\n\n{strategy_guidance}"
        
        logger.info(
            f"Dialogue strategy applied: phase={phase.value}, "
            f"emotion={emotion_type}/{emotion_intensity}, "
            f"response_type={response_type.value}"
        )
        
        return enhanced_prompt


# Module-level singleton to avoid unnecessary object allocation
_injector_instance: Optional[DialogueStrategyInjector] = None


def enhance_prompt_with_strategy(
    original_prompt: str,
    conversation_history: List[Dict[str, str]],
    current_message: str
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
        
    Returns:
        str: 增强后的system prompt
        
    Example:
        ```python
        enhanced_prompt = enhance_prompt_with_strategy(
            original_prompt=bot.system_prompt,
            conversation_history=history,
            current_message=message_text
        )
        history.insert(0, {"role": "system", "content": enhanced_prompt})
        ```
    """
    global _injector_instance
    if _injector_instance is None:
        _injector_instance = DialogueStrategyInjector()
    return _injector_instance.inject_strategy(original_prompt, conversation_history, current_message)
