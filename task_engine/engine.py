"""
任务引擎 - Plan → Execute → Verify → Report

核心编排器，串联 planner → executor_router → verifier → reporter。
"""
from .executor_router import route_and_execute
from .models import Task, TaskStatus
from .planner import plan
from .reporter import report
from .verifier import verify


class TaskEngine:
    """
    任务引擎

    使用方式：
        engine = TaskEngine()
        result_text = await engine.run("打开网页里的音乐输入周杰伦播放音乐")
    """

    async def run(self, user_input: str) -> str:
        """
        运行完整任务流程

        流程：Plan → Execute → Verify → Report

        Args:
            user_input: 用户原始自然语言输入

        Returns:
            str: 用户友好的执行结果文本
        """
        # 1. 规划
        task: Task = await plan(user_input)
        task.status = TaskStatus.RUNNING

        # 2. 执行每个步骤（当前只有 1 个步骤）
        for step in task.steps:
            result = await route_and_execute(step)
            task.result = result
            # 如果某步骤失败，停止执行后续步骤
            if not result.success:
                break

        # 3. 验证
        task = await verify(task)

        # 4. 报告
        return await report(task)
