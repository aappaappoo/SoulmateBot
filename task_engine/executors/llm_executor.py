"""
LLM 执行器 - 纯文本回答

当任务不需要桌面操控时，使用 LLM 直接生成文本回答。
"""
from ..models import Step, StepResult
from .base import BaseExecutor


class LLMExecutor(BaseExecutor):
    """LLM 纯文本执行器（兜底）"""

    async def execute(self, step: Step) -> StepResult:
        """
        使用 LLM 生成文本回答

        当前实现为占位返回，实际可对接 VLLMProvider / OpenAI 等

        Args:
            step: 包含 params["task"] 的步骤

        Returns:
            StepResult: LLM 回答结果
        """
        task_text: str = step.params.get("task", "")
        if not task_text:
            return StepResult(success=False, message="缺少 task 参数")

        # 占位实现：后续可对接真实 LLM
        return StepResult(
            success=True,
            message=f"[LLM] 已收到任务：{task_text}（LLM 直答模式暂未对接）",
        )
