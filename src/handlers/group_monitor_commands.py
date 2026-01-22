"""
Group Monitor Command Handlers

群组监控命令处理器 - 提供监控相关的Telegram命令

命令列表：
- /start_monitor <group_link> - 开始监控群组
- /stop_monitor [config_id] - 停止监控
- /monitor_status - 查看监控状态
- /monitor_report [config_id] - 生成监控报告
- /my_monitors - 查看我的监控列表
"""
from datetime import datetime, timedelta
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger

from src.database import get_async_db_context
from src.subscription.async_service import AsyncSubscriptionService
from src.services.group_monitor import GroupMonitorService
from src.ai import conversation_service


async def start_monitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    开始监控群组
    
    用法: /start_monitor <group_link> [start_time] [end_time] [keywords]
    
    示例:
    - /start_monitor https://t.me/my_group
    - /start_monitor t.me/my_group 2024-01-01 2024-01-31
    - /start_monitor t.me/my_group keywords:比特币,以太坊
    """
    user = update.effective_user
    if not user:
        await update.message.reply_text("❌ 无法识别用户")
        return
    
    # 解析参数
    args = context.args
    if not args:
        await update.message.reply_text(
            "📡 **开始群组监控**\n\n"
            "用法: `/start_monitor <群组链接>`\n\n"
            "示例:\n"
            "• `/start_monitor https://t.me/my_group`\n"
            "• `/start_monitor t.me/my_group`\n\n"
            "可选参数:\n"
            "• 时间范围: `2024-01-01 2024-01-31`\n"
            "• 关键词: `keywords:比特币,以太坊`"
        )
        return
    
    group_link = args[0]
    
    # 确保链接格式正确
    if not group_link.startswith("http"):
        if not group_link.startswith("t.me"):
            group_link = f"https://t.me/{group_link}"
        else:
            group_link = f"https://{group_link}"
    
    # 解析其他参数
    start_time = None
    end_time = None
    keywords = []
    
    for arg in args[1:]:
        if arg.startswith("keywords:"):
            keywords = arg.replace("keywords:", "").split(",")
        else:
            try:
                parsed_date = datetime.strptime(arg, "%Y-%m-%d")
                if start_time is None:
                    start_time = parsed_date
                else:
                    end_time = parsed_date
            except ValueError:
                pass
    
    async with get_async_db_context() as db:
        try:
            # 获取用户
            subscription_service = AsyncSubscriptionService(db)
            db_user = await subscription_service.get_user_by_telegram_id(user.id)
            
            if not db_user:
                await update.message.reply_text("❌ 用户未注册，请先使用 /start 注册")
                return
            
            # 创建监控配置
            monitor_service = GroupMonitorService(db, llm_provider=conversation_service.provider)
            config = await monitor_service.create_monitor_config(
                user_id=db_user.id,
                group_link=group_link,
                start_time=start_time or datetime.utcnow(),
                end_time=end_time,
                keywords=keywords
            )
            
            await update.message.reply_text(
                f"✅ **监控已启动**\n\n"
                f"🔗 群组: {group_link}\n"
                f"🆔 配置ID: {config.uuid[:8]}\n"
                f"📅 开始时间: {config.start_time.strftime('%Y-%m-%d %H:%M')}\n"
                f"📅 结束时间: {config.end_time.strftime('%Y-%m-%d %H:%M') if config.end_time else '持续监控'}\n"
                f"🔑 关键词: {', '.join(keywords) if keywords else '无'}\n\n"
                f"⚠️ **注意**: 请确保Bot已加入目标群组并有读取消息权限。\n\n"
                f"使用 `/stop_monitor {config.uuid[:8]}` 停止监控\n"
                f"使用 `/monitor_report {config.uuid[:8]}` 查看报告"
            )
            
        except Exception as e:
            logger.error(f"❌ Error starting monitor: {e}", exc_info=True)
            await update.message.reply_text(f"❌ 启动监控失败: {str(e)}")


async def stop_monitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    停止监控
    
    用法: /stop_monitor [config_id]
    """
    user = update.effective_user
    if not user:
        await update.message.reply_text("❌ 无法识别用户")
        return
    
    args = context.args
    
    async with get_async_db_context() as db:
        try:
            subscription_service = AsyncSubscriptionService(db)
            db_user = await subscription_service.get_user_by_telegram_id(user.id)
            
            if not db_user:
                await update.message.reply_text("❌ 用户未注册")
                return
            
            monitor_service = GroupMonitorService(db)
            
            if args:
                # 停止指定的监控
                config_uuid = args[0]
                configs = await monitor_service.get_user_configs(db_user.id, active_only=True)
                
                target_config = None
                for config in configs:
                    if config.uuid.startswith(config_uuid):
                        target_config = config
                        break
                
                if not target_config:
                    await update.message.reply_text(f"❌ 未找到ID为 {config_uuid} 的监控配置")
                    return
                
                await monitor_service.stop_monitor(target_config.id)
                await update.message.reply_text(
                    f"✅ **监控已停止**\n\n"
                    f"🔗 群组: {target_config.group_link}\n"
                    f"🆔 配置ID: {target_config.uuid[:8]}"
                )
            else:
                # 显示所有活跃监控供选择
                configs = await monitor_service.get_user_configs(db_user.id, active_only=True)
                
                if not configs:
                    await update.message.reply_text("📭 当前没有活跃的监控任务")
                    return
                
                buttons = []
                for config in configs[:10]:
                    buttons.append([
                        InlineKeyboardButton(
                            f"🔴 {config.group_link[:30]}...",
                            callback_data=f"stop_monitor:{config.uuid[:8]}"
                        )
                    ])
                
                keyboard = InlineKeyboardMarkup(buttons)
                await update.message.reply_text(
                    "⏹️ **选择要停止的监控:**",
                    reply_markup=keyboard
                )
                
        except Exception as e:
            logger.error(f"❌ Error stopping monitor: {e}", exc_info=True)
            await update.message.reply_text(f"❌ 停止监控失败: {str(e)}")


async def monitor_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    查看监控状态
    
    用法: /monitor_status
    """
    user = update.effective_user
    if not user:
        await update.message.reply_text("❌ 无法识别用户")
        return
    
    async with get_async_db_context() as db:
        try:
            subscription_service = AsyncSubscriptionService(db)
            db_user = await subscription_service.get_user_by_telegram_id(user.id)
            
            if not db_user:
                await update.message.reply_text("❌ 用户未注册")
                return
            
            monitor_service = GroupMonitorService(db)
            configs = await monitor_service.get_user_configs(db_user.id, active_only=True)
            
            if not configs:
                await update.message.reply_text(
                    "📭 **监控状态**\n\n"
                    "当前没有活跃的监控任务。\n\n"
                    "使用 `/start_monitor <群组链接>` 开始新的监控"
                )
                return
            
            status_lines = [
                "📈 **监控状态**\n",
                f"🔄 活跃监控: {len(configs)}",
                ""
            ]
            
            for i, config in enumerate(configs[:5], 1):
                stats = await monitor_service.get_message_stats(config.id)
                
                status_lines.append(f"**{i}. {config.group_link}**")
                status_lines.append(f"   🆔 ID: `{config.uuid[:8]}`")
                status_lines.append(f"   📝 消息: {stats['total_messages']}")
                status_lines.append(f"   👥 用户: {stats['unique_users']}")
                status_lines.append("")
            
            await update.message.reply_text("\n".join(status_lines))
            
        except Exception as e:
            logger.error(f"❌ Error getting monitor status: {e}", exc_info=True)
            await update.message.reply_text(f"❌ 获取状态失败: {str(e)}")


async def monitor_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    生成监控报告
    
    用法: /monitor_report [config_id]
    """
    user = update.effective_user
    if not user:
        await update.message.reply_text("❌ 无法识别用户")
        return
    
    args = context.args
    
    async with get_async_db_context() as db:
        try:
            subscription_service = AsyncSubscriptionService(db)
            db_user = await subscription_service.get_user_by_telegram_id(user.id)
            
            if not db_user:
                await update.message.reply_text("❌ 用户未注册")
                return
            
            monitor_service = GroupMonitorService(db, llm_provider=conversation_service.provider)
            
            if args:
                # 指定配置的报告
                config_uuid = args[0]
                configs = await monitor_service.get_user_configs(db_user.id, active_only=False)
                
                target_config = None
                for config in configs:
                    if config.uuid.startswith(config_uuid):
                        target_config = config
                        break
                
                if not target_config:
                    await update.message.reply_text(f"❌ 未找到ID为 {config_uuid} 的监控配置")
                    return
            else:
                # 使用最新的配置
                configs = await monitor_service.get_user_configs(db_user.id, active_only=False)
                if not configs:
                    await update.message.reply_text("📭 没有找到任何监控配置")
                    return
                target_config = configs[0]
            
            # 发送处理提示
            await update.message.reply_text("⏳ 正在生成报告，请稍候...")
            
            # 分析话题
            await monitor_service.analyze_topics(target_config.id)
            
            # 生成报告
            report = await monitor_service.generate_report(target_config.id)
            
            await update.message.reply_text(report)
            
        except Exception as e:
            logger.error(f"❌ Error generating report: {e}", exc_info=True)
            await update.message.reply_text(f"❌ 生成报告失败: {str(e)}")


async def my_monitors_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    查看我的所有监控
    
    用法: /my_monitors
    """
    user = update.effective_user
    if not user:
        await update.message.reply_text("❌ 无法识别用户")
        return
    
    async with get_async_db_context() as db:
        try:
            subscription_service = AsyncSubscriptionService(db)
            db_user = await subscription_service.get_user_by_telegram_id(user.id)
            
            if not db_user:
                await update.message.reply_text("❌ 用户未注册")
                return
            
            monitor_service = GroupMonitorService(db)
            configs = await monitor_service.get_user_configs(db_user.id, active_only=False)
            
            if not configs:
                await update.message.reply_text(
                    "📭 **我的监控**\n\n"
                    "你还没有创建任何监控。\n\n"
                    "使用 `/start_monitor <群组链接>` 开始新的监控"
                )
                return
            
            active_count = sum(1 for c in configs if c.is_active)
            
            lines = [
                "📋 **我的监控列表**\n",
                f"📊 总数: {len(configs)} | 活跃: {active_count}",
                ""
            ]
            
            for i, config in enumerate(configs[:10], 1):
                status_emoji = "🟢" if config.is_active else "🔴"
                lines.append(
                    f"{i}. {status_emoji} `{config.uuid[:8]}` - {config.group_link[:25]}..."
                )
            
            if len(configs) > 10:
                lines.append(f"\n...还有 {len(configs) - 10} 个监控未显示")
            
            lines.append("\n📝 **操作:**")
            lines.append("• `/monitor_report <id>` - 查看报告")
            lines.append("• `/stop_monitor <id>` - 停止监控")
            
            await update.message.reply_text("\n".join(lines))
            
        except Exception as e:
            logger.error(f"❌ Error listing monitors: {e}", exc_info=True)
            await update.message.reply_text(f"❌ 获取列表失败: {str(e)}")


async def handle_monitor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理监控相关的回调"""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    if callback_data.startswith("stop_monitor:"):
        config_uuid = callback_data.split(":", 1)[1]
        
        async with get_async_db_context() as db:
            try:
                user = update.effective_user
                subscription_service = AsyncSubscriptionService(db)
                db_user = await subscription_service.get_user_by_telegram_id(user.id)
                
                monitor_service = GroupMonitorService(db)
                configs = await monitor_service.get_user_configs(db_user.id, active_only=True)
                
                target_config = None
                for config in configs:
                    if config.uuid.startswith(config_uuid):
                        target_config = config
                        break
                
                if target_config:
                    await monitor_service.stop_monitor(target_config.id)
                    await query.edit_message_text(
                        f"✅ 已停止监控: {target_config.group_link}"
                    )
                else:
                    await query.edit_message_text("❌ 未找到该监控配置")
                    
            except Exception as e:
                logger.error(f"❌ Error in monitor callback: {e}")
                await query.edit_message_text(f"❌ 操作失败: {str(e)}")
