"""
Fitness Bot - 健身教练机器人

专业的健身指导助手，提供健身计划和饮食建议
适合：健身指导、饮食规划、健康管理
"""
from pathlib import Path

# Bot目录路径
BOT_DIR = Path(__file__).parent

# 配置文件路径
CONFIG_FILE = BOT_DIR / "config.yaml"

# Bot标识
BOT_ID = "fitness_bot"
BOT_NAME = "FitnessBot"
BOT_DESCRIPTION = "专业健身教练，助你塑造完美身材"
