"""
执行器路由 - shell / llm / desktop 分发

根据 Step.executor_type 将步骤路由到对应的执行器。
"""
from task_engine.models import ExecutorType, Step, StepResult
from task_engine.executors.shell_executor import ShellExecutor
from task_engine.executors.llm_executor import LLMExecutor
from task_engine.executors.desktop_executor import DesktopExecutor


# 延迟实例化的执行器缓存
_executors = {}


def _get_executor(executor_type: ExecutorType):
    """获取或创建执行器实例（懒加载单例）"""
    if executor_type not in _executors:
        if executor_type == ExecutorType.SHELL:
            _executors[executor_type] = ShellExecutor()
        elif executor_type == ExecutorType.LLM:
            _executors[executor_type] = LLMExecutor()
        elif executor_type == ExecutorType.DESKTOP:
            _executors[executor_type] = DesktopExecutor()
    return _executors[executor_type]


async def route_and_execute(step: Step) -> StepResult:
    """
    根据步骤类型路由到对应执行器并执行

    Args:
        step: 要执行的步骤

    Returns:
        StepResult: 执行结果
    """
    executor = _get_executor(step.executor_type)
    return await executor.execute(step)
