"""
Tests for voice handler commands
测试语音命令处理器
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.handlers.voice_handler import voice_on_command, voice_off_command


class TestVoiceCommands:
    """语音命令测试类"""
    
    @pytest.mark.asyncio
    async def test_voice_on_command_sends_text_confirmation(self):
        """测试 /voice_on 命令发送文本确认消息"""
        # 模拟 Update 和 Context
        mock_update = MagicMock()
        mock_update.effective_user.id = 12345
        mock_update.message = AsyncMock()
        
        mock_context = MagicMock()
        mock_context.bot.username = "test_bot"
        
        # 模拟语音偏好服务
        with patch('src.handlers.voice_handler.voice_preference_service') as mock_pref:
            # 执行命令
            await voice_on_command(mock_update, mock_context)
            
            # 验证设置了语音偏好为开启
            mock_pref.set_voice_enabled.assert_called_once_with(12345, "test_bot", True)
            
            # 验证发送了文本确认消息
            mock_update.message.reply_text.assert_called_once()
            confirmation_text = mock_update.message.reply_text.call_args[0][0]
            assert "语音回复功能已开启" in confirmation_text
            assert "后续的对话将使用语音进行回复" in confirmation_text
    
    @pytest.mark.asyncio
    async def test_voice_off_command_sends_text_confirmation(self):
        """测试 /voice_off 命令发送文本确认消息"""
        # 模拟 Update 和 Context
        mock_update = MagicMock()
        mock_update.effective_user.id = 12345
        mock_update.message = AsyncMock()
        
        mock_context = MagicMock()
        mock_context.bot.username = "test_bot"
        
        # 模拟语音偏好服务
        with patch('src.handlers.voice_handler.voice_preference_service') as mock_pref:
            # 执行命令
            await voice_off_command(mock_update, mock_context)
            
            # 验证设置了语音偏好为关闭
            mock_pref.set_voice_enabled.assert_called_once_with(12345, "test_bot", False)
            
            # 验证发送了文本确认消息
            mock_update.message.reply_text.assert_called_once()
            confirmation_text = mock_update.message.reply_text.call_args[0][0]
            assert "语音回复功能已关闭" in confirmation_text
            assert "后续的对话将使用文本进行回复" in confirmation_text
