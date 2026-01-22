#!/usr/bin/env python3
"""
Channel CRUD操作
================

提供Channel的增删改查操作。
"""

import sys
import os
from typing import Optional, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import get_db_session
from src.models.database import Channel, User, ChannelBotMapping, SubscriptionTier


class ChannelCRUD:
    """
    Channel CRUD操作类
    
    提供Channel管理的所有数据库操作:
    - create: 创建Channel
    - get: 获取Channel
    - list: 列出所有Channel
    - update: 更新Channel
    - delete: 删除Channel
    """

    # ==================== CREATE ====================
    
    @staticmethod
    def create(
        telegram_chat_id: int,
        chat_type: str,
        title: str = None,
        username: str = None,
        owner_id: int = None,
        subscription_tier: str = None,
        is_active: bool = True
    ) -> Optional[Channel]:
        """
        创建新Channel
        
        Args:
            telegram_chat_id: Telegram聊天ID
            chat_type: 聊天类型(private/group/supergroup/channel)
            title: 频道标题
            username: 频道用户名
            owner_id: 所有者用户ID
            subscription_tier: 订阅等级
            is_active: 是否激活
            
        Returns:
            Channel: 创建的Channel对象，失败返回None
        """
        db = get_db_session()
        try:
            # 检查是否已存在
            existing = db.query(Channel).filter(Channel.telegram_chat_id == telegram_chat_id).first()
            if existing:
                print(f"⚠️  Channel已存在: ID={existing.id}")
                return existing
            
            channel = Channel(
                telegram_chat_id=telegram_chat_id,
                chat_type=chat_type,
                title=title,
                username=username,
                owner_id=owner_id,
                subscription_tier=subscription_tier or SubscriptionTier.FREE.value,
                is_active=is_active
            )
            db.add(channel)
            db.commit()
            db.refresh(channel)
            print(f"✅ Channel创建成功: ID={channel.id}, chat_id={telegram_chat_id}")
            return channel
        except Exception as e:
            db.rollback()
            print(f"❌ 创建Channel失败: {e}")
            return None
        finally:
            db.close()

    @staticmethod
    def create_interactive() -> Optional[Channel]:
        """交互式创建Channel"""
        print("\n" + "=" * 60)
        print("💬 创建新Channel")
        print("=" * 60)
        
        try:
            telegram_chat_id = int(input("\n请输入Telegram Chat ID: "))
            
            print("\n选择Chat类型:")
            print("   [1] private - 私聊")
            print("   [2] group - 普通群组")
            print("   [3] supergroup - 超级群组")
            print("   [4] channel - 频道")
            type_choice = input("请选择 (1/2/3/4): ").strip()
            
            type_map = {"1": "private", "2": "group", "3": "supergroup", "4": "channel"}
            chat_type = type_map.get(type_choice, "private")
            
            title = input("频道标题 (可选): ").strip() or None
            
            # 选择所有者
            db = get_db_session()
            users = db.query(User).all()
            db.close()
            
            owner_id = None
            if users:
                print("\n👤 选择所有者 (可选):")
                for u in users:
                    print(f"   [{u.id}] @{u.username}")
                owner_input = input("请输入用户ID (直接回车跳过): ").strip()
                if owner_input:
                    owner_id = int(owner_input)
            
            return ChannelCRUD.create(
                telegram_chat_id=telegram_chat_id,
                chat_type=chat_type,
                title=title,
                owner_id=owner_id
            )
        except ValueError as e:
            print(f"❌ 输入错误: {e}")
            return None

    # ==================== READ ====================
    
    @staticmethod
    def get(channel_id: int = None, telegram_chat_id: int = None) -> Optional[Channel]:
        """
        获取Channel
        
        Args:
            channel_id: 数据库Channel ID
            telegram_chat_id: Telegram聊天ID
            
        Returns:
            Channel: Channel对象，未找到返回None
        """
        db = get_db_session()
        try:
            if channel_id:
                return db.query(Channel).filter(Channel.id == channel_id).first()
            elif telegram_chat_id:
                return db.query(Channel).filter(Channel.telegram_chat_id == telegram_chat_id).first()
            return None
        finally:
            db.close()

    @staticmethod
    def list_all() -> List[Channel]:
        """
        列出所有Channel
        
        Returns:
            List[Channel]: Channel列表
        """
        db = get_db_session()
        try:
            return db.query(Channel).all()
        finally:
            db.close()

    @staticmethod
    def list_print() -> None:
        """打印Channel列表"""
        db = get_db_session()
        try:
            channels = db.query(Channel).all()
            
            print("\n" + "=" * 60)
            print("💬 Channel列表")
            print("=" * 60)
            
            if not channels:
                print("\n   📭 暂无Channel")
                return
            
            print(f"\n   共 {len(channels)} 个Channel:\n")
            for c in channels:
                # 获取绑定的Bot数
                bot_count = db.query(ChannelBotMapping).filter(
                    ChannelBotMapping.channel_id == c.id,
                    ChannelBotMapping.is_active == True
                ).count()
                
                print(f"   [{c.id}] {c.title or '(无标题)'}")
                print(f"       类型: {c.chat_type}")
                print(f"       Chat ID: {c.telegram_chat_id}")
                print(f"       订阅: {c.subscription_tier}")
                print(f"       绑定Bot数: {bot_count}")
                print(f"       状态: {'✅ 激活' if c.is_active else '❌ 未激活'}")
                print()
        finally:
            db.close()

    # ==================== UPDATE ====================
    
    @staticmethod
    def update(
        channel_id: int,
        title: str = None,
        username: str = None,
        subscription_tier: str = None,
        is_active: bool = None
    ) -> Optional[Channel]:
        """
        更新Channel信息
        
        Args:
            channel_id: Channel ID
            title: 新标题
            username: 新用户名
            subscription_tier: 新订阅等级
            is_active: 新激活状态
            
        Returns:
            Channel: 更新后的Channel对象
        """
        db = get_db_session()
        try:
            channel = db.query(Channel).filter(Channel.id == channel_id).first()
            if not channel:
                print(f"❌ Channel不存在: ID={channel_id}")
                return None
            
            if title is not None:
                channel.title = title
            if username is not None:
                channel.username = username
            if subscription_tier is not None:
                channel.subscription_tier = subscription_tier
            if is_active is not None:
                channel.is_active = is_active
            
            db.commit()
            db.refresh(channel)
            print(f"✅ Channel更新成功: ID={channel.id}")
            return channel
        except Exception as e:
            db.rollback()
            print(f"❌ 更新Channel失败: {e}")
            return None
        finally:
            db.close()

    @staticmethod
    def update_interactive() -> Optional[Channel]:
        """交互式更新Channel"""
        ChannelCRUD.list_print()
        
        try:
            channel_id = int(input("\n请输入要更新的Channel ID: "))
            
            db = get_db_session()
            channel = db.query(Channel).filter(Channel.id == channel_id).first()
            db.close()
            
            if not channel:
                print(f"❌ Channel不存在: ID={channel_id}")
                return None
            
            print(f"\n正在更新Channel {channel.title or channel.telegram_chat_id}")
            print("(直接回车保持原值不变)\n")
            
            title = input(f"标题 [{channel.title}]: ").strip() or None
            
            return ChannelCRUD.update(
                channel_id=channel_id,
                title=title
            )
        except ValueError as e:
            print(f"❌ 输入错误: {e}")
            return None

    # ==================== DELETE ====================
    
    @staticmethod
    def delete(channel_id: int, confirm: bool = False) -> bool:
        """
        删除Channel
        
        Args:
            channel_id: Channel ID
            confirm: 是否跳过确认
            
        Returns:
            bool: 删除是否成功
        """
        db = get_db_session()
        try:
            channel = db.query(Channel).filter(Channel.id == channel_id).first()
            if not channel:
                print(f"❌ Channel不存在: ID={channel_id}")
                return False
            
            if not confirm:
                print(f"\n⚠️  将删除Channel {channel.title or channel.telegram_chat_id} 及其所有绑定关系")
                if input("输入 'yes' 确认: ").lower() != 'yes':
                    print("❌ 已取消")
                    return False
            
            # 删除相关绑定
            db.query(ChannelBotMapping).filter(ChannelBotMapping.channel_id == channel_id).delete()
            db.delete(channel)
            db.commit()
            print(f"✅ Channel已删除: {channel.title or channel.telegram_chat_id}")
            return True
        except Exception as e:
            db.rollback()
            print(f"❌ 删除Channel失败: {e}")
            return False
        finally:
            db.close()

    @staticmethod
    def delete_interactive() -> bool:
        """交互式删除Channel"""
        ChannelCRUD.list_print()
        
        try:
            channel_id = int(input("\n请输入要删除的Channel ID: "))
            return ChannelCRUD.delete(channel_id)
        except ValueError as e:
            print(f"❌ 输入错误: {e}")
            return False
