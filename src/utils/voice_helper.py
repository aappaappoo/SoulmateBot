"""
Voice helper utilities for sending voice or text replies
语音回复辅助工具
"""
from loguru import logger

from src.services.tts_service import tts_service
from src.services.voice_preference_service import voice_preference_service


async def send_voice_or_text_reply(message, response: str, bot, subscription_service=None, db_user=None, user_id=None):
    """
    发送语音或文本回复
    
    根据用户的语音设置决定发送语音还是文本回复：
    - 如果用户通过 /voice_on 命令开启了语音，则将文本转换为语音发送
    - 如果用户通过 /voice_off 命令关闭了语音，则发送文本回复
    - 如果语音生成失败，回退到文本回复
    
    Args:
        message: Telegram 消息对象
        response: AI生成的回复文本
        bot: 当前Bot数据库对象
        subscription_service: 订阅服务（可选，用于记录语音使用量）
        db_user: 数据库用户对象（可选）
        user_id: 用户Telegram ID（可选，用于检查用户语音偏好）
        
    Returns:
        str: 发送的消息类型 ("voice" 或 "text")
    """
    # 检查用户是否通过 /voice_on 命令开启了语音回复
    # 用户的语音偏好设置优先级最高
    # 默认为 False，仅当 user_id 和 bot_username 都有效时才检查
    user_voice_enabled = False
    bot_username = getattr(bot, 'bot_username', None)
    
    logger.info(f"🎤 [VOICE FLOW 1/5] PREFERENCE_CHECK: Checking voice preference for user_id={user_id}, bot=@{bot_username}")
    
    if user_id is not None and bot_username:
        user_voice_enabled = voice_preference_service.is_voice_enabled(user_id, bot_username)

    logger.info(f"🎤 [VOICE FLOW 1/5] PREFERENCE_CHECK: voice_enabled={user_voice_enabled}")
    
    # 如果用户没有开启语音，则发送文本
    # 用户通过 /voice_on 和 /voice_off 命令控制是否使用语音回复
    if not user_voice_enabled:
        logger.info(f"📝 [VOICE FLOW 2/5] TEXT_REPLY: Sending text reply (voice disabled), response_length={len(response)}")
        await message.reply_text(response)
        logger.info(f"📝 [VOICE FLOW 2/5] TEXT_REPLY: Text reply sent successfully")
        return "text"
    
    # 获取Bot的音色ID
    voice_id = bot.voice_id
    logger.info(f"🎤 [VOICE FLOW 2/5] VOICE_CONFIG: Using voice_id={voice_id} for bot @{bot.bot_username}")
    
    try:
        # 生成语音
        logger.info(f"🎤 [VOICE FLOW 3/5] TTS_REQUEST: Requesting TTS service, text_length={len(response)}, voice_id={voice_id}")
        audio_data = await tts_service.generate_voice(
            text=response,
            voice_id=voice_id,
            user_id=db_user.id if db_user else None
        )
        
        if audio_data:
            logger.info(f"🎤 [VOICE FLOW 3/5] TTS_RESPONSE: TTS generated successfully, audio_size={len(audio_data)} bytes")
            
            # 将音频数据转换为可发送的缓冲区
            logger.info(f"🎤 [VOICE FLOW 4/5] BUFFER_CREATE: Creating audio buffer for Telegram")
            audio_buffer = tts_service.get_voice_as_buffer(audio_data)
            
            # 发送语音消息（同时附带文本作为caption）
            # 注意：Telegram语音消息的caption有限制，如果文本太长需要分开发送
            logger.info(f"🎤 [VOICE FLOW 5/5] VOICE_SEND: Sending voice message to Telegram")
            if len(response) <= 1024:
                await message.reply_voice(
                    voice=audio_buffer,
                    caption=response
                )
            else:
                # 文本太长，分开发送
                await message.reply_voice(voice=audio_buffer)
                await message.reply_text(response)
            
            # 记录语音使用量
            if subscription_service and db_user:
                await subscription_service.record_usage(db_user, action_type="voice")
                logger.info(f"🎤 [VOICE FLOW 5/5] USAGE_RECORD: Voice usage recorded for db_user_id={db_user.id}")
            
            logger.info(f"🎤 [VOICE FLOW 5/5] VOICE_SEND: Voice response sent successfully for bot @{bot.bot_username}")
            return "voice"
        else:
            # 语音生成失败，回退到文本
            logger.warning(f"⚠️ [VOICE FLOW 3/5] TTS_FAILED: Voice generation returned None, falling back to text")
            await message.reply_text(response)
            return "text"
            
    except Exception as e:
        # 语音发送失败，回退到文本
        logger.error(f"❌ [VOICE FLOW] ERROR: Voice response failed: {e}, falling back to text")
        await message.reply_text(response)
        return "text"
