"""
任务规划器 - 识别 desktop / playwright 任务，生成对应 step

设计理念：
- 若用户意图包含 打开/网页 + 音乐/播放/搜索歌曲 等关键词 → playwright 类型（web 音乐场景）
- 若用户意图包含 打开/网页/点击/输入/播放 等关键词 → desktop 类型
- 只返回 1 个 step
- planner 只做粗粒度规划，细节由各执行器内部自主决定
"""
from typing import List

from .models import ExecutorType, Step, Task


# 桌面操控意图关键词
_DESKTOP_KEYWORDS: List[str] = [
    "打开", "网页", "浏览器", "点击", "输入",
    "播放", "音乐", "搜索歌曲", "视频", "网站",
    "下载", "安装", "截图", "屏幕", "桌面",
]

# Web 音乐播放场景关键词（需同时命中 web + music 两组）
_WEB_KEYWORDS: List[str] = ["网页", "浏览器", "网站", "打开"]
_MUSIC_KEYWORDS: List[str] = ["音乐", "搜索歌曲", "听歌", "歌曲"]


async def plan(user_input: str) -> Task:
    """
    根据用户输入生成任务执行计划

    规则：
    - 同时匹配 web + music 关键词 → 生成 1 个 PLAYWRIGHT step
    - 匹配桌面操控关键词 → 生成 1 个 DESKTOP step
    - 否则 → 生成 1 个 LLM step（兜底）

    Args:
        user_input: 用户原始自然语言输入

    Returns:
        Task: 包含步骤列表的任务对象
    """
    task = Task(user_input=user_input)

    if _is_web_music_task(user_input):
        step = Step(
            executor_type=ExecutorType.PLAYWRIGHT,
            description="Web 音乐播放任务",
            params={"task": user_input},
        )
    elif _is_desktop_task(user_input):
        step = Step(
            executor_type=ExecutorType.DESKTOP,
            description="桌面操控任务",
            params={"task": user_input},
        )
    else:
        step = Step(
            executor_type=ExecutorType.LLM,
            description="LLM 文本回答",
            params={"task": user_input},
        )

    task.steps.append(step)
    return task


def _is_web_music_task(text: str) -> bool:
    """
    判断用户输入是否为 web 音乐播放任务

    同时命中 web 关键词和 music 关键词视为 web 音乐任务

    Args:
        text: 用户输入文本

    Returns:
        bool: 是否为 web 音乐播放任务
    """
    has_web = any(kw in text for kw in _WEB_KEYWORDS)
    has_music = any(kw in text for kw in _MUSIC_KEYWORDS)
    return has_web and has_music


def _is_desktop_task(text: str) -> bool:
    """
    判断用户输入是否为桌面操控任务

    通过关键词匹配判断，命中 ≥2 个关键词视为桌面任务

    Args:
        text: 用户输入文本

    Returns:
        bool: 是否为桌面操控任务
    """
    hit_count = sum(1 for kw in _DESKTOP_KEYWORDS if kw in text)
    return hit_count >= 2
