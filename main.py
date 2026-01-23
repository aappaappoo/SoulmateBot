"""
Multi-Bot Launcher - 多机器人并行启动器
==========================================

同时启动和管理多个 Telegram Bot 实例，每个 Bot 独立轮询消息。

使用方法:
  python multi_bot_launcher.py              # 启动所有已注册的 Bot
  python multi_bot_launcher.py --list       # 列出所有可用的 Bot
  python multi_bot_launcher.py --bot qiqi   # 只启动指定的 Bot
"""
import asyncio
import signal
import sys
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from loguru import logger
from sqlalchemy import select

from src.database import get_async_db_context, init_async_db
from src.models.database import Bot as BotModel
from src.bot.config_loader import BotConfigLoader, BotConfig
from src.llm_gateway import get_llm_gateway
from src.conversation import get_session_manager
from src.handlers import (
    start_command, help_command, status_command, subscribe_command,
    image_command, pay_basic_command, pay_premium_command, check_payment_command,
    handle_photo, handle_sticker, error_handler,
    list_bots_command, add_bot_command, remove_bot_command, my_bots_command, config_bot_command,
    feedback_stats_command, my_feedback_command
)
from src.handlers.agent_integration import (
    handle_message_with_agents, handle_skills_command, get_skill_callback_handler
)


@dataclass
class RunningBot:
    """运行中的 Bot 实例"""
    bot_id: int
    bot_username: str
    application: Application
    task: Optional[asyncio.Task] = None
    started_at: Optional[datetime] = None
    message_count: int = 0
    error_count: int = 0


class MultiBotLauncher:
    """
    多 Bot 启动器

    负责从数据库加载所有活跃的 Bot 配置和 Token，
    然后并行启动它们各自的轮询循环。
    """

    def __init__(self, bots_dir: str = "bots"):
        self.bots_dir = bots_dir
        self.config_loader = BotConfigLoader(bots_dir)
        self.running_bots: Dict[int, RunningBot] = {}
        self._shutdown_event = asyncio.Event()
        self._llm_gateway = None
        self._session_manager = None

        logger.info("MultiBotLauncher initialized")

    async def load_bots_from_db(self) -> List[BotModel]:
        """从数据库加载所有活跃的 Bot"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(BotModel).where(
                    BotModel.status == "active",
                    BotModel.bot_token.isnot(None)
                )
            )
            bots = result.scalars().all()
            logger.info(f"Loaded {len(bots)} active bots from database")
            return list(bots)

    def setup_handlers(self, app: Application, bot_db: BotModel, bot_config: Optional[BotConfig] = None) -> None:
        """
        为每个 Bot 设置处理器

        Args:
            app: Telegram Application 实例
            bot_db: 数据库中的 Bot 记录
            bot_config: 从 YAML 加载的配置（可选）
        """
        # ===== 基础命令处理器 =====
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("status", status_command))
        app.add_handler(CommandHandler("subscribe", subscribe_command))
        app.add_handler(CommandHandler("image", image_command))

        # ===== 支付命令 =====
        app.add_handler(CommandHandler("pay_basic", pay_basic_command))
        app.add_handler(CommandHandler("pay_premium", pay_premium_command))
        app.add_handler(CommandHandler("check_payment", check_payment_command))

        # ===== Bot 管理命令 =====
        app.add_handler(CommandHandler("list_bots", list_bots_command))
        app.add_handler(CommandHandler("add_bot", add_bot_command))
        app.add_handler(CommandHandler("remove_bot", remove_bot_command))
        app.add_handler(CommandHandler("my_bots", my_bots_command))
        app.add_handler(CommandHandler("config_bot", config_bot_command))

        # ===== 反馈命令 =====
        app.add_handler(CommandHandler("feedback_stats", feedback_stats_command))
        app.add_handler(CommandHandler("my_feedback", my_feedback_command))

        # ===== Agent 技能命令 =====
        app.add_handler(CommandHandler("skills", handle_skills_command))
        app.add_handler(get_skill_callback_handler())

        # ===== 消息处理器 =====
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message_with_agents
        ))
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        app.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))

        # ===== 错误处理器 =====
        app.add_error_handler(error_handler)

        logger.info(f"Handlers registered for bot: @{bot_db.bot_username}")

    async def run_single_bot(self, bot_db: BotModel) -> None:
        """
        运行单个 Bot 的轮询循环

        Args:
            bot_db: 数据库中的 Bot 记录
        """
        bot_id = bot_db.id
        bot_username = bot_db.bot_username
        token = bot_db.bot_token

        logger.info(f"Starting bot: @{bot_username} (ID: {bot_id})")

        try:
            # 尝试加载 YAML 配置（如果存在）
            bot_config = self.config_loader.get_config(f"{bot_username}_bot")
            if not bot_config:
                # 尝试其他命名格式
                bot_config = self.config_loader.get_config(bot_username)

            # 创建 Application
            app = Application.builder().token(token).build()

            # 设置处理器
            self.setup_handlers(app, bot_db, bot_config)

            # 记录运行状态
            self.running_bots[bot_id] = RunningBot(
                bot_id=bot_id,
                bot_username=bot_username,
                application=app,
                started_at=datetime.now(timezone.utc)
            )

            # 初始化并启动
            await app.initialize()
            await app.start()
            await app.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )

            logger.info(f"✅ Bot @{bot_username} is now polling for updates")

            # 保持运行直到收到停止信号
            while not self._shutdown_event.is_set():
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info(f"Bot @{bot_username} received cancel signal")
        except Exception as e:
            logger.error(f"❌ Error running bot @{bot_username}: {e}", exc_info=True)
            if bot_id in self.running_bots:
                self.running_bots[bot_id].error_count += 1
        finally:
            # 清理
            await self.stop_bot(bot_id)

    async def stop_bot(self, bot_id: int) -> None:
        """停止指定的 Bot"""
        if bot_id not in self.running_bots:
            return

        running_bot = self.running_bots[bot_id]
        logger.info(f"Stopping bot: @{running_bot.bot_username}")

        try:
            if running_bot.application:
                if running_bot.application.updater.running:
                    await running_bot.application.updater.stop()
                await running_bot.application.stop()
                await running_bot.application.shutdown()
        except Exception as e:
            logger.error(f"Error stopping bot @{running_bot.bot_username}: {e}")
        finally:
            del self.running_bots[bot_id]
            logger.info(f"Bot @{running_bot.bot_username} stopped")

    async def start_all(self, specific_bot: Optional[str] = None) -> None:
        """
        启动所有或指定的 Bot

        Args:
            specific_bot: 可选，只启动指定用户名的 Bot
        """
        # 初始化数据库
        logger.info("Initializing database...")
        await init_async_db()

        # 初始化共享服务
        self._llm_gateway = get_llm_gateway()
        self._session_manager = get_session_manager()

        # 加载 YAML 配置
        self.config_loader.load_all_configs()

        # 从数据库加载 Bot
        bots = await self.load_bots_from_db()

        if not bots:
            logger.error("❌ No active bots found in database!")
            logger.info("请先使用 db_manager.py 注册 Bot 并设置 Token")
            return

        # 过滤指定的 Bot
        if specific_bot:
            bots = [b for b in bots if b.bot_username == specific_bot]
            if not bots:
                logger.error(f"❌ Bot '{specific_bot}' not found in database")
                return

        logger.info(f"🚀 Starting {len(bots)} bot(s)...")

        # 创建所有 Bot 的任务
        tasks = []
        for bot_db in bots:
            task = asyncio.create_task(self.run_single_bot(bot_db))
            tasks.append(task)
            # 稍微延迟，避免同时发起太多请求
            await asyncio.sleep(0.5)

        # 设置信号处理
        def signal_handler():
            logger.info("Received shutdown signal...")
            self._shutdown_event.set()

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, signal_handler)
            except NotImplementedError:
                # Windows 不支持 add_signal_handler
                pass

        # 等待所有任务完成或收到停止信号
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass

        logger.info("All bots stopped")

    async def stop_all(self) -> None:
        """停止所有 Bot"""
        self._shutdown_event.set()

        for bot_id in list(self.running_bots.keys()):
            await self.stop_bot(bot_id)

    def get_stats(self) -> Dict:
        """获取运行统计"""
        return {
            "running_bots": len(self.running_bots),
            "bots": [
                {
                    "id": rb.bot_id,
                    "username": rb.bot_username,
                    "started_at": rb.started_at.isoformat() if rb.started_at else None,
                    "message_count": rb.message_count,
                    "error_count": rb.error_count
                }
                for rb in self.running_bots.values()
            ]
        }


async def list_available_bots():
    """列出数据库中所有可用的 Bot"""
    await init_async_db()

    async with get_async_db_context() as db:
        result = await db.execute(select(BotModel))
        bots = result.scalars().all()

        if not bots:
            print("❌ 数据库中没有注册的 Bot")
            print("\n请使用以下命令注册 Bot:")
            print("  python db_manager.py register --username your_bot_username --token YOUR_BOT_TOKEN")
            return

        print("\n📋 已注册的 Bot 列表:\n")
        print(f"{'ID':<6} {'用户名':<20} {'名称':<15} {'状态':<10} {'Token':<10}")
        print("-" * 65)

        for bot in bots:
            token_status = "✅ 已设置" if bot.bot_token else "❌ 未设置"
            print(f"{bot.id:<6} @{bot.bot_username:<19} {bot.bot_name:<15} {bot.status:<10} {token_status}")

        print("\n")


async def main():
    """主入口"""
    import argparse

    parser = argparse.ArgumentParser(description="Multi-Bot Launcher - 多机器人启动器")
    parser.add_argument("--list", action="store_true", help="列出所有可用的 Bot")
    parser.add_argument("--bot", type=str, help="只启动指定用户名的 Bot")
    parser.add_argument("--stats", action="store_true", help="显示运行统计")

    args = parser.parse_args()

    # 配置日志
    logger.add(
        "logs/multi_bot_{time}.log",
        rotation="1 day",
        retention="7 days",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}"
    )

    if args.list:
        await list_available_bots()
        return

    # 启动 Bot
    launcher = MultiBotLauncher()

    try:
        await launcher.start_all(specific_bot=args.bot)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        await launcher.stop_all()


if __name__ == "__main__":
    asyncio.run(main())