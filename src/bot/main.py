"""
主 Telegram Bot 应用程序

本模块是SoulmateBot的核心入口，负责：
1. 初始化Bot应用
2. 注册命令和消息处理器
3. 启动轮询监听用户消息
"""
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    MessageReactionHandler,
    filters
)
from loguru import logger

from config import settings
from src.database import init_db
from src.handlers import (
    start_command,
    help_command,
    status_command,
    subscribe_command,
    image_command,
    pay_basic_command,
    pay_premium_command,
    check_payment_command,
    list_bots_command,
    add_bot_command,
    remove_bot_command,
    my_bots_command,
    config_bot_command,
    handle_message,
    handle_photo,
    handle_sticker,
    error_handler,
    # 反馈处理器
    handle_message_reaction,
    handle_message_reaction_count,
    handle_pinned_message,
    feedback_stats_command,
    my_feedback_command
)


class SoulmateBot:
    """
    主Bot应用类
    
    这是SoulmateBot的核心类，负责整个Bot的生命周期管理：
    - 初始化配置
    - 注册处理器
    - 启动和停止Bot
    """
    
    def __init__(self):
        """初始化Bot实例"""
        self.app = None
        
    def setup_handlers(self):
        """
        配置命令和消息处理器
        
        注册所有的命令处理器和消息处理器，包括：
        - 基础命令（/start, /help等）
        - 订阅和支付命令
        - Bot管理命令
        - 消息、图片、贴纸处理器
        """
        # 基础命令处理器
        self.app.add_handler(CommandHandler("start", start_command))
        self.app.add_handler(CommandHandler("help", help_command))
        self.app.add_handler(CommandHandler("status", status_command))
        self.app.add_handler(CommandHandler("subscribe", subscribe_command))
        self.app.add_handler(CommandHandler("image", image_command))
        
        # 支付相关命令
        self.app.add_handler(CommandHandler("pay_basic", pay_basic_command))
        self.app.add_handler(CommandHandler("pay_premium", pay_premium_command))
        self.app.add_handler(CommandHandler("check_payment", check_payment_command))
        
        # Bot管理命令（多Bot架构）
        self.app.add_handler(CommandHandler("list_bots", list_bots_command))
        self.app.add_handler(CommandHandler("add_bot", add_bot_command))
        self.app.add_handler(CommandHandler("remove_bot", remove_bot_command))
        self.app.add_handler(CommandHandler("my_bots", my_bots_command))
        self.app.add_handler(CommandHandler("config_bot", config_bot_command))
        
        # 消息处理器（处理普通文本消息）
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,  # 非命令的文本消息
            handle_message
        ))
        
        # 图片处理器
        self.app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        
        # 贴纸处理器
        self.app.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
        
        # 反馈相关命令
        self.app.add_handler(CommandHandler("feedback_stats", feedback_stats_command))
        self.app.add_handler(CommandHandler("my_feedback", my_feedback_command))
        
        # 反应处理器（处理用户对消息的表情反应）
        self.app.add_handler(MessageReactionHandler(handle_message_reaction))
        
        # 置顶消息处理器
        self.app.add_handler(MessageHandler(filters.StatusUpdate.PINNED_MESSAGE, handle_pinned_message))
        
        # 错误处理器（捕获并处理所有错误）
        self.app.add_error_handler(error_handler)
        
        logger.info("所有处理器注册成功")
    
    async def post_init(self, application: Application):
        """
        初始化后钩子
        
        在Bot完全初始化后调用，用于执行启动后的任务
        """
        logger.info("Bot初始化成功")
        logger.info(f"Bot用户名: @{application.bot.username}")
    
    async def post_shutdown(self, application: Application):
        """
        关闭后钩子
        
        在Bot关闭后调用，用于清理资源
        """
        logger.info("Bot已关闭")
    
    def run(self):
        """
        运行Bot
        
        执行以下步骤：
        1. 初始化数据库
        2. 创建Application实例
        3. 注册所有处理器
        4. 启动轮询监听
        """
        logger.info("正在启动 SoulmateBot...")
        
        # 初始化数据库（创建表结构）
        logger.info("正在初始化数据库...")
        init_db()
        logger.info("数据库初始化完成")
        
        # 创建Telegram Bot Application
        self.app = Application.builder().token(settings.telegram_bot_token).build()
        
        # 注册所有处理器
        self.setup_handlers()
        
        # 添加生命周期钩子
        self.app.post_init = self.post_init
        self.app.post_shutdown = self.post_shutdown
        
        # 启动轮询（长轮询方式监听消息）
        logger.info("开始轮询监听...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    # 配置日志记录器
    # - 按天轮转日志文件
    # - 保留最近7天的日志
    logger.add(
        "logs/bot_{time}.log",
        rotation="1 day",      # 每天创建新日志文件
        retention="7 days",    # 保留7天历史日志
        level=settings.log_level
    )
    
    # 创建并运行Bot实例
    bot = SoulmateBot()
    bot.run()
