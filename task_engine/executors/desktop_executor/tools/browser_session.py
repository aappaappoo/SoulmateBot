"""
Playwright 浏览器会话管理 - 单例模式

管理全局 Playwright 浏览器实例和页面，供各工具共享。
"""
import asyncio

from loguru import logger


_browser = None
_page = None
_playwright = None
_loop_id = None


async def get_page():
    """
    获取当前 Playwright 页面实例（懒加载单例）

    如果事件循环发生变化（如测试环境），自动重新创建浏览器实例。

    Returns:
        Page: Playwright 页面对象
    """
    global _browser, _page, _playwright, _loop_id

    current_loop_id = id(asyncio.get_event_loop())

    # 事件循环变化时重置
    if _loop_id is not None and _loop_id != current_loop_id:
        _browser = None
        _page = None
        _playwright = None
        _loop_id = None

    # 尝试复用现有页面
    if _page is not None:
        try:
            if not _page.is_closed():
                return _page
        except Exception:
            pass
        _page = None
        _browser = None
        _playwright = None

    from playwright.async_api import async_playwright

    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(headless=True)
    _page = await _browser.new_page()
    _loop_id = current_loop_id
    logger.info("🌐 [browser_session] Playwright 浏览器已启动")
    return _page


async def close_browser() -> None:
    """关闭浏览器和 Playwright 实例"""
    global _browser, _page, _playwright, _loop_id

    try:
        if _page and not _page.is_closed():
            await _page.close()
    except Exception:
        pass
    _page = None

    try:
        if _browser:
            await _browser.close()
    except Exception:
        pass
    _browser = None

    try:
        if _playwright:
            await _playwright.stop()
    except Exception:
        pass
    _playwright = None
    _loop_id = None

    logger.info("🌐 [browser_session] Playwright 浏览器已关闭")
