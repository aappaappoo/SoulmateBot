"""
结果验证器 - 成功/失败判断

根据 StepResult 判断任务整体是否成功。
"""
from .models import StepResult, Task, TaskStatus


async def verify(task: Task) -> Task:
    """
    验证任务执行结果

    根据最后一个步骤的结果判断任务整体状态。

    Args:
        task: 已执行完步骤的任务

    Returns:
        Task: 更新了 status 的任务
    """
    if task.result is None:
        task.status = TaskStatus.FAILED
        return task

    if task.result.success:
        task.status = TaskStatus.SUCCESS
    else:
        # 检查是否被安全守卫终止
        if "安全守卫终止" in task.result.message:
            task.status = TaskStatus.ABORTED
        else:
            task.status = TaskStatus.FAILED

    return task
