"""
Bot configuration helper utilities
Bot 配置辅助工具
"""
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from telegram.ext import ContextTypes
    from src.bot.config_loader import ValuesConfig


def get_bot_values(context: "ContextTypes.DEFAULT_TYPE") -> Optional["ValuesConfig"]:
    """
    从 context.bot_data 中提取 bot_values 配置
    
    Extract bot_values configuration from context.bot_data
    
    Args:
        context: Telegram bot context
        
    Returns:
        ValuesConfig if bot_config exists and has values, None otherwise
    """
    bot_config = context.bot_data.get("bot_config")
    return bot_config.values if bot_config else None
