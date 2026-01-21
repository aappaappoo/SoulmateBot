"""
Mock Payment Gateway - 模拟支付网关

提供Mock的支付和额度管理功能，用于开发和测试
"""
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import uuid
from loguru import logger


class PaymentStatus(str, Enum):
    """支付状态"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class SubscriptionTier(str, Enum):
    """订阅等级"""
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"


@dataclass
class MockPayment:
    """Mock支付记录"""
    payment_id: str
    user_id: str
    amount: float
    currency: str = "CNY"
    tier: SubscriptionTier = SubscriptionTier.BASIC
    duration_days: int = 30
    status: PaymentStatus = PaymentStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "payment_id": self.payment_id,
            "user_id": self.user_id,
            "amount": self.amount,
            "currency": self.currency,
            "tier": self.tier.value,
            "duration_days": self.duration_days,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


@dataclass
class UserQuota:
    """用户额度"""
    user_id: str
    tier: SubscriptionTier = SubscriptionTier.FREE
    messages_used: int = 0
    messages_limit: int = 10
    images_used: int = 0
    images_limit: int = 0
    reset_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
    subscription_end: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "tier": self.tier.value,
            "messages_used": self.messages_used,
            "messages_limit": self.messages_limit,
            "messages_remaining": max(0, self.messages_limit - self.messages_used),
            "images_used": self.images_used,
            "images_limit": self.images_limit,
            "reset_date": self.reset_date.isoformat(),
            "subscription_end": self.subscription_end.isoformat() if self.subscription_end else None
        }


# 订阅计划配置
SUBSCRIPTION_PLANS = {
    SubscriptionTier.FREE: {
        "name": "免费版",
        "price": 0,
        "messages_limit": 10,
        "images_limit": 0,
        "features": ["基础对话"]
    },
    SubscriptionTier.BASIC: {
        "name": "基础版",
        "price": 9.9,
        "messages_limit": 100,
        "images_limit": 5,
        "features": ["基础对话", "图片生成", "对话历史"]
    },
    SubscriptionTier.PREMIUM: {
        "name": "高级版",
        "price": 29.9,
        "messages_limit": 1000,
        "images_limit": 50,
        "features": ["基础对话", "图片生成", "对话历史", "优先响应", "专属客服"]
    }
}


class MockPaymentGateway:
    """
    Mock支付网关
    
    模拟支付流程，用于开发和测试
    """
    
    def __init__(self):
        # 支付记录
        self._payments: Dict[str, MockPayment] = {}
        
        # 用户额度
        self._quotas: Dict[str, UserQuota] = {}
        
        logger.info("MockPaymentGateway initialized")
    
    def _get_plan_limits(self, tier: SubscriptionTier) -> tuple:
        """获取计划限额"""
        plan = SUBSCRIPTION_PLANS.get(tier, SUBSCRIPTION_PLANS[SubscriptionTier.FREE])
        return plan["messages_limit"], plan["images_limit"]
    
    def get_user_quota(self, user_id: str) -> UserQuota:
        """获取用户额度"""
        if user_id not in self._quotas:
            self._quotas[user_id] = UserQuota(user_id=user_id)
        
        quota = self._quotas[user_id]
        
        # 检查是否需要重置每日额度
        now = datetime.now(timezone.utc)
        if now >= quota.reset_date:
            quota.messages_used = 0
            quota.images_used = 0
            quota.reset_date = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            logger.info(f"Reset daily quota for user: {user_id}")
        
        # 检查订阅是否过期
        if quota.subscription_end and now > quota.subscription_end:
            if quota.tier != SubscriptionTier.FREE:
                logger.info(f"Subscription expired for user: {user_id}")
                quota.tier = SubscriptionTier.FREE
                quota.messages_limit, quota.images_limit = self._get_plan_limits(SubscriptionTier.FREE)
        
        return quota
    
    def check_quota(self, user_id: str, action_type: str = "message") -> bool:
        """
        检查用户额度
        
        Args:
            user_id: 用户ID
            action_type: 操作类型 (message/image)
            
        Returns:
            True如果有额度，False如果已用完
        """
        quota = self.get_user_quota(user_id)
        
        if action_type == "message":
            return quota.messages_used < quota.messages_limit
        elif action_type == "image":
            return quota.images_used < quota.images_limit
        
        return True
    
    def consume_quota(self, user_id: str, action_type: str = "message", count: int = 1) -> bool:
        """
        消费额度
        
        Args:
            user_id: 用户ID
            action_type: 操作类型
            count: 消费数量
            
        Returns:
            True如果成功消费，False如果额度不足
        """
        quota = self.get_user_quota(user_id)
        
        if action_type == "message":
            if quota.messages_used + count > quota.messages_limit:
                return False
            quota.messages_used += count
        elif action_type == "image":
            if quota.images_used + count > quota.images_limit:
                return False
            quota.images_used += count
        
        logger.debug(f"Consumed {count} {action_type} quota for user: {user_id}")
        return True
    
    def create_payment(
        self,
        user_id: str,
        tier: SubscriptionTier,
        duration_days: int = 30
    ) -> MockPayment:
        """
        创建支付订单
        
        Args:
            user_id: 用户ID
            tier: 订阅等级
            duration_days: 订阅天数
            
        Returns:
            支付记录
        """
        plan = SUBSCRIPTION_PLANS.get(tier)
        if not plan:
            raise ValueError(f"Invalid subscription tier: {tier}")
        
        payment = MockPayment(
            payment_id=str(uuid.uuid4()),
            user_id=user_id,
            amount=plan["price"] * (duration_days / 30),
            tier=tier,
            duration_days=duration_days
        )
        
        self._payments[payment.payment_id] = payment
        logger.info(f"Created payment: {payment.payment_id} for user: {user_id}")
        
        return payment
    
    def complete_payment(self, payment_id: str) -> bool:
        """
        完成支付（Mock - 直接成功）
        
        Args:
            payment_id: 支付ID
            
        Returns:
            是否成功
        """
        payment = self._payments.get(payment_id)
        if not payment:
            logger.warning(f"Payment not found: {payment_id}")
            return False
        
        if payment.status != PaymentStatus.PENDING:
            logger.warning(f"Payment already processed: {payment_id}")
            return False
        
        # Mock: 直接完成支付
        payment.status = PaymentStatus.COMPLETED
        payment.completed_at = datetime.now(timezone.utc)
        
        # 更新用户额度
        self._upgrade_subscription(
            payment.user_id,
            payment.tier,
            payment.duration_days
        )
        
        logger.info(f"Payment completed: {payment_id}")
        return True
    
    def _upgrade_subscription(
        self,
        user_id: str,
        tier: SubscriptionTier,
        duration_days: int
    ) -> None:
        """升级用户订阅"""
        quota = self.get_user_quota(user_id)
        
        quota.tier = tier
        quota.messages_limit, quota.images_limit = self._get_plan_limits(tier)
        
        now = datetime.now(timezone.utc)
        if quota.subscription_end and quota.subscription_end > now:
            # 延长现有订阅
            quota.subscription_end += timedelta(days=duration_days)
        else:
            # 新订阅
            quota.subscription_end = now + timedelta(days=duration_days)
        
        logger.info(f"Upgraded subscription for user: {user_id} to {tier.value}")
    
    def get_payment(self, payment_id: str) -> Optional[MockPayment]:
        """获取支付记录"""
        return self._payments.get(payment_id)
    
    def get_user_payments(self, user_id: str) -> list:
        """获取用户的所有支付记录"""
        return [p for p in self._payments.values() if p.user_id == user_id]
    
    def get_subscription_plans(self) -> Dict:
        """获取订阅计划列表"""
        return {
            tier.value: {
                **plan,
                "tier": tier.value
            }
            for tier, plan in SUBSCRIPTION_PLANS.items()
        }
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total_payments = len(self._payments)
        completed_payments = sum(1 for p in self._payments.values() if p.status == PaymentStatus.COMPLETED)
        total_revenue = sum(p.amount for p in self._payments.values() if p.status == PaymentStatus.COMPLETED)
        
        tier_counts = {}
        for quota in self._quotas.values():
            tier = quota.tier.value
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        
        return {
            "total_users": len(self._quotas),
            "total_payments": total_payments,
            "completed_payments": completed_payments,
            "total_revenue": total_revenue,
            "users_by_tier": tier_counts
        }


# 全局Mock支付网关实例
_mock_gateway: Optional[MockPaymentGateway] = None


def get_mock_payment_gateway() -> MockPaymentGateway:
    """获取Mock支付网关实例"""
    global _mock_gateway
    if _mock_gateway is None:
        _mock_gateway = MockPaymentGateway()
    return _mock_gateway
