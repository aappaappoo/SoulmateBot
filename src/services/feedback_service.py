"""
Feedback Service - 用户反馈管理服务

本模块提供用户反馈管理的核心功能：
1. Reaction（表情反应）管理
2. Interaction（交互行为）记录
3. 反馈统计和汇总
4. 满意度分析

设计原则：
- 高并发安全：使用事务和乐观锁
- 性能优化：使用批量操作和缓存
- 商业分析：提供丰富的统计接口
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from loguru import logger

from src.models.database import (
    MessageReaction,
    MessageInteraction,
    FeedbackSummary,
    ReactionType,
    InteractionType,
    User,
    Bot,
    Channel,
    Conversation
)


# 定义正面、负面、中性反应分类
POSITIVE_REACTIONS = {
    ReactionType.THUMBS_UP.value,
    ReactionType.HEART.value,
    ReactionType.FIRE.value,
    ReactionType.CLAP.value,
    ReactionType.PARTY.value,
    ReactionType.STAR_STRUCK.value,
    ReactionType.OK.value,
    ReactionType.HUNDRED.value,
    ReactionType.LAUGH.value,
}

NEGATIVE_REACTIONS = {
    ReactionType.THUMBS_DOWN.value,
    ReactionType.POOP.value,
    ReactionType.VOMIT.value,
    ReactionType.ANGRY.value,
}

NEUTRAL_REACTIONS = {
    ReactionType.EYES.value,
    ReactionType.THINKING.value,
    ReactionType.SHOCK.value,
    ReactionType.CRYING.value,
    ReactionType.SAD.value,
}


class FeedbackService:
    """
    反馈服务类
    
    提供完整的用户反馈管理功能：
    - 记录和管理用户对消息的reactions
    - 记录用户的各类交互行为
    - 生成反馈统计报告
    - 计算满意度和参与度指标
    """
    
    def __init__(self, db: Session):
        """
        初始化反馈服务
        
        Args:
            db: SQLAlchemy数据库会话
        """
        self.db = db
    
    # ==================== Reaction 管理 ====================
    
    def add_reaction(
        self,
        user_id: int,
        message_id: int,
        chat_id: int,
        reaction_emoji: str,
        conversation_id: Optional[int] = None,
        bot_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        custom_emoji_id: Optional[str] = None,
        is_big: bool = False
    ) -> MessageReaction:
        """
        添加或更新消息反应
        
        如果用户已对该消息有反应，则更新为新反应
        
        Args:
            user_id: 用户ID
            message_id: Telegram消息ID
            chat_id: Telegram聊天ID
            reaction_emoji: 反应表情
            conversation_id: 对话记录ID（可选）
            bot_id: 机器人ID（可选）
            channel_id: 频道ID（可选）
            custom_emoji_id: 自定义表情ID（可选）
            is_big: 是否为大型表情
            
        Returns:
            创建或更新的MessageReaction对象
        """
        try:
            # 查找用户对该消息的现有活跃反应
            existing_reaction = self.db.query(MessageReaction).filter(
                and_(
                    MessageReaction.user_id == user_id,
                    MessageReaction.message_id == message_id,
                    MessageReaction.chat_id == chat_id,
                    MessageReaction.is_active == True
                )
            ).first()
            
            if existing_reaction:
                # 如果是相同的反应，不做任何操作
                if existing_reaction.reaction_emoji == reaction_emoji:
                    logger.debug(f"User {user_id} already has same reaction on message {message_id}")
                    return existing_reaction
                
                # 取消旧反应
                existing_reaction.is_active = False
                existing_reaction.removed_at = datetime.utcnow()
                logger.info(f"Deactivated old reaction '{existing_reaction.reaction_emoji}' for user {user_id}")
            
            # 确定反应类型
            reaction_type = self._classify_reaction(reaction_emoji)
            
            # 创建新反应
            new_reaction = MessageReaction(
                user_id=user_id,
                message_id=message_id,
                chat_id=chat_id,
                reaction_emoji=reaction_emoji,
                reaction_type=reaction_type,
                conversation_id=conversation_id,
                bot_id=bot_id,
                channel_id=channel_id,
                custom_emoji_id=custom_emoji_id,
                is_big=is_big,
                is_active=True
            )
            
            self.db.add(new_reaction)
            self.db.commit()
            
            logger.info(f"Added reaction '{reaction_emoji}' by user {user_id} on message {message_id}")
            return new_reaction
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error adding reaction: {e}")
            raise
    
    def remove_reaction(
        self,
        user_id: int,
        message_id: int,
        chat_id: int,
        reaction_emoji: Optional[str] = None
    ) -> bool:
        """
        移除消息反应
        
        Args:
            user_id: 用户ID
            message_id: Telegram消息ID
            chat_id: Telegram聊天ID
            reaction_emoji: 要移除的特定反应表情（可选，不指定则移除所有）
            
        Returns:
            是否成功移除
        """
        try:
            query = self.db.query(MessageReaction).filter(
                and_(
                    MessageReaction.user_id == user_id,
                    MessageReaction.message_id == message_id,
                    MessageReaction.chat_id == chat_id,
                    MessageReaction.is_active == True
                )
            )
            
            if reaction_emoji:
                query = query.filter(MessageReaction.reaction_emoji == reaction_emoji)
            
            reactions = query.all()
            
            if not reactions:
                logger.debug(f"No active reaction found for user {user_id} on message {message_id}")
                return False
            
            for reaction in reactions:
                reaction.is_active = False
                reaction.removed_at = datetime.utcnow()
            
            self.db.commit()
            logger.info(f"Removed {len(reactions)} reaction(s) by user {user_id} on message {message_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error removing reaction: {e}")
            raise
    
    def get_message_reactions(
        self,
        message_id: int,
        chat_id: int,
        active_only: bool = True
    ) -> List[MessageReaction]:
        """
        获取消息的所有反应
        
        Args:
            message_id: Telegram消息ID
            chat_id: Telegram聊天ID
            active_only: 是否只返回活跃反应
            
        Returns:
            反应列表
        """
        query = self.db.query(MessageReaction).filter(
            and_(
                MessageReaction.message_id == message_id,
                MessageReaction.chat_id == chat_id
            )
        )
        
        if active_only:
            query = query.filter(MessageReaction.is_active == True)
        
        return query.order_by(MessageReaction.created_at.desc()).all()
    
    def get_reaction_summary(
        self,
        message_id: int,
        chat_id: int
    ) -> Dict[str, int]:
        """
        获取消息的反应统计摘要
        
        Args:
            message_id: Telegram消息ID
            chat_id: Telegram聊天ID
            
        Returns:
            {emoji: count} 格式的字典
        """
        results = self.db.query(
            MessageReaction.reaction_emoji,
            func.count(MessageReaction.id).label('count')
        ).filter(
            and_(
                MessageReaction.message_id == message_id,
                MessageReaction.chat_id == chat_id,
                MessageReaction.is_active == True
            )
        ).group_by(MessageReaction.reaction_emoji).all()
        
        return {row.reaction_emoji: row.count for row in results}
    
    def _classify_reaction(self, emoji: str) -> str:
        """
        分类反应为正面/负面/中性
        
        Args:
            emoji: 反应表情
            
        Returns:
            反应分类：positive/negative/neutral/custom
        """
        if emoji in POSITIVE_REACTIONS:
            return "positive"
        elif emoji in NEGATIVE_REACTIONS:
            return "negative"
        elif emoji in NEUTRAL_REACTIONS:
            return "neutral"
        else:
            return "custom"
    
    # ==================== Interaction 管理 ====================
    
    def record_interaction(
        self,
        user_id: int,
        message_id: int,
        chat_id: int,
        interaction_type: str,
        conversation_id: Optional[int] = None,
        bot_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source_platform: str = "telegram",
        client_info: Optional[Dict[str, Any]] = None
    ) -> MessageInteraction:
        """
        记录用户交互行为
        
        Args:
            user_id: 用户ID
            message_id: Telegram消息ID
            chat_id: Telegram聊天ID
            interaction_type: 交互类型
            conversation_id: 对话记录ID（可选）
            bot_id: 机器人ID（可选）
            channel_id: 频道ID（可选）
            metadata: 额外元数据
            source_platform: 来源平台
            client_info: 客户端信息
            
        Returns:
            创建的MessageInteraction对象
        """
        try:
            interaction = MessageInteraction(
                user_id=user_id,
                message_id=message_id,
                chat_id=chat_id,
                interaction_type=interaction_type,
                conversation_id=conversation_id,
                bot_id=bot_id,
                channel_id=channel_id,
                extra_data=metadata or {},
                source_platform=source_platform,
                client_info=client_info or {},
                is_successful=True
            )
            
            self.db.add(interaction)
            self.db.commit()
            
            logger.info(f"Recorded interaction '{interaction_type}' by user {user_id} on message {message_id}")
            return interaction
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error recording interaction: {e}")
            raise
    
    def record_copy(
        self,
        user_id: int,
        message_id: int,
        chat_id: int,
        **kwargs
    ) -> MessageInteraction:
        """记录复制消息行为"""
        return self.record_interaction(
            user_id=user_id,
            message_id=message_id,
            chat_id=chat_id,
            interaction_type=InteractionType.COPY.value,
            **kwargs
        )
    
    def record_copy_link(
        self,
        user_id: int,
        message_id: int,
        chat_id: int,
        **kwargs
    ) -> MessageInteraction:
        """记录复制消息链接行为"""
        return self.record_interaction(
            user_id=user_id,
            message_id=message_id,
            chat_id=chat_id,
            interaction_type=InteractionType.COPY_LINK.value,
            **kwargs
        )
    
    def record_reply(
        self,
        user_id: int,
        message_id: int,
        chat_id: int,
        reply_message_id: Optional[int] = None,
        **kwargs
    ) -> MessageInteraction:
        """记录回复消息行为"""
        metadata = kwargs.get('metadata', {})
        if reply_message_id:
            metadata['reply_message_id'] = reply_message_id
        kwargs['metadata'] = metadata
        
        return self.record_interaction(
            user_id=user_id,
            message_id=message_id,
            chat_id=chat_id,
            interaction_type=InteractionType.REPLY.value,
            **kwargs
        )
    
    def record_forward(
        self,
        user_id: int,
        message_id: int,
        chat_id: int,
        forward_to_chat_id: Optional[int] = None,
        **kwargs
    ) -> MessageInteraction:
        """记录转发消息行为"""
        metadata = kwargs.get('metadata', {})
        if forward_to_chat_id:
            metadata['forward_to_chat_id'] = forward_to_chat_id
        kwargs['metadata'] = metadata
        
        return self.record_interaction(
            user_id=user_id,
            message_id=message_id,
            chat_id=chat_id,
            interaction_type=InteractionType.FORWARD.value,
            **kwargs
        )
    
    def record_pin(
        self,
        user_id: int,
        message_id: int,
        chat_id: int,
        **kwargs
    ) -> MessageInteraction:
        """记录置顶消息行为"""
        return self.record_interaction(
            user_id=user_id,
            message_id=message_id,
            chat_id=chat_id,
            interaction_type=InteractionType.PIN.value,
            **kwargs
        )
    
    def record_unpin(
        self,
        user_id: int,
        message_id: int,
        chat_id: int,
        **kwargs
    ) -> MessageInteraction:
        """记录取消置顶消息行为"""
        return self.record_interaction(
            user_id=user_id,
            message_id=message_id,
            chat_id=chat_id,
            interaction_type=InteractionType.UNPIN.value,
            **kwargs
        )
    
    def record_report(
        self,
        user_id: int,
        message_id: int,
        chat_id: int,
        report_reason: Optional[str] = None,
        **kwargs
    ) -> MessageInteraction:
        """记录举报消息行为"""
        metadata = kwargs.get('metadata', {})
        if report_reason:
            metadata['report_reason'] = report_reason
        kwargs['metadata'] = metadata
        
        return self.record_interaction(
            user_id=user_id,
            message_id=message_id,
            chat_id=chat_id,
            interaction_type=InteractionType.REPORT.value,
            **kwargs
        )
    
    def get_user_interactions(
        self,
        user_id: int,
        interaction_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[MessageInteraction]:
        """
        获取用户的交互历史
        
        Args:
            user_id: 用户ID
            interaction_type: 交互类型过滤（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            limit: 最大返回数量
            
        Returns:
            交互记录列表
        """
        query = self.db.query(MessageInteraction).filter(
            MessageInteraction.user_id == user_id
        )
        
        if interaction_type:
            query = query.filter(MessageInteraction.interaction_type == interaction_type)
        
        if start_date:
            query = query.filter(MessageInteraction.created_at >= start_date)
        
        if end_date:
            query = query.filter(MessageInteraction.created_at <= end_date)
        
        return query.order_by(MessageInteraction.created_at.desc()).limit(limit).all()
    
    # ==================== 统计和分析 ====================
    
    def get_bot_feedback_stats(
        self,
        bot_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        获取机器人的反馈统计
        
        Args:
            bot_id: 机器人ID
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            
        Returns:
            统计数据字典
        """
        # 默认统计最近30天
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        # 反应统计
        reaction_query = self.db.query(
            MessageReaction.reaction_type,
            func.count(MessageReaction.id).label('count')
        ).filter(
            and_(
                MessageReaction.bot_id == bot_id,
                MessageReaction.is_active == True,
                MessageReaction.created_at >= start_date,
                MessageReaction.created_at <= end_date
            )
        ).group_by(MessageReaction.reaction_type)
        
        reaction_stats = {row.reaction_type: row.count for row in reaction_query.all()}
        
        # 交互统计
        interaction_query = self.db.query(
            MessageInteraction.interaction_type,
            func.count(MessageInteraction.id).label('count')
        ).filter(
            and_(
                MessageInteraction.bot_id == bot_id,
                MessageInteraction.created_at >= start_date,
                MessageInteraction.created_at <= end_date
            )
        ).group_by(MessageInteraction.interaction_type)
        
        interaction_stats = {row.interaction_type: row.count for row in interaction_query.all()}
        
        # 计算满意度分数
        positive_count = reaction_stats.get('positive', 0)
        negative_count = reaction_stats.get('negative', 0)
        total_rated = positive_count + negative_count
        
        satisfaction_score = None
        if total_rated > 0:
            satisfaction_score = int((positive_count / total_rated) * 100)
        
        return {
            'bot_id': bot_id,
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'reactions': {
                'total': sum(reaction_stats.values()),
                'positive': positive_count,
                'negative': negative_count,
                'neutral': reaction_stats.get('neutral', 0),
                'custom': reaction_stats.get('custom', 0),
                'breakdown': reaction_stats
            },
            'interactions': {
                'total': sum(interaction_stats.values()),
                'breakdown': interaction_stats
            },
            'scores': {
                'satisfaction': satisfaction_score,
                'engagement': sum(interaction_stats.values())
            }
        }
    
    def get_user_feedback_history(
        self,
        user_id: int,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        获取用户的反馈历史
        
        Args:
            user_id: 用户ID
            limit: 最大返回数量
            
        Returns:
            用户反馈历史数据
        """
        # 获取用户的反应历史
        reactions = self.db.query(MessageReaction).filter(
            MessageReaction.user_id == user_id
        ).order_by(MessageReaction.created_at.desc()).limit(limit).all()
        
        # 获取用户的交互历史
        interactions = self.db.query(MessageInteraction).filter(
            MessageInteraction.user_id == user_id
        ).order_by(MessageInteraction.created_at.desc()).limit(limit).all()
        
        return {
            'user_id': user_id,
            'reactions': [
                {
                    'id': r.id,
                    'emoji': r.reaction_emoji,
                    'message_id': r.message_id,
                    'is_active': r.is_active,
                    'created_at': r.created_at.isoformat()
                }
                for r in reactions
            ],
            'interactions': [
                {
                    'id': i.id,
                    'type': i.interaction_type,
                    'message_id': i.message_id,
                    'created_at': i.created_at.isoformat()
                }
                for i in interactions
            ]
        }
    
    def generate_feedback_summary(
        self,
        period_type: str = 'daily',
        period_start: Optional[datetime] = None,
        bot_id: Optional[int] = None,
        channel_id: Optional[int] = None
    ) -> FeedbackSummary:
        """
        生成反馈汇总报告
        
        Args:
            period_type: 周期类型（hourly/daily/weekly/monthly）
            period_start: 周期开始时间
            bot_id: 机器人ID（可选）
            channel_id: 频道ID（可选）
            
        Returns:
            生成的FeedbackSummary对象
        """
        # 确定统计周期
        if not period_start:
            period_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        period_end = self._calculate_period_end(period_start, period_type)
        
        # 检查是否已存在
        existing = self.db.query(FeedbackSummary).filter(
            and_(
                FeedbackSummary.bot_id == bot_id,
                FeedbackSummary.channel_id == channel_id,
                FeedbackSummary.period_type == period_type,
                FeedbackSummary.period_start == period_start
            )
        ).first()
        
        if existing:
            # 更新现有记录
            summary = existing
        else:
            # 创建新记录
            summary = FeedbackSummary(
                bot_id=bot_id,
                channel_id=channel_id,
                period_type=period_type,
                period_start=period_start,
                period_end=period_end
            )
        
        # 构建查询过滤条件
        reaction_filters = [
            MessageReaction.created_at >= period_start,
            MessageReaction.created_at < period_end,
            MessageReaction.is_active == True
        ]
        
        interaction_filters = [
            MessageInteraction.created_at >= period_start,
            MessageInteraction.created_at < period_end
        ]
        
        if bot_id:
            reaction_filters.append(MessageReaction.bot_id == bot_id)
            interaction_filters.append(MessageInteraction.bot_id == bot_id)
        
        if channel_id:
            reaction_filters.append(MessageReaction.channel_id == channel_id)
            interaction_filters.append(MessageInteraction.channel_id == channel_id)
        
        # 统计反应
        reaction_query = self.db.query(
            MessageReaction.reaction_emoji,
            func.count(MessageReaction.id).label('count')
        ).filter(and_(*reaction_filters)).group_by(MessageReaction.reaction_emoji)
        
        reaction_breakdown = {}
        total_reactions = 0
        positive_reactions = 0
        negative_reactions = 0
        neutral_reactions = 0
        
        for row in reaction_query.all():
            reaction_breakdown[row.reaction_emoji] = row.count
            total_reactions += row.count
            
            if row.reaction_emoji in POSITIVE_REACTIONS:
                positive_reactions += row.count
            elif row.reaction_emoji in NEGATIVE_REACTIONS:
                negative_reactions += row.count
            else:
                neutral_reactions += row.count
        
        # 统计交互
        interaction_query = self.db.query(
            MessageInteraction.interaction_type,
            func.count(MessageInteraction.id).label('count')
        ).filter(and_(*interaction_filters)).group_by(MessageInteraction.interaction_type)
        
        interaction_breakdown = {}
        total_interactions = 0
        copy_count = 0
        reply_count = 0
        forward_count = 0
        pin_count = 0
        report_count = 0
        
        for row in interaction_query.all():
            interaction_breakdown[row.interaction_type] = row.count
            total_interactions += row.count
            
            if row.interaction_type == InteractionType.COPY.value:
                copy_count = row.count
            elif row.interaction_type == InteractionType.REPLY.value:
                reply_count = row.count
            elif row.interaction_type == InteractionType.FORWARD.value:
                forward_count = row.count
            elif row.interaction_type == InteractionType.PIN.value:
                pin_count = row.count
            elif row.interaction_type == InteractionType.REPORT.value:
                report_count = row.count
        
        # 计算满意度分数
        satisfaction_score = None
        if positive_reactions + negative_reactions > 0:
            satisfaction_score = int((positive_reactions / (positive_reactions + negative_reactions)) * 100)
        
        # 更新汇总数据
        summary.total_reactions = total_reactions
        summary.positive_reactions = positive_reactions
        summary.negative_reactions = negative_reactions
        summary.neutral_reactions = neutral_reactions
        summary.reaction_breakdown = reaction_breakdown
        
        summary.total_interactions = total_interactions
        summary.copy_count = copy_count
        summary.reply_count = reply_count
        summary.forward_count = forward_count
        summary.pin_count = pin_count
        summary.report_count = report_count
        summary.interaction_breakdown = interaction_breakdown
        
        summary.satisfaction_score = satisfaction_score
        summary.engagement_score = min(100, total_interactions)  # 简单的参与度分数
        
        if not existing:
            self.db.add(summary)
        
        self.db.commit()
        
        logger.info(f"Generated feedback summary for period {period_type} starting {period_start}")
        return summary
    
    def _calculate_period_end(self, period_start: datetime, period_type: str) -> datetime:
        """计算周期结束时间"""
        if period_type == 'hourly':
            return period_start + timedelta(hours=1)
        elif period_type == 'daily':
            return period_start + timedelta(days=1)
        elif period_type == 'weekly':
            return period_start + timedelta(weeks=1)
        elif period_type == 'monthly':
            # 简化处理：假设30天
            return period_start + timedelta(days=30)
        else:
            return period_start + timedelta(days=1)
    
    def get_trending_reactions(
        self,
        hours: int = 24,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取热门反应趋势
        
        Args:
            hours: 统计时间范围（小时）
            limit: 返回数量
            
        Returns:
            热门反应列表
        """
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        results = self.db.query(
            MessageReaction.reaction_emoji,
            func.count(MessageReaction.id).label('count')
        ).filter(
            and_(
                MessageReaction.created_at >= start_time,
                MessageReaction.is_active == True
            )
        ).group_by(
            MessageReaction.reaction_emoji
        ).order_by(
            func.count(MessageReaction.id).desc()
        ).limit(limit).all()
        
        return [
            {'emoji': row.reaction_emoji, 'count': row.count}
            for row in results
        ]
