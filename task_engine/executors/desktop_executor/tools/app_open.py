"""
打开浏览器或 URL 工具（Playwright 方案）
"""
from loguru import logger

from task_engine.executors.desktop_executor.tools.browser_session import get_page


async def app_open(url: str) -> str:
    """
    使用 Playwright 打开浏览器并访问指定 URL

    Args:
        url: 要打开的 URL

    Returns:
        str: 操作结果描述
    """
    try:
        page = await get_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        title = await page.title()
        logger.info(f"🌐 [app_open] 已打开: {url}, 标题: {title}")
        return f"已打开: {url}，页面标题: {title}"
    except Exception as e:
        return f"打开失败: {e}"
