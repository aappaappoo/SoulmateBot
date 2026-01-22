#!/usr/bin/env python3
"""
Channel-Bot映射管理
===================

提供Channel和Bot绑定关系的管理操作。
"""

import sys
import os
from typing import Optional, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import get_db_session
from src.models.database import Channel, Bot, ChannelBotMapping, SubscriptionTier


class MappingCRUD:
    """
    Channel-Bot映射管理类

    提供映射关系的所有数据库操作:
    - bind:  绑定Bot到Channel
    - unbind:  解绑Bot
    - list:  列出所有映射
    - update: 更新映射配置
    """

    # ==================== BIND (CREATE) ====================

    @staticmethod
    def bind(
            channel_id: int,
            bot_id: int,
            routing_mode: str = "mention",
            priority: int = 0,
            keywords: List[str] = None,
            is_active: bool = True
    ) -> Optional[ChannelBotMapping]:
        """
        绑定Bot到Channel

        Args:
            channel_id: Channel数据库ID
            bot_id: Bot数据库ID
            routing_mode: 路由模式(mention/auto/keyword)
            priority: 优先级
            keywords: 关键词列表
            is_active: 是否激活

        Returns:
            ChannelBotMapping:  创建的映射对象
        """
        db = get_db_session()
        try:
            # 检查Channel和Bot是否存在
            channel = db.query(Channel).filter(Channel.id == channel_id).first()
            if not channel:
                print(f"❌ Channel不存在: ID={channel_id}")
                return None

            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                print(f"❌ Bot不存在: ID={bot_id}")
                return None

            # 检查是否已绑定
            existing = db.query(ChannelBotMapping).filter(
                ChannelBotMapping.channel_id == channel_id,
                ChannelBotMapping.bot_id == bot_id
            ).first()

            if existing:
                # 更新现有绑定
                existing.routing_mode = routing_mode
                existing.priority = priority
                existing.keywords = keywords or []
                existing.is_active = is_active
                db.commit()
                db.refresh(existing)
                print(f"✅ 更新绑定:  {channel.title or channel.telegram_chat_id} <-> @{bot.bot_username}")
                return existing

            # 创建新绑定
            mapping = ChannelBotMapping(
                channel_id=channel_id,
                bot_id=bot_id,
                routing_mode=routing_mode,
                priority=priority,
                keywords=keywords or [],
                is_active=is_active,
                settings={}
            )
            db.add(mapping)
            db.commit()
            db.refresh(mapping)
            print(f"✅ 绑定成功: {channel.title or channel.telegram_chat_id} <-> @{bot.bot_username}")
            return mapping
        except Exception as e:
            db.rollback()
            print(f"❌ 绑定失败: {e}")
            return None
        finally:
            db.close()

    @staticmethod
    def bind_quick(telegram_chat_id: int, bot_id: int, routing_mode: str = "mention") -> bool:
        """
        快速绑定(通过Telegram Chat ID)

        Args:
            telegram_chat_id:  Telegram聊天ID
            bot_id: Bot数据库ID
            routing_mode: 路由模式

        Returns:
            bool: 绑定是否成功
        """
        db = get_db_session()
        try:
            channel = db.query(Channel).filter(Channel.telegram_chat_id == telegram_chat_id).first()
            if not channel:
                print(f"❌ Channel不存在: chat_id={telegram_chat_id}")
                return False

            db.close()
            return MappingCRUD.bind(channel.id, bot_id, routing_mode) is not None
        finally:
            db.close()

    @staticmethod
    def bind_interactive() -> Optional[ChannelBotMapping]:
        """交互式绑定Bot到Channel"""
        print("\n" + "=" * 60)
        print("🔗 绑定Bot到Channel")
        print("=" * 60)

        db = get_db_session()
        try:
            # 显示可用的Bot
            bots = db.query(Bot).all()
            if not bots:
                print("\n❌ 没有可用的Bot")
                return None

            print("\n🤖 可用的Bot:")
            for b in bots:
                print(f"   [{b.id}] @{b.bot_username} - {b.bot_name}")

            bot_id = int(input("\n请输入Bot ID: "))
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                print(f"❌ Bot不存在: ID={bot_id}")
                return None

            # 显示已有的Channel
            channels = db.query(Channel).all()
            print("\n💬 已有的Channel:")
            if channels:
                for c in channels:
                    # 检查是否已绑定
                    is_bound = db.query(ChannelBotMapping).filter(
                        ChannelBotMapping.channel_id == c.id,
                        ChannelBotMapping.bot_id == bot_id
                    ).first()
                    bound_mark = " ✓ (已绑定)" if is_bound else ""
                    print(f"   [{c.id}] {c.chat_type}:  {c.title or c.telegram_chat_id}{bound_mark}")
            else:
                print("   (无)")

            # 获取Channel
            print("\n选择操作:")
            print("   [1] 绑定到已有Channel")
            print("   [2] 创建新Channel并绑定")
            choice = input("\n请选择 (1/2): ").strip()

            if choice == "1":
                if not channels:
                    print("❌ 没有已有的Channel")
                    return None
                channel_id = int(input("请输入Channel ID: "))
            else:
                # 创建新Channel
                telegram_chat_id = int(input("请输入Telegram Chat ID: "))

                existing = db.query(Channel).filter(Channel.telegram_chat_id == telegram_chat_id).first()
                if existing:
                    print(f"   ℹ️  Channel已存在 (ID:  {existing.id})")
                    channel_id = existing.id
                else:
                    print("\n选择Chat类型:")
                    print("   [1] private - 私聊 (推荐)")
                    print("   [2] group - 普通群组")
                    print("   [3] supergroup - 超级群组")
                    print("   [4] channel - 频道")
                    type_choice = input("请选择 (1/2/3/4, 默认1): ").strip() or "1"
                    type_map = {"1": "private", "2": "group", "3": "supergroup", "4": "channel"}
                    chat_type = type_map.get(type_choice, "private")

                    # title 改为可选
                    title = input("名称 (可选，直接回车跳过): ").strip() or None

                    channel = Channel(
                        telegram_chat_id=telegram_chat_id,
                        chat_type=chat_type,
                        title=title,  # 可以为 None
                        subscription_tier=SubscriptionTier.FREE.value,
                        is_active=True
                    )
                    db.add(channel)
                    db.commit()
                    db.refresh(channel)
                    print(f"   ✅ Channel已创建: ID={channel.id}")
                    channel_id = channel.id

            # 设置路由模式
            print("\n📌 选择路由模式:")
            print("   [1] mention - 需要@机器人才响应 (推荐用于群组/频道)")
            print("   [2] auto - 自动响应所有消息 (推荐用于私聊)")
            print("   [3] keyword - 根据关键词触发")
            mode_choice = input("\n请选择 (1/2/3, 默认1): ").strip() or "1"
            mode_map = {"1": "mention", "2": "auto", "3": "keyword"}
            routing_mode = mode_map.get(mode_choice, "mention")

            # 关键词
            keywords = []
            if routing_mode == "keyword":
                kw_input = input("请输入关键词 (逗号分隔): ").strip()
                keywords = [k.strip() for k in kw_input.split(",") if k.strip()]

            # 优先级
            priority = int(input("优先级 (默认0): ").strip() or "0")

            db.close()

            return MappingCRUD.bind(
                channel_id=channel_id,
                bot_id=bot_id,
                routing_mode=routing_mode,
                priority=priority,
                keywords=keywords
            )
        except ValueError as e:
            print(f"❌ 输入错误: {e}")
            return None
        finally:
            db.close()

    # ==================== UNBIND (DELETE) ====================

    @staticmethod
    def unbind(channel_id: int, bot_id: int, confirm: bool = False) -> bool:
        """
        解绑Bot与Channel

        Args:
            channel_id: Channel ID
            bot_id: Bot ID
            confirm: 是否跳过确认

        Returns:
            bool: 解绑是否成功
        """
        db = get_db_session()
        try:
            mapping = db.query(ChannelBotMapping).filter(
                ChannelBotMapping.channel_id == channel_id,
                ChannelBotMapping.bot_id == bot_id
            ).first()

            if not mapping:
                print(f"❌ 绑定不存在: Channel={channel_id}, Bot={bot_id}")
                return False

            if not confirm:
                bot = db.query(Bot).filter(Bot.id == bot_id).first()
                channel = db.query(Channel).filter(Channel.id == channel_id).first()
                print(f"\n⚠️  将解绑:  {channel.title or channel.telegram_chat_id} <-> @{bot.bot_username}")
                if input("输入 'yes' 确认: ").lower() != 'yes':
                    print("❌ 已取消")
                    return False

            db.delete(mapping)
            db.commit()
            print(f"✅ 解绑成功")
            return True
        except Exception as e:
            db.rollback()
            print(f"❌ 解绑失败: {e}")
            return False
        finally:
            db.close()

    @staticmethod
    def unbind_interactive() -> bool:
        """
        交互式解绑Bot与Channel

        显示所有绑定关系，让用户选择要解绑的项目

        Returns:
            bool: 解绑是否成功
        """
        print("\n" + "=" * 60)
        print("🔓 解绑Bot与Channel")
        print("=" * 60)

        db = get_db_session()
        try:
            # 获取所有映射关系
            mappings = db.query(ChannelBotMapping).all()

            if not mappings:
                print("\n📭 当前没有任何绑定关系")
                return False

            # 显示所有绑定关系（带序号）
            print(f"\n📋 当前绑定关系 (共 {len(mappings)} 个):\n")
            print("   " + "-" * 56)
            print(f"   {'序号':<6}{'Channel ID':<12}{'Bot ID':<10}{'Channel名称':<20}{'Bot用户名':<15}{'状态':<6}")
            print("   " + "-" * 56)

            mapping_list = []
            for idx, m in enumerate(mappings, 1):
                bot = db.query(Bot).filter(Bot.id == m.bot_id).first()
                channel = db.query(Channel).filter(Channel.id == m.channel_id).first()

                bot_username = f"@{bot.bot_username}" if bot else f"Bot#{m.bot_id}"
                channel_name = (channel.title or str(channel.telegram_chat_id))[
                               : 18] if channel else f"Channel#{m.channel_id}"
                status = "✅ 活跃" if m.is_active else "❌ 停用"

                print(f"   [{idx: <4}] {m.channel_id:<12}{m.bot_id:<10}{channel_name:<20}{bot_username:<15}{status}")

                # 保存映射信息用于后续选择
                mapping_list.append({
                    'index': idx,
                    'channel_id': m.channel_id,
                    'bot_id': m.bot_id,
                    'channel_name': channel_name,
                    'bot_username': bot_username,
                    'routing_mode': m.routing_mode
                })

            print("   " + "-" * 56)

            # 显示详细信息
            print("\n📝 详细信息:")
            for item in mapping_list:
                print(
                    f"   [{item['index']}] {item['channel_name']} <-> {item['bot_username']} (模式: {item['routing_mode']})")

            # 用户选择
            print("\n" + "=" * 60)
            print("请选择要解绑的项目:")
            print("   - 输入序号 (如:  1)")
            print("   - 输入 'all' 解绑所有")
            print("   - 输入 'q' 或 'quit' 取消")
            print("=" * 60)

            choice = input("\n请输入选择: ").strip().lower()

            if choice in ['q', 'quit', '']:
                print("❌ 已取消")
                return False

            if choice == 'all':
                # 解绑所有
                print(f"\n⚠️  将解绑所有 {len(mappings)} 个绑定关系!")
                if input("输入 'yes' 确认: ").lower() != 'yes':
                    print("❌ 已取消")
                    return False

                for m in mappings:
                    db.delete(m)
                db.commit()
                print(f"✅ 已解绑所有 {len(mappings)} 个绑定关系")
                return True

            # 解绑单个
            try:
                idx = int(choice)
                if idx < 1 or idx > len(mapping_list):
                    print(f"❌ 无效的序号: {idx}")
                    return False

                selected = mapping_list[idx - 1]
                channel_id = selected['channel_id']
                bot_id = selected['bot_id']

                print(f"\n⚠️  将解绑:  {selected['channel_name']} <-> {selected['bot_username']}")
                if input("输入 'yes' 确认: ").lower() != 'yes':
                    print("❌ 已取消")
                    return False

                # 执行解绑
                mapping = db.query(ChannelBotMapping).filter(
                    ChannelBotMapping.channel_id == channel_id,
                    ChannelBotMapping.bot_id == bot_id
                ).first()

                if mapping:
                    db.delete(mapping)
                    db.commit()
                    print(f"✅ 解绑成功:  {selected['channel_name']} <-> {selected['bot_username']}")
                    return True
                else:
                    print("❌ 绑定关系不存在")
                    return False

            except ValueError:
                print(f"❌ 无效的输入: {choice}")
                return False

        except Exception as e:
            db.rollback()
            print(f"❌ 解绑失败: {e}")
            return False
        finally:
            db.close()

    # ==================== LIST (READ) ====================

    @staticmethod
    def list_all() -> List[ChannelBotMapping]:
        """列出所有映射"""
        db = get_db_session()
        try:
            return db.query(ChannelBotMapping).all()
        finally:
            db.close()

    @staticmethod
    def list_print() -> None:
        """打印映射列表（详细版本，包含ID信息）"""
        db = get_db_session()
        try:
            mappings = db.query(ChannelBotMapping).all()

            print("\n" + "=" * 60)
            print("🔗 绑定列表")
            print("=" * 60)

            if not mappings:
                print("\n   📭 暂无绑定")
                return

            print(f"\n   共 {len(mappings)} 个绑定:\n")
            print("   " + "-" * 56)
            print(f"   {'Channel ID':<12}{'Bot ID':<10}{'Channel名称':<18}{'Bot用户名': <15}{'状态':<6}")
            print("   " + "-" * 56)

            for m in mappings:
                bot = db.query(Bot).filter(Bot.id == m.bot_id).first()
                channel = db.query(Channel).filter(Channel.id == m.channel_id).first()

                bot_username = f"@{bot.bot_username}" if bot else f"Bot#{m.bot_id}"
                channel_name = (channel.title or str(channel.telegram_chat_id))[
                               :16] if channel else f"Ch#{m.channel_id}"
                status = "✅" if m.is_active else "❌"

                print(f"   {m.channel_id:<12}{m.bot_id:<10}{channel_name:<18}{bot_username:<15}{status}")

            print("   " + "-" * 56)

            # 额外显示详细信息
            print("\n   📝 详细信息:")
            for m in mappings:
                bot = db.query(Bot).filter(Bot.id == m.bot_id).first()
                channel = db.query(Channel).filter(Channel.id == m.channel_id).first()

                bot_name = f"@{bot.bot_username}" if bot else f"Bot#{m.bot_id}"
                channel_name = channel.title or str(channel.telegram_chat_id) if channel else f"Channel#{m.channel_id}"
                status = "✅ 活跃" if m.is_active else "❌ 停用"

                print(f"\n   {status} {channel_name} <-> {bot_name}")
                print(f"       Channel ID: {m.channel_id}")
                print(f"       Bot ID: {m.bot_id}")
                print(f"       路由模式: {m.routing_mode}")
                print(f"       优先级: {m.priority}")
                if m.keywords:
                    print(f"       关键词:  {m.keywords}")
                if channel:
                    print(f"       Chat ID: {channel.telegram_chat_id}")
                    print(f"       Chat类型: {channel.chat_type}")
        finally:
            db.close()

    @staticmethod
    def list_by_channel(channel_id: int) -> List[ChannelBotMapping]:
        """列出Channel的所有绑定"""
        db = get_db_session()
        try:
            return db.query(ChannelBotMapping).filter(
                ChannelBotMapping.channel_id == channel_id
            ).all()
        finally:
            db.close()

    @staticmethod
    def list_by_bot(bot_id: int) -> List[ChannelBotMapping]:
        """列出Bot的所有绑定"""
        db = get_db_session()
        try:
            return db.query(ChannelBotMapping).filter(
                ChannelBotMapping.bot_id == bot_id
            ).all()
        finally:
            db.close()

    # ==================== UPDATE ====================

    @staticmethod
    def update(
            channel_id: int,
            bot_id: int,
            routing_mode: str = None,
            priority: int = None,
            keywords: List[str] = None,
            is_active: bool = None
    ) -> Optional[ChannelBotMapping]:
        """
        更新映射配置

        Args:
            channel_id: Channel ID
            bot_id: Bot ID
            routing_mode: 新路由模式
            priority: 新优先级
            keywords: 新关键词列表
            is_active: 新激活状态

        Returns:
            ChannelBotMapping: 更新后的映射对象
        """
        db = get_db_session()
        try:
            mapping = db.query(ChannelBotMapping).filter(
                ChannelBotMapping.channel_id == channel_id,
                ChannelBotMapping.bot_id == bot_id
            ).first()

            if not mapping:
                print(f"❌ 绑定不存在: Channel={channel_id}, Bot={bot_id}")
                return None

            if routing_mode is not None:
                mapping.routing_mode = routing_mode
            if priority is not None:
                mapping.priority = priority
            if keywords is not None:
                mapping.keywords = keywords
            if is_active is not None:
                mapping.is_active = is_active

            db.commit()
            db.refresh(mapping)
            print(f"✅ 绑定更新成功")
            return mapping
        except Exception as e:
            db.rollback()
            print(f"❌ 更新失败: {e}")
            return None
        finally:
            db.close()

    @staticmethod
    def update_interactive() -> Optional[ChannelBotMapping]:
        """交互式更新映射配置"""
        print("\n" + "=" * 60)
        print("✏️  更新绑定配置")
        print("=" * 60)

        # 先显示所有绑定
        MappingCRUD.list_print()

        db = get_db_session()
        try:
            channel_id = int(input("\n请输入要更新的 Channel ID: "))
            bot_id = int(input("请输入要更新的 Bot ID: "))

            mapping = db.query(ChannelBotMapping).filter(
                ChannelBotMapping.channel_id == channel_id,
                ChannelBotMapping.bot_id == bot_id
            ).first()

            if not mapping:
                print(f"❌ 绑定不存在: Channel={channel_id}, Bot={bot_id}")
                return None

            print(f"\n当前配置:")
            print(f"   路由模式: {mapping.routing_mode}")
            print(f"   优先级: {mapping.priority}")
            print(f"   关键词: {mapping.keywords}")
            print(f"   状态: {'活跃' if mapping.is_active else '停用'}")

            print("\n请输入新配置 (直接回车保持原值):")

            # 路由模式
            print("\n路由模式选项:  mention / auto / keyword")
            new_mode = input(f"新路由模式 [{mapping.routing_mode}]: ").strip()
            if new_mode and new_mode in ['mention', 'auto', 'keyword']:
                routing_mode = new_mode
            else:
                routing_mode = None

            # 优先级
            new_priority = input(f"新优先级 [{mapping.priority}]: ").strip()
            if new_priority:
                try:
                    priority = int(new_priority)
                except ValueError:
                    priority = None
            else:
                priority = None

            # 关键词
            new_keywords = input(
                f"新关键词 (逗号分隔) [{','.join(mapping.keywords) if mapping.keywords else '无'}]: ").strip()
            if new_keywords:
                keywords = [k.strip() for k in new_keywords.split(",") if k.strip()]
            else:
                keywords = None

            # 状态
            new_status = input(
                f"状态 (active/inactive) [{'active' if mapping.is_active else 'inactive'}]: ").strip().lower()
            if new_status == 'active':
                is_active = True
            elif new_status == 'inactive':
                is_active = False
            else:
                is_active = None

            db.close()

            return MappingCRUD.update(
                channel_id=channel_id,
                bot_id=bot_id,
                routing_mode=routing_mode,
                priority=priority,
                keywords=keywords,
                is_active=is_active
            )

        except ValueError as e:
            print(f"❌ 输入错误: {e}")
            return None
        finally:
            db.close()