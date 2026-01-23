"""
Tests for TTS (Text-to-Speech) service
语音服务测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import io

from src.services.tts_service import TTSService, tts_service


class TestTTSService:
    """TTS服务测试类"""
    
    def test_available_voices(self):
        """测试可用音色列表"""
        voices = TTSService.get_available_voices()
        
        assert len(voices) == 6
        assert "alloy" in voices
        assert "echo" in voices
        assert "fable" in voices
        assert "onyx" in voices
        assert "nova" in voices
        assert "shimmer" in voices
    
    def test_is_voice_id_valid(self):
        """测试音色ID验证"""
        # 有效的音色ID
        assert TTSService.is_voice_id_valid("alloy") is True
        assert TTSService.is_voice_id_valid("nova") is True
        assert TTSService.is_voice_id_valid("shimmer") is True
        
        # 无效的音色ID
        assert TTSService.is_voice_id_valid("invalid") is False
        assert TTSService.is_voice_id_valid("") is False
        assert TTSService.is_voice_id_valid("ALLOY") is False  # 区分大小写
    
    def test_get_voice_as_buffer(self):
        """测试音频数据转缓冲区"""
        service = TTSService()
        
        # 模拟音频数据
        audio_data = b"fake audio data"
        
        buffer = service.get_voice_as_buffer(audio_data)
        
        assert isinstance(buffer, io.BytesIO)
        assert buffer.name == "voice.opus"
        assert buffer.read() == audio_data
    
    def test_default_voice(self):
        """测试默认音色设置"""
        service = TTSService()
        
        # 默认值应该是从settings读取的
        assert service.default_voice is not None
        assert TTSService.is_voice_id_valid(service.default_voice)
    
    @pytest.mark.asyncio
    async def test_generate_voice_no_api_key(self):
        """测试没有API密钥时的行为"""
        service = TTSService()
        
        # 模拟没有API密钥的情况
        with patch('src.services.tts_service.settings') as mock_settings:
            mock_settings.openai_api_key = None
            mock_settings.default_voice_id = "alloy"
            mock_settings.openai_tts_model = "tts-1"
            
            # 重新创建service以获取模拟的settings
            test_service = TTSService()
            
            result = await test_service.generate_voice("Hello world")
            
            # 没有API密钥应该返回None
            assert result is None
    
    @pytest.mark.asyncio
    async def test_generate_voice_with_mock(self):
        """测试语音生成（模拟API调用）"""
        service = TTSService()
        
        # 模拟OpenAI响应
        mock_response = MagicMock()
        mock_response.content = b"fake audio content"
        
        with patch('src.services.tts_service.settings') as mock_settings:
            mock_settings.openai_api_key = "fake-key"
            mock_settings.default_voice_id = "alloy"
            mock_settings.openai_tts_model = "tts-1"
            
            with patch('openai.AsyncOpenAI') as mock_openai:
                mock_client = AsyncMock()
                mock_client.audio.speech.create = AsyncMock(return_value=mock_response)
                mock_openai.return_value = mock_client
                
                result = await service.generate_voice("Hello world", voice_id="nova")
                
                # 验证返回了音频数据
                assert result == b"fake audio content"
    
    @pytest.mark.asyncio
    async def test_generate_voice_invalid_voice_id(self):
        """测试使用无效音色ID时自动使用默认音色"""
        service = TTSService()
        
        # 模拟OpenAI响应
        mock_response = MagicMock()
        mock_response.content = b"fake audio content"
        
        with patch('src.services.tts_service.settings') as mock_settings:
            mock_settings.openai_api_key = "fake-key"
            mock_settings.default_voice_id = "alloy"
            mock_settings.openai_tts_model = "tts-1"
            
            with patch('openai.AsyncOpenAI') as mock_openai:
                mock_client = AsyncMock()
                mock_audio_create = AsyncMock(return_value=mock_response)
                mock_client.audio.speech.create = mock_audio_create
                mock_openai.return_value = mock_client
                
                # 使用无效的voice_id
                result = await service.generate_voice("Hello world", voice_id="invalid_voice")
                
                # 应该仍然成功返回音频
                assert result == b"fake audio content"


class TestVoiceReplyIntegration:
    """语音回复集成测试"""
    
    @pytest.mark.asyncio
    async def test_send_voice_or_text_reply_voice_disabled(self):
        """测试Bot禁用语音时发送文本"""
        from src.utils.voice_helper import send_voice_or_text_reply
        
        # 模拟Bot对象
        mock_bot = MagicMock()
        mock_bot.voice_enabled = False
        mock_bot.voice_id = None
        mock_bot.bot_username = "test_bot"
        
        # 模拟消息对象
        mock_message = AsyncMock()
        
        result = await send_voice_or_text_reply(
            message=mock_message,
            response="Hello!",
            bot=mock_bot
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
        mock_bot.voice_id = "nova"
        mock_bot.bot_username = "test_bot"
        
        # 模拟消息对象
        mock_message = AsyncMock()
        
        # 模拟TTS服务
        with patch('src.utils.voice_helper.tts_service') as mock_tts:
            mock_tts.generate_voice = AsyncMock(return_value=b"fake audio")
            mock_tts.get_voice_as_buffer = MagicMock(return_value=io.BytesIO(b"fake audio"))
            
            result = await send_voice_or_text_reply(
                message=mock_message,
                response="Hello!",
                bot=mock_bot
            )
            
            # 应该发送语音
            assert result == "voice"
            mock_message.reply_voice.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_voice_or_text_reply_fallback_on_error(self):
        """测试语音生成失败时回退到文本"""
        from src.utils.voice_helper import send_voice_or_text_reply
        
        # 模拟Bot对象
        mock_bot = MagicMock()
        mock_bot.voice_enabled = True
        mock_bot.voice_id = "nova"
        mock_bot.bot_username = "test_bot"
        
        # 模拟消息对象
        mock_message = AsyncMock()
        
        # 模拟TTS服务返回None（生成失败）
        with patch('src.utils.voice_helper.tts_service') as mock_tts:
            mock_tts.generate_voice = AsyncMock(return_value=None)
            
            result = await send_voice_or_text_reply(
                message=mock_message,
                response="Hello!",
                bot=mock_bot
            )
            
            # 应该回退到文本
            assert result == "text"
            mock_message.reply_text.assert_called_once_with("Hello!")
