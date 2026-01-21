"""
Feedback Handlers - 用户反馈处理器

本模块处理用户的反馈相关事件：
1. Telegram Reactions（表情反应）
2. 消息交互事件（回复、转发、置顶等）
3. 消息编辑和删除事件

设计原则：
- 异步处理：不阻塞主消息处理流程
- 容错设计：反馈记录失败不影响用户体验
- 完整记录：捕获尽可能多的用户交互信息
"""
from telegram import Update, MessageReactionUpdated
from telegram.ext import ContextTypes
from loguru import logger

from src.database import get_db_session
from src.services.feedback_service import FeedbackService
from src.services.channel_manager import ChannelManagerService
from src.subscription.service import SubscriptionService
from src.models.database import InteractionType


async def handle_message_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理Telegram消息反应事件
    
    当用户对消息添加或移除reaction时触发
    
    Args:
        update: Telegram更新对象
        context: 上下文对象
    """
    reaction_update = update.message_reaction
    
    if not reaction_update:
        logger.debug("No message_reaction in update")
        return
    
    # 获取基本信息
    chat_id = reaction_update.chat.id
    message_id = reaction_update.message_id
    user = reaction_update.user
    
    if not user:
        logger.debug("No user info in reaction update")
        return
    
    user_id = user.id
    
    # 获取新旧反应列表
    old_reactions = reaction_update.old_reaction or []
    new_reactions = reaction_update.new_reaction or []
    
    logger.info(f"Reaction update from user {user_id} on message {message_id}")
    logger.info(f"Old reactions: {[r.emoji for r in old_reactions if hasattr(r, 'emoji')]}")
    logger.info(f"New reactions: {[r.emoji for r in new_reactions if hasattr(r, 'emoji')]}")
    
    db = get_db_session()
    try:
        feedback_service = FeedbackService(db)
        subscription_service = SubscriptionService(db)
        channel_service = ChannelManagerService(db)
        
        # 获取或创建用户
        db_user = subscription_service.get_user_by_telegram_id(user_id)
        
        # 获取或创建频道
        channel = channel_service.get_or_create_channel(
            telegram_chat_id=chat_id,
            chat_type=reaction_update.chat.type,
            title=reaction_update.chat.title if hasattr(reaction_update.chat, 'title') else None,
            username=reaction_update.chat.username if hasattr(reaction_update.chat, 'username') else None,
            owner_id=user_id
        )
        
        # 解析被移除的反应
        old_emojis = set()
        for reaction in old_reactions:
            if hasattr(reaction, 'emoji') and reaction.emoji:
                old_emojis.add(reaction.emoji)
        
        # 解析新添加的反应
        new_emojis = set()
        for reaction in new_reactions:
            if hasattr(reaction, 'emoji') and reaction.emoji:
                new_emojis.add(reaction.emoji)
        
        # 计算添加和移除的反应
        added_emojis = new_emojis - old_emojis
        removed_emojis = old_emojis - new_emojis
        
        # 处理移除的反应
        for emoji in removed_emojis:
            try:
                feedback_service.remove_reaction(
                    user_id=db_user.id,
                    message_id=message_id,
                    chat_id=chat_id,
                    reaction_emoji=emoji
                )
                logger.info(f"Removed reaction '{emoji}' by user {user_id}")
            except Exception as e:
                logger.error(f"Error removing reaction: {e}")
        
        # 处理添加的反应
        for emoji in added_emojis:
            try:
                # 检查是否是自定义emoji
                custom_emoji_id = None
                is_big = False
                
                for reaction in new_reactions:
                    if hasattr(reaction, 'emoji') and reaction.emoji == emoji:
                        is_big = getattr(reaction, 'is_big', False)
                    elif hasattr(reaction, 'custom_emoji_id'):
                        custom_emoji_id = reaction.custom_emoji_id
                
                feedback_service.add_reaction(
                    user_id=db_user.id,
                    message_id=message_id,
                    chat_id=chat_id,
                    reaction_emoji=emoji,
                    channel_id=channel.id,
                    custom_emoji_id=custom_emoji_id,
                    is_big=is_big
                )
                logger.info(f"Added reaction '{emoji}' by user {user_id}")
            except Exception as e:
                logger.error(f"Error adding reaction: {e}")
        
    except Exception as e:
        logger.error(f"Error handling message reaction: {e}", exc_info=True)
    finally:
        db.close()


async def handle_message_reaction_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理匿名反应计数更新
    
    在频道中，反应可能是匿名的，只能获取计数更新
    
    Args:
        update: Telegram更新对象
        context: 上下文对象
    """
    reaction_count = update.message_reaction_count
    
    if not reaction_count:
        return
    
    chat_id = reaction_count.chat.id
    message_id = reaction_count.message_id
    reactions = reaction_count.reactions
    
    logger.info(f"Anonymous reaction count update on message {message_id} in chat {chat_id}")
    
    # 记录反应计数（用于分析）
    for reaction in reactions:
        if hasattr(reaction, 'type') and hasattr(reaction.type, 'emoji'):
            emoji = reaction.type.emoji
            count = reaction.total_count
            logger.info(f"  {emoji}: {count}")


async def handle_reply_interaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理回复消息的交互
    
    当用户回复机器人消息时，记录这一交互
    注意：这个函数应该在消息处理器中调用
    
    Args:
        update: Telegram更新对象
        context: 上下文对象
    """
    message = update.message or update.channel_post
    
    if not message:
        return
    
    # 检查是否是回复消息
    reply_to = message.reply_to_message
    if not reply_to:
        return
    
    user = update.effective_user
    if not user:
        return
    
    db = get_db_session()
    try:
        feedback_service = FeedbackService(db)
        subscription_service = SubscriptionService(db)
        channel_service = ChannelManagerService(db)
        
        # 获取或创建用户
        db_user = subscription_service.get_user_by_telegram_id(user.id)
        
        # 获取或创建频道
        channel = channel_service.get_or_create_channel(
            telegram_chat_id=message.chat.id,
            chat_type=message.chat.type,
            title=message.chat.title if hasattr(message.chat, 'title') else None,
            username=message.chat.username if hasattr(message.chat, 'username') else None,
            owner_id=user.id
        )
        
        # 记录回复交互
        feedback_service.record_reply(
            user_id=db_user.id,
            message_id=reply_to.message_id,
            chat_id=message.chat.id,
            reply_message_id=message.message_id,
            channel_id=channel.id
        )
        
        logger.info(f"Recorded reply interaction by user {user.id} to message {reply_to.message_id}")
        
    except Exception as e:
        logger.error(f"Error recording reply interaction: {e}", exc_info=True)
    finally:
        db.close()


async def handle_pinned_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理消息置顶事件
    
    Args:
        update: Telegram更新对象
        context: 上下文对象
    """
    message = update.message or update.channel_post
    
    if not message or not message.pinned_message:
        return
    
    pinned = message.pinned_message
    user = update.effective_user
    
    if not user:
        return
    
    db = get_db_session()
    try:
        feedback_service = FeedbackService(db)
        subscription_service = SubscriptionService(db)
        channel_service = ChannelManagerService(db)
        
        # 获取或创建用户
        db_user = subscription_service.get_user_by_telegram_id(user.id)
        
        # 获取或创建频道
        channel = channel_service.get_or_create_channel(
            telegram_chat_id=message.chat.id,
            chat_type=message.chat.type,
            title=message.chat.title if hasattr(message.chat, 'title') else None,
            username=message.chat.username if hasattr(message.chat, 'username') else None,
            owner_id=user.id
        )
        
        # 记录置顶交互
        feedback_service.record_pin(
            user_id=db_user.id,
            message_id=pinned.message_id,
            chat_id=message.chat.id,
            channel_id=channel.id
        )
        
        logger.info(f"Recorded pin interaction by user {user.id} on message {pinned.message_id}")
        
    except Exception as e:
        logger.error(f"Error recording pin interaction: {e}", exc_info=True)
    finally:
        db.close()


async def handle_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理消息转发事件
    
    注意：当消息被转发到其他地方时，我们可能无法直接追踪
    这个处理器主要处理转发到我们的bot的消息
    
    Args:
        update: Telegram更新对象
        context: 上下文对象
    """
    message = update.message
    
    if not message:
        return
    
    # 检查是否是转发的消息
    forward_origin = message.forward_origin
    if not forward_origin:
        return
    
    user = update.effective_user
    if not user:
        return
    
    db = get_db_session()
    try:
        feedback_service = FeedbackService(db)
        subscription_service = SubscriptionService(db)
        
        # 获取或创建用户
        db_user = subscription_service.get_user_by_telegram_id(user.id)
        
        # 记录转发交互
        metadata = {
            'forward_origin_type': str(type(forward_origin).__name__),
            'forward_date': forward_origin.date.isoformat() if hasattr(forward_origin, 'date') else None
        }
        
        feedback_service.record_interaction(
            user_id=db_user.id,
            message_id=message.message_id,
            chat_id=message.chat.id,
            interaction_type=InteractionType.FORWARD.value,
            metadata=metadata
        )
        
        logger.info(f"Recorded forward interaction by user {user.id}")
        
    except Exception as e:
        logger.error(f"Error recording forward interaction: {e}", exc_info=True)
    finally:
        db.close()


# 命令处理器：获取反馈统计

async def feedback_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /feedback_stats 命令 - 查看反馈统计
    
    显示当前频道/聊天的反馈统计信息
    """
    message = update.message
    user = update.effective_user
    
    if not message or not user:
        return
    
    db = get_db_session()
    try:
        feedback_service = FeedbackService(db)
        subscription_service = SubscriptionService(db)
        channel_service = ChannelManagerService(db)
        
        # 获取或创建用户
        db_user = subscription_service.get_user_by_telegram_id(user.id)
        
        # 获取频道
        channel = channel_service.get_or_create_channel(
            telegram_chat_id=message.chat.id,
            chat_type=message.chat.type,
            title=message.chat.title if hasattr(message.chat, 'title') else None,
            username=message.chat.username if hasattr(message.chat, 'username') else None,
            owner_id=user.id
        )
        
        # 获取热门反应
        trending = feedback_service.get_trending_reactions(hours=24, limit=5)
        
        # 构建统计消息
        stats_message = "📊 **反馈统计**\n\n"
        
        if trending:
            stats_message += "🔥 **24小时热门反应**\n"
            for item in trending:
                stats_message += f"  {item['emoji']}: {item['count']}次\n"
        else:
            stats_message += "暂无反应数据\n"
        
        stats_message += "\n💡 提示：对机器人的回复发送表情反应，帮助我们改进服务！"
        
        await message.reply_text(stats_message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error getting feedback stats: {e}", exc_info=True)
        await message.reply_text("获取统计信息时出错，请稍后重试。")
    finally:
        db.close()


async def my_feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /my_feedback 命令 - 查看我的反馈历史
    
    显示用户自己的反馈记录
    """
    message = update.message
    user = update.effective_user
    
    if not message or not user:
        return
    
    db = get_db_session()
    try:
        feedback_service = FeedbackService(db)
        subscription_service = SubscriptionService(db)
        
        # 获取或创建用户
        db_user = subscription_service.get_user_by_telegram_id(user.id)
        
        # 获取用户反馈历史
        history = feedback_service.get_user_feedback_history(db_user.id, limit=20)
        
        # 构建历史消息
        history_message = "📝 **我的反馈历史**\n\n"
        
        if history['reactions']:
            history_message += "**最近的反应**\n"
            for r in history['reactions'][:5]:
                status = "✅" if r['is_active'] else "❌"
                history_message += f"  {status} {r['emoji']} - 消息#{r['message_id']}\n"
        
        if history['interactions']:
            history_message += "\n**最近的交互**\n"
            for i in history['interactions'][:5]:
                history_message += f"  • {i['type']} - 消息#{i['message_id']}\n"
        
        if not history['reactions'] and not history['interactions']:
            history_message += "暂无反馈记录\n"
        
        history_message += "\n💡 您的反馈帮助我们不断改进！"
        
        await message.reply_text(history_message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error getting user feedback history: {e}", exc_info=True)
        await message.reply_text("获取反馈历史时出错，请稍后重试。")
    finally:
        db.close()
