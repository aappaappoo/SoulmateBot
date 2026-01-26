"""
用户语音偏好服务
管理用户是否开启语音回复的设置
"""
from typing import Dict, Optional
from loguru import logger
import json
from pathlib import Path


class VoicePreferenceService:
    """
    用户语音偏好管理

    存储每个用户对每个 Bot 的语音偏好设置
    """

    def __init__(self):
        self.data_dir = Path("data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.preferences_file = self.data_dir / "voice_preferences.json"
        self._preferences: Dict[str, bool] = {}
        self._load()

    def _load(self):
        """从文件加载偏好设置"""
        if self.preferences_file.exists():
            try:
                with open(self.preferences_file, 'r', encoding='utf-8') as f:
                    self._preferences = json.load(f)
                logger.info(f"Loaded {len(self._preferences)} voice preferences")
            except Exception as e:
                logger.error(f"Failed to load voice preferences: {e}")
                self._preferences = {}
        else:
            self._preferences = {}

    def _save(self):
        """保存偏好设置到文件"""
        try:
            with open(self.preferences_file, 'w', encoding='utf-8') as f:
                json.dump(self._preferences, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save voice preferences: {e}")

    def _get_key(self, user_id: int, bot_username: str) -> str:
        """生成存储键"""
        return f"{user_id}:{bot_username}"

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
        # 默认关闭语音
        return self._preferences.get(key, False)

    def set_voice_enabled(self, user_id: int, bot_username: str, enabled: bool):
        """
        设置用户的语音偏好

        Args:
            user_id: 用户 Telegram ID
            bot_username: Bot 用户名
            enabled: 是否开启
        """
        key = self._get_key(user_id, bot_username)
        self._preferences[key] = enabled
        self._save()
        logger.info(f"Voice preference set: user={user_id}, bot={bot_username}, enabled={enabled}")

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


# 全局实例
voice_preference_service = VoicePreferenceService()