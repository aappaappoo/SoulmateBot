"""
Message handlers for conversations - Async Version
异步消息处理器
"""
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from loguru import logger

from src.database import get_async_db_context
from src.subscription.async_service import AsyncSubscriptionService
from src.services.async_channel_manager import AsyncChannelManagerService
from src.services.message_router import MessageRouter
from src.services.tts_service import tts_service
from src.models.database import Conversation
from src.ai import conversation_service


async def send_voice_or_text_reply(message, response: str, bot, subscription_service=None, db_user=None):
    """
    发送语音或文本回复
    
    根据Bot的语音设置决定发送语音还是文本回复
    
    Args:
        message: Telegram 消息对象
        response: AI生成的回复文本
        bot: 当前Bot数据库对象
        subscription_service: 订阅服务（可选）
        db_user: 数据库用户对象（可选）
        
    Returns:
        str: 发送的消息类型 ("voice" 或 "text")
    """
    # 检查Bot是否启用语音
    if not bot.voice_enabled:
        await message.reply_text(response)
        return "text"
    
    # 获取Bot的音色ID
    voice_id = bot.voice_id
    
    try:
        # 生成语音
        logger.info(f"🎤 Generating voice response for bot @{bot.bot_username} with voice_id={voice_id}")
        audio_data = await tts_service.generate_voice(
            text=response,
            voice_id=voice_id,
            user_id=db_user.id if db_user else None
        )
        
        if audio_data:
            # 将音频数据转换为可发送的缓冲区
            audio_buffer = tts_service.get_voice_as_buffer(audio_data)
            
            # 发送语音消息
            if len(response) <= 1024:
                await message.reply_voice(voice=audio_buffer, caption=response)
            else:
                await message.reply_voice(voice=audio_buffer)
                await message.reply_text(response)
            
            # 记录语音使用量
            if subscription_service and db_user:
                await subscription_service.record_usage(db_user, action_type="voice")
            
            logger.info(f"✅ Voice response sent successfully for bot @{bot.bot_username}")
            return "voice"
        else:
            logger.warning(f"⚠️ Voice generation returned None, falling back to text")
            await message.reply_text(response)
            return "text"
            
    except Exception as e:
        logger.error(f"❌ Voice response failed: {e}, falling back to text")
        await message.reply_text(response)
        return "text"


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages with multi-bot routing support (Async Version)"""

    logger.info("=" * 50)
    logger.info(f"Received update ID: {update.update_id}")

    message = update.message or update.channel_post

    if not message:
        logger.warning("❌ No message or channel_post in update")
        return

    if not message.text:
        logger. warning("❌ Message has no text")
        return

    chat_type = message.chat.type
    chat_id = message.chat.id
    message_text = message.text

    logger.info(f"📨 Message from chat type: {chat_type}")
    logger.info(f"📝 Message text: {message_text[: 50]}...")

    # 使用异步上下文管理器
    async with get_async_db_context() as db:
        try:
            channel_service = AsyncChannelManagerService(db)

            # 异步获取或创建频道记录
            channel = await channel_service.get_or_create_channel(
                telegram_chat_id=chat_id,
                chat_type=chat_type,
                title=message.chat.title if hasattr(message.chat, 'title') else None,
                username=message.chat.username if hasattr(message.chat, 'username') else None,
                owner_id=update.effective_user.id if update.effective_user else None
            )

            # 异步获取频道中的活跃机器人
            mappings = await channel_service.get_channel_bots(channel.id, active_only=True)

            # 检查是否应该响应
            if not MessageRouter.should_respond_in_channel(chat_type, mappings):
                logger.info("No active bots in this channel, skipping")
                return

            # 提取@的机器人（如果有）
            mentioned_username = MessageRouter.extract_mention(message_text)

            # 选择响应的机器人
            selected_mapping = MessageRouter.select_bot(
                message_text=message_text,
                channel=channel,
                mappings=mappings,
                mentioned_username=mentioned_username
            )

            if not selected_mapping:
                logger. info("No bot selected to respond")
                return

            selected_bot = selected_mapping.bot
            logger.info(f"✅ Selected bot: @{selected_bot.bot_username}")

            # 处理用户信息
            user = update.effective_user
            if not user:
                if "channel" in str(chat_type).lower():
                    logger.info("📢 Channel message - processing without user")
                    await message. chat.send_action("typing")
                    try:
                        history = []
                        if selected_bot.system_prompt:
                            history. insert(0, {"role": "system", "content":  selected_bot.system_prompt})
                        response = await conversation_service.get_response(message_text, history)
                        await message.reply_text(response)
                        logger.info(f"✅ Replied to channel with @{selected_bot.bot_username}")
                    except Exception as e:
                        logger.error(f"❌ Channel error: {e}")
                    return
                else:
                    logger.warning("No effective_user")
                    return

            logger.info(f"Processing message from user {user.id}:  {message_text[: 50]}...")

            subscription_service = AsyncSubscriptionService(db)

            # 异步获取或创建用户
            db_user = await subscription_service. get_user_by_telegram_id(user.id)

            # 更新用户信息
            await subscription_service.update_user_info(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                language_code=user.language_code
            )

            # 检查订阅状态
            if not await subscription_service.check_subscription_status(db_user):
                await message.reply_text(
                    "⚠️ 你的订阅已过期。\n\n"
                    "使用 /subscribe 续订以继续使用高级功能。"
                )
                return

            # 检查使用限制
            if not await subscription_service.check_usage_limit(db_user, action_type="message"):
                await message.reply_text(
                    "⚠️ 你今天的消息额度已用完。\n\n"
                    f"当前计划：{db_user.subscription_tier}\n"
                    "升级订阅以获取更多额度！\n\n"
                    "使用 /subscribe 查看订阅计划。"
                )
                return

            # 发送typing指示
            await message.chat. send_action("typing")

            # 异步获取对话历史
            result = await db.execute(
                select(Conversation)
                .where(Conversation. user_id == db_user.id)
                .order_by(Conversation.timestamp.desc())
                .limit(10)
            )
            recent_conversations = result.scalars().all()

            # 构建对话历史
            history = []
            for conv in reversed(list(recent_conversations)):
                if conv.is_user_message:
                    history.append({"role": "user", "content": conv.message})
                else:
                    history.append({"role": "assistant", "content": conv.response})

            try:
                # 添加系统提示
                if selected_bot.system_prompt:
                    history.insert(0, {"role": "system", "content":  selected_bot.system_prompt})

                # 获取AI响应
                response = await conversation_service.get_response(
                    user_message=message_text,
                    conversation_history=history
                )

                # 发送响应（根据Bot设置决定是语音还是文本）
                message_type = await send_voice_or_text_reply(
                    message=message,
                    response=response,
                    bot=selected_bot,
                    subscription_service=subscription_service,
                    db_user=db_user
                )
                logger.info(f"✅ Successfully replied to user {user.id} with bot @{selected_bot.bot_username} (type: {message_type})")

                # 保存用户消息到数据库
                user_conv = Conversation(
                    user_id=db_user.id,
                    message=message_text,
                    response=response,
                    is_user_message=True,
                    message_type="text"
                )
                db.add(user_conv)

                # 保存机器人回复到数据库（记录消息类型）
                bot_conv = Conversation(
                    user_id=db_user.id,
                    message=message_text,
                    response=response,
                    is_user_message=False,
                    message_type=message_type
                )
                db.add(bot_conv)

                # 记录使用量
                await subscription_service.record_usage(db_user, action_type="message")

                # 提交事务（由上下文管理器自动处理）
                await db.commit()

            except Exception as e:
                logger.error(f"❌ Error getting AI response: {str(e)}", exc_info=True)
                await db.rollback()
                await message.reply_text(
                    f"抱歉，我遇到了一些问题：{str(e)}\n\n"
                    "请稍后再试，或联系管理员。"
                )

        except Exception as e:
            logger.error(f"❌ Error in handle_message: {str(e)}", exc_info=True)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming photos"""
    message = update.message or update.channel_post

    if not message:
        return

    logger.info("Received photo")

    await message.reply_text(
        "📷 谢谢你分享的照片！\n\n"
        "我看到了你的照片。虽然我还在学习如何更好地理解图片，"
        "但我能感受到你想要分享的心情。\n\n"
        "如果你想聊聊这张照片，或者告诉我你的感受，我很乐意倾听！"
    )


async def handle_sticker(update: Update, context:  ContextTypes.DEFAULT_TYPE):
    """Handle incoming stickers"""
    message = update.message or update.channel_post

    if not message:
        return

    logger.info("Received sticker")

    await message.reply_text(
        "😊 收到了你的表情包！\n\n"
        "我能感受到你想表达的情绪。继续和我聊天吧！"
    )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    import traceback

    error_traceback = ''.join(traceback.format_exception(
        type(context.error),
        context.error,
        context.error.__traceback__
    ))

    logger.error(f"❌ Error occurred: {context.error}")
    logger.error(f"Full traceback:\n{error_traceback}")
    logger.error(f"Update that caused error: {update}")

    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "抱歉，发生了一个错误。请稍后再试。"
            )
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")