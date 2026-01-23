"""
Main entry point for SoulmateBot
"""
import asyncio
from src.bot import SoulmateBot
from loguru import logger

if __name__ == "__main__":
    bot = SoulmateBot()
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("收到退出信号，正在关闭...")
