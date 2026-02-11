"""
语音命令处理器
处理用户开启/关闭语音回复的命令，以及接收用户语音消息并进行识别
"""
import os
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from loguru import logger

from src.services.voice_preference_service import voice_preference_service
from src.services.voice_recognition_service import voice_recognition_service
from src.utils.voice_helper import build_voice_recognition_prompt


# 用户语音文件存储基础目录
VOICE_STORAGE_BASE_DIR = Path("data/voice")


def get_user_voice_storage_path(user_id: int) -> Path:
    """
    获取用户语音文件存储路径

    路径格式: data/voice/{user_id}/{日期(YYYY-MM-DD)}/

    Args:
        user_id: 用户ID

    Returns:
        用户当天的语音存储目录路径
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    voice_dir = VOICE_STORAGE_BASE_DIR / str(user_id) / current_date
    voice_dir.mkdir(parents=True, exist_ok=True)
    return voice_dir


def generate_voice_filename() -> str:
    """
    生成语音文件名

    文件名格式: {时-分-秒}.mp3

    Returns:
        生成的文件名
    """
    current_time = datetime.now().strftime("%H-%M-%S")
    return f"{current_time}.mp3"


async def convert_ogg_to_mp3(ogg_path: str, mp3_path: str) -> bool:
    """
    将 OGG 格式音频转换为 MP3 格式

    使用 ffmpeg 进行转换

    Args:
        ogg_path: OGG 文件路径
        mp3_path: 目标 MP3 文件路径

    Returns:
        转换是否成功
    """
    try:
        # 使用 ffmpeg 转换，-y 表示覆盖已存在的文件
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", ogg_path, "-acodec", "libmp3lame", "-q:a", "2", mp3_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            logger.info(f"🎙️ [VOICE] Successfully converted {ogg_path} to {mp3_path}")
            return True
        else:
            logger.error(f"🎙️ [VOICE] ffmpeg conversion failed: {result.stderr}")
            return False

    except FileNotFoundError:
        logger.error("🎙️ [VOICE] ffmpeg not found. Please install ffmpeg.")
        return False
    except subprocess.TimeoutExpired:
        logger.error("🎙️ [VOICE] ffmpeg conversion timed out")
        return False
    except Exception as e:
        logger.error(f"🎙️ [VOICE] Error during audio conversion: {e}")
        return False


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
    1. 下载用户发送的语音文件（OGG 格式）
    2. 将语音文件保存到 data/voice/{user_id}/{日期}/{时间}.mp3
    3. 调用 DashScope ASR 服务进行语音识别
    4. 将识别出的文本和情绪构建为 LLM 提示
    5. 调用 agent_integration 的消息处理流程获取 AI 回复
    6. 发送回复给用户
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

    tmp_ogg_path = None
    saved_mp3_path = None

    try:
        # 1. 下载语音文件
        voice_file = await message.voice.get_file()

        # 创建临时文件保存原始 OGG 语音
        with tempfile.NamedTemporaryFile(
            suffix=".ogg", delete=False, dir=tempfile.gettempdir()
        ) as tmp_file:
            tmp_ogg_path = tmp_file.name

        await voice_file.download_to_drive(tmp_ogg_path)
        logger.info(f"🎙️ [VOICE MSG] Voice file downloaded to temp: {tmp_ogg_path}")

        # 2. 保存语音文件到用户目录 (转换为 MP3 格式)
        if user_id:
            user_voice_dir = get_user_voice_storage_path(user_id)
            voice_filename = generate_voice_filename()
            saved_mp3_path = str(user_voice_dir / voice_filename)

            # 转换 OGG 到 MP3
            conversion_success = await convert_ogg_to_mp3(tmp_ogg_path, saved_mp3_path)

            if conversion_success:
                logger.info(f"🎙️ [VOICE MSG] Voice file saved to: {saved_mp3_path}")
            else:
                # 如果转换失败，直接复制 OGG 文件（改名为 .mp3 后缀）
                logger.warning("🎙️ [VOICE MSG] MP3 conversion failed, saving OGG file instead")
                import shutil
                saved_mp3_path = str(user_voice_dir / voice_filename.replace('.mp3', '.ogg'))
                shutil.copy(tmp_ogg_path, saved_mp3_path)
                logger.info(f"🎙️ [VOICE MSG] Voice file saved as OGG: {saved_mp3_path}")

        # 3. 调用语音识别服务（使用保存的 MP3 文件）
        # 注意：DashScope ASR 支持 mp3/ogg/wav 等格式
        asr_file_path = saved_mp3_path if saved_mp3_path and os.path.exists(saved_mp3_path) else tmp_ogg_path
        recognition_result = await voice_recognition_service.recognize_voice(asr_file_path)

        if not recognition_result.text:
            logger.warning("🎙️ [VOICE MSG] Voice recognition returned empty text")
            await message.reply_text("🎙️ 抱歉，我没有听清你说的内容，请再试一次~")
            return

        logger.info(
            f"🎙️ [VOICE MSG] Recognition result: text='{recognition_result.text[:100]}', "
            f"emotion={recognition_result.emotion}"
        )

        # 4. 构建包含语音信息的提示文本
        enhanced_text = build_voice_recognition_prompt(
            recognized_text=recognition_result.text,
            emotion=recognition_result.emotion,
        )

        # 5. 将语音识别结果作为文本消息注入到 agent 处理流程
        # 通过模拟文本消息，复用现有的 handle_message_with_agents 逻辑
        from src.handlers.agent_integration import handle_message_with_agents

        # 保存原始文本，替换为语音识别增强文本
        original_text = message.text
        message.text = enhanced_text

        # 在 context 中标记这是一条语音消息，供后续处理使用
        context.user_data["voice_input"] = True
        context.user_data["voice_recognized_text"] = recognition_result.text
        context.user_data["voice_emotion"] = recognition_result.emotion
        context.user_data["voice_file_path"] = saved_mp3_path  # 保存语音文件路径

        logger.info(f"🎙️ [VOICE MSG] Forwarding to agent handler: '{enhanced_text[:100]}'")

        await handle_message_with_agents(update, context)

        # 清理 context 标记
        context.user_data.pop("voice_input", None)
        context.user_data.pop("voice_recognized_text", None)
        context.user_data.pop("voice_emotion", None)
        context.user_data.pop("voice_file_path", None)

        # 恢复原始文本
        message.text = original_text

    except Exception as e:
        logger.error(f"❌ [VOICE MSG] Error processing voice message: {e}", exc_info=True)
        await message.reply_text(
            "🎙️ 抱歉，处理语音消息时遇到了问题，请稍后再试~"
        )
    finally:
        # 清理临时 OGG 文件
        if tmp_ogg_path and os.path.exists(tmp_ogg_path):
            try:
                os.unlink(tmp_ogg_path)
                logger.debug(f"🎙️ [VOICE MSG] Temp OGG file cleaned: {tmp_ogg_path}")
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