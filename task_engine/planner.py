"""
任务规划器 - 识别 desktop 任务，仅生成 1 个 desktop step

设计理念：
- 若用户意图包含 打开/网页/点击/输入/播放 等关键词 → desktop 类型
- 只返回 1 个 step：executor_type=DESKTOP, params.task=完整自然语言任务
- planner 只做粗粒度规划，细节由 desktop_executor 内部 LLM 自主决定
"""
from typing import List

from .models import ExecutorType, Step, Task


# 桌面操控意图关键词
_DESKTOP_KEYWORDS: List[str] = [
    "打开", "网页", "浏览器", "点击", "输入",
    "播放", "音乐", "搜索歌曲", "视频", "网站",
    "下载", "安装", "截图", "屏幕", "桌面",
]


async def plan(user_input: str) -> Task:
    """
    根据用户输入生成任务执行计划

    规则：
    - 匹配桌面操控关键词 → 生成 1 个 DESKTOP step
    - 否则 → 生成 1 个 LLM step（兜底）

    Args:
        user_input: 用户原始自然语言输入

    Returns:
        Task: 包含步骤列表的任务对象
    """
    task = Task(user_input=user_input)

    if _is_desktop_task(user_input):
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
