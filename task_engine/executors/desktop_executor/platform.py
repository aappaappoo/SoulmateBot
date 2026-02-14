"""
平台检测 - mac / linux 自动适配

检测当前操作系统，提供平台相关的命令差异适配。
"""
import asyncio
import platform
from enum import Enum
from typing import Optional, Tuple


class PlatformType(str, Enum):
    """支持的平台类型"""
    MACOS = "macos"
    LINUX = "linux"
    UNKNOWN = "unknown"


def detect_platform() -> PlatformType:
    """
    检测当前操作系统平台

    Returns:
        PlatformType: 当前平台类型
    """
    system = platform.system().lower()
    if system == "darwin":
        return PlatformType.MACOS
    elif system == "linux":
        return PlatformType.LINUX
    return PlatformType.UNKNOWN


def get_open_command() -> str:
    """
    获取平台对应的打开命令

    Returns:
        str: macOS 返回 'open'，Linux 返回 'xdg-open'
    """
    p = detect_platform()
    if p == PlatformType.MACOS:
        return "open"
    return "xdg-open"


def get_screenshot_command() -> str:
    """
    获取平台对应的截图命令

    Returns:
        str: 截图命令模板，包含 {path} 占位符
    """
    p = detect_platform()
    if p == PlatformType.MACOS:
        return "screencapture -t jpg -x {path}"
    # Linux: 使用 scrot 或 gnome-screenshot
    return "scrot {path}"


async def get_screen_resolution() -> Optional[Tuple[int, int]]:
    """
    获取屏幕逻辑分辨率（非 Retina/HiDPI 物理像素）

    macOS Retina 屏幕的截图像素尺寸通常是逻辑分辨率的 2 倍，
    而 osascript 点击坐标使用的是逻辑分辨率坐标系。
    此函数返回逻辑分辨率，用于将截图像素坐标映射到屏幕坐标。

    Returns:
        (width, height) 逻辑分辨率元组，获取失败返回 None
    """
    p = detect_platform()

    try:
        if p == PlatformType.MACOS:
            # macOS: 使用 system_profiler 获取逻辑分辨率
            cmd = (
                "system_profiler SPDisplaysDataType "
                "| grep Resolution "
                "| head -1 "
                "| awk '{print $2, $4}'"
            )
        else:
            # Linux: 使用 xdpyinfo 或 xrandr
            cmd = "xdpyinfo | grep dimensions | awk '{print $2}' | tr 'x' ' '"

        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)

        if proc.returncode == 0 and stdout:
            parts = stdout.decode().strip().split()
            if len(parts) >= 2:
                return (int(parts[0]), int(parts[1]))
    except Exception:
        pass

    return None
