#!/usr/bin/env python3
"""
对话记录CRUD操作
================

提供对话记录的管理功能，包括清空指定用户和Bot的聊天记录。
"""

import sys
import os
from typing import Optional, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import get_db_session
from src.models.database import Conversation, User, Bot
from loguru import logger


class ConversationCRUD:
    """
    对话记录CRUD操作类

    提供对话记录管理的所有数据库操作:
    - clear_user_bot_history: 清空指定用户与指定Bot的聊天记录（按session_id）
    - clear_user_all_history: 清空指定用户的所有聊天记录
    - delete_by_user_and_bot: 删除指定用户和Bot的所有记录（包括session_id为空的）
    - list_user_conversations: 列出用户的对话记录
    """

    @staticmethod
    def delete_by_user_and_bot(
            user_id: int = None,
            telegram_user_id: int = None,
            bot_id: int = None,
            bot_username: str = None,
            confirm: bool = False
    ) -> int:
        """
        删除指定用户和Bot的所有聊天记录

        与 clear_user_bot_history 的区别：
        - 此方法会删除所有该用户的对话记录，包括 session_id 为空的记录
        - 同时按 session_id 格式 "{user_id}_{bot_id}" 匹配和 session_id 为 NULL 的记录

        Args:
            user_id: 数据库用户ID
            telegram_user_id: Telegram用户ID
            bot_id: 数据库Bot ID
            bot_username: Bot用户名
            confirm: 是否跳过确认

        Returns:
            int: 删除的记录数
        """
        from sqlalchemy import or_

        db = get_db_session()
        try:
            # 解析用户
            user = None
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
            elif telegram_user_id:
                user = db.query(User).filter(User.telegram_id == telegram_user_id).first()

            if not user:
                print(f"❌ 用户不存在")
                return 0

            # 解析Bot
            bot = None
            if bot_id:
                bot = db.query(Bot).filter(Bot.id == bot_id).first()
            elif bot_username:
                bot = db.query(Bot).filter(Bot.bot_username == bot_username).first()

            if not bot:
                print(f"❌ Bot不存在")
                return 0

            # 构建查询条件
            # 匹配条件：user_id 匹配 且 (session_id 匹配 或 session_id 为空)
            session_id = f"{user.id}_{bot.id}"
            query = db.query(Conversation).filter(
                Conversation.user_id == user.id,
                or_(
                    Conversation.session_id == session_id,
                    Conversation.session_id.is_(None)
                )
            )

            count = query.count()

            if count == 0:
                print(f"ℹ️  用户 @{user.username} (ID={user.id}) 与 Bot @{bot.bot_username} (ID={bot.id}) 之间没有聊天记录")
                return 0

            if not confirm:
                print(f"\n⚠️  将删除用户 @{user.username} (ID={user.id}) 与 Bot @{bot.bot_username} (ID={bot.id}) 的 {count} 条聊天记录")
                print(f"   包括 session_id='{session_id}' 和 session_id=NULL 的记录")
                if input("输入 'yes' 确认: ").lower() != 'yes':
                    print("❌ 已取消")
                    return 0

            # 执行删除
            deleted = query.delete(synchronize_session=False)
            db.commit()

            print(f"✅ 已删除 {deleted} 条聊天记录")
            logger.info(f"Deleted {deleted} conversation records for user {user.id} with bot {bot.id}")
            return deleted

        except Exception as e:
            db.rollback()
            print(f"❌ 删除失败: {e}")
            logger.error(f"Failed to delete conversation: {e}")
            return 0
        finally:
            db.close()

    @staticmethod
    def delete_all_by_user(
            user_id: int = None,
            telegram_user_id: int = None,
            confirm: bool = False
    ) -> int:
        """
        删除指定用户与所有Bot的聊天记录

        Args:
            user_id: 数据库用户ID
            telegram_user_id: Telegram用户ID
            confirm: 是否跳过确认

        Returns:
            int: 删除的记录数
        """
        db = get_db_session()
        try:
            # 解析用户
            user = None
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
            elif telegram_user_id:
                user = db.query(User).filter(User.telegram_id == telegram_user_id).first()

            if not user:
                print(f"❌ 用户不存在")
                return 0

            # 查询记录数
            count = db.query(Conversation).filter(Conversation.user_id == user.id).count()

            if count == 0:
                print(f"ℹ️  用户 @{user.username} (ID={user.id}) 没有聊天记录")
                return 0

            if not confirm:
                print(f"\n⚠️  将删除用户 @{user.username} (ID={user.id}) 的所有 {count} 条聊天记录")
                if input("输入 'yes' 确认: ").lower() != 'yes':
                    print("❌ 已取消")
                    return 0

            # 执行删除
            deleted = db.query(Conversation).filter(Conversation.user_id == user.id).delete()
            db.commit()

            print(f"✅ 已删除 {deleted} 条聊天记录")
            logger.info(f"Deleted all {deleted} conversation records for user {user.id}")
            return deleted

        except Exception as e:
            db.rollback()
            print(f"❌ 删除失败: {e}")
            logger.error(f"Failed to delete conversation: {e}")
            return 0
        finally:
            db.close()

    @staticmethod
    def delete_interactive() -> None:
        """交互式删除聊天记录"""
        print("\n" + "=" * 60)
        print("🗑️  删除聊天记录")
        print("=" * 60)

        db = get_db_session()
        try:
            # 列出所有用户
            users = db.query(User).all()
            if not users:
                print("❌ 没有用户数据")
                return

            print("\n👤 选择用户:")
            for u in users:
                # 统计该用户的对话记录数
                conv_count = db.query(Conversation).filter(Conversation.user_id == u.id).count()
                print(f"   [{u.id}] @{u.username} | {u.first_name} | TG ID: {u.telegram_id} | 对话数: {conv_count}")

            user_id = int(input("\n请输入用户ID: ").strip())
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                print("❌ 用户不存在")
                return

            # 选择操作
            print("\n选择操作:")
            print("   [1] 删除与指定Bot的聊天记录")
            print("   [2] 删除所有聊天记录")

            choice = input("\n请选择 [1/2]: ").strip()

            if choice == "1":
                # 列出所有Bot
                bots = db.query(Bot).all()
                if not bots:
                    print("❌ 没有Bot数据")
                    return

                print("\n🤖 选择Bot:")
                for b in bots:
                    # 统计该用户与此Bot的对话记录数
                    session_id = f"{user.id}_{b.id}"
                    from sqlalchemy import or_
                    conv_count = db.query(Conversation).filter(
                        Conversation.user_id == user.id,
                        or_(
                            Conversation.session_id == session_id,
                            Conversation.session_id.is_(None)
                        )
                    ).count()
                    print(f"   [{b.id}] @{b.bot_username} | {b.bot_name} | 对话数: {conv_count}")

                bot_id = int(input("\n请输入Bot ID: ").strip())

                db.close()
                ConversationCRUD.delete_by_user_and_bot(user_id=user_id, bot_id=bot_id)

            elif choice == "2":
                db.close()
                ConversationCRUD.delete_all_by_user(user_id=user_id)
            else:
                print("❌ 无效选择")

        except ValueError:
            print("❌ 请输入有效的数字")
        except Exception as e:
            print(f"❌ 操作失败: {e}")
        finally:
            try:
                db.close()
            except:
                pass

    @staticmethod
    def clear_user_bot_history(
            user_id: int = None,
            telegram_user_id: int = None,
            bot_id: int = None,
            bot_username: str = None,
            confirm: bool = False
    ) -> int:
        """
        清空指定用户与指定Bot的聊天记录

        Args:
            user_id: 数据库用户ID
            telegram_user_id: Telegram用户ID
            bot_id: 数据库Bot ID
            bot_username: Bot用户名
            confirm: 是否跳过确认

        Returns:
            int: 删除的记录数
        """
        db = get_db_session()
        try:
            # 解析用户
            user = None
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
            elif telegram_user_id:
                user = db.query(User).filter(User.telegram_id == telegram_user_id).first()

            if not user:
                print(f"❌ 用户不存在")
                return 0

            # 解析Bot
            bot = None
            if bot_id:
                bot = db.query(Bot).filter(Bot.id == bot_id).first()
            elif bot_username:
                bot = db.query(Bot).filter(Bot.bot_username == bot_username).first()

            if not bot:
                print(f"❌ Bot不存在")
                return 0

            # 查询要删除的记录数
            # 注意：Conversation模型中的user_id是数据库用户ID
            # 需要根据实际的Conversation模型来构建查询
            # 假设Conversation有 user_id 和 session_id 字段
            # session_id 的格式可能包含 bot_id 信息

            # 构建查询条件
            query = db.query(Conversation).filter(Conversation.user_id == user.id)

            # 如果session_id包含bot信息，可以通过session_id过滤
            # 格式: "{user_id}_{bot_id}"
            session_id = f"{user.id}_{bot.id}"
            query = query.filter(Conversation.session_id == session_id)

            count = query.count()

            if count == 0:
                print(f"ℹ️  用户 @{user.username} 与 Bot @{bot.bot_username} 之间没有聊天记录")
                return 0

            if not confirm:
                print(f"\n⚠️  将删除用户 @{user.username} 与 Bot @{bot.bot_username} 的 {count} 条聊天记录")
                if input("输入 'yes' 确认: ").lower() != 'yes':
                    print("❌ 已取消")
                    return 0

            # 执行删除
            deleted = query.delete(synchronize_session=False)
            db.commit()

            print(f"✅ 已删除 {deleted} 条聊天记录")
            logger.info(f"Cleared {deleted} conversation records for user {user.id} with bot {bot.id}")
            return deleted

        except Exception as e:
            db.rollback()
            print(f"❌ 删除失败: {e}")
            logger.error(f"Failed to clear conversation: {e}")
            return 0
        finally:
            db.close()

    @staticmethod
    def clear_user_all_history(
            user_id: int = None,
            telegram_user_id: int = None,
            confirm: bool = False
    ) -> int:
        """
        清空指定用户的所有聊天记录

        Args:
            user_id: 数据库用户ID
            telegram_user_id: Telegram用户ID
            confirm: 是否跳过确认

        Returns:
            int: 删除的记录数
        """
        db = get_db_session()
        try:
            # 解析用户
            user = None
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
            elif telegram_user_id:
                user = db.query(User).filter(User.telegram_id == telegram_user_id).first()

            if not user:
                print(f"❌ 用户不存在")
                return 0

            # 查询记录数
            count = db.query(Conversation).filter(Conversation.user_id == user.id).count()

            if count == 0:
                print(f"ℹ️  用户 @{user.username} 没有聊天记录")
                return 0

            if not confirm:
                print(f"\n⚠️  将删除用户 @{user.username} 的所有 {count} 条聊天记录")
                if input("输入 'yes' 确认: ").lower() != 'yes':
                    print("❌ 已取消")
                    return 0

            # 执行删除
            deleted = db.query(Conversation).filter(Conversation.user_id == user.id).delete()
            db.commit()

            print(f"✅ 已删除 {deleted} 条聊天记录")
            logger.info(f"Cleared all {deleted} conversation records for user {user.id}")
            return deleted

        except Exception as e:
            db.rollback()
            print(f"❌ 删除失败: {e}")
            logger.error(f"Failed to clear conversation: {e}")
            return 0
        finally:
            db.close()

    @staticmethod
    def clear_interactive() -> None:
        """交互式清空聊天记录"""
        print("\n" + "=" * 60)
        print("🧹 清空聊天记录")
        print("=" * 60)

        db = get_db_session()
        try:
            # 列出所有用户
            users = db.query(User).all()
            if not users:
                print("❌ 没有用户数据")
                return

            print("\n👤 选择用户:")
            for u in users:
                print(f"   [{u.id}] @{u.username} | {u.first_name} | TG ID: {u.telegram_id}")

            user_id = int(input("\n请输入用户ID: ").strip())
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                print("❌ 用户不存在")
                return

            # 选择操作
            print("\n选择操作:")
            print("   [1] 清空与指定Bot的聊天记录")
            print("   [2] 清空所有聊天记录")

            choice = input("\n请选择 [1/2]: ").strip()

            if choice == "1":
                # 列出所有Bot
                bots = db.query(Bot).all()
                if not bots:
                    print("❌ 没有Bot数据")
                    return

                print("\n🤖 选择Bot:")
                for b in bots:
                    print(f"   [{b.id}] @{b.bot_username} | {b.bot_name}")

                bot_id = int(input("\n请输入Bot ID: ").strip())

                db.close()
                ConversationCRUD.clear_user_bot_history(user_id=user_id, bot_id=bot_id)

            elif choice == "2":
                db.close()
                ConversationCRUD.clear_user_all_history(user_id=user_id)
            else:
                print("❌ 无效选择")

        except ValueError:
            print("❌ 请输入有效的数字")
        except Exception as e:
            print(f"❌ 操作失败: {e}")
        finally:
            try:
                db.close()
            except:
                pass

    @staticmethod
    def list_user_conversations(user_id: int, limit: int = 20) -> List[Conversation]:
        """
        列出用户的对话记录

        Args:
            user_id: 用户ID
            limit: 返回记录数限制

        Returns:
            List[Conversation]: 对话记录列表
        """
        db = get_db_session()
        try:
            conversations = db.query(Conversation) \
                .filter(Conversation.user_id == user_id) \
                .order_by(Conversation.timestamp.desc()) \
                .limit(limit) \
                .all()
            return conversations
        finally:
            db.close()