"""
Handlers package
"""
from .commands import (
    start_command,
    help_command,
    status_command,
    subscribe_command,
    image_command,
    pay_basic_command,
    pay_premium_command,
    check_payment_command
)
from .messages import (
    handle_message,
    handle_photo,
    handle_sticker,
    error_handler
)
from .bot_commands import (
    list_bots_command,
    add_bot_command,
    remove_bot_command,
    my_bots_command,
    config_bot_command
)
from .feedback import (
    handle_message_reaction,
    handle_message_reaction_count,
    handle_reply_interaction,
    handle_pinned_message,
    handle_forward,
    feedback_stats_command,
    my_feedback_command
)
from .agent_integration import (
    handle_message_with_agents,
    handle_skill_callback,
    handle_skills_command,
    get_skill_callback_handler
)

__all__ = [
    # 基础命令
    "start_command",
    "help_command",
    "status_command",
    "subscribe_command",
    "image_command",
    "pay_basic_command",
    "pay_premium_command",
    "check_payment_command",
    # 消息处理
    "handle_message",
    "handle_photo",
    "handle_sticker",
    "error_handler",
    # Bot管理命令
    "list_bots_command",
    "add_bot_command",
    "remove_bot_command",
    "my_bots_command",
    "config_bot_command",
    # 反馈处理
    "handle_message_reaction",
    "handle_message_reaction_count",
    "handle_reply_interaction",
    "handle_pinned_message",
    "handle_forward",
    "feedback_stats_command",
    "my_feedback_command",
    # Agent集成 - 支持工具调用
    "handle_message_with_agents",
    "handle_skill_callback",
    "handle_skills_command",
    "get_skill_callback_handler",
]
