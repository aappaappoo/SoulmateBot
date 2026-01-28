"""
Voice helper utilities for sending voice or text replies
语音回复辅助工具
"""
import asyncio
from typing import Tuple
from loguru import logger

from src.services.tts_service import tts_service
from src.services.voice_preference_service import voice_preference_service
from src.utils.emotion_parser import extract_emotion_and_text, parse_multi_message_response


async def send_voice_or_text_reply(message, response: str, bot, subscription_service=None, db_user=None, user_id=None) -> Tuple[str, str]:
    """
    发送语音或文本回复，支持多消息分割发送
    
    根据用户的语音设置决定发送语音还是文本回复：
    - 如果用户通过 /voice_on 命令开启了语音，则将文本转换为语音发送
    - 如果用户通过 /voice_off 命令关闭了语音，则发送文本回复
    - 如果语音生成失败，回退到文本回复
    
    LLM响应可能包含：
    1. 语气前缀（如：（语气：开心、轻快）），用于控制TTS的情感表达
    2. 多消息分隔符 [MSG_SPLIT]，用于将回复分成多条消息发送
    
    Args:
        message: Telegram 消息对象
        response: AI生成的回复文本（可能包含语气前缀和分隔符）
        bot: 当前Bot数据库对象
        subscription_service: 订阅服务（可选，用于记录语音使用量）
        db_user: 数据库用户对象（可选）
        user_id: 用户Telegram ID（可选，用于检查用户语音偏好）
        
    Returns:
        Tuple[str, str]: (消息类型, 完整内容)
        - 消息类型: "voice" 或 "text"
        - 完整内容: 用于存储到数据库的完整回复内容（不含分隔符）
    """
    # 解析多消息响应
    # Parse multi-message response
    messages, full_content = parse_multi_message_response(response)
    
    if len(messages) > 1:
        logger.info(f"📝 [VOICE FLOW 0/5] MULTI_MSG_PARSE: Parsed {len(messages)} messages to send separately")
    
    # 检查用户是否通过 /voice_on 命令开启了语音回复
    # 用户的语音偏好设置优先级最高
    # 默认为 False，仅当 user_id 和 bot_username 都有效时才检查
    user_voice_enabled = False
    bot_username = getattr(bot, 'bot_username', None)
    # 确保 bot_username 格式一致（去掉 @ 前缀）
    if bot_username and bot_username.startswith('@'):
        bot_username = bot_username[1:]
    logger.info(f"🎤 [VOICE FLOW 1/5] PREFERENCE_CHECK: Checking voice preference for user_id={user_id}, bot=@{bot_username}")
    if user_id is not None and bot_username:
        user_voice_enabled = voice_preference_service.is_voice_enabled(user_id, bot_username)

    logger.info(f"🎤 [VOICE FLOW 1/5] PREFERENCE_CHECK: voice_enabled={user_voice_enabled}")
    
    # 如果用户没有开启语音，则发送文本
    # 用户通过 /voice_on 和 /voice_off 命令控制是否使用语音回复
    if not user_voice_enabled:
        logger.info(f"📝 [VOICE FLOW 2/5] TEXT_REPLY: Sending text reply (voice disabled), message_count={len(messages)}")
        # 发送多条消息
        await send_multi_text_messages(message, messages)
        logger.info(f"📝 [VOICE FLOW 2/5] TEXT_REPLY: Text reply sent successfully")
        return "text", full_content
    
    # 获取Bot的音色ID
    voice_id = bot.voice_id
    logger.info(f"🎤 [VOICE FLOW 2/5] VOICE_CONFIG: Using voice_id={voice_id} for bot @{bot.bot_username}")
    
    try:
        # 对于多消息，只对第一条消息生成语音，其余发送文本
        # For multi-message, generate voice only for the first message
        first_msg = messages[0] if messages else response
        remaining_msgs = messages[1:] if len(messages) > 1 else []
        
        # 从第一条消息中提取语气标签和干净文本
        emotion_tag, clean_text = extract_emotion_and_text(first_msg)
        
        if emotion_tag:
            logger.info(f"🎭 [VOICE FLOW 0/5] EMOTION_PARSE: Extracted emotion='{emotion_tag}', clean_text_length={len(clean_text)}")
        
        # 生成语音（使用完整响应，包含语气前缀，让TTS服务解析情感）
        logger.info(f"🎤 [VOICE FLOW 3/5] TTS_REQUEST: Requesting TTS service, text_length={len(first_msg)}, voice_id={voice_id}, emotion={emotion_tag}")
        audio_data = await tts_service.generate_voice(
            text=first_msg,
            voice_id=voice_id,
            user_id=db_user.id if db_user else None,
            emotion=emotion_tag
        )
        
        if audio_data:
            logger.info(f"🎤 [VOICE FLOW 3/5] TTS_RESPONSE: TTS generated successfully, audio_size={len(audio_data)} bytes")
            
            # 将音频数据转换为可发送的缓冲区
            logger.info(f"🎤 [VOICE FLOW 4/5] BUFFER_CREATE: Creating audio buffer for Telegram")
            audio_buffer = tts_service.get_voice_as_buffer(audio_data)
            
            # 发送语音消息（caption使用干净文本，不包含语气前缀）
            # 注意：Telegram语音消息的caption有限制，如果文本太长需要分开发送
            logger.info(f"🎤 [VOICE FLOW 5/5] VOICE_SEND: Sending voice message to Telegram")
            if len(clean_text) <= 1024:
                await message.reply_voice(
                    voice=audio_buffer,
                    caption=clean_text
                )
            else:
                # 文本太长，分开发送
                await message.reply_voice(voice=audio_buffer)
                await message.reply_text(clean_text)
            
            # 发送剩余的文本消息
            if remaining_msgs:
                logger.info(f"📝 [VOICE FLOW 5/5] REMAINING_MSG: Sending {len(remaining_msgs)} remaining text messages")
                await send_multi_text_messages(message, remaining_msgs)
            
            # 记录语音使用量
            if subscription_service and db_user:
                await subscription_service.record_usage(db_user, action_type="voice")
                logger.info(f"🎤 [VOICE FLOW 5/5] USAGE_RECORD: Voice usage recorded for db_user_id={db_user.id}")
            
            logger.info(f"🎤 [VOICE FLOW 5/5] VOICE_SEND: Voice response sent successfully for bot @{bot.bot_username}")
            return "voice", full_content
        else:
            # 语音生成失败，回退到文本（使用干净文本）
            logger.warning(f"⚠️ [VOICE FLOW 3/5] TTS_FAILED: Voice generation returned None, falling back to text")
            await send_multi_text_messages(message, messages)
            return "text", full_content
            
    except Exception as e:
        # 语音发送失败，回退到文本（使用干净文本）
        logger.error(f"❌ [VOICE FLOW] ERROR: Voice response failed: {e}, falling back to text")
        await send_multi_text_messages(message, messages)
        return "text", full_content


async def send_multi_text_messages(message, messages: list, delay_seconds: float = 0.5):
    """
    发送多条文本消息，模拟真人聊天的节奏
    
    Send multiple text messages with a small delay between them to simulate
    human-like typing rhythm.
    
    Args:
        message: Telegram 消息对象
        messages: 要发送的消息列表
        delay_seconds: 每条消息之间的延迟秒数
    """
    for i, msg_text in enumerate(messages):
        # 从每条消息中提取干净文本（去除语气前缀）
        _, clean_text = extract_emotion_and_text(msg_text)
        
        if clean_text:
            await message.reply_text(clean_text)
            
            # 在消息之间添加短暂延迟（模拟打字节奏），最后一条不延迟
            if i < len(messages) - 1:
                await asyncio.sleep(delay_seconds)
