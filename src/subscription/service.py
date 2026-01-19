"""
Subscription management service
"""
from datetime import datetime, timedelta
from sqlalchemy. orm import Session
from sqlalchemy import func
from loguru import logger

from src.models.database import User, UsageRecord, SubscriptionTier
from config import settings


class SubscriptionService:
    """Service for managing user subscriptions and usage limits"""

    def __init__(self, db: Session):
        self.db = db

    def get_user_by_telegram_id(self, telegram_id: int) -> User:
        """Get or create user by Telegram ID"""
        try:
            logger.info(f"Looking for user with telegram_id: {telegram_id}")
            user = self.db. query(User).filter(User.telegram_id == telegram_id).first()

            if not user:
                logger.info(f"Creating new user with telegram_id: {telegram_id}")

                # ✅ 使用 . value 获取枚举的字符串值
                user = User(
                    telegram_id=telegram_id,
                    subscription_tier=SubscriptionTier.FREE.value,  # 注意这里
                    is_active=True
                )

                self.db.add(user)
                self.db.commit()
                self.db.refresh(user)
                logger.info(f"✅ User created successfully with ID: {user.id}")
            else:
                logger.info(f"Found existing user:  {user.id}")

            return user

        except Exception as e:
            # logger.error(f"Error in get_user_by_telegram_id: {str(e)}", exc_info=True)
            logger.error("Error in get_user_by_telegram_id: {}", str(e), exc_info=True)
            self.db.rollback()
            raise

    def update_user_info(
        self,
        telegram_id: int,
        username: str = None,
        first_name: str = None,
        last_name:  str = None,
        language_code: str = None
    ) -> User:
        """Update user information"""
        try:
            user = self.get_user_by_telegram_id(telegram_id)

            if username is not None:
                user.username = username
            if first_name is not None:
                user. first_name = first_name
            if last_name is not None:
                user.last_name = last_name
            if language_code is not None:
                user.language_code = language_code

            user.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(user)

            logger.info(f"✅ Updated user info for telegram_id: {telegram_id}")
            return user

        except Exception as e:
            logger.error(f"Error updating user info: {str(e)}", exc_info=True)
            self.db.rollback()
            raise

    def get_daily_limit(self, subscription_tier: str) -> int:
        """Get daily message limit for subscription tier"""
        # ✅ 处理字符串或枚举
        if isinstance(subscription_tier, SubscriptionTier):
            tier_value = subscription_tier.value
        else:
            tier_value = subscription_tier

        limits = {
            SubscriptionTier.FREE.value: settings.free_plan_daily_limit,
            SubscriptionTier.BASIC.value: settings.basic_plan_daily_limit,
            SubscriptionTier.PREMIUM. value: settings.premium_plan_daily_limit,
        }
        return limits.get(tier_value, settings.free_plan_daily_limit)

    def check_subscription_status(self, user: User) -> bool:
        """Check if user's subscription is active"""
        if user.subscription_tier == SubscriptionTier.FREE.value:
            return True

        if user.subscription_end_date and datetime.utcnow() > user.subscription_end_date:
            logger.warning(f"Subscription expired for user {user.id}")
            user.subscription_tier = SubscriptionTier.FREE.value
            user.is_active = True
            self.db.commit()
            return False

        return user.is_active

    def check_usage_limit(self, user: User, action_type: str = "message") -> bool:
        """Check if user has exceeded their daily usage limit"""
        try:
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

            usage_count = self.db.query(func.sum(UsageRecord.count)).filter(
                UsageRecord.user_id == user.id,
                UsageRecord.action_type == action_type,
                UsageRecord.date >= today_start
            ).scalar() or 0

            daily_limit = self.get_daily_limit(user.subscription_tier)

            logger.info(f"User {user.id} usage: {usage_count}/{daily_limit}")

            return usage_count < daily_limit

        except Exception as e:
            logger.error(f"Error checking usage limit: {str(e)}", exc_info=True)
            return True

    def record_usage(self, user: User, action_type: str = "message", count: int = 1):
        """Record user usage"""
        try:
            usage = UsageRecord(
                user_id=user.id,
                action_type=action_type,
                count=count,
                date=datetime.utcnow()
            )
            self.db.add(usage)
            self.db.commit()
            logger.info(f"✅ Recorded usage for user {user. id}: {action_type} x{count}")

        except Exception as e:
            logger.error(f"Error recording usage: {str(e)}", exc_info=True)
            self.db.rollback()

    def get_usage_stats(self, user: User) -> dict:
        """Get user's usage statistics for today"""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        message_count = self.db.query(func.sum(UsageRecord.count)).filter(
            UsageRecord.user_id == user.id,
            UsageRecord.action_type == "message",
            UsageRecord.date >= today_start
        ).scalar() or 0

        image_count = self.db.query(func.sum(UsageRecord.count)).filter(
            UsageRecord.user_id == user.id,
            UsageRecord.action_type == "image",
            UsageRecord.date >= today_start
        ).scalar() or 0

        daily_limit = self.get_daily_limit(user.subscription_tier)

        return {
            "subscription_tier": user.subscription_tier,
            "is_active": user.is_active,
            "messages_used": int(message_count),
            "messages_limit": daily_limit,
            "images_used": int(image_count)
        }

    def upgrade_subscription(
        self,
        user: User,
        tier: SubscriptionTier,
        duration_days: int = 30
    ) -> User:
        """Upgrade user subscription"""
        try:
            user.subscription_tier = tier.value  # ✅ 使用 .value
            user.subscription_start_date = datetime.utcnow()
            user.subscription_end_date = datetime.utcnow() + timedelta(days=duration_days)
            user.is_active = True

            self.db.commit()
            self.db.refresh(user)

            logger.info(f"✅ Upgraded user {user.id} to {tier.value}")
            return user

        except Exception as e:
            logger.error(f"Error upgrading subscription: {str(e)}", exc_info=True)
            self.db.rollback()
            raise