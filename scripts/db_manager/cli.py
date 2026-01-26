#!/usr/bin/env python3
"""
数据库管理命令行接口
===================

提供统一的命令行接口来管理数据库。

使用方法:
  python -m scripts.db_manager <command> [subcommand] [options]

命令列表:
  rebuild             重建数据库(删除所有表并重新创建)
  status              查看数据库状态
  fix                 修复数据库结构
  clear               清空所有数据
  
  user list           列出所有用户
  user create         创建新用户
  user update         更新用户信息
  user delete         删除用户
  
  bot list            列出所有Bot
  bot create          创建新Bot
  bot update          更新Bot信息
  bot delete          删除Bot
  
  channel list        列出所有Channel
  channel create      创建新Channel
  channel update      更新Channel信息
  channel delete      删除Channel
  
  bind                绑定Bot到Channel(交互式)
  bind-quick <chat_id> <bot_id> [mode]   快速绑定
  unbind              解绑Bot(交互式)
  mapping list        列出所有绑定关系
  
  token               Token管理(交互菜单)
  token-set <bot_id> <token>   快速设置Token
  token-list          列出所有Token
  token-validate      验证Token有效性
  
  init                初始化测试数据(交互式)
  all                 重建数据库并初始化测试数据
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .base import DatabaseManager
from .user_crud import UserCRUD
from .bot_crud import BotCRUD
from .channel_crud import ChannelCRUD
from .mapping_crud import MappingCRUD
from .token_manager import TokenManager


def init_test_data() -> bool:
    """
    初始化数据 - 简化版

    步骤：
    1. 创建用户（只需 Telegram ID 和 Username）
    2. 从 bots/ 目录选择配置创建 Bot
    3. 自动绑定
    """
    import yaml
    from pathlib import Path

    print("\n" + "=" * 60)
    print("📦 初始化数据")
    print("=" * 60)

    try:
        # ========== 1. 创建用户 ==========
        print("\n" + "-" * 60)
        print("👤 步骤 1/3: 创建用户")
        print("-" * 60)

        while True:
            telegram_id_str = input("\nTelegram User ID (数字): ").strip()
            if not telegram_id_str:
                print("   ❌ ID 不能为空")
                continue
            try:
                telegram_id = int(telegram_id_str)
                break
            except ValueError:
                print("   ❌ 请输入有效的数字ID")

        while True:
            username = input("Username (不含@): ").strip().lstrip('@')
            if username:
                break
            print("   ❌ Username 不能为空")

        user = UserCRUD.create(
            telegram_id=telegram_id,
            username=username,
            first_name=username
        )

        if not user:
            print("❌ 创建用户失败")
            return False

        # ========== 2. 选择配置并创建 Bot ==========
        print("\n" + "-" * 60)
        print("🤖 步骤 2/3: 创建 Bot")
        print("-" * 60)

        # 扫描 bots/ 目录
        bots_dir = Path("bots")
        if not bots_dir.exists():
            print(f"❌ bots 目录不存在: {bots_dir}")
            return False

        available_configs = []
        for bot_dir in sorted(bots_dir.iterdir()):
            if bot_dir.is_dir() and not bot_dir.name.startswith('_'):
                config_file = bot_dir / "config.yaml"
                if config_file.exists():
                    try:
                        with open(config_file, 'r', encoding='utf-8') as f:
                            data = yaml.safe_load(f)
                        bot_data = data.get("bot", {})
                        available_configs.append({
                            "dir_name": bot_dir.name,
                            "name": bot_data.get("name", bot_dir.name),
                            "description": bot_data.get("description", "")[:40],
                            "data": data
                        })
                    except:
                        pass

        if not available_configs:
            print("❌ bots 目录下没有找到配置文件")
            return False

        print("\n📁 可用的 Bot 配置:")
        for i, cfg in enumerate(available_configs, 1):
            print(f"   [{i}] {cfg['dir_name']}/  -  {cfg['name']}")

        try:
            choice = int(input("\n请选择配置 [序号]: ").strip())
            if choice < 1 or choice > len(available_configs):
                print("❌ 无效的选择")
                return False
            selected = available_configs[choice - 1]
        except ValueError:
            print("❌ 请输入数字")
            return False

        config_dir_name = selected["dir_name"]
        data = selected["data"]
        bot_data = data.get("bot", {})
        personality_data = data.get("personality", {})
        ai_data = data.get("ai", {})

        bot_name = bot_data.get("name", config_dir_name)
        description = bot_data.get("description", "")

        # 构建 system_prompt
        character = personality_data.get("character", "")
        traits = personality_data.get("traits", [])
        if character:
            system_prompt = f"你是{bot_name}。\n\n{character}"
            if traits:
                system_prompt += f"\n\n你的性格特点: {', '.join(traits)}"
        else:
            system_prompt = f"你是一个名叫{bot_name}的智能助手。{description}"

        ai_provider = ai_data.get("provider", "openai")
        ai_model = ai_data.get("model", "gpt-4")

        print(f"\n已选择: {config_dir_name}/ ({bot_name})")

        # 输入 Token
        print("\n🔑 请输入 Bot Token (从 @BotFather 获取):")
        bot_token = input("Token: ").strip()
        if not bot_token:
            print("❌ Token 不能为空")
            return False

        # 验证 Token 并获取用户名
        print("\n🔍 验证 Token...")
        bot_username = None
        try:
            import requests
            response = requests.get(
                f"https://api.telegram.org/bot{bot_token}/getMe",
                timeout=10
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    bot_info = result.get("result", {})
                    bot_username = bot_info.get("username", "")
                    print(f"   ✅ Token 有效! Bot: @{bot_username}")
        except:
            pass

        if not bot_username:
            bot_username = input("请手动输入 Bot 用户名 (不含@): ").strip()
            if not bot_username:
                print("❌ Bot 用户名不能为空")
                return False

        # 创建 Bot
        bot = BotCRUD.create(
            bot_token=bot_token,
            bot_username=bot_username,
            bot_name=bot_name,
            description=description,
            personality=character,
            system_prompt=system_prompt,
            ai_provider=ai_provider,
            ai_model=ai_model,
            created_by=user.id,
            is_public=True
        )

        if not bot:
            print("❌ 创建 Bot 失败")
            return False

        # ========== 3. 创建 Channel 并绑定 ==========
        print("\n" + "-" * 60)
        print("🔗 步骤 3/3: 创建 Channel 并绑定")
        print("-" * 60)

        # 使用用户的 Telegram ID 作为私聊 Channel
        channel = ChannelCRUD.create(
            telegram_chat_id=telegram_id,
            chat_type="private",
            title=f"{username} 的私聊",
            owner_id=user.id
        )

        if not channel:
            print("❌ 创建 Channel 失败")
            return False

        # 绑定 Bot 到 Channel（私聊默认 auto 模式）
        mapping = MappingCRUD.bind(
            channel_id=channel.id,
            bot_id=bot.id,
            routing_mode="auto"
        )

        if not mapping:
            print("❌ 绑定失败")
            return False

        # ========== 完成 ==========
        print("\n" + "=" * 60)
        print("🎉 初始化完成!")
        print("=" * 60)
        print(f"""
📋 创建的数据:
   👤 用户: @{username} (Telegram ID: {telegram_id})
   🤖 Bot: @{bot_username} ({bot_name})
   💬 Channel: 私聊 (自动回复模式)
   📁 配置目录: bots/{config_dir_name}/

⚠️  重要：请在 main.py 中添加配置映射:

   BOT_CONFIG_MAPPING = {{
       "{bot_username}": "{config_dir_name}",
   }}

🚀 启动 Bot:
   python main.py
""")
        return True

    except KeyboardInterrupt:
        print("\n\n❌ 已取消")
        return False
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def print_help():
    """打印帮助信息"""
    print(__doc__)
    print("\n📌 常用命令示例:")
    print("   python -m scripts.db_manager status")
    print("   python -m scripts.db_manager user list")
    print("   python -m scripts.db_manager bot create")
    print("   python -m scripts.db_manager bind")
    print("   python -m scripts.db_manager token-set 1 YOUR_TOKEN")


def main():
    """主入口函数"""
    manager = DatabaseManager()

    if len(sys.argv) < 2:
        print_help()
        sys.exit(0)

    command = sys.argv[1].lower()
    subcommand = sys.argv[2].lower() if len(sys.argv) > 2 else None

    # 基础命令
    if command == 'rebuild':
        manager.rebuild()

    elif command == 'status':
        manager.status()

    elif command == 'fix':
        manager.fix_schema()

    elif command == 'clear':
        manager.clear_data()

    elif command == 'init':
        init_test_data()

    elif command == 'all':
        if manager.rebuild(confirm=False):
            init_test_data()

    # 用户命令
    elif command == 'user':
        if subcommand == 'list':
            UserCRUD.list_print()
        elif subcommand == 'create':
            UserCRUD.create_interactive()
        elif subcommand == 'update':
            UserCRUD.update_interactive()
        elif subcommand == 'delete':
            UserCRUD.delete_interactive()
        else:
            print("用法: python -m scripts.db_manager user [list|create|update|delete]")

    # Bot命令
    elif command == 'bot':
        if subcommand == 'list':
            BotCRUD.list_print()
        elif subcommand == 'create':
            BotCRUD.create_interactive()
        elif subcommand == 'create-from-template' or subcommand == 'template':
            BotCRUD.create_from_template_interactive()
        elif subcommand == 'update':
            BotCRUD.update_interactive()
        elif subcommand == 'sync':
            BotCRUD.sync_from_yaml_interactive()
        elif subcommand == 'sync-all':
            BotCRUD.sync_all_from_yaml()
        elif subcommand == 'delete':
            BotCRUD.delete_interactive()
        else:
            print("用法:  python -m scripts.db_manager bot [list|create|template|update|delete]")
            print("\n命令说明:")
            print("   list     - 列出所有Bot")
            print("   create   - 手动创建Bot")
            print("   template - 从模板创建Bot (推荐)")
            print("   update   - 更新Bot信息")
            print("   delete   - 删除Bot")

    # Channel命令
    elif command == 'channel':
        if subcommand == 'list':
            ChannelCRUD.list_print()
        elif subcommand == 'create':
            ChannelCRUD.create_interactive()
        elif subcommand == 'update':
            ChannelCRUD.update_interactive()
        elif subcommand == 'delete':
            ChannelCRUD.delete_interactive()
        else:
            print("用法: python -m scripts.db_manager channel [list|create|update|delete]")

    # 添加快捷命令
    elif command == 'register':
        # 快捷命令：从模板注册Bot
        BotCRUD.create_from_template_interactive()

    # 绑定命令
    elif command == 'bind':
        MappingCRUD.bind_interactive()

    elif command == 'bind-quick':
        if len(sys.argv) >= 4:
            chat_id = int(sys.argv[2])
            bot_id = int(sys.argv[3])
            mode = sys.argv[4] if len(sys.argv) > 4 else "mention"
            MappingCRUD.bind_quick(chat_id, bot_id, mode)
        else:
            print("用法: python -m scripts.db_manager bind-quick <chat_id> <bot_id> [mode]")

    elif command == 'unbind':
        MappingCRUD.unbind_interactive()

    elif command == 'mapping':
        if subcommand == 'list':
            MappingCRUD.list_print()
        elif subcommand == 'update':
            MappingCRUD.update_interactive()
        else:
            print("用法: python -m scripts.db_manager mapping [list|update]")

    # Token命令
    elif command == 'token':
        TokenManager.manage_interactive()

    elif command == 'token-set':
        if len(sys.argv) >= 4:
            bot_id = int(sys.argv[2])
            token = sys.argv[3]
            TokenManager.set_token(bot_id, token)
        else:
            print("用法: python -m scripts.db_manager token-set <bot_id> <token>")

    elif command == 'token-list':
        TokenManager.list_tokens()

    elif command == 'token-validate':
        TokenManager.validate_token()

    # 帮助
    elif command in ['help', '-h', '--help']:
        print_help()

    else:
        print(f"❌ 未知命令: {command}")
        print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
