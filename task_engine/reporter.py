"""
报告生成器 - 用户友好回复

将任务执行结果转换为自然语言回复。
"""
from .models import Task, TaskStatus


async def report(task: Task) -> str:
    """
    生成用户友好的任务执行报告

    Args:
        task: 已验证的任务

    Returns:
        str: 自然语言回复
    """
    if task.status == TaskStatus.SUCCESS:
        msg = task.result.message if task.result else "任务已完成"
        return f"✅ {msg}"

    if task.status == TaskStatus.ABORTED:
        msg = task.result.message if task.result else "任务被终止"
        return f"⚠️ {msg}"

    if task.status == TaskStatus.FAILED:
        msg = task.result.message if task.result else "任务执行失败"
        return f"❌ {msg}"

    return "⏳ 任务仍在处理中..."
