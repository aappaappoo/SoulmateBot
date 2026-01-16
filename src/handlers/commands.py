"""
Telegram bot command handlers
"""
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy.orm import Session

from src.database import get_db_session
from src.subscription.service import SubscriptionService
from src.models.database import SubscriptionTier


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    
    # Get or create user in database
    db = get_db_session()
    try:
        subscription_service = SubscriptionService(db)
        db_user = subscription_service.update_user_info(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=user.language_code
        )
        
        welcome_message = f"""
👋 你好 {user.first_name}！

欢迎来到情感陪伴机器人 SoulmateBot！

我是你的情感陪伴助手，随时准备倾听你的心声，陪伴你度过每一天。

🌟 我能做什么：
• 💬 和你聊天，提供情感支持
• 🖼️ 发送温馨的图片
• 📊 查看你的使用情况

📝 可用命令：
/start - 开始使用
/help - 查看帮助
/status - 查看订阅状态
/subscribe - 订阅高级功能
/image - 获取温馨图片

💝 现在就开始和我聊天吧！
        """
        
        await update.message.reply_text(welcome_message)
    finally:
        db.close()


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
📖 帮助信息

🎯 功能介绍：

1️⃣ 对话功能
直接发送消息给我，我会用心倾听并回复你。

2️⃣ 图片功能
使用 /image 命令，我会发送温馨的图片给你。

3️⃣ 订阅功能
使用 /subscribe 查看订阅计划。

📊 订阅计划：

🆓 免费版
• 每天 10 条消息
• 基础对话功能

💎 基础版
• 每天 100 条消息
• 图片发送功能
• 优先响应

👑 高级版
• 每天 1000 条消息
• 无限图片
• 个性化对话
• 最快响应速度

❓ 需要帮助？
随时发送消息给我！
    """
    
    await update.message.reply_text(help_text)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - show subscription status"""
    user = update.effective_user
    
    db = get_db_session()
    try:
        subscription_service = SubscriptionService(db)
        db_user = subscription_service.get_user_by_telegram_id(user.id)
        stats = subscription_service.get_usage_stats(db_user)
        
        tier_names = {
            "free": "🆓 免费版",
            "basic": "💎 基础版",
            "premium": "👑 高级版"
        }
        
        status_message = f"""
📊 你的状态

👤 用户：{user.first_name}
🎫 订阅：{tier_names.get(stats['subscription_tier'], '未知')}
✅ 状态：{'激活' if stats['is_active'] else '未激活'}

📈 今日使用情况：
💬 消息：{stats['messages_used']} / {stats['messages_limit']}
🖼️ 图片：{stats['images_used']}

⏳ 剩余额度：{stats['messages_limit'] - stats['messages_used']} 条消息

{'✨ 你还有充足的使用额度！' if stats['messages_used'] < stats['messages_limit'] * 0.8 else '⚠️ 使用额度即将用完，考虑升级订阅？'}
        """
        
        await update.message.reply_text(status_message)
    finally:
        db.close()


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /subscribe command - show subscription plans"""
    subscribe_message = """
💎 订阅计划

选择适合你的订阅计划：

🆓 免费版 - $0/月
• 每天 10 条消息
• 基础对话功能
• 适合偶尔使用

💎 基础版 - $9.99/月
• 每天 100 条消息
• 图片发送功能
• 优先响应
• 适合日常使用

👑 高级版 - $19.99/月
• 每天 1000 条消息
• 无限图片生成
• 个性化对话体验
• 最快响应速度
• 适合深度用户

📝 如何订阅？
1. 选择你想要的计划
2. 点击下方链接完成支付
3. 立即享受高级功能

💳 支付方式：
• 信用卡/借记卡
• PayPal
• 支付宝（即将支持）

🔗 立即订阅：[点击这里]（开发中）

💡 提示：订阅后立即生效，按月计费。
    """
    
    await update.message.reply_text(subscribe_message)


async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /image command - send comforting image"""
    user = update.effective_user
    
    db = get_db_session()
    try:
        subscription_service = SubscriptionService(db)
        db_user = subscription_service.get_user_by_telegram_id(user.id)
        
        # Check usage limit for images
        if not subscription_service.check_usage_limit(db_user, action_type="image"):
            await update.message.reply_text(
                "⚠️ 你今天的图片额度已用完。\n\n"
                "升级到基础版或高级版以获取更多额度！\n"
                "使用 /subscribe 查看订阅计划。"
            )
            return
        
        # Record usage
        subscription_service.record_usage(db_user, action_type="image")
        
        # Send a placeholder message for now
        await update.message.reply_text(
            "🖼️ 正在为你准备一张温馨的图片...\n\n"
            "💝 送给你一份温暖！"
        )
        
        # In production, you would use the image service here:
        # from src.services import image_service
        # image_path = await image_service.send_daily_image()
        # if image_path:
        #     await update.message.reply_photo(photo=open(image_path, 'rb'))
        
    finally:
        db.close()
