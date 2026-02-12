"""
平台检测 - mac / linux 自动适配

检测当前操作系统，提供平台相关的命令差异适配。
"""
import platform
from enum import Enum


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
        return "screencapture -x {path}"
    # Linux: 使用 scrot 或 gnome-screenshot
    return "scrot {path}"
