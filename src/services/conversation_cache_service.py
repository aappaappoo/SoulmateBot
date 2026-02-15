"""
对话缓存服务
将近期对话记录和中期摘要记忆缓存到 Redis，避免每次从 MySQL 查询
使用 Redis 存储，支持高并发场景，Redis 不可用时降级到内存存储
"""
import json
from typing import Optional, List, Dict, Any
from loguru import logger
import redis
from redis import Redis

from config import settings


class ConversationCacheService:
    """
    对话缓存管理

    使用 Redis 缓存每个用户的近期对话记录和中期摘要记忆
    支持高并发和多实例部署
    """

    # Redis key 前缀
    HISTORY_KEY_PREFIX = "conv_history"
    SUMMARY_KEY_PREFIX = "conv_summary"
    # 对话历史最大条数
    MAX_HISTORY_SIZE = 50
    # 默认过期时间（秒），24小时
    DEFAULT_TTL = 86400

    def __init__(self):
        self._redis: Optional[Redis] = None
        self._fallback_history: dict = {}
        self._fallback_summary: dict = {}
        self._init_redis()

    def _init_redis(self):
        """初始化 Redis 连接"""
        if settings.redis_url:
            try:
                self._redis = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                self._redis.ping()
                logger.info("ConversationCacheService: Redis connected successfully")
            except Exception as e:
                logger.warning(f"ConversationCacheService: Redis connection failed: {e}, using fallback mode")
                self._redis = None
        else:
            logger.warning("ConversationCacheService: redis_url not configured, using fallback mode")

    def _history_key(self, session_id: str) -> str:
        """生成对话历史 Redis key"""
        return f"{self.HISTORY_KEY_PREFIX}:{session_id}"

    def _summary_key(self, chat_id: str, user_id: str) -> str:
        """生成摘要 Redis key"""
        return f"{self.SUMMARY_KEY_PREFIX}:{chat_id}:{user_id}"

    # ==================== 近期对话记录 ====================

    def get_conversation_history(self, session_id: str) -> Optional[List[Dict[str, str]]]:
        """
        从 Redis 获取近期对话记录

        Args:
            session_id: 会话ID (格式: user_id_bot_id)

        Returns:
            对话记录列表，缓存未命中返回 None
        """
        key = self._history_key(session_id)

        if self._redis:
            try:
                data = self._redis.get(key)
                if data:
                    logger.debug(f"ConversationCache HIT: {session_id}")
                    return json.loads(data)
                logger.debug(f"ConversationCache MISS: {session_id}")
                return None
            except Exception as e:
                logger.error(f"Redis get error: {e}")
                return self._fallback_history.get(key)
        else:
            return self._fallback_history.get(key)

    def set_conversation_history(self, session_id: str, history: List[Dict[str, str]]):
        """
        将对话记录缓存到 Redis

        Args:
            session_id: 会话ID
            history: 对话记录列表
        """
        key = self._history_key(session_id)
        # 限制最大条数
        if len(history) > self.MAX_HISTORY_SIZE:
            history = history[-self.MAX_HISTORY_SIZE:]

        data = json.dumps(history, ensure_ascii=False)

        if self._redis:
            try:
                self._redis.setex(key, self.DEFAULT_TTL, data)
            except Exception as e:
                logger.error(f"Redis set error: {e}")
                self._fallback_history[key] = history
        else:
            self._fallback_history[key] = history

    def append_conversation(self, session_id: str, user_msg: Dict[str, str], bot_msg: Dict[str, str]):
        """
        追加一轮对话到缓存

        Args:
            session_id: 会话ID
            user_msg: 用户消息 {"role": "user", "content": ..., "timestamp": ...}
            bot_msg: 助手消息 {"role": "assistant", "content": ...}
        """
        history = self.get_conversation_history(session_id) or []
        history.append(user_msg)
        history.append(bot_msg)
        self.set_conversation_history(session_id, history)

    # ==================== 中期摘要记忆 ====================

    def get_summary(self, chat_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        从 Redis 获取 LLM 生成的摘要

        Args:
            chat_id: 对话ID
            user_id: 用户ID

        Returns:
            摘要字典，缓存未命中返回 None
        """
        key = self._summary_key(chat_id, user_id)

        if self._redis:
            try:
                data = self._redis.get(key)
                if data:
                    return json.loads(data)
                return None
            except Exception as e:
                logger.error(f"Redis get error: {e}")
                return self._fallback_summary.get(key)
        else:
            return self._fallback_summary.get(key)

    def set_summary(self, chat_id: str, user_id: str, summary: Dict[str, Any]):
        """
        将 LLM 生成的摘要缓存到 Redis

        Args:
            chat_id: 对话ID
            user_id: 用户ID
            summary: 摘要字典
        """
        key = self._summary_key(chat_id, user_id)
        data = json.dumps(summary, ensure_ascii=False)

        if self._redis:
            try:
                self._redis.setex(key, self.DEFAULT_TTL, data)
            except Exception as e:
                logger.error(f"Redis set error: {e}")
                self._fallback_summary[key] = summary
        else:
            self._fallback_summary[key] = summary

    def health_check(self) -> dict:
        """健康检查"""
        status = {
            "redis_available": False,
            "mode": "fallback",
            "fallback_history_count": len(self._fallback_history),
            "fallback_summary_count": len(self._fallback_summary)
        }

        if self._redis:
            try:
                self._redis.ping()
                status["redis_available"] = True
                status["mode"] = "redis"
            except Exception as e:
                status["error"] = str(e)

        return status


# 全局实例
_conversation_cache_service: Optional[ConversationCacheService] = None


def get_conversation_cache_service() -> ConversationCacheService:
    """获取全局对话缓存服务实例"""
    global _conversation_cache_service
    if _conversation_cache_service is None:
        _conversation_cache_service = ConversationCacheService()
    return _conversation_cache_service
