#!/usr/bin/env python3
"""
SoulmateBot 数据库管理工具包
============================

提供完整的数据库CRUD操作和管理功能。

模块结构:
- base.py: 基础管理类和通用工具
- user_crud.py: 用户增删改查操作
- bot_crud.py: Bot增删改查操作
- channel_crud.py: Channel增删改查操作
- mapping_crud.py: Channel-Bot映射管理
- token_manager.py: Token管理功能
- cli.py: 命令行接口

使用方法:
  python -m scripts.db_manager rebuild
  python -m scripts.db_manager status
  python -m scripts.db_manager user list
  python -m scripts.db_manager bot create
  python -m scripts.db_manager channel list
"""

from .base import DatabaseManager
from .user_crud import UserCRUD
from .bot_crud import BotCRUD
from .channel_crud import ChannelCRUD
from .mapping_crud import MappingCRUD
from .token_manager import TokenManager
from .conversation_crud import ConversationCRUD

__all__ = [
    "DatabaseManager",
    "UserCRUD",
    "BotCRUD", 
    "ChannelCRUD",
    "MappingCRUD",
    "TokenManager",
    "ConversationCRUD",
]
