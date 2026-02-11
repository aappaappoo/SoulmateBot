"""
语音命令处理器
处理用户开启/关闭语音回复的命令，以及接收用户语音消息并进行识别
"""
import os
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from loguru import logger

from src.services.voice_preference_service import voice_preference_service
from src.services.voice_recognition_service import voice_recognition_service
from src.utils.voice_helper import build_voice_recognition_prompt


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


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理用户发送的语音消息

    流程：
    1. 下载用户发送的语音文件
    2. 调用 DashScope ASR 服务进行语音识别
    3. 将识别出的文本和情绪构建为 LLM 提示
    4. 调用 agent_integration 的消息处理流程获取 AI 回复
    5. 发送回复给用户
    """
    message = update.message
    if not message or not message.voice:
        logger.warning("❌ [VOICE MSG] No voice message found in update")
        return

    user_id = update.effective_user.id if update.effective_user else None
    chat_id = message.chat.id

    logger.info(
        f"🎙️ [VOICE MSG] Voice message received from user_id={user_id}, "
        f"duration={message.voice.duration}s, file_size={message.voice.file_size}"
    )

    # 发送 typing 指示
    await message.chat.send_action("typing")

    tmp_file_path = None
    try:
        # 1. 下载语音文件
        voice_file = await message.voice.get_file()

        # 创建临时文件保存语音
        with tempfile.NamedTemporaryFile(
            suffix=".ogg", delete=False, dir=tempfile.gettempdir()
        ) as tmp_file:
            tmp_file_path = tmp_file.name

        await voice_file.download_to_drive(tmp_file_path)
        logger.info(f"🎙️ [VOICE MSG] Voice file downloaded to: {tmp_file_path}")

        # 2. 调用语音识别服务
        recognition_result = await voice_recognition_service.recognize_voice(tmp_file_path)

        if not recognition_result.text:
            logger.warning("🎙️ [VOICE MSG] Voice recognition returned empty text")
            await message.reply_text("🎙️ 抱歉，我没有听清你说的内容，请再试一次~")
            return

        logger.info(
            f"🎙️ [VOICE MSG] Recognition result: text='{recognition_result.text[:100]}', "
            f"emotion={recognition_result.emotion}"
        )

        # 3. 构建包含语音信息的提示文本
        enhanced_text = build_voice_recognition_prompt(
            recognized_text=recognition_result.text,
            emotion=recognition_result.emotion,
        )

        # 4. 将语音识别结果作为文本消息注入到 agent 处理流程
        # 通过模拟文本消息，复用现有的 handle_message_with_agents 逻辑
        from src.handlers.agent_integration import handle_message_with_agents

        # 保存原始文本，替换为语音识别增强文本
        original_text = message.text
        message.text = enhanced_text

        # 在 context 中标记这是一条语音消息，供后续处理使用
        context.user_data["voice_input"] = True
        context.user_data["voice_recognized_text"] = recognition_result.text
        context.user_data["voice_emotion"] = recognition_result.emotion

        logger.info(f"🎙️ [VOICE MSG] Forwarding to agent handler: '{enhanced_text[:100]}'")

        await handle_message_with_agents(update, context)

        # 清理 context 标记
        context.user_data.pop("voice_input", None)
        context.user_data.pop("voice_recognized_text", None)
        context.user_data.pop("voice_emotion", None)

        # 恢复原始文本
        message.text = original_text

    except Exception as e:
        logger.error(f"❌ [VOICE MSG] Error processing voice message: {e}", exc_info=True)
        await message.reply_text(
            "🎙️ 抱歉，处理语音消息时遇到了问题，请稍后再试~"
        )
    finally:
        # 清理临时文件
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.unlink(tmp_file_path)
                logger.debug(f"🎙️ [VOICE MSG] Temp file cleaned: {tmp_file_path}")
            except OSError as e:
                logger.warning(f"🎙️ [VOICE MSG] Failed to clean temp file: {e}")


def get_voice_handlers():
    """
    获取语音相关的处理器
    """
    return [
        CommandHandler("voice", voice_command),
        CommandHandler("voice_on", voice_on_command),
        CommandHandler("voice_off", voice_off_command),
        CallbackQueryHandler(voice_callback, pattern="^voice_"),
        MessageHandler(filters.VOICE, handle_voice_message),
    ]