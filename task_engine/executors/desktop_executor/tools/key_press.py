"""
键盘按键工具（Playwright 方案）

使用 Playwright 模拟键盘按键。
"""
from loguru import logger

from task_engine.executors.desktop_executor.tools.browser_session import get_page


async def key_press(key: str) -> str:
    """
    按下键盘按键

    Args:
        key: 按键名称（如 Enter、Tab、Escape 等）

    Returns:
        str: 操作结果描述
    """
    try:
        page = await get_page()
        await page.keyboard.press(key)
        logger.info(f"⌨️ [key_press] 已按下: {key}")
        return f"已按下: {key}"
    except Exception as e:
        return f"按键失败: {e}"
