"""
Channel Manager Service - 频道管理服务

负责管理频道和机器人的映射关系
"""
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from loguru import logger

from src.models.database import Channel, Bot, ChannelBotMapping, SubscriptionTier


class ChannelManagerService:
    """频道管理服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_or_create_channel(
        self,
        telegram_chat_id: int,
        chat_type: str,
        title: Optional[str] = None,
        username: Optional[str] = None,
        owner_id: Optional[int] = None
    ) -> Channel:
        """
        获取或创建频道
        
        Args:
            telegram_chat_id: Telegram聊天ID
            chat_type: 聊天类型（private, group, supergroup, channel）
            title: 频道标题
            username: 频道用户名
            owner_id: 所有者ID
            
        Returns:
            Channel: 频道对象
        """
        channel = self.db.query(Channel).filter(
            Channel.telegram_chat_id == telegram_chat_id
        ).first()
        
        if channel:
            # 更新频道信息
            if title:
                channel.title = title
            if username:
                channel.username = username
            if owner_id and not channel.owner_id:
                channel.owner_id = owner_id
            self.db.commit()
            self.db.refresh(channel)
        else:
            # 创建新频道
            channel = Channel(
                telegram_chat_id=telegram_chat_id,
                chat_type=chat_type,
                title=title,
                username=username,
                owner_id=owner_id,
                subscription_tier=SubscriptionTier.FREE.value,
                is_active=True,
                settings={}
            )
            self.db.add(channel)
            self.db.commit()
            self.db.refresh(channel)
            logger.info(f"Created channel: {telegram_chat_id} ({chat_type})")
        
        return channel
    
    def get_channel_by_chat_id(self, telegram_chat_id: int) -> Optional[Channel]:
        """根据Telegram Chat ID获取频道"""
        return self.db.query(Channel).filter(
            Channel.telegram_chat_id == telegram_chat_id
        ).first()
    
    def add_bot_to_channel(
        self,
        channel_id: int,
        bot_id: int,
        is_active: bool = True,
        priority: int = 0,
        routing_mode: str = "mention",
        keywords: Optional[List[str]] = None,
        settings: Optional[Dict[str, Any]] = None
    ) -> ChannelBotMapping:
        """
        将机器人添加到频道
        
        Args:
            channel_id: 频道ID
            bot_id: 机器人ID
            is_active: 是否激活
            priority: 优先级
            routing_mode: 路由模式（mention/auto/keyword）
            keywords: 关键词列表
            settings: 特定配置
            
        Returns:
            ChannelBotMapping: 映射对象
        """
        # 检查映射是否已存在
        existing = self.db.query(ChannelBotMapping).filter(
            ChannelBotMapping.channel_id == channel_id,
            ChannelBotMapping.bot_id == bot_id
        ).first()
        
        if existing:
            # 更新现有映射
            existing.is_active = is_active
            existing.priority = priority
            existing.routing_mode = routing_mode
            existing.keywords = keywords or []
            existing.settings = settings or {}
            self.db.commit()
            self.db.refresh(existing)
            logger.info(f"Updated bot mapping: channel={channel_id}, bot={bot_id}")
            return existing
        
        # 创建新映射
        mapping = ChannelBotMapping(
            channel_id=channel_id,
            bot_id=bot_id,
            is_active=is_active,
            priority=priority,
            routing_mode=routing_mode,
            keywords=keywords or [],
            settings=settings or {}
        )
        
        self.db.add(mapping)
        self.db.commit()
        self.db.refresh(mapping)
        logger.info(f"Added bot to channel: channel={channel_id}, bot={bot_id}")
        return mapping
    
    def remove_bot_from_channel(self, channel_id: int, bot_id: int) -> bool:
        """
        从频道移除机器人
        
        Args:
            channel_id: 频道ID
            bot_id: 机器人ID
            
        Returns:
            bool: 是否成功移除
        """
        mapping = self.db.query(ChannelBotMapping).filter(
            ChannelBotMapping.channel_id == channel_id,
            ChannelBotMapping.bot_id == bot_id
        ).first()
        
        if not mapping:
            return False
        
        self.db.delete(mapping)
        self.db.commit()
        logger.info(f"Removed bot from channel: channel={channel_id}, bot={bot_id}")
        return True
    
    def get_channel_bots(self, channel_id: int, active_only: bool = True) -> List[ChannelBotMapping]:
        """
        获取频道中的所有机器人
        
        Args:
            channel_id: 频道ID
            active_only: 是否只返回激活的机器人
            
        Returns:
            List[ChannelBotMapping]: 映射列表
        """
        query = self.db.query(ChannelBotMapping).filter(
            ChannelBotMapping.channel_id == channel_id
        )
        
        if active_only:
            query = query.filter(ChannelBotMapping.is_active == True)
        
        # 按优先级排序
        return query.order_by(ChannelBotMapping.priority.desc()).all()
    
    def get_bot_channels(self, bot_id: int) -> List[ChannelBotMapping]:
        """获取某个机器人所在的所有频道"""
        return self.db.query(ChannelBotMapping).filter(
            ChannelBotMapping.bot_id == bot_id,
            ChannelBotMapping.is_active == True
        ).all()
    
    def update_mapping_settings(
        self,
        channel_id: int,
        bot_id: int,
        **kwargs
    ) -> Optional[ChannelBotMapping]:
        """
        更新频道-机器人映射配置
        
        Args:
            channel_id: 频道ID
            bot_id: 机器人ID
            **kwargs: 要更新的字段
            
        Returns:
            ChannelBotMapping: 更新后的映射对象
        """
        mapping = self.db.query(ChannelBotMapping).filter(
            ChannelBotMapping.channel_id == channel_id,
            ChannelBotMapping.bot_id == bot_id
        ).first()
        
        if not mapping:
            return None
        
        # 更新允许的字段
        allowed_fields = ['is_active', 'priority', 'routing_mode', 'keywords', 'settings']
        
        for key, value in kwargs.items():
            if key in allowed_fields and value is not None:
                setattr(mapping, key, value)
        
        self.db.commit()
        self.db.refresh(mapping)
        logger.info(f"Updated mapping: channel={channel_id}, bot={bot_id}")
        return mapping
    
    def check_bot_in_channel(self, channel_id: int, bot_id: int) -> bool:
        """检查机器人是否在频道中"""
        mapping = self.db.query(ChannelBotMapping).filter(
            ChannelBotMapping.channel_id == channel_id,
            ChannelBotMapping.bot_id == bot_id,
            ChannelBotMapping.is_active == True
        ).first()
        
        return mapping is not None
