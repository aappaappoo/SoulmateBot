"""
Multi-Bot Platform Launcher - 多机器人平台启动器

负责：
- 加载多个Bot配置
- 启动和管理多个Bot实例
- 统一的消息分发
- 平台级监控和日志
"""
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from loguru import logger

from src.bot.config_loader import BotConfigLoader, BotConfig
from src.llm_gateway import get_llm_gateway, LLMGateway
from src.conversation import get_session_manager, SessionManager
from src.database import init_db


@dataclass
class BotInstance:
    """
    Bot实例
    
    封装单个Bot的运行时状态
    """
    bot_id: str
    config: BotConfig
    application: Optional[Application] = None
    is_running: bool = False
    started_at: Optional[datetime] = None
    message_count: int = 0
    error_count: int = 0


class MultiBotPlatform:
    """
    多机器人平台
    
    管理多个Bot实例的生命周期，提供统一的平台服务
    """
    
    def __init__(
        self,
        bots_dir: str = "bots",
        enable_database: bool = True
    ):
        """
        初始化平台
        
        Args:
            bots_dir: Bots配置目录
            enable_database: 是否启用数据库
        """
        self.bots_dir = bots_dir
        self.enable_database = enable_database
        
        # 配置加载器
        self.config_loader = BotConfigLoader(bots_dir)
        
        # Bot实例注册表
        self._instances: Dict[str, BotInstance] = {}
        
        # 平台服务
        self._llm_gateway: Optional[LLMGateway] = None
        self._session_manager: Optional[SessionManager] = None
        
        # 平台状态
        self._is_initialized = False
        self._started_at: Optional[datetime] = None
        
        logger.info(f"MultiBotPlatform created with bots_dir: {bots_dir}")
    
    def initialize(self) -> None:
        """
        初始化平台
        
        加载配置，初始化共享服务
        """
        if self._is_initialized:
            logger.warning("Platform already initialized")
            return
        
        logger.info("Initializing MultiBotPlatform...")
        
        # 初始化数据库
        if self.enable_database:
            logger.info("Initializing database...")
            init_db()
        
        # 初始化共享服务
        self._llm_gateway = get_llm_gateway()
        self._session_manager = get_session_manager()
        
        # 加载所有Bot配置
        configs = self.config_loader.load_all_configs()
        
        for bot_id, config in configs.items():
            self._instances[bot_id] = BotInstance(
                bot_id=bot_id,
                config=config
            )
            logger.info(f"Registered bot: {bot_id} ({config.name})")
        
        self._is_initialized = True
        logger.info(f"Platform initialized with {len(self._instances)} bots")
    
    def get_bot_instance(self, bot_id: str) -> Optional[BotInstance]:
        """获取Bot实例"""
        return self._instances.get(bot_id)
    
    def list_bots(self) -> List[Dict[str, Any]]:
        """列出所有Bot"""
        bots = []
        for bot_id, instance in self._instances.items():
            bots.append({
                "bot_id": bot_id,
                "name": instance.config.name,
                "description": instance.config.description,
                "type": instance.config.bot_type,
                "is_running": instance.is_running,
                "message_count": instance.message_count,
                "error_count": instance.error_count
            })
        return bots
    
    async def start_bot(self, bot_id: str, token: str) -> bool:
        """
        启动指定的Bot
        
        Args:
            bot_id: Bot标识
            token: Telegram Bot Token
            
        Returns:
            是否成功启动
        """
        instance = self._instances.get(bot_id)
        if not instance:
            logger.error(f"Bot not found: {bot_id}")
            return False
        
        if instance.is_running:
            logger.warning(f"Bot already running: {bot_id}")
            return True
        
        try:
            # 创建Telegram Application
            app = Application.builder().token(token).build()
            
            # 注册处理器
            self._setup_handlers(app, instance)
            
            # 保存Application实例
            instance.application = app
            instance.is_running = True
            instance.started_at = datetime.now(timezone.utc)
            
            logger.info(f"Bot started: {bot_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start bot {bot_id}: {e}")
            instance.error_count += 1
            return False
    
    def _setup_handlers(self, app: Application, instance: BotInstance) -> None:
        """为Bot设置消息处理器"""
        config = instance.config
        
        # 基础命令处理器
        async def start_command(update: Update, context):
            await update.message.reply_text(config.messages.welcome)
        
        async def help_command(update: Update, context):
            await update.message.reply_text(config.messages.help)
        
        async def handle_message(update: Update, context):
            """处理普通消息"""
            instance.message_count += 1
            
            message = update.message or update.channel_post
            if not message or not message.text:
                return
            
            try:
                # 获取或创建会话
                user_id = str(update.effective_user.id) if update.effective_user else "unknown"
                session = self._session_manager.get_or_create_session(
                    user_id=user_id,
                    bot_id=instance.bot_id,
                    system_prompt=config.get_system_prompt()
                )
                
                # 添加用户消息
                session.add_user_message(message.text)
                
                # 发送typing指示
                await message.chat.send_action("typing")
                
                # 调用LLM生成响应
                response = await self._llm_gateway.generate_simple(
                    messages=session.get_messages_for_llm(),
                    user_id=user_id,
                    bot_id=instance.bot_id,
                    model=config.ai.model,
                    provider=config.ai.provider,
                    max_tokens=config.ai.max_tokens,
                    temperature=config.ai.temperature
                )
                
                # 添加助手响应到会话
                session.add_assistant_message(response)
                
                # 发送响应
                await message.reply_text(response)
                
            except Exception as e:
                logger.error(f"Error handling message for bot {instance.bot_id}: {e}")
                instance.error_count += 1
                await message.reply_text("抱歉，处理消息时出现错误。请稍后再试。")
        
        # 注册处理器
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        ))
    
    async def stop_bot(self, bot_id: str) -> bool:
        """停止指定的Bot"""
        instance = self._instances.get(bot_id)
        if not instance:
            logger.error(f"Bot not found: {bot_id}")
            return False
        
        if not instance.is_running:
            logger.warning(f"Bot not running: {bot_id}")
            return True
        
        try:
            if instance.application:
                await instance.application.stop()
                await instance.application.shutdown()
            
            instance.is_running = False
            instance.application = None
            
            logger.info(f"Bot stopped: {bot_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping bot {bot_id}: {e}")
            return False
    
    async def run_single_bot(self, bot_id: str, token: str) -> None:
        """
        运行单个Bot（阻塞模式）
        
        用于只运行一个Bot的场景
        """
        if not self._is_initialized:
            self.initialize()
        
        instance = self._instances.get(bot_id)
        if not instance:
            logger.error(f"Bot not found: {bot_id}")
            return
        
        # 创建并配置Application
        app = Application.builder().token(token).build()
        self._setup_handlers(app, instance)
        
        instance.application = app
        instance.is_running = True
        instance.started_at = datetime.now(timezone.utc)
        
        logger.info(f"Starting bot: {bot_id} ({instance.config.name})")
        
        # 启动轮询
        await app.initialize()
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        
        # 保持运行
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop_bot(bot_id)
    
    def run_polling(self, bot_id: str, token: str) -> None:
        """
        同步方式运行单个Bot
        
        Args:
            bot_id: Bot标识
            token: Telegram Bot Token
        """
        if not self._is_initialized:
            self.initialize()
        
        instance = self._instances.get(bot_id)
        if not instance:
            raise ValueError(f"Bot not found: {bot_id}")
        
        # 创建并配置Application
        app = Application.builder().token(token).build()
        self._setup_handlers(app, instance)
        
        instance.application = app
        instance.is_running = True
        instance.started_at = datetime.now(timezone.utc)
        
        logger.info(f"Starting bot in polling mode: {bot_id}")
        
        # 启动轮询（阻塞）
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取平台统计信息"""
        total_messages = sum(i.message_count for i in self._instances.values())
        total_errors = sum(i.error_count for i in self._instances.values())
        running_bots = sum(1 for i in self._instances.values() if i.is_running)
        
        return {
            "total_bots": len(self._instances),
            "running_bots": running_bots,
            "total_messages": total_messages,
            "total_errors": total_errors,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "llm_stats": self._llm_gateway.get_stats() if self._llm_gateway else {},
            "session_stats": self._session_manager.get_stats() if self._session_manager else {}
        }


# 全局平台实例
_platform: Optional[MultiBotPlatform] = None


def get_platform() -> MultiBotPlatform:
    """获取全局平台实例"""
    global _platform
    if _platform is None:
        _platform = MultiBotPlatform()
    return _platform
