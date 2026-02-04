"""
Integrated Message Handler with Agent Orchestrator

集成Agent编排器的消息处理模块 - 将Agent系统与Bot消息处理完全整合

功能：
1. 使用AgentOrchestrator自动判断是否需要调用Agent
2. 支持技能选择（生成Telegram按钮）
3. 处理技能回调
4. 与现有消息处理流程无缝集成
5. 支持语音回复功能（当Bot启用语音时）
6. 对话记忆功能：保存重要事件，检索历史记忆
7. 提醒功能：支持用户设置定时提醒
"""
from typing import Optional, Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from sqlalchemy import select
from loguru import logger

from src.database import get_async_db_context
from src.subscription.async_service import AsyncSubscriptionService
from src.services.async_channel_manager import AsyncChannelManagerService
from src.services.message_router import MessageRouter
from src.services.conversation_memory_service import get_conversation_memory_service
from src.services.reminder_service import ReminderService, format_reminder_confirmation
from src.utils.voice_helper import send_voice_or_text_reply
from src.utils.config_helper import get_bot_values
from src.models.database import Conversation
from src.ai import conversation_service
from src.agents import (
    AgentOrchestrator, AgentLoader, Message as AgentMessage,
    ChatContext, IntentType, skill_button_generator, skill_registry
)
from datetime import datetime
from src.models.database import UserMemory
from src.services.conversation_memory_service import DateParser
from src.conversation.dialogue_strategy import enhance_prompt_with_strategy
from src.conversation.context_builder import UnifiedContextBuilder, ContextConfig

# 全局编排器实例（懒加载）
_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    """
    获取或创建全局AgentOrchestrator实例
    
    使用懒加载模式，首次调用时初始化
    """
    global _orchestrator

    if _orchestrator is None:
        # 加载所有Agent
        loader = AgentLoader(agents_dir="agents")
        agents = loader.load_agents()

        # 创建编排器
        _orchestrator = AgentOrchestrator(
            agents=agents,
            llm_provider=conversation_service.provider,
            enable_skills=True,
            skill_threshold=3,
            enable_unified_mode=True
        )

        logger.info(f"AgentOrchestrator初始化完成，加载了{len(agents)}个Agent")

    return _orchestrator


def build_skill_keyboard(options: List[Dict[str, str]], columns: int = 2) -> InlineKeyboardMarkup:
    """
    构建技能选择键盘
    
    Args:
        options: 技能选项列表
        columns: 每行按钮数量
        
    Returns:
        InlineKeyboardMarkup: Telegram键盘对象
    """
    buttons = []
    row = []

    for option in options:
        button_text = option.get("button_text") or option.get("text", "Unknown")
        callback_data = option.get("callback_data", "skill:unknown")

        row.append(InlineKeyboardButton(
            text=button_text,
            callback_data=callback_data
        ))

        if len(row) >= columns:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    # 添加取消按钮
    buttons.append([InlineKeyboardButton("❌ 取消", callback_data="skill:cancel")])

    return InlineKeyboardMarkup(buttons)


async def handle_message_with_agents(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    使用Agent编排器处理消息
    
    这个处理器会自动判断是否需要调用Agent能力：
    1. 分析用户消息意图
    2. 如果需要调用Agent，选择合适的Agent(s)
    3. 协调多个Agent的响应
    4. 返回综合后的最终回复
    """
    logger.info("=" * 50)
    logger.info(f"[Agent Mode] Received update ID: {update.update_id}")
    message = update.message or update.channel_post
    if not message:
        logger.warning("❌ No message or channel_post in update")
        return

    if not message.text:
        logger.warning("❌ Message has no text")
        return

    chat_type = message.chat.type
    chat_id = message.chat.id
    user_id = str(update.effective_user.id) if update.effective_user else "anonymous"
    message_text = message.text

    logger.info(f"📨 Message from chat type: {chat_type}")
    logger.info(f"📝 Message text: {message_text[:50]}...")

    async with get_async_db_context() as db:
        channel_service = AsyncChannelManagerService(db)

        # 对于私聊，直接使用当前接收消息的 bot
        if chat_type == "private":
            # 获取当前处理消息的 bot
            current_bot_username = context.bot.username
            # 从数据库获取对应的 Bot 对象
            from src.models.database import Bot
            result = await db.execute(
                select(Bot).where(Bot.bot_username == current_bot_username)
            )
            selected_bot = result.scalar_one_or_none()
            if not selected_bot:
                logger.warning(f"Bot not found in database: {current_bot_username}")
                return
            logger.info(f"✅ Private chat - using current bot: @{selected_bot.bot_username}")
        else:
            # 群聊/频道：使用原有的路由逻辑
            channel = await channel_service.get_or_create_channel(
                telegram_chat_id=chat_id,
                chat_type=chat_type,
                title=message.chat.title if hasattr(message.chat, 'title') else None,
                username=message.chat.username if hasattr(message.chat, 'username') else None,
                owner_id=update.effective_user.id if update.effective_user else None
            )

            mappings = await channel_service.get_channel_bots(channel.id, active_only=True)
            if not MessageRouter.should_respond_in_channel(chat_type, mappings):
                logger.info("No active bots in this channel, skipping")
                return
            mentioned_username = MessageRouter.extract_mention(message_text)
            selected_mapping = MessageRouter.select_bot(
                message_text=message_text,
                channel=channel,
                mappings=mappings,
                mentioned_username=mentioned_username
            )

            if not selected_mapping:
                logger.info("No bot selected to respond")
                return
            selected_bot = selected_mapping.bot
        logger.info(f"✅ Selected bot: @{selected_bot.bot_username}")
        # Store the system prompt for later use
        # Priority: YAML config > database
        bot_config = context.bot_data.get("bot_config")
        if bot_config:
            # Use system prompt from YAML config file
            system_prompt = bot_config.get_system_prompt()
            logger.info(f"📄 Using system prompt from YAML config for @{selected_bot.bot_username}")
        else:
            # Fallback to database
            system_prompt = selected_bot.system_prompt
            logger.info(f"💾 Using system prompt from database for @{selected_bot.bot_username}")
        try:
            # 检查用户和订阅状态
            user = update.effective_user
            db_user = None
            if user:
                subscription_service = AsyncSubscriptionService(db)
                db_user = await subscription_service.get_user_by_telegram_id(user.id)
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

            # 🔔 检查是否是提醒请求（用于定时任务）
            if db_user:
                reminder_service = ReminderService(db)
                reminder = await reminder_service.parse_and_create_reminder(
                    message=message_text,
                    user_id=db_user.id,
                    telegram_user_id=update.effective_user.id,
                    chat_id=chat_id,
                    bot_id=selected_bot.id if selected_bot else None
                )
                if reminder:
                    # 计算提醒时间（分钟）
                    time_diff = reminder.remind_at - datetime.utcnow()
                    minutes = int(time_diff.total_seconds() / 60)
                    confirmation = format_reminder_confirmation(minutes, reminder.reminder_text)
                    await message.reply_text(confirmation)
                    # 记录使用量
                    await subscription_service.record_usage(db_user, action_type="message")
                    logger.info(f"📅 Reminder set for user {db_user.id}: {reminder.reminder_text[:50]}...")
                    return

            # 发送typing指示
            await message.chat.send_action("typing")
            # 获取对话历史
            history_messages = []
            recent_conversations = []
            session_id = f"{db_user.id}_{selected_bot.id}" if db_user and selected_bot else None
            if db_user:
                db_result = await db.execute(
                    select(Conversation)
                    .where(Conversation.user_id == db_user.id)
                    .where(Conversation.session_id == session_id)
                    .order_by(Conversation.timestamp.desc())
                    .limit(50)  # 增加到50条以支持中期摘要
                )
                recent_conversations = list(db_result.scalars().all())
                # 构建 Message 对象列表，使用 user_id 来标识 user 或 assistant
                for conv in reversed(recent_conversations):
                    if conv.is_user_message:
                        history_messages.append(AgentMessage(
                            content=conv.message,
                            user_id="user",  # 标识为用户消息
                            chat_id=str(chat_id)
                        ))
                    else:
                        history_messages.append(AgentMessage(
                            content=conv.response,
                            user_id="assistant",  # 标识为助手消息
                            chat_id=str(chat_id)
                        ))
            # 🧠 创建记忆服务实例（在整个请求中复用）
            memory_service = None
            if db_user:
                memory_service = get_conversation_memory_service(
                    db=db,
                    llm_provider=conversation_service.provider
                )
            # 🧠 检索用户的相关记忆
            user_memories = []
            if db_user and memory_service:
                try:
                    memories = await memory_service.retrieve_memories(
                        user_id=db_user.id,
                        bot_id=selected_bot.id if selected_bot else None,
                        current_message=message_text,
                        skip_llm_analysis=True  # 避免额外 LLM 调用
                    )
                    if memories:
                        # 转换为字典格式供 UnifiedContextBuilder 使用,统一使用 "YYYY-MM-DD" 格式
                        user_memories = [
                            {
                                "event_summary": m.event_summary,
                                "event_date": m.event_date.strftime("%Y-%m-%d") if m.event_date else None,
                                "event_type": m.event_type,
                                "keywords": m.keywords
                            }
                            for m in memories
                        ]
                        logger.info(f"🧠 Retrieved {len(user_memories)} memories for context injection")
                except Exception as e:
                    logger.warning(f"Error retrieving memories: {e}", exc_info=True)

            # 构建对话历史格式（用于 UnifiedContextBuilder）
            conversation_history_for_builder = []
            for conv in reversed(recent_conversations):
                if conv.is_user_message:
                    conversation_history_for_builder.append({"role": "user", "content": conv.message})
                else:
                    conversation_history_for_builder.append({"role": "assistant", "content": conv.response})

            # 应用动态对话策略（生成策略文本）
            dialogue_strategy_text = None
            # 获取 bot_config 中的 values 配置（如果存在）
            bot_values = get_bot_values(context)
            if conversation_history_for_builder:
                try:
                    # 先生成对话策略
                    base_system_prompt = system_prompt or ""
                    enhanced_with_strategy = enhance_prompt_with_strategy(
                        original_prompt=base_system_prompt,
                        conversation_history=conversation_history_for_builder,
                        current_message=message_text,
                        bot_values=bot_values
                    )
                    # 提取策略部分（去掉原始 system_prompt）
                    if base_system_prompt and enhanced_with_strategy.startswith(base_system_prompt):
                        dialogue_strategy_text = enhanced_with_strategy[len(base_system_prompt):].strip()

                except Exception as e:
                    logger.warning(f"Error generating dialogue strategy: {e}", exc_info=True)

            # 🔧 使用 UnifiedContextBuilder 构建上下文
            context_builder = UnifiedContextBuilder(
                config=ContextConfig(
                    short_term_rounds=5,
                    mid_term_start=3,
                    mid_term_end=20,
                    max_memories=8,
                    use_llm_summary=False,  # 使用规则摘要节省 token
                    enable_proactive_strategy=True
                )
            )
            # 获取之前保存的 LLM 摘要
            summary_key = f"llm_summary_{chat_id}_{db_user.id if db_user else 'unknown'}"
            previous_summary = context.bot_data.get(summary_key)
            try:
                builder_result = await context_builder.build_context(
                    bot_system_prompt=system_prompt or "",
                    conversation_history=conversation_history_for_builder,
                    current_message=message_text,
                    user_memories=user_memories,
                    dialogue_strategy=dialogue_strategy_text,
                    llm_generated_summary=previous_summary  # 传递之前的摘要
                )
                # 提取构建好的消息列表
                enhanced_messages = builder_result.messages
                # 提取 system prompt（第一条消息）
                enhanced_system_prompt = enhanced_messages[0]["content"] if enhanced_messages else system_prompt
                # 记录 token 使用情况
                budget_info = context_builder.get_token_budget_info(builder_result)
                logger.info(
                    f"🔧 Context built: {len(enhanced_messages)} messages, "
                    f"~{budget_info['estimated_tokens']} tokens "
                    f"({budget_info['usage_percentage']:.1f}% of budget)"
                )
            except Exception as e:
                logger.error(f"Error building context with UnifiedContextBuilder: {e}", exc_info=True)
                # 回退到简单的 system prompt
                enhanced_system_prompt = system_prompt or ""
                enhanced_messages = [
                    {"role": "system", "content": enhanced_system_prompt},
                    {"role": "user", "content": message_text}
                ]
            # 创建Agent消息和上下文
            agent_message = AgentMessage(
                content=message_text,
                user_id=user_id,
                chat_id=str(chat_id),
                metadata={"telegram_message_id": message.message_id}
            )
            chat_context = ChatContext(
                chat_id=str(chat_id),
                conversation_history=history_messages,
                system_prompt=enhanced_system_prompt
            )
            # 使用编排器处理消息
            orchestrator = get_orchestrator()
            result = await orchestrator.process(agent_message, chat_context)
            # 保存 LLM 生成的摘要供下一轮使用
            if hasattr(result, 'metadata') and result.metadata.get("conversation_summary"):
                llm_summary = result.metadata["conversation_summary"]
                # 存储到 context.bot_data 中，供下一轮对话使用
                summary_key = f"llm_summary_{chat_id}_{db_user.id if db_user else 'unknown'}"
                context.bot_data[summary_key] = llm_summary
                # 定期清理旧的摘要（简单的大小限制）
                # 保留最近100个摘要，防止内存泄漏
                summary_keys = [k for k in context.bot_data.keys() if k.startswith("llm_summary_")]
                if len(summary_keys) > 100:
                    # 删除最旧的摘要（假设键按时间顺序添加）
                    oldest_keys = summary_keys[:len(summary_keys) - 100]
                    for old_key in oldest_keys:
                        context.bot_data.pop(old_key, None)
                    logger.debug(f"🧹 Cleaned up {len(oldest_keys)} old summaries from bot_data")
                logger.info(f"📝 Saved LLM summary: {llm_summary.get('summary_text', '')[:50]}...")
            # 日志记录意图类型和来源
            intent_source = result.metadata.get("intent_source", "unknown")
            logger.info(f"🎯 Intent type: {result.intent_type} | Source: {intent_source}")
            logger.info(f"📋 Selected agents: {result.selected_agents}")
            # 处理不同类型的结果
            if result.intent_type == IntentType.SKILL_SELECTION:
                # 需要用户选择技能，生成按钮
                keyboard = build_skill_keyboard(result.skill_options)
                # 保存原始消息到context，供回调使用
                context.user_data["pending_skill_message"] = message_text
                context.user_data["pending_skill_chat_id"] = chat_id
                await message.reply_text(
                    result.final_response,
                    reply_markup=keyboard
                )
            else:
                # 使用编排器的响应
                response = result.final_response
                if isinstance(response, tuple):
                    response = response[0] if response else ""
                elif response is None:
                    response = ""
                parse_mode = None
                if result.agent_responses:
                    # 获取第一个 agent 的 parse_mode
                    for agent_resp in result.agent_responses:
                        if hasattr(agent_resp, 'metadata') and agent_resp.metadata:
                            parse_mode = agent_resp.metadata.get('parse_mode')
                            if parse_mode:
                                break
                # 发送回复（根据用户语音设置决定是语音还是文本）
                message_type, _ = await send_voice_or_text_reply(
                    message=message,
                    response=response,
                    bot=selected_bot,
                    subscription_service=subscription_service if db_user else None,
                    db_user=db_user,
                    user_id=update.effective_user.id if update.effective_user else None,
                    parse_mode=parse_mode
                )
                # 保存对话到数据库
                if db_user and response:
                    user_conv = Conversation(
                        user_id=db_user.id,
                        session_id=session_id,
                        message=message_text,
                        response=response,
                        is_user_message=True,
                        message_type="text"
                    )
                    db.add(user_conv)
                    # 保存机器人回复（记录消息类型）
                    bot_conv = Conversation(
                        user_id=db_user.id,
                        session_id=session_id,
                        message=message_text,
                        response=response,
                        is_user_message=False,
                        message_type=message_type
                    )
                    db.add(bot_conv)
                    # 记录使用量
                    await subscription_service.record_usage(db_user, action_type="message")
                    await db.commit()
                    # 🧠 保存记忆（优先使用统一分析结果，无需额外 LLM）
                    if result.memory_analysis is not None:
                        # 统一模式已返回记忆分析结果，直接使用（无论是否重要）
                        if result.memory_analysis.is_important:
                            try:
                                # 检查重要性级别
                                importance_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
                                level = result.memory_analysis.importance_level or "low"
                                if importance_order.get(level, 0) >= importance_order.get("medium", 1):
                                    # 解析日期
                                    event_date = None
                                    if result.memory_analysis.event_date:
                                        try:
                                            event_date = datetime.strptime(result.memory_analysis.event_date,"%Y-%m-%d")
                                        except ValueError:
                                            pass
                                    if not event_date and result.memory_analysis.raw_date_expression:
                                        event_date = DateParser().parse(result.memory_analysis.raw_date_expression)
                                    if not event_date:
                                        event_date = DateParser().parse_from_message(message_text)
                                    # 生成 Embedding
                                    embedding, embedding_model = None, None
                                    if memory_service and memory_service.embedding_service:
                                        try:
                                            embed_result = await memory_service.embedding_service.embed_text(
                                                result.memory_analysis.event_summary or message_text[:200]
                                            )
                                            embedding, embedding_model = embed_result.embedding, embed_result.model
                                        except Exception as e:
                                            logger.warning(f"Embedding error: {e}")
                                    # 保存记忆
                                    memory = UserMemory(
                                        user_id=db_user.id,
                                        bot_id=selected_bot.id if selected_bot else None,
                                        event_summary=result.memory_analysis.event_summary or message_text[:200],
                                        user_message=message_text,
                                        bot_response=response,
                                        importance=result.memory_analysis.importance_level or "medium",
                                        event_type=result.memory_analysis.event_type,
                                        keywords=result.memory_analysis.keywords or [],
                                        event_date=event_date,
                                        embedding=embedding,
                                        embedding_model=embedding_model
                                    )
                                    db.add(memory)
                                    logger.info(f"🧠 Saved memory from unified analysis (0 extra LLM calls)")
                            except Exception as e:
                                logger.warning(f"Error saving memory: {e}")
                        else:
                            # 统一模式判断不重要，直接跳过，不再回退调用
                            logger.debug(f"🧠 Skipping memory save - unified analysis determined not important")
                    elif memory_service:
                        # 只有在非统一模式（result.memory_analysis is None）时才回退
                        try:
                            saved_memory = await memory_service.extract_and_save_important_events(
                                user_id=db_user.id,
                                bot_id=selected_bot.id if selected_bot else None,
                                user_message=message_text,
                                bot_response=response
                            )
                            if saved_memory:
                                logger.info(f"🧠 Saved memory (legacy mode): {saved_memory.event_summary[:50]}...")
                        except Exception as e:
                            logger.warning(f"Error saving memory: {e}")
            # 记录处理信息
            if result.agent_responses:
                logger.info(f"✅ Agent responses: {[r.agent_name for r in result.agent_responses]}")
        except Exception as e:
            logger.error(f"❌ Error in handle_message_with_agents: {str(e)}", exc_info=True)
            await message.reply_text(
                f"抱歉，我遇到了一些问题：{str(e)}\n\n"
                "请稍后再试，或联系管理员。"
            )
