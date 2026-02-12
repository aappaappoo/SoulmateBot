"""
执行器抽象基类

所有执行器（shell / llm / desktop）必须继承此基类。
"""
from abc import ABC, abstractmethod

from ..models import Step, StepResult


class BaseExecutor(ABC):
    """执行器抽象基类"""

    @abstractmethod
    async def execute(self, step: Step) -> StepResult:
        """
        执行一个步骤

        Args:
            step: 要执行的步骤

        Returns:
            StepResult: 执行结果
        """
        ...
