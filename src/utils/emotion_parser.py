"""
Emotion parser utility for LLM responses
从LLM响应中解析语气标签并分离干净文本

LLM responses may contain emotion prefixes like:
- （语气：开心、轻快、兴奋，语速稍快，语调上扬）这是内容
- （语气：低落、语速较慢，情绪克制）这是内容
- （语气：生气，愤怒）这是内容
- （语气：温柔、轻声、放慢语速，语调柔和）这是内容
"""
import re
from typing import Tuple, Optional
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
