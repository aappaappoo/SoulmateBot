"""
Tests for voice handler commands
测试语音命令处理器
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import io

from src.handlers.voice_handler import voice_on_command, voice_off_command


class TestVoiceCommands:
    """语音命令测试类"""
    
    @pytest.mark.asyncio
    async def test_voice_on_command_sends_voice(self):
        """测试 /voice_on 命令发送语音确认"""
        # 模拟 Update 和 Context
        mock_update = MagicMock()
        mock_update.effective_user.id = 12345
        mock_update.message = AsyncMock()
        
        mock_context = MagicMock()
        mock_context.bot.username = "test_bot"
        
        # 模拟 TTS 服务
        with patch('src.handlers.voice_handler.tts_service') as mock_tts, \
             patch('src.handlers.voice_handler.voice_preference_service') as mock_pref:
            # 模拟成功生成语音
            mock_tts.generate_voice = AsyncMock(return_value=b"fake audio data")
            mock_tts.get_voice_as_buffer = MagicMock(return_value=io.BytesIO(b"fake audio data"))
            
            # 执行命令
            await voice_on_command(mock_update, mock_context)
            
            # 验证设置了语音偏好
            mock_pref.set_voice_enabled.assert_called_once_with(12345, "test_bot", True)
            
            # 验证生成了语音
            mock_tts.generate_voice.assert_called_once()
            call_args = mock_tts.generate_voice.call_args
            assert "语音回复已开启" in call_args.kwargs['text']
            assert call_args.kwargs['user_id'] == 12345
            
            # 验证发送了语音消息
            mock_update.message.reply_voice.assert_called_once()
            # 验证没有发送文本消息
            mock_update.message.reply_text.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_voice_on_command_fallback_to_text(self):
        """测试 /voice_on 命令在语音生成失败时回退到文本"""
        # 模拟 Update 和 Context
        mock_update = MagicMock()
        mock_update.effective_user.id = 12345
        mock_update.message = AsyncMock()
        
        mock_context = MagicMock()
        mock_context.bot.username = "test_bot"
        
        # 模拟 TTS 服务生成失败
        with patch('src.handlers.voice_handler.tts_service') as mock_tts, \
             patch('src.handlers.voice_handler.voice_preference_service') as mock_pref:
            # 模拟语音生成失败（返回 None）
            mock_tts.generate_voice = AsyncMock(return_value=None)
            
            # 执行命令
            await voice_on_command(mock_update, mock_context)
            
            # 验证设置了语音偏好
            mock_pref.set_voice_enabled.assert_called_once_with(12345, "test_bot", True)
            
            # 验证尝试生成了语音
            mock_tts.generate_voice.assert_called_once()
            
            # 验证回退到文本消息
            mock_update.message.reply_text.assert_called_once()
            assert "语音回复已开启" in mock_update.message.reply_text.call_args[0][0]
            # 验证没有发送语音消息
            mock_update.message.reply_voice.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_voice_on_command_exception_handling(self):
        """测试 /voice_on 命令的异常处理"""
        # 模拟 Update 和 Context
        mock_update = MagicMock()
        mock_update.effective_user.id = 12345
        mock_update.message = AsyncMock()
        
        mock_context = MagicMock()
        mock_context.bot.username = "test_bot"
        
        # 模拟 TTS 服务抛出异常
        with patch('src.handlers.voice_handler.tts_service') as mock_tts, \
             patch('src.handlers.voice_handler.voice_preference_service') as mock_pref:
            # 模拟语音生成抛出异常
            mock_tts.generate_voice = AsyncMock(side_effect=Exception("TTS error"))
            
            # 执行命令
            await voice_on_command(mock_update, mock_context)
            
            # 验证设置了语音偏好
            mock_pref.set_voice_enabled.assert_called_once_with(12345, "test_bot", True)
            
            # 验证回退到文本消息
            mock_update.message.reply_text.assert_called_once()
            assert "语音回复已开启" in mock_update.message.reply_text.call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_voice_off_command_sends_voice_then_disables(self):
        """测试 /voice_off 命令先发送语音然后关闭语音"""
        # 模拟 Update 和 Context
        mock_update = MagicMock()
        mock_update.effective_user.id = 12345
        mock_update.message = AsyncMock()
        
        mock_context = MagicMock()
        mock_context.bot.username = "test_bot"
        
        # 模拟 TTS 服务
        with patch('src.handlers.voice_handler.tts_service') as mock_tts, \
             patch('src.handlers.voice_handler.voice_preference_service') as mock_pref:
            # 模拟成功生成语音
            mock_tts.generate_voice = AsyncMock(return_value=b"fake audio data")
            mock_tts.get_voice_as_buffer = MagicMock(return_value=io.BytesIO(b"fake audio data"))
            
            # 执行命令
            await voice_off_command(mock_update, mock_context)
            
            # 验证生成了语音
            mock_tts.generate_voice.assert_called_once()
            call_args = mock_tts.generate_voice.call_args
            assert "语音回复已关闭" in call_args.kwargs['text']
            
            # 验证发送了语音消息
            mock_update.message.reply_voice.assert_called_once()
            
            # 验证最后关闭了语音偏好
            mock_pref.set_voice_enabled.assert_called_once_with(12345, "test_bot", False)
            
            # 验证没有发送文本消息
            mock_update.message.reply_text.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_voice_off_command_fallback_to_text(self):
        """测试 /voice_off 命令在语音生成失败时回退到文本"""
        # 模拟 Update 和 Context
        mock_update = MagicMock()
        mock_update.effective_user.id = 12345
        mock_update.message = AsyncMock()
        
        mock_context = MagicMock()
        mock_context.bot.username = "test_bot"
        
        # 模拟 TTS 服务生成失败
        with patch('src.handlers.voice_handler.tts_service') as mock_pref, \
             patch('src.handlers.voice_handler.voice_preference_service') as mock_pref_service:
            # 模拟语音生成失败（返回 None）
            mock_pref.generate_voice = AsyncMock(return_value=None)
            
            # 执行命令
            await voice_off_command(mock_update, mock_context)
            
            # 验证尝试生成了语音
            mock_pref.generate_voice.assert_called_once()
            
            # 验证回退到文本消息
            mock_update.message.reply_text.assert_called_once()
            assert "语音回复已关闭" in mock_update.message.reply_text.call_args[0][0]
            
            # 验证关闭了语音偏好
            mock_pref_service.set_voice_enabled.assert_called_once_with(12345, "test_bot", False)
            
            # 验证没有发送语音消息
            mock_update.message.reply_voice.assert_not_called()
