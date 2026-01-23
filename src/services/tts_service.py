"""
Text-to-Speech (TTS) service for voice response generation
文本转语音服务 - 用于生成语音回复

支持多个TTS服务提供商：
- OpenAI TTS
- 科大讯飞 (iFlytek) TTS
"""
import io
from typing import Optional
from datetime import datetime
from pathlib import Path
from loguru import logger
import openai

from config import settings


class TTSService:
    """
    Text-to-Speech 统一服务
    
    根据配置选择使用 OpenAI TTS 或 科大讯飞 TTS
    支持多种音色选择，每个Bot可以有自己独特的声音
    
    OpenAI 可用音色 (voice_id):
    - alloy: 中性，平衡的声音
    - echo: 柔和，有质感的声音
    - fable: 英式口音，叙事风格
    - onyx: 深沉，有力的声音
    - nova: 年轻，活泼的声音
    - shimmer: 温暖，表达力强的声音
    
    科大讯飞可用音色 (voice_id):
    - xiaoyan: 小燕，青年女声（温柔亲切）
    - xiaoyu: 小宇，青年男声（阳光开朗）
    - vixy: 小研，青年女声（知性大方）
    - vixq: 小琪，青年女声（活泼可爱）
    - vixf: 小峰，青年男声（成熟稳重）
    - aisjinger: 小婧，青年女声（温婉动人）
    - aisjiuxu: 许久，青年男声（温暖磁性）
    """
    
    # OpenAI可用的语音音色列表
    OPENAI_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    
    # 科大讯飞可用音色列表
    IFLYTEK_VOICES = ["xiaoyan", "xiaoyu", "vixy", "vixq", "vixf", "vinn", "vixx", 
                      "aisjiuxu", "aisxping", "aisjinger"]
    
    # 所有可用音色（合并两个提供商）
    AVAILABLE_VOICES = OPENAI_VOICES + IFLYTEK_VOICES
    
    def __init__(self):
        self.voice_dir = Path("data/voice")
        self.voice_dir.mkdir(parents=True, exist_ok=True)
        
        # 确定TTS提供商（默认使用讯飞）
        self.provider = settings.tts_provider.lower() if hasattr(settings, 'tts_provider') else "iflytek"
        
        if self.provider == "iflytek":
            self.default_voice = settings.default_iflytek_voice_id if hasattr(settings, 'default_iflytek_voice_id') else "xiaoyan"
            # 延迟导入讯飞TTS服务
            from .iflytek_tts_service import iflytek_tts_service
            self._iflytek_service = iflytek_tts_service
        else:
            self.default_voice = settings.default_voice_id
            self._iflytek_service = None
        
        self.model = settings.openai_tts_model
        
        logger.info(f"TTS Service initialized with provider: {self.provider}, default_voice: {self.default_voice}")
    
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
        if self.provider == "iflytek":
            return await self._generate_voice_iflytek(text, voice_id, user_id)
        else:
            return await self._generate_voice_openai(text, voice_id, user_id)
    
    async def _generate_voice_openai(
        self,
        text: str,
        voice_id: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Optional[bytes]:
        """
        使用 OpenAI TTS 生成语音
        """
        if not settings.openai_api_key or not settings.openai_api_key.strip():
            logger.error("OpenAI API key not configured, cannot generate voice")
            return None
        
        # 验证音色是否有效
        voice = voice_id if voice_id in self.OPENAI_VOICES else self.default_voice
        
        try:
            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            
            logger.info(f"Generating voice with OpenAI TTS, voice_id={voice}, text_length={len(text)}")
            
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
            logger.error(f"OpenAI TTS generation error: {str(e)}", exc_info=True)
            return None
    
    async def _generate_voice_iflytek(
        self,
        text: str,
        voice_id: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Optional[bytes]:
        """
        使用科大讯飞 TTS 生成语音
        """
        if self._iflytek_service is None:
            from .iflytek_tts_service import iflytek_tts_service
            self._iflytek_service = iflytek_tts_service
        
        return await self._iflytek_service.generate_voice(text, voice_id, user_id)
    
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
        ext = "opus" if self.provider == "openai" else "pcm"
        filename = f"voice_{timestamp}{user_suffix}.{ext}"
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
        ext = "opus" if self.provider == "openai" else "pcm"
        buffer.name = f"voice.{ext}"  # Telegram需要文件名
        buffer.seek(0)
        return buffer
    
    def is_voice_id_valid(self, voice_id: str) -> bool:
        """
        检查音色ID是否有效
        
        Args:
            voice_id: 要检查的音色ID
            
        Returns:
            True 如果有效，否则 False
        """
        if not voice_id:
            return False
        
        if self.provider == "iflytek":
            if self._iflytek_service is None:
                from .iflytek_tts_service import IflytekTTSService
                return IflytekTTSService.is_voice_id_valid(voice_id)
            return self._iflytek_service.is_voice_id_valid(voice_id)
        else:
            return voice_id in self.OPENAI_VOICES
    
    def get_available_voices(self) -> list:
        """
        获取当前提供商可用的音色列表
        
        Returns:
            可用音色ID列表
        """
        if self.provider == "iflytek":
            return self.IFLYTEK_VOICES.copy()
        else:
            return self.OPENAI_VOICES.copy()


# 全局 TTS 服务实例
tts_service = TTSService()
