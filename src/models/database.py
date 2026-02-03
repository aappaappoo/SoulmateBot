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
    
    # 语音配置
    voice_enabled = Column(Boolean, default=False, comment="是否启用语音回复功能")
    voice_id = Column(String(100), nullable=True, comment="语音音色ID，如OpenAI TTS的voice参数：alloy, echo, fable, onyx, nova, shimmer")
    
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
    owner_id = Column(BigInteger, ForeignKey("users.id"), nullable=True, comment="频道所有者用户ID")
    
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


class ReactionType(str, enum.Enum):
    """
    Telegram Reactions 类型枚举
    Telegram reaction type enumeration
    
    包含Telegram支持的主要表情反应类型
    """
    # 正面反应
    THUMBS_UP = "👍"           # 赞
    HEART = "❤️"               # 爱心
    FIRE = "🔥"                # 火
    CLAP = "👏"                # 鼓掌
    PARTY = "🎉"               # 庆祝
    STAR_STRUCK = "🤩"         # 惊艳
    EYES = "👀"                # 关注
    OK = "👌"                  # OK
    HUNDRED = "💯"             # 100分
    
    # 负面反应
    THUMBS_DOWN = "👎"         # 踩
    POOP = "💩"                # 差评
    VOMIT = "🤮"               # 恶心
    
    # 情感反应
    CRYING = "😢"              # 哭泣
    THINKING = "🤔"            # 思考
    SHOCK = "😱"               # 震惊
    ANGRY = "😡"               # 生气
    SAD = "😔"                 # 悲伤
    LAUGH = "😂"               # 大笑
    
    # 自定义/其他
    CUSTOM = "custom"          # 自定义表情


class InteractionType(str, enum.Enum):
    """
    用户交互行为类型枚举
    User interaction type enumeration
    
    记录用户对机器人消息的各类操作
    """
    # 消息操作
    COPY = "copy"              # 复制消息内容
    COPY_LINK = "copy_link"    # 复制消息链接
    REPLY = "reply"            # 回复消息
    FORWARD = "forward"        # 转发消息
    
    # 管理操作
    PIN = "pin"                # 置顶消息
    UNPIN = "unpin"            # 取消置顶
    REPORT = "report"          # 举报消息
    DELETE = "delete"          # 删除消息
    
    # 互动操作
    QUOTE = "quote"            # 引用消息
    EDIT = "edit"              # 编辑（仅用于用户消息）
    SELECT = "select"          # 选择消息（多选）
    TRANSLATE = "translate"    # 翻译消息
    
    # 分析类型
    SHARE = "share"            # 分享
    SAVE = "save"              # 保存/收藏


class MessageReaction(Base):
    """
    消息反应模型 - 存储用户对消息的Reaction记录
    Message reaction model for storing user reactions to messages
    
    设计说明：
    - 支持Telegram的emoji反应功能
    - 记录用户对机器人回复的表情评价
    - 支持商业分析和用户满意度统计
    
    并发控制说明：
    - 使用复合唯一约束防止重复反应
    - 支持反应更新和取消
    """
    __tablename__ = "message_reactions"

    # 主键和标识符
    id = Column(Integer, primary_key=True, index=True, comment="内部自增主键")
    uuid = Column(String(36), unique=True, index=True, default=generate_uuid, nullable=False, comment="外部引用UUID")
    
    # 关联关系
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="反应用户ID")
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True, comment="关联的对话记录ID")
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="SET NULL"), nullable=True, index=True, comment="被反应的机器人ID")
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="SET NULL"), nullable=True, index=True, comment="发生反应的频道ID")
    
    # Telegram消息标识
    message_id = Column(BigInteger, nullable=False, index=True, comment="Telegram消息ID")
    chat_id = Column(BigInteger, nullable=False, index=True, comment="Telegram聊天ID")
    
    # 反应信息
    reaction_type = Column(String(50), nullable=False, comment="反应类型：emoji字符或custom")
    reaction_emoji = Column(String(50), nullable=False, comment="反应的emoji表情")
    custom_emoji_id = Column(String(255), nullable=True, comment="自定义emoji的ID（如果是自定义表情）")
    is_big = Column(Boolean, default=False, comment="是否为大型动画表情")
    
    # 反应状态
    is_active = Column(Boolean, default=True, comment="反应是否有效（取消后为False）")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, index=True, comment="反应时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间（如更改反应）")
    removed_at = Column(DateTime, nullable=True, comment="取消反应的时间")
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    conversation = relationship("Conversation", foreign_keys=[conversation_id])
    bot = relationship("Bot", foreign_keys=[bot_id])
    channel = relationship("Channel", foreign_keys=[channel_id])
    
    # 索引和约束
    __table_args__ = (
        # 复合索引：优化按消息查询反应
        Index('idx_message_reaction_lookup', 'chat_id', 'message_id'),
        # 复合索引：优化用户反应历史查询
        Index('idx_user_reactions', 'user_id', 'created_at'),
        # 复合索引：优化机器人反应统计
        Index('idx_bot_reactions', 'bot_id', 'reaction_type', 'is_active'),
        # 唯一约束说明：包含is_active是有意设计，允许保留历史反应记录（is_active=False）
        # 同时确保每个用户对每条消息只有一个活跃反应（is_active=True）
        # 应用层通过FeedbackService确保更新反应时先将旧反应设为inactive
        UniqueConstraint('user_id', 'message_id', 'chat_id', 'is_active', name='uq_user_message_active_reaction'),
    )
    
    def __repr__(self):
        return f"<MessageReaction(id={self.id}, user_id={self.user_id}, emoji={self.reaction_emoji}, active={self.is_active})>"


class MessageInteraction(Base):
    """
    消息交互模型 - 存储用户对消息的操作行为
    Message interaction model for storing user actions on messages
    
    设计说明：
    - 记录复制、回复、pin、举报、复制链接等操作
    - 用于商业分析：理解用户行为模式
    - 支持高频操作的批量统计
    
    并发控制说明：
    - 使用复合索引优化查询性能
    - 支持批量插入和统计查询
    """
    __tablename__ = "message_interactions"

    # 主键和标识符
    id = Column(Integer, primary_key=True, index=True, comment="内部自增主键")
    uuid = Column(String(36), unique=True, index=True, default=generate_uuid, nullable=False, comment="外部引用UUID")
    
    # 关联关系
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="操作用户ID")
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True, comment="关联的对话记录ID")
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="SET NULL"), nullable=True, index=True, comment="被操作的机器人消息所属机器人ID")
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="SET NULL"), nullable=True, index=True, comment="发生操作的频道ID")
    
    # Telegram消息标识
    message_id = Column(BigInteger, nullable=False, index=True, comment="Telegram消息ID")
    chat_id = Column(BigInteger, nullable=False, index=True, comment="Telegram聊天ID")
    
    # 交互信息
    interaction_type = Column(String(50), nullable=False, comment="交互类型：copy/reply/pin/report/copy_link等")
    
    # 扩展元数据（JSON格式存储额外信息）
    extra_data = Column(JSON, default={}, comment="交互的额外元数据，如：reply_to_message_id, forward_to_chat_id等")
    
    # 交互结果
    is_successful = Column(Boolean, default=True, comment="操作是否成功")
    error_message = Column(Text, nullable=True, comment="如果操作失败，记录错误信息")
    
    # 来源信息
    source_platform = Column(String(50), default="telegram", comment="来源平台：telegram/web/api等")
    client_info = Column(JSON, default={}, comment="客户端信息，如版本、设备类型等")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, index=True, comment="操作时间")
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    conversation = relationship("Conversation", foreign_keys=[conversation_id])
    bot = relationship("Bot", foreign_keys=[bot_id])
    channel = relationship("Channel", foreign_keys=[channel_id])
    
    # 索引和约束
    __table_args__ = (
        # 复合索引：优化按消息查询交互记录
        Index('idx_message_interaction_lookup', 'chat_id', 'message_id'),
        # 复合索引：优化用户交互历史查询
        Index('idx_user_interactions', 'user_id', 'interaction_type', 'created_at'),
        # 复合索引：优化机器人交互统计
        Index('idx_bot_interactions', 'bot_id', 'interaction_type'),
        # 复合索引：优化按时间段统计
        Index('idx_interaction_analytics', 'interaction_type', 'created_at', 'is_successful'),
    )
    
    def __repr__(self):
        return f"<MessageInteraction(id={self.id}, user_id={self.user_id}, type={self.interaction_type})>"


class FeedbackSummary(Base):
    """
    反馈汇总模型 - 按时间段汇总用户反馈统计
    Feedback summary model for aggregated feedback statistics
    
    设计说明：
    - 定期（每小时/每天）汇总反应和交互数据
    - 用于快速获取统计数据，避免实时聚合查询
    - 支持商业报表和数据分析
    
    并发控制说明：
    - 使用唯一约束确保同一统计周期不重复
    - 使用version字段支持并发更新
    """
    __tablename__ = "feedback_summaries"

    # 主键和标识符
    id = Column(Integer, primary_key=True, index=True, comment="内部自增主键")
    
    # 统计维度
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=True, index=True, comment="统计的机器人ID，NULL表示全局统计")
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=True, index=True, comment="统计的频道ID，NULL表示所有频道")
    period_type = Column(String(20), nullable=False, comment="统计周期类型：hourly/daily/weekly/monthly")
    period_start = Column(DateTime, nullable=False, index=True, comment="统计周期开始时间")
    period_end = Column(DateTime, nullable=False, comment="统计周期结束时间")
    
    # 反应统计
    total_reactions = Column(Integer, default=0, comment="总反应数")
    positive_reactions = Column(Integer, default=0, comment="正面反应数（👍❤️🔥👏🎉等）")
    negative_reactions = Column(Integer, default=0, comment="负面反应数（👎💩🤮等）")
    neutral_reactions = Column(Integer, default=0, comment="中性反应数（🤔👀等）")
    reaction_breakdown = Column(JSON, default={}, comment="各类反应的详细数量，如：{'👍': 100, '❤️': 50}")
    
    # 交互统计
    total_interactions = Column(Integer, default=0, comment="总交互数")
    copy_count = Column(Integer, default=0, comment="复制次数")
    reply_count = Column(Integer, default=0, comment="回复次数")
    forward_count = Column(Integer, default=0, comment="转发次数")
    pin_count = Column(Integer, default=0, comment="置顶次数")
    report_count = Column(Integer, default=0, comment="举报次数")
    interaction_breakdown = Column(JSON, default={}, comment="各类交互的详细数量")
    
    # 计算指标
    satisfaction_score = Column(Integer, nullable=True, comment="满意度分数（0-100），基于正负反应比例计算")
    engagement_score = Column(Integer, nullable=True, comment="参与度分数（0-100），基于交互频率计算")
    
    # 并发控制
    version = Column(Integer, default=1, nullable=False, comment="乐观锁版本号")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment="记录创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="最后更新时间")
    
    # Relationships
    bot = relationship("Bot", foreign_keys=[bot_id])
    channel = relationship("Channel", foreign_keys=[channel_id])
    
    # 索引和约束
    __table_args__ = (
        # 唯一约束：确保同一维度同一周期不重复
        UniqueConstraint('bot_id', 'channel_id', 'period_type', 'period_start', name='uq_feedback_summary_period'),
        # 复合索引：优化按周期查询
        Index('idx_summary_period', 'period_type', 'period_start'),
        # 复合索引：优化按机器人查询
        Index('idx_summary_bot', 'bot_id', 'period_type', 'period_start'),
    )
    
    def __repr__(self):
        return f"<FeedbackSummary(id={self.id}, bot_id={self.bot_id}, period={self.period_type}, start={self.period_start})>"


class MemoryImportance(str, enum.Enum):
    """
    记忆重要性级别枚举
    Memory importance level enumeration
    """
    LOW = "low"          # 低重要性（日常寒暄等，通常不记录）
    MEDIUM = "medium"    # 中等重要性（一般事件）
    HIGH = "high"        # 高重要性（重要事件，如生日、重要决定等）
    CRITICAL = "critical"  # 关键重要性（非常重要的事件）


class UserMemory(Base):
    """
    用户长期记忆模型 - 存储用户与Bot的重要对话事件
    User long-term memory model for storing important conversation events
    
    设计说明：
    - 使用RAG技术存储和检索重要对话事件
    - 只记录重要事件，过滤日常寒暄
    - 支持按用户和Bot检索相关记忆
    - 用于提供个性化的对话体验
    
    并发控制说明：
    - 使用复合索引优化按用户和Bot查询的性能
    """
    __tablename__ = "user_memories"

    # 主键和标识符
    id = Column(Integer, primary_key=True, index=True, comment="内部自增主键")
    uuid = Column(String(36), unique=True, index=True, default=generate_uuid, nullable=False, comment="外部引用UUID")
    
    # 关联关系
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联的用户ID")
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="SET NULL"), nullable=True, index=True, comment="关联的机器人ID")
    
    # 记忆内容
    event_summary = Column(Text, nullable=False, comment="事件摘要，用于快速检索")
    user_message = Column(Text, nullable=True, comment="用户原始消息")
    bot_response = Column(Text, nullable=True, comment="机器人回复")
    
    # 记忆分类和重要性
    importance = Column(String(20), default=MemoryImportance.MEDIUM.value, comment="重要性级别：low/medium/high/critical")
    event_type = Column(String(50), nullable=True, comment="事件类型：birthday, preference, goal, emotion, life_event等")
    keywords = Column(JSON, default=[], comment="关键词列表，用于检索匹配")
    
    # 向量嵌入（用于RAG检索）
    embedding = Column(JSON, nullable=True, comment="事件摘要的向量嵌入，用于语义相似度检索")
    embedding_model = Column(String(50), nullable=True, comment="生成嵌入向量使用的模型名称")
    
    # 时间信息
    event_date = Column(DateTime, nullable=True, comment="事件发生的日期（如果提及）")
    created_at = Column(DateTime, default=datetime.utcnow, index=True, comment="记忆创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="最后更新时间")
    
    # 记忆状态
    is_active = Column(Boolean, default=True, comment="记忆是否有效")
    access_count = Column(Integer, default=0, comment="记忆被访问次数，用于优化检索")
    last_accessed_at = Column(DateTime, nullable=True, comment="最后访问时间")
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    bot = relationship("Bot", foreign_keys=[bot_id])
    
    # 索引和约束
    __table_args__ = (
        # 复合索引：优化按用户和Bot查询记忆
        Index('idx_user_bot_memory', 'user_id', 'bot_id', 'is_active'),
        # 复合索引：优化按重要性查询
        Index('idx_memory_importance', 'user_id', 'importance', 'created_at'),
        # 复合索引：优化按事件类型查询
        Index('idx_memory_event_type', 'user_id', 'event_type', 'is_active'),
    )
    
    def __repr__(self):
        return f"<UserMemory(id={self.id}, user_id={self.user_id}, importance={self.importance}, summary={self.event_summary[:50]}...)>"


class ReminderStatus(str, enum.Enum):
    """
    提醒状态枚举
    Reminder status enumeration
    """
    PENDING = "pending"      # 待发送
    SENT = "sent"            # 已发送
    FAILED = "failed"        # 发送失败
    CANCELLED = "cancelled"  # 已取消


class Reminder(Base):
    """
    提醒模型 - 存储用户设置的定时提醒
    Reminder model for storing user scheduled reminders
    
    设计说明：
    - 支持用户设置定时提醒，如"1小时后提醒我做某事"
    - Bot 会在指定时间主动发送提醒消息给用户
    - 支持按用户和 Bot 管理提醒
    
    并发控制说明：
    - 使用复合索引优化按状态和时间查询待发送提醒
    """
    __tablename__ = "reminders"

    # 主键和标识符
    id = Column(Integer, primary_key=True, index=True, comment="内部自增主键")
    uuid = Column(String(36), unique=True, index=True, default=generate_uuid, nullable=False, comment="外部引用UUID")
    
    # 关联关系
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联的用户ID")
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="SET NULL"), nullable=True, index=True, comment="关联的机器人ID")
    
    # Telegram 信息
    telegram_user_id = Column(BigInteger, nullable=False, index=True, comment="Telegram 用户 ID，用于发送提醒")
    chat_id = Column(BigInteger, nullable=False, comment="Telegram 聊天 ID，用于发送提醒")
    
    # 提醒内容
    reminder_text = Column(Text, nullable=False, comment="提醒内容")
    original_message = Column(Text, nullable=True, comment="用户设置提醒时的原始消息")
    
    # 时间信息
    remind_at = Column(DateTime, nullable=False, index=True, comment="提醒触发时间")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    sent_at = Column(DateTime, nullable=True, comment="实际发送时间")
    
    # 状态
    status = Column(String(20), default=ReminderStatus.PENDING.value, index=True, comment="提醒状态：pending/sent/failed/cancelled")
    retry_count = Column(Integer, default=0, comment="重试次数")
    error_message = Column(Text, nullable=True, comment="发送失败时的错误信息")
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    bot = relationship("Bot", foreign_keys=[bot_id])
    
    # 索引和约束
    __table_args__ = (
        # 复合索引：优化查询待发送的提醒
        Index('idx_reminder_pending', 'status', 'remind_at'),
        # 复合索引：优化按用户查询提醒
        Index('idx_reminder_user', 'user_id', 'status', 'remind_at'),
    )
    
    def __repr__(self):
        return f"<Reminder(id={self.id}, user_id={self.user_id}, remind_at={self.remind_at}, status={self.status})>"