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
    """初始化测试数据"""
    print("\n" + "=" * 60)
    print("📦 初始化测试数据")
    print("=" * 60)
    
    # 尝试导入配置
    try:
        from config import settings
    except Exception as e:
        print(f"❌ 无法加载配置: {e}")
        print("   请确保已配置 .env 文件")
        return False
    
    try:
        # 创建用户
        telegram_user_id = int(input("\n请输入你的 Telegram User ID: "))
        username = input("请输入你的 Telegram 用户名 (不含@): ").strip()
        first_name = input("请输入你的名字: ").strip()
        last_name = input("请输入你的姓氏 (可选): ").strip() or None
        bot_username = input("请输入 Bot 用户名 (不含@): ").strip()
        
        # 创建用户
        user = UserCRUD.create(
            telegram_id=telegram_user_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        
        if not user:
            return False
        
        # 创建Bot
        bot = BotCRUD.create(
            bot_token=settings.telegram_bot_token,
            bot_username=bot_username,
            bot_name=bot_username,
            description="智能情感陪伴助手",
            ai_provider="openai" if settings.openai_api_key else "vllm",
            ai_model=settings.openai_model if settings.openai_api_key else settings.vllm_model,
            created_by=user.id
        )
        
        if not bot:
            return False
        
        # 创建私聊Channel
        channel = ChannelCRUD.create(
            telegram_chat_id=telegram_user_id,
            chat_type="private",
            title=f"{first_name}的私聊",
            owner_id=user.id
        )
        
        if not channel:
            return False
        
        # 绑定Bot到Channel
        mapping = MappingCRUD.bind(
            channel_id=channel.id,
            bot_id=bot.id,
            routing_mode="auto"
        )
        
        if not mapping:
            return False
        
        print("\n" + "=" * 60)
        print("🎉 初始化完成!")
        print("=" * 60)
        print(f"""
📋 创建的数据:
   👤 用户: @{username} (ID: {user.id})
   🤖 Bot: @{bot_username} (ID: {bot.id})
   💬 Channel: 私聊 (ID: {channel.id})
   🔗 绑定: 自动回复模式

🚀 现在可以在Telegram中与@{bot_username}对话了!
""")
        return True
        
    except ValueError as e:
        print(f"❌ 输入错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
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
        elif subcommand == 'update':
            BotCRUD.update_interactive()
        elif subcommand == 'delete':
            BotCRUD.delete_interactive()
        else:
            print("用法: python -m scripts.db_manager bot [list|create|update|delete]")
    
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
        MappingCRUD.list_print()
        try:
            channel_id = int(input("\n请输入Channel ID: "))
            bot_id = int(input("请输入Bot ID: "))
            MappingCRUD.unbind(channel_id, bot_id)
        except ValueError:
            print("❌ 输入错误")
    
    elif command == 'mapping':
        if subcommand == 'list':
            MappingCRUD.list_print()
        else:
            print("用法: python -m scripts.db_manager mapping list")
    
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
