"""
Chat Member Handler - 处理用户聊天状态变更事件

当用户执行以下操作时触发：
1. 删除与Bot的聊天记录（Clear chat history）
2. 删除并屏蔽Bot（Delete and block）
3. 屏蔽Bot（Block）

这些事件会触发 my_chat_member 更新，我们监听这个事件来清理数据库中的聊天记录。
"""
from telegram import Update, ChatMemberUpdated
from telegram.ext import ContextTypes, ChatMemberHandler
from loguru import logger

from src.database import get_db_session
from src.models.database import Conversation, User, Bot
from src.services.channel_manager import ChannelManagerService


async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理Bot的成员状态变更

    当用户屏蔽Bot或删除与Bot的对话时触发

    Args:
        update: Telegram更新对象
        context: 上下文对象
    """
    my_chat_member = update.my_chat_member

    if not my_chat_member:
        return

    # 获取变更信息
    chat = my_chat_member.chat
    user = my_chat_member.from_user
    old_status = my_chat_member.old_chat_member.status
    new_status = my_chat_member.new_chat_member.status

    logger.info(f"my_chat_member update: user={user.id}, chat={chat.id}, "
                f"old_status={old_status}, new_status={new_status}")

    # 检测用户是否屏蔽了Bot（kicked 状态表示用户屏蔽了Bot）
    # 或者用户离开了聊天（left 状态）
    if new_status in ['kicked', 'left']:
        logger.info(f"User {user.id} blocked/left the bot in chat {chat.id}")

        # 清理该用户的聊天记录
        await clear_user_conversation_async(
            telegram_user_id=user.id,
            chat_id=chat.id,
            bot_username=context.bot.username
        )
async def clear_user_conversation_async(
        telegram_user_id: int,
        chat_id: int,
        bot_username: str = None
) -> int:
    """
    异步清理用户的所有对话记录（包括三层存储）

    Args:
        telegram_user_id: Telegram用户ID
        chat_id: 聊天ID（保留参数，便于将来按聊天清理）
        bot_username: Bot用户名（可选）

    Returns:
        int: 删除的记录总数
    """
    db = get_db_session()
    try:
        # 查找用户
        user = db.query(User).filter(User.telegram_id == telegram_user_id).first()
        if not user:
            logger.debug(f"User with telegram_id {telegram_user_id} not found in database")
            return 0

        # 查找Bot（如果提供了bot_username）
        bot = None
        if bot_username:
            bot = db.query(Bot).filter(Bot.bot_username == bot_username).first()

        total_deleted = 0

        # ========== 1. 清理内存中的上下文缓存（短期记忆）==========
        try:
            from src.conversation import get_context_manager
            context_manager = get_context_manager()
            if bot:
                context_manager.delete_context(str(user.id), str(bot.id))
                logger.info(f"Cleared in-memory context for user {user.id} with bot {bot.id}")
            else:
                # 如果没有指定bot，尝试清理该用户的所有上下文
                logger.debug(f"No bot specified, skipping in-memory context cleanup for user {user.id}")
        except Exception as e:
            logger.warning(f"Failed to clear in-memory context: {e}")

        # ========== 2. 清理数据库对话记录（中期记忆 - Conversation表）==========
        conv_query = db.query(Conversation).filter(Conversation.user_id == user.id)

        # 如果有Bot信息，可以进一步过滤
        # session_id格式: "{user_id}_{bot_id}"
        if bot:
            session_id = f"{user.id}_{bot.id}"
            conv_query = conv_query.filter(Conversation.session_id == session_id)

        conv_count = conv_query.count()
        if conv_count > 0:
            conv_query.delete(synchronize_session=False)
            total_deleted += conv_count
            logger.info(f"Cleared {conv_count} conversation records for user {user.id} "
                        f"(telegram_id: {telegram_user_id})")

        # ========== 3. 清理长期记忆（UserMemory表）==========
        try:
            from src.models.database import UserMemory
            memory_query = db.query(UserMemory).filter(
                UserMemory.user_id == user.id,
                UserMemory.is_active == True
            )

            if bot:
                memory_query = memory_query.filter(UserMemory.bot_id == bot.id)

            memory_count = memory_query.count()
            if memory_count > 0:
                # 软删除：将 is_active 设为 False
                memory_query.update({"is_active": False}, synchronize_session=False)
                total_deleted += memory_count
                logger.info(f"Cleared {memory_count} user memories for user {user.id} "
                            f"(telegram_id: {telegram_user_id})")
        except Exception as e:
            logger.warning(f"Failed to clear user memories: {e}")

        # 提交所有更改
        db.commit()

        logger.info(f"Total cleared for user {user.id} (telegram_id: {telegram_user_id}): "
                    f"{total_deleted} records after block/delete action")

        return total_deleted

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to clear conversation for user {telegram_user_id}: {e}")
        return 0
    finally:
        db.close()


def get_chat_member_handler() -> ChatMemberHandler:
    """
    获取ChatMemberHandler实例

    Returns:
        ChatMemberHandler: 处理my_chat_member更新的handler
    """
    return ChatMemberHandler(
        handle_my_chat_member,
        ChatMemberHandler.MY_CHAT_MEMBER
    )