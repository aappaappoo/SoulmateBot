"""
Emotion parser utility for LLM responses
从LLM响应中解析语气标签并分离干净文本

Supports two formats:
1. Legacy prefix format: （语气：开心、轻快、兴奋，语速稍快，语调上扬）这是内容
2. JSON format: {"response": "这是内容", "emotion_info": {"emotion_type": "happy", "intensity": "high", "tone_description": "开心、轻快"}}
"""
import re
import json
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass
from loguru import logger


# Pattern to match emotion prefix in format: （语气：...）
# Matches Chinese parentheses （）containing emotion description starting with 语气：
EMOTION_PATTERN = re.compile(r'^（语气：[^）]+）')

# Mapping from keywords in emotion prefix to TTS emotion tags
# Note: These keywords are extracted from common Chinese emotion descriptions
# and mapped to the TTS service's supported emotion tags
EMOTION_KEYWORDS_MAP = {
    # Happy/Excited emotions
    "开心": "happy",
    "轻快": "happy",
    "兴奋": "excited",
    "活跃": "excited",
    # Gentle/Warm emotions
    "温柔": "gentle",
    "轻声": "gentle",
    "柔和": "gentle",
    "温暖": "gentle",
    # Sad/Down emotions
    "低落": "sad",
    "克制": "sad",
    "伤感": "sad",
    "难过": "sad",
    # Angry emotions
    "生气": "angry",
    "愤怒": "angry",
    # Crying emotions
    "委屈": "crying",
    "哭泣": "crying",
}


@dataclass
class ParsedEmotionResponse:
    """
    解析后的情绪响应对象
    
    Attributes:
        clean_text: 干净的响应文本（不包含情绪前缀或JSON结构）
        emotion_type: 情绪类型
        intensity: 情绪强度
        tone_description: 语气描述（原始中文描述）
    """
    clean_text: str
    emotion_type: Optional[str] = None
    intensity: Optional[str] = None
    tone_description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "clean_text": self.clean_text,
            "emotion_type": self.emotion_type,
            "intensity": self.intensity,
            "tone_description": self.tone_description
        }
    
    def get_emotion_info_dict(self) -> Optional[Dict[str, Any]]:
        """获取情绪信息字典（不包含clean_text）"""
        if not self.emotion_type and not self.intensity and not self.tone_description:
            return None
        return {
            "emotion_type": self.emotion_type,
            "intensity": self.intensity,
            "tone_description": self.tone_description
        }


def parse_llm_response_with_emotion(response: str) -> ParsedEmotionResponse:
    """
    解析LLM响应，提取情绪信息和干净文本。
    
    支持两种格式：
    1. JSON格式：{"response": "...", "emotion_info": {...}}
    2. 前缀格式：（语气：...）内容
    
    Args:
        response: LLM原始响应
        
    Returns:
        ParsedEmotionResponse对象，包含干净文本和情绪信息
    """
    if not response:
        return ParsedEmotionResponse(clean_text="")
    
    # Try to parse as JSON first
    json_result = _try_parse_json_format(response)
    if json_result:
        logger.debug(f"🎭 Parsed JSON emotion format: emotion_type={json_result.emotion_type}, intensity={json_result.intensity}")
        return json_result
    
    # Fall back to legacy prefix format
    emotion_tag, clean_text = extract_emotion_and_text(response)
    
    # If we found emotion from prefix, extract additional info
    if emotion_tag:
        # Get the prefix for tone description
        match = EMOTION_PATTERN.match(response)
        tone_desc = match.group(0)[4:-1] if match else None  # Remove （语气： and ）
        
        # Try to determine intensity from the prefix
        intensity = _parse_intensity_from_text(response)
        
        return ParsedEmotionResponse(
            clean_text=clean_text,
            emotion_type=emotion_tag,
            intensity=intensity,
            tone_description=tone_desc
        )
    
    return ParsedEmotionResponse(clean_text=clean_text)


def _try_parse_json_format(response: str) -> Optional[ParsedEmotionResponse]:
    """
    尝试将响应解析为JSON格式。
    
    期望格式：
    {
        "response": "回复内容",
        "emotion_info": {
            "emotion_type": "happy",
            "intensity": "high", 
            "tone_description": "开心、轻快、兴奋"
        }
    }
    
    Args:
        response: LLM响应字符串
        
    Returns:
        ParsedEmotionResponse对象或None（如果不是有效的JSON格式）
    """
    try:
        # Try to find JSON in the response
        # The response might be pure JSON or JSON wrapped in text
        stripped = response.strip()
        
        # Check if it starts with { and ends with }
        if not (stripped.startswith('{') and stripped.endswith('}')):
            return None
        
        data = json.loads(stripped)
        
        # Check required fields
        if "response" not in data:
            return None
        
        clean_text = data.get("response", "")
        emotion_info = data.get("emotion_info", {})
        
        # Validate emotion_info is a dict before accessing
        if emotion_info and isinstance(emotion_info, dict):
            return ParsedEmotionResponse(
                clean_text=clean_text,
                emotion_type=emotion_info.get("emotion_type"),
                intensity=emotion_info.get("intensity"),
                tone_description=emotion_info.get("tone_description")
            )
        else:
            return ParsedEmotionResponse(clean_text=clean_text)
            
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None


def _parse_intensity_from_text(text: str) -> str:
    """
    从文本中解析情绪强度。
    
    Args:
        text: 包含情绪描述的文本
        
    Returns:
        强度级别（high, medium, low），默认为 medium
    """
    # Check intensity in priority order: high > medium > low
    # Group keywords by intensity level
    high_keywords = ["高", "强", "强烈", "非常", "极度"]
    medium_keywords = ["中", "适中", "一般"]
    low_keywords = ["低", "轻微", "略微", "有点"]
    
    for keyword in high_keywords:
        if keyword in text:
            return "high"
    
    for keyword in medium_keywords:
        if keyword in text:
            return "medium"
    
    for keyword in low_keywords:
        if keyword in text:
            return "low"
    
    return "medium"  # Default to medium if no intensity keywords found


def extract_emotion_and_text(response: str) -> Tuple[Optional[str], str]:
    """
    Extract emotion tag and clean text from LLM response.
    
    从LLM响应中提取语气标签和干净文本。
    
    Args:
        response: The full LLM response that may contain emotion prefix
        
    Returns:
        Tuple of (emotion_tag, clean_text) where:
        - emotion_tag: One of "happy", "gentle", "sad", "excited", "angry", "crying" or None
        - clean_text: The response text with emotion prefix stripped
        
    Examples:
        >>> extract_emotion_and_text("（语气：开心、轻快）你好啊！")
        ("happy", "你好啊！")
        
        >>> extract_emotion_and_text("（语气：生气，愤怒）这太过分了！")
        ("angry", "这太过分了！")
        
        >>> extract_emotion_and_text("普通回复内容")
        (None, "普通回复内容")
    """
    if not response:
        return None, ""
    
    # Try to match emotion prefix at the start of the response
    match = EMOTION_PATTERN.match(response)
    
    if not match:
        # No emotion prefix found, return original text
        return None, response
    
    # Extract the emotion prefix
    emotion_prefix = match.group(0)
    
    # Get the clean text by removing the emotion prefix
    clean_text = response[len(emotion_prefix):].lstrip()
    
    # Determine the emotion tag based on keywords in the prefix
    emotion_tag = _parse_emotion_from_prefix(emotion_prefix)
    
    logger.debug(f"🎭 Parsed emotion: prefix='{emotion_prefix}', tag='{emotion_tag}'")
    
    return emotion_tag, clean_text


def _parse_emotion_from_prefix(emotion_prefix: str) -> Optional[str]:
    """
    Parse emotion tag from emotion prefix string.
    
    根据语气前缀内容判断情绪标签。
    
    Args:
        emotion_prefix: The emotion prefix like "（语气：开心、轻快，语速稍快）"
        
    Returns:
        Emotion tag string or None if no matching emotion found
    """
    # Check for each keyword in priority order
    # Priority: angry > crying > sad > excited > happy > gentle
    priority_order = ["angry", "crying", "sad", "excited", "happy", "gentle"]
    
    for target_emotion in priority_order:
        for keyword, emotion in EMOTION_KEYWORDS_MAP.items():
            if emotion == target_emotion and keyword in emotion_prefix:
                return emotion
    
    return None


def strip_emotion_prefix(response: str) -> str:
    """
    Strip emotion prefix from response, returning only clean text.
    
    仅去除语气前缀，返回干净文本。
    
    Args:
        response: The full LLM response that may contain emotion prefix
        
    Returns:
        Clean text with emotion prefix stripped
    """
    _, clean_text = extract_emotion_and_text(response)
    return clean_text


# Multi-message split marker
MSG_SPLIT_MARKER = "[MSG_SPLIT]"


def parse_multi_message_response(response: str) -> Tuple[list, str]:
    """
    Parse LLM response to extract multiple messages if split markers are present.
    
    解析LLM响应，提取多条消息（如果存在分隔标记）。
    
    The LLM may include [MSG_SPLIT] markers to indicate where the response should
    be split into multiple Telegram messages. This function extracts each message
    while also returning the full content for storage/history purposes.
    
    Args:
        response: The LLM response that may contain [MSG_SPLIT] markers
        
    Returns:
        Tuple of (messages_list, full_content) where:
        - messages_list: List of individual message strings to send separately
        - full_content: The complete response without split markers (for storage)
        
    Examples:
        >>> parse_multi_message_response("你好啊[MSG_SPLIT]最近怎么样？")
        (["你好啊", "最近怎么样？"], "你好啊\n最近怎么样？")
        
        >>> parse_multi_message_response("普通回复内容")
        (["普通回复内容"], "普通回复内容")
    """
    if not response:
        return [], ""
    
    # Check if the response contains split markers
    if MSG_SPLIT_MARKER not in response:
        return [response.strip()], response.strip()
    
    # Split the response by the marker
    parts = response.split(MSG_SPLIT_MARKER)
    
    # Clean up each part and filter out empty strings
    messages = [part.strip() for part in parts if part.strip()]
    
    # Limit to maximum 3 messages to avoid spam
    if len(messages) > 3:
        logger.warning(f"📝 Multi-message response exceeded limit, truncating from {len(messages)} to 3 messages")
        messages = messages[:3]
    
    # Create full content by joining with newlines (for storage/history)
    full_content = "\n".join(messages)
    
    logger.info(f"📝 Parsed multi-message response: {len(messages)} message(s)")
    
    return messages, full_content
