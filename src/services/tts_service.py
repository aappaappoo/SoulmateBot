"""
Text-to-Speech (TTS) service for voice response generation
文本转语音服务 - 用于生成语音回复
"""
import os
import io
from typing import Optional
from datetime import datetime
from pathlib import Path
from loguru import logger

from config import settings


class TTSService:
    """
    Text-to-Speech 服务
    
    使用 OpenAI TTS API 将文本转换为语音
    支持多种音色选择，每个Bot可以有自己独特的声音
    
    可用音色 (voice_id):
    - alloy: 中性，平衡的声音
    - echo: 柔和，有质感的声音
    - fable: 英式口音，叙事风格
    - onyx: 深沉，有力的声音
    - nova: 年轻，活泼的声音
    - shimmer: 温暖，表达力强的声音
    """
    
    # 可用的语音音色列表
    AVAILABLE_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    
    def __init__(self):
        self.voice_dir = Path("data/voice")
        self.voice_dir.mkdir(parents=True, exist_ok=True)
        self.default_voice = settings.default_voice_id
        self.model = settings.openai_tts_model
    
    async def generate_voice(
        self,
        text: str,
        voice_id: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Optional[bytes]:
        """
        将文本转换为语音
        
        Args:
            text: 要转换的文本内容
            voice_id: 语音音色ID，默认使用配置中的音色
            user_id: 用户ID（用于日志记录）
            
        Returns:
            语音数据的字节流，如果失败返回None
        """
        if not settings.openai_api_key:
            logger.error("OpenAI API key not configured, cannot generate voice")
            return None
        
        # 验证音色是否有效
        voice = voice_id if voice_id in self.AVAILABLE_VOICES else self.default_voice
        
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            
            logger.info(f"Generating voice with voice_id={voice}, text_length={len(text)}")
            
            # 调用 OpenAI TTS API
            response = await client.audio.speech.create(
                model=self.model,
                voice=voice,
                input=text,
                response_format="opus"  # Telegram推荐的格式
            )
            
            # 获取音频数据
            audio_data = response.content
            
            logger.info(f"Voice generated successfully, size={len(audio_data)} bytes")
            return audio_data
            
        except Exception as e:
            logger.error(f"TTS generation error: {str(e)}", exc_info=True)
            return None
    
    async def generate_voice_file(
        self,
        text: str,
        voice_id: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Optional[str]:
        """
        将文本转换为语音并保存到文件
        
        Args:
            text: 要转换的文本内容
            voice_id: 语音音色ID
            user_id: 用户ID
            
        Returns:
            语音文件路径，如果失败返回None
        """
        audio_data = await self.generate_voice(text, voice_id, user_id)
        
        if audio_data is None:
            return None
        
        # 生成文件名并保存
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        user_suffix = f"_user_{user_id}" if user_id else ""
        filename = f"voice_{timestamp}{user_suffix}.opus"
        filepath = self.voice_dir / filename
        
        try:
            with open(filepath, 'wb') as f:
                f.write(audio_data)
            
            logger.info(f"Voice file saved: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to save voice file: {str(e)}")
            return None
    
    def get_voice_as_buffer(self, audio_data: bytes) -> io.BytesIO:
        """
        将音频数据转换为可用于Telegram API的字节流缓冲区
        
        Args:
            audio_data: 音频数据字节
            
        Returns:
            BytesIO 缓冲区对象
        """
        buffer = io.BytesIO(audio_data)
        buffer.name = "voice.opus"  # Telegram需要文件名
        buffer.seek(0)
        return buffer
    
    @staticmethod
    def is_voice_id_valid(voice_id: str) -> bool:
        """
        检查音色ID是否有效
        
        Args:
            voice_id: 要检查的音色ID
            
        Returns:
            True 如果有效，否则 False
        """
        return voice_id in TTSService.AVAILABLE_VOICES
    
    @staticmethod
    def get_available_voices() -> list:
        """
        获取所有可用的音色列表
        
        Returns:
            可用音色ID列表
        """
        return TTSService.AVAILABLE_VOICES.copy()


# 全局 TTS 服务实例
tts_service = TTSService()
