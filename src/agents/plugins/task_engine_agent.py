"""
TaskEngine Agent - 任务引擎与 Agent 系统的桥接

将 TaskEngine 异步执行能力桥接到 BaseAgent 同步接口。
Agent 的选择完全由 LLM 根据 self._description 语义匹配决定，
不使用关键词列表或硬编码判断逻辑。

同步 Agent 接口中桥接异步 TaskEngine.run()
返回最终自然语言结果
"""
import asyncio
from typing import Any, Dict, List, Optional

from src.agents.base_agent import BaseAgent
from src.agents.models import AgentResponse, ChatContext, Message

from task_engine import TaskEngine


class TaskEngineAgent(BaseAgent):
    """
    TaskEngine 桥接 Agent

    当 LLM 根据描述判定为桌面操控意图后，调用 TaskEngine 执行多步骤桌面任务。
    Agent 选择完全由 LLM 基于 self._description 自主决定。
    """

    def __init__(self, memory_store=None, **kwargs) -> None:
        self._name = "TaskEngineAgent"
        self._description = (
            "桌面操控任务引擎，支持打开浏览器、搜索音乐、播放视频等自动化操作。"
            "适用于需要操控桌面应用、执行网页自动化、播放媒体内容等任务型请求。"
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
        return {}

    def get_skill_description(self, skill_id: str) -> Optional[str]:
        descriptions = {
            "desktop_control": "桌面操控，包括打开应用、点击、输入文本等",
            "music_play": "自动搜索并播放音乐",
            "web_automation": "自动化网页操作",
        }
        return descriptions.get(skill_id)

    def can_handle(self, message: Message, context: ChatContext) -> float:
        """
        返回基础置信度，实际选择由编排器中的 LLM 根据 description 决定。
        仅保留 @提及 的精确匹配。
        """
        if message.has_mention(self.name):
            return 1.0

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
            # 已在异步上下文中，在独立线程运行新事件循环避免死锁
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, self._engine.run(user_input))
                result_text = future.result(timeout=120)
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
        """
        读取任务执行的最小必要状态

        只保留：任务完成状态 + 执行次数（极简记忆策略）
        """
        return self._memory.get(user_id, {})

    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        """
        写入任务执行的最小必要状态

        只允许记录：
        - task_completed: 任务是否完成
        - task_count: 任务执行次数
        """
        minimal_data = {
            "task_completed": data.get("task_completed", False),
            "task_count": data.get("task_count", 0),
        }
        self._memory[user_id] = minimal_data
