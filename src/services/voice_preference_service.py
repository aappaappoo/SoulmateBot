"""
用户语音偏好服务
管理用户是否开启语音回复的设置
使用 Redis 存储，支持高并发场景
"""
from typing import Optional
from loguru import logger
import redis
from redis import Redis

from config import settings


class VoicePreferenceService:
    """
    用户语音偏好管理

    使用 Redis 存储每个用户对每个 Bot 的语音偏好设置
    支持高并发和多实例部署
    """
    
    # Redis key 前缀
    KEY_PREFIX = "voice_pref"
    # 默认过期时间（秒），0 表示永不过期
    DEFAULT_TTL = 0

    def __init__(self):
        self._redis: Optional[Redis] = None
        self._fallback_preferences: dict = {}  # Redis 不可用时的降级方案
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
                # 测试连接（5秒超时，失败时自动降级到 fallback 模式）
                self._redis.ping()
                logger.info(f"VoicePreferenceService: Redis connected successfully")
            except Exception as e:
                logger.warning(f"VoicePreferenceService: Redis connection failed: {e}, using fallback mode")
                self._redis = None
        else:
            logger.warning("VoicePreferenceService: redis_url not configured, using fallback mode")

    def _get_key(self, user_id: int, bot_username: str) -> str:
        """生成 Redis 存储键"""
        return f"{self.KEY_PREFIX}:{user_id}:{bot_username}"

    def is_voice_enabled(self, user_id: int, bot_username: str) -> bool:
        """
        检查用户是否开启了语音回复

        Args:
            user_id: 用户 Telegram ID
            bot_username: Bot 用户名

        Returns:
            bool: 是否开启语音
        """
        key = self._get_key(user_id, bot_username)
        
        if self._redis:
            try:
                value = self._redis.get(key)
                return value == "1"
            except Exception as e:
                logger.error(f"Redis get error: {e}")
                # 降级到内存存储
                return self._fallback_preferences.get(key, False)
        else:
            return self._fallback_preferences.get(key, False)

    def set_voice_enabled(self, user_id: int, bot_username: str, enabled: bool):
        """
        设置用户的语音偏好

        Args:
            user_id: 用户 Telegram ID
            bot_username: Bot 用户名
            enabled: 是否开启
        """
        key = self._get_key(user_id, bot_username)
        value = "1" if enabled else "0"
        
        if self._redis:
            try:
                if self.DEFAULT_TTL > 0:
                    self._redis.setex(key, self.DEFAULT_TTL, value)
                else:
                    self._redis.set(key, value)
                logger.info(f"Voice preference set (Redis): user={user_id}, bot={bot_username}, enabled={enabled}")
            except Exception as e:
                logger.error(f"Redis set error: {e}")
                # 降级到内存存储
                self._fallback_preferences[key] = enabled
                logger.info(f"Voice preference set (fallback): user={user_id}, bot={bot_username}, enabled={enabled}")
        else:
            self._fallback_preferences[key] = enabled
            logger.info(f"Voice preference set (fallback): user={user_id}, bot={bot_username}, enabled={enabled}")

    def toggle_voice(self, user_id: int, bot_username: str) -> bool:
        """
        切换语音开关状态

        Returns:
            bool: 切换后的状态
        """
        current = self.is_voice_enabled(user_id, bot_username)
        new_state = not current
        self.set_voice_enabled(user_id, bot_username, new_state)
        return new_state
    
    def get_all_preferences_for_user(self, user_id: int) -> dict:
        """
        获取用户对所有 Bot 的语音偏好设置
        
        Args:
            user_id: 用户 Telegram ID
            
        Returns:
            dict: {bot_username: enabled} 格式的字典
        """
        pattern = f"{self.KEY_PREFIX}:{user_id}:*"
        preferences = {}
        
        if self._redis:
            try:
                # 使用 scan_iter 而不是 keys，避免阻塞 Redis 服务器
                for key in self._redis.scan_iter(match=pattern):
                    # 从 key 中提取 bot_username
                    # 格式: voice_pref:user_id:bot_username
                    parts = key.split(":", 2)  # 最多分割成3部分
                    if len(parts) == 3:
                        # 支持 bot_username 中包含冒号的情况
                        bot_username = parts[2]
                        value = self._redis.get(key)
                        preferences[bot_username] = value == "1"
            except Exception as e:
                logger.error(f"Redis scan error: {e}")
        
        return preferences
    
    def delete_preference(self, user_id: int, bot_username: str) -> bool:
        """
        删除用户的语音偏好设置
        
        Args:
            user_id: 用户 Telegram ID
            bot_username: Bot 用户名
            
        Returns:
            bool: 是否删除成功
        """
        key = self._get_key(user_id, bot_username)
        
        if self._redis:
            try:
                result = self._redis.delete(key)
                logger.info(f"Voice preference deleted: user={user_id}, bot={bot_username}")
                return result > 0
            except Exception as e:
                logger.error(f"Redis delete error: {e}")
                return False
        else:
            if key in self._fallback_preferences:
                del self._fallback_preferences[key]
                return True
            return False
    
    def health_check(self) -> dict:
        """
        健康检查
        
        Returns:
            dict: 包含 Redis 连接状态的信息
        """
        status = {
            "redis_available": False,
            "mode": "fallback",
            "fallback_count": len(self._fallback_preferences)
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
voice_preference_service = VoicePreferenceService()