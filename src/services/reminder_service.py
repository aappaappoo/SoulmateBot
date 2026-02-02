"""
Reminder Service - 提醒服务

负责解析用户的提醒请求，创建提醒记录，并在指定时间发送提醒。

支持的提醒格式：
- "X分钟/小时后提醒我..."
- "提醒我X分钟/小时后..."
- "X分钟/小时后记得提醒我..."
"""
import re
import asyncio
from typing import Optional, Tuple, List
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import Reminder, ReminderStatus, User, Bot


class ReminderParser:
    """
    提醒解析器 - 解析用户消息中的提醒请求
    """
    
    # 时间单位映射
    TIME_UNITS = {
        "分钟": 1,
        "分": 1,
        "分鐘": 1,
        "min": 1,
        "minute": 1,
        "minutes": 1,
        "小时": 60,
        "小時": 60,
        "个小时": 60,
        "個小時": 60,
        "hour": 60,
        "hours": 60,
        "hr": 60,
        "h": 60,
        "天": 1440,
        "day": 1440,
        "days": 1440,
    }
    
    # 中文数字映射
    CHINESE_NUMBERS = {
        "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
        "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
        "半": 0.5, "两": 2, "兩": 2
    }
    
    # 匹配提醒模式的正则表达式
    REMINDER_PATTERNS = [
        # "X分钟/小时后提醒我做某事" 或 "X分钟/小时后记得提醒我做某事"
        r"(\d+|[一二三四五六七八九十两兩半]+)\s*(分钟|分|分鐘|小时|小時|个小时|個小時|天|hour|hours|minute|minutes|min|day|days|hr|h)后[记記]?[得要]?提醒我(.+)",
        # "提醒我X分钟/小时后做某事"
        r"提醒我(\d+|[一二三四五六七八九十两兩半]+)\s*(分钟|分|分鐘|小时|小時|个小时|個小時|天|hour|hours|minute|minutes|min|day|days|hr|h)后(.+)",
        # "过X分钟/小时提醒我做某事"
        r"过[了]?(\d+|[一二三四五六七八九十两兩半]+)\s*(分钟|分|分鐘|小时|小時|个小时|個小時|天|hour|hours|minute|minutes|min|day|days|hr|h)提醒我(.+)",
        # 英文格式 "remind me in X minutes/hours to do something"
        r"remind me in (\d+)\s*(minute|minutes|min|hour|hours|hr|h|day|days)s?\s+(?:to\s+)?(.+)",
        # 英文格式 "in X minutes/hours remind me to do something"
        r"in (\d+)\s*(minute|minutes|min|hour|hours|hr|h|day|days)s?\s+remind me\s+(?:to\s+)?(.+)",
    ]
    
    def parse(self, message: str) -> Optional[Tuple[int, str]]:
        """
        解析消息，提取提醒时间和内容
        
        Args:
            message: 用户消息
            
        Returns:
            (minutes, reminder_text) 或 None（如果不是提醒请求）
        """
        message = message.strip()
        
        for pattern in self.REMINDER_PATTERNS:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                amount_str = match.group(1)
                unit = match.group(2).lower()
                content = match.group(3).strip()
                
                # 解析数量
                amount = self._parse_amount(amount_str)
                if amount is None:
                    continue
                
                # 计算分钟数
                minutes = int(amount * self.TIME_UNITS.get(unit, 1))
                
                # 清理内容
                content = self._clean_content(content)
                
                if content and minutes > 0:
                    return (minutes, content)
        
        return None
    
    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """解析数量（支持阿拉伯数字和中文数字）"""
        # 尝试作为阿拉伯数字解析
        try:
            return float(amount_str)
        except ValueError:
            pass
        
        # 尝试作为中文数字解析
        if amount_str in self.CHINESE_NUMBERS:
            return self.CHINESE_NUMBERS[amount_str]
        
        # 处理组合中文数字（如"十五"）
        if "十" in amount_str:
            if amount_str == "十":
                return 10
            elif amount_str.startswith("十"):
                # "十X" = 10 + X
                rest = amount_str[1:]
                if rest in self.CHINESE_NUMBERS:
                    return 10 + self.CHINESE_NUMBERS[rest]
            else:
                # "X十" 或 "X十Y"
                parts = amount_str.split("十")
                if len(parts) == 2:
                    tens = self.CHINESE_NUMBERS.get(parts[0], 0) * 10
                    ones = self.CHINESE_NUMBERS.get(parts[1], 0) if parts[1] else 0
                    return tens + ones
        
        return None
    
    def _clean_content(self, content: str) -> str:
        """清理提醒内容"""
        # 移除开头的独立"要"或"去"字
        # 仅当后面有内容且不会破坏词义时移除
        if content.startswith("要") and len(content) > 1:
            content = content[1:]
        elif content.startswith("去") and len(content) > 1:
            content = content[1:]
        # 移除结尾的标点符号
        content = content.rstrip("。！？!?")
        return content.strip()


class ReminderService:
    """
    提醒服务 - 管理用户的提醒
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.parser = ReminderParser()
    
    async def parse_and_create_reminder(
        self,
        message: str,
        user_id: int,
        telegram_user_id: int,
        chat_id: int,
        bot_id: Optional[int] = None
    ) -> Optional[Reminder]:
        """
        解析消息并创建提醒
        
        Args:
            message: 用户消息
            user_id: 数据库用户 ID
            telegram_user_id: Telegram 用户 ID
            chat_id: Telegram 聊天 ID
            bot_id: Bot ID
            
        Returns:
            创建的 Reminder 对象，如果消息不是提醒请求则返回 None
        """
        result = self.parser.parse(message)
        if not result:
            return None
        
        minutes, reminder_text = result
        remind_at = datetime.utcnow() + timedelta(minutes=minutes)
        
        reminder = Reminder(
            user_id=user_id,
            bot_id=bot_id,
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            reminder_text=reminder_text,
            original_message=message,
            remind_at=remind_at,
            status=ReminderStatus.PENDING.value
        )
        
        self.db.add(reminder)
        await self.db.commit()
        await self.db.refresh(reminder)
        
        logger.info(f"📅 Created reminder: {reminder_text[:50]}... at {remind_at}")
        return reminder
    
    async def get_pending_reminders(self, current_time: Optional[datetime] = None) -> List[Reminder]:
        """
        获取需要发送的待处理提醒
        
        Args:
            current_time: 当前时间，默认为 UTC 现在
            
        Returns:
            待发送的提醒列表
        """
        if current_time is None:
            current_time = datetime.utcnow()
        
        result = await self.db.execute(
            select(Reminder)
            .where(Reminder.status == ReminderStatus.PENDING.value)
            .where(Reminder.remind_at <= current_time)
            .order_by(Reminder.remind_at.asc())
        )
        return list(result.scalars().all())
    
    async def mark_as_sent(self, reminder_id: int) -> None:
        """标记提醒为已发送"""
        result = await self.db.execute(
            select(Reminder).where(Reminder.id == reminder_id)
        )
        reminder = result.scalar_one_or_none()
        if reminder:
            reminder.status = ReminderStatus.SENT.value
            reminder.sent_at = datetime.utcnow()
            await self.db.commit()
    
    async def mark_as_failed(self, reminder_id: int, error_message: str) -> None:
        """标记提醒为发送失败"""
        result = await self.db.execute(
            select(Reminder).where(Reminder.id == reminder_id)
        )
        reminder = result.scalar_one_or_none()
        if reminder:
            reminder.status = ReminderStatus.FAILED.value
            reminder.error_message = error_message
            reminder.retry_count += 1
            await self.db.commit()
    
    async def get_user_reminders(self, user_id: int, status: Optional[str] = None) -> List[Reminder]:
        """获取用户的提醒列表"""
        query = select(Reminder).where(Reminder.user_id == user_id)
        if status:
            query = query.where(Reminder.status == status)
        query = query.order_by(Reminder.remind_at.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())


def format_reminder_confirmation(minutes: int, reminder_text: str) -> str:
    """
    格式化提醒确认消息
    
    Args:
        minutes: 提醒时间（分钟）
        reminder_text: 提醒内容
        
    Returns:
        确认消息
    """
    if minutes >= 1440:
        days = minutes // 1440
        time_str = f"{days}天"
    elif minutes >= 60:
        hours = minutes // 60
        remaining_mins = minutes % 60
        if remaining_mins > 0:
            time_str = f"{hours}小时{remaining_mins}分钟"
        else:
            time_str = f"{hours}小时"
    else:
        time_str = f"{minutes}分钟"
    
    return f"⏰ 好的！我会在 {time_str} 后提醒你：\n\n📝 {reminder_text}\n\n放心吧，到时间我会准时提醒你的！"


def format_reminder_message(reminder_text: str) -> str:
    """
    格式化提醒发送消息
    
    Args:
        reminder_text: 提醒内容
        
    Returns:
        提醒消息
    """
    return f"⏰ **提醒时间到！**\n\n📝 {reminder_text}\n\n记得去做哦！"
