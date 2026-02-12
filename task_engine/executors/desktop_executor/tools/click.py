"""
鼠标点击工具

使用平台工具在屏幕指定坐标执行鼠标点击。
macOS: 使用 osascript / cliclick
Linux: 使用 xdotool
"""
import asyncio

from ..platform import detect_platform, PlatformType


async def click(x: int, y: int) -> str:
    """
    在屏幕指定坐标执行鼠标点击

    Args:
        x: X 坐标
        y: Y 坐标

    Returns:
        str: 操作结果描述
    """
    plat = detect_platform()
    if plat == PlatformType.MACOS:
        # macOS: 使用 osascript 模拟点击
        script = (
            f'tell application "System Events" to click at {{{x}, {y}}}'
        )
        command = f"osascript -e '{script}'"
    else:
        # Linux: 使用 xdotool
        command = f"xdotool mousemove {x} {y} click 1"

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
        if proc.returncode == 0:
            return f"已点击坐标 ({x}, {y})"
        err = stderr.decode(errors="replace") if stderr else "未知错误"
        return f"点击失败: {err}"
    except asyncio.TimeoutError:
        return "点击超时"
    except Exception as e:
        return f"点击异常: {e}"
