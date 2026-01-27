"""
Text-to-Speech (TTS) service for voice response generation
"""
import io
import os
import base64
import threading
import time
import asyncio
from typing import Optional
from datetime import datetime
from pathlib import Path
from loguru import logger
import subprocess
import tempfile
import re
import numpy as np
from config import settings


try:
    import dashscope
    from dashscope.audio.qwen_tts_realtime import QwenTtsRealtime, QwenTtsRealtimeCallback, AudioFormat

    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False
    logger.warning("dashscope package not installed. Qwen TTS will not be available.")


# 在 qwen_tts_service.py 顶部添加
_EMOTION_PATTERN = re.compile(r'^（语气：([^）]+)）')


def extract_emotion_and_text(text: str) -> str | None:
    """简单提取情感前缀用于日志（避免循环导入）"""
    match = _EMOTION_PATTERN.match(text)
    return match.group(1) if match else None



class QwenTTSCallback(QwenTtsRealtimeCallback):
    """
    Qwen TTS 回调处理器
    用于接收和处理 TTS 生成的音频数据
    """

    def __init__(self):
        self.complete_event = threading.Event()
        self.audio_buffer = bytearray()
        self.session_id = None
        self.first_audio_delay = None
        self.error_message = None
        self._start_time = None

    def on_open(self) -> None:
        logger.debug("Qwen TTS WebSocket connection opened")
        self._start_time = time.time()

    def on_close(self, close_status_code, close_msg) -> None:
        logger.debug(f"Qwen TTS WebSocket connection closed: {close_status_code}, {close_msg}")

    def on_event(self, response: dict) -> None:
        try:
            msg_type = response.get('type')

            if msg_type == 'session.created':
                self.session_id = response.get('session', {}).get('id')
                logger.debug(f"Qwen TTS session created: {self.session_id}")

            elif msg_type == 'response.audio.delta':
                # 首次收到音频数据时记录延迟
                if self.first_audio_delay is None and self._start_time:
                    self.first_audio_delay = time.time() - self._start_time
                    logger.debug(f"Qwen TTS first audio delay: {self.first_audio_delay:.3f}s")

                recv_audio_b64 = response.get('delta', '')
                if recv_audio_b64:
                    pcm_bytes = base64.b64decode(recv_audio_b64)
                    self.audio_buffer.extend(pcm_bytes)

            elif msg_type == 'response.done':
                logger.debug("Qwen TTS response done")

            elif msg_type == 'session.finished':
                logger.debug("Qwen TTS session finished")
                self.complete_event.set()

            elif msg_type == 'error':
                self.error_message = response.get('message', 'Unknown error')
                logger.error(f"Qwen TTS error: {self.error_message}")
                self.complete_event.set()

        except Exception as e:
            logger.error(f"Qwen TTS callback error: {e}")
            self.error_message = str(e)
            self.complete_event.set()

    def wait_for_finished(self, timeout: float = 60.0) -> bool:
        """
        等待 TTS 完成
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            True 如果成功完成，False 如果超时
        """
        return self.complete_event.wait(timeout=timeout)

    def get_audio_bytes(self) -> bytes:
        """
        获取生成的 PCM 音频数据
        
        Returns:
            PCM 格式的音频字节数据
        """
        return bytes(self.audio_buffer)

    def get_audio_numpy(self) -> np.ndarray:
        """
        获取 numpy 格式的音频数据
        PCM_16BIT -> float32 numpy (-1 ~ 1)
        
        Returns:
            numpy 数组格式的音频数据
        """
        pcm = np.frombuffer(self.audio_buffer, dtype=np.int16)
        audio = pcm.astype(np.float32) / 32768.0
        return audio


class QwenTTSService:
    """
    Qwen Text-to-Speech 服务
    使用阿里云 DashScope 的 Qwen TTS Realtime API
    """

    # Qwen TTS 可用音色列表
    # voice 参数    说明                             适用
    # Cherry      阳光积极、亲切自然的女性音色         Realtime & Flash
    # Serena      温柔的女性音色                      Realtime & Flash（部分模型）
    # Ethan       阳光、温暖、活力的男性音色           Realtime & Flash（部分模型）
    # Chelsie     虚拟风格女生                        标准 TTS（部分版本）
    # Dylan       北京话风格男声                      标准 TTS（部分版本）
    # Jada        上海话风格女声                      标准 TTS（部分版本）
    # Sunny       四川话女声                          标准 TTS（部分版本）
    AVAILABLE_VOICES = {
        "Cherry": {"description": "阳光积极、亲切自然的女性音色", "type": "realtime"},
        "Serena": {"description": "温柔的女性音色", "type": "realtime"},
        "Ethan": {"description": "阳光、温暖、活力的男性音色", "type": "realtime"},
        "Chelsie": {"description": "虚拟风格女生", "type": "standard"},
        "Dylan": {"description": "北京话风格男声", "type": "standard"},
        "Jada": {"description": "上海话风格女声", "type": "standard"},
        "Sunny": {"description": "四川话女声", "type": "standard"},
    }

    # 情感映射
    EMOTION_MAP = {
        "happy": "（语气：开心、轻快、兴奋，语速稍快，语调上扬）",
        "gentle": "（语气：温柔、轻声、放慢语速，语调柔和）",
        "sad": "（语气：低落、语速较慢，情绪克制）",
        "excited": "（语气：非常兴奋，节奏活跃，富有感染力）",
        "angry": "（语气：生气，愤怒）",
        "crying": "（委屈，哭泣）",
    }

    # WebSocket API URL
    DEFAULT_API_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"

    # 默认采样率
    SAMPLE_RATE = 24000

    def __init__(self):
        self.voice_dir = Path("data/voice")
        self.voice_dir.mkdir(parents=True, exist_ok=True)
        self.default_voice = getattr(settings, 'default_qwen_voice_id', 'Cherry')
        self.api_key = getattr(settings, 'dashscope_api_key', None)
        self.api_url = getattr(settings, 'dashscope_api_url', self.DEFAULT_API_URL)
        self.model = getattr(settings, 'qwen_tts_model', 'qwen3-tts-flash-realtime')
        self.speed = getattr(settings, 'qwen_tts_speed', 1.0)

        # 从环境变量获取 API key（如果未在配置中设置）
        if not self.api_key and 'DASHSCOPE_API_KEY' in os.environ:
            self.api_key = os.environ['DASHSCOPE_API_KEY']

    def _get_qwen_voice_id(self, voice_id: Optional[str]) -> str:
        """
        获取 Qwen 音色 ID
        
        如果传入的音色有效，则直接返回
        否则返回默认音色
        """
        if not voice_id:
            return self.default_voice

        # 检查是否是有效的 Qwen 音色
        if voice_id in self.AVAILABLE_VOICES:
            return voice_id

        # 尝试匹配（忽略大小写）
        for v in self.AVAILABLE_VOICES:
            if v.lower() == voice_id.lower():
                return v

        logger.warning(f"Invalid Qwen voice_id '{voice_id}', using default: {self.default_voice}")
        return self.default_voice

    async def generate_voice(
            self,
            text: str,
            voice_id: Optional[str] = None,
            user_id: Optional[int] = None,
            emotion: Optional[str] = None
    ) -> Optional[bytes]:
        """
        将文本转换为语音
        
        Args:
            text: 要转换的文本内容
            voice_id: 语音音色 ID
            user_id: 用户 ID（用于日志记录）
            emotion: 情感标签（可选，如 happy, gentle, sad, excited）
            
        Returns:
            语音数据的字节流（PCM 格式），如果失败返回 None
        """
        logger.info(
            f"🔊 [TTS QWEN] generate_voice called: voice_id={voice_id}, text_length={len(text)}, user_id={user_id}")

        if not DASHSCOPE_AVAILABLE:
            logger.error("🔊 [TTS QWEN] dashscope package not installed, cannot generate voice")
            return None

        if not self.api_key:
            logger.error("🔊 [TTS QWEN] DashScope API key not configured, cannot generate voice")
            return None

        # 获取 Qwen 音色 ID
        qwen_voice = self._get_qwen_voice_id(voice_id)
        logger.info(f"🔊 [TTS QWEN] Resolved voice_id: input={voice_id} -> qwen_voice={qwen_voice}")

        try:
            logger.info(f"🔊 [TTS QWEN] Starting WebSocket connection to Qwen TTS API")
            # 使用同步 WebSocket 并在线程池中运行
            audio_data = await asyncio.get_event_loop().run_in_executor(
                None,
                self._sync_generate_voice,
                text,
                qwen_voice,
                emotion
            )

            if audio_data:
                logger.info(f"🔊 [TTS QWEN] Voice generated successfully: audio_size={len(audio_data)} bytes")
            else:
                logger.warning(f"🔊 [TTS QWEN] Voice generation returned no data")

            return audio_data

        except Exception as e:
            logger.error(f"🔊 [TTS QWEN] TTS generation error: {str(e)}", exc_info=True)
            return None

    def _sync_generate_voice(
            self,
            text: str,
            voice_id: str,
            emotion: Optional[str] = None
    ) -> Optional[bytes]:
        """
        同步方式生成语音（用于在线程池中执行）
        """
        callback = QwenTTSCallback()
        qwen_tts_realtime = None

        try:
            if self.api_key:
                dashscope.api_key = self.api_key

            # 创建 TTS 客户端，传入 API key
            qwen_tts_realtime = QwenTtsRealtime(
                model=self.model,
                callback=callback,
                url=self.api_url,
            )

            # 连接
            qwen_tts_realtime.connect()
            # 更新会话配置
            qwen_tts_realtime.update_session(
                voice=voice_id,
                response_format=AudioFormat.PCM_24000HZ_MONO_16BIT,
                mode='server_commit',
            )

            # 如果有情感标签，添加情感描述前缀
            extracted_emotion = extract_emotion_and_text(text)
            if extracted_emotion:
                logger.debug(f"🔊 [TTS QWEN] Text contains emotion prefix: {extracted_emotion}")
            else:
                logger.debug(f"🔊 [TTS QWEN] Text contains emotion prefix: None")

            # 这个部分暂时先删除后续增加情感部分
            text = re.compile(r'^（语气：[^）]+）').sub('', text)
            qwen_tts_realtime.append_text(text)

            # 完成发送
            qwen_tts_realtime.finish()

            # 等待完成
            if not callback.wait_for_finished(timeout=60.0):
                logger.error("🔊 [TTS QWEN] TTS generation timeout")
                return None

            # 检查是否有错误
            if callback.error_message:
                logger.error(f"🔊 [TTS QWEN] TTS generation failed: {callback.error_message}")
                return None

            # 获取音频数据
            audio_data = callback.get_audio_bytes()

            if not audio_data:
                logger.warning("🔊 [TTS QWEN] No audio data received from Qwen TTS")
                return None

            logger.info(f"🔊 [TTS QWEN] Metrics - session: {callback.session_id}, "
                        f"first_audio_delay: {callback.first_audio_delay:.3f}s" if callback.first_audio_delay else "")

            return audio_data

        except Exception as e:
            logger.error(f"🔊 [TTS QWEN] Error in sync voice generation: {e}", exc_info=True)
            return None
        finally:
            # 确保清理连接资源
            if qwen_tts_realtime is not None:
                try:
                    # 尝试关闭连接
                    if hasattr(qwen_tts_realtime, 'close'):
                        qwen_tts_realtime.close()
                except Exception as cleanup_error:
                    logger.debug(f"🔊 [TTS QWEN] Cleanup error (ignored): {cleanup_error}")

    async def generate_voice_file(
            self,
            text: str,
            voice_id: Optional[str] = None,
            user_id: Optional[int] = None,
            emotion: Optional[str] = None
    ) -> Optional[str]:
        """
        将文本转换为语音并保存到文件
        
        Args:
            text: 要转换的文本内容
            voice_id: 语音音色 ID
            user_id: 用户 ID
            emotion: 情感标签
            
        Returns:
            语音文件路径，如果失败返回 None
        """
        audio_data = await self.generate_voice(text, voice_id, user_id, emotion)

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
        将 PCM 音频数据转换为 Telegram 支持的 OGG/Opus 格式

        Args:
            audio_data: PCM 格式的音频字节数据 (24kHz, 16-bit, mono)

        Returns:
            BytesIO 缓冲区对象（OGG/Opus 格式）
        """
        try:
            # 使用 ffmpeg 将 PCM 转换为 OGG/Opus
            with tempfile.NamedTemporaryFile(suffix='.pcm', delete=False) as pcm_file:
                pcm_file.write(audio_data)
                pcm_path = pcm_file.name

            ogg_path = pcm_path.replace('.pcm', '.ogg')
            tempo_value = max(0.5, min(2.0, self.speed))  # 限制在有效范围内
            logger.info(f"🔊 [TTS QWEN] update_session with speed={self.speed}")
            cmd = [
                'ffmpeg', '-y',
                '-f', 's16le',
                '-ar', '24000',
                '-ac', '1',
                '-i', pcm_path,
                '-af', f'atempo={tempo_value}',  # 添加语速调整
                '-c:a', 'libopus',
                '-b:a', '32k',
                ogg_path
            ]

            subprocess.run(cmd, check=True, capture_output=True)

            # 读取转换后的文件
            with open(ogg_path, 'rb') as f:
                ogg_data = f.read()

            # 清理临时文件
            import os
            os.unlink(pcm_path)
            os.unlink(ogg_path)
            buffer = io.BytesIO(ogg_data)
            buffer.name = "voice.ogg"
            buffer.seek(0)

            logger.info(f"🔊 [TTS QWEN] Converted PCM to OGG/Opus: {len(audio_data)} -> {len(ogg_data)} bytes")
            return buffer

        except Exception as e:
            logger.error(f"🔊 [TTS QWEN] Failed to convert PCM to OGG: {e}")
            # 回退：返回原始 PCM（虽然 Telegram 不支持）
            buffer = io.BytesIO(audio_data)
            buffer.name = "voice.pcm"
            buffer.seek(0)
            return buffer

    @staticmethod
    def is_voice_id_valid(voice_id: str) -> bool:
        """
        检查音色 ID 是否有效
        
        Args:
            voice_id: 要检查的音色 ID
            
        Returns:
            True 如果有效，否则 False
        """
        if not voice_id:
            return False

        # 检查是否在可用音色列表中（忽略大小写）
        return voice_id in QwenTTSService.AVAILABLE_VOICES or \
            voice_id.lower() in [v.lower() for v in QwenTTSService.AVAILABLE_VOICES]

    @staticmethod
    def get_available_voices() -> dict:
        """
        获取所有可用的音色列表
        
        Returns:
            可用音色字典，包含音色详细信息
        """
        return QwenTTSService.AVAILABLE_VOICES.copy()

    @staticmethod
    def get_voice_for_gender(gender: str, personality: str = "default") -> str:
        """
        根据性别和性格推荐合适的音色
        
        Args:
            gender: 性别，"male" 或 "female"
            personality: 性格类型，如 "gentle", "lively", "mature" 等
            
        Returns:
            推荐的音色 ID
        """
        if gender == "male":
            # 男性音色
            if personality in ["warm", "lively", "default"]:
                return "Ethan"  # 阳光、温暖、活力的男性音色
            elif personality in ["mature", "calm"]:
                return "Dylan"  # 北京话风格男声
            else:
                return "Ethan"  # 默认男声
        else:  # female
            # 女性音色
            if personality in ["gentle", "warm"]:
                return "Serena"  # 温柔的女性音色
            elif personality in ["lively", "cute", "default"]:
                return "Cherry"  # 阳光积极、亲切自然的女性音色
            elif personality in ["virtual", "young"]:
                return "Chelsie"  # 虚拟风格女生
            else:
                return "Cherry"  # 默认女声


# 全局 Qwen TTS 服务实例
qwen_tts_service = QwenTTSService()
