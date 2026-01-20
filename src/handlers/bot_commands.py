"""
Bot Management Command Handlers - 机器人管理命令处理器

处理多机器人管理相关的命令
"""
from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

from src.database import get_db_session
from src.services.bot_manager import BotManagerService
from src.services.channel_manager import ChannelManagerService
from src.subscription.service import SubscriptionService


async def list_bots_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理 /list_bots 命令 - 列出所有可用的机器人
    """
    user = update.effective_user
    message = update.message
    
    if not message:
        return
    
    db = get_db_session()
    try:
        bot_service = BotManagerService(db)
        
        # 获取所有公开的活跃机器人
        public_bots = bot_service.list_public_bots(status="active")
        
        if not public_bots:
            await message.reply_text(
                "❌ 当前没有可用的机器人。"
            )
            return
        
        # 构建机器人列表消息
        response = "🤖 **可用机器人列表**\n\n"
        response += "以下机器人可以添加到您的频道或群组：\n\n"
        
        for bot in public_bots:
            response += f"**@{bot.bot_username}** - {bot.bot_name}\n"
            if bot.description:
                response += f"   📝 {bot.description}\n"
            response += f"   🤖 模型: {bot.ai_model} ({bot.ai_provider})\n"
            response += f"   🆔 Bot ID: {bot.id}\n\n"
        
        response += "\n💡 使用方法：\n"
        response += "• 在私聊中：直接发送消息\n"
        response += "• 在群组中：使用 /add_bot <bot_id> 添加机器人\n"
        response += "• 在频道中：将机器人设为管理员\n"
        
        await message.reply_text(response, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in list_bots_command: {e}", exc_info=True)
        await message.reply_text(f"❌ 获取机器人列表失败：{str(e)}")
    finally:
        db.close()


async def add_bot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理 /add_bot 命令 - 将机器人添加到当前频道/群组
    
    用法: /add_bot <bot_id> [routing_mode]
    """
    user = update.effective_user
    message = update.message
    chat = message.chat
    
    if not message or not user:
        return
    
    # 检查是否在群组或频道中
    if chat.type == "private":
        await message.reply_text(
            "⚠️ 此命令只能在群组或频道中使用。\n\n"
            "在私聊中，您可以直接与机器人对话。"
        )
        return
    
    # 解析参数
    if not context.args or len(context.args) < 1:
        await message.reply_text(
            "⚠️ 用法错误！\n\n"
            "正确用法：/add_bot <bot_id> [routing_mode]\n\n"
            "例如：\n"
            "• /add_bot 1 mention (需要@机器人才回复)\n"
            "• /add_bot 1 auto (自动回复所有消息)\n"
            "• /add_bot 1 keyword (根据关键词触发)\n\n"
            "使用 /list_bots 查看可用的机器人。"
        )
        return
    
    try:
        bot_id = int(context.args[0])
    except ValueError:
        await message.reply_text("❌ Bot ID 必须是数字！")
        return
    
    routing_mode = context.args[1] if len(context.args) > 1 else "mention"
    
    if routing_mode not in ["mention", "auto", "keyword"]:
        await message.reply_text(
            "❌ 路由模式无效！\n\n"
            "可用模式：\n"
            "• mention - 需要@机器人\n"
            "• auto - 自动回复\n"
            "• keyword - 关键词触发"
        )
        return
    
    db = get_db_session()
    try:
        bot_service = BotManagerService(db)
        channel_service = ChannelManagerService(db)
        
        # 检查机器人是否存在
        bot = bot_service.get_bot_by_id(bot_id)
        if not bot:
            await message.reply_text(f"❌ 找不到 ID 为 {bot_id} 的机器人！")
            return
        
        # 检查机器人是否公开
        if not bot.is_public:
            await message.reply_text(
                f"❌ 机器人 @{bot.bot_username} 不是公开的，无法添加。"
            )
            return
        
        # 检查机器人状态
        if bot.status != "active":
            await message.reply_text(
                f"⚠️ 机器人 @{bot.bot_username} 当前不可用（状态：{bot.status}）。"
            )
            return
        
        # 获取或创建频道记录
        channel = channel_service.get_or_create_channel(
            telegram_chat_id=chat.id,
            chat_type=chat.type,
            title=chat.title,
            username=chat.username,
            owner_id=user.id
        )
        
        # 检查是否已经添加
        if channel_service.check_bot_in_channel(channel.id, bot_id):
            await message.reply_text(
                f"ℹ️ 机器人 @{bot.bot_username} 已经在此频道中。\n\n"
                "使用 /config_bot 修改配置。"
            )
            return
        
        # 添加机器人到频道
        mapping = channel_service.add_bot_to_channel(
            channel_id=channel.id,
            bot_id=bot_id,
            is_active=True,
            priority=0,
            routing_mode=routing_mode
        )
        
        await message.reply_text(
            f"✅ 成功添加机器人 @{bot.bot_username}！\n\n"
            f"📝 配置信息：\n"
            f"• 路由模式：{routing_mode}\n"
            f"• 优先级：0\n\n"
            f"💡 提示：\n"
            f"• 使用 /my_bots 查看频道中的所有机器人\n"
            f"• 使用 /config_bot {bot_id} 修改配置\n"
            f"• 使用 /remove_bot {bot_id} 移除机器人"
        )
        
    except Exception as e:
        logger.error(f"Error in add_bot_command: {e}", exc_info=True)
        await message.reply_text(f"❌ 添加机器人失败：{str(e)}")
    finally:
        db.close()


async def remove_bot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理 /remove_bot 命令 - 从当前频道/群组移除机器人
    
    用法: /remove_bot <bot_id>
    """
    user = update.effective_user
    message = update.message
    chat = message.chat
    
    if not message or not user:
        return
    
    # 检查是否在群组或频道中
    if chat.type == "private":
        await message.reply_text(
            "⚠️ 此命令只能在群组或频道中使用。"
        )
        return
    
    # 解析参数
    if not context.args or len(context.args) < 1:
        await message.reply_text(
            "⚠️ 用法错误！\n\n"
            "正确用法：/remove_bot <bot_id>\n\n"
            "使用 /my_bots 查看当前频道的机器人。"
        )
        return
    
    try:
        bot_id = int(context.args[0])
    except ValueError:
        await message.reply_text("❌ Bot ID 必须是数字！")
        return
    
    db = get_db_session()
    try:
        channel_service = ChannelManagerService(db)
        bot_service = BotManagerService(db)
        
        # 获取频道
        channel = channel_service.get_channel_by_chat_id(chat.id)
        if not channel:
            await message.reply_text("❌ 频道信息未找到！")
            return
        
        # 获取机器人
        bot = bot_service.get_bot_by_id(bot_id)
        if not bot:
            await message.reply_text(f"❌ 找不到 ID 为 {bot_id} 的机器人！")
            return
        
        # 移除机器人
        success = channel_service.remove_bot_from_channel(channel.id, bot_id)
        
        if success:
            await message.reply_text(
                f"✅ 已从此频道移除机器人 @{bot.bot_username}。"
            )
        else:
            await message.reply_text(
                f"ℹ️ 机器人 @{bot.bot_username} 不在此频道中。"
            )
        
    except Exception as e:
        logger.error(f"Error in remove_bot_command: {e}", exc_info=True)
        await message.reply_text(f"❌ 移除机器人失败：{str(e)}")
    finally:
        db.close()


async def my_bots_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理 /my_bots 命令 - 查看当前频道/群组中的机器人
    """
    user = update.effective_user
    message = update.message
    chat = message.chat
    
    if not message or not user:
        return
    
    # 检查是否在群组或频道中
    if chat.type == "private":
        await message.reply_text(
            "ℹ️ 在私聊中，您可以直接与机器人对话。\n\n"
            "此命令用于查看群组或频道中的机器人。"
        )
        return
    
    db = get_db_session()
    try:
        channel_service = ChannelManagerService(db)
        
        # 获取频道
        channel = channel_service.get_channel_by_chat_id(chat.id)
        if not channel:
            await message.reply_text(
                "ℹ️ 此频道还没有添加任何机器人。\n\n"
                "使用 /list_bots 查看可用机器人，\n"
                "使用 /add_bot <bot_id> 添加机器人。"
            )
            return
        
        # 获取频道中的机器人
        mappings = channel_service.get_channel_bots(channel.id, active_only=True)
        
        if not mappings:
            await message.reply_text(
                "ℹ️ 此频道还没有添加任何机器人。\n\n"
                "使用 /list_bots 查看可用机器人，\n"
                "使用 /add_bot <bot_id> 添加机器人。"
            )
            return
        
        # 构建机器人列表消息
        response = f"🤖 **当前频道的机器人** ({len(mappings)}个)\n\n"
        
        for mapping in mappings:
            bot = mapping.bot
            response += f"**@{bot.bot_username}** - {bot.bot_name}\n"
            response += f"   🆔 ID: {bot.id}\n"
            response += f"   📡 路由模式: {mapping.routing_mode}\n"
            response += f"   ⭐ 优先级: {mapping.priority}\n"
            response += f"   ✅ 状态: {'激活' if mapping.is_active else '停用'}\n\n"
        
        response += "\n💡 管理命令：\n"
        response += "• /config_bot <bot_id> - 配置机器人\n"
        response += "• /remove_bot <bot_id> - 移除机器人\n"
        
        await message.reply_text(response, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in my_bots_command: {e}", exc_info=True)
        await message.reply_text(f"❌ 获取机器人列表失败：{str(e)}")
    finally:
        db.close()


async def config_bot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理 /config_bot 命令 - 配置频道中的机器人
    
    用法: /config_bot <bot_id> <key> <value>
    """
    user = update.effective_user
    message = update.message
    chat = message.chat
    
    if not message or not user:
        return
    
    # 检查是否在群组或频道中
    if chat.type == "private":
        await message.reply_text(
            "⚠️ 此命令只能在群组或频道中使用。"
        )
        return
    
    # 解析参数
    if not context.args or len(context.args) < 1:
        await message.reply_text(
            "⚠️ 用法错误！\n\n"
            "正确用法：\n"
            "• /config_bot <bot_id> - 查看配置\n"
            "• /config_bot <bot_id> routing_mode <mode> - 设置路由模式\n"
            "• /config_bot <bot_id> priority <number> - 设置优先级\n\n"
            "路由模式：mention（需@）, auto（自动）, keyword（关键词）"
        )
        return
    
    try:
        bot_id = int(context.args[0])
    except ValueError:
        await message.reply_text("❌ Bot ID 必须是数字！")
        return
    
    db = get_db_session()
    try:
        channel_service = ChannelManagerService(db)
        bot_service = BotManagerService(db)
        
        # 获取频道
        channel = channel_service.get_channel_by_chat_id(chat.id)
        if not channel:
            await message.reply_text("❌ 频道信息未找到！")
            return
        
        # 获取机器人
        bot = bot_service.get_bot_by_id(bot_id)
        if not bot:
            await message.reply_text(f"❌ 找不到 ID 为 {bot_id} 的机器人！")
            return
        
        # 检查机器人是否在频道中
        if not channel_service.check_bot_in_channel(channel.id, bot_id):
            await message.reply_text(
                f"❌ 机器人 @{bot.bot_username} 不在此频道中。\n\n"
                "使用 /add_bot 先添加机器人。"
            )
            return
        
        # 如果只有一个参数，显示当前配置
        if len(context.args) == 1:
            mappings = channel_service.get_channel_bots(channel.id, active_only=False)
            mapping = next((m for m in mappings if m.bot_id == bot_id), None)
            
            if mapping:
                response = f"⚙️ **机器人配置** - @{bot.bot_username}\n\n"
                response += f"📡 路由模式: {mapping.routing_mode}\n"
                response += f"⭐ 优先级: {mapping.priority}\n"
                response += f"✅ 状态: {'激活' if mapping.is_active else '停用'}\n"
                
                if mapping.keywords:
                    response += f"🔑 关键词: {', '.join(mapping.keywords)}\n"
                
                await message.reply_text(response, parse_mode="Markdown")
            else:
                await message.reply_text("❌ 找不到配置信息！")
            
            return
        
        # 更新配置
        if len(context.args) < 3:
            await message.reply_text("❌ 参数不足！需要提供配置项和值。")
            return
        
        config_key = context.args[1].lower()
        config_value = context.args[2]
        
        update_data = {}
        
        if config_key == "routing_mode":
            if config_value not in ["mention", "auto", "keyword"]:
                await message.reply_text("❌ 路由模式无效！可用：mention, auto, keyword")
                return
            update_data["routing_mode"] = config_value
            
        elif config_key == "priority":
            try:
                update_data["priority"] = int(config_value)
            except ValueError:
                await message.reply_text("❌ 优先级必须是数字！")
                return
                
        elif config_key == "active":
            update_data["is_active"] = config_value.lower() in ["true", "1", "yes"]
            
        else:
            await message.reply_text(f"❌ 未知的配置项：{config_key}")
            return
        
        # 更新配置
        mapping = channel_service.update_mapping_settings(
            channel_id=channel.id,
            bot_id=bot_id,
            **update_data
        )
        
        if mapping:
            await message.reply_text(
                f"✅ 配置已更新！\n\n"
                f"机器人：@{bot.bot_username}\n"
                f"配置项：{config_key}\n"
                f"新值：{config_value}"
            )
        else:
            await message.reply_text("❌ 更新配置失败！")
        
    except Exception as e:
        logger.error(f"Error in config_bot_command: {e}", exc_info=True)
        await message.reply_text(f"❌ 配置机器人失败：{str(e)}")
    finally:
        db.close()
