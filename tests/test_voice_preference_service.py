"""
Tests for VoicePreferenceService
测试用户语音偏好服务
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import only what we need, bypassing the services __init__.py
import importlib.util
spec = importlib.util.spec_from_file_location(
    "voice_preference_service", 
    project_root / "src" / "services" / "voice_preference_service.py"
)
voice_pref_module = importlib.util.module_from_spec(spec)
sys.modules["voice_preference_service"] = voice_pref_module
spec.loader.exec_module(voice_pref_module)

VoicePreferenceService = voice_pref_module.VoicePreferenceService


class TestVoicePreferenceService:
    """VoicePreferenceService 测试类"""
    
    def test_init_without_redis(self):
        """测试没有Redis配置时使用fallback模式"""
        with patch('voice_preference_service.settings') as mock_settings:
            mock_settings.redis_url = None
            service = VoicePreferenceService()
            
            assert service._redis is None
            assert service._fallback_preferences == {}
    
    def test_init_with_redis_success(self):
        """测试Redis连接成功"""
        with patch('voice_preference_service.settings') as mock_settings, \
             patch('voice_preference_service.redis.from_url') as mock_from_url:
            
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_redis = MagicMock()
            mock_redis.ping.return_value = True
            mock_from_url.return_value = mock_redis
            
            service = VoicePreferenceService()
            
            assert service._redis is not None
            mock_from_url.assert_called_once()
            mock_redis.ping.assert_called_once()
    
    def test_init_with_redis_failure(self):
        """测试Redis连接失败时降级到fallback"""
        with patch('voice_preference_service.settings') as mock_settings, \
             patch('voice_preference_service.redis.from_url') as mock_from_url:
            
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_from_url.side_effect = Exception("Connection failed")
            
            service = VoicePreferenceService()
            
            assert service._redis is None
            assert service._fallback_preferences == {}
    
    def test_get_key_format(self):
        """测试生成的key格式"""
        with patch('voice_preference_service.settings') as mock_settings:
            mock_settings.redis_url = None
            service = VoicePreferenceService()
            
            key = service._get_key(123456, "TestBot")
            assert key == "voice_pref:123456:TestBot"
    
    def test_is_voice_enabled_default_false(self):
        """测试默认情况下语音未开启"""
        with patch('voice_preference_service.settings') as mock_settings:
            mock_settings.redis_url = None
            service = VoicePreferenceService()
            
            result = service.is_voice_enabled(123456, "TestBot")
            assert result is False
    
    def test_set_and_get_voice_enabled_fallback(self):
        """测试fallback模式下设置和获取语音偏好"""
        with patch('voice_preference_service.settings') as mock_settings:
            mock_settings.redis_url = None
            service = VoicePreferenceService()
            
            # 设置为开启
            service.set_voice_enabled(123456, "TestBot", True)
            assert service.is_voice_enabled(123456, "TestBot") is True
            
            # 设置为关闭
            service.set_voice_enabled(123456, "TestBot", False)
            assert service.is_voice_enabled(123456, "TestBot") is False
    
    def test_set_and_get_voice_enabled_redis(self):
        """测试Redis模式下设置和获取语音偏好"""
        with patch('voice_preference_service.settings') as mock_settings, \
             patch('voice_preference_service.redis.from_url') as mock_from_url:
            
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_redis = MagicMock()
            mock_redis.ping.return_value = True
            mock_from_url.return_value = mock_redis
            
            service = VoicePreferenceService()
            
            # 测试设置为开启
            mock_redis.get.return_value = None
            service.set_voice_enabled(123456, "TestBot", True)
            mock_redis.set.assert_called_with("voice_pref:123456:TestBot", "1")
            
            # 测试获取开启状态
            mock_redis.get.return_value = "1"
            result = service.is_voice_enabled(123456, "TestBot")
            assert result is True
            
            # 测试设置为关闭
            service.set_voice_enabled(123456, "TestBot", False)
            mock_redis.set.assert_called_with("voice_pref:123456:TestBot", "0")
            
            # 测试获取关闭状态
            mock_redis.get.return_value = "0"
            result = service.is_voice_enabled(123456, "TestBot")
            assert result is False
    
    def test_toggle_voice_fallback(self):
        """测试fallback模式下切换语音状态"""
        with patch('voice_preference_service.settings') as mock_settings:
            mock_settings.redis_url = None
            service = VoicePreferenceService()
            
            # 初始状态为False，切换为True
            new_state = service.toggle_voice(123456, "TestBot")
            assert new_state is True
            assert service.is_voice_enabled(123456, "TestBot") is True
            
            # 再次切换为False
            new_state = service.toggle_voice(123456, "TestBot")
            assert new_state is False
            assert service.is_voice_enabled(123456, "TestBot") is False
    
    def test_toggle_voice_redis(self):
        """测试Redis模式下切换语音状态"""
        with patch('voice_preference_service.settings') as mock_settings, \
             patch('voice_preference_service.redis.from_url') as mock_from_url:
            
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_redis = MagicMock()
            mock_redis.ping.return_value = True
            mock_from_url.return_value = mock_redis
            
            service = VoicePreferenceService()
            
            # 初始状态为False（Redis返回None）
            mock_redis.get.return_value = None
            new_state = service.toggle_voice(123456, "TestBot")
            assert new_state is True
            
            # 状态切换为True后，再次切换为False
            mock_redis.get.return_value = "1"
            new_state = service.toggle_voice(123456, "TestBot")
            assert new_state is False
    
    def test_redis_error_fallback_to_memory(self):
        """测试Redis操作出错时降级到内存存储"""
        with patch('voice_preference_service.settings') as mock_settings, \
             patch('voice_preference_service.redis.from_url') as mock_from_url:
            
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_redis = MagicMock()
            mock_redis.ping.return_value = True
            mock_from_url.return_value = mock_redis
            
            service = VoicePreferenceService()
            
            # 模拟Redis set操作失败
            mock_redis.set.side_effect = Exception("Redis error")
            service.set_voice_enabled(123456, "TestBot", True)
            
            # 应该降级到fallback存储
            assert service._fallback_preferences["voice_pref:123456:TestBot"] is True
            
            # 模拟Redis get操作失败
            mock_redis.get.side_effect = Exception("Redis error")
            result = service.is_voice_enabled(123456, "TestBot")
            
            # 应该从fallback存储读取
            assert result is True
    
    def test_get_all_preferences_for_user_fallback(self):
        """测试fallback模式下获取用户所有偏好"""
        with patch('voice_preference_service.settings') as mock_settings:
            mock_settings.redis_url = None
            service = VoicePreferenceService()
            
            # 设置多个bot的偏好
            service.set_voice_enabled(123456, "Bot1", True)
            service.set_voice_enabled(123456, "Bot2", False)
            service.set_voice_enabled(789, "Bot1", True)  # 不同用户
            
            preferences = service.get_all_preferences_for_user(123456)
            
            # fallback模式下返回空字典（因为没有实现对fallback的扫描）
            assert preferences == {}
    
    def test_get_all_preferences_for_user_redis(self):
        """测试Redis模式下获取用户所有偏好"""
        with patch('voice_preference_service.settings') as mock_settings, \
             patch('voice_preference_service.redis.from_url') as mock_from_url:
            
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_redis = MagicMock()
            mock_redis.ping.return_value = True
            mock_from_url.return_value = mock_redis
            
            service = VoicePreferenceService()
            
            # 模拟Redis keys返回
            mock_redis.keys.return_value = [
                "voice_pref:123456:Bot1",
                "voice_pref:123456:Bot2"
            ]
            
            # 模拟Redis get返回
            def get_side_effect(key):
                if key == "voice_pref:123456:Bot1":
                    return "1"
                elif key == "voice_pref:123456:Bot2":
                    return "0"
                return None
            
            mock_redis.get.side_effect = get_side_effect
            
            preferences = service.get_all_preferences_for_user(123456)
            
            assert preferences == {"Bot1": True, "Bot2": False}
    
    def test_delete_preference_fallback(self):
        """测试fallback模式下删除偏好"""
        with patch('voice_preference_service.settings') as mock_settings:
            mock_settings.redis_url = None
            service = VoicePreferenceService()
            
            # 设置一个偏好
            service.set_voice_enabled(123456, "TestBot", True)
            
            # 删除偏好
            result = service.delete_preference(123456, "TestBot")
            assert result is True
            
            # 验证已删除
            assert service.is_voice_enabled(123456, "TestBot") is False
            
            # 删除不存在的偏好
            result = service.delete_preference(999, "NonExistent")
            assert result is False
    
    def test_delete_preference_redis(self):
        """测试Redis模式下删除偏好"""
        with patch('voice_preference_service.settings') as mock_settings, \
             patch('voice_preference_service.redis.from_url') as mock_from_url:
            
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_redis = MagicMock()
            mock_redis.ping.return_value = True
            mock_from_url.return_value = mock_redis
            
            service = VoicePreferenceService()
            
            # 模拟成功删除
            mock_redis.delete.return_value = 1
            result = service.delete_preference(123456, "TestBot")
            assert result is True
            mock_redis.delete.assert_called_with("voice_pref:123456:TestBot")
            
            # 模拟删除不存在的key
            mock_redis.delete.return_value = 0
            result = service.delete_preference(999, "NonExistent")
            assert result is False
    
    def test_health_check_fallback(self):
        """测试fallback模式下的健康检查"""
        with patch('voice_preference_service.settings') as mock_settings:
            mock_settings.redis_url = None
            service = VoicePreferenceService()
            
            # 添加一些fallback数据
            service.set_voice_enabled(123, "Bot1", True)
            service.set_voice_enabled(456, "Bot2", False)
            
            status = service.health_check()
            
            assert status["redis_available"] is False
            assert status["mode"] == "fallback"
            assert status["fallback_count"] == 2
    
    def test_health_check_redis_available(self):
        """测试Redis可用时的健康检查"""
        with patch('voice_preference_service.settings') as mock_settings, \
             patch('voice_preference_service.redis.from_url') as mock_from_url:
            
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_redis = MagicMock()
            mock_redis.ping.return_value = True
            mock_from_url.return_value = mock_redis
            
            service = VoicePreferenceService()
            
            status = service.health_check()
            
            assert status["redis_available"] is True
            assert status["mode"] == "redis"
            assert "error" not in status
    
    def test_health_check_redis_unavailable(self):
        """测试Redis不可用时的健康检查"""
        with patch('voice_preference_service.settings') as mock_settings, \
             patch('voice_preference_service.redis.from_url') as mock_from_url:
            
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_redis = MagicMock()
            mock_redis.ping.side_effect = [True, Exception("Connection lost")]
            mock_from_url.return_value = mock_redis
            
            service = VoicePreferenceService()
            
            # 第一次ping成功（初始化时）
            # 第二次ping失败（健康检查时）
            status = service.health_check()
            
            assert status["redis_available"] is False
            assert status["mode"] == "fallback"
            assert "error" in status
    
    def test_multiple_users_and_bots(self):
        """测试多用户多bot场景"""
        with patch('voice_preference_service.settings') as mock_settings:
            mock_settings.redis_url = None
            service = VoicePreferenceService()
            
            # 设置不同用户对不同bot的偏好
            service.set_voice_enabled(111, "BotA", True)
            service.set_voice_enabled(111, "BotB", False)
            service.set_voice_enabled(222, "BotA", False)
            service.set_voice_enabled(222, "BotB", True)
            
            # 验证各自的设置
            assert service.is_voice_enabled(111, "BotA") is True
            assert service.is_voice_enabled(111, "BotB") is False
            assert service.is_voice_enabled(222, "BotA") is False
            assert service.is_voice_enabled(222, "BotB") is True
    
    def test_set_voice_enabled_with_ttl(self):
        """测试设置TTL的情况"""
        with patch('voice_preference_service.settings') as mock_settings, \
             patch('voice_preference_service.redis.from_url') as mock_from_url:
            
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_redis = MagicMock()
            mock_redis.ping.return_value = True
            mock_from_url.return_value = mock_redis
            
            service = VoicePreferenceService()
            
            # 临时修改TTL
            original_ttl = service.DEFAULT_TTL
            service.DEFAULT_TTL = 3600  # 1小时
            
            service.set_voice_enabled(123456, "TestBot", True)
            
            # 应该调用setex而不是set
            mock_redis.setex.assert_called_with("voice_pref:123456:TestBot", 3600, "1")
            
            # 恢复原值
            service.DEFAULT_TTL = original_ttl
