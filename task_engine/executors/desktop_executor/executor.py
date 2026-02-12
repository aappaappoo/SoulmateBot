"""
桌面操控执行器 - Playwright 浏览器自动化方案

⭐ 这是整个 task_engine 中最关键的模块。

使用 Playwright 替代原先的视觉点击方案：
- 原方案：截图 → 视觉模型分析 → 坐标点击（已删除）
- 新方案：Playwright 直接操控浏览器 DOM

执行流程：
1. 解析用户意图，提取搜索关键词
2. 使用 Playwright 打开音乐网站
3. 在搜索框输入关键词并搜索
4. 点击第一首歌曲的播放按钮
"""
import re
from typing import Optional

from task_engine.models import Step, StepResult
from task_engine.executors.base import BaseExecutor
from task_engine.executors.desktop_executor.guard import GuardAction, TaskGuard


# 音乐搜索 URL 模板
_MUSIC_SEARCH_URL = "https://y.qq.com/n/ryqq/search?w={query}&t=song"


class DesktopExecutor(BaseExecutor):
    """
    桌面操控执行器

    通过 Playwright 浏览器自动化实现桌面操控。
    """

    def __init__(self) -> None:
        self._guard = TaskGuard()

    async def execute(self, step: Step) -> StepResult:
        """
        执行桌面操控任务

        Args:
            step: 包含 params["task"] 的步骤

        Returns:
            StepResult: 执行结果
        """
        task_text: str = step.params.get("task", "")
        if not task_text:
            return StepResult(success=False, message="缺少 task 参数")

        self._guard.reset()

        # 守卫检查任务文本
        action = self._guard.check("task", {"task": task_text}, task_text)
        if action == GuardAction.ABORT:
            return StepResult(
                success=False,
                message="安全守卫终止：检测到危险操作",
            )

        # 解析音乐搜索关键词
        query = self._extract_music_query(task_text)
        if not query:
            return StepResult(success=False, message="无法识别搜索关键词")

        # 使用 Playwright 播放音乐
        return await self._play_music(query)

    @staticmethod
    def _extract_music_query(task_text: str) -> Optional[str]:
        """
        从任务文本中提取音乐搜索关键词

        支持模式：
        - "输入XXX播放" → XXX
        - "搜索XXX播放" → XXX

        Args:
            task_text: 用户任务文本

        Returns:
            提取的关键词，或 None
        """
        match = re.search(r"输入(.+?)(?:播放|搜索|$)", task_text)
        if match:
            return match.group(1).strip()
        match = re.search(r"搜索(.+?)(?:播放|$)", task_text)
        if match:
            return match.group(1).strip()
        return None

    async def _play_music(self, query: str) -> StepResult:
        """
        使用 Playwright 在音乐网站搜索并播放

        Args:
            query: 搜索关键词（如 "周杰伦"）

        Returns:
            StepResult: 执行结果
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return StepResult(
                success=False,
                message="Playwright 未安装，请运行: pip install playwright && playwright install chromium",
            )

        browser = None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                # 1. 访问音乐搜索页
                search_url = _MUSIC_SEARCH_URL.format(query=query)
                await page.goto(search_url, timeout=30000)

                # 2. 等待歌曲列表加载
                await page.wait_for_selector(
                    ".songlist__list, .song-list, [class*='songlist']",
                    timeout=15000,
                )

                # 3. 点击第一首歌播放
                play_btn = page.locator(
                    ".songlist__item [class*='play'], "
                    ".song-list__item [class*='play'], "
                    "[class*='songlist'] [class*='play']"
                ).first
                await play_btn.click(timeout=10000)

                # 4. 等待播放启动
                await page.wait_for_timeout(3000)

                # 5. 获取歌曲信息
                song_info = await page.locator(
                    ".songlist__item a, .song-list__item a"
                ).first.text_content()
                song_name = (song_info or query).strip()

                await browser.close()
                browser = None

            return StepResult(
                success=True,
                message=f"已播放 {query} 的音乐: {song_name}",
                data={"query": query, "song": song_name},
            )
        except Exception as e:
            return StepResult(
                success=False,
                message=f"Playwright 播放失败: {e}",
                data={"query": query},
            )
        finally:
            if browser:
                await browser.close()
