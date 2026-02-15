"""
任务引擎模块 - AI 自主操控任务执行

支持用户自然语言指令，由 LLM 自主决策完成任务：
LLM 意图理解 → 自主选择目标网站 → 浏览器工具操控 → 验证完成

核心流程：LLM + browser tool-call 循环
启动浏览器 → 导航 → 快照 → 操作 → 再快照 → 直到完成
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
