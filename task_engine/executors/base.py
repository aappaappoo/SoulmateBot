"""
执行器抽象基类
"""
from abc import ABC, abstractmethod

from task_engine.models import Step, StepResult
from task_engine.polisher import polish


class BaseExecutor(ABC):
    """执行器抽象基类"""

    # 子类可覆盖此属性来控制是否启用润色
    enable_polish: bool = False

    async def run(self, step: Step) -> StepResult:
        """
        模板方法：execute → (可选) polish

        子类只需实现 execute()，润色由基类统一处理。
        """
        result = await self.execute(step)

        # 成功且启用润色时，对 message 进行润色
        if self.enable_polish and result.success and result.message:
            task_text = step.params.get("task", "")
            polished = await polish(result.message, task_text)
            result.message = polished

        return result

    @abstractmethod
    async def execute(self, step: Step) -> StepResult:
        """子类实现具体执行逻辑"""
        ...