"""
Database models for SoulmateBot
"""
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean, ForeignKey, Text, Enum as SQLEnum, JSON
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


class BotStatus(str, enum.Enum):
    """Bot status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
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


class Bot(Base):
    """Bot model for storing bot configurations"""
    __tablename__ = "bots"

    id = Column(Integer, primary_key=True, index=True)
    bot_token = Column(String(255), unique=True, nullable=False, index=True)
    bot_name = Column(String(255), nullable=False)
    bot_username = Column(String(255), unique=True, nullable=False, index=True)
    
    # Bot configuration
    description = Column(Text, nullable=True)
    personality = Column(Text, nullable=True)  # Bot的个性描述
    system_prompt = Column(Text, nullable=True)  # AI系统提示词
    ai_model = Column(String(100), default="gpt-4")  # 使用的AI模型
    ai_provider = Column(String(50), default="openai")  # AI提供商: openai, anthropic, vllm
    
    # Bot settings (stored as JSON)
    settings = Column(JSON, default={})  # 其他配置项，如temperature, max_tokens等
    
    # Status and ownership
    status = Column(String(20), default=BotStatus.ACTIVE.value)
    is_public = Column(Boolean, default=True)  # 是否可被其他用户添加到频道
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)  # 创建者
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    channel_mappings = relationship("ChannelBotMapping", back_populates="bot", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Bot(id={self.id}, username=@{self.bot_username}, name={self.bot_name})>"


class Channel(Base):
    """Channel model for storing channel/chat information"""
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    telegram_chat_id = Column(BigInteger, unique=True, index=True, nullable=False)
    chat_type = Column(String(50), nullable=False)  # private, group, supergroup, channel
    title = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    
    # Owner information
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Channel settings
    settings = Column(JSON, default={})  # 频道配置，如路由模式、订阅信息等
    
    # Subscription info (for channel-level subscriptions)
    subscription_tier = Column(String(20), default=SubscriptionTier.FREE.value)
    subscription_start_date = Column(DateTime, nullable=True)
    subscription_end_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    bot_mappings = relationship("ChannelBotMapping", back_populates="channel", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Channel(id={self.id}, chat_id={self.telegram_chat_id}, type={self.chat_type})>"


class ChannelBotMapping(Base):
    """Mapping table for channel-bot relationships"""
    __tablename__ = "channel_bot_mappings"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Mapping configuration
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # 机器人响应优先级，数字越大优先级越高
    routing_mode = Column(String(50), default="mention")  # mention（需要@）, auto（自动回复）, keyword（关键词触发）
    keywords = Column(JSON, default=[])  # 关键词列表，用于keyword模式
    
    # Settings specific to this mapping
    settings = Column(JSON, default={})  # 特定于这个映射的配置
    
    # Timestamps
    added_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    channel = relationship("Channel", back_populates="bot_mappings")
    bot = relationship("Bot", back_populates="channel_mappings")
    
    def __repr__(self):
        return f"<ChannelBotMapping(id={self.id}, channel_id={self.channel_id}, bot_id={self.bot_id})>"