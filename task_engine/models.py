"""
Task / Step / Result 数据模型

定义任务引擎的核心数据结构，包括：
- Task：完整任务描述
- Step：单个执行步骤
- StepResult：步骤执行结果
- ExecutorType：执行器类型枚举
- TaskStatus：任务状态枚举
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class ExecutorType(str, Enum):
    """执行器类型"""
    SHELL = "shell"
    LLM = "llm"
    DESKTOP = "desktop"


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class Step:
    """
    单个执行步骤

    Attributes:
        executor_type: 执行器类型（shell / llm / desktop）
        description: 步骤描述
        params: 执行参数（如 task=自然语言任务描述）
    """
    executor_type: ExecutorType
    description: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    """
    步骤执行结果

    Attributes:
        success: 是否成功
        message: 结果描述
        data: 额外数据
    """
    success: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """
    完整任务描述

    Attributes:
        user_input: 用户原始输入
        steps: 规划的执行步骤列表
        status: 当前任务状态
        result: 最终执行结果
    """
    user_input: str
    steps: list = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[StepResult] = None
