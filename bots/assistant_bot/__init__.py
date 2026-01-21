"""
Assistant Bot - 智能助手机器人

通用智能助手，帮助用户解决各种问题
"""
from pathlib import Path

# Bot目录路径
BOT_DIR = Path(__file__).parent

# 配置文件路径
CONFIG_FILE = BOT_DIR / "config.yaml"

# Bot标识
BOT_ID = "assistant_bot"
BOT_NAME = "AssistantBot"
BOT_DESCRIPTION = "智能助手，帮你解决各种问题"
