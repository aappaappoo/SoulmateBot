"""
文本输入工具 - 支持中文

在当前焦点位置输入文本。
macOS: 使用 osascript
Linux: 使用 xdotool
"""
import asyncio

from task_engine.executors.desktop_executor.platform import detect_platform, PlatformType


async def type_text(text: str) -> str:
    """
    在当前焦点位置输入文本

    Args:
        text: 要输入的文本（支持中文）

    Returns:
        str: 操作结果描述
    """
    plat = detect_platform()

    if plat == PlatformType.MACOS:
        # macOS: 通过剪贴板 + cmd+v 处理中文
        escaped = text.replace("'", "'\\''")
        copy_cmd = f"echo -n '{escaped}' | pbcopy"
        paste_script = (
            'tell application "System Events" to keystroke "v" using command down'
        )
        command = f"{copy_cmd} && osascript -e '{paste_script}'"
    else:
        # Linux: xdotool 对中文支持有限，使用 xclip + xdotool
        escaped = text.replace("'", "'\\''")
        command = (
            f"echo -n '{escaped}' | xclip -selection clipboard && "
            f"xdotool key ctrl+v"
        )

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
        if proc.returncode == 0:
            return f"已输入文本: {text}"
        err = stderr.decode(errors="replace") if stderr else "未知错误"
        return f"输入失败: {err}"
    except asyncio.TimeoutError:
        return "输入超时"
    except Exception as e:
        return f"输入异常: {e}"
