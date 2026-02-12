"""
打开浏览器或 URL 工具
"""
import asyncio

from ..platform import get_open_command


async def app_open(url: str) -> str:
    """
    打开浏览器并访问指定 URL

    Args:
        url: 要打开的 URL 或应用名称

    Returns:
        str: 操作结果描述
    """
    open_cmd = get_open_command()
    command = f'{open_cmd} "{url}"'

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode == 0:
            return f"已打开: {url}"
        err = stderr.decode(errors="replace") if stderr else "未知错误"
        return f"打开失败: {err}"
    except asyncio.TimeoutError:
        return "打开超时（10秒）"
    except Exception as e:
        return f"打开异常: {e}"
