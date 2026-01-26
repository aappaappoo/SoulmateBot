"""
语音命令处理器
处理用户开启/关闭语音回复的命令
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from loguru import logger

from src.services.voice_preference_service import voice_preference_service
from src.services.tts_service import tts_service


async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /voice 命令 - 显示语音设置菜单
    """
    user_id = update.effective_user.id
    bot_username = context.bot.username

    # 获取当前状态
    is_enabled = voice_preference_service.is_voice_enabled(user_id, bot_username)
    status = "✅ 已开启" if is_enabled else "❌ 已关闭"

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


async def voice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理语音设置按钮回调
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    bot_username = context.bot.username

    if query.data == "voice_toggle":
        # 切换状态
        new_state = voice_preference_service.toggle_voice(user_id, bot_username)

        if new_state:
            status = "✅ 已开启"
            message = "🎤 语音回复已开启！\n\n我会用声音回复你的消息~"
            button_text = "📝 关闭语音"
        else:
            status = "❌ 已关闭"
            message = "📝 语音回复已关闭\n\n我会用文字回复你的消息"
            button_text = "🎤 开启语音"

        # ���新按钮
        keyboard = [[InlineKeyboardButton(button_text, callback_data="voice_toggle")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🎙️ **语音回复设置**\n\n"
            f"当前状态: {status}\n\n"
            f"{message}",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )


async def voice_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /voice_on 命令 - 快速开启语音
    """
    user_id = update.effective_user.id
    bot_username = context.bot.username

    voice_preference_service.set_voice_enabled(user_id, bot_username, True)
    
    # 用语音回复确认消息
    confirmation_text = "🎤 语音回复已开启！我会用声音回复你~"
    
    try:
        # 生成语音
        audio_data = await tts_service.generate_voice(
            text=confirmation_text,
            voice_id=None,  # 使用默认音色
            user_id=user_id
        )
        
        if audio_data:
            # 将音频数据转换为可发送的缓冲区
            audio_buffer = tts_service.get_voice_as_buffer(audio_data)
            
            # 发送语音消息（同时附带文本作为caption）
            await update.message.reply_voice(
                voice=audio_buffer,
                caption=confirmation_text
            )
            logger.info(f"✅ Voice confirmation sent for /voice_on command, user={user_id}")
        else:
            # 语音生成失败，回退到文本
            logger.warning(f"⚠️ Voice generation failed for /voice_on, falling back to text")
            await update.message.reply_text(confirmation_text)
    except Exception as e:
        # 语音发送失败，回退到文本
        logger.error(f"❌ Voice response failed for /voice_on: {e}, falling back to text")
        await update.message.reply_text(confirmation_text)


async def voice_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /voice_off 命令 - 快速关闭语音
    """
    user_id = update.effective_user.id
    bot_username = context.bot.username
    
    # 用语音回复确认消息（作为最后一条语音消息，之后就关闭了）
    confirmation_text = "📝 语音回复已关闭，我会用文字回复你"
    
    # 先发送语音确认（在关闭之前）
    try:
        # 生成语音
        audio_data = await tts_service.generate_voice(
            text=confirmation_text,
            voice_id=None,  # 使用默认音色
            user_id=user_id
        )
        
        if audio_data:
            # 将音频数据转换为可发送的缓冲区
            audio_buffer = tts_service.get_voice_as_buffer(audio_data)
            
            # 发送语音消息（同时附带文本作为caption）
            await update.message.reply_voice(
                voice=audio_buffer,
                caption=confirmation_text
            )
            logger.info(f"✅ Voice confirmation sent for /voice_off command, user={user_id}")
        else:
            # 语音生成失败，回退到文本
            logger.warning(f"⚠️ Voice generation failed for /voice_off, falling back to text")
            await update.message.reply_text(confirmation_text)
    except Exception as e:
        # 语音发送失败，回退到文本
        logger.error(f"❌ Voice response failed for /voice_off: {e}, falling back to text")
        await update.message.reply_text(confirmation_text)
    
    # 然后关闭语音设置
    voice_preference_service.set_voice_enabled(user_id, bot_username, False)


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