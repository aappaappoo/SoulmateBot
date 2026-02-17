"""
内存对话记录服务

将近期对话记录（短期和中期）存储在内存中，通过 session_id（{user_id}_{bot_id}）
实现多用户多Bot下的记忆隔离。服务端关闭后数据自动消失。

短期记忆：最近 5 轮用户消息及后续
中期记忆：最近 6～20 轮用户消息及后续
"""
from typing import Dict, List, Optional

from loguru import logger


class InMemoryConversationHistory:
    """
    基于内存的近期对话记录存储

    特点：
    - 使用内存字典存储，通过 session_id（{user_id}_{bot_id}）实现多用户多Bot隔离
    - 服务端关闭后数据自动消失
    - 短期记忆来自最近 5 轮用户消息及后续
    - 中期记忆来自最近 6～20 轮用户消息及后续
    """

    MAX_MESSAGES = 50  # 最大存储消息数

    def __init__(self):
        self._store: Dict[str, List[Dict]] = {}
        logger.info("InMemoryConversationHistory: initialized")

    def add_message(self, session_id: str, message: Dict[str, str]) -> None:
        """
        添加一条消息到对话记录

        Args:
            session_id: 会话 ID（格式: {user_id}_{bot_id}）
            message: 消息字典，包含 role, content 等字段
        """
        if session_id not in self._store:
            self._store[session_id] = []
        self._store[session_id].append(message)
        if len(self._store[session_id]) > self.MAX_MESSAGES:
            self._store[session_id] = self._store[session_id][
                -self.MAX_MESSAGES :
            ]

    def get_history(
        self, session_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        获取近期对话记录

        Args:
            session_id: 会话 ID
            limit: 最大返回消息数（None 表示返回所有）

        Returns:
            对话消息列表
        """
        messages = self._store.get(session_id, [])
        if limit:
            return messages[-limit:]
        return list(messages)

    def clear_history(self, session_id: str) -> None:
        """
        清空指定会话的对话记录

        Args:
            session_id: 会话 ID
        """
        self._store.pop(session_id, None)


# 全局单例
_memory_history: Optional[InMemoryConversationHistory] = None


def get_conversation_history() -> InMemoryConversationHistory:
    """获取全局内存对话记录服务实例"""
    global _memory_history
    if _memory_history is None:
        _memory_history = InMemoryConversationHistory()
    return _memory_history


# 向后兼容别名
RedisConversationHistory = InMemoryConversationHistory
get_redis_conversation_history = get_conversation_history
