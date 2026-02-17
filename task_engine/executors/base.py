"""
执行器抽象基类
"""
from abc import ABC, abstractmethod

from task_engine.models import Step, StepResult
from task_engine.polisher import polish


class BaseExecutor(ABC):
    """执行器抽象基类"""

    async def run(self, step: Step) -> StepResult:
        """
        模板方法：execute → (可选) polish

        子类只需实现 execute()，润色由基类统一处理。
        """
        result = await self.execute(step)
        return result

    @abstractmethod
    async def execute(self, step: Step) -> StepResult:
        """子类实现具体执行逻辑"""
        ...