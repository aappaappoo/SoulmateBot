"""
Async Subscription Service - 异步订阅服务
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from loguru import logger

from src.models.database import User, UsageRecord, SubscriptionTier
from config import settings


class AsyncSubscriptionService:
    """异步订阅服务"""

    def __init__(self, db:  AsyncSession):
        self.db = db

    async def get_user_by_telegram_id(self, telegram_id: int) -> User:
        """根据Telegram ID获取或创建用户"""
        result = await self.db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                telegram_id=telegram_id,
                subscription_tier=SubscriptionTier.FREE.value,
                is_active=True
            )
            self.db. add(user)
            await self.db.commit()
            await self.db.refresh(user)
            logger.info(f"Created new user: telegram_id={telegram_id}")

        return user

    async def update_user_info(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name:  Optional[str] = None,
        language_code: Optional[str] = None
    ) -> User:
        """更新用户信息"""
        user = await self.get_user_by_telegram_id(telegram_id)

        if username:
            user.username = username
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        if language_code:
            user.language_code = language_code

        await self.db.commit()
        await self.db. refresh(user)
        return user

    async def check_subscription_status(self, user:  User) -> bool:
        """检查订阅状态"""
        if user.subscription_tier == SubscriptionTier.FREE.value:
            return True

        if user.subscription_end_date and user.subscription_end_date < datetime.utcnow():
            return False

        return user.is_active

    async def check_usage_limit(self, user: User, action_type: str = "message") -> bool:
        """检查使用限制"""
        daily_limit = self.get_daily_limit(user. subscription_tier)

        if daily_limit == -1:  # 无限制
            return True

        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        result = await self.db.execute(
            select(func.sum(UsageRecord.count)).where(
                UsageRecord.user_id == user.id,
                UsageRecord.action_type == action_type,
                UsageRecord.date >= today_start,
                UsageRecord.date <= today_end
            )
        )
        total_usage = result.scalar() or 0

        return total_usage < daily_limit

    async def record_usage(self, user: User, action_type: str = "message", count: int = 1):
        """记录使用量"""
        usage_record = UsageRecord(
            user_id=user.id,
            action_type=action_type,
            count=count,
            date=datetime.utcnow()
        )
        self.db.add(usage_record)
        await self.db.commit()

    async def get_usage_stats(self, user: User) -> Dict[str, Any]:
        """获取使用统计"""
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        # 查询今日消息使用量
        result = await self.db.execute(
            select(func.sum(UsageRecord.count)).where(
                UsageRecord.user_id == user.id,
                UsageRecord.action_type == "message",
                UsageRecord.date >= today_start,
                UsageRecord. date <= today_end
            )
        )
        messages_used = result.scalar() or 0

        # 查询今日图片使用量
        result = await self.db.execute(
            select(func.sum(UsageRecord.count)).where(
                UsageRecord.user_id == user.id,
                UsageRecord.action_type == "image",
                UsageRecord. date >= today_start,
                UsageRecord.date <= today_end
            )
        )
        images_used = result.scalar() or 0

        daily_limit = self.get_daily_limit(user.subscription_tier)

        return {
            "messages_used": messages_used,
            "messages_limit": daily_limit,
            "images_used": images_used,
            "subscription_tier": user.subscription_tier
        }

    def get_daily_limit(self, tier: str) -> int:
        """获取每日限额"""
        limits = {
            SubscriptionTier.FREE.value: settings.free_plan_daily_limit,
            SubscriptionTier.BASIC.value: settings.basic_plan_daily_limit,
            SubscriptionTier.PREMIUM. value: settings.premium_plan_daily_limit,
        }
        return limits.get(tier, settings.free_plan_daily_limit)

    async def upgrade_subscription(
        self,
        user: User,
        tier: SubscriptionTier,
        duration_days: int = 30
    ) -> User:
        """升级订阅"""
        user.subscription_tier = tier.value
        user.subscription_start_date = datetime.utcnow()
        user.subscription_end_date = datetime.utcnow() + timedelta(days=duration_days)

        await self.db.commit()
        await self.db.refresh(user)
        logger.info(f"User {user.telegram_id} upgraded to {tier. value}")
        return user