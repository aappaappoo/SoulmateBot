"""
Message handlers for conversations
"""
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy.orm import Session

from src.database import get_db_session
from src.subscription.service import SubscriptionService
from src.models.database import Conversation
from src.ai import conversation_service


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages"""
    user = update.effective_user
    message_text = update.message.text
    
    db = get_db_session()
    try:
        subscription_service = SubscriptionService(db)
        
        # Get or create user
        db_user = subscription_service.get_user_by_telegram_id(user.id)
        
        # Check if subscription is active
        if not subscription_service.check_subscription_status(db_user):
            await update.message.reply_text(
                "⚠️ 你的订阅已过期。\n\n"
                "使用 /subscribe 续订以继续使用高级功能。"
            )
            return
        
        # Check usage limit
        if not subscription_service.check_usage_limit(db_user, action_type="message"):
            await update.message.reply_text(
                "⚠️ 你今天的消息额度已用完。\n\n"
                f"当前计划：{db_user.subscription_tier.value}\n"
                "升级订阅以获取更多额度！\n\n"
                "使用 /subscribe 查看订阅计划。"
            )
            return
        
        # Send typing indicator
        await update.message.chat.send_action("typing")
        
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
            await update.message.reply_text(response)
            
        except Exception as e:
            await update.message.reply_text(
                f"抱歉，我遇到了一些问题：{str(e)}\n\n"
                "请稍后再试，或联系管理员。"
            )
    
    finally:
        db.close()


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming photos"""
    await update.message.reply_text(
        "📷 谢谢你分享的照片！\n\n"
        "我看到了你的照片。虽然我还在学习如何更好地理解图片，"
        "但我能感受到你想要分享的心情。\n\n"
        "如果你想聊聊这张照片，或者告诉我你的感受，我很乐意倾听！"
    )


async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming stickers"""
    await update.message.reply_text(
        "😊 收到了你的表情包！\n\n"
        "我能感受到你想表达的情绪。继续和我聊天吧！"
    )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    print(f"Error: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "抱歉，发生了一个错误。请稍后再试。"
        )
