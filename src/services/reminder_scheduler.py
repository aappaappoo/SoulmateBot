"""
Reminder Scheduler - 提醒调度器

负责定期检查待发送的提醒并发送给用户。

使用方法：
1. 在 Bot 启动时调用 start_reminder_scheduler()
2. 调度器会每分钟检查一次待发送的提醒
3. 在 Bot 关闭时调用 stop_reminder_scheduler()
"""
import asyncio
from typing import Dict, Optional
from datetime import datetime
from loguru import logger
from telegram import Bot
from telegram.error import TelegramError

from src.database import get_async_db_context
from src.services.reminder_service import ReminderService, format_reminder_message
from src.models.database import ReminderStatus


class ReminderScheduler:
    """
    提醒调度器 - 管理提醒的定时发送
    """
    
    def __init__(self, check_interval: int = 60):
        """
        初始化调度器
        
        Args:
            check_interval: 检查间隔（秒），默认60秒
        """
        self.check_interval = check_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._bots: Dict[int, Bot] = {}  # bot_id -> Bot 实例的映射
    
    def register_bot(self, bot_id: int, bot: Bot) -> None:
        """
        注册 Bot 实例，用于发送提醒消息
        
        Args:
            bot_id: 数据库中的 Bot ID
            bot: Telegram Bot 实例
        """
        self._bots[bot_id] = bot
        logger.info(f"📝 Registered bot {bot_id} for reminder scheduler")
    
    def unregister_bot(self, bot_id: int) -> None:
        """
        取消注册 Bot 实例
        
        Args:
            bot_id: Bot ID
        """
        if bot_id in self._bots:
            del self._bots[bot_id]
            logger.info(f"📝 Unregistered bot {bot_id} from reminder scheduler")
    
    async def start(self) -> None:
        """启动调度器"""
        if self._running:
            logger.warning("Reminder scheduler is already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("🔔 Reminder scheduler started")
    
    async def stop(self) -> None:
        """停止调度器"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("🔔 Reminder scheduler stopped")
    
    async def _run_loop(self) -> None:
        """调度器主循环"""
        while self._running:
            try:
                await self._check_and_send_reminders()
            except Exception as e:
                logger.error(f"Error in reminder scheduler: {e}", exc_info=True)
            
            await asyncio.sleep(self.check_interval)
    
    async def _check_and_send_reminders(self) -> None:
        """检查并发送待处理的提醒"""
        async with get_async_db_context() as db:
            reminder_service = ReminderService(db)
            pending_reminders = await reminder_service.get_pending_reminders()
            
            if not pending_reminders:
                return
            
            logger.info(f"📅 Found {len(pending_reminders)} pending reminders")
            
            for reminder in pending_reminders:
                await self._send_reminder(db, reminder_service, reminder)
    
    async def _send_reminder(self, db, reminder_service: ReminderService, reminder) -> None:
        """
        发送单个提醒
        
        Args:
            db: 数据库会话
            reminder_service: 提醒服务
            reminder: 提醒对象
        """
        try:
            # 获取对应的 Bot 实例
            bot = self._bots.get(reminder.bot_id)
            
            if not bot:
                # 如果没有注册对应的 Bot，尝试使用任意一个 Bot
                if self._bots:
                    bot = next(iter(self._bots.values()))
                else:
                    logger.warning(f"No bot available to send reminder {reminder.id}")
                    await reminder_service.mark_as_failed(
                        reminder.id, 
                        "No bot available"
                    )
                    return
            
            # 发送提醒消息
            reminder_message = format_reminder_message(reminder.reminder_text)
            
            await bot.send_message(
                chat_id=reminder.chat_id,
                text=reminder_message,
                parse_mode="Markdown"
            )
            
            # 标记为已发送
            await reminder_service.mark_as_sent(reminder.id)
            logger.info(f"✅ Reminder {reminder.id} sent successfully")
            
        except TelegramError as e:
            logger.error(f"Failed to send reminder {reminder.id}: {e}")
            await reminder_service.mark_as_failed(reminder.id, str(e))
        except Exception as e:
            logger.error(f"Error sending reminder {reminder.id}: {e}", exc_info=True)
            await reminder_service.mark_as_failed(reminder.id, str(e))


# 全局调度器实例
_scheduler: Optional[ReminderScheduler] = None


def get_reminder_scheduler() -> ReminderScheduler:
    """获取全局提醒调度器实例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = ReminderScheduler()
    return _scheduler


async def start_reminder_scheduler() -> None:
    """启动全局提醒调度器"""
    scheduler = get_reminder_scheduler()
    await scheduler.start()


async def stop_reminder_scheduler() -> None:
    """停止全局提醒调度器"""
    scheduler = get_reminder_scheduler()
    await scheduler.stop()
