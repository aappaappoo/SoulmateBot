"""
Bot Manager Service - 机器人管理服务

负责管理多个机器人实例，包括创建、配置、启用/禁用机器人
"""
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from loguru import logger

from src.models.database import Bot, BotStatus, User


class BotManagerService:
    """Bot管理服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_bot(
        self,
        bot_token: str,
        bot_name: str,
        bot_username: str,
        creator_id: int,
        description: Optional[str] = None,
        personality: Optional[str] = None,
        system_prompt: Optional[str] = None,
        ai_model: str = "gpt-4",
        ai_provider: str = "openai",
        is_public: bool = True,
        settings: Optional[Dict[str, Any]] = None
    ) -> Bot:
        """
        创建新机器人
        
        Args:
            bot_token: Telegram Bot Token
            bot_name: 机器人名称
            bot_username: 机器人用户名（不含@）
            creator_id: 创建者用户ID
            description: 机器人描述
            personality: 机器人个性
            system_prompt: AI系统提示词
            ai_model: AI模型名称
            ai_provider: AI提供商
            is_public: 是否公开（可被其他用户添加）
            settings: 其他配置项
            
        Returns:
            Bot: 创建的机器人对象
        """
        # 检查bot_username是否已存在
        existing = self.db.query(Bot).filter(Bot.bot_username == bot_username).first()
        if existing:
            raise ValueError(f"Bot username @{bot_username} already exists")
        
        # 创建机器人
        bot = Bot(
            bot_token=bot_token,
            bot_name=bot_name,
            bot_username=bot_username,
            created_by=creator_id,
            description=description,
            personality=personality,
            system_prompt=system_prompt,
            ai_model=ai_model,
            ai_provider=ai_provider,
            is_public=is_public,
            status=BotStatus.ACTIVE.value,
            settings=settings or {}
        )
        
        self.db.add(bot)
        self.db.commit()
        self.db.refresh(bot)
        
        logger.info(f"Created bot: @{bot_username} (ID: {bot.id})")
        return bot
    
    def get_bot_by_id(self, bot_id: int) -> Optional[Bot]:
        """根据ID获取机器人"""
        return self.db.query(Bot).filter(Bot.id == bot_id).first()
    
    def get_bot_by_username(self, username: str) -> Optional[Bot]:
        """根据用户名获取机器人"""
        # 移除@符号（如果有）
        username = username.lstrip('@')
        return self.db.query(Bot).filter(Bot.bot_username == username).first()
    
    def get_bot_by_token(self, token: str) -> Optional[Bot]:
        """根据token获取机器人"""
        return self.db.query(Bot).filter(Bot.bot_token == token).first()
    
    def list_public_bots(self, status: Optional[str] = None) -> List[Bot]:
        """
        列出所有公开的机器人
        
        Args:
            status: 可选的状态筛选
            
        Returns:
            List[Bot]: 机器人列表
        """
        query = self.db.query(Bot).filter(Bot.is_public == True)
        
        if status:
            query = query.filter(Bot.status == status)
        
        return query.order_by(Bot.created_at.desc()).all()
    
    def list_bots_by_creator(self, creator_id: int) -> List[Bot]:
        """列出某用户创建的所有机器人"""
        return self.db.query(Bot).filter(
            Bot.created_by == creator_id
        ).order_by(Bot.created_at.desc()).all()
    
    def update_bot(
        self,
        bot_id: int,
        **kwargs
    ) -> Optional[Bot]:
        """
        更新机器人配置
        
        Args:
            bot_id: 机器人ID
            **kwargs: 要更新的字段
            
        Returns:
            Bot: 更新后的机器人对象
        """
        bot = self.get_bot_by_id(bot_id)
        if not bot:
            return None
        
        # 更新允许的字段
        allowed_fields = [
            'bot_name', 'description', 'personality', 'system_prompt',
            'ai_model', 'ai_provider', 'is_public', 'status', 'settings'
        ]
        
        for key, value in kwargs.items():
            if key in allowed_fields and value is not None:
                setattr(bot, key, value)
        
        self.db.commit()
        self.db.refresh(bot)
        
        logger.info(f"Updated bot: @{bot.bot_username} (ID: {bot.id})")
        return bot
    
    def activate_bot(self, bot_id: int) -> bool:
        """激活机器人"""
        bot = self.get_bot_by_id(bot_id)
        if not bot:
            return False
        
        bot.status = BotStatus.ACTIVE.value
        self.db.commit()
        logger.info(f"Activated bot: @{bot.bot_username}")
        return True
    
    def deactivate_bot(self, bot_id: int) -> bool:
        """停用机器人"""
        bot = self.get_bot_by_id(bot_id)
        if not bot:
            return False
        
        bot.status = BotStatus.INACTIVE.value
        self.db.commit()
        logger.info(f"Deactivated bot: @{bot.bot_username}")
        return True
    
    def delete_bot(self, bot_id: int, creator_id: int) -> bool:
        """
        删除机器人（需要创建者权限）
        
        Args:
            bot_id: 机器人ID
            creator_id: 创建者ID
            
        Returns:
            bool: 是否成功删除
        """
        bot = self.get_bot_by_id(bot_id)
        if not bot:
            return False
        
        # 验证权限
        if bot.created_by != creator_id:
            logger.warning(f"User {creator_id} attempted to delete bot {bot_id} without permission")
            return False
        
        self.db.delete(bot)
        self.db.commit()
        logger.info(f"Deleted bot: @{bot.bot_username} (ID: {bot_id})")
        return True
