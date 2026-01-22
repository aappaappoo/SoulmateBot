"""
Teacher Bot - 智慧导师机器人

专业的教育辅导助手，帮助用户学习和解答疑问
适合：学生辅导、知识解答、学习方法指导
"""
from pathlib import Path

# Bot目录路径
BOT_DIR = Path(__file__).parent

# 配置文件路径
CONFIG_FILE = BOT_DIR / "config.yaml"

# Bot标识
BOT_ID = "teacher_bot"
BOT_NAME = "TeacherBot"
BOT_DESCRIPTION = "智慧导师，耐心解答学习问题"
