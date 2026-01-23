#!/usr/bin/env python3
"""
Database Manager - 数据库管理工具
===================================

用于管理 Bot 注册、Token 设置等数据库操作。

使用方法:
  python db_manager.py register --username qiqi_bot --name 琪琪 --token YOUR_TOKEN
  python db_manager.py token-set --username qiqi_bot --token YOUR_TOKEN
  python db_manager.py list
  python db_manager.py activate --username qiqi_bot
  python db_manager.py deactivate --username qiqi_bot
"""
import sys
import os
import argparse

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from src.database import get_db_session, init_db
from src.models.database import Bot, User, BotStatus


def get_or_create_admin_user(db: Session) -> User:
    """获取或创建管理员用户"""
    admin = db.query(User).filter(User.telegram_id == 1).first()
    if not admin:
        admin = User(
            telegram_id=1,
            username="admin",
            first_name="Admin",
            subscription_tier="premium"
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
    return admin


def register_bot(
        username: str,
        name: str,
        token: str = None,
        description: str = "",
        system_prompt: str = "",
        ai_model: str = "gpt-4",
        ai_provider: str = "openai",
        is_public: bool = True
) -> None:
    """注册新的 Bot"""
    init_db()
    db = get_db_session()

    try:
        # 检查是否已存在
        existing = db.query(Bot).filter(Bot.bot_username == username).first()
        if existing:
            print(f"❌ Bot @{username} 已存在 (ID: {existing.id})")
            print(f"   如需更新 Token，请使用: python db_manager.py token-set --username {username} --token YOUR_TOKEN")
            return

        # 获取管理员用户
        admin = get_or_create_admin_user(db)

        # 创建 Bot
        bot = Bot(
            bot_username=username,
            bot_name=name,
            bot_token=token,
            description=description,
            system_prompt=system_prompt or f"你是一个名叫{name}的智能助手。",
            ai_model=ai_model,
            ai_provider=ai_provider,
            is_public=is_public,
            status=BotStatus.ACTIVE.value,
            created_by=admin.id
        )

        db.add(bot)
        db.commit()
        db.refresh(bot)

        print(f"✅ Bot 注册成功!")
        print(f"   ID: {bot.id}")
        print(f"   用户名: @{bot.bot_username}")
        print(f"   名称: {bot.bot_name}")
        print(f"   Token: {'已设置' if token else '未设置'}")
        print(f"   状态: {bot.status}")

        if not token:
            print(f"\n⚠️  请设置 Token: python db_manager.py token-set --username {username} --token YOUR_TOKEN")

    except Exception as e:
        print(f"❌ 注册失败: {e}")
        db.rollback()
    finally:
        db.close()


def set_token(username: str, token: str) -> None:
    """设置 Bot 的 Telegram Token"""
    init_db()
    db = get_db_session()

    try:
        bot = db.query(Bot).filter(Bot.bot_username == username).first()
        if not bot:
            print(f"❌ Bot @{username} 不存在")
            print(f"   请先注册: python db_manager.py register --username {username} --name 名称 --token YOUR_TOKEN")
            return

        bot.bot_token = token
        db.commit()

        print(f"✅ Token 设置成功!")
        print(f"   Bot: @{username}")
        print(f"   ID: {bot.id}")

    except Exception as e:
        print(f"❌ 设置失败: {e}")
        db.rollback()
    finally:
        db.close()


def list_bots() -> None:
    """列出所有 Bot"""
    init_db()
    db = get_db_session()

    try:
        bots = db.query(Bot).all()

        if not bots:
            print("❌ 数据库中没有注册的 Bot")
            return

        print("\n📋 已注册的 Bot 列表:\n")
        print(f"{'ID':<6} {'用户名':<20} {'名称':<15} {'模型':<15} {'状态':<10} {'Token':<10}")
        print("-" * 80)

        for bot in bots:
            token_status = "✅ 已设置" if bot.bot_token else "❌ 未设置"
            print(
                f"{bot.id:<6} @{bot.bot_username:<19} {bot.bot_name:<15} {bot.ai_model:<15} {bot.status:<10} {token_status}")

        print("\n")

    finally:
        db.close()


def activate_bot(username: str) -> None:
    """激活 Bot"""
    init_db()
    db = get_db_session()

    try:
        bot = db.query(Bot).filter(Bot.bot_username == username).first()
        if not bot:
            print(f"❌ Bot @{username} 不存在")
            return

        bot.status = BotStatus.ACTIVE.value
        db.commit()
        print(f"✅ Bot @{username} 已激活")

    except Exception as e:
        print(f"❌ 操作失败: {e}")
        db.rollback()
    finally:
        db.close()


def deactivate_bot(username: str) -> None:
    """停用 Bot"""
    init_db()
    db = get_db_session()

    try:
        bot = db.query(Bot).filter(Bot.bot_username == username).first()
        if not bot:
            print(f"❌ Bot @{username} 不存在")
            return

        bot.status = BotStatus.INACTIVE.value
        db.commit()
        print(f"✅ Bot @{username} 已停用")

    except Exception as e:
        print(f"❌ 操作失败: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="数据库管理工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # register 命令
    register_parser = subparsers.add_parser("register", help="注册新的 Bot")
    register_parser.add_argument("--username", required=True, help="Bot 用户名 (不含@)")
    register_parser.add_argument("--name", required=True, help="Bot 显示名称")
    register_parser.add_argument("--token", help="Telegram Bot Token")
    register_parser.add_argument("--description", default="", help="Bot 描述")
    register_parser.add_argument("--model", default="gpt-4", help="AI 模型")
    register_parser.add_argument("--provider", default="openai", help="AI 提供商")

    # token-set 命令
    token_parser = subparsers.add_parser("token-set", help="设置 Bot 的 Token")
    token_parser.add_argument("--username", required=True, help="Bot 用户名")
    token_parser.add_argument("--token", required=True, help="Telegram Bot Token")

    # list 命令
    subparsers.add_parser("list", help="列出所有 Bot")

    # activate 命令
    activate_parser = subparsers.add_parser("activate", help="激活 Bot")
    activate_parser.add_argument("--username", required=True, help="Bot 用户名")

    # deactivate 命令
    deactivate_parser = subparsers.add_parser("deactivate", help="停用 Bot")
    deactivate_parser.add_argument("--username", required=True, help="Bot 用户名")

    args = parser.parse_args()

    if args.command == "register":
        register_bot(
            username=args.username,
            name=args.name,
            token=args.token,
            description=args.description,
            ai_model=args.model,
            ai_provider=args.provider
        )
    elif args.command == "token-set":
        set_token(args.username, args.token)
    elif args.command == "list":
        list_bots()
    elif args.command == "activate":
        activate_bot(args.username)
    elif args.command == "deactivate":
        deactivate_bot(args.username)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()