"""
屏幕截图工具
"""
import asyncio
import os
import tempfile
import time

from task_engine.executors.desktop_executor.platform import get_screenshot_command


async def screenshot() -> str:
    """
    执行屏幕截图

    Returns:
        str: 截图文件路径或错误信息
    """
    # 使用临时目录存储截图
    tmp_dir = tempfile.gettempdir()
    filename = f"desktop_screenshot_{int(time.time())}.png"
    filepath = os.path.join(tmp_dir, filename)

    cmd_template = get_screenshot_command()
    command = cmd_template.format(path=filepath)

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode == 0 and os.path.exists(filepath):
            return filepath
        err = stderr.decode(errors="replace") if stderr else "截图命令失败"
        return f"截图失败: {err}"
    except asyncio.TimeoutError:
        return "截图超时（10秒）"
    except Exception as e:
        return f"截图异常: {e}"
