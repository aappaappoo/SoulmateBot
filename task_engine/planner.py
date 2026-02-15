"""
任务规划器 - 使用 LLM 识别 desktop / playwright 任务，生成对应 step

设计理念：
- 使用 LLM 对用户输入进行语义理解和意图分类
- 分为三类：playwright（web 音乐场景）、desktop（桌面操控）、llm（普通文本）
- 只返回 1 个 step
- planner 只做粗粒度规划，细节由各执行器内部自主决定
"""
import json

import aiohttp
from loguru import logger

from config import settings
from .models import ExecutorType, Step, Task

# LLM 配置
_PLANNER_LLM_URL = getattr(settings, "executor_llm_url", None) or getattr(settings, "vllm_api_url", None)
_PLANNER_LLM_MODEL = getattr(settings, "executor_llm_model", None) or getattr(settings, "vllm_model", "default")
_PLANNER_LLM_TOKEN = getattr(settings, "executor_llm_token", None) or getattr(settings, "vllm_api_token", None)

# 任务分类 system prompt
_CLASSIFY_SYSTEM_PROMPT = """你是一个任务意图分类器。根据用户输入，判断任务类型并返回 JSON。

任务类型说明：
- "playwright"：用户想通过网页浏览器播放音乐或搜索歌曲（web 音乐播放场景）
- "desktop"：用户想操控桌面应用，如打开浏览器、点击按钮、输入文本、播放视频、下载安装软件、截图等
- "llm"：普通的对话或文本问答，不涉及桌面操控或网页自动化

你必须只返回以下 JSON 格式，不要添加任何其他文本：
{"task_type": "playwright" | "desktop" | "llm", "description": "简短描述任务内容"}
"""


async def plan(user_input: str) -> Task:
    """
    根据用户输入生成任务执行计划（使用 LLM 进行意图分类）

    Args:
        user_input: 用户原始自然语言输入

    Returns:
        Task: 包含步骤列表的任务对象
    """
    task = Task(user_input=user_input)

    task_type = await _classify_task_with_llm(user_input)

    if task_type == "playwright":
        step = Step(
            executor_type=ExecutorType.PLAYWRIGHT,
            description="Web 音乐播放任务",
            params={"task": user_input},
        )
    elif task_type == "desktop":
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


async def _classify_task_with_llm(text: str) -> str:
    """
    使用 LLM 对用户输入进行任务类型分类

    Args:
        text: 用户输入文本

    Returns:
        str: 任务类型 ("playwright" | "desktop" | "llm")
    """
    if not _PLANNER_LLM_URL:
        logger.warning("⚠️ [Planner] LLM URL 未配置，回退到 llm 类型")
        return "llm"

    messages = [
        {"role": "system", "content": _CLASSIFY_SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]

    headers = {"Content-Type": "application/json"}
    if _PLANNER_LLM_TOKEN:
        headers["Authorization"] = f"Bearer {_PLANNER_LLM_TOKEN}"

    payload = {
        "model": _PLANNER_LLM_MODEL,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 100,
    }

    try:
        async with aiohttp.ClientSession() as session:
            api_url = _PLANNER_LLM_URL.rstrip("/")
            async with session.post(
                f"{api_url}/v1/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"❌ [Planner] LLM API 错误: {response.status} - {error_text}")
                    return "llm"

                result = await response.json()
                content = result["choices"][0]["message"]["content"].strip()

                # 解析 JSON 响应
                task_type = _parse_llm_classification(content)
                logger.debug(f"🔍 [Planner] LLM 分类结果: input='{text}' -> task_type='{task_type}'")
                return task_type

    except Exception as e:
        logger.error(f"❌ [Planner] LLM 分类失败: {e}，回退到 llm 类型")
        return "llm"


def _parse_llm_classification(content: str) -> str:
    """
    解析 LLM 返回的分类 JSON

    Args:
        content: LLM 返回的原始文本

    Returns:
        str: 任务类型 ("playwright" | "desktop" | "llm")
    """
    try:
        # 尝试提取 JSON（处理可能的 markdown 代码块包裹）
        json_str = content
        if "```" in content:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                json_str = content[start:end]

        parsed = json.loads(json_str)
        task_type = parsed.get("task_type", "llm").lower()

        if task_type in ("playwright", "desktop", "llm"):
            return task_type

        logger.warning(f"⚠️ [Planner] 未知任务类型: {task_type}，回退到 llm")
        return "llm"

    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        # JSONDecodeError: 无效 JSON
        # AttributeError: parsed 不是 dict 时调用 .get() 失败
        # TypeError: parsed 为 None 或非预期类型
        logger.warning(f"⚠️ [Planner] JSON 解析失败: {e}, content='{content}'")
        return "llm"
