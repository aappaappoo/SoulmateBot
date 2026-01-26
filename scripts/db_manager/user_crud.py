#!/usr/bin/env python3
"""
用户CRUD操作
============

提供用户的增删改查操作。
"""

import sys
import os
from typing import Optional, List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import get_db_session
from src.models.database import User, SubscriptionTier


class UserCRUD:
    """
    用户CRUD操作类
    
    提供用户管理的所有数据库操作:
    - create: 创建用户
    - get: 获取用户
    - list: 列出所有用户
    - update: 更新用户
    - delete: 删除用户
    """

    # ==================== CREATE ====================
    
    @staticmethod
    def create(
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        subscription_tier: Optional[str] = None,
        is_active: bool = True
    ) -> Optional[User]:
        """
        创建新用户
        
        Args:
            telegram_id: Telegram用户ID
            username: 用户名
            first_name: 名字
            last_name: 姓氏
            subscription_tier: 订阅等级
            is_active: 是否激活
            
        Returns:
            User: 创建的用户对象，失败返回None
        """
        db = get_db_session()
        try:
            # 检查是否已存在
            existing = db.query(User).filter(User.telegram_id == telegram_id).first()
            if existing:
                print(f"⚠️  用户已存在: ID={existing.id}")
                return existing
            
            tier = subscription_tier or SubscriptionTier.FREE.value
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                subscription_tier=tier,
                is_active=is_active
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"✅ 用户创建成功: ID={user.id}, @{username}")
            return user
        except Exception as e:
            db.rollback()
            print(f"❌ 创建用户失败: {e}")
            return None
        finally:
            db.close()

    @staticmethod
    def create_interactive() -> Optional[User]:
        """
        交互式创建用户（简化版）

        只需要输入 Telegram ID 和 Username
        """
        print("\n" + "=" * 60)
        print("👤 创建新用户")
        print("=" * 60)

        try:
            # ===== 必填: Telegram User ID =====
            while True:
                telegram_id_str = input("\nTelegram User ID: ").strip()
                if not telegram_id_str:
                    print("   ❌ ID 不能为空")
                    continue
                try:
                    telegram_id = int(telegram_id_str)
                    break
                except ValueError:
                    print("   ❌ 请输入有效的数字ID")

            # ===== 必填: Username =====
            while True:
                username = input("Username (带@的名称): ").strip()
                # 移除 @ 符号（如果用户输入了）
                username = username.lstrip('@')
                if username:
                    break
                print("   ❌ Username 不能为空")

            # 直接创建用户
            return UserCRUD.create(
                telegram_id=telegram_id,
                username=username,
                first_name=username
            )

        except KeyboardInterrupt:
            print("\n\n❌ 已取消")
            return None
        except Exception as e:
            print(f"\n❌ 创建失败: {e}")
            return None

    @staticmethod
    def get(user_id: int = None, telegram_id: int = None, username: str = None) -> Optional[User]:
        """
        获取用户
        
        Args:
            user_id: 数据库用户ID
            telegram_id: Telegram用户ID
            username: 用户名
            
        Returns:
            User: 用户对象，未找到返回None
        """
        db = get_db_session()
        try:
            if user_id:
                return db.query(User).filter(User.id == user_id).first()
            elif telegram_id:
                return db.query(User).filter(User.telegram_id == telegram_id).first()
            elif username:
                return db.query(User).filter(User.username == username).first()
            return None
        finally:
            db.close()

    @staticmethod
    def list_all() -> List[User]:
        """
        列出所有用户
        
        Returns:
            List[User]: 用户列表
        """
        db = get_db_session()
        try:
            return db.query(User).all()
        finally:
            db.close()

    @staticmethod
    def list_print() -> None:
        """打印用户列表"""
        users = UserCRUD.list_all()
        
        print("\n" + "=" * 60)
        print("👤 用户列表")
        print("=" * 60)
        
        if not users:
            print("\n   📭 暂无用户")
            return
        
        print(f"\n   共 {len(users)} 个用户:\n")
        for u in users:
            print(f"   [{u.id}] @{u.username or '(无)'}")
            print(f"       名字: {u.first_name or ''} {u.last_name or ''}")
            print(f"       Telegram ID: {u.telegram_id}")
            print(f"       订阅: {u.subscription_tier}")
            print(f"       状态: {'✅ 激活' if u.is_active else '❌ 未激活'}")
            print()

    # ==================== UPDATE ====================
    
    @staticmethod
    def update(
        user_id: int,
        username: str = None,
        first_name: str = None,
        last_name: str = None,
        subscription_tier: str = None,
        is_active: bool = None
    ) -> Optional[User]:
        """
        更新用户信息
        
        Args:
            user_id: 用户ID
            username: 新用户名
            first_name: 新名字
            last_name: 新姓氏
            subscription_tier: 新订阅等级
            is_active: 新激活状态
            
        Returns:
            User: 更新后的用户对象
        """
        db = get_db_session()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                print(f"❌ 用户不存在: ID={user_id}")
                return None
            
            if username is not None:
                user.username = username
            if first_name is not None:
                user.first_name = first_name
            if last_name is not None:
                user.last_name = last_name
            if subscription_tier is not None:
                user.subscription_tier = subscription_tier
            if is_active is not None:
                user.is_active = is_active
            
            db.commit()
            db.refresh(user)
            print(f"✅ 用户更新成功: ID={user.id}")
            return user
        except Exception as e:
            db.rollback()
            print(f"❌ 更新用户失败: {e}")
            return None
        finally:
            db.close()

    @staticmethod
    def update_interactive() -> Optional[User]:
        """交互式更新用户"""
        UserCRUD.list_print()
        
        try:
            user_id = int(input("\n请输入要更新的用户ID: "))
            
            db = get_db_session()
            user = db.query(User).filter(User.id == user_id).first()
            db.close()
            
            if not user:
                print(f"❌ 用户不存在: ID={user_id}")
                return None
            
            print(f"\n正在更新用户 @{user.username}")
            print("(直接回车保持原值不变)\n")
            
            username = input(f"用户名 [{user.username}]: ").strip() or None
            first_name = input(f"名字 [{user.first_name}]: ").strip() or None
            last_name = input(f"姓氏 [{user.last_name}]: ").strip() or None
            
            return UserCRUD.update(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name
            )
        except ValueError as e:
            print(f"❌ 输入错误: {e}")
            return None

    # ==================== DELETE ====================
    
    @staticmethod
    def delete(user_id: int, confirm: bool = False) -> bool:
        """
        删除用户
        
        Args:
            user_id: 用户ID
            confirm: 是否跳过确认
            
        Returns:
            bool: 删除是否成功
        """
        db = get_db_session()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                print(f"❌ 用户不存在: ID={user_id}")
                return False
            
            if not confirm:
                print(f"\n⚠️  将删除用户: @{user.username}")
                if input("输入 'yes' 确认: ").lower() != 'yes':
                    print("❌ 已取消")
                    return False
            
            db.delete(user)
            db.commit()
            print(f"✅ 用户已删除: @{user.username}")
            return True
        except Exception as e:
            db.rollback()
            print(f"❌ 删除用户失败: {e}")
            return False
        finally:
            db.close()

    @staticmethod
    def delete_interactive() -> bool:
        """交互式删除用户"""
        UserCRUD.list_print()
        
        try:
            user_id = int(input("\n请输入要删除的用户ID: "))
            return UserCRUD.delete(user_id)
        except ValueError as e:
            print(f"❌ 输入错误: {e}")
            return False
