"""
Message handlers for conversations
"""
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy.orm import Session
from loguru import logger

from src.database import get_db_session
from src.subscription.service import SubscriptionService
from src.services.channel_manager import ChannelManagerService
from src.services.message_router import MessageRouter
from src.models.database import Conversation
from src.ai import conversation_service


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages with multi-bot routing support"""

    # ===== 🔍 调试信息 =====
    logger.info("=" * 50)
    logger.info(f"Received update ID: {update.update_id}")

    # ✅ 统一处理私聊消息和频道消息
    message = update.message or update.channel_post

    if not message:
        logger.warning("❌ No message or channel_post in update")
        return

    if not message.text:
        logger.warning(f"❌ Message has no text")
        return

    # 检查消息来源
    chat_type = message.chat.type
    chat_id = message.chat.id
    message_text = message.text
    
    logger.info(f"📨 Message from chat type: {chat_type}")
    logger.info(f"📝 Message text: {message_text[:50]}...")

    db = get_db_session()
    try:
        channel_service = ChannelManagerService(db)
        
        # 获取或创建频道记录
        channel = channel_service.get_or_create_channel(
            telegram_chat_id=chat_id,
            chat_type=chat_type,
            title=message.chat.title if hasattr(message.chat, 'title') else None,
            username=message.chat.username if hasattr(message.chat, 'username') else None,
            owner_id=update.effective_user.id if update.effective_user else None
        )
        
        # 获取频道中的活跃机器人
        mappings = channel_service.get_channel_bots(channel.id, active_only=True)
        
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
            # 没有机器人响应（例如：mention模式但没有@，或keyword模式但没有匹配）
            logger.info("No bot selected to respond")
            return
        
        selected_bot = selected_mapping.bot
        logger.info(f"✅ Selected bot: @{selected_bot.bot_username}")
        
        # 处理用户信息（仅私聊或群组有用户）
        user = update.effective_user
        if not user:
            logger.warning("No effective_user")
            return
        
        logger.info(f"Processing message from user {user.id}: {message_text[:50]}...")
        
        subscription_service = SubscriptionService(db)

        # Get or create user
        db_user = subscription_service.get_user_by_telegram_id(user.id)

        # Check if subscription is active
        if not subscription_service.check_subscription_status(db_user):
            await message.reply_text(
                "⚠️ 你的订阅已过期。\n\n"
                "使用 /subscribe 续订以继续使用高级功能。"
            )
            return

        # Check usage limit
        if not subscription_service.check_usage_limit(db_user, action_type="message"):
            await message.reply_text(
                "⚠️ 你今天的消息额度已用完。\n\n"
                f"当前计划：{db_user.subscription_tier}\n"
                "升级订阅以获取更多额度！\n\n"
                "使用 /subscribe 查看订阅计划。"
            )
            return

        # Send typing indicator
        await message.chat.send_action("typing")

        # Get conversation history
        recent_conversations = db.query(Conversation).filter(
            Conversation.user_id == db_user.id
        ).order_by(Conversation.timestamp.desc()).limit(10).all()

        # Build conversation history
        history = []
        for conv in reversed(recent_conversations):
            if conv.is_user_message:
                history.append({"role": "user", "content": conv.message})
            else:
                history.append({"role": "assistant", "content": conv.response})

        try:
            # 使用选定机器人的配置获取AI响应
            # TODO: 这里可以根据 selected_bot 的 ai_provider 和 ai_model 使用不同的AI服务
            # 当前先使用默认的 conversation_service
            
            # 可以将机器人的 system_prompt 添加到对话历史开头
            if selected_bot.system_prompt:
                history.insert(0, {"role": "system", "content": selected_bot.system_prompt})
            
            # Get AI response
            response = await conversation_service.get_response(
                user_message=message_text,
                conversation_history=history
            )

            # Save conversation to database
            user_conv = Conversation(
                user_id=db_user.id,
                message=message_text,
                response=response,
                is_user_message=True,
                message_type="text"
            )
            db.add(user_conv)

            bot_conv = Conversation(
                user_id=db_user.id,
                message=message_text,
                response=response,
                is_user_message=False,
                message_type="text"
            )
            db.add(bot_conv)

            # Record usage
            subscription_service.record_usage(db_user, action_type="message")

            db.commit()

            # Send response
            await message.reply_text(response)
            logger.info(f"✅ Successfully replied to user {user.id} with bot @{selected_bot.bot_username}")

        except Exception as e:
            logger.error(f"❌ Error getting AI response: {str(e)}", exc_info=True)
            db.rollback()
            await message.reply_text(
                f"抱歉，我遇到了一些问题：{str(e)}\n\n"
                "请稍后再试，或联系管理员。"
            )
            
    except Exception as e:
        logger.error(f"❌ Error in handle_message: {e}", exc_info=True)
    finally:
        db.close()


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming photos"""
    message = update.message or update.channel_post

    if not message:
        return

    logger.info(f"Received photo")

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

    logger.info(f"Received sticker")

    await message.reply_text(
        "😊 收到了你的表情包！\n\n"
        "我能感受到你想表达的情绪。继续和我聊天吧！"
    )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    import traceback

    # 打印完整的错误堆栈
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