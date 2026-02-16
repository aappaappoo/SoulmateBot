"""
任务引擎 - Plan → Execute → Verify → Report

核心编排器，串联 planner → executor_router → verifier → reporter。
"""
from loguru import logger

from .executor_router import route_and_execute
from .models import Task, TaskStatus
from .planner import plan
from .polisher import polish
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
        logger.debug(f"🚀 [TaskEngine] ===== 开始任务 =====")
        logger.debug(f"🚀 [TaskEngine] 输入: {user_input}")

        # 1. 规划
        task: Task = await plan(user_input)
        task.status = TaskStatus.RUNNING
        logger.debug(
            f"📋 [TaskEngine] 规划完成: steps={len(task.steps)}, "
            f"types=[{', '.join(s.executor_type.value for s in task.steps)}]"
        )
        for i, step in enumerate(task.steps):
            logger.debug(
                f"📋 [TaskEngine] Step[{i}]: type={step.executor_type.value}, "
                f"desc='{step.description}', params={step.params}"
            )

        # 2. 执行每个步骤（当前只有 1 个步骤）
        for i, step in enumerate(task.steps):
            logger.debug(
                f"⚙️ [TaskEngine] 执行 Step[{i}]: type={step.executor_type.value}"
            )
            result = await route_and_execute(step)
            task.result = result
            logger.debug(
                f"⚙️ [TaskEngine] Step[{i}] 结果: success={result.success}, "
                f"message='{result.message}'"
            )
            # 如果某步骤失败，停止执行后续步骤
            if not result.success:
                logger.debug(f"⚙️ [TaskEngine] Step[{i}] 失败，停止后续步骤")
                break

        # 3. 验证
        task = await verify(task)
        logger.debug(
            f"✅ [TaskEngine] 验证完成: status={task.status.value}"
        )

        # 4. 报告
        report_text = await report(task)
        logger.debug(f"📝 [TaskEngine] 报告输出: {report_text}")

        # 5. 润色
        polished_text = await polish(report_text, user_input)
        logger.debug(f"🏁 [TaskEngine] ===== 任务结束 =====")

        return polished_text
