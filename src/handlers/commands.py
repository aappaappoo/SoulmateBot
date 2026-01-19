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
/pay_basic - 订阅基础版（¥9.99/月）
/pay_premium - 订阅高级版（¥19.99/月）
/check_payment - 查询支付状态
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

📝 可用命令：
/start - 开始使用机器人
/help - 查看帮助信息
/status - 查看订阅状态和使用情况
/subscribe - 查看订阅计划
/pay_basic - 订阅基础版（¥9.99/月）
/pay_premium - 订阅高级版（¥19.99/月）
/check_payment - 查询支付状态
/image - 获取温馨图片

📊 订阅计划：

🆓 免费版
• 每天 10 条消息
• 基础对话功能

💎 基础版 - ¥9.99/月
• 每天 100 条消息
• 图片发送功能
• 优先响应

👑 高级版 - ¥19.99/月
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

🆓 免费版 - ¥0/月
• 每天 10 条消息
• 基础对话功能
• 适合偶尔使用

💎 基础版 - ¥9.99/月
• 每天 100 条消息
• 图片发送功能
• 优先响应
• 适合日常使用

👑 高级版 - ¥19.99/月
• 每天 1000 条消息
• 无限图片生成
• 个性化对话体验
• 最快响应速度
• 适合深度用户

📝 如何订阅？
使用以下命令订阅：
• /pay_basic - 订阅基础版
• /pay_premium - 订阅高级版

💳 支付方式：
• 微信支付
• Stripe (信用卡/借记卡)

💡 提示：订阅后立即生效，按月计费。
    """
    
    await update.message.reply_text(subscribe_message)


async def pay_basic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /pay_basic command - initiate basic subscription payment"""
    user = update.effective_user
    
    db = get_db_session()
    try:
        from src.payment import WeChatPayService
        from src.models.database import Payment
        import uuid
        
        subscription_service = SubscriptionService(db)
        db_user = subscription_service.get_user_by_telegram_id(user.id)
        
        # Check if WeChat Pay is configured
        from config import settings
        if not settings.wechat_pay_app_id or not settings.wechat_pay_mch_id:
            await update.message.reply_text(
                "⚠️ 微信支付暂未配置，请联系管理员。\n\n"
                "您也可以使用其他支付方式。"
            )
            return
        
        # Generate order ID
        order_id = f"ORDER_{db_user.id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Create payment record
        payment = Payment(
            user_id=db_user.id,
            amount=999,  # 9.99 CNY in cents
            currency="CNY",
            provider="wechat",
            provider_order_id=order_id,
            subscription_tier="basic",
            subscription_duration_days=30,
            status="pending"
        )
        db.add(payment)
        db.commit()
        
        # Create WeChat Pay order
        wechat_service = WeChatPayService()
        result = wechat_service.create_native_pay_order(
            order_id=order_id,
            amount=999,
            description="SoulmateBot 基础版订阅 - 1个月",
            user_id=db_user.id
        )
        
        if result["success"]:
            payment_message = f"""
✅ 订单已创建

📦 订单信息：
• 订单号：{order_id}
• 套餐：💎 基础版
• 价格：¥9.99
• 时长：30天

💳 支付方式：微信支付

📱 扫描二维码支付：
{result["code_url"]}

⚠️ 请在15分钟内完成支付
使用 /check_payment 查询支付状态
            """
            await update.message.reply_text(payment_message)
        else:
            await update.message.reply_text(
                f"❌ 订单创建失败：{result.get('error', '未知错误')}\n\n"
                "请稍后重试或联系客服。"
            )
    except Exception as e:
        await update.message.reply_text(
            f"❌ 发生错误：{str(e)}\n\n"
            "请稍后重试或联系客服。"
        )
    finally:
        db.close()


async def pay_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /pay_premium command - initiate premium subscription payment"""
    user = update.effective_user
    
    db = get_db_session()
    try:
        from src.payment import WeChatPayService
        from src.models.database import Payment
        import uuid
        import time
        
        subscription_service = SubscriptionService(db)
        db_user = subscription_service.get_user_by_telegram_id(user.id)
        
        # Check if WeChat Pay is configured
        from config import settings
        if not settings.wechat_pay_app_id or not settings.wechat_pay_mch_id:
            await update.message.reply_text(
                "⚠️ 微信支付暂未配置，请联系管理员。\n\n"
                "您也可以使用其他支付方式。"
            )
            return
        
        # Generate order ID
        order_id = f"ORDER_{db_user.id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Create payment record
        payment = Payment(
            user_id=db_user.id,
            amount=1999,  # 19.99 CNY in cents
            currency="CNY",
            provider="wechat",
            provider_order_id=order_id,
            subscription_tier="premium",
            subscription_duration_days=30,
            status="pending"
        )
        db.add(payment)
        db.commit()
        
        # Create WeChat Pay order
        wechat_service = WeChatPayService()
        result = wechat_service.create_native_pay_order(
            order_id=order_id,
            amount=1999,
            description="SoulmateBot 高级版订阅 - 1个月",
            user_id=db_user.id
        )
        
        if result["success"]:
            payment_message = f"""
✅ 订单已创建

📦 订单信息：
• 订单号：{order_id}
• 套餐：👑 高级版
• 价格：¥19.99
• 时长：30天

💳 支付方式：微信支付

📱 扫描二维码支付：
{result["code_url"]}

⚠️ 请在15分钟内完成支付
使用 /check_payment 查询支付状态
            """
            await update.message.reply_text(payment_message)
        else:
            await update.message.reply_text(
                f"❌ 订单创建失败：{result.get('error', '未知错误')}\n\n"
                "请稍后重试或联系客服。"
            )
    except Exception as e:
        await update.message.reply_text(
            f"❌ 发生错误：{str(e)}\n\n"
            "请稍后重试或联系客服。"
        )
    finally:
        db.close()


async def check_payment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /check_payment command - check payment status"""
    user = update.effective_user
    
    db = get_db_session()
    try:
        from src.payment import WeChatPayService
        from src.models.database import Payment
        
        subscription_service = SubscriptionService(db)
        db_user = subscription_service.get_user_by_telegram_id(user.id)
        
        # Get the most recent pending payment
        payment = db.query(Payment).filter(
            Payment.user_id == db_user.id,
            Payment.status == "pending"
        ).order_by(Payment.created_at.desc()).first()
        
        if not payment:
            await update.message.reply_text(
                "ℹ️ 没有待支付的订单。\n\n"
                "使用 /subscribe 查看订阅计划。"
            )
            return
        
        # Query payment status
        wechat_service = WeChatPayService()
        result = wechat_service.query_order(payment.provider_order_id)
        
        if result["success"] and result["paid"]:
            # Update payment status
            payment.status = "completed"
            payment.provider_payment_id = result.get("transaction_id")
            db.commit()
            
            # Upgrade subscription
            tier = SubscriptionTier.BASIC if payment.subscription_tier == "basic" else SubscriptionTier.PREMIUM
            subscription_service.upgrade_subscription(
                db_user,
                tier,
                duration_days=payment.subscription_duration_days
            )
            
            tier_names = {
                "basic": "💎 基础版",
                "premium": "👑 高级版"
            }
            
            await update.message.reply_text(
                f"🎉 支付成功！\n\n"
                f"恭喜你成功订阅 {tier_names.get(payment.subscription_tier)}！\n"
                f"订阅有效期：{payment.subscription_duration_days}天\n\n"
                f"现在就可以享受高级功能了！\n"
                f"使用 /status 查看订阅状态。"
            )
        elif result["success"]:
            await update.message.reply_text(
                f"⏳ 订单状态：{result.get('trade_state', '处理中')}\n\n"
                f"订单号：{payment.provider_order_id}\n"
                f"请完成支付后再次查询。"
            )
        else:
            await update.message.reply_text(
                f"❌ 查询失败：{result.get('error', '未知错误')}\n\n"
                "请稍后重试或联系客服。"
            )
    except Exception as e:
        await update.message.reply_text(
            f"❌ 发生错误：{str(e)}\n\n"
            "请稍后重试或联系客服。"
        )
    finally:
        db.close()


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
