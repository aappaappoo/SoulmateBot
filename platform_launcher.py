#!/usr/bin/env python3
"""
Multi-Bot Platform Launcher

使用方式:
    # 运行默认 Bot（使用 main.py 配置）
    python platform_launcher.py
    
    # 运行指定 Bot
    python platform_launcher.py --bot solin_bot --token YOUR_TOKEN
    
    # 列出可用 Bot
    python platform_launcher.py --list
"""
import argparse
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def main():
    parser = argparse.ArgumentParser(description="Multi-Bot Platform Launcher")
    parser.add_argument(
        "--bot",
        type=str,
        help="Bot ID to run (e.g., solin_bot)"
    )
    parser.add_argument(
        "--token",
        type=str,
        help="Telegram Bot Token (overrides environment)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available bots"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show platform statistics"
    )
    
    args = parser.parse_args()
    
    # 导入平台组件
    from src.bot.platform import get_platform
    from src.bot.config_loader import get_config_loader
    from loguru import logger
    
    # 配置日志
    logger.add(
        "logs/platform_{time}.log",
        rotation="1 day",
        retention="7 days",
        level="INFO"
    )
    
    if args.list:
        # 列出可用 Bot
        loader = get_config_loader()
        bots = loader.list_bots()
        
        print("\n📋 可用的 Bot:")
        print("-" * 40)
        
        for bot_id in bots:
            config = loader.load_config(bot_id)
            if config:
                print(f"  • {bot_id}")
                print(f"    名称: {config.name}")
                print(f"    描述: {config.description}")
                print(f"    类型: {config.bot_type}")
                print()
        
        if not bots:
            print("  (没有找到可用的 Bot)")
        print()
        return
    
    if args.stats:
        # 显示统计信息
        platform = get_platform()
        platform.initialize()
        
        stats = platform.get_stats()
        
        print("\n📊 平台统计:")
        print("-" * 40)
        print(f"  Bot 总数: {stats['total_bots']}")
        print(f"  运行中: {stats['running_bots']}")
        print(f"  总消息数: {stats['total_messages']}")
        print(f"  错误数: {stats['total_errors']}")
        print()
        
        if stats.get('llm_stats'):
            llm = stats['llm_stats']
            print("  LLM Gateway:")
            print(f"    总请求: {llm.get('total_requests', 0)}")
            print(f"    成功率: {llm.get('success_rate', 0):.2%}")
        print()
        return
    
    # 运行 Bot
    token = args.token or os.environ.get("TELEGRAM_BOT_TOKEN")
    
    if not token:
        print("❌ 错误: 请提供 Telegram Bot Token")
        print("   使用 --token 参数或设置 TELEGRAM_BOT_TOKEN 环境变量")
        sys.exit(1)
    
    if args.bot:
        # 运行指定 Bot
        platform = get_platform()
        platform.initialize()
        
        try:
            logger.info(f"Starting bot: {args.bot}")
            platform.run_polling(args.bot, token)
        except ValueError as e:
            print(f"❌ 错误: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
    else:
        # 运行默认配置（使用原有的 main.py 逻辑）
        from src.bot import SoulmateBot
        
        logger.info("Starting default bot...")
        bot = SoulmateBot()
        bot.run()


if __name__ == "__main__":
    main()
