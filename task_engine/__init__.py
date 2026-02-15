"""
任务引擎模块 - 多步骤网页操控任务执行

支持用户自然语言指令自动化网页操作：
打开浏览器 → 进入网站 → 搜索 → 播放等。

核心流程：LLM + tool-call while 循环
通过 Playwright 浏览器自动化完成网页交互操作。
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
