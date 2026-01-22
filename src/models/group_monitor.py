"""
Database models for Group Monitoring feature

群组监控数据库模型 - 存储群组消息和话题总结

设计说明：
1. GroupMonitorConfig: 监控配置表，存储用户设置的监控参数
2. GroupMessage: 群组消息表，存储监控的群组消息
3. TopicSummary: 话题总结表，存储分析后的话题信息
"""
from sqlalchemy import (
    Column, Integer, BigInteger, String, DateTime, Boolean,
    ForeignKey, Text, JSON, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from src.models.database import Base


def generate_uuid() -> str:
    """生成UUID字符串"""
    return str(uuid.uuid4())


class GroupMonitorConfig(Base):
    """
    群组监控配置模型
    
    存储用户设置的群组监控参数，如目标群组、监控时间范围等。
    
    并发控制说明：
    - 使用version字段实现乐观锁
    """
    __tablename__ = "group_monitor_configs"
    
    # 主键和标识符
    id = Column(Integer, primary_key=True, index=True, comment="内部自增主键")
    uuid = Column(String(36), unique=True, index=True, default=generate_uuid, nullable=False, comment="外部引用UUID")
    
    # 用户关联
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="创建监控的用户ID")
    
    # 群组信息
    group_link = Column(String(255), nullable=False, comment="Telegram群组链接")
    group_chat_id = Column(BigInteger, nullable=True, index=True, comment="群组的Telegram Chat ID")
    group_title = Column(String(255), nullable=True, comment="群组标题")
    group_username = Column(String(255), nullable=True, comment="群组用户名")
    
    # 监控配置
    start_time = Column(DateTime, nullable=True, comment="监控开始时间")
    end_time = Column(DateTime, nullable=True, comment="监控结束时间")
    is_active = Column(Boolean, default=True, comment="是否正在监控")
    
    # 监控设置
    keywords = Column(JSON, default=[], comment="关注的关键词列表")
    min_message_length = Column(Integer, default=5, comment="最小消息长度（过滤短消息）")
    include_media = Column(Boolean, default=False, comment="是否包含媒体消息")
    
    # 并发控制
    version = Column(Integer, default=1, nullable=False, comment="乐观锁版本号")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    messages = relationship("GroupMessage", back_populates="config", cascade="all, delete-orphan")
    summaries = relationship("TopicSummary", back_populates="config", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_monitor_user_active', 'user_id', 'is_active'),
        Index('idx_monitor_group', 'group_chat_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<GroupMonitorConfig(id={self.id}, group={self.group_link}, active={self.is_active})>"


class GroupMessage(Base):
    """
    群组消息模型
    
    存储从监控群组收集的消息内容。
    
    设计说明：
    - 消息内容使用Text类型支持长文本
    - 记录发送者信息用于分析活跃用户
    """
    __tablename__ = "group_messages"
    
    # 主键和标识符
    id = Column(Integer, primary_key=True, index=True, comment="内部自增主键")
    
    # 关联监控配置
    config_id = Column(Integer, ForeignKey("group_monitor_configs.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联的监控配置ID")
    
    # Telegram消息信息
    message_id = Column(BigInteger, nullable=False, comment="Telegram消息ID")
    chat_id = Column(BigInteger, nullable=False, index=True, comment="群组Chat ID")
    
    # 发送者信息
    sender_id = Column(BigInteger, nullable=True, comment="发送者的Telegram用户ID")
    sender_username = Column(String(255), nullable=True, comment="发送者用户名")
    sender_name = Column(String(255), nullable=True, comment="发送者显示名称")
    
    # 消息内容
    content = Column(Text, nullable=True, comment="消息文本内容")
    message_type = Column(String(50), default="text", comment="消息类型：text/photo/video/document等")
    
    # 元数据
    reply_to_message_id = Column(BigInteger, nullable=True, comment="回复的消息ID")
    forward_from = Column(String(255), nullable=True, comment="转发来源")
    
    # 分析标记
    is_processed = Column(Boolean, default=False, comment="是否已处理分析")
    topic_id = Column(Integer, ForeignKey("topic_summaries.id", ondelete="SET NULL"), nullable=True, comment="归属的话题ID")
    
    # 时间戳
    message_date = Column(DateTime, nullable=False, index=True, comment="消息发送时间")
    collected_at = Column(DateTime, default=datetime.utcnow, comment="收集时间")
    
    # Relationships
    config = relationship("GroupMonitorConfig", back_populates="messages")
    topic = relationship("TopicSummary", back_populates="messages", foreign_keys=[topic_id])
    
    # 索引
    __table_args__ = (
        Index('idx_message_config_date', 'config_id', 'message_date'),
        Index('idx_message_chat_date', 'chat_id', 'message_date'),
        UniqueConstraint('config_id', 'message_id', 'chat_id', name='uq_config_message'),
    )
    
    def __repr__(self):
        return f"<GroupMessage(id={self.id}, chat_id={self.chat_id}, sender={self.sender_username})>"


class TopicSummary(Base):
    """
    话题总结模型
    
    存储对群组讨论的话题分析和总结。
    
    设计说明：
    - 话题由AI分析生成
    - 包含关键词、摘要、活跃用户等信息
    """
    __tablename__ = "topic_summaries"
    
    # 主键和标识符
    id = Column(Integer, primary_key=True, index=True, comment="内部自增主键")
    uuid = Column(String(36), unique=True, index=True, default=generate_uuid, nullable=False, comment="外部引用UUID")
    
    # 关联监控配置
    config_id = Column(Integer, ForeignKey("group_monitor_configs.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联的监控配置ID")
    
    # 话题信息
    topic_title = Column(String(255), nullable=False, comment="话题标题")
    topic_summary = Column(Text, nullable=True, comment="话题摘要")
    keywords = Column(JSON, default=[], comment="话题关键词列表")
    
    # 统计信息
    message_count = Column(Integer, default=0, comment="相关消息数量")
    participant_count = Column(Integer, default=0, comment="参与用户数量")
    active_participants = Column(JSON, default=[], comment="活跃参与者列表")
    
    # 时间范围
    start_time = Column(DateTime, nullable=True, comment="话题开始时间")
    end_time = Column(DateTime, nullable=True, comment="话题结束时间")
    
    # 分析结果
    sentiment = Column(String(50), nullable=True, comment="话题情感倾向：positive/negative/neutral")
    importance_score = Column(Integer, default=50, comment="话题重要性评分（0-100）")
    
    # AI分析元数据
    ai_analysis = Column(JSON, default={}, comment="AI分析的详细结果")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    
    # Relationships
    config = relationship("GroupMonitorConfig", back_populates="summaries")
    messages = relationship("GroupMessage", back_populates="topic", foreign_keys="GroupMessage.topic_id")
    
    # 索引
    __table_args__ = (
        Index('idx_topic_config_time', 'config_id', 'start_time'),
        Index('idx_topic_importance', 'config_id', 'importance_score'),
    )
    
    def __repr__(self):
        return f"<TopicSummary(id={self.id}, title={self.topic_title}, messages={self.message_count})>"
    
    def to_dict(self) -> dict:
        """转换为字典，用于API响应"""
        return {
            "id": self.uuid,
            "title": self.topic_title,
            "summary": self.topic_summary,
            "keywords": self.keywords,
            "message_count": self.message_count,
            "participant_count": self.participant_count,
            "active_participants": self.active_participants,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "sentiment": self.sentiment,
            "importance_score": self.importance_score,
        }
