"""
轻量 shell 命令执行工具（安全过滤）
"""
import asyncio
import re
from typing import List

# 危险命令黑名单
_DENY_PATTERNS: List[re.Pattern] = [
    re.compile(r"\brm\s+(-\w+\s+)*-r", re.IGNORECASE),
    re.compile(r"\bsudo\b", re.IGNORECASE),
    re.compile(r"\bmkfs\b", re.IGNORECASE),
    re.compile(r"\bdd\s+if=", re.IGNORECASE),
    re.compile(r"\bshutdown\b", re.IGNORECASE),
    re.compile(r"\breboot\b", re.IGNORECASE),
]


async def shell_run(command: str) -> str:
    """
    安全执行 shell 命令

    Args:
        command: 要执行的命令

    Returns:
        str: 命令输出或错误信息
    """
    for pattern in _DENY_PATTERNS:
        if pattern.search(command):
            return f"安全拒绝：命令包含危险操作"

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        output = stdout.decode(errors="replace") if stdout else ""
        err = stderr.decode(errors="replace") if stderr else ""
        if proc.returncode == 0:
            return output or "执行成功"
        return f"命令失败 (exit {proc.returncode}): {err}"
    except asyncio.TimeoutError:
        return "命令执行超时（15秒）"
    except Exception as e:
        return f"执行异常: {e}"
