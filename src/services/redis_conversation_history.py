"""
Redis 近期对话记录服务

将近期对话记录存储在 Redis 中，服务端关闭后数据自动消失。
支持 Redis 不可用时降级到内存存储。
"""
import json
from typing import Dict, List, Optional

import redis
from loguru import logger
from redis import Redis

from config import settings


class RedisConversationHistory:
    """
    基于 Redis 的近期对话记录存储

    特点：
    - 使用 Redis List 存储对话消息，按时间顺序排列
    - 服务端关闭后 Redis 中的数据自动过期（TTL）
    - Redis 不可用时降级到内存字典存储
    """

    KEY_PREFIX = "conv_history"
    DEFAULT_TTL = 3600  # 默认 1 小时过期
    MAX_MESSAGES = 50  # 最大存储消息数

    def __init__(self, ttl: int = DEFAULT_TTL):
        self._redis: Optional[Redis] = None
        self._fallback: Dict[str, List[Dict]] = {}
        self._ttl = ttl
        self._init_redis()

    def _init_redis(self):
        """初始化 Redis 连接"""
        if settings.redis_url:
            try:
                self._redis = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
                self._redis.ping()
                logger.info("RedisConversationHistory: Redis connected successfully")
            except Exception as e:
                logger.warning(
                    f"RedisConversationHistory: Redis connection failed: {e}, "
                    f"using fallback mode"
                )
                self._redis = None
        else:
            logger.warning(
                "RedisConversationHistory: redis_url not configured, "
                "using fallback mode"
            )

    def _get_key(self, session_id: str) -> str:
        """生成 Redis key"""
        return f"{self.KEY_PREFIX}:{session_id}"

    def add_message(self, session_id: str, message: Dict[str, str]) -> None:
        """
        添加一条消息到对话记录

        Args:
            session_id: 会话 ID（格式: {user_id}_{bot_id}）
            message: 消息字典，包含 role, content 等字段
        """
        if self._redis:
            try:
                key = self._get_key(session_id)
                self._redis.rpush(key, json.dumps(message, ensure_ascii=False))
                # 保持列表长度不超过 MAX_MESSAGES
                self._redis.ltrim(key, -self.MAX_MESSAGES, -1)
                # 设置 TTL
                self._redis.expire(key, self._ttl)
                return
            except Exception as e:
                logger.warning(
                    f"RedisConversationHistory: Redis write failed: {e}, "
                    f"falling back to memory"
                )

        # 降级到内存
        if session_id not in self._fallback:
            self._fallback[session_id] = []
        self._fallback[session_id].append(message)
        if len(self._fallback[session_id]) > self.MAX_MESSAGES:
            self._fallback[session_id] = self._fallback[session_id][
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
        if self._redis:
            try:
                key = self._get_key(session_id)
                if limit:
                    raw_messages = self._redis.lrange(key, -limit, -1)
                else:
                    raw_messages = self._redis.lrange(key, 0, -1)
                # 刷新 TTL
                self._redis.expire(key, self._ttl)
                return [json.loads(msg) for msg in raw_messages]
            except Exception as e:
                logger.warning(
                    f"RedisConversationHistory: Redis read failed: {e}, "
                    f"falling back to memory"
                )

        # 降级到内存
        messages = self._fallback.get(session_id, [])
        if limit:
            return messages[-limit:]
        return list(messages)

    def clear_history(self, session_id: str) -> None:
        """
        清空指定会话的对话记录

        Args:
            session_id: 会话 ID
        """
        if self._redis:
            try:
                key = self._get_key(session_id)
                self._redis.delete(key)
                return
            except Exception as e:
                logger.warning(
                    f"RedisConversationHistory: Redis delete failed: {e}"
                )

        self._fallback.pop(session_id, None)


# 全局单例
_redis_history: Optional[RedisConversationHistory] = None


def get_redis_conversation_history() -> RedisConversationHistory:
    """获取全局 Redis 对话记录服务实例"""
    global _redis_history
    if _redis_history is None:
        _redis_history = RedisConversationHistory()
    return _redis_history
