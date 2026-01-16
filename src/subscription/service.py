"""
Subscription management service
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.models.database import User, UsageRecord, SubscriptionTier
from config import settings


class SubscriptionService:
    """Service for managing user subscriptions and usage limits"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_by_telegram_id(self, telegram_id: int) -> User:
        """Get or create user by Telegram ID"""
        user = self.db.query(User).filter(User.telegram_id == telegram_id).first()
        
        if not user:
            user = User(
                telegram_id=telegram_id,
                subscription_tier=SubscriptionTier.FREE,
                is_active=True
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        
        return user
    
    def update_user_info(
        self,
        telegram_id: int,
        username: str = None,
        first_name: str = None,
        last_name: str = None,
        language_code: str = None
    ) -> User:
        """Update user information"""
        user = self.get_user_by_telegram_id(telegram_id)
        
        if username is not None:
            user.username = username
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if language_code is not None:
            user.language_code = language_code
        
        user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        
        return user
    
    def get_daily_limit(self, subscription_tier: SubscriptionTier) -> int:
        """Get daily message limit for subscription tier"""
        limits = {
            SubscriptionTier.FREE: settings.free_plan_daily_limit,
            SubscriptionTier.BASIC: settings.basic_plan_daily_limit,
            SubscriptionTier.PREMIUM: settings.premium_plan_daily_limit,
        }
        return limits.get(subscription_tier, settings.free_plan_daily_limit)
    
    def check_usage_limit(self, user: User, action_type: str = "message") -> bool:
        """
        Check if user has exceeded their daily usage limit
        
        Returns:
            True if user can proceed, False if limit exceeded
        """
        # Get today's usage
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        usage_count = self.db.query(func.sum(UsageRecord.count)).filter(
            UsageRecord.user_id == user.id,
            UsageRecord.action_type == action_type,
            UsageRecord.date >= today_start
        ).scalar() or 0
        
        # Get user's daily limit
        daily_limit = self.get_daily_limit(user.subscription_tier)
        
        return usage_count < daily_limit
    
    def record_usage(self, user: User, action_type: str = "message", count: int = 1):
        """Record user usage"""
        usage = UsageRecord(
            user_id=user.id,
            action_type=action_type,
            count=count,
            date=datetime.utcnow()
        )
        self.db.add(usage)
        self.db.commit()
    
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
            "subscription_tier": user.subscription_tier.value,
            "messages_used": message_count,
            "messages_limit": daily_limit,
            "images_used": image_count,
            "is_active": user.is_active
        }
    
    def upgrade_subscription(
        self,
        user: User,
        new_tier: SubscriptionTier,
        duration_days: int = 30
    ) -> User:
        """Upgrade user subscription"""
        user.subscription_tier = new_tier
        user.subscription_start_date = datetime.utcnow()
        user.subscription_end_date = datetime.utcnow() + timedelta(days=duration_days)
        user.is_active = True
        user.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(user)
        
        return user
    
    def check_subscription_status(self, user: User) -> bool:
        """Check if user's subscription is still active"""
        if user.subscription_tier == SubscriptionTier.FREE:
            return True
        
        if user.subscription_end_date and user.subscription_end_date < datetime.utcnow():
            # Subscription expired, downgrade to free
            user.subscription_tier = SubscriptionTier.FREE
            user.is_active = True
            self.db.commit()
            return False
        
        return user.is_active
