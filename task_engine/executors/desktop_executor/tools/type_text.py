"""
文本输入工具（Playwright 方案）

通过 CSS 选择器定位输入框并填入文本。
"""
from loguru import logger

from task_engine.executors.desktop_executor.tools.browser_session import get_page


async def type_text(selector: str, text: str) -> str:
    """
    在指定输入框中填入文本

    Args:
        selector: 输入框的 CSS 选择器
        text: 要输入的文本

    Returns:
        str: 操作结果描述
    """
    try:
        page = await get_page()
        await page.fill(selector, text, timeout=5000)
        logger.info(f"⌨️ [type_text] 已输入文本: {text} -> {selector}")
        return f"已输入文本: {text}"
    except Exception as e:
        return f"输入失败: {e}"
