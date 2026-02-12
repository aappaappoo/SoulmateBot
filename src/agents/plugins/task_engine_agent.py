"""
TaskEngine Agent - 任务引擎与 Agent 系统的桥接

将 TaskEngine 异步执行能力桥接到 BaseAgent 同步接口，
通过关键词匹配检测桌面操控意图。

关键词命中（打开/网页/音乐/播放…）→ 高置信度
同步 Agent 接口中桥接异步 TaskEngine.run()
返回最终自然语言结果
"""
import asyncio
from typing import Any, Dict, List, Optional

from src.agents.base_agent import BaseAgent
from src.agents.models import AgentResponse, ChatContext, Message

from task_engine import TaskEngine

# 桌面操控意图关键词
_TASK_KEYWORDS: List[str] = [
    "打开", "网页", "浏览器", "音乐", "播放",
    "点击", "输入", "搜索歌曲", "视频", "网站",
    "桌面", "截图", "屏幕",
]


class TaskEngineAgent(BaseAgent):
    """
    TaskEngine 桥接 Agent

    检测桌面操控意图后，调用 TaskEngine 执行多步骤桌面任务。
    """

    def __init__(self, memory_store=None, **kwargs) -> None:
        self._name = "TaskEngineAgent"
        self._description = (
            "桌面操控任务引擎，支持打开浏览器、搜索音乐、播放视频等自动化操作。"
        )
        self._memory: Dict[str, Dict[str, Any]] = {}
        self._engine = TaskEngine()

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def skills(self) -> List[str]:
        return ["desktop_control", "music_play", "web_automation"]

    @property
    def skill_keywords(self) -> Dict[str, List[str]]:
        return {
            "desktop_control": ["打开", "点击", "输入", "桌面", "截图"],
            "music_play": ["音乐", "播放", "歌曲"],
            "web_automation": ["网页", "浏览器", "网站"],
        }

    def get_skill_description(self, skill_id: str) -> Optional[str]:
        descriptions = {
            "desktop_control": "桌面操控，包括打开应用、点击、输入文本等",
            "music_play": "自动搜索并播放音乐",
            "web_automation": "自动化网页操作",
        }
        return descriptions.get(skill_id)

    def can_handle(self, message: Message, context: ChatContext) -> float:
        """
        判断是否为桌面操控任务

        通过关键词匹配计算置信度：
        - @提及 → 1.0
        - 命中 ≥3 个关键词 → 0.9
        - 命中 2 个 → 0.75
        - 命中 1 个 → 0.4
        - 无命中 → 0.0
        """
        if message.has_mention(self.name):
            return 1.0

        content = message.content
        hit_count = sum(1 for kw in _TASK_KEYWORDS if kw in content)

        if hit_count >= 3:
            return 0.9
        elif hit_count == 2:
            return 0.75
        elif hit_count == 1:
            return 0.4
        return 0.0

    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        """
        执行桌面操控任务并返回结果

        通过 asyncio 桥接异步 TaskEngine.run()
        """
        user_input = message.get_clean_content()

        # 桥接异步 TaskEngine
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # 已在异步上下文中（如 Telegram handler），创建新任务
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result_text = pool.submit(
                    asyncio.run, self._engine.run(user_input)
                ).result(timeout=120)
        else:
            result_text = asyncio.run(self._engine.run(user_input))

        return AgentResponse(
            content=result_text,
            agent_name=self.name,
            confidence=0.9,
            metadata={"task_type": "desktop", "user_input": user_input},
            should_continue=False,
        )

    def memory_read(self, user_id: str) -> Dict[str, Any]:
        return self._memory.get(user_id, {})

    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        self._memory[user_id] = data
