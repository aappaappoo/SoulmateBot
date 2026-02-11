"""
语音识别服务 - Voice Recognition Service
使用阿里云 DashScope 的 ASR (Automatic Speech Recognition) API
将用户发送的语音消息转换为文本，并分析语音中的情绪

Usage:
    from src.services.voice_recognition_service import voice_recognition_service

    result = await voice_recognition_service.recognize_voice(audio_file_path)
    # result.text  -> 识别出的文本
    # result.emotion -> 识别出的情绪 (如 "happy", "sad" 等)
"""
import os
import asyncio
import tempfile
from typing import Optional
from dataclasses import dataclass, field
from loguru import logger

from config import settings

try:
    import dashscope
    from dashscope.audio.asr import Recognition

    DASHSCOPE_ASR_AVAILABLE = True
except ImportError:
    DASHSCOPE_ASR_AVAILABLE = False
    logger.warning("dashscope ASR package not available. Voice recognition will not work.")


# 情绪关键词映射 - 从语音识别文本中推断情绪
EMOTION_KEYWORDS = {
    "happy": ["哈哈", "嘻嘻", "开心", "高兴", "太好了", "棒", "好开心", "太棒了", "耶", "好的呀"],
    "excited": ["太厉害了", "哇", "天呐", "真的吗", "不会吧", "太激动"],
    "sad": ["唉", "难过", "伤心", "不开心", "好难过", "心痛", "呜呜", "呜"],
    "angry": ["气死了", "烦死了", "讨厌", "太过分", "生气", "怒"],
    "gentle": ["嗯", "好吧", "好的", "谢谢", "感谢", "辛苦了"],
    "crying": ["呜呜呜", "哭了", "好委屈", "委屈"],
}


@dataclass
class VoiceRecognitionResult:
    """
    语音识别结果

    Attributes:
        text: 识别出的文本内容
        emotion: 推断的情绪类型 (happy, sad, angry, excited, gentle, crying, None)
        duration_ms: 音频时长（毫秒），如果可用
        confidence: 识别置信度（0-1），如果可用
        raw_response: DashScope API 原始响应（用于调试）
    """
    text: str = ""
    emotion: Optional[str] = None
    duration_ms: Optional[int] = None
    confidence: Optional[float] = None
    raw_response: Optional[dict] = field(default=None, repr=False)


class VoiceRecognitionService:
    """
    语音识别服务

    使用阿里云 DashScope ASR API 将语音转为文本，
    并从识别出的文本中推断情绪。
    """

    # 默认 ASR 模型
    DEFAULT_MODEL = "qwen3-asr-flash"

    def __init__(self):
        self.api_key = getattr(settings, 'dashscope_api_key', None)
        self.model = getattr(settings, 'asr_model', self.DEFAULT_MODEL)

        # 从环境变量获取 API key（如果未在配置中设置）
        if not self.api_key and 'DASHSCOPE_API_KEY' in os.environ:
            self.api_key = os.environ['DASHSCOPE_API_KEY']

    async def recognize_voice(
        self,
        audio_file_path: str,
    ) -> VoiceRecognitionResult:
        """
        识别语音文件中的内容

        Args:
            audio_file_path: 音频文件路径 (支持 wav/mp3/ogg/m4a/flac 格式)

        Returns:
            VoiceRecognitionResult: 包含识别文本和情绪的结果对象
        """
        logger.info(
            f"🎙️ [ASR] recognize_voice called: file={audio_file_path}, model={self.model}"
        )

        if not DASHSCOPE_ASR_AVAILABLE:
            logger.error("🎙️ [ASR] dashscope package not installed, cannot recognize voice")
            return VoiceRecognitionResult(text="", emotion=None)

        if not self.api_key:
            logger.error("🎙️ [ASR] DashScope API key not configured")
            return VoiceRecognitionResult(text="", emotion=None)

        if not os.path.exists(audio_file_path):
            logger.error(f"🎙️ [ASR] Audio file not found: {audio_file_path}")
            return VoiceRecognitionResult(text="", emotion=None)

        try:
            # 在线程池中执行同步 ASR 调用
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self._sync_recognize,
                audio_file_path,
            )
            return result

        except Exception as e:
            logger.error(f"🎙️ [ASR] Voice recognition error: {e}", exc_info=True)
            return VoiceRecognitionResult(text="", emotion=None)

    def _sync_recognize(
        self,
        audio_file_path: str,
    ) -> VoiceRecognitionResult:
        """
        同步方式执行语音识别（用于在线程池中执行）

        Args:
            audio_file_path: 音频文件路径

        Returns:
            VoiceRecognitionResult
        """
        try:
            # 设置 API key
            if self.api_key:
                dashscope.api_key = self.api_key

            logger.info(f"🎙️ [ASR] Calling DashScope Recognition API: model={self.model}")

            # 调用 DashScope Recognition API
            response = Recognition.call(
                model=self.model,
                audio_file=audio_file_path,
            )

            logger.debug(f"🎙️ [ASR] Raw response status: {response.status_code}")

            if response.status_code == 200:
                # 提取识别文本
                output = response.output or {}
                recognized_text = ""

                # DashScope ASR 返回格式：output.sentence 或 output.text
                if isinstance(output, dict):
                    recognized_text = output.get("sentence", {}).get("text", "") if isinstance(
                        output.get("sentence"), dict
                    ) else output.get("sentence", "")
                    if not recognized_text:
                        recognized_text = output.get("text", "")
                elif isinstance(output, str):
                    recognized_text = output

                recognized_text = recognized_text.strip()
                logger.info(
                    f"🎙️ [ASR] Recognition successful: text_length={len(recognized_text)}, "
                    f"text='{recognized_text[:100]}...'" if len(recognized_text) > 100
                    else f"🎙️ [ASR] Recognition successful: text='{recognized_text}'"
                )

                # 从文本中推断情绪
                emotion = self._infer_emotion_from_text(recognized_text)
                if emotion:
                    logger.info(f"🎙️ [ASR] Inferred emotion: {emotion}")

                return VoiceRecognitionResult(
                    text=recognized_text,
                    emotion=emotion,
                    raw_response=output,
                )
            else:
                logger.error(
                    f"🎙️ [ASR] Recognition failed: status={response.status_code}, "
                    f"message={response.message}"
                )
                return VoiceRecognitionResult(text="", emotion=None)

        except Exception as e:
            logger.error(f"🎙️ [ASR] Error in sync recognition: {e}", exc_info=True)
            return VoiceRecognitionResult(text="", emotion=None)

    @staticmethod
    def _infer_emotion_from_text(text: str) -> Optional[str]:
        """
        从识别出的文本中推断情绪

        通过关键词匹配来推断用户语音中的情绪倾向。

        Args:
            text: 识别出的文本

        Returns:
            情绪标签 (happy, sad, angry, excited, gentle, crying) 或 None
        """
        if not text:
            return None

        # 按优先级检查情绪关键词
        # Priority: angry > crying > sad > excited > happy > gentle
        priority_order = ["angry", "crying", "sad", "excited", "happy", "gentle"]
        for emotion in priority_order:
            keywords = EMOTION_KEYWORDS.get(emotion, [])
            for keyword in keywords:
                if keyword in text:
                    return emotion

        return None


# 全局语音识别服务实例
voice_recognition_service = VoiceRecognitionService()
