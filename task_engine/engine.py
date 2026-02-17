"""
任务引擎 - Plan → Execute → Verify → Report

核心编排器，串联 planner → executor_router → verifier → reporter。
"""
from loguru import logger

from .executor_router import route_and_execute
from .models import ExecutorType, Step, Task, TaskStatus
from .polisher import polish
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
        logger.debug(f"🚀 [TaskEngine] ===== 开始任务 =====")
        logger.debug(f"🚀 [TaskEngine] 输入: {user_input}")
        task = Task(user_input=user_input)
        step = Step(
            executor_type=ExecutorType.AGENT,
            description="AI 自主操控任务",
            params={"task": user_input},
        )
        task.status = TaskStatus.RUNNING
        result = await route_and_execute(step)
        task.result = result
        # 如果某步骤失败，停止执行后续步骤
        if not result.success:
            logger.debug(f"⚙️ [TaskEngine] Step 执行失败，停止后续步骤")

        # 3. 验证
        task = await verify(task)

        # 4. 润色报告
        report_text = task.result.message
        report_text = await polish(report_text, user_input)
        return report_text
