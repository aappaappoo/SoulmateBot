#!/usr/bin/env python3
"""
SoulmateBot 数据库管理工具
===========================

功能:
  1. rebuild    - 重建数据库（删除所有表并重新创建）
  2. init       - 初始化测试数据
  3. status     - 查看数据库状态
  4. fix        - 修复数据库结构
  5. clear      - 清空所有数据
  6. bot        - 创建/管理 Bot
  7. bind       - 绑定 Bot 到 Channel
  8. token      - Token/ID 管理（新增）
  9. register   - 批量注册机器人（新增）
  10. all       - 重建 + 初始化

使用方法:
  python scripts/db_manager.py rebuild
  python scripts/db_manager.py init
  python scripts/db_manager.py status
  python scripts/db_manager.py fix
  python scripts/db_manager.py clear
  python scripts/db_manager.py bot           # 创建新 Bot（交互式）
  python scripts/db_manager.py bind          # 绑定 Bot 到 Channel
  python scripts/db_manager.py bind-quick <chat_id> <bot_id> <mode>
  python scripts/db_manager.py token         # Token/ID 管理
  python scripts/db_manager.py token-set <bot_id> <token>  # 快速设置Token
  python scripts/db_manager.py register      # 批量注册机器人
  python scripts/db_manager.py all
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text
from loguru import logger

from src.database import engine, get_db_session
from src.models.database import (
    Base, User, Bot, Channel, ChannelBotMapping,
    Conversation, UsageRecord, Payment, SubscriptionTier, BotStatus
)
from config import settings


class DatabaseManager:
    """数据库管理器"""

    def __init__(self):
        self.engine = engine

    def rebuild(self, confirm: bool = False) -> bool:
        """重建数据库：删除所有表并重新创建"""
        print("\n" + "=" * 60)
        print("🗑️  数据库重建工具")
        print("=" * 60)
        print("\n⚠️  警告：这将删除所有数据！\n")

        if not confirm:
            user_input = input("输入 'yes' 继续:  ")
            if user_input.lower() != 'yes':
                print("❌ 已取消")
                return False

        try:
            print("\n🗑️  正在删除所有表...")
            Base.metadata.drop_all(bind=self.engine)
            print("✅ 所有表已删除")

            print("\n🔨 正在重新创建所有表...")
            Base.metadata.create_all(bind=self.engine)
            print("✅ 所有表已创建完成!")

            self._show_tables()
            return True

        except Exception as e:
            print(f"❌ 重建失败: {e}")
            return False

    def init_test_data(
            self,
            telegram_user_id: int = None,
            username: str = None,
            first_name: str = None,
            last_name: str = None,
            bot_username: str = None
    ) -> bool:
        """初始化测试数据"""
        print("\n" + "=" * 60)
        print("📦 初始化测试数据")
        print("=" * 60)

        if telegram_user_id is None:
            telegram_user_id = int(input("\n请输入你的 Telegram User ID: "))
        if username is None:
            username = input("请输入你的 Telegram 用户名 (不含@): ")
        if first_name is None:
            first_name = input("请输入你的名字: ")
        if last_name is None:
            last_name = input("请输入你的姓氏 (可选，直接回车跳过): ") or None
        if bot_username is None:
            bot_username = input("请输入 Bot 用户名 (不含@): ")

        db = get_db_session()

        try:
            # 1. 创建用户
            print("\n👤 创建用户...")
            user = User(
                telegram_id=telegram_user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                subscription_tier=SubscriptionTier.FREE.value,
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"   ✅ 用户已创建: ID={user.id}, telegram_id={user.telegram_id}")

            # 2. 创建 Bot
            print("\n🤖 创建 Bot...")
            bot = Bot(
                bot_token=settings.telegram_bot_token,
                bot_name=bot_username,
                bot_username=bot_username,
                description="智能情感陪伴助手",
                personality="温柔、善解人意、有耐心",
                system_prompt="""你是一个温柔、善解人意的情感陪伴助手。
你的任务是倾听用户的心声，提供情感支持和陪伴。
请用温暖、关怀的语气回复，让用户感受到被理解和支持。
回复要自然、真诚，避免机械化的回答。""",
                ai_model=settings.openai_model if settings.openai_api_key else settings.vllm_model,
                ai_provider="openai" if settings.openai_api_key else "vllm",
                created_by=user.id,
                is_public=True,
                status=BotStatus.ACTIVE.value
            )
            db.add(bot)
            db.commit()
            db.refresh(bot)
            print(f"   ✅ Bot 已创建: ID={bot.id}, @{bot.bot_username}")

            # 3. 创建私聊 Channel
            print("\n💬 创建私聊 Channel...")
            private_channel = Channel(
                telegram_chat_id=telegram_user_id,
                chat_type="private",
                title=f"{first_name} 的私聊",
                owner_id=user.id,
                subscription_tier=SubscriptionTier.FREE.value,
                is_active=True
            )
            db.add(private_channel)
            db.commit()
            db.refresh(private_channel)
            print(f"   ✅ 私聊 Channel 已创建: ID={private_channel.id}")

            # 4. 绑定 Bot 到私聊 Channel
            print("\n🔗 绑定 Bot 到私聊 Channel...")
            mapping = ChannelBotMapping(
                channel_id=private_channel.id,
                bot_id=bot.id,
                is_active=True,
                priority=0,
                routing_mode="auto",
                keywords=[],
                settings={}
            )
            db.add(mapping)
            db.commit()
            print(f"   ✅ 绑定完成: Channel {private_channel.id} <-> Bot {bot.id} (mode: auto)")

            print("\n" + "=" * 60)
            print("🎉 初始化完成！")
            print("=" * 60)
            print(f"""
📋 创建的数据: 
   👤 用户: {user.username} (ID: {user.id})
   🤖 Bot: @{bot.bot_username} (ID: {bot.id})
   💬 Channel: 私聊 (ID: {private_channel.id})
   🔗 绑定: 自动回复模式 (auto)

🚀 现在可以在 Telegram 私聊中与 @{bot.bot_username} 对话了！

⚠️  如果需要在频道中使用，请运行: 
   python scripts/db_manager.py bind
""")
            return True

        except Exception as e:
            db.rollback()
            print(f"❌ 初始化失败: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            db.close()

    def create_bot(self) -> bool:
        """
        创建新的 Bot 记录

        用于将从 BotFather 创建的新机器人添加到数据库中
        """
        print("\n" + "=" * 60)
        print("🤖 创建新 Bot")
        print("=" * 60)

        db = get_db_session()

        try:
            # 1. 检查是否有用户，没有则先创建
            users = db.query(User).all()
            if not users:
                print("\n⚠️  数据库中没有用户，需要先创建一个用户")
                telegram_user_id = int(input("请输入你的 Telegram User ID: "))
                username = input("请输入你的 Telegram 用户名 (不含@): ")
                first_name = input("请输入你的名字: ")

                user = User(
                    telegram_id=telegram_user_id,
                    username=username,
                    first_name=first_name,
                    subscription_tier=SubscriptionTier.FREE.value,
                    is_active=True
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                print(f"   ✅ 用户已创建:  ID={user.id}")
            else:
                print("\n👤 选择 Bot 的创建者:")
                for u in users:
                    print(f"   [{u.id}] @{u.username} - {u.first_name}")
                user_id = int(input("\n请输入用户 ID: "))
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    print(f"❌ 用户 ID {user_id} 不存在")
                    return False

            # 2. 获取 Bot 信息
            print("\n📝 请输入 Bot 信息:")
            print("   (这些信息来自 BotFather 创建机器人时获取的)")

            bot_token = input("\n请输入 Bot Token (从 BotFather 获取): ").strip()
            if not bot_token:
                print("   使用 . env 中的 TELEGRAM_BOT_TOKEN")
                bot_token = settings.telegram_bot_token

            bot_username = input("请输入 Bot 用户名 (不含@，如 Solin_AI_Bot): ").strip()
            if not bot_username:
                print("❌ Bot 用户名不能为空")
                return False

            bot_name = input(f"请输入 Bot 显示名称 (直接回车使用 {bot_username}): ").strip()
            if not bot_name:
                bot_name = bot_username

            description = input("请输入 Bot 描述 (可选): ").strip() or "智能情感陪伴助手"

            print("\n🧠 选择 AI 提供商:")
            print("   [1] OpenAI (GPT-4)")
            print("   [2] Anthropic (Claude)")
            print("   [3] vLLM (自托管)")
            ai_choice = input("请选择 (1/2/3，默认1): ").strip() or "1"

            ai_provider_map = {"1": "openai", "2": "anthropic", "3": "vllm"}
            ai_provider = ai_provider_map.get(ai_choice, "openai")

            if ai_provider == "openai":
                ai_model = input(f"请输入模型名称 (默认 {settings.openai_model}): ").strip() or settings.openai_model
            elif ai_provider == "anthropic":
                ai_model = input(
                    f"请输入模型名称 (默认 {settings.anthropic_model}): ").strip() or settings.anthropic_model
            else:
                ai_model = input(f"请输入模型名称 (默认 {settings.vllm_model}): ").strip() or settings.vllm_model

            print("\n📌 请输入 System Prompt (机器人的人设):")
            print("   直接回车使用默认的情感陪伴助手人设")
            print("   输入多行后，单独输入 'END' 结束")

            lines = []
            first_line = input("> ")
            if first_line.strip():
                lines.append(first_line)
                while True:
                    line = input("> ")
                    if line.strip().upper() == 'END':
                        break
                    lines.append(line)
                system_prompt = "\n".join(lines)
            else:
                system_prompt = """你是一个温柔、善解人意的情感陪伴助手。
你的任务是倾听用户的心声，提供情感支持和陪伴。
请用温暖、关怀的语气回复，让用户感受到被理解和支持。
回复要自然、真诚，避免机械化的回答。"""

            # 3. 检查 Bot 是否已存在
            existing_bot = db.query(Bot).filter(Bot.bot_username == bot_username).first()
            if existing_bot:
                print(f"\n⚠️  Bot @{bot_username} 已存在 (ID: {existing_bot.id})")
                update = input("是否更新这个 Bot 的信息? (yes/no): ")
                if update.lower() == 'yes':
                    existing_bot.bot_token = bot_token
                    existing_bot.bot_name = bot_name
                    existing_bot.description = description
                    existing_bot.ai_provider = ai_provider
                    existing_bot.ai_model = ai_model
                    existing_bot.system_prompt = system_prompt
                    db.commit()
                    print(f"   ✅ Bot 已更新:  ID={existing_bot.id}")
                    return True
                else:
                    return False

            # 4. 创建 Bot
            bot = Bot(
                bot_token=bot_token,
                bot_name=bot_name,
                bot_username=bot_username,
                description=description,
                personality="温柔、善解人意、有耐心",
                system_prompt=system_prompt,
                ai_model=ai_model,
                ai_provider=ai_provider,
                created_by=user.id,
                is_public=True,
                status=BotStatus.ACTIVE.value
            )
            db.add(bot)
            db.commit()
            db.refresh(bot)

            print("\n" + "=" * 60)
            print("✅ Bot 创建成功！")
            print("=" * 60)
            print(f"""
📋 Bot 详情:
   🆔 ID: {bot.id}
   🤖 用户名: @{bot.bot_username}
   📛 名称: {bot.bot_name}
   🧠 AI:  {bot.ai_provider} / {bot.ai_model}
   👤 创建者: {user.username} (ID: {user.id})

💡 下一步: 
   1. 将此 Bot 绑定到 Channel: 
      python scripts/db_manager.py bind

   2. 或使用快速绑定:
      python scripts/db_manager.py bind-quick <chat_id> {bot.id} mention
""")
            return True

        except Exception as e:
            db.rollback()
            print(f"❌ 创建失败:  {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            db.close()

    def manage_bot(self) -> None:
        """Bot 管理菜单"""
        print("\n" + "=" * 60)
        print("🤖 Bot 管理")
        print("=" * 60)

        print("\n选择操作:")
        print("   [1] 创建新 Bot")
        print("   [2] 查看所有 Bot")
        print("   [3] 更新 Bot 信息")
        print("   [4] 删除 Bot")

        choice = input("\n请选择 (1/2/3/4): ").strip()

        if choice == "1":
            self.create_bot()
        elif choice == "2":
            self._list_bots()
        elif choice == "3":
            self._update_bot()
        elif choice == "4":
            self._delete_bot()
        else:
            print("❌ 无效选择")

    def _list_bots(self) -> None:
        """列出所有 Bot"""
        db = get_db_session()
        try:
            bots = db.query(Bot).all()
            if not bots:
                print("\n📭 没有任何 Bot")
                return

            print("\n🤖 Bot 列表:")
            print("-" * 80)
            for b in bots:
                # 获取绑定数量
                binding_count = db.query(ChannelBotMapping).filter(
                    ChannelBotMapping.bot_id == b.id,
                    ChannelBotMapping.is_active == True
                ).count()

                print(f"""
   ID: {b.id}
   用户名: @{b.bot_username}
   名称: {b.bot_name}
   描述: {b.description or '(无)'}
   AI:  {b.ai_provider} / {b.ai_model}
   状态: {b.status}
   绑定的 Channel 数: {binding_count}
   创建时间: {b.created_at}
""")
                print("-" * 80)
        finally:
            db.close()

    def _update_bot(self) -> bool:
        """更新 Bot 信息"""
        db = get_db_session()
        try:
            self._list_bots()
            bot_id = int(input("\n请输入要更新的 Bot ID: "))
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                print(f"❌ Bot ID {bot_id} 不存在")
                return False

            print(f"\n正在更新 @{bot.bot_username}")
            print("(直接回车保持原值不变)\n")

            new_name = input(f"名称 [{bot.bot_name}]:  ").strip()
            if new_name:
                bot.bot_name = new_name

            new_desc = input(f"描述 [{bot.description}]: ").strip()
            if new_desc:
                bot.description = new_desc

            new_model = input(f"AI 模型 [{bot.ai_model}]: ").strip()
            if new_model:
                bot.ai_model = new_model

            print("\n更新 System Prompt?  (yes/no)")
            if input().lower() == 'yes':
                print("输入新的 System Prompt (输入 'END' 结束):")
                lines = []
                while True:
                    line = input("> ")
                    if line.strip().upper() == 'END':
                        break
                    lines.append(line)
                if lines:
                    bot.system_prompt = "\n".join(lines)

            db.commit()
            print(f"\n✅ Bot @{bot.bot_username} 已更新")
            return True

        except Exception as e:
            db.rollback()
            print(f"❌ 更新失败: {e}")
            return False
        finally:
            db.close()

    def _delete_bot(self) -> bool:
        """删除 Bot"""
        db = get_db_session()
        try:
            self._list_bots()
            bot_id = int(input("\n请输入要删除的 Bot ID: "))
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                print(f"❌ Bot ID {bot_id} 不存在")
                return False

            print(f"\n⚠️  将删除 @{bot.bot_username} 及其所有绑定关系")
            if input("输入 'yes' 确认: ").lower() != 'yes':
                print("❌ 已取消")
                return False

            # 删除绑定关系
            db.query(ChannelBotMapping).filter(ChannelBotMapping.bot_id == bot_id).delete()
            # 删除 Bot
            db.delete(bot)
            db.commit()

            print(f"✅ Bot @{bot.bot_username} 已删除")
            return True

        except Exception as e:
            db.rollback()
            print(f"❌ 删除失败: {e}")
            return False
        finally:
            db.close()

    def bind_bot_to_channel(self) -> bool:
        """
        绑定 Bot 到 Channel（频道/群组）

        支持的路由模式:
        - mention: 需要 @机器人 才会响应
        - auto: 自动响应所有消息
        - keyword: 根据关键词触发
        """
        print("\n" + "=" * 60)
        print("🔗 绑定 Bot 到 Channel")
        print("=" * 60)

        db = get_db_session()

        try:
            # 1. 显示可用的 Bot
            bots = db.query(Bot).all()
            if not bots:
                print("\n❌ 没有可用的 Bot")
                print("   请先创建 Bot:  python scripts/db_manager.py bot")
                create_now = input("\n是否现在创建?  (yes/no): ")
                if create_now.lower() == 'yes':
                    db.close()
                    if self.create_bot():
                        db = get_db_session()
                        bots = db.query(Bot).all()
                    else:
                        return False
                else:
                    return False

            print("\n🤖 可用的 Bot:")
            for b in bots:
                print(f"   [{b.id}] @{b.bot_username} - {b.bot_name}")

            bot_id = int(input("\n请输入要绑定的 Bot ID: "))
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                print(f"❌ Bot ID {bot_id} 不存在")
                return False

            # 2. 显示已有的 Channel
            channels = db.query(Channel).all()
            print("\n💬 已有的 Channel:")
            if channels:
                for c in channels:
                    # 检查是否已绑定此 Bot
                    is_bound = db.query(ChannelBotMapping).filter(
                        ChannelBotMapping.channel_id == c.id,
                        ChannelBotMapping.bot_id == bot_id
                    ).first()
                    bound_mark = " ✓ (已绑定此Bot)" if is_bound else ""
                    print(f"   [{c.id}] {c.chat_type}:  {c.title or c.telegram_chat_id}{bound_mark}")
            else:
                print("   (无)")

            # 3. 获取 Channel 信息
            print("\n选择操作:")
            print("   [1] 绑定到已有 Channel")
            print("   [2] 创建新 Channel 并绑定")
            choice = input("\n请选择 (1/2): ")

            if choice == "1":
                if not channels:
                    print("❌ 没有已有的 Channel，请选择 2 创建新的")
                    return False
                channel_id = int(input("请输入 Channel ID: "))
                channel = db.query(Channel).filter(Channel.id == channel_id).first()
                if not channel:
                    print(f"❌ Channel ID {channel_id} 不存在")
                    return False
            else:
                # 创建新 Channel
                telegram_chat_id = int(input("请输入 Telegram Chat ID (频道/群组的 ID，通常是负数): "))

                # 检查是否已存在
                existing_channel = db.query(Channel).filter(
                    Channel.telegram_chat_id == telegram_chat_id
                ).first()

                if existing_channel:
                    print(f"   ℹ️  Channel 已存在 (ID: {existing_channel.id})")
                    channel = existing_channel
                else:
                    print("\n选择 Chat 类型:")
                    print("   [1] channel - Telegram 频道")
                    print("   [2] group - 普通群组")
                    print("   [3] supergroup - 超级群组")
                    chat_type_choice = input("请选择 (1/2/3): ")
                    chat_type_map = {"1": "channel", "2": "group", "3": "supergroup"}
                    chat_type = chat_type_map.get(chat_type_choice, "channel")

                    title = input("请输入频道/群组名称:  ")

                    channel = Channel(
                        telegram_chat_id=telegram_chat_id,
                        chat_type=chat_type,
                        title=title,
                        subscription_tier=SubscriptionTier.FREE.value,
                        is_active=True
                    )
                    db.add(channel)
                    db.commit()
                    db.refresh(channel)
                    print(f"   ✅ Channel 已创建:  ID={channel.id}")

            # 4. 检查是否已绑定
            existing = db.query(ChannelBotMapping).filter(
                ChannelBotMapping.channel_id == channel.id,
                ChannelBotMapping.bot_id == bot.id
            ).first()

            if existing:
                print(f"\n⚠️  @{bot.bot_username} 已绑定到此 Channel")
                print(f"   当前模式: {existing.routing_mode}, 活跃: {existing.is_active}")
                update = input("是否更新绑定设置? (yes/no): ")
                if update.lower() != 'yes':
                    return False
                mapping = existing
            else:
                mapping = ChannelBotMapping(
                    channel_id=channel.id,
                    bot_id=bot.id
                )

            # 5. 设置路由模式
            print("\n📌 选择路由模式:")
            print("   [1] mention - 需要 @机器人 才响应 (推荐用于频道/群组)")
            print("   [2] auto    - 自动响应所有消息 (推荐用于私聊)")
            print("   [3] keyword - 根据关键词触发")

            mode_choice = input("\n请选择 (1/2/3，默认1): ").strip() or "1"
            mode_map = {"1": "mention", "2": "auto", "3": "keyword"}
            routing_mode = mode_map.get(mode_choice, "mention")

            # 如果是关键词模式，获取关键词
            keywords = []
            if routing_mode == "keyword":
                kw_input = input("请输入关键词 (用逗号分隔): ")
                keywords = [k.strip() for k in kw_input.split(",") if k.strip()]

            # 6. 设置优先级
            priority = int(input("请输入优先级 (数字越大越优先，默认0): ") or "0")

            # 7. 保存绑定
            mapping.is_active = True
            mapping.routing_mode = routing_mode
            mapping.priority = priority
            mapping.keywords = keywords

            if not existing:
                db.add(mapping)

            db.commit()

            print("\n" + "=" * 60)
            print("✅ 绑定成功！")
            print("=" * 60)
            print(f"""
📋 绑定详情:
   🤖 Bot: @{bot.bot_username} (ID: {bot.id})
   💬 Channel: {channel.title or channel.telegram_chat_id} (ID: {channel.id})
   📌 路由模式: {routing_mode}
   🔢 优先级: {priority}
   🔑 关键词: {keywords if keywords else '(无)'}

💡 使用提示:
""")
            if routing_mode == "mention":
                print(f"   在频道中发送 @{bot.bot_username} 消息内容 即可触发回复")
            elif routing_mode == "auto":
                print(f"   Bot 将自动回复频道中的所有消息")
            else:
                print(f"   发送包含关键词 {keywords} 的消息即可触发回复")

            return True

        except Exception as e:
            db.rollback()
            print(f"❌ 绑定失败: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            db.close()

    def quick_bind_channel(self, telegram_chat_id: int, bot_id: int = 1, routing_mode: str = "mention") -> bool:
        """快速绑定频道"""
        print(f"\n🔗 快速绑定:  Chat ID {telegram_chat_id} -> Bot {bot_id} ({routing_mode})")

        db = get_db_session()

        try:
            # 获取 Bot
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                print(f"❌ Bot ID {bot_id} 不存在")
                print("\n可用的 Bot:")
                for b in db.query(Bot).all():
                    print(f"   [{b.id}] @{b.bot_username}")
                return False

            # 获取或创建 Channel
            channel = db.query(Channel).filter(
                Channel.telegram_chat_id == telegram_chat_id
            ).first()

            if not channel:
                print(f"❌ Channel (chat_id={telegram_chat_id}) 不存在")
                print("   请先在该频道中发送一条消息让 Bot 自动创建 Channel")
                return False

            # 检查是否已绑定
            existing = db.query(ChannelBotMapping).filter(
                ChannelBotMapping.channel_id == channel.id,
                ChannelBotMapping.bot_id == bot.id
            ).first()

            if existing:
                existing.is_active = True
                existing.routing_mode = routing_mode
                print(f"   ✅ 更新绑定:  {routing_mode}")
            else:
                mapping = ChannelBotMapping(
                    channel_id=channel.id,
                    bot_id=bot.id,
                    is_active=True,
                    routing_mode=routing_mode,
                    priority=0,
                    keywords=[]
                )
                db.add(mapping)
                print(f"   ✅ 创建绑定: {routing_mode}")

            db.commit()
            print(f"✅ @{bot.bot_username} 已绑定到 {channel.title or channel.telegram_chat_id}")
            return True

        except Exception as e:
            db.rollback()
            print(f"❌ 绑定失败:  {e}")
            return False

        finally:
            db.close()

    def status(self) -> None:
        """显示数据库状态"""
        print("\n" + "=" * 60)
        print("📊 数据库状态")
        print("=" * 60)

        self._show_tables()

        db = get_db_session()
        try:
            print("\n📈 数据统计:")
            print(f"   👤 用户数: {db.query(User).count()}")
            print(f"   🤖 Bot 数: {db.query(Bot).count()}")
            print(f"   💬 Channel 数: {db.query(Channel).count()}")
            print(f"   🔗 绑定数:  {db.query(ChannelBotMapping).count()}")
            print(f"   💭 对话数: {db.query(Conversation).count()}")

            print("\n" + "-" * 60)
            print("📋 详细数据:")

            users = db.query(User).all()
            if users:
                print("\n   👤 用户列表:")
                for u in users:
                    print(f"      [{u.id}] @{u.username} | {u.first_name} | tier:{u.subscription_tier}")

            bots = db.query(Bot).all()
            if bots:
                print("\n   🤖 Bot 列表:")
                for b in bots:
                    print(f"      [{b.id}] @{b.bot_username} | {b.bot_name} | {b.ai_provider}/{b.ai_model}")

            channels = db.query(Channel).all()
            if channels:
                print("\n   💬 Channel 列表:")
                for c in channels:
                    print(f"      [{c.id}] {c.chat_type}:  {c.title or '(无标题)'} | chat_id:{c.telegram_chat_id}")

            mappings = db.query(ChannelBotMapping).all()
            if mappings:
                print("\n   🔗 绑定列表:")
                for m in mappings:
                    bot = db.query(Bot).filter(Bot.id == m.bot_id).first()
                    channel = db.query(Channel).filter(Channel.id == m.channel_id).first()
                    bot_name = f"@{bot.bot_username}" if bot else f"Bot#{m.bot_id}"
                    channel_name = channel.title or str(
                        channel.telegram_chat_id) if channel else f"Channel#{m.channel_id}"
                    status = "✅" if m.is_active else "❌"
                    print(f"      {status} {channel_name} <-> {bot_name} | mode:{m.routing_mode}")

        finally:
            db.close()

    def fix_schema(self) -> bool:
        """修复数据库结构"""
        print("\n" + "=" * 60)
        print("🔧 修复数据库结构")
        print("=" * 60)

        inspector = inspect(self.engine)

        schema_fixes = {
            'users': [('uuid', 'VARCHAR(36)'), ('version', 'INTEGER DEFAULT 1')],
            'bots': [('uuid', 'VARCHAR(36)'), ('version', 'INTEGER DEFAULT 1')],
            'channels': [('version', 'INTEGER DEFAULT 1')],
            'channel_bot_mappings': [('version', 'INTEGER DEFAULT 1')],
        }

        try:
            with self.engine.connect() as conn:
                for table_name, columns in schema_fixes.items():
                    if table_name not in inspector.get_table_names():
                        continue

                    existing_cols = [col['name'] for col in inspector.get_columns(table_name)]

                    for col_name, col_type in columns:
                        if col_name not in existing_cols:
                            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))
                            print(f"   ✅ {table_name}. {col_name} 已添加")

                conn.commit()

            print("\n✅ 数据库结构修复完成!")
            return True

        except Exception as e:
            print(f"❌ 修复失败: {e}")
            return False

    def clear_data(self, confirm: bool = False) -> bool:
        """清空所有数据"""
        print("\n" + "=" * 60)
        print("🧹 清空数据")
        print("=" * 60)

        if not confirm:
            if input("\n输入 'yes' 继续:  ").lower() != 'yes':
                print("❌ 已取消")
                return False

        db = get_db_session()
        try:
            db.query(ChannelBotMapping).delete()
            db.query(Conversation).delete()
            db.query(UsageRecord).delete()
            db.query(Payment).delete()
            db.query(Channel).delete()
            db.query(Bot).delete()
            db.query(User).delete()
            db.commit()
            print("✅ 所有数据已清空!")
            return True
        except Exception as e:
            db.rollback()
            print(f"❌ 清空失败: {e}")
            return False
        finally:
            db.close()

    def _show_tables(self) -> None:
        """显示所有表"""
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        print(f"\n📋 数据库中的表 ({len(tables)} 个):")
        for table in tables:
            cols = [col['name'] for col in inspector.get_columns(table)]
            print(f"   • {table}:  {len(cols)} 列")

    # ======================================
    # Token/ID 管理功能
    # ======================================
    
    def manage_token(self) -> None:
        """
        Token/ID 管理菜单
        
        管理机器人的 Token 绑定，不涉及人设配置
        """
        print("\n" + "=" * 60)
        print("🔑 Token/ID 管理")
        print("=" * 60)
        
        print("\n选择操作:")
        print("   [1] 查看所有 Bot Token")
        print("   [2] 设置/更新 Bot Token")
        print("   [3] 验证 Token 有效性")
        print("   [4] 批量导入 Token")
        
        choice = input("\n请选择 (1/2/3/4): ").strip()
        
        if choice == "1":
            self._list_tokens()
        elif choice == "2":
            self._set_token()
        elif choice == "3":
            self._validate_tokens()
        elif choice == "4":
            self._batch_import_tokens()
        else:
            print("❌ 无效选择")
    
    def _list_tokens(self) -> None:
        """列出所有 Bot 的 Token 信息"""
        db = get_db_session()
        try:
            bots = db.query(Bot).all()
            if not bots:
                print("\n📭 没有任何 Bot")
                return
            
            print("\n🔑 Bot Token 列表:")
            print("-" * 80)
            for b in bots:
                # 隐藏 Token 中间部分
                token = b.bot_token
                if token and len(token) > 20:
                    masked_token = token[:10] + "..." + token[-10:]
                else:
                    masked_token = token or "(未设置)"
                
                print(f"""
   ID: {b.id}
   用户名: @{b.bot_username}
   名称: {b.bot_name}
   Token: {masked_token}
   状态: {b.status}
""")
                print("-" * 80)
        finally:
            db.close()
    
    def _set_token(self) -> bool:
        """设置或更新 Bot Token"""
        db = get_db_session()
        try:
            # 显示所有 Bot
            bots = db.query(Bot).all()
            if not bots:
                print("\n❌ 没有任何 Bot，请先创建 Bot")
                return False
            
            print("\n🤖 可用的 Bot:")
            for b in bots:
                print(f"   [{b.id}] @{b.bot_username} - {b.bot_name}")
            
            bot_id = int(input("\n请输入 Bot ID: "))
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                print(f"❌ Bot ID {bot_id} 不存在")
                return False
            
            print(f"\n正在更新 @{bot.bot_username} 的 Token")
            new_token = input("请输入新的 Bot Token (从 BotFather 获取): ").strip()
            
            if not new_token:
                print("❌ Token 不能为空")
                return False
            
            # 验证 Token 格式
            if ':' not in new_token:
                print("⚠️  Token 格式可能不正确 (应包含 ':')")
                if input("是否继续? (yes/no): ").lower() != 'yes':
                    return False
            
            bot.bot_token = new_token
            db.commit()
            
            print(f"\n✅ Token 已更新: @{bot.bot_username}")
            return True
            
        except Exception as e:
            db.rollback()
            print(f"❌ 更新失败: {e}")
            return False
        finally:
            db.close()
    
    def quick_set_token(self, bot_id: int, token: str) -> bool:
        """
        快速设置 Token (命令行模式)
        
        Args:
            bot_id: Bot ID
            token: Telegram Bot Token
        """
        print(f"\n🔑 快速设置 Token: Bot {bot_id}")
        
        db = get_db_session()
        try:
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                print(f"❌ Bot ID {bot_id} 不存在")
                return False
            
            bot.bot_token = token
            db.commit()
            
            print(f"✅ Token 已设置: @{bot.bot_username}")
            return True
            
        except Exception as e:
            db.rollback()
            print(f"❌ 设置失败: {e}")
            return False
        finally:
            db.close()
    
    def _validate_tokens(self) -> None:
        """验证所有 Bot Token 的有效性"""
        print("\n🔍 验证 Token 有效性...")
        print("   (此功能需要网络连接)\n")
        
        try:
            import requests
        except ImportError:
            print("❌ 需要安装 requests 库")
            return
        
        db = get_db_session()
        try:
            bots = db.query(Bot).all()
            
            for bot in bots:
                if not bot.bot_token:
                    print(f"   ⚠️  @{bot.bot_username}: Token 未设置")
                    continue
                
                try:
                    # 使用 Telegram API 验证 Token
                    url = f"https://api.telegram.org/bot{bot.bot_token}/getMe"
                    response = requests.get(url, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('ok'):
                            api_username = data['result'].get('username', '')
                            print(f"   ✅ @{bot.bot_username}: Token 有效 (API: @{api_username})")
                        else:
                            print(f"   ❌ @{bot.bot_username}: Token 无效")
                    else:
                        print(f"   ❌ @{bot.bot_username}: Token 无效 (HTTP {response.status_code})")
                        
                except Exception as e:
                    print(f"   ⚠️  @{bot.bot_username}: 验证失败 ({e})")
                    
        finally:
            db.close()
    
    def _batch_import_tokens(self) -> bool:
        """批量导入 Token"""
        print("\n📥 批量导入 Token")
        print("-" * 60)
        print("格式说明：每行一个 Token，格式为:")
        print("   bot_username,token")
        print("   或")
        print("   bot_id,token")
        print("\n示例:")
        print("   my_bot,123456:ABC-DEF1234")
        print("   1,789012:GHI-JKL5678")
        print("\n输入 Token 列表 (输入 'END' 结束):")
        
        lines = []
        while True:
            line = input("> ").strip()
            if line.upper() == 'END':
                break
            if line:
                lines.append(line)
        
        if not lines:
            print("❌ 没有输入任何 Token")
            return False
        
        db = get_db_session()
        try:
            success_count = 0
            for line in lines:
                parts = line.split(',')
                if len(parts) != 2:
                    print(f"   ⚠️  格式错误: {line}")
                    continue
                
                identifier, token = parts[0].strip(), parts[1].strip()
                
                # 判断是 ID 还是 username
                try:
                    bot_id = int(identifier)
                    bot = db.query(Bot).filter(Bot.id == bot_id).first()
                except ValueError:
                    # 是 username
                    bot = db.query(Bot).filter(Bot.bot_username == identifier).first()
                
                if not bot:
                    print(f"   ⚠️  Bot 不存在: {identifier}")
                    continue
                
                bot.bot_token = token
                success_count += 1
                print(f"   ✅ @{bot.bot_username}: Token 已更新")
            
            db.commit()
            print(f"\n✅ 批量导入完成: {success_count}/{len(lines)} 成功")
            return True
            
        except Exception as e:
            db.rollback()
            print(f"❌ 批量导入失败: {e}")
            return False
        finally:
            db.close()
    
    # ======================================
    # 批量注册机器人功能
    # ======================================
    
    def batch_register_bots(self) -> bool:
        """
        批量注册机器人
        
        从 bots/ 目录中自动发现并注册所有机器人到数据库
        仅处理 Token 和基本信息，人设配置由代码中的 config.yaml 决定
        """
        print("\n" + "=" * 60)
        print("📦 批量注册机器人")
        print("=" * 60)
        
        import yaml
        from pathlib import Path
        
        # 获取 bots 目录
        project_root = Path(__file__).parent.parent
        bots_dir = project_root / "bots"
        
        if not bots_dir.exists():
            print(f"❌ bots 目录不存在: {bots_dir}")
            return False
        
        # 发现所有 bot 目录
        bot_dirs = [d for d in bots_dir.iterdir() 
                    if d.is_dir() and (d / "config.yaml").exists()]
        
        print(f"\n🔍 发现 {len(bot_dirs)} 个机器人配置:")
        for bot_dir in bot_dirs:
            print(f"   • {bot_dir.name}")
        
        if not bot_dirs:
            print("❌ 没有发现任何机器人配置")
            return False
        
        print("\n选择操作:")
        print("   [1] 注册所有机器人")
        print("   [2] 选择性注册")
        
        choice = input("\n请选择 (1/2): ").strip()
        
        if choice == "2":
            print("\n输入要注册的机器人 ID (用逗号分隔):")
            selected = input("> ").strip().split(',')
            selected = [s.strip() for s in selected if s.strip()]
            bot_dirs = [d for d in bot_dirs if d.name in selected]
        
        if not bot_dirs:
            print("❌ 没有选择任何机器人")
            return False
        
        # 获取创建者用户
        db = get_db_session()
        try:
            users = db.query(User).all()
            if not users:
                print("\n⚠️  数据库中没有用户，需要先创建一个用户")
                telegram_user_id = int(input("请输入你的 Telegram User ID: "))
                username = input("请输入你的 Telegram 用户名 (不含@): ")
                first_name = input("请输入你的名字: ")
                
                user = User(
                    telegram_id=telegram_user_id,
                    username=username,
                    first_name=first_name,
                    subscription_tier=SubscriptionTier.FREE.value,
                    is_active=True
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                print(f"   ✅ 用户已创建: ID={user.id}")
            else:
                print("\n👤 选择创建者:")
                for u in users:
                    print(f"   [{u.id}] @{u.username} - {u.first_name}")
                user_id = int(input("\n请输入用户 ID: ") or str(users[0].id))
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    user = users[0]
            
            # 注册每个机器人
            success_count = 0
            for bot_dir in bot_dirs:
                try:
                    config_file = bot_dir / "config.yaml"
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                    
                    bot_config = config.get('bot', {})
                    bot_username = bot_config.get('username', bot_dir.name)
                    bot_name = bot_config.get('name', bot_username)
                    description = bot_config.get('description', '')
                    
                    # 检查是否已存在
                    existing = db.query(Bot).filter(Bot.bot_username == bot_username).first()
                    if existing:
                        print(f"   ⚠️  @{bot_username} 已存在 (ID: {existing.id})")
                        continue
                    
                    # AI 配置
                    ai_config = config.get('ai', {})
                    ai_provider = ai_config.get('provider', 'openai')
                    ai_model = ai_config.get('model', 'gpt-4')
                    
                    # 获取系统提示词
                    prompt_config = config.get('prompt', {})
                    system_prompt = prompt_config.get('custom', f"你是 {bot_name}。{description}")
                    
                    # 人设配置
                    personality_config = config.get('personality', {})
                    personality = ', '.join(personality_config.get('traits', []))
                    
                    # 创建 Bot
                    bot = Bot(
                        bot_token=f"PLACEHOLDER_{bot_username}",  # 占位符，需要后续设置
                        bot_name=bot_name,
                        bot_username=bot_username,
                        description=description,
                        personality=personality,
                        system_prompt=system_prompt,
                        ai_model=ai_model,
                        ai_provider=ai_provider,
                        created_by=user.id,
                        is_public=bot_config.get('is_public', True),
                        status=BotStatus.ACTIVE.value
                    )
                    db.add(bot)
                    db.commit()
                    db.refresh(bot)
                    
                    print(f"   ✅ @{bot_username} 已注册 (ID: {bot.id})")
                    success_count += 1
                    
                except Exception as e:
                    print(f"   ❌ {bot_dir.name} 注册失败: {e}")
            
            print("\n" + "=" * 60)
            print(f"📊 注册结果: {success_count}/{len(bot_dirs)} 成功")
            print("=" * 60)
            
            if success_count > 0:
                print("""
💡 下一步:
   1. 在 BotFather 中创建对应的 Telegram Bot
   2. 获取每个 Bot 的 Token
   3. 使用以下命令设置 Token:
      python scripts/db_manager.py token
      或
      python scripts/db_manager.py token-set <bot_id> <token>
""")
            
            return success_count > 0
            
        except Exception as e:
            db.rollback()
            print(f"❌ 批量注册失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            db.close()


def main():
    """主函数"""
    manager = DatabaseManager()

    if len(sys.argv) < 2:
        print(__doc__)
        print("\n📌 常用命令:")
        print("   python scripts/db_manager.py status              # 查看数据库状态")
        print("   python scripts/db_manager.py bot                 # 创建/管理 Bot")
        print("   python scripts/db_manager.py bind                # 绑定 Bot 到 Channel")
        print("   python scripts/db_manager.py token               # Token/ID 管理")
        print("   python scripts/db_manager.py register            # 批量注册机器人")
        print("   python scripts/db_manager.py bind-quick <chat_id> <bot_id> <mode>")
        print("   python scripts/db_manager.py token-set <bot_id> <token>")
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == 'rebuild':
        manager.rebuild()
    elif command == 'init':
        manager.init_test_data()
    elif command == 'status':
        manager.status()
    elif command == 'fix':
        manager.fix_schema()
    elif command == 'clear':
        manager.clear_data()
    elif command == 'bot':
        manager.manage_bot()
    elif command == 'bind':
        manager.bind_bot_to_channel()
    elif command == 'bind-quick':
        if len(sys.argv) >= 3:
            chat_id = int(sys.argv[2])
            bot_id = int(sys.argv[3]) if len(sys.argv) > 3 else 1
            mode = sys.argv[4] if len(sys.argv) > 4 else "mention"
            manager.quick_bind_channel(chat_id, bot_id, mode)
        else:
            print("用法: python scripts/db_manager.py bind-quick <chat_id> [bot_id] [mode]")
    elif command == 'token':
        manager.manage_token()
    elif command == 'token-set':
        if len(sys.argv) >= 4:
            bot_id = int(sys.argv[2])
            token = sys.argv[3]
            manager.quick_set_token(bot_id, token)
        else:
            print("用法: python scripts/db_manager.py token-set <bot_id> <token>")
    elif command == 'register':
        manager.batch_register_bots()
    elif command == 'all':
        if manager.rebuild(confirm=False):
            manager.init_test_data()
    else:
        print(f"❌ 未知命令: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()