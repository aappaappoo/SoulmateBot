"""
Playwright 执行器 - 基于 Playwright 的 Web 自动化

针对 Web 音乐播放场景，使用 Playwright 无头浏览器：
1. 启动 Chromium（headless）
2. 打开音乐网站
3. 搜索关键词
4. 点击播放

优势：
- 无需 VLM 视觉模型，不依赖截图分析
- 无需 xdotool / osascript 等桌面工具
- 支持 headless 模式，可在服务器环境运行
- 通过 CSS 选择器精准定位元素
"""
from loguru import logger

from task_engine.models import Step, StepResult
from task_engine.executors.base import BaseExecutor
from task_engine.executors.playwright_executor.browser_manager import browser_manager
from task_engine.executors.playwright_executor.music_handler import (
    extract_search_keyword,
    search_and_play_music,
)


class PlaywrightExecutor(BaseExecutor):
    """
    Playwright Web 自动化执行器

    通过 Playwright 浏览器自动化完成 Web 音乐播放任务。
    """

    async def execute(self, step: Step) -> StepResult:
        """
        执行 Web 音乐播放任务

        Args:
            step: 包含 params["task"] 的步骤

        Returns:
            StepResult: 执行结果
        """
        task_text: str = step.params.get("task", "")
        if not task_text:
            return StepResult(success=False, message="缺少 task 参数")

        logger.info(f"🎵 [PlaywrightExecutor] 开始 Web 音乐任务: {task_text}")

        # 提取搜索关键词
        keyword = extract_search_keyword(task_text)
        logger.info(f"🔑 [PlaywrightExecutor] 提取关键词: {keyword}")

        context = None
        try:
            # 创建浏览器上下文和页面
            context = await browser_manager.new_context()
            page = await context.new_page()

            # 搜索并播放音乐
            result = await search_and_play_music(page, keyword)

            if result.success:
                logger.info(f"✅ [PlaywrightExecutor] 音乐播放成功: {result.message}")
                return StepResult(
                    success=True,
                    message=result.message,
                    data={
                        "song_title": result.song_title,
                        "artist": result.artist,
                        "url": result.url,
                    },
                )
            else:
                logger.warning(f"❌ [PlaywrightExecutor] 音乐播放失败: {result.message}")
                return StepResult(success=False, message=result.message)

        except RuntimeError as e:
            # playwright 未安装
            logger.error(f"❌ [PlaywrightExecutor] 环境错误: {e}")
            return StepResult(success=False, message=str(e))
        except Exception as e:
            logger.error(f"❌ [PlaywrightExecutor] 执行异常: {e}")
            return StepResult(success=False, message=f"Web 自动化执行异常: {e}")
        finally:
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
