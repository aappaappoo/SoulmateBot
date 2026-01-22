"""
Async Channel Manager Service - 异步频道管理服务
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
from loguru import logger

from src.models.database import Channel, Bot, ChannelBotMapping, SubscriptionTier


class AsyncChannelManagerService:
    """异步频道管理服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_channel(
            self,
            telegram_chat_id: int,
            chat_type: str,
            title: Optional[str] = None,
            username: Optional[str] = None,
            owner_id: Optional[int] = None
    ) -> Channel:
        """
        获取或创建频道（异步版本）
        """
        # 查询现有频道
        result = await self.db.execute(
            select(Channel).where(Channel.telegram_chat_id == telegram_chat_id)
        )
        channel = result.scalar_one_or_none()

        if channel:
            # 更新频道信息
            if title:
                channel.title = title
            if username:
                channel.username = username
            if owner_id and not channel.owner_id:
                channel.owner_id = owner_id
            await self.db.commit()
            await self.db.refresh(channel)
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
            await self.db.commit()
            await self.db.refresh(channel)
            logger.info(f"Created channel: {telegram_chat_id} ({chat_type})")

        return channel

    async def get_channel_by_chat_id(self, telegram_chat_id: int) -> Optional[Channel]:
        """根据Telegram Chat ID获取频道"""
        result = await self.db.execute(
            select(Channel).where(Channel.telegram_chat_id == telegram_chat_id)
        )
        return result.scalar_one_or_none()

    async def get_channel_bots(
            self,
            channel_id: int,
            active_only: bool = True
    ) -> List[ChannelBotMapping]:
        """
        获取频道中的所有机器人（异步版本）
        """
        query = select(ChannelBotMapping).options(
            selectinload(ChannelBotMapping.bot)  # 预加载bot关系
        ).where(ChannelBotMapping.channel_id == channel_id)

        if active_only:
            query = query.where(ChannelBotMapping.is_active == True)

        query = query.order_by(ChannelBotMapping.priority.desc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def add_bot_to_channel(
            self,
            channel_id: int,
            bot_id: int,
            is_active: bool = True,
            priority: int = 0,
            routing_mode: str = "mention",
            keywords: Optional[List[str]] = None,
            settings: Optional[Dict[str, Any]] = None
    ) -> ChannelBotMapping:
        """将机器人添加到频道（异步版本）"""
        # 检查映射是否已存在
        result = await self.db.execute(
            select(ChannelBotMapping).where(
                ChannelBotMapping.channel_id == channel_id,
                ChannelBotMapping.bot_id == bot_id
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.is_active = is_active
            existing.priority = priority
            existing.routing_mode = routing_mode
            existing.keywords = keywords or []
            existing.settings = settings or {}
            await self.db.commit()
            await self.db.refresh(existing)
            logger.info(f"Updated bot mapping: channel={channel_id}, bot={bot_id}")
            return existing

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
        await self.db.commit()
        await self.db.refresh(mapping)
        logger.info(f"Added bot to channel: channel={channel_id}, bot={bot_id}")
        return mapping

    async def remove_bot_from_channel(self, channel_id: int, bot_id: int) -> bool:
        """从频道移除机器人"""
        result = await self.db.execute(
            select(ChannelBotMapping).where(
                ChannelBotMapping.channel_id == channel_id,
                ChannelBotMapping.bot_id == bot_id
            )
        )
        mapping = result.scalar_one_or_none()

        if not mapping:
            return False

        await self.db.delete(mapping)
        await self.db.commit()
        logger.info(f"Removed bot from channel: channel={channel_id}, bot={bot_id}")
        return True