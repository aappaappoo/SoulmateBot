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
"""
from src.services.voice_preference_service import voice_preference_service
from src.services.tts_service import tts_service
from typing import Optional, Dict, Any, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from sqlalchemy import select
from loguru import logger

from src.database import get_async_db_context
from src.subscription.async_service import AsyncSubscriptionService
from src.services.async_channel_manager import AsyncChannelManagerService
from src.services.message_router import MessageRouter
from src.services.conversation_memory_service import get_conversation_memory_service
from src.utils.voice_helper import send_voice_or_text_reply
from src.models.database import Conversation
from src.ai import conversation_service
from src.agents import (
    AgentOrchestrator, AgentLoader, Message as AgentMessage,
    ChatContext, IntentType, skill_button_generator, skill_registry
)


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
            skill_threshold=3
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
        system_prompt = selected_bot.system_prompt
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
            
            # 发送typing指示
            await message.chat.send_action("typing")
            
            # 获取对话历史（构建ChatContext）
            history_messages = []
            recent_conversations = []
            if db_user:
                db_result = await db.execute(
                    select(Conversation)
                    .where(Conversation.user_id == db_user.id)
                    .order_by(Conversation.timestamp.desc())
                    .limit(10)
                )
                recent_conversations = list(db_result.scalars().all())
                
                for conv in reversed(recent_conversations):
                    history_messages.append(AgentMessage(
                        content=conv.message if conv.is_user_message else conv.response,
                        user_id=user_id,
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
            memory_context = ""
            if db_user and memory_service:
                try:
                    memories = await memory_service.retrieve_memories(
                        user_id=db_user.id,
                        bot_id=selected_bot.id if selected_bot else None,
                        current_message=message_text
                    )
                    if memories:
                        memory_context = await memory_service.format_memories_for_context(memories)
                        logger.info(f"🧠 Retrieved {len(memories)} memories for context injection")
                except Exception as e:
                    logger.warning(f"Error retrieving memories: {e}")
            
            # 将记忆注入到system prompt中
            enhanced_system_prompt = system_prompt or ""
            if memory_context:
                enhanced_system_prompt = f"{enhanced_system_prompt}\n\n{memory_context}"
            
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
                
                # 发送回复（根据用户语音设置决定是语音还是文本）
                message_type = await send_voice_or_text_reply(
                    message=message,
                    response=response,
                    bot=selected_bot,
                    subscription_service=subscription_service if db_user else None,
                    db_user=db_user,
                    user_id=update.effective_user.id if update.effective_user else None
                )
                
                # 保存对话到数据库
                if db_user and response:
                    # 保存用户消息
                    user_conv = Conversation(
                        user_id=db_user.id,
                        message=message_text,
                        response=response,
                        is_user_message=True,
                        message_type="text"
                    )
                    db.add(user_conv)
                    
                    # 保存机器人回复（记录消息类型）
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
                    await db.commit()
                    
                    # 🧠 提取并保存重要对话事件到长期记忆（复用已创建的memory_service）
                    if memory_service:
                        try:
                            saved_memory = await memory_service.extract_and_save_important_events(
                                user_id=db_user.id,
                                bot_id=selected_bot.id if selected_bot else None,
                                user_message=message_text,
                                bot_response=response
                            )
                            if saved_memory:
                                logger.info(f"🧠 Saved important memory: {saved_memory.event_summary[:50]}...")
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


async def handle_skill_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理技能选择回调
    
    当用户点击技能按钮后，执行相应的Agent。
    """
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    if not callback_data.startswith("skill:"):
        return
    
    skill_id = callback_data.split(":", 1)[1]
    logger.info(f"🔘 Skill callback: {skill_id}")
    
    # 处理取消
    if skill_id == "cancel":
        await query.edit_message_text("已取消操作。")
        return
    
    # 处理返回主菜单
    if skill_id == "back_to_main":
        buttons = skill_button_generator.generate_main_menu()
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(btn["text"], callback_data=btn["callback_data"]) for btn in row]
            for row in buttons
        ])
        await query.edit_message_text("请选择服务：", reply_markup=keyboard)
        return
    
    # 获取原始消息
    original_message = context.user_data.get("pending_skill_message", "")
    chat_id = context.user_data.get("pending_skill_chat_id", 0)
    user_id = str(update.effective_user.id) if update.effective_user else "anonymous"
    
    # 更新消息提示正在处理
    await query.edit_message_text(f"⏳ 正在使用 {skill_id} 处理您的请求...")
    
    try:
        # 查找技能对应的Agent
        skill = skill_registry.get(skill_id)
        agent_name = skill.agent_name if skill else skill_id
        
        # 创建消息和上下文
        agent_message = AgentMessage(
            content=original_message,
            user_id=user_id,
            chat_id=str(chat_id)
        )
        chat_context = ChatContext(chat_id=str(chat_id))
        
        # 执行技能回调
        orchestrator = get_orchestrator()
        result = await orchestrator.process_skill_callback(
            skill_name=agent_name,
            message=agent_message,
            context=chat_context
        )
        
        # 发送结果
        await query.edit_message_text(result.final_response)
        
        # 清理临时数据
        context.user_data.pop("pending_skill_message", None)
        context.user_data.pop("pending_skill_chat_id", None)
        
    except Exception as e:
        logger.error(f"❌ Error in skill callback: {e}", exc_info=True)
        await query.edit_message_text(f"抱歉，处理请求时发生错误：{str(e)}")


async def handle_skills_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理 /skills 命令，显示可用技能菜单
    """
    buttons = skill_button_generator.generate_main_menu()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn["text"], callback_data=btn["callback_data"]) for btn in row]
        for row in buttons
    ])
    
    await update.message.reply_text(
        "🔧 **可用技能**\n\n"
        "请选择您需要的服务：",
        reply_markup=keyboard
    )


def get_skill_callback_handler() -> CallbackQueryHandler:
    """获取技能回调处理器，用于注册到Bot"""
    return CallbackQueryHandler(handle_skill_callback, pattern=r"^skill:")


async def send_response_with_voice(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        response_text: str,
        bot_username: str,
        voice_config: dict
):
    """
    发送回复（根据用户偏好决定是��使用语音）

    Args:
        update: Telegram Update
        context: Bot Context
        response_text: AI 回复文本
        bot_username: Bot 用户名
        voice_config: Bot 的语音配置
    """
    user_id = update.effective_user.id

    # 检查用户是否通过 /voice_on 开启了语音回复
    # 用户的语音偏好设置优先级最高
    user_voice_enabled = voice_preference_service.is_voice_enabled(user_id, bot_username)

    if user_voice_enabled:
        # 用户开启了语音，尝试生成语音回复
        try:
            voice_id = voice_config.get("voice_id", "xiaoyan")

            logger.info(f"Generating voice response for user {user_id}, voice_id={voice_id}")

            # 生成语音
            audio_data = await tts_service.generate_voice(
                text=response_text,
                voice_id=voice_id,
                user_id=user_id
            )

            if audio_data:
                # 发送语音消息
                audio_buffer = tts_service.get_voice_as_buffer(audio_data)
                await update.message.reply_voice(
                    voice=audio_buffer,
                    caption=response_text[:1024] if len(response_text) > 200 else None
                )
                logger.info(f"Voice response sent to user {user_id}")
                return
            else:
                logger.warning(f"Voice generation failed, falling back to text")

        except Exception as e:
            logger.error(f"Voice response error: {e}")

    # 获取语音配置 (需要从某处获取，可以存在 context.bot_data 中)
    voice_config = context.bot_data.get("voice_config", {})
    bot_username = context.bot.username

    await send_response_with_voice(
        update=update,
        context=context,
        response_text=response,
        bot_username=bot_username,
        voice_config=voice_config
    )
