"""
语音命令处理器
处理用户开启/关闭语音回复的命令
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from loguru import logger

from src.services.voice_preference_service import voice_preference_service


async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /voice 命令 - 显示语音设置菜单
    """
    user_id = update.effective_user.id
    bot_username = context.bot.username

    logger.info(f"🎤 [VOICE CMD] /voice command received from user_id={user_id}, bot=@{bot_username}")

    # 获取当前状态
    is_enabled = voice_preference_service.is_voice_enabled(user_id, bot_username)
    status = "✅ 已开启" if is_enabled else "❌ 已关闭"
    
    logger.info(f"🎤 [VOICE CMD] Current voice status for user_id={user_id}: enabled={is_enabled}")

    # 创建按钮
    keyboard = [
        [
            InlineKeyboardButton(
                "🎤 开启语音" if not is_enabled else "📝 关闭语音",
                callback_data=f"voice_toggle"
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🎙️ **语音回复设置**\n\n"
        f"当前状态: {status}\n\n"
        f"开启后，我会用语音回复你的消息~",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    logger.info(f"🎤 [VOICE CMD] Voice settings menu sent to user_id={user_id}")


async def voice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理语音设置按钮回调
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    bot_username = context.bot.username

    logger.info(f"🎤 [VOICE CALLBACK] Voice toggle callback received from user_id={user_id}, bot=@{bot_username}")

    if query.data == "voice_toggle":
        # 切换状态
        new_state = voice_preference_service.toggle_voice(user_id, bot_username)
        logger.info(f"🎤 [VOICE CALLBACK] Voice preference toggled for user_id={user_id}: new_state={new_state}")

        if new_state:
            status = "✅ 已开启"
            message = "🎤 语音回复功能已开启，后续的对话将使用语音进行回复"
            button_text = "📝 关闭语音"
        else:
            status = "❌ 已关闭"
            message = "📝 语音回复功能已关闭，后续的对话将使用文本进行回复"
            button_text = "🎤 开启语音"

        # 新按钮
        keyboard = [[InlineKeyboardButton(button_text, callback_data="voice_toggle")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🎙️ **语音回复设置**\n\n"
            f"当前状态: {status}\n\n"
            f"{message}",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        logger.info(f"🎤 [VOICE CALLBACK] Voice settings updated for user_id={user_id}")


async def voice_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /voice_on 命令 - 快速开启语音
    """
    user_id = update.effective_user.id
    bot_username = context.bot.username

    logger.info(f"🎤 [VOICE ON] /voice_on command received from user_id={user_id}, bot=@{bot_username}")

    voice_preference_service.set_voice_enabled(user_id, bot_username, True)
    logger.info(f"🎤 [VOICE ON] Voice preference set to enabled for user_id={user_id}")
    
    # 仅发送文本提示消息
    confirmation_text = "🎤 语音回复功能已开启，后续的对话将使用语音进行回复"
    await update.message.reply_text(confirmation_text)
    logger.info(f"🎤 [VOICE ON] Confirmation sent for user_id={user_id}")


async def voice_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /voice_off 命令 - 快速关闭语音
    """
    user_id = update.effective_user.id
    bot_username = context.bot.username
    
    logger.info(f"🎤 [VOICE OFF] /voice_off command received from user_id={user_id}, bot=@{bot_username}")
    
    # 关闭语音设置
    voice_preference_service.set_voice_enabled(user_id, bot_username, False)
    logger.info(f"🎤 [VOICE OFF] Voice preference set to disabled for user_id={user_id}")
    
    # 仅发送文本提示消息
    confirmation_text = "📝 语音回复功能已关闭，后续的对话将使用文本进行回复"
    await update.message.reply_text(confirmation_text)
    logger.info(f"🎤 [VOICE OFF] Confirmation sent for user_id={user_id}")


def get_voice_handlers():
    """
    获取语音相关的处理器
    """
    return [
        CommandHandler("voice", voice_command),
        CommandHandler("voice_on", voice_on_command),
        CommandHandler("voice_off", voice_off_command),
        CallbackQueryHandler(voice_callback, pattern="^voice_"),
    ]