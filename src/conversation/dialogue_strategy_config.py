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
    # 情绪倾诉 — 用户在宣泄情绪（如"好烦"、"压力大"、"崩溃"）
    EMOTIONAL_VENT = "emotional_vent"
    # 观点讨论 — 用户在表达观点并寻求交流（如"我觉得..."、"你怎么看"）
    OPINION_DISCUSSION = "opinion_discussion"
    # 信息需求 — 用户在寻求信息或知识（如"推荐"、"知道吗"、"怎么回事"）
    INFO_REQUEST = "info_request"
    # 决策咨询 — 用户面临选择需要帮助（如"该不该"、"怎么选"、"帮我分析"）
    DECISION_CONSULTING = "decision_consulting"
    # 日常闲聊 — 没有匹配到任何特殊类型时的默认兜底
    CASUAL_CHAT = "casual_chat"


class StanceStrategy(str, Enum):
    """
    立场表达策略
    """
    # 完全同意 — 表达对用户观点的完全认同
    AGREE = "agree"
    # 先同意再补充 — 先认可用户合理部分，再温和地补充不同视角
    AGREE_AND_ADD = "agree_and_add"
    # 部分同意 — 明确指出认同和不认同的部分
    PARTIAL_AGREE = "partial_agree"
    # 尊重地表达不同意见 — 先复述用户观点表示尊重，再明确表达不同看法
    RESPECTFUL_DISAGREE = "respectful_disagree"
    # 温和质疑 — 通过提问引导用户重新思考，指出潜在矛盾
    CHALLENGE = "challenge"


class DialoguePhase(Enum):
    # 开场阶段（用户消息 ≤ 2 轮）
    OPENING = "opening"
    # 倾听阶段（用户消息 3 ~ 5 轮）
    LISTENING = "listening"
    # 深入阶段（用户消息 6 ~ 8 轮）
    DEEPENING = "deepening"
    # 支持阶段（用户消息 ≥ 9 轮）
    SUPPORTING = "supporting"


class ResponseType(Enum):
    # 主动倾听 — "听起来你感觉..."、"我能感受到你..."
    ACTIVE_LISTENING = "active_listening"
    # 共情式提问 — 通过温和问题帮助用户探索感受
    EMPATHIC_QUESTIONING = "empathic_questioning"
    # 认可与验证 — 明确认可用户感受是正常合理的
    VALIDATION = "validation"
    # 安慰与支持 — "我在这里陪着你"
    COMFORT = "comfort"
    # 温和引导 — 用"也许"、"或许"等词温和提供想法或视角
    GENTLE_GUIDANCE = "gentle_guidance"
    # 主动追问 — 主动询问用户兴趣爱好、星座、心情等个人信息
    PROACTIVE_INQUIRY = "proactive_inquiry"


# ========== 从 YAML 构建运行时常量 ==========
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