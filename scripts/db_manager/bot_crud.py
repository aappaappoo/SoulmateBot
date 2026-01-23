#!/usr/bin/env python3
"""
Bot CRUD操作
============

提供Bot的增删改查操作。
"""

import sys
import os
from typing import Optional, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import get_db_session
from src.models.database import Bot, User, ChannelBotMapping, BotStatus, SubscriptionTier
from config import settings


class BotCRUD:
    """
    Bot CRUD操作类
    
    提供Bot管理的所有数据库操作:
    - create: 创建Bot
    - get: 获取Bot
    - list: 列出所有Bot
    - update: 更新Bot
    - delete: 删除Bot
    """

    # ==================== CREATE ====================

    @staticmethod
    def create(
            bot_token: str,
            bot_username: str,
            bot_name: str,
            description: str = "",
            personality: str = "",
            system_prompt: str = "",
            ai_provider: str = "openai",
            ai_model: str = "gpt-4",
            created_by: int = None,
            is_public: bool = True,
            status: str = None
    ) -> Optional[Bot]:
        """
        创建新Bot
        
        Args:
            bot_token: Telegram Bot Token
            bot_username: Bot用户名
            bot_name: Bot显示名称
            description: Bot描述
            personality: 人设特征
            system_prompt: 系统提示词
            ai_provider: AI提供商
            ai_model: AI模型
            created_by: 创建者用户ID
            is_public: 是否公开
            status: Bot状态
            
        Returns:
            Bot: 创建的Bot对象，失败返回None
        """
        db = get_db_session()
        try:
            # 检查是否已存在
            existing = db.query(Bot).filter(Bot.bot_username == bot_username).first()
            if existing:
                print(f"⚠️  Bot已存在: @{bot_username} (ID={existing.id})")
                return existing

            bot = Bot(
                bot_token=bot_token,
                bot_name=bot_name,
                bot_username=bot_username,
                description=description,
                personality=personality,
                system_prompt=system_prompt,
                ai_model=ai_model,
                ai_provider=ai_provider,
                created_by=created_by,
                is_public=is_public,
                status=status or BotStatus.ACTIVE.value
            )
            db.add(bot)
            db.commit()
            db.refresh(bot)
            print(f"✅ Bot创建成功: @{bot_username} (ID={bot.id})")
            return bot
        except Exception as e:
            db.rollback()
            print(f"❌ 创建Bot失败: {e}")
            return None
        finally:
            db.close()

    @staticmethod
    def create_interactive() -> Optional[Bot]:
        """交互式创建Bot"""
        print("\n" + "=" * 60)
        print("🤖 创建新Bot")
        print("=" * 60)

        db = get_db_session()
        try:
            # 获取创建者
            users = db.query(User).all()
            if not users:
                print("\n⚠️  数据库中没有用户，需要先创建用户")
                print("   运行: python -m scripts.db_manager user create")
                return None

            print("\n👤 选择创建者:")
            for u in users:
                print(f"   [{u.id}] @{u.username} - {u.first_name}")
            user_id = int(input("\n请输入用户ID: "))
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                print(f"❌ 用户不存在: ID={user_id}")
                return None
        finally:
            db.close()

        # 获取Bot信息
        print("\n📝 请输入Bot信息:")

        bot_token = input("Bot Token (从BotFather获取): ").strip()
        if not bot_token:
            print("   使用.env中的TELEGRAM_BOT_TOKEN")
            bot_token = settings.telegram_bot_token

        bot_username = input("Bot用户名 (不含@): ").strip()
        if not bot_username:
            print("❌ Bot用户名不能为空")
            return None

        bot_name = input(f"显示名称 (默认{bot_username}): ").strip() or bot_username
        description = input("描述 (可选): ").strip() or "智能情感陪伴助手"

        # AI配置
        print("\n🧠 选择AI提供商:")
        print("   [1] OpenAI (GPT-4)")
        print("   [2] Anthropic (Claude)")
        print("   [3] vLLM (自托管)")
        ai_choice = input("请选择 (1/2/3, 默认1): ").strip() or "1"

        ai_provider_map = {"1": "openai", "2": "anthropic", "3": "vllm"}
        ai_provider = ai_provider_map.get(ai_choice, "openai")

        model_defaults = {
            "openai": settings.openai_model,
            "anthropic": settings.anthropic_model,
            "vllm": settings.vllm_model
        }
        ai_model = input(f"模型名称 (默认{model_defaults[ai_provider]}): ").strip() or model_defaults[ai_provider]

        # 系统提示词
        print("\n📌 请输入System Prompt (机器人人设):")
        print("   直接回车使用默认人设，输入多行后输入'END'结束")

        lines = []
        first_line = input("> ").strip()
        if first_line:
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

        return BotCRUD.create(
            bot_token=bot_token,
            bot_username=bot_username,
            bot_name=bot_name,
            description=description,
            system_prompt=system_prompt,
            ai_provider=ai_provider,
            ai_model=ai_model,
            created_by=user_id
        )

    # ==================== READ ====================

    @staticmethod
    def get(bot_id: int = None, bot_username: str = None) -> Optional[Bot]:
        """
        获取Bot
        
        Args:
            bot_id: Bot ID
            bot_username: Bot用户名
            
        Returns:
            Bot: Bot对象，未找到返回None
        """
        db = get_db_session()
        try:
            if bot_id:
                return db.query(Bot).filter(Bot.id == bot_id).first()
            elif bot_username:
                return db.query(Bot).filter(Bot.bot_username == bot_username).first()
            return None
        finally:
            db.close()

    @staticmethod
    def list_all() -> List[Bot]:
        """
        列出所有Bot
        
        Returns:
            List[Bot]: Bot列表
        """
        db = get_db_session()
        try:
            return db.query(Bot).all()
        finally:
            db.close()

    @staticmethod
    def list_print() -> None:
        """打印Bot列表"""
        db = get_db_session()
        try:
            bots = db.query(Bot).all()

            print("\n" + "=" * 60)
            print("🤖 Bot列表")
            print("=" * 60)

            if not bots:
                print("\n   📭 暂无Bot")
                return

            print(f"\n   共 {len(bots)} 个Bot:\n")
            for b in bots:
                # 获取绑定数量
                binding_count = db.query(ChannelBotMapping).filter(
                    ChannelBotMapping.bot_id == b.id,
                    ChannelBotMapping.is_active == True
                ).count()

                # 隐藏Token
                token = b.bot_token
                if token and len(token) > 20:
                    masked_token = token[:8] + "..." + token[-8:]
                else:
                    masked_token = token or "(未设置)"

                print(f"   [{b.id}] @{b.bot_username}")
                print(f"       名称: {b.bot_name}")
                print(f"       描述: {b.description or '(无)'}")
                print(f"       AI: {b.ai_provider}/{b.ai_model}")
                print(f"       Token: {masked_token}")
                print(f"       状态: {b.status}")
                print(f"       绑定Channel数: {binding_count}")
                print()
        finally:
            db.close()

    # ==================== UPDATE ====================

    @staticmethod
    def update(
            bot_id: int,
            bot_name: str = None,
            description: str = None,
            personality: str = None,
            system_prompt: str = None,
            ai_provider: str = None,
            ai_model: str = None,
            bot_token: str = None,
            status: str = None
    ) -> Optional[Bot]:
        """
        更新Bot信息
        
        Args:
            bot_id: Bot ID
            bot_name: 新名称
            description: 新描述
            personality: 新人设特征
            system_prompt: 新系统提示词
            ai_provider: 新AI提供商
            ai_model: 新AI模型
            bot_token: 新Token
            status: 新状态
            
        Returns:
            Bot: 更新后的Bot对象
        """
        db = get_db_session()
        try:
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                print(f"❌ Bot不存在: ID={bot_id}")
                return None

            if bot_name is not None:
                bot.bot_name = bot_name
            if description is not None:
                bot.description = description
            if personality is not None:
                bot.personality = personality
            if system_prompt is not None:
                bot.system_prompt = system_prompt
            if ai_provider is not None:
                bot.ai_provider = ai_provider
            if ai_model is not None:
                bot.ai_model = ai_model
            if bot_token is not None:
                bot.bot_token = bot_token
            if status is not None:
                bot.status = status

            db.commit()
            db.refresh(bot)
            print(f"✅ Bot更新成功: @{bot.bot_username}")
            return bot
        except Exception as e:
            db.rollback()
            print(f"❌ 更新Bot失败: {e}")
            return None
        finally:
            db.close()

    @staticmethod
    def update_interactive() -> Optional[Bot]:
        """交互式更新Bot"""
        BotCRUD.list_print()

        try:
            bot_id = int(input("\n请输入要更新的Bot ID: "))

            db = get_db_session()
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            db.close()

            if not bot:
                print(f"❌ Bot不存在: ID={bot_id}")
                return None

            print(f"\n正在更新 @{bot.bot_username}")
            print("(直接回车保持原值不变)\n")

            bot_name = input(f"名称 [{bot.bot_name}]: ").strip() or None
            description = input(f"描述 [{bot.description}]: ").strip() or None
            ai_model = input(f"AI模型 [{bot.ai_model}]: ").strip() or None

            print("\n更新System Prompt? (yes/no)")
            system_prompt = None
            if input().lower() == 'yes':
                print("输入新的System Prompt (输入'END'结束):")
                lines = []
                while True:
                    line = input("> ")
                    if line.strip().upper() == 'END':
                        break
                    lines.append(line)
                if lines:
                    system_prompt = "\n".join(lines)

            return BotCRUD.update(
                bot_id=bot_id,
                bot_name=bot_name,
                description=description,
                ai_model=ai_model,
                system_prompt=system_prompt
            )
        except ValueError as e:
            print(f"❌ 输入错误: {e}")
            return None

    # ==================== DELETE ====================

    @staticmethod
    def delete(bot_id: int, confirm: bool = False) -> bool:
        """
        删除Bot
        
        Args:
            bot_id: Bot ID
            confirm: 是否跳过确认
            
        Returns:
            bool: 删除是否成功
        """
        db = get_db_session()
        try:
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                print(f"❌ Bot不存在: ID={bot_id}")
                return False

            if not confirm:
                print(f"\n⚠️  将删除Bot @{bot.bot_username} 及其所有绑定关系")
                if input("输入 'yes' 确认: ").lower() != 'yes':
                    print("❌ 已取消")
                    return False

            # 删除相关绑定
            db.query(ChannelBotMapping).filter(ChannelBotMapping.bot_id == bot_id).delete()
            db.delete(bot)
            db.commit()
            print(f"✅ Bot已删除: @{bot.bot_username}")
            return True
        except Exception as e:
            db.rollback()
            print(f"❌ 删除Bot失败: {e}")
            return False
        finally:
            db.close()

    @staticmethod
    def delete_interactive() -> bool:
        """交互式删除Bot"""
        BotCRUD.list_print()

        try:
            bot_id = int(input("\n请输入要删除的Bot ID: "))
            return BotCRUD.delete(bot_id)
        except ValueError as e:
            print(f"❌ 输入错误: {e}")
            return False

    @staticmethod
    def get_bot_info_from_token(bot_token: str) -> Optional[dict]:
        """
        通过 Token 从 Telegram API 获取 Bot 信息

        Args:
            bot_token:  Telegram Bot Token

        Returns:
            dict:  Bot信息，包含 id, username, first_name 等
        """
        import urllib.request
        import json
        import ssl

        try:
            # 创建 SSL 上下文
            ctx = ssl.create_default_context()

            url = f"https://api.telegram.org/bot{bot_token}/getMe"

            print("   正在验证 Token...")

            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                data = json.loads(response.read().decode())

                if data.get('ok'):
                    bot_info = data['result']
                    print(f"   ✅ Token 验证成功!")
                    print(f"      Bot ID: {bot_info['id']}")
                    print(f"      用户名: @{bot_info['username']}")
                    print(f"      名称: {bot_info['first_name']}")
                    return bot_info
                else:
                    print(f"   ❌ Token 无效: {data.get('description', '未知错误')}")
                    return None

        except urllib.error.HTTPError as e:
            if e.code == 401:
                print("   ❌ Token 无效或已过期")
            else:
                print(f"   ❌ HTTP 错误: {e.code}")
            return None
        except urllib.error.URLError as e:
            print(f"   ❌ 网络错误: {e.reason}")
            print("   提示:  请检查网络连接或代理设置")
            return None
        except Exception as e:
            print(f"   ❌ 验证失败: {e}")
            return None

    @staticmethod
    def create_from_template(template_name: str, bot_token: str, created_by: int = None, bot_info: dict = None) -> \
            Optional[Bot]:
        """
        从模板创建Bot

        Args:
            template_name: 模板目录名
            bot_token:  Telegram Bot Token
            created_by: 创建者用户ID
            bot_info: 从 Telegram API 获取的 Bot 信息（可选）

        Returns:
            Bot:  创建的Bot对象
        """
        import yaml
        from pathlib import Path

        # 查找模板
        template_path = Path(f"bots/{template_name}/config.yaml")
        if not template_path.exists():
            print(f"❌ 模板不存在: {template_path}")
            return None

        # 读取模板配置
        with open(template_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        bot_config = config.get('bot', {})
        personality_config = config.get('personality', {})
        ai_config = config.get('ai', {})

        # 优先使用从 Telegram API 获取的真实信息
        if bot_info:
            bot_username = bot_info.get('username', bot_config.get('username', template_name))
            bot_name = bot_info.get('first_name', bot_config.get('name', template_name))
        else:
            bot_username = bot_config.get('username', template_name)
            bot_name = bot_config.get('name', template_name)

        # 构建系统提示词
        system_prompt = personality_config.get('character', '')
        if personality_config.get('traits'):
            system_prompt += "\n\n你的性格特点：\n" + "\n".join(f"- {t}" for t in personality_config['traits'])

        speaking_style = personality_config.get('speaking_style', {})
        if speaking_style:
            system_prompt += "\n\n语言风格要求："
            if speaking_style.get('tone'):
                system_prompt += f"\n- 语气:  {speaking_style['tone']}"
            if speaking_style.get('use_emoji'):
                system_prompt += f"\n- 使用emoji:  {'是' if speaking_style['use_emoji'] else '否'}"
            if speaking_style.get('avoid'):
                system_prompt += "\n- 避免:  " + "、".join(speaking_style['avoid'])

        # 构建人设描述
        personality = ""
        if personality_config.get('traits'):
            personality = "、".join(personality_config['traits'])

        # 创建Bot
        return BotCRUD.create(
            bot_token=bot_token,
            bot_username=bot_username,
            bot_name=bot_name,
            description=bot_config.get('description', ''),
            personality=personality,
            system_prompt=system_prompt,
            ai_model=ai_config.get('model', 'gpt-4'),
            ai_provider=ai_config.get('provider', 'openai'),
            is_public=bot_config.get('is_public', True),
            created_by=created_by
        )

    @staticmethod
    def create_from_template_interactive() -> Optional[Bot]:
        """交互式从模板创建Bot"""
        import yaml
        from pathlib import Path

        print("\n" + "=" * 60)
        print("🤖 从模板创建Bot")
        print("=" * 60)

        db = get_db_session()
        try:
            # 选择创建者
            users = db.query(User).all()
            if not users:
                print("\n❌ 数据库中没有用户，需要先创建用户")
                print("   运行:  python -m scripts.db_manager user create")
                return None

            print("\n👤 选择创建者:")
            for u in users:
                print(f"   [{u.id}] {u.first_name or u.username} (Telegram ID: {u.telegram_id})")

            try:
                user_id = int(input("\n请选择用户ID: ").strip())
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    print(f"❌ 用户不存在: ID={user_id}")
                    return None
                created_by = user.id
            except ValueError:
                print("❌ 无效的用户ID")
                return None

            # ========== 先输入 Token 并验证 ==========
            print("\n" + "-" * 60)
            print("📝 请输入从 @BotFather 获取的 Token")
            print("   格式: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz")
            print("-" * 60)

            try:
                bot_token = input("\nBot Token: ").strip()
            except KeyboardInterrupt:
                print("\n❌ 已取消")
                return None

            if not bot_token:
                print("❌ Token不能为空")
                return None

            # 自动获取 Bot 信息
            print()
            bot_info = BotCRUD.get_bot_info_from_token(bot_token)

            if not bot_info:
                print("\n⚠️  无法从 Telegram 获取 Bot 信息")
                if input("是否继续?  (y/n): ").lower() != 'y':
                    return None
                bot_info = None
            # ==========================================

            # 列出可用模板
            bots_dir = Path("bots")
            if not bots_dir.exists():
                print(f"❌ bots目录不存在: {bots_dir}")
                return None

            templates = []

            print("\n📁 可用的Bot模板 (选择人设配置):\n")
            idx = 0
            for d in sorted(bots_dir.iterdir()):
                if d.is_dir() and (d / "config.yaml").exists():
                    idx += 1
                    try:
                        with open(d / "config.yaml", 'r', encoding='utf-8') as f:
                            config = yaml.safe_load(f)
                        bot_cfg = config.get('bot', {})
                        personality_cfg = config.get('personality', {})
                        name = bot_cfg.get('name', d.name)
                        desc = bot_cfg.get('description', '无描述')
                        if len(desc) > 35:
                            desc = desc[: 35] + "..."
                        traits = personality_cfg.get('traits', [])[:3]

                        print(f"   [{idx}] {d.name}")
                        print(f"       描述: {desc}")
                        if traits:
                            print(f"       性格:  {', '.join(traits)}")
                        print()
                        templates.append(d.name)
                    except Exception as e:
                        print(f"   [{idx}] {d.name} (配置读取失败)")
                        templates.append(d.name)

            if not templates:
                print("   ❌ 没有可用的模板")
                return None

            # 选择模板
            try:
                choice = input("请选择模板序号: ").strip()
                try:
                    idx = int(choice) - 1
                    if idx < 0 or idx >= len(templates):
                        print(f"❌ 无效的选择")
                        return None
                    template_name = templates[idx]
                except ValueError:
                    if choice in templates:
                        template_name = choice
                    else:
                        print(f"❌ 无效的输入")
                        return None
            except KeyboardInterrupt:
                print("\n❌ 已取消")
                return None

            print(f"\n✅ 已选择模板: {template_name}")

            # 显示即将创建的 Bot 信息
            print("\n" + "-" * 60)
            print("📋 即将创建的 Bot:")
            print("-" * 60)
            if bot_info:
                print(f"   用户名: @{bot_info['username']} (来自 Telegram)")
                print(f"   名称: {bot_info['first_name']} (来自 Telegram)")
            else:
                print(f"   用户名: (将从模板读取)")
                print(f"   名称: (将从模板读取)")
            print(f"   人设模板: {template_name}")
            print(f"   创建者: {user.first_name or user.username}")
            print("-" * 60)

            if input("\n确认创建?  (y/n): ").lower() != 'y':
                print("❌ 已取消")
                return None

            db.close()

            # 创建Bot
            print("\n正在创建Bot...")
            bot = BotCRUD.create_from_template(
                template_name=template_name,
                bot_token=bot_token,
                created_by=created_by,
                bot_info=bot_info  # 传入从 API 获取的信息
            )

            if bot:
                print("\n" + "=" * 60)
                print("✅ Bot创建成功!")
                print("=" * 60)
                print(f"   Bot ID: {bot.id}")
                print(f"   用户名: @{bot.bot_username}")
                print(f"   名称: {bot.bot_name}")
                print(f"   人设模板: {template_name}")
                print(f"   AI模型: {bot.ai_model}")
                print(f"   创建者: {user.first_name or user.username}")
                print("\n📌 下一步:")
                print("   1. 运行 'python -m scripts.db_manager bind' 绑定到Channel")
                print("   2. 运行 'python main.py' 启动Bot")

            return bot

        except Exception as e:
            print(f"❌ 发生错误: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            db.close()
