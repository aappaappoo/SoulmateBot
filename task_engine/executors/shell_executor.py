"""
安全 Shell 执行器

执行受限的 shell 命令，禁止危险操作（rm -rf / sudo 等）。
"""
import asyncio
import re
from typing import List

from ..models import Step, StepResult
from .base import BaseExecutor

# 危险命令黑名单正则
_DENY_PATTERNS: List[re.Pattern] = [
    re.compile(r"\brm\s+(-\w+\s+)*-r", re.IGNORECASE),
    re.compile(r"\brm\s+(-\w+\s+)*/", re.IGNORECASE),
    re.compile(r"\bsudo\b", re.IGNORECASE),
    re.compile(r"\bmkfs\b", re.IGNORECASE),
    re.compile(r"\bdd\s+if=", re.IGNORECASE),
    re.compile(r"\b:(){ :\|:& };:", re.IGNORECASE),
    re.compile(r"\bchmod\s+(-\w+\s+)*777\s+/", re.IGNORECASE),
    re.compile(r"\bshutdown\b", re.IGNORECASE),
    re.compile(r"\breboot\b", re.IGNORECASE),
]


class ShellExecutor(BaseExecutor):
    """安全 Shell 执行器，拒绝危险命令"""

    async def execute(self, step: Step) -> StepResult:
        """
        执行 shell 命令

        Args:
            step: 包含 params["command"] 的步骤

        Returns:
            StepResult: 命令执行结果
        """
        command: str = step.params.get("command", "")
        if not command:
            return StepResult(success=False, message="缺少 command 参数")

        # 安全检查
        for pattern in _DENY_PATTERNS:
            if pattern.search(command):
                return StepResult(
                    success=False,
                    message=f"安全拒绝：命令包含危险操作 ({pattern.pattern})",
                )

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            stdout_text = stdout.decode(errors="replace") if stdout else ""
            stderr_text = stderr.decode(errors="replace") if stderr else ""

            if proc.returncode == 0:
                return StepResult(
                    success=True,
                    message=stdout_text or "命令执行成功",
                    data={"returncode": 0, "stdout": stdout_text, "stderr": stderr_text},
                )
            else:
                return StepResult(
                    success=False,
                    message=f"命令失败 (exit {proc.returncode}): {stderr_text}",
                    data={"returncode": proc.returncode, "stdout": stdout_text, "stderr": stderr_text},
                )
        except asyncio.TimeoutError:
            return StepResult(success=False, message="命令执行超时（30秒）")
        except Exception as e:
            return StepResult(success=False, message=f"命令执行异常: {e}")
