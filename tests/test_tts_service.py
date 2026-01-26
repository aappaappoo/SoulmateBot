"""
Tests for TTS (Text-to-Speech) service
语音服务测试

支持 OpenAI TTS 和 科大讯飞 (iFlytek) TTS
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import io

from src.services.tts_service import TTSService, tts_service
from src.services.iflytek_tts_service import IflytekTTSService


class TestTTSService:
    """TTS服务测试类"""
    
    def test_available_voices_iflytek(self):
        """测试讯飞可用音色列表"""
        voices = IflytekTTSService.AVAILABLE_VOICES
        
        # 检查常用的讯飞音色
        assert "xiaoyan" in voices
        assert "xiaoyu" in voices
        assert "vixq" in voices
        assert "aisjinger" in voices
        assert "vixf" in voices
    
    def test_openai_to_iflytek_mapping(self):
        """测试OpenAI音色到讯飞音色的映射"""
        mapping = IflytekTTSService.OPENAI_TO_IFLYTEK_MAP
        
        assert mapping["alloy"] == "xiaoyan"
        assert mapping["nova"] == "vixq"
        assert mapping["shimmer"] == "aisjinger"
        assert mapping["onyx"] == "aisjiuxu"
    
    def test_is_voice_id_valid_iflytek(self):
        """测试讯飞音色ID验证"""
        # 有效的讯飞音色ID
        assert IflytekTTSService.is_voice_id_valid("xiaoyan") is True
        assert IflytekTTSService.is_voice_id_valid("xiaoyu") is True
        assert IflytekTTSService.is_voice_id_valid("vixq") is True
        
        # OpenAI音色ID也应该有效（会被映射）
        assert IflytekTTSService.is_voice_id_valid("nova") is True
        assert IflytekTTSService.is_voice_id_valid("shimmer") is True
        
        # 无效的音色ID
        assert IflytekTTSService.is_voice_id_valid("invalid") is False
        assert IflytekTTSService.is_voice_id_valid("") is False
    
    def test_get_voice_for_gender(self):
        """测试根据性别推荐音色"""
        # 男性角色
        assert IflytekTTSService.get_voice_for_gender("male", "lively") == "xiaoyu"
        assert IflytekTTSService.get_voice_for_gender("male", "mature") == "vixf"
        assert IflytekTTSService.get_voice_for_gender("male", "warm") == "aisjiuxu"
        
        # 女性角色
        assert IflytekTTSService.get_voice_for_gender("female", "gentle") == "aisjinger"
        assert IflytekTTSService.get_voice_for_gender("female", "lively") == "vixq"
        assert IflytekTTSService.get_voice_for_gender("female", "intellectual") == "vixy"
    
    def test_get_voice_as_buffer(self):
        """测试音频数据转缓冲区"""
        with patch('src.services.tts_service.settings') as mock_settings:
            mock_settings.tts_provider = "iflytek"
            mock_settings.default_iflytek_voice_id = "xiaoyan"
            mock_settings.openai_tts_model = "tts-1"
            mock_settings.default_voice_id = "alloy"
            
            service = TTSService()
            
            # 模拟音频数据
            audio_data = b"fake audio data"
            
            buffer = service.get_voice_as_buffer(audio_data)
            
            assert isinstance(buffer, io.BytesIO)
            # 讯飞使用PCM格式
            assert "pcm" in buffer.name or "opus" in buffer.name
            assert buffer.read() == audio_data
    
    @pytest.mark.asyncio
    async def test_generate_voice_no_credentials(self):
        """测试没有TTS凭证时的行为"""
        with patch('src.services.iflytek_tts_service.settings') as mock_settings:
            mock_settings.iflytek_app_id = None
            mock_settings.iflytek_api_key = None
            mock_settings.iflytek_api_secret = None
            mock_settings.default_iflytek_voice_id = "xiaoyan"
            
            service = IflytekTTSService()
            
            result = await service.generate_voice("Hello world")
            
            # 没有凭证应该返回None
            assert result is None


class TestVoiceReplyIntegration:
    """语音回复集成测试"""
    
    @pytest.mark.asyncio
    async def test_send_voice_or_text_reply_voice_disabled(self):
        """测试Bot禁用语音且用户未开启语音时发送文本"""
        from src.utils.voice_helper import send_voice_or_text_reply
        
        # 模拟Bot对象
        mock_bot = MagicMock()
        mock_bot.voice_enabled = False
        mock_bot.voice_id = None
        mock_bot.bot_username = "test_bot"
        
        # 模拟消息对象
        mock_message = AsyncMock()
        
        # 模拟用户语音偏好服务（用户未开启语音）
        with patch('src.utils.voice_helper.voice_preference_service') as mock_pref:
            mock_pref.is_voice_enabled = MagicMock(return_value=False)
            
            result = await send_voice_or_text_reply(
                message=mock_message,
                response="Hello!",
                bot=mock_bot,
                user_id=12345
            )
            
            # 应该发送文本
            assert result == "text"
            mock_message.reply_text.assert_called_once_with("Hello!")
            mock_message.reply_voice.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_send_voice_or_text_reply_voice_enabled(self):
        """测试Bot启用语音时发送语音"""
        from src.utils.voice_helper import send_voice_or_text_reply
        
        # 模拟Bot对象
        mock_bot = MagicMock()
        mock_bot.voice_enabled = True
        mock_bot.voice_id = "xiaoyu"  # 使用讯飞音色
        mock_bot.bot_username = "test_bot"
        
        # 模拟消息对象
        mock_message = AsyncMock()
        
        # 模拟TTS服务和用户语音偏好
        with patch('src.utils.voice_helper.tts_service') as mock_tts, \
             patch('src.utils.voice_helper.voice_preference_service') as mock_pref:
            mock_tts.generate_voice = AsyncMock(return_value=b"fake audio")
            mock_tts.get_voice_as_buffer = MagicMock(return_value=io.BytesIO(b"fake audio"))
            mock_pref.is_voice_enabled = MagicMock(return_value=False)
            
            result = await send_voice_or_text_reply(
                message=mock_message,
                response="Hello!",
                bot=mock_bot,
                user_id=12345
            )
            
            # 应该发送语音
            assert result == "voice"
            mock_message.reply_voice.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_voice_or_text_reply_user_voice_enabled(self):
        """测试用户通过/voice命令开启语音时发送语音"""
        from src.utils.voice_helper import send_voice_or_text_reply
        
        # 模拟Bot对象（Bot没有启用语音，但用户开启了）
        mock_bot = MagicMock()
        mock_bot.voice_enabled = False
        mock_bot.voice_id = "xiaoyan"
        mock_bot.bot_username = "test_bot"
        
        # 模拟消息对象
        mock_message = AsyncMock()
        
        # 模拟TTS服务和用户语音偏好（用户开启了语音）
        with patch('src.utils.voice_helper.tts_service') as mock_tts, \
             patch('src.utils.voice_helper.voice_preference_service') as mock_pref:
            mock_tts.generate_voice = AsyncMock(return_value=b"fake audio")
            mock_tts.get_voice_as_buffer = MagicMock(return_value=io.BytesIO(b"fake audio"))
            mock_pref.is_voice_enabled = MagicMock(return_value=True)  # 用户开启了语音
            
            result = await send_voice_or_text_reply(
                message=mock_message,
                response="Hello!",
                bot=mock_bot,
                user_id=12345
            )
            
            # 应该发送语音（因为用户开启了语音）
            assert result == "voice"
            mock_message.reply_voice.assert_called_once()
            # 验证查询了用户语音偏好
            mock_pref.is_voice_enabled.assert_called_once_with(12345, "test_bot")
    
    @pytest.mark.asyncio
    async def test_send_voice_or_text_reply_fallback_on_error(self):
        """测试语音生成失败时回退到文本"""
        from src.utils.voice_helper import send_voice_or_text_reply
        
        # 模拟Bot对象
        mock_bot = MagicMock()
        mock_bot.voice_enabled = True
        mock_bot.voice_id = "xiaoyan"  # 使用讯飞音色
        mock_bot.bot_username = "test_bot"
        
        # 模拟消息对象
        mock_message = AsyncMock()
        
        # 模拟TTS服务返回None（生成失败）和用户语音偏好
        with patch('src.utils.voice_helper.tts_service') as mock_tts, \
             patch('src.utils.voice_helper.voice_preference_service') as mock_pref:
            mock_tts.generate_voice = AsyncMock(return_value=None)
            mock_pref.is_voice_enabled = MagicMock(return_value=False)
            
            result = await send_voice_or_text_reply(
                message=mock_message,
                response="Hello!",
                bot=mock_bot,
                user_id=12345
            )
            
            # 应该回退到文本
            assert result == "text"
            mock_message.reply_text.assert_called_once_with("Hello!")
