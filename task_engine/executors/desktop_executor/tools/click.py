"""
元素点击工具（Playwright 方案）

通过 CSS 选择器定位并点击页面元素。
"""
from loguru import logger

from task_engine.executors.desktop_executor.tools.browser_session import get_page


async def click(selector: str) -> str:
    """
    通过选择器点击页面元素

    Args:
        selector: CSS 选择器

    Returns:
        str: 操作结果描述
    """
    try:
        page = await get_page()
        await page.click(selector, timeout=5000)
        logger.info(f"🖱️ [click] 已点击元素: {selector}")
        return f"已点击元素: {selector}"
    except Exception as e:
        return f"点击失败: {e}"
