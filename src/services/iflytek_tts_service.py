"""
iFlytek Text-to-Speech (TTS) service for voice response generation
科大讯飞文本转语音服务 - 用于生成语音回复
"""
import io
import base64
import hashlib
import hmac
import json
import ssl
import websocket
import asyncio
from typing import Optional
from datetime import datetime
from time import mktime
from wsgiref.handlers import format_date_time
from urllib.parse import urlencode, urlparse
from pathlib import Path
from loguru import logger

from config import settings


class IflytekTTSService:
    """
    科大讯飞 Text-to-Speech 服务
    
    使用科大讯飞 WebSocket API 将文本转换为语音
    支持多种音色选择，每个Bot可以有自己独特的声音
    
    可用音色 (voice_id/vcn):
    - xiaoyan: 小燕，青年女声（普通话）- 温柔亲切
    - xiaoyu: 小宇，青年男声（普通话）- 阳光开朗
    - vixy: 小研，青年女声（普通话）- 知性大方
    - vixq: 小琪，青年女声（普通话）- 活泼可爱
    - vixf: 小峰，青年男声（普通话）- 成熟稳重
    - vinn: 楠楠，童年女声（普通话）- 可爱甜美
    - vixx: 小新，童年男声（普通话）- 活泼调皮
    - aisjiuxu: 许久，青年男声 - 温暖磁性
    - aisxping: 小萍，青年女声 - 甜美清新
    - aisjinger: 小婧，青年女声 - 温婉动人
    """
    
    # 可用的语音音色列表 - 科大讯飞常用发音人
    AVAILABLE_VOICES = {
        # 普通话女声
        "xiaoyan": {"name": "小燕", "gender": "female", "desc": "青年女声，温柔亲切"},
        "vixy": {"name": "小研", "gender": "female", "desc": "青年女声，知性大方"},
        "vixq": {"name": "小琪", "gender": "female", "desc": "青年女声，活泼可爱"},
        "aisxping": {"name": "小萍", "gender": "female", "desc": "青年女声，甜美清新"},
        "aisjinger": {"name": "小婧", "gender": "female", "desc": "青年女声，温婉动人"},
        "vinn": {"name": "楠楠", "gender": "female", "desc": "童年女声，可爱甜美"},
        
        # 普通话男声
        "xiaoyu": {"name": "小宇", "gender": "male", "desc": "青年男声，阳光开朗"},
        "vixf": {"name": "小峰", "gender": "male", "desc": "青年男声，成熟稳重"},
        "aisjiuxu": {"name": "许久", "gender": "male", "desc": "青年男声，温暖磁性"},
        "vixx": {"name": "小新", "gender": "male", "desc": "童年男声，活泼调皮"},
    }
    
    # OpenAI音色到讯飞音色的映射表
    OPENAI_TO_IFLYTEK_MAP = {
        "alloy": "xiaoyan",      # 中性平衡 -> 小燕（温柔亲切）
        "echo": "vixy",          # 柔和有质感 -> 小研（知性大方）
        "fable": "vixf",         # 叙事风格 -> 小峰（成熟稳重）
        "onyx": "aisjiuxu",      # 深沉有力 -> 许久（温暖磁性）
        "nova": "vixq",          # 年轻活泼 -> 小琪（活泼可爱）
        "shimmer": "aisjinger",  # 温暖表达力强 -> 小婧（温婉动人）
    }
    
    # API配置
    TTS_API_HOST = "tts-api.xfyun.cn"
    TTS_API_PATH = "/v2/tts"
    
    def __init__(self):
        self.voice_dir = Path("data/voice")
        self.voice_dir.mkdir(parents=True, exist_ok=True)
        self.default_voice = settings.default_iflytek_voice_id
        self.app_id = settings.iflytek_app_id
        self.api_key = settings.iflytek_api_key
        self.api_secret = settings.iflytek_api_secret
    
    def _create_auth_url(self) -> str:
        """
        创建鉴权URL
        
        使用 HMAC-SHA256 签名生成讯飞API的鉴权URL
        """
        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        
        # 拼接签名原文
        signature_origin = f"host: {self.TTS_API_HOST}\n"
        signature_origin += f"date: {date}\n"
        signature_origin += f"GET {self.TTS_API_PATH} HTTP/1.1"
        
        # 使用HMAC-SHA256加密
        signature_sha = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        signature_sha = base64.b64encode(signature_sha).decode('utf-8')
        
        # 生成authorization
        authorization_origin = f'api_key="{self.api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha}"'
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
        
        # 构建URL参数
        params = {
            "authorization": authorization,
            "date": date,
            "host": self.TTS_API_HOST
        }
        
        url = f"wss://{self.TTS_API_HOST}{self.TTS_API_PATH}?{urlencode(params)}"
        return url
    
    def _get_iflytek_voice_id(self, voice_id: Optional[str]) -> str:
        """
        获取讯飞音色ID
        
        如果传入的是OpenAI音色ID，则转换为对应的讯飞音色
        如果是讯飞音色ID，则直接返回
        否则返回默认音色
        """
        if not voice_id:
            return self.default_voice
        
        # 如果是OpenAI音色，转换为讯飞音色
        if voice_id in self.OPENAI_TO_IFLYTEK_MAP:
            return self.OPENAI_TO_IFLYTEK_MAP[voice_id]
        
        # 如果是有效的讯飞音色，直接返回
        if voice_id in self.AVAILABLE_VOICES:
            return voice_id
        
        # 无效的音色ID，返回默认
        logger.warning(f"Invalid voice_id '{voice_id}', using default: {self.default_voice}")
        return self.default_voice
    
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
            voice_id: 语音音色ID（支持OpenAI或讯飞音色ID）
            user_id: 用户ID（用于日志记录）
            
        Returns:
            语音数据的字节流，如果失败返回None
        """
        if not self.app_id or not self.api_key or not self.api_secret:
            logger.error("iFlytek TTS credentials not configured, cannot generate voice")
            return None
        
        # 获取讯飞音色ID
        iflytek_voice = self._get_iflytek_voice_id(voice_id)
        
        try:
            logger.info(f"Generating voice with iFlytek TTS, voice={iflytek_voice}, text_length={len(text)}")
            
            # 使用同步WebSocket并在线程池中运行
            audio_data = await asyncio.get_event_loop().run_in_executor(
                None,
                self._sync_generate_voice,
                text,
                iflytek_voice
            )
            
            if audio_data:
                logger.info(f"Voice generated successfully, size={len(audio_data)} bytes")
            
            return audio_data
            
        except Exception as e:
            logger.error(f"iFlytek TTS generation error: {str(e)}", exc_info=True)
            return None
    
    def _sync_generate_voice(self, text: str, voice_id: str) -> Optional[bytes]:
        """
        同步方式生成语音（用于在线程池中执行）
        """
        audio_data = bytearray()
        error_occurred = False
        error_message = ""
        
        def on_message(ws, message):
            nonlocal audio_data, error_occurred, error_message
            try:
                data = json.loads(message)
                code = data.get("code", 0)
                
                if code != 0:
                    error_occurred = True
                    error_message = data.get("message", f"Error code: {code}")
                    logger.error(f"iFlytek TTS API error: {error_message}")
                    ws.close()
                    return
                
                # 获取音频数据
                audio = data.get("data", {}).get("audio")
                if audio:
                    audio_bytes = base64.b64decode(audio)
                    audio_data.extend(audio_bytes)
                
                # 检查是否为最后一帧
                status = data.get("data", {}).get("status", 0)
                if status == 2:
                    ws.close()
                    
            except Exception as e:
                error_occurred = True
                error_message = str(e)
                logger.error(f"Error processing TTS response: {e}")
                ws.close()
        
        def on_error(ws, error):
            nonlocal error_occurred, error_message
            error_occurred = True
            error_message = str(error)
            logger.error(f"WebSocket error: {error}")
        
        def on_close(ws, close_status_code, close_msg):
            pass
        
        def on_open(ws):
            # 发送TTS请求
            request_data = {
                "common": {
                    "app_id": self.app_id
                },
                "business": {
                    "aue": "raw",  # raw: pcm格式
                    "auf": "audio/L16;rate=16000",  # 16k采样率
                    "vcn": voice_id,  # 发音人
                    "tte": "UTF8",  # 文本编码
                    "speed": 50,  # 语速，范围0-100
                    "volume": 50,  # 音量，范围0-100
                    "pitch": 50,  # 音高，范围0-100
                },
                "data": {
                    "status": 2,  # 数据状态，2表示一次性发送完毕
                    "text": base64.b64encode(text.encode('utf-8')).decode('utf-8')
                }
            }
            ws.send(json.dumps(request_data))
        
        # 创建鉴权URL
        url = self._create_auth_url()
        
        # 创建WebSocket连接
        ws = websocket.WebSocketApp(
            url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        
        # 运行WebSocket（使用SSL，启用证书验证）
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_REQUIRED})
        
        if error_occurred:
            logger.error(f"TTS generation failed: {error_message}")
            return None
        
        if not audio_data:
            logger.warning("No audio data received from iFlytek TTS")
            return None
        
        # 将PCM数据转换为OGG/Opus格式（Telegram推荐格式）
        # 这里我们直接返回PCM数据，后续可以考虑转换
        return bytes(audio_data)
    
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
        filename = f"voice_{timestamp}{user_suffix}.pcm"
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
            audio_data: 音频数据字节（PCM格式）
            
        Returns:
            BytesIO 缓冲区对象
        """
        buffer = io.BytesIO(audio_data)
        buffer.name = "voice.pcm"  # PCM格式
        buffer.seek(0)
        return buffer
    
    @staticmethod
    def is_voice_id_valid(voice_id: str) -> bool:
        """
        检查音色ID是否有效
        
        支持OpenAI音色ID和讯飞音色ID
        
        Args:
            voice_id: 要检查的音色ID
            
        Returns:
            True 如果有效，否则 False
        """
        if not voice_id:
            return False
        # 同时支持OpenAI音色和讯飞音色
        return (voice_id in IflytekTTSService.AVAILABLE_VOICES or 
                voice_id in IflytekTTSService.OPENAI_TO_IFLYTEK_MAP)
    
    @staticmethod
    def get_available_voices() -> dict:
        """
        获取所有可用的音色列表
        
        Returns:
            可用音色字典，包含音色详细信息
        """
        return IflytekTTSService.AVAILABLE_VOICES.copy()
    
    @staticmethod
    def get_voice_for_gender(gender: str, personality: str = "default") -> str:
        """
        根据性别和性格推荐合适的音色
        
        Args:
            gender: 性别，"male" 或 "female"
            personality: 性格类型，如 "gentle", "lively", "mature" 等
            
        Returns:
            推荐的音色ID
        """
        if gender == "male":
            if personality in ["mature", "calm"]:
                return "vixf"  # 小峰，成熟稳重
            elif personality in ["lively", "humorous"]:
                return "xiaoyu"  # 小宇，阳光开朗
            elif personality in ["warm", "magnetic"]:
                return "aisjiuxu"  # 许久，温暖磁性
            else:
                return "xiaoyu"  # 默认男声
        else:  # female
            if personality in ["gentle", "warm"]:
                return "aisjinger"  # 小婧，温婉动人
            elif personality in ["lively", "cute"]:
                return "vixq"  # 小琪，活泼可爱
            elif personality in ["intellectual", "calm"]:
                return "vixy"  # 小研，知性大方
            elif personality in ["sweet", "young"]:
                return "aisxping"  # 小萍，甜美清新
            elif personality in ["childlike"]:
                return "vinn"  # 楠楠，童年女声
            else:
                return "xiaoyan"  # 默认女声


# 全局讯飞TTS服务实例
iflytek_tts_service = IflytekTTSService()
