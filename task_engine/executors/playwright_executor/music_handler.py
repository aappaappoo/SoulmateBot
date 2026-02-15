"""
Web 音乐搜索与播放处理器

通过 Playwright 自动化浏览器操作：
1. 打开音乐网站
2. 搜索歌手/歌曲
3. 点击播放

支持网站：
- 酷狗音乐 (kugou.com)
"""
import asyncio
import re
from dataclasses import dataclass
from typing import Optional

from loguru import logger

try:
    from playwright.async_api import Page, TimeoutError as PlaywrightTimeout
except ImportError:
    Page = None  # type: ignore
    PlaywrightTimeout = Exception  # type: ignore


@dataclass
class MusicResult:
    """音乐播放结果"""
    success: bool
    message: str
    song_title: str = ""
    artist: str = ""
    url: str = ""


def extract_search_keyword(user_input: str) -> str:
    """
    从用户自然语言输入中提取搜索关键词

    示例：
        "打开网页里的音乐输入周杰伦播放音乐" → "周杰伦"
        "播放音乐搜索五月天" → "五月天"

    Args:
        user_input: 用户原始输入

    Returns:
        str: 提取的搜索关键词
    """
    # 去除常见的操作指令词，保留核心搜索词
    noise_words = [
        "打开", "网页里的", "网页", "音乐", "输入", "播放",
        "搜索", "歌曲", "歌", "浏览器", "网站", "听",
        "里的", "的", "里", "帮我", "请", "去",
    ]

    text = user_input.strip()
    for word in noise_words:
        text = text.replace(word, " ")

    # 清理多余空格，取最长非空片段
    parts = [p.strip() for p in text.split() if p.strip()]
    if parts:
        # 返回最长的那个词段（通常是歌手名或歌曲名）
        return max(parts, key=len)

    # 回退：返回原始输入
    return user_input.strip()


async def search_and_play_music(page: "Page", keyword: str) -> MusicResult:
    """
    在酷狗音乐网站搜索并播放音乐

    流程：
    1. 打开酷狗音乐
    2. 在搜索框输入关键词
    3. 点击搜索
    4. 点击第一首歌的播放按钮

    Args:
        page: Playwright Page 实例
        keyword: 搜索关键词（歌手名或歌曲名）

    Returns:
        MusicResult: 播放结果
    """
    url = "https://www.kugou.com"
    logger.info(f"🎵 [MusicHandler] 打开酷狗音乐: {url}")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
    except PlaywrightTimeout:
        logger.warning("🎵 [MusicHandler] 酷狗音乐页面加载超时，尝试继续")
    except Exception as e:
        return MusicResult(
            success=False,
            message=f"打开酷狗音乐失败: {e}",
            url=url,
        )

    # 等待页面基本加载
    await asyncio.sleep(2)

    # 搜索流程
    result = await _kugou_search_and_play(page, keyword)
    if result.success:
        return result

    return MusicResult(
        success=False,
        message=f"在酷狗音乐搜索 '{keyword}' 未能播放，{result.message}",
        url=url,
    )


async def _kugou_search_and_play(page: "Page", keyword: str) -> MusicResult:
    """
    酷狗音乐搜索并播放

    Args:
        page: Playwright Page 实例
        keyword: 搜索关键词

    Returns:
        MusicResult: 播放结果
    """
    logger.info(f"🔍 [MusicHandler] 在酷狗搜索: {keyword}")

    # 策略1: 直接使用搜索URL导航
    search_url = f"https://www.kugou.com/yy/html/search.html#searchType=song&searchKeyWord={keyword}"
    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
    except PlaywrightTimeout:
        logger.warning("🎵 [MusicHandler] 搜索页面加载超时，尝试继续")
    except Exception as e:
        return MusicResult(success=False, message=f"搜索页面加载失败: {e}")

    await asyncio.sleep(3)

    # 尝试查找并点击第一首歌
    play_result = await _try_click_first_song(page, keyword)
    if play_result.success:
        return play_result

    # 策略2: 尝试在当前页面找搜索框并输入
    search_filled = await _try_fill_search_box(page, keyword)
    if search_filled:
        await asyncio.sleep(3)
        play_result = await _try_click_first_song(page, keyword)
        if play_result.success:
            return play_result

    return MusicResult(success=False, message="未找到可播放的搜索结果")


async def _try_fill_search_box(page: "Page", keyword: str) -> bool:
    """
    尝试在页面中找到搜索框并输入关键词

    Args:
        page: Playwright Page 实例
        keyword: 搜索关键词

    Returns:
        bool: 是否成功输入
    """
    search_selectors = [
        'input#search_key',
        'input[name="searchKeyWord"]',
        'input[type="search"]',
        'input[placeholder*="搜索"]',
        'input[placeholder*="search" i]',
        'input.search-input',
        '#searchInput',
    ]

    for selector in search_selectors:
        try:
            search_box = page.locator(selector).first
            if await search_box.is_visible(timeout=2000):
                await search_box.click()
                await search_box.fill(keyword)
                await page.keyboard.press("Enter")
                logger.info(f"✅ [MusicHandler] 已在搜索框输入: {keyword}")
                return True
        except Exception:
            continue

    logger.warning("⚠️ [MusicHandler] 未找到搜索框")
    return False


async def _try_click_first_song(page: "Page", keyword: str) -> MusicResult:
    """
    尝试在搜索结果中点击第一首歌

    Args:
        page: Playwright Page 实例
        keyword: 搜索关键词

    Returns:
        MusicResult: 播放结果
    """
    # 酷狗搜索结果中的歌曲链接选择器
    song_selectors = [
        '.song_name a',
        '.song-name a',
        'a.song_name',
        '.songname a',
        '.song_list .song_name',
        'table.song_list td.song_name a',
        '.search_list_content a',
        '#search_song_list a',
    ]

    for selector in song_selectors:
        try:
            song_link = page.locator(selector).first
            if await song_link.is_visible(timeout=3000):
                song_title = await song_link.text_content() or ""
                song_title = song_title.strip()

                # 在新页面中打开（酷狗歌曲页面通常会自动播放）
                async with page.context.expect_page(timeout=10000) as new_page_info:
                    await song_link.click()

                new_page = await new_page_info.value
                await asyncio.sleep(3)

                logger.info(f"🎵 [MusicHandler] 已打开歌曲: {song_title}")

                # 尝试在新页面点击播放按钮
                await _try_click_play_button(new_page)

                return MusicResult(
                    success=True,
                    message=f"已在酷狗音乐搜索并播放 '{keyword}' 的音乐：{song_title}",
                    song_title=song_title,
                    artist=keyword,
                    url=new_page.url,
                )
        except PlaywrightTimeout:
            continue
        except Exception as e:
            logger.debug(f"选择器 {selector} 尝试失败: {e}")
            continue

    # 尝试通用的链接点击（包含关键词的链接）
    try:
        link = page.locator(f'a:has-text("{keyword}")').first
        if await link.is_visible(timeout=3000):
            link_text = await link.text_content() or keyword
            link_text = link_text.strip()

            try:
                async with page.context.expect_page(timeout=10000) as new_page_info:
                    await link.click()
                new_page = await new_page_info.value
                await asyncio.sleep(3)
                await _try_click_play_button(new_page)
            except PlaywrightTimeout:
                # 没有打开新页面，可能在当前页面操作
                await asyncio.sleep(2)
                await _try_click_play_button(page)

            return MusicResult(
                success=True,
                message=f"已在酷狗音乐搜索并播放 '{keyword}' 的音乐：{link_text}",
                song_title=link_text,
                artist=keyword,
                url=page.url,
            )
    except Exception:
        pass

    return MusicResult(success=False, message="搜索结果中未找到可点击的歌曲")


async def _try_click_play_button(page: "Page") -> bool:
    """
    尝试在页面上点击播放按钮

    Args:
        page: Playwright Page 实例

    Returns:
        bool: 是否成功点击
    """
    play_selectors = [
        '.play_btn',
        '.play-btn',
        'button.play',
        '[class*="play"]',
        '.btn-play',
        '#play_btn',
        '.playBtn',
    ]

    for selector in play_selectors:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                logger.info(f"▶️ [MusicHandler] 已点击播放按钮: {selector}")
                return True
        except Exception:
            continue

    logger.debug("⚠️ [MusicHandler] 未找到播放按钮（页面可能自动播放）")
    return False
