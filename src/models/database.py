"""
Database models for SoulmateBot
数据库模型 - 包含所有核心表的定义

设计原则：
1. 每个字段都有中文备注说明
2. 支持高并发场景（乐观锁、会话隔离）
3. 使用UUID/MD5字符串作为外部引用标识，内部仍使用Integer主键
"""
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean, ForeignKey, Text, Enum as SQLEnum, JSON, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid


Base = declarative_base()


def generate_uuid() -> str:
    """生成UUID字符串，用于外部引用标识"""
    return str(uuid.uuid4())


class SubscriptionTier(str, enum.Enum):
    """
    订阅等级枚举
    Subscription tier enumeration
    """
    FREE = "free"        # 免费版
    BASIC = "basic"      # 基础版
    PREMIUM = "premium"  # 高级版


class BotStatus(str, enum.Enum):
    """
    机器人状态枚举
    Bot status enumeration
    """
    ACTIVE = "active"           # 活跃状态
    INACTIVE = "inactive"       # 非活跃状态
    MAINTENANCE = "maintenance" # 维护中


class User(Base):
    """
    用户模型 - 存储用户基本信息
    User model for storing user information
    
    并发控制说明：
    - 使用version字段实现乐观锁，防止并发更新冲突
    - uuid字段用于外部API引用，避免暴露内部ID
    """
    __tablename__ = "users"

    # 主键和标识符
    id = Column(Integer, primary_key=True, index=True, comment="内部自增主键")
    uuid = Column(String(36), unique=True, index=True, default=generate_uuid, nullable=False, comment="外部引用UUID，用于API和外部系统交互")
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False, comment="Telegram用户ID")
    
    # 用户基本信息
    username = Column(String(255), nullable=True, comment="Telegram用户名")
    first_name = Column(String(255), nullable=True, comment="用户名（名）")
    last_name = Column(String(255), nullable=True, comment="用户姓（姓）")
    language_code = Column(String(10), default="zh", comment="用户语言偏好，默认中文")

    # 订阅信息
    # ✅ 修复：使用 String 而不是 SQLEnum，避免 PostgreSQL 的 Enum 类型问题
    subscription_tier = Column(String(20), default=SubscriptionTier.FREE.value, comment="订阅等级：free/basic/premium")
    subscription_start_date = Column(DateTime, nullable=True, comment="订阅开始日期")
    subscription_end_date = Column(DateTime, nullable=True, comment="订阅结束日期")
    is_active = Column(Boolean, default=True, comment="用户是否激活")

    # 并发控制
    version = Column(Integer, default=1, nullable=False, comment="乐观锁版本号，用于并发控制")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="最后更新时间")

    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    usage_records = relationship("UsageRecord", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, uuid={self.uuid}, telegram_id={self.telegram_id}, tier={self.subscription_tier})>"

    @property
    def subscription_tier_enum(self):
        """Get subscription tier as enum"""
        return SubscriptionTier(self.subscription_tier)


class Conversation(Base):
    """
    对话模型 - 存储聊天历史记录
    Conversation model for storing chat history
    
    并发控制说明：
    - 使用session_id支持多会话隔离
    - 添加复合索引优化高并发查询性能
    """
    __tablename__ = "conversations"

    # 主键和标识符
    id = Column(Integer, primary_key=True, index=True, comment="内部自增主键")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="关联的用户ID")
    session_id = Column(String(64), nullable=True, index=True, comment="会话标识，用于区分不同对话上下文")
    
    # 消息内容
    message = Column(Text, nullable=False, comment="用户消息或AI回复内容")
    response = Column(Text, nullable=True, comment="AI回复内容（仅用户消息时有值）")
    is_user_message = Column(Boolean, default=True, comment="是否为用户发送的消息")

    # 元数据
    message_type = Column(String(50), default="text", comment="消息类型：text/image/voice等")
    timestamp = Column(DateTime, default=datetime.utcnow, index=True, comment="消息时间戳")

    # Relationships
    user = relationship("User", back_populates="conversations")
    
    # 复合索引：优化用户会话查询性能
    __table_args__ = (
        Index('idx_user_session', 'user_id', 'session_id'),
        Index('idx_user_timestamp', 'user_id', 'timestamp'),
    )

    def __repr__(self):
        return f"<Conversation(id={self.id}, user_id={self.user_id}, type={self.message_type})>"


class UsageRecord(Base):
    """
    使用记录模型 - 追踪API调用并执行限制
    Usage record for tracking API calls and enforcing limits
    
    并发控制说明：
    - 使用复合索引优化按用户和日期查询的性能
    - 支持高并发下的使用量统计
    """
    __tablename__ = "usage_records"

    # 主键和关联
    id = Column(Integer, primary_key=True, index=True, comment="内部自增主键")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="关联的用户ID")
    
    # 使用记录信息
    action_type = Column(String(50), nullable=False, comment="操作类型：message/image/voice等")
    count = Column(Integer, default=1, comment="操作次数")
    date = Column(DateTime, default=datetime.utcnow, index=True, comment="记录日期")

    # Relationships
    user = relationship("User", back_populates="usage_records")
    
    # 复合索引：优化用户使用量统计查询
    __table_args__ = (
        Index('idx_user_action_date', 'user_id', 'action_type', 'date'),
    )

    def __repr__(self):
        return f"<UsageRecord(id={self.id}, user_id={self.user_id}, type={self.action_type}, count={self.count})>"


class Payment(Base):
    """
    支付模型 - 追踪订阅支付记录
    Payment model for tracking subscription payments
    
    并发控制说明：
    - 使用唯一索引防止重复支付
    - 支持幂等性处理
    """
    __tablename__ = "payments"

    # 主键和关联
    id = Column(Integer, primary_key=True, index=True, comment="内部自增主键")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="支付用户ID")
    
    # 支付金额信息
    amount = Column(Integer, nullable=False, comment="支付金额（单位：分）")
    currency = Column(String(3), default="CNY", comment="货币类型，默认人民币")

    # 支付渠道信息
    provider = Column(String(50), default="wechat", comment="支付渠道：wechat/alipay等")
    provider_payment_id = Column(String(255), unique=True, comment="支付渠道返回的支付ID")
    provider_order_id = Column(String(255), unique=True, index=True, comment="支付渠道的订单ID")
    
    # 订阅信息
    subscription_tier = Column(String(20), nullable=True, comment="购买的订阅等级")
    subscription_duration_days = Column(Integer, default=30, comment="订阅时长（天）")

    # 状态
    status = Column(String(50), default="pending", comment="支付状态：pending/success/failed/refunded")

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment="支付创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="最后更新时间")

    def __repr__(self):
        return f"<Payment(id={self.id}, user_id={self.user_id}, amount={self.amount}, status={self.status})>"


class Bot(Base):
    """
    机器人模型 - 存储机器人配置
    Bot model for storing bot configurations
    
    并发控制说明：
    - 使用version字段实现乐观锁，防止配置并发更新冲突
    - uuid字段用于外部API引用，避免暴露内部ID
    """
    __tablename__ = "bots"

    # 主键和标识符
    id = Column(Integer, primary_key=True, index=True, comment="内部自增主键")
    uuid = Column(String(36), unique=True, index=True, default=generate_uuid, nullable=False, comment="外部引用UUID，用于API和外部系统交互")
    bot_token = Column(String(255), unique=True, nullable=False, index=True, comment="Telegram Bot Token")
    bot_name = Column(String(255), nullable=False, comment="机器人显示名称")
    bot_username = Column(String(255), unique=True, nullable=False, index=True, comment="Telegram机器人用户名")
    
    # 机器人配置
    description = Column(Text, nullable=True, comment="机器人描述说明")
    personality = Column(Text, nullable=True, comment="机器人个性描述")
    system_prompt = Column(Text, nullable=True, comment="AI系统提示词")
    ai_model = Column(String(100), default="gpt-4", comment="使用的AI模型名称")
    ai_provider = Column(String(50), default="openai", comment="AI提供商：openai/anthropic/vllm")
    
    # 机器人设置（JSON存储）
    settings = Column(JSON, default={}, comment="其他配置项，如temperature、max_tokens等")
    
    # 状态和归属
    status = Column(String(20), default=BotStatus.ACTIVE.value, comment="机器人状态：active/inactive/maintenance")
    is_public = Column(Boolean, default=True, comment="是否可被其他用户添加到频道")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, comment="创建者用户ID")
    
    # 并发控制
    version = Column(Integer, default=1, nullable=False, comment="乐观锁版本号，用于并发控制")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="最后更新时间")
    
    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    channel_mappings = relationship("ChannelBotMapping", back_populates="bot", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Bot(id={self.id}, uuid={self.uuid}, username=@{self.bot_username}, name={self.bot_name})>"


class Channel(Base):
    """
    频道模型 - 存储频道/群聊信息
    Channel model for storing channel/chat information
    
    并发控制说明：
    - 使用version字段实现乐观锁，防止频道配置并发更新冲突
    """
    __tablename__ = "channels"

    # 主键和标识符
    id = Column(Integer, primary_key=True, index=True, comment="内部自增主键")
    telegram_chat_id = Column(BigInteger, unique=True, index=True, nullable=False, comment="Telegram聊天ID")
    chat_type = Column(String(50), nullable=False, comment="聊天类型：private/group/supergroup/channel")
    title = Column(String(255), nullable=True, comment="频道/群组标题")
    username = Column(String(255), nullable=True, comment="频道/群组用户名")
    
    # 归属信息
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="频道所有者用户ID")
    
    # 频道设置
    settings = Column(JSON, default={}, comment="频道配置，如路由模式、通知设置等")
    
    # 订阅信息（频道级别订阅）
    subscription_tier = Column(String(20), default=SubscriptionTier.FREE.value, comment="频道订阅等级")
    subscription_start_date = Column(DateTime, nullable=True, comment="订阅开始日期")
    subscription_end_date = Column(DateTime, nullable=True, comment="订阅结束日期")
    is_active = Column(Boolean, default=True, comment="频道是否激活")
    
    # 并发控制
    version = Column(Integer, default=1, nullable=False, comment="乐观锁版本号，用于并发控制")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="最后更新时间")
    
    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    bot_mappings = relationship("ChannelBotMapping", back_populates="channel", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Channel(id={self.id}, chat_id={self.telegram_chat_id}, type={self.chat_type})>"


class ChannelBotMapping(Base):
    """
    频道机器人映射表 - 存储频道与机器人的关联关系
    Mapping table for channel-bot relationships
    
    并发控制说明：
    - 使用复合唯一索引防止重复映射
    - 支持按优先级排序的机器人选择
    """
    __tablename__ = "channel_bot_mappings"

    # 主键和关联
    id = Column(Integer, primary_key=True, index=True, comment="内部自增主键")
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联的频道ID")
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联的机器人ID")
    
    # 映射配置
    is_active = Column(Boolean, default=True, comment="映射是否激活")
    priority = Column(Integer, default=0, comment="机器人响应优先级，数字越大优先级越高")
    routing_mode = Column(String(50), default="mention", comment="路由模式：mention（需@）/auto（自动回复）/keyword（关键词触发）")
    keywords = Column(JSON, default=[], comment="关键词列表，用于keyword模式触发")
    
    # 特定映射配置
    settings = Column(JSON, default={}, comment="此映射的特定配置")
    
    # 时间戳
    added_at = Column(DateTime, default=datetime.utcnow, comment="添加时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="最后更新时间")
    
    # Relationships
    channel = relationship("Channel", back_populates="bot_mappings")
    bot = relationship("Bot", back_populates="channel_mappings")
    
    # 复合唯一约束和索引：防止同一频道重复添加同一机器人
    __table_args__ = (
        UniqueConstraint('channel_id', 'bot_id', name='uq_channel_bot'),
        Index('idx_channel_active_priority', 'channel_id', 'is_active', 'priority'),
    )
    
    def __repr__(self):
        return f"<ChannelBotMapping(id={self.id}, channel_id={self.channel_id}, bot_id={self.bot_id})>"