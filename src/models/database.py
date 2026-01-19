"""
Database models for SoulmateBot
"""
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum


Base = declarative_base()


class SubscriptionTier(str, enum.Enum):
    """Subscription tier enumeration"""
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"


class User(Base):
    """User model for storing user information"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    language_code = Column(String(10), default="zh")

    # ✅ 修复：使用 String 而不是 SQLEnum，避免 PostgreSQL 的 Enum 类型问题
    subscription_tier = Column(String(20), default=SubscriptionTier.FREE.value)
    subscription_start_date = Column(DateTime, nullable=True)
    subscription_end_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    usage_records = relationship("UsageRecord", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, tier={self.subscription_tier})>"

    @property
    def subscription_tier_enum(self):
        """Get subscription tier as enum"""
        return SubscriptionTier(self.subscription_tier)


class Conversation(Base):
    """Conversation model for storing chat history"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    message = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    is_user_message = Column(Boolean, default=True)

    # Metadata
    message_type = Column(String(50), default="text")
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="conversations")

    def __repr__(self):
        return f"<Conversation(id={self.id}, user_id={self.user_id}, type={self.message_type})>"


class UsageRecord(Base):
    """Usage record for tracking API calls and enforcing limits"""
    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action_type = Column(String(50), nullable=False)
    count = Column(Integer, default=1)
    date = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="usage_records")

    def __repr__(self):
        return f"<UsageRecord(id={self.id}, user_id={self.user_id}, type={self.action_type}, count={self.count})>"


class Payment(Base):
    """Payment model for tracking subscription payments"""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users. id"), nullable=False)
    amount = Column(Integer, nullable=False)
    currency = Column(String(3), default="CNY")

    # Payment provider info
    provider = Column(String(50), default="wechat")
    provider_payment_id = Column(String(255), unique=True)
    provider_order_id = Column(String(255), unique=True, index=True)
    
    # Subscription info
    subscription_tier = Column(String(20), nullable=True)
    subscription_duration_days = Column(Integer, default=30)

    # Status
    status = Column(String(50), default="pending")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Payment(id={self.id}, user_id={self.user_id}, amount={self.amount}, status={self.status})>"