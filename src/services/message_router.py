"""
Message Router - 消息路由系统

负责在多机器人架构中将消息路由到合适的机器人
"""
from typing import Optional, List
from loguru import logger

from src.models.database import Bot, Channel, ChannelBotMapping


class MessageRouter:
    """消息路由器"""
    
    @staticmethod
    def select_bot(
        message_text: str,
        channel: Channel,
        mappings: List[ChannelBotMapping],
        mentioned_username: Optional[str] = None
    ) -> Optional[ChannelBotMapping]:
        """
        根据路由规则选择响应的机器人
        
        Args:
            message_text: 消息文本
            channel: 频道对象
            mappings: 频道中的机器人映射列表
            mentioned_username: 被@的机器人用户名（如果有）
            
        Returns:
            ChannelBotMapping: 选中的机器人映射，如果没有则返回None
        """
        if not mappings:
            return None
        
        # 优先处理mention模式
        if mentioned_username:
            mentioned_username = mentioned_username.lstrip('@')
            for mapping in mappings:
                if mapping.bot.bot_username == mentioned_username:
                    logger.info(f"Selected bot by mention: @{mentioned_username}")
                    return mapping
        
        # 按路由模式处理
        candidates = []
        
        for mapping in mappings:
            if not mapping.is_active:
                continue
            
            if mapping.routing_mode == "mention":
                # mention模式需要显式@机器人
                if mentioned_username and mapping.bot.bot_username == mentioned_username:
                    candidates.append((mapping, mapping.priority))
                    
            elif mapping.routing_mode == "auto":
                # auto模式总是响应
                candidates.append((mapping, mapping.priority))
                
            elif mapping.routing_mode == "keyword":
                # keyword模式检查关键词
                if MessageRouter._check_keywords(message_text, mapping.keywords):
                    candidates.append((mapping, mapping.priority))
        
        if not candidates:
            return None
        
        # 按优先级排序，选择最高优先级的机器人
        candidates.sort(key=lambda x: x[1], reverse=True)
        selected_mapping = candidates[0][0]
        
        logger.info(
            f"Selected bot: @{selected_mapping.bot.bot_username} "
            f"(mode: {selected_mapping.routing_mode}, priority: {selected_mapping.priority})"
        )
        
        return selected_mapping
    
    @staticmethod
    def _check_keywords(message_text: str, keywords: List[str]) -> bool:
        """
        检查消息是否包含关键词
        
        Args:
            message_text: 消息文本
            keywords: 关键词列表
            
        Returns:
            bool: 是否匹配
        """
        if not keywords:
            return False
        
        message_lower = message_text.lower()
        
        for keyword in keywords:
            if keyword.lower() in message_lower:
                logger.debug(f"Keyword matched: {keyword}")
                return True
        
        return False
    
    @staticmethod
    def extract_mention(message_text: str) -> Optional[str]:
        """
        从消息中提取@的机器人用户名
        
        Args:
            message_text: 消息文本
            
        Returns:
            str: 被@的用户名（不含@），如果没有则返回None
        """
        # 简单的@提取，支持 @username 格式
        words = message_text.split()
        for word in words:
            if word.startswith('@'):
                username = word[1:].rstrip(',.!?;:')
                if username:
                    return username
        
        return None
    
    @staticmethod
    def should_respond_in_channel(
        chat_type: str,
        mappings: List[ChannelBotMapping]
    ) -> bool:
        """
        判断是否应该在频道中响应
        
        Args:
            chat_type: 聊天类型
            mappings: 机器人映射列表
            
        Returns:
            bool: 是否应该响应
        """
        # 私聊总是响应
        if chat_type == "private":
            return True
        
        # 群组或频道：检查是否有活跃的机器人
        active_mappings = [m for m in mappings if m.is_active]
        
        if not active_mappings:
            logger.info(f"No active bots in channel (type: {chat_type})")
            return False
        
        return True
