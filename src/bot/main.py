"""
Main Telegram Bot application
"""
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
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
    error_handler
)


class SoulmateBot:
    """Main bot application class"""
    
    def __init__(self):
        self.app = None
        
    def setup_handlers(self):
        """Setup command and message handlers"""
        # Command handlers
        self.app.add_handler(CommandHandler("start", start_command))
        self.app.add_handler(CommandHandler("help", help_command))
        self.app.add_handler(CommandHandler("status", status_command))
        self.app.add_handler(CommandHandler("subscribe", subscribe_command))
        self.app.add_handler(CommandHandler("image", image_command))
        self.app.add_handler(CommandHandler("pay_basic", pay_basic_command))
        self.app.add_handler(CommandHandler("pay_premium", pay_premium_command))
        self.app.add_handler(CommandHandler("check_payment", check_payment_command))
        
        # Bot management handlers
        self.app.add_handler(CommandHandler("list_bots", list_bots_command))
        self.app.add_handler(CommandHandler("add_bot", add_bot_command))
        self.app.add_handler(CommandHandler("remove_bot", remove_bot_command))
        self.app.add_handler(CommandHandler("my_bots", my_bots_command))
        self.app.add_handler(CommandHandler("config_bot", config_bot_command))
        
        # Message handlers
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        ))
        self.app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        self.app.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
        
        # Error handler
        self.app.add_error_handler(error_handler)
        
        logger.info("Handlers registered successfully")
    
    async def post_init(self, application: Application):
        """Post initialization hook"""
        logger.info("Bot initialized successfully")
        logger.info(f"Bot username: @{application.bot.username}")
    
    async def post_shutdown(self, application: Application):
        """Post shutdown hook"""
        logger.info("Bot shutdown complete")
    
    def run(self):
        """Run the bot"""
        logger.info("Starting SoulmateBot...")
        
        # Initialize database
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized")
        
        # Create application
        self.app = Application.builder().token(settings.telegram_bot_token).build()
        
        # Setup handlers
        self.setup_handlers()
        
        # Add initialization hooks
        self.app.post_init = self.post_init
        self.app.post_shutdown = self.post_shutdown
        
        # Run bot
        logger.info("Starting polling...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    # Configure logger
    logger.add(
        "logs/bot_{time}.log",
        rotation="1 day",
        retention="7 days",
        level=settings.log_level
    )
    
    # Create and run bot
    bot = SoulmateBot()
    bot.run()
