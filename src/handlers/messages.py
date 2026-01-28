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
from src.utils.voice_helper import send_voice_or_text_reply
from src.models.database import Conversation
from src.ai import conversation_service
from src.conversation.dialogue_strategy import enhance_prompt_with_strategy


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages with multi-bot routing support (Async Version)"""

    logger.info("=" * 50)
    logger.info(f"📥 [STEP 1/9] RECEIVE: Incoming message received, update_id={update.update_id}")

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
    user_id = update.effective_user.id if update.effective_user else None

    logger.info(f"📥 [STEP 1/9] RECEIVE: chat_type={chat_type}, chat_id={chat_id}, user_id={user_id}, text_length={len(message_text)}")
    logger.info(f"📥 [STEP 1/9] RECEIVE: Message preview: {message_text[:50]}{'...' if len(message_text) > 50 else ''}")

    # 使用异步上下文管理器
    logger.info(f"🗄️ [STEP 2/9] DB_CONNECT: Opening async database session")
    async with get_async_db_context() as db:
        try:
            channel_service = AsyncChannelManagerService(db)

            # 异步获取或创建频道记录
            logger.info(f"🗄️ [STEP 3/9] CHANNEL_LOOKUP: Looking up channel for chat_id={chat_id}")
            channel = await channel_service.get_or_create_channel(
                telegram_chat_id=chat_id,
                chat_type=chat_type,
                title=message.chat.title if hasattr(message.chat, 'title') else None,
                username=message.chat.username if hasattr(message.chat, 'username') else None,
                owner_id=update.effective_user.id if update.effective_user else None
            )
            logger.info(f"🗄️ [STEP 3/9] CHANNEL_LOOKUP: Found channel_id={channel.id}, type={channel.chat_type}")

            # 异步获取频道中的活跃机器人
            logger.info(f"🤖 [STEP 4/9] BOT_SELECT: Getting active bots for channel_id={channel.id}")
            mappings = await channel_service.get_channel_bots(channel.id, active_only=True)
            logger.info(f"🤖 [STEP 4/9] BOT_SELECT: Found {len(mappings)} active bot(s) in channel")

            # 检查是否应该响应
            if not MessageRouter.should_respond_in_channel(chat_type, mappings):
                logger.info("🤖 [STEP 4/9] BOT_SELECT: No active bots in this channel, skipping")
                return

            # 提取@的机器人（如果有）
            mentioned_username = MessageRouter.extract_mention(message_text)
            if mentioned_username:
                logger.info(f"🤖 [STEP 4/9] BOT_SELECT: Mentioned bot: @{mentioned_username}")

            # 选择响应的机器人
            selected_mapping = MessageRouter.select_bot(
                message_text=message_text,
                channel=channel,
                mappings=mappings,
                mentioned_username=mentioned_username
            )

            if not selected_mapping:
                logger.info("🤖 [STEP 4/9] BOT_SELECT: No bot selected to respond")
                return

            selected_bot = selected_mapping.bot
            logger.info(f"🤖 [STEP 4/9] BOT_SELECT: Selected bot_id={selected_bot.id}, username=@{selected_bot.bot_username}")

            # 处理用户信息
            user = update.effective_user
            if not user:
                if "channel" in str(chat_type).lower():
                    logger.info("📢 [STEP 5/9] USER_PROCESS: Channel message - processing without user")
                    await message.chat.send_action("typing")
                    try:
                        history = []
                        if selected_bot.system_prompt:
                            # Channel messages have no conversation history, so pass empty list
                            enhanced_prompt = enhance_prompt_with_strategy(
                                original_prompt=selected_bot.system_prompt,
                                conversation_history=[],
                                current_message=message_text
                            )
                            history.insert(0, {"role": "system", "content": enhanced_prompt})
                        logger.info(f"🧠 [STEP 6/9] AI_REQUEST: Sending to AI service, history_length={len(history)}")
                        response = await conversation_service.get_response(message_text, history)
                        logger.info(f"🧠 [STEP 6/9] AI_RESPONSE: Received response, length={len(response)}")
                        await message.reply_text(response)
                        logger.info(f"📤 [STEP 9/9] REPLY_SENT: Text reply sent to channel with @{selected_bot.bot_username}")
                    except Exception as e:
                        logger.error(f"❌ Channel error: {e}")
                    return
                else:
                    logger.warning("❌ No effective_user and not a channel message")
                    return

            logger.info(f"👤 [STEP 5/9] USER_PROCESS: Processing message from telegram_user_id={user.id}")

            subscription_service = AsyncSubscriptionService(db)

            # 异步获取或创建用户
            logger.info(f"🗄️ [STEP 5/9] USER_LOOKUP: Looking up user in database for telegram_id={user.id}")
            db_user = await subscription_service. get_user_by_telegram_id(user.id)
            logger.info(f"🗄️ [STEP 5/9] USER_LOOKUP: Found db_user_id={db_user.id}, subscription_tier={db_user.subscription_tier}")

            # 更新用户信息
            await subscription_service.update_user_info(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                language_code=user.language_code
            )
            logger.info(f"👤 [STEP 5/9] USER_UPDATE: Updated user info for db_user_id={db_user.id}")

            # 检查订阅状态
            logger.info(f"📋 [STEP 5/9] SUBSCRIPTION_CHECK: Checking subscription status for db_user_id={db_user.id}")
            if not await subscription_service.check_subscription_status(db_user):
                logger.info(f"📋 [STEP 5/9] SUBSCRIPTION_CHECK: Subscription expired for db_user_id={db_user.id}")
                await message.reply_text(
                    "⚠️ 你的订阅已过期。\n\n"
                    "使用 /subscribe 续订以继续使用高级功能。"
                )
                return
            logger.info(f"📋 [STEP 5/9] SUBSCRIPTION_CHECK: Subscription active for db_user_id={db_user.id}")

            # 检查使用限制
            logger.info(f"📊 [STEP 5/9] USAGE_CHECK: Checking usage limit for db_user_id={db_user.id}")
            if not await subscription_service.check_usage_limit(db_user, action_type="message"):
                logger.info(f"📊 [STEP 5/9] USAGE_CHECK: Usage limit exceeded for db_user_id={db_user.id}")
                await message.reply_text(
                    "⚠️ 你今天的消息额度已用完。\n\n"
                    f"当前计划：{db_user.subscription_tier}\n"
                    "升级订阅以获取更多额度！\n\n"
                    "使用 /subscribe 查看订阅计划。"
                )
                return
            logger.info(f"📊 [STEP 5/9] USAGE_CHECK: Usage within limit for db_user_id={db_user.id}")

            # 发送typing指示
            await message.chat. send_action("typing")

            # 异步获取对话历史
            logger.info(f"🗄️ [STEP 6/9] HISTORY_FETCH: Fetching conversation history for db_user_id={db_user.id}")
            result = await db.execute(
                select(Conversation)
                .where(Conversation. user_id == db_user.id)
                .order_by(Conversation.timestamp.desc())
                .limit(10)
            )
            recent_conversations = result.scalars().all()
            logger.info(f"🗄️ [STEP 6/9] HISTORY_FETCH: Found {len(recent_conversations)} recent conversation(s)")

            # 构建对话历史
            history = []
            for conv in reversed(list(recent_conversations)):
                if conv.is_user_message:
                    history.append({"role": "user", "content": conv.message})
                else:
                    history.append({"role": "assistant", "content": conv.response})

            try:
                # 添加系统提示（使用动态对话策略增强）
                if selected_bot.system_prompt:
                    enhanced_prompt = enhance_prompt_with_strategy(
                        original_prompt=selected_bot.system_prompt,
                        conversation_history=history,
                        current_message=message_text
                    )
                    history.insert(0, {"role": "system", "content": enhanced_prompt})

                # 获取AI响应
                logger.info(f"🧠 [STEP 7/9] AI_REQUEST: Sending request to AI service, history_length={len(history)}, message_length={len(message_text)}")
                response = await conversation_service.get_response(
                    user_message=message_text,
                    conversation_history=history
                )
                logger.info(f"🧠 [STEP 7/9] AI_RESPONSE: Received AI response, response_length={len(response)}")

                # 发送响应（根据用户语音设置决定是语音还是文本）
                logger.info(f"🎤 [STEP 8/9] RESPONSE_DISPATCH: Determining response type (voice/text) for user_id={user.id}")
                message_type = await send_voice_or_text_reply(
                    message=message,
                    response=response,
                    bot=selected_bot,
                    subscription_service=subscription_service,
                    db_user=db_user,
                    user_id=user.id
                )
                logger.info(f"📤 [STEP 8/9] REPLY_SENT: Response sent to user_id={user.id}, bot=@{selected_bot.bot_username}, type={message_type}")

                # 保存用户消息到数据库
                logger.info(f"🗄️ [STEP 9/9] DB_SAVE: Saving conversation to database for db_user_id={db_user.id}")
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
                logger.info(f"🗄️ [STEP 9/9] DB_SAVE: Conversation saved, usage recorded for db_user_id={db_user.id}")

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