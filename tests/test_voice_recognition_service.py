"""
Tests for voice recognition service and voice message handling
测试语音识别服务和语音消息处理
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.voice_recognition_service import (
    VoiceRecognitionService,
    VoiceRecognitionResult,
    EMOTION_KEYWORDS,
)
from src.utils.voice_helper import build_voice_recognition_prompt, VOICE_EMOTION_DESCRIPTIONS


class TestVoiceRecognitionResult:
    """语音识别结果数据类测试"""

    def test_default_result(self):
        """测试默认结果"""
        result = VoiceRecognitionResult()
        assert result.text == ""
        assert result.emotion is None
        assert result.duration_ms is None
        assert result.confidence is None
        assert result.raw_response is None

    def test_result_with_text_and_emotion(self):
        """测试带文本和情绪的结果"""
        result = VoiceRecognitionResult(
            text="你好啊",
            emotion="happy",
        )
        assert result.text == "你好啊"
        assert result.emotion == "happy"


class TestVoiceRecognitionServiceEmotionInference:
    """语音识别服务的情绪推断测试"""

    def test_infer_happy_emotion(self):
        """测试推断开心情绪"""
        service = VoiceRecognitionService()
        assert service._infer_emotion_from_text("哈哈太好了") == "happy"

    def test_infer_sad_emotion(self):
        """测试推断难过情绪"""
        service = VoiceRecognitionService()
        assert service._infer_emotion_from_text("我好难过啊") == "sad"

    def test_infer_angry_emotion(self):
        """测试推断生气情绪"""
        service = VoiceRecognitionService()
        assert service._infer_emotion_from_text("气死了真的") == "angry"

    def test_infer_excited_emotion(self):
        """测试推断激动情绪"""
        service = VoiceRecognitionService()
        assert service._infer_emotion_from_text("哇太厉害了") == "excited"

    def test_infer_crying_emotion(self):
        """测试推断委屈情绪"""
        service = VoiceRecognitionService()
        assert service._infer_emotion_from_text("呜呜呜好委屈") == "crying"

    def test_infer_gentle_emotion(self):
        """测试推断温柔情绪"""
        service = VoiceRecognitionService()
        assert service._infer_emotion_from_text("谢谢你") == "gentle"

    def test_infer_no_emotion(self):
        """测试无情绪"""
        service = VoiceRecognitionService()
        assert service._infer_emotion_from_text("今天天气怎么样") is None

    def test_infer_empty_text(self):
        """测试空文本"""
        service = VoiceRecognitionService()
        assert service._infer_emotion_from_text("") is None

    def test_emotion_priority_angry_over_happy(self):
        """测试情绪优先级 - angry 优先于 happy"""
        service = VoiceRecognitionService()
        # "气死了" -> angry should win over "哈哈" -> happy
        assert service._infer_emotion_from_text("气死了哈哈") == "angry"


class TestBuildVoiceRecognitionPrompt:
    """构建语音识别提示文本的测试"""

    def test_prompt_with_emotion(self):
        """测试带情绪的提示"""
        result = build_voice_recognition_prompt("你好啊", "happy")
        assert "[用户通过语音发送了这条消息，语气听起来是开心的]" in result
        assert "你好啊" in result

    def test_prompt_without_emotion(self):
        """测试不带情绪的提示"""
        result = build_voice_recognition_prompt("你好啊", None)
        assert "[用户通过语音发送了这条消息]" in result
        assert "你好啊" in result

    def test_prompt_with_unknown_emotion(self):
        """测试未知情绪标签"""
        result = build_voice_recognition_prompt("你好啊", "unknown")
        assert "[用户通过语音发送了这条消息]" in result
        assert "你好啊" in result

    def test_prompt_empty_text(self):
        """测试空文本"""
        result = build_voice_recognition_prompt("", "happy")
        assert result == ""

    def test_all_emotion_descriptions_mapped(self):
        """测试所有情绪描述都有映射"""
        for emotion in ["happy", "excited", "sad", "angry", "gentle", "crying"]:
            assert emotion in VOICE_EMOTION_DESCRIPTIONS

    def test_prompt_with_sad_emotion(self):
        """测试带难过情绪的提示"""
        result = build_voice_recognition_prompt("我今天不太开心", "sad")
        assert "语气听起来是难过的" in result
        assert "我今天不太开心" in result

    def test_prompt_with_angry_emotion(self):
        """测试带生气情绪的提示"""
        result = build_voice_recognition_prompt("这太过分了", "angry")
        assert "语气听起来是生气的" in result
        assert "这太过分了" in result


class TestVoiceRecognitionServiceRecognize:
    """语音识别服务的识别功能测试"""

    @pytest.mark.asyncio
    async def test_recognize_returns_empty_when_no_api_key(self):
        """测试无 API key 时返回空结果"""
        service = VoiceRecognitionService()
        service.api_key = None

        result = await service.recognize_voice("/tmp/test.ogg")
        assert result.text == ""
        assert result.emotion is None

    @pytest.mark.asyncio
    async def test_recognize_returns_empty_for_missing_file(self):
        """测试文件不存在时返回空结果"""
        service = VoiceRecognitionService()
        service.api_key = "test_key"

        result = await service.recognize_voice("/tmp/nonexistent_file.ogg")
        assert result.text == ""
        assert result.emotion is None
