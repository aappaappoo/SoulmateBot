"""
Main bot entry point - Async Version
"""
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from loguru import logger
import sys
from config import settings
from src.database import init_async_db, close_async_db
from src.handlers.commands import (
    start_command,
    help_command,
    status_command,
    subscribe_command,
    image_command,
    pay_basic_command,
    pay_premium_command,
    check_payment_command
)
from src.handlers.messages import (
    handle_photo,
    handle_sticker,
    error_handler
)
from src.handlers.bot_commands import (
    list_bots_command,
    add_bot_command,
    remove_bot_command,
    my_bots_command,
    config_bot_command
)
from src.handlers.feedback import (
    feedback_stats_command,
    my_feedback_command
)
from src.handlers.agent_integration import (
    handle_message_with_agents,
)

logger.remove()

# 控制台
logger.add(
    sys.stdout,
    level=settings.console_log_level,
    colorize=True
)

# 文件
logger.add(
    "logs/{time}.log",
    level=settings.file_log_level,
    rotation="1 day"
)

class SoulmateBot:
    """
    SoulmateBot 主类
    负责初始化和运行Telegram Bot
    """
    def __init__(self):
        """初始化Bot实例"""
        self.app = None

    def setup_handlers(self):
        """配置命令和消息处理器"""
        # 基础命令处理器
        self.app.add_handler(CommandHandler("start", start_command))
        self.app.add_handler(CommandHandler("help", help_command))
        self.app.add_handler(CommandHandler("status", status_command))
        self.app.add_handler(CommandHandler("subscribe", subscribe_command))
        self.app.add_handler(CommandHandler("image", image_command))

        # 支付命令
        self.app.add_handler(CommandHandler("pay_basic", pay_basic_command))
        self.app.add_handler(CommandHandler("pay_premium", pay_premium_command))
        self.app.add_handler(CommandHandler("check_payment", check_payment_command))

        # Bot管理命令
        self.app.add_handler(CommandHandler("list_bots", list_bots_command))
        self.app.add_handler(CommandHandler("add_bot", add_bot_command))
        self.app.add_handler(CommandHandler("remove_bot", remove_bot_command))
        self.app.add_handler(CommandHandler("my_bots", my_bots_command))
        self.app.add_handler(CommandHandler("config_bot", config_bot_command))

        # 反馈命令
        self.app.add_handler(CommandHandler("feedback_stats", feedback_stats_command))
        self.app.add_handler(CommandHandler("my_feedback", my_feedback_command))

        # 消息处理器 - 使用Agent集成版本
        # 注意：这是对原有handle_message的替代，会自动分析用户消息并选择合适的Agent处理
        # 如果需要恢复原有行为，可以将handle_message_with_agents替换为handle_message
        # 主要变化：
        # 1. 自动判断是否需要调用Agent能力
        # 2. 支持多Agent协作响应
        # 3. 可选的技能选择按钮（减少token消耗）
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message_with_agents
        ))
        self.app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        self.app.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))

        # 错误处理器
        self.app.add_error_handler(error_handler)

        logger.info("所有处理器注册成功")

    async def post_init(self, application: Application):
        """Bot初始化后的回调"""
        bot_info = await application.bot. get_me()
        logger.info("Bot初始化成功")
        logger.info(f"Bot用户名: @{bot_info.username}")

    async def post_shutdown(self, application: Application):
        """Bot关闭后的回调 - 清理异步资源"""
        logger. info("正在关闭数据库连接...")
        await close_async_db()
        logger.info("数据库连接已关闭")

    async def run(self):
        """运行Bot"""
        logger.info("正在启动 SoulmateBot...")

        # 创建Application
        self.app = (
            Application.builder()
            .token(settings.telegram_bot_token)
            .post_init(self.post_init)
            .post_shutdown(self.post_shutdown)
            .build()
        )

        # 异步初始化数据库
        logger.info("正在初始化数据库...")
        await init_async_db()
        logger.info("数据库初始化完成")

        # 设置处理器
        self.setup_handlers()

        # 启动轮询
        logger.info("开始轮询监听...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)

        # 保持运行
        import asyncio
        try:
            while True:
                await asyncio. sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()


def main():
    """程序入口"""
    import asyncio

    bot = SoulmateBot()

    try:
        asyncio. run(bot.run())
    except KeyboardInterrupt:
        logger.info("收到退出信号，正在关闭...")


if __name__ == "__main__":
    main()