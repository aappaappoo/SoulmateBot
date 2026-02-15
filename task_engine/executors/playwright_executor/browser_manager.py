"""
浏览器生命周期管理 - Playwright 浏览器单例

管理 Chromium 浏览器实例的创建和销毁，支持 headless 模式。
"""
import asyncio
from typing import Optional

from loguru import logger

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright
except ImportError:
    async_playwright = None  # type: ignore
    Browser = None  # type: ignore
    BrowserContext = None  # type: ignore
    Playwright = None  # type: ignore


class BrowserManager:
    """
    Playwright 浏览器单例管理器

    确保全局只有一个浏览器实例，避免重复启动。
    """

    def __init__(self) -> None:
        self._playwright: Optional["Playwright"] = None
        self._browser: Optional["Browser"] = None
        self._lock = asyncio.Lock()

    async def get_browser(self) -> "Browser":
        """
        获取或创建浏览器实例

        Returns:
            Browser: Playwright 浏览器实例

        Raises:
            RuntimeError: playwright 未安装
        """
        if async_playwright is None:
            raise RuntimeError(
                "playwright 未安装，请运行: pip install playwright && python -m playwright install chromium"
            )

        async with self._lock:
            if self._browser is None or not self._browser.is_connected():
                logger.info("🌐 [BrowserManager] 启动 Chromium 浏览器")
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    # 1. 调试阶段建议设为 False，能看到浏览器界面和播放状态
                    headless=False,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--audio-output-channels=2",
                    ],
                )
            return self._browser

    async def new_context(self) -> "BrowserContext":
        """
        创建新的浏览器上下文（独立的 cookie / 存储）

        Returns:
            BrowserContext: 浏览器上下文
        """
        browser = await self.get_browser()
        return await browser.new_context(
            viewport={"width": 1280, "height": 720},
            locale="zh-CN",
        )

    async def close(self) -> None:
        """关闭浏览器和 Playwright 实例"""
        async with self._lock:
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    pass
                self._browser = None
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None
                logger.info("🌐 [BrowserManager] 浏览器已关闭")


# 全局单例
browser_manager = BrowserManager()
