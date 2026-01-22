"""
Group Monitor Service

群组监控服务 - 提供群组消息收集和话题总结功能

主要功能：
1. 创建监控配置
2. 收集群组消息
3. 分析并总结讨论话题
4. 生成监控报告
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from loguru import logger
import json

from src.models.group_monitor import GroupMonitorConfig, GroupMessage, TopicSummary
from src.models.database import User


# Configuration constants
MAX_MESSAGES_TEXT_LENGTH = 10000  # Maximum characters for LLM analysis
UUID_SHORT_LENGTH = 8  # Length of shortened UUID for display


class GroupMonitorService:
    """
    群组监控服务
    
    提供群组监控的核心业务逻辑。
    """
    
    def __init__(self, db: AsyncSession, llm_provider=None):
        """
        初始化服务
        
        Args:
            db: 异步数据库会话
            llm_provider: LLM提供者（用于话题分析）
        """
        self.db = db
        self.llm_provider = llm_provider
    
    async def create_monitor_config(
        self,
        user_id: int,
        group_link: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        keywords: List[str] = None
    ) -> GroupMonitorConfig:
        """
        创建监控配置
        
        Args:
            user_id: 用户ID
            group_link: 群组链接
            start_time: 开始监控时间
            end_time: 结束监控时间
            keywords: 关注的关键词
            
        Returns:
            GroupMonitorConfig: 创建的配置实例
        """
        config = GroupMonitorConfig(
            user_id=user_id,
            group_link=group_link,
            start_time=start_time or datetime.utcnow(),
            end_time=end_time,
            keywords=keywords or [],
            is_active=True
        )
        
        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)
        
        logger.info(f"创建监控配置: user={user_id}, group={group_link}")
        return config
    
    async def get_user_configs(
        self,
        user_id: int,
        active_only: bool = True
    ) -> List[GroupMonitorConfig]:
        """
        获取用户的监控配置列表
        
        Args:
            user_id: 用户ID
            active_only: 是否只返回激活的配置
            
        Returns:
            List[GroupMonitorConfig]: 配置列表
        """
        query = select(GroupMonitorConfig).where(
            GroupMonitorConfig.user_id == user_id
        )
        
        if active_only:
            query = query.where(GroupMonitorConfig.is_active == True)
        
        query = query.order_by(desc(GroupMonitorConfig.created_at))
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_config_by_id(self, config_id: int) -> Optional[GroupMonitorConfig]:
        """获取指定配置"""
        result = await self.db.execute(
            select(GroupMonitorConfig).where(GroupMonitorConfig.id == config_id)
        )
        return result.scalar_one_or_none()
    
    async def update_config(
        self,
        config_id: int,
        **updates
    ) -> Optional[GroupMonitorConfig]:
        """
        更新监控配置
        
        Args:
            config_id: 配置ID
            **updates: 要更新的字段
            
        Returns:
            GroupMonitorConfig: 更新后的配置
        """
        config = await self.get_config_by_id(config_id)
        if not config:
            return None
        
        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        config.version += 1
        await self.db.commit()
        await self.db.refresh(config)
        
        return config
    
    async def stop_monitor(self, config_id: int) -> bool:
        """停止监控"""
        config = await self.update_config(config_id, is_active=False, end_time=datetime.utcnow())
        return config is not None
    
    async def save_message(
        self,
        config_id: int,
        message_id: int,
        chat_id: int,
        content: str,
        sender_id: int = None,
        sender_username: str = None,
        sender_name: str = None,
        message_type: str = "text",
        message_date: datetime = None,
        reply_to_message_id: int = None,
        forward_from: str = None
    ) -> GroupMessage:
        """
        保存群组消息
        
        Args:
            config_id: 监控配置ID
            message_id: Telegram消息ID
            chat_id: 群组Chat ID
            content: 消息内容
            sender_id: 发送者ID
            sender_username: 发送者用户名
            sender_name: 发送者名称
            message_type: 消息类型
            message_date: 消息发送时间
            reply_to_message_id: 回复的消息ID
            forward_from: 转发来源
            
        Returns:
            GroupMessage: 保存的消息实例
        """
        message = GroupMessage(
            config_id=config_id,
            message_id=message_id,
            chat_id=chat_id,
            content=content,
            sender_id=sender_id,
            sender_username=sender_username,
            sender_name=sender_name,
            message_type=message_type,
            message_date=message_date or datetime.utcnow(),
            reply_to_message_id=reply_to_message_id,
            forward_from=forward_from
        )
        
        self.db.add(message)
        
        try:
            await self.db.commit()
            await self.db.refresh(message)
            return message
        except Exception as e:
            await self.db.rollback()
            logger.warning(f"保存消息失败（可能已存在）: {e}")
            return None
    
    async def get_messages(
        self,
        config_id: int,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 1000
    ) -> List[GroupMessage]:
        """
        获取配置的消息列表
        
        Args:
            config_id: 配置ID
            start_time: 开始时间
            end_time: 结束时间
            limit: 最大返回数量
            
        Returns:
            List[GroupMessage]: 消息列表
        """
        query = select(GroupMessage).where(
            GroupMessage.config_id == config_id
        )
        
        if start_time:
            query = query.where(GroupMessage.message_date >= start_time)
        if end_time:
            query = query.where(GroupMessage.message_date <= end_time)
        
        query = query.order_by(GroupMessage.message_date).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_message_stats(self, config_id: int) -> Dict[str, Any]:
        """
        获取消息统计信息
        
        Args:
            config_id: 配置ID
            
        Returns:
            Dict: 统计信息
        """
        # 总消息数
        total_result = await self.db.execute(
            select(func.count(GroupMessage.id)).where(
                GroupMessage.config_id == config_id
            )
        )
        total_count = total_result.scalar() or 0
        
        # 活跃用户数
        users_result = await self.db.execute(
            select(func.count(func.distinct(GroupMessage.sender_id))).where(
                GroupMessage.config_id == config_id
            )
        )
        unique_users = users_result.scalar() or 0
        
        # 时间范围
        time_result = await self.db.execute(
            select(
                func.min(GroupMessage.message_date),
                func.max(GroupMessage.message_date)
            ).where(GroupMessage.config_id == config_id)
        )
        time_row = time_result.one_or_none()
        
        # 最活跃用户
        top_users_result = await self.db.execute(
            select(
                GroupMessage.sender_username,
                func.count(GroupMessage.id).label('count')
            ).where(
                GroupMessage.config_id == config_id
            ).group_by(
                GroupMessage.sender_username
            ).order_by(
                desc('count')
            ).limit(5)
        )
        top_users = [{"username": row[0], "count": row[1]} for row in top_users_result.all()]
        
        return {
            "total_messages": total_count,
            "unique_users": unique_users,
            "start_time": time_row[0].isoformat() if time_row and time_row[0] else None,
            "end_time": time_row[1].isoformat() if time_row and time_row[1] else None,
            "top_users": top_users
        }
    
    async def analyze_topics(
        self,
        config_id: int,
        start_time: datetime = None,
        end_time: datetime = None
    ) -> List[TopicSummary]:
        """
        分析并总结话题
        
        使用LLM分析消息内容，提取主要讨论话题。
        
        Args:
            config_id: 配置ID
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            List[TopicSummary]: 话题总结列表
        """
        # 获取消息
        messages = await self.get_messages(config_id, start_time, end_time)
        
        if not messages:
            logger.info(f"配置 {config_id} 没有消息可分析")
            return []
        
        # 准备消息文本
        messages_text = self._prepare_messages_for_analysis(messages)
        
        # 获取消息统计
        stats = await self.get_message_stats(config_id)
        
        # 使用LLM分析话题
        if self.llm_provider:
            topics_data = await self._analyze_with_llm(messages_text, stats)
        else:
            # 简单的基于规则的分析
            topics_data = self._analyze_without_llm(messages)
        
        # 保存话题总结
        summaries = []
        for topic in topics_data:
            summary = TopicSummary(
                config_id=config_id,
                topic_title=topic.get("title", "未命名话题"),
                topic_summary=topic.get("summary", ""),
                keywords=topic.get("keywords", []),
                message_count=topic.get("message_count", 0),
                participant_count=topic.get("participant_count", 0),
                active_participants=topic.get("active_participants", []),
                start_time=start_time or (messages[0].message_date if messages else None),
                end_time=end_time or (messages[-1].message_date if messages else None),
                sentiment=topic.get("sentiment", "neutral"),
                importance_score=topic.get("importance_score", 50),
                ai_analysis=topic.get("ai_analysis", {})
            )
            
            self.db.add(summary)
            summaries.append(summary)
        
        await self.db.commit()
        
        # 刷新所有摘要
        for summary in summaries:
            await self.db.refresh(summary)
        
        logger.info(f"分析完成，生成 {len(summaries)} 个话题总结")
        return summaries
    
    def _prepare_messages_for_analysis(self, messages: List[GroupMessage]) -> str:
        """准备消息文本用于分析"""
        lines = []
        for msg in messages:
            sender = msg.sender_username or msg.sender_name or "Anonymous"
            time_str = msg.message_date.strftime("%Y-%m-%d %H:%M")
            lines.append(f"[{time_str}] {sender}: {msg.content or '[非文本消息]'}")
        
        return "\n".join(lines)
    
    async def _analyze_with_llm(
        self,
        messages_text: str,
        stats: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """使用LLM分析话题"""
        prompt = f"""分析以下群聊消息，识别主要讨论话题。

消息统计：
- 总消息数：{stats['total_messages']}
- 参与用户数：{stats['unique_users']}
- 时间范围：{stats['start_time']} 到 {stats['end_time']}

群聊消息：
{messages_text[:MAX_MESSAGES_TEXT_LENGTH]}

请以JSON格式返回话题列表，每个话题包含：
- title: 话题标题
- summary: 话题摘要（100字以内）
- keywords: 关键词列表
- message_count: 相关消息估计数量
- participant_count: 参与讨论的用户数量
- active_participants: 最活跃的参与者用户名列表（最多5个）
- sentiment: 情感倾向（positive/negative/neutral）
- importance_score: 重要性评分（0-100）

只返回JSON数组，不要其他内容。"""

        try:
            response = await self.llm_provider.generate_response(
                [{"role": "user", "content": prompt}],
                context="你是一个专业的群组讨论分析助手，擅长识别话题和总结讨论内容。"
            )
            
            # 解析JSON响应
            response_text = response.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            topics = json.loads(response_text)
            return topics if isinstance(topics, list) else [topics]
            
        except Exception as e:
            logger.error(f"LLM话题分析失败: {e}")
            return self._analyze_without_llm_from_text(messages_text, stats)
    
    def _analyze_without_llm(self, messages: List[GroupMessage]) -> List[Dict[str, Any]]:
        """不使用LLM的简单话题分析"""
        if not messages:
            return []
        
        # 统计词频
        from collections import Counter
        word_counter = Counter()
        user_counter = Counter()
        
        for msg in messages:
            if msg.content:
                # 简单的中英文分词
                words = msg.content.replace("，", " ").replace("。", " ").replace("！", " ").replace("？", " ").split()
                for word in words:
                    if len(word) >= 2:
                        word_counter[word] += 1
            
            if msg.sender_username:
                user_counter[msg.sender_username] += 1
        
        # 生成话题
        top_keywords = [word for word, _ in word_counter.most_common(10)]
        top_users = [user for user, _ in user_counter.most_common(5)]
        
        return [{
            "title": "群组讨论总结",
            "summary": f"群组共有 {len(messages)} 条消息，{len(user_counter)} 位用户参与讨论。",
            "keywords": top_keywords,
            "message_count": len(messages),
            "participant_count": len(user_counter),
            "active_participants": top_users,
            "sentiment": "neutral",
            "importance_score": 50
        }]
    
    def _analyze_without_llm_from_text(
        self,
        messages_text: str,
        stats: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """从文本分析话题（无LLM）"""
        return [{
            "title": "群组讨论总结",
            "summary": f"群组共有 {stats['total_messages']} 条消息，{stats['unique_users']} 位用户参与讨论。",
            "keywords": [],
            "message_count": stats['total_messages'],
            "participant_count": stats['unique_users'],
            "active_participants": [u['username'] for u in stats.get('top_users', [])],
            "sentiment": "neutral",
            "importance_score": 50
        }]
    
    async def get_summaries(
        self,
        config_id: int,
        limit: int = 10
    ) -> List[TopicSummary]:
        """获取话题总结列表"""
        result = await self.db.execute(
            select(TopicSummary).where(
                TopicSummary.config_id == config_id
            ).order_by(
                desc(TopicSummary.importance_score)
            ).limit(limit)
        )
        return list(result.scalars().all())
    
    async def generate_report(
        self,
        config_id: int,
        start_time: datetime = None,
        end_time: datetime = None
    ) -> str:
        """
        生成监控报告
        
        Args:
            config_id: 配置ID
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            str: 格式化的报告文本
        """
        config = await self.get_config_by_id(config_id)
        if not config:
            return "❌ 监控配置未找到"
        
        stats = await self.get_message_stats(config_id)
        summaries = await self.get_summaries(config_id)
        
        # 构建报告
        report_lines = [
            "📊 **群组监控报告**",
            "",
            f"📍 群组: {config.group_title or config.group_link}",
            f"📅 时间范围: {stats.get('start_time', 'N/A')} - {stats.get('end_time', 'N/A')}",
            f"📝 消息总数: {stats['total_messages']}",
            f"👥 参与用户: {stats['unique_users']}",
            "",
            "🔝 **最活跃用户:**",
        ]
        
        for i, user in enumerate(stats.get('top_users', [])[:5], 1):
            report_lines.append(f"  {i}. @{user['username']}: {user['count']}条消息")
        
        report_lines.append("")
        report_lines.append("📌 **主要话题:**")
        
        if summaries:
            for i, summary in enumerate(summaries[:5], 1):
                sentiment_emoji = {
                    "positive": "😊",
                    "negative": "😔",
                    "neutral": "😐"
                }.get(summary.sentiment, "😐")
                
                report_lines.append(f"\n{i}. **{summary.topic_title}** {sentiment_emoji}")
                report_lines.append(f"   {summary.topic_summary}")
                if summary.keywords:
                    report_lines.append(f"   关键词: {', '.join(summary.keywords[:5])}")
        else:
            report_lines.append("  暂无话题分析")
        
        return "\n".join(report_lines)
