"""
任务引擎模块 - 多步骤桌面操控任务执行

支持用户自然语言指令自动化桌面操作：
打开浏览器 → 进入网站 → 搜索 → 播放等。

核心流程：LLM + tool-call while 循环
截图 → 视觉分析 → 点击/输入 → 再截图 → 验证 → 直到完成
"""
from .engine import TaskEngine
from .models import Task, Step, StepResult, ExecutorType, TaskStatus

__all__ = [
    "TaskEngine",
    "Task",
    "Step",
    "StepResult",
    "ExecutorType",
    "TaskStatus",
]
