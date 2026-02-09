"""
Dialogue Strategy Configuration - 对话策略配置文件

从 YAML 配置文件加载所有对话策略配置数据。
Enum 类型定义保留在 Python 中，配置数据从 YAML 读取。
"""

from enum import Enum
from pathlib import Path
from typing import Dict, Any

import yaml
from loguru import logger


# ========== 加载 YAML 配置 ==========
_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "dialogue_strategy.yaml"


def _load_yaml_config() -> Dict[str, Any]:
    """加载对话策略 YAML 配置文件"""
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            logger.info(f"✅ 对话策略配置已加载: {_CONFIG_PATH}")
            return config or {}
    except FileNotFoundError:
        logger.error(f"❌ 对话策略配置文件未找到: {_CONFIG_PATH}")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"❌ 对话策略配置文件解析失败: {e}")
        return {}


_config = _load_yaml_config()


# ========== Enum 定义保持不变 ==========

class ConversationType(str, Enum):
    """对话类型分类"""
    EMOTIONAL_VENT = "emotional_vent"
    OPINION_DISCUSSION = "opinion_discussion"
    INFO_REQUEST = "info_request"
    DECISION_CONSULTING = "decision_consulting"
    CASUAL_CHAT = "casual_chat"


class StanceStrategy(str, Enum):
    """立场表达策略"""
    AGREE = "agree"
    AGREE_AND_ADD = "agree_and_add"
    PARTIAL_AGREE = "partial_agree"
    RESPECTFUL_DISAGREE = "respectful_disagree"
    CHALLENGE = "challenge"


class DialoguePhase(Enum):
    """对话阶段枚举"""
    OPENING = "opening"
    LISTENING = "listening"
    DEEPENING = "deepening"
    SUPPORTING = "supporting"


class ResponseType(Enum):
    """回应类型枚举"""
    ACTIVE_LISTENING = "active_listening"
    EMPATHIC_QUESTIONING = "empathic_questioning"
    VALIDATION = "validation"
    COMFORT = "comfort"
    GENTLE_GUIDANCE = "gentle_guidance"
    PROACTIVE_INQUIRY = "proactive_inquiry"


# ========== 从 YAML 构建运行时常量 ==========

# 情绪关键词 → dict 结构不变，直接取
EMOTION_KEYWORDS: Dict = _config.get("emotion_keywords", {})

# 策略模板 → YAML string key 映射到 ResponseType enum
STRATEGY_TEMPLATES: Dict[ResponseType, str] = {
    ResponseType(k): v
    for k, v in _config.get("strategy_templates", {}).items()
}

# 立场策略模板 → YAML string key 映射到 StanceStrategy enum
STANCE_STRATEGY_TEMPLATES: Dict[StanceStrategy, str] = {
    StanceStrategy(k): v
    for k, v in _config.get("stance_strategy_templates", {}).items()
}

# 对话类型信号词 → YAML string key 映射到 ConversationType enum
# 不管 YAML 中用 ["a","b"] 还是 - "a" 格式，解析后都是 list
CONVERSATION_TYPE_SIGNALS: Dict[ConversationType, list] = {
    ConversationType(k): v
    for k, v in _config.get("conversation_type_signals", {}).items()
}


def reload_config():
    """热重载配置"""
    global _config, EMOTION_KEYWORDS, STRATEGY_TEMPLATES, STANCE_STRATEGY_TEMPLATES, CONVERSATION_TYPE_SIGNALS
    _config = _load_yaml_config()
    EMOTION_KEYWORDS = _config.get("emotion_keywords", {})
    STRATEGY_TEMPLATES = {
        ResponseType(k): v for k, v in _config.get("strategy_templates", {}).items()
    }
    STANCE_STRATEGY_TEMPLATES = {
        StanceStrategy(k): v for k, v in _config.get("stance_strategy_templates", {}).items()
    }
    CONVERSATION_TYPE_SIGNALS = {
        ConversationType(k): v for k, v in _config.get("conversation_type_signals", {}).items()
    }
    logger.info("🔄 对话策略配置已重载")