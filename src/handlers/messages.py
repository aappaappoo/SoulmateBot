"""
Message handlers for conversations
"""
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy. orm import Session
from loguru import logger

from src.database import get_db_session
from src.subscription. service import SubscriptionService
from src.models.database import Conversation
from src.ai import conversation_service


async def handle_message(update:  Update, context: ContextTypes. DEFAULT_TYPE):
    """Handle incoming text messages"""

    # ===== 🔍 调试信息 =====
    logger.info("=" * 50)
    logger.info(f"Received update ID: {update.update_id}")

    # ✅ 统一处理私聊消息和频道消息
    message = update.message or update.channel_post

    if not message:
        logger.warning("❌ No message or channel_post in update")
        return

    if not message.text:
        logger. warning(f"❌ Message has no text")
        return

    # 检查消息来源
    chat_type = message.chat.type
    logger.info(f"📨 Message from chat type: {chat_type}")
    logger.info(f"📝 Message text: {message.text[: 50]}...")

    # 频道消息特殊处理
    if chat_type == "channel":
        logger.info("📢 This is a channel message")
        # 频道消息没有 from_user，使用 sender_chat
        if not message.sender_chat:
            logger.warning("No sender_chat in channel message")
            return

        # 频道消息通常不需要个人订阅功能
        # 你可以选择：
        # 1. 忽略频道消息
        # 2. 提供简化的回复
        await message.reply_text(
            "👋 你好！我是情感陪伴机器人。\n\n"
            "💡 请在私聊中与我对话，才能使用完整功能！\n"
            "点击这里开始：@你的Bot用户名"
        )
        return

    # 私聊和群组消息处理
    user = update.effective_user
    if not user:
        logger.warning("No effective_user")
        return

    message_text = message.text
    logger.info(f"Processing message from user {user.id}: {message_text[:50]}...")

    db = get_db_session()
    try:
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
                f"当前计划：{db_user.subscription_tier.value}\n"
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
                history. append({"role": "assistant", "content": conv.response})

        try:
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
            logger.info(f"✅ Successfully replied to user {user.id}")

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