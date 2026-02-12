"""
键盘按键工具

按下键盘按键（如 Enter、Tab、cmd+v 等）。
macOS: 使用 osascript
Linux: 使用 xdotool
"""
import asyncio

from task_engine.executors.desktop_executor.platform import detect_platform, PlatformType

# macOS 按键名称映射
_MACOS_KEY_MAP = {
    "enter": "return",
    "return": "return",
    "tab": "tab",
    "escape": "escape",
    "esc": "escape",
    "space": "space",
    "backspace": "delete",
    "delete": "forward delete",
    "up": "up arrow",
    "down": "down arrow",
    "left": "left arrow",
    "right": "right arrow",
}

# Linux xdotool 按键名称映射
_LINUX_KEY_MAP = {
    "enter": "Return",
    "return": "Return",
    "tab": "Tab",
    "escape": "Escape",
    "esc": "Escape",
    "space": "space",
    "backspace": "BackSpace",
    "delete": "Delete",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
}


async def key_press(key: str) -> str:
    """
    按下键盘按键

    支持组合键（如 cmd+v, ctrl+a）

    Args:
        key: 按键名称（如 Return, Tab, cmd+v）

    Returns:
        str: 操作结果描述
    """
    plat = detect_platform()

    if plat == PlatformType.MACOS:
        command = _build_macos_key_command(key)
    else:
        command = _build_linux_key_command(key)

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
        if proc.returncode == 0:
            return f"已按下: {key}"
        err = stderr.decode(errors="replace") if stderr else "未知错误"
        return f"按键失败: {err}"
    except asyncio.TimeoutError:
        return "按键超时"
    except Exception as e:
        return f"按键异常: {e}"


def _build_macos_key_command(key: str) -> str:
    """构建 macOS osascript 按键命令"""
    key_lower = key.lower().strip()

    # 处理组合键（如 cmd+v）
    if "+" in key_lower:
        parts = [p.strip() for p in key_lower.split("+")]
        modifiers = []
        main_key = parts[-1]
        for mod in parts[:-1]:
            if mod in ("cmd", "command"):
                modifiers.append("command down")
            elif mod in ("ctrl", "control"):
                modifiers.append("control down")
            elif mod in ("alt", "option"):
                modifiers.append("option down")
            elif mod == "shift":
                modifiers.append("shift down")
        using = " using {" + ", ".join(modifiers) + "}" if modifiers else ""
        script = f'tell application "System Events" to keystroke "{main_key}"{using}'
    else:
        mapped = _MACOS_KEY_MAP.get(key_lower, key_lower)
        if mapped in _MACOS_KEY_MAP.values():
            # 特殊按键使用 key code
            script = (
                f'tell application "System Events" to key code '
                f'{_get_macos_keycode(mapped)}'
            )
        else:
            # 普通文本按键使用 keystroke
            script = f'tell application "System Events" to keystroke "{mapped}"'

    return f"osascript -e '{script}'"


def _build_linux_key_command(key: str) -> str:
    """构建 Linux xdotool 按键命令"""
    key_lower = key.lower().strip()

    # 处理组合键
    if "+" in key_lower:
        parts = [p.strip() for p in key_lower.split("+")]
        xdo_parts = []
        for p in parts:
            if p in ("cmd", "command", "super"):
                xdo_parts.append("super")
            elif p in ("ctrl", "control"):
                xdo_parts.append("ctrl")
            elif p in ("alt", "option"):
                xdo_parts.append("alt")
            elif p == "shift":
                xdo_parts.append("shift")
            else:
                mapped = _LINUX_KEY_MAP.get(p, p)
                xdo_parts.append(mapped)
        combo = "+".join(xdo_parts)
        return f"xdotool key {combo}"

    mapped = _LINUX_KEY_MAP.get(key_lower, key_lower)
    return f"xdotool key {mapped}"


def _get_macos_keycode(key_name: str) -> int:
    """获取 macOS 按键码"""
    # 常用按键码映射
    codes = {
        "return": 36,
        "tab": 48,
        "escape": 53,
        "space": 49,
        "delete": 51,
        "forward delete": 117,
        "up arrow": 126,
        "down arrow": 125,
        "left arrow": 123,
        "right arrow": 124,
    }
    return codes.get(key_name, 36)  # 默认 return
