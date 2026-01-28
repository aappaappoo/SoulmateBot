"""
Tests for emotion parser utility
测试语气解析工具
"""
import pytest

# Import directly from the module file to avoid dependency chain issues
import sys
import os
import importlib.util

# Get the path to the emotion_parser module
module_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'utils', 'emotion_parser.py')
spec = importlib.util.spec_from_file_location("emotion_parser", module_path)
emotion_parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(emotion_parser)

# Import functions from the loaded module
extract_emotion_and_text = emotion_parser.extract_emotion_and_text
strip_emotion_prefix = emotion_parser.strip_emotion_prefix
parse_llm_response_with_emotion = emotion_parser.parse_llm_response_with_emotion
ParsedEmotionResponse = emotion_parser.ParsedEmotionResponse


class TestEmotionParser:
    """语气解析器测试类"""
    
    def test_extract_happy_emotion(self):
        """测试提取开心语气"""
        response = "（语气：开心、轻快，语速稍快，语调上扬）你好啊！今天天气真好！"
        emotion, text = extract_emotion_and_text(response)
        
        assert emotion == "happy"
        assert text == "你好啊！今天天气真好！"
    
    def test_extract_excited_emotion(self):
        """测试提取兴奋语气（兴奋关键词优先级高于开心）"""
        response = "（语气：开心、轻快、兴奋，语速稍快，语调上扬）你好啊！今天天气真好！"
        emotion, text = extract_emotion_and_text(response)
        
        # 因为包含"兴奋"关键词，优先级高于"开心"
        assert emotion == "excited"
        assert text == "你好啊！今天天气真好！"
    
    def test_extract_gentle_emotion(self):
        """测试提取温柔语气"""
        response = "（语气：温柔、轻声、放慢语速，语调柔和）我理解你的感受，慢慢来没关系的"
        emotion, text = extract_emotion_and_text(response)
        
        assert emotion == "gentle"
        assert text == "我理解你的感受，慢慢来没关系的"
    
    def test_extract_sad_emotion(self):
        """测试提取低落语气"""
        response = "（语气：低落、语速较慢，情绪克制）我知道这对你来说很难..."
        emotion, text = extract_emotion_and_text(response)
        
        assert emotion == "sad"
        assert text == "我知道这对你来说很难..."
    
    def test_extract_angry_emotion(self):
        """测试提取生气语气"""
        response = "（语气：生气，愤怒）这太过分了！"
        emotion, text = extract_emotion_and_text(response)
        
        assert emotion == "angry"
        assert text == "这太过分了！"
    
    def test_extract_excited_emotion_from_node(self):
        """测试提取兴奋语气"""
        response = "（语气：非常兴奋，节奏活跃，富有感染力）太棒了！恭喜你！"
        emotion, text = extract_emotion_and_text(response)
        
        assert emotion == "excited"
        assert text == "太棒了！恭喜你！"
    
    def test_extract_crying_emotion(self):
        """测试提取哭泣语气"""
        response = "（语气：委屈，哭泣）为什么会这样..."
        emotion, text = extract_emotion_and_text(response)
        
        assert emotion == "crying"
        assert text == "为什么会这样..."
    
    def test_no_emotion_prefix(self):
        """测试没有语气前缀的情况"""
        response = "这是一条普通的回复，没有语气标签"
        emotion, text = extract_emotion_and_text(response)
        
        assert emotion is None
        assert text == "这是一条普通的回复，没有语气标签"
    
    def test_empty_response(self):
        """测试空响应"""
        emotion, text = extract_emotion_and_text("")
        
        assert emotion is None
        assert text == ""
    
    def test_none_response(self):
        """测试None响应"""
        emotion, text = extract_emotion_and_text(None)
        
        assert emotion is None
        assert text == ""
    
    def test_emotion_in_middle_not_matched(self):
        """测试语气前缀不在开头时不匹配"""
        response = "前面有内容（语气：开心）这个不应该被匹配"
        emotion, text = extract_emotion_and_text(response)
        
        assert emotion is None
        assert text == response
    
    def test_strip_emotion_prefix(self):
        """测试只剥离语气前缀"""
        response = "（语气：开心、轻快）欢迎回来！"
        clean_text = strip_emotion_prefix(response)
        
        assert clean_text == "欢迎回来！"
    
    def test_strip_no_prefix(self):
        """测试没有前缀时返回原文本"""
        response = "这是普通文本"
        clean_text = strip_emotion_prefix(response)
        
        assert clean_text == response
    
    def test_complex_emotion_description(self):
        """测试复杂的语气描述"""
        response = "（语气：温柔但带着一丝担心，语速放慢，声音轻柔）你还好吗？"
        emotion, text = extract_emotion_and_text(response)
        
        # 应该匹配到温柔
        assert emotion == "gentle"
        assert text == "你还好吗？"
    
    def test_emotion_priority_angry_over_sad(self):
        """测试情绪优先级：生气优先于低落"""
        response = "（语气：低落又生气，情绪复杂）这真是太让人失望了"
        emotion, text = extract_emotion_and_text(response)
        
        # angry 优先级高于 sad
        assert emotion == "angry"
    
    def test_text_with_leading_whitespace(self):
        """测试内容前有空格的情况"""
        response = "（语气：开心）   你好！"
        emotion, text = extract_emotion_and_text(response)
        
        assert emotion == "happy"
        assert text == "你好！"  # 空格应该被去掉
    
    def test_multiline_content(self):
        """测试多行内容"""
        response = "（语气：温柔、轻声）第一行\n第二行\n第三行"
        emotion, text = extract_emotion_and_text(response)
        
        assert emotion == "gentle"
        assert text == "第一行\n第二行\n第三行"


class TestEmotionParserEdgeCases:
    """边界情况测试"""
    
    def test_parentheses_only(self):
        """测试只有括号的情况"""
        response = "（）后面的内容"
        emotion, text = extract_emotion_and_text(response)
        
        assert emotion is None
        assert text == response
    
    def test_incomplete_prefix(self):
        """测试不完整的前缀"""
        response = "（语气：开心"  # 缺少闭合括号
        emotion, text = extract_emotion_and_text(response)
        
        assert emotion is None
        assert text == response
    
    def test_wrong_prefix_format(self):
        """测试错误的前缀格式"""
        response = "（情绪：开心）这个格式不对"  # 使用"情绪"而不是"语气"
        emotion, text = extract_emotion_and_text(response)
        
        assert emotion is None
        assert text == response
    
    def test_english_parentheses_not_matched(self):
        """测试英文括号不匹配"""
        response = "(语气：开心)这个不应该匹配"
        emotion, text = extract_emotion_and_text(response)
        
        assert emotion is None
        assert text == response
    
    def test_unknown_emotion_keywords(self):
        """测试未知情绪关键词"""
        response = "（语气：平静、冷漠）这是一个未知情绪"
        emotion, text = extract_emotion_and_text(response)
        
        # 前缀被识别，但情绪标签为None因为没有匹配的关键词
        assert emotion is None
        assert text == "这是一个未知情绪"


class TestParseLLMResponseWithEmotion:
    """测试 parse_llm_response_with_emotion 函数"""
    
    def test_json_format_parsing(self):
        """测试JSON格式解析"""
        json_response = '{"response": "你好啊！", "emotion_info": {"emotion_type": "happy", "intensity": "high", "tone_description": "开心、轻快"}}'
        parsed = parse_llm_response_with_emotion(json_response)
        
        assert parsed.clean_text == "你好啊！"
        assert parsed.emotion_type == "happy"
        assert parsed.intensity == "high"
        assert parsed.tone_description == "开心、轻快"
    
    def test_json_format_without_emotion_info(self):
        """测试JSON格式但不包含emotion_info"""
        json_response = '{"response": "普通回复内容"}'
        parsed = parse_llm_response_with_emotion(json_response)
        
        assert parsed.clean_text == "普通回复内容"
        assert parsed.emotion_type is None
        assert parsed.intensity is None
    
    def test_legacy_prefix_format(self):
        """测试传统前缀格式解析"""
        response = "（语气：温柔、轻声）我理解你的感受"
        parsed = parse_llm_response_with_emotion(response)
        
        assert parsed.clean_text == "我理解你的感受"
        assert parsed.emotion_type == "gentle"
        assert parsed.intensity == "medium"  # Default intensity
    
    def test_legacy_prefix_with_high_intensity(self):
        """测试传统前缀格式带高强度关键词"""
        response = "（语气：非常开心、强烈兴奋）太棒了！"
        parsed = parse_llm_response_with_emotion(response)
        
        assert parsed.clean_text == "太棒了！"
        assert parsed.emotion_type == "excited"
        assert parsed.intensity == "high"
    
    def test_plain_text_response(self):
        """测试普通文本响应"""
        response = "这是一条普通的回复"
        parsed = parse_llm_response_with_emotion(response)
        
        assert parsed.clean_text == "这是一条普通的回复"
        assert parsed.emotion_type is None
        assert parsed.intensity is None
    
    def test_empty_response(self):
        """测试空响应"""
        parsed = parse_llm_response_with_emotion("")
        
        assert parsed.clean_text == ""
        assert parsed.emotion_type is None
    
    def test_none_response(self):
        """测试None响应"""
        parsed = parse_llm_response_with_emotion(None)
        
        assert parsed.clean_text == ""
        assert parsed.emotion_type is None
    
    def test_invalid_json(self):
        """测试无效JSON（回退到普通文本）"""
        response = "{invalid json"
        parsed = parse_llm_response_with_emotion(response)
        
        assert parsed.clean_text == response
        assert parsed.emotion_type is None
    
    def test_json_without_response_field(self):
        """测试JSON缺少response字段（回退到普通文本）"""
        response = '{"content": "内容", "emotion_info": {}}'
        parsed = parse_llm_response_with_emotion(response)
        
        # Should fall back to treating as plain text
        assert parsed.clean_text == response


class TestParsedEmotionResponse:
    """测试 ParsedEmotionResponse 类"""
    
    def test_to_dict(self):
        """测试转换为字典"""
        parsed = ParsedEmotionResponse(
            clean_text="你好",
            emotion_type="happy",
            intensity="high",
            tone_description="开心、轻快"
        )
        result = parsed.to_dict()
        
        assert result["clean_text"] == "你好"
        assert result["emotion_type"] == "happy"
        assert result["intensity"] == "high"
        assert result["tone_description"] == "开心、轻快"
    
    def test_get_emotion_info_dict(self):
        """测试获取情绪信息字典"""
        parsed = ParsedEmotionResponse(
            clean_text="你好",
            emotion_type="happy",
            intensity="high",
            tone_description="开心"
        )
        emotion_info = parsed.get_emotion_info_dict()
        
        assert emotion_info is not None
        assert emotion_info["emotion_type"] == "happy"
        assert "clean_text" not in emotion_info
    
    def test_get_emotion_info_dict_empty(self):
        """测试情绪信息全为空时返回None"""
        parsed = ParsedEmotionResponse(clean_text="你好")
        emotion_info = parsed.get_emotion_info_dict()
        
        assert emotion_info is None
    
    def test_get_emotion_info_dict_partial(self):
        """测试部分情绪信息"""
        parsed = ParsedEmotionResponse(
            clean_text="你好",
            emotion_type="happy"
        )
        emotion_info = parsed.get_emotion_info_dict()
        
        assert emotion_info is not None
        assert emotion_info["emotion_type"] == "happy"
        assert emotion_info["intensity"] is None


class TestParseMultiMessageResponse:
    """测试 parse_multi_message_response 函数"""
    
    # Import the function
    @pytest.fixture(autouse=True)
    def setup(self):
        self.parse_multi_message_response = emotion_parser.parse_multi_message_response
    
    def test_single_message_no_split(self):
        """测试单条消息（无分隔符）"""
        response = "你好啊，今天天气真好！"
        messages, full_content = self.parse_multi_message_response(response)
        
        assert len(messages) == 1
        assert messages[0] == "你好啊，今天天气真好！"
        assert full_content == "你好啊，今天天气真好！"
    
    def test_two_messages_split(self):
        """测试两条消息（有分隔符）"""
        response = "你好啊[MSG_SPLIT]今天天气真好！"
        messages, full_content = self.parse_multi_message_response(response)
        
        assert len(messages) == 2
        assert messages[0] == "你好啊"
        assert messages[1] == "今天天气真好！"
        assert full_content == "你好啊\n今天天气真好！"
    
    def test_three_messages_split(self):
        """测试三条消息（两个分隔符）"""
        response = "第一条[MSG_SPLIT]第二条[MSG_SPLIT]第三条"
        messages, full_content = self.parse_multi_message_response(response)
        
        assert len(messages) == 3
        assert messages[0] == "第一条"
        assert messages[1] == "第二条"
        assert messages[2] == "第三条"
        assert full_content == "第一条\n第二条\n第三条"
    
    def test_more_than_three_messages_truncated(self):
        """测试超过三条消息被截断"""
        response = "第一条[MSG_SPLIT]第二条[MSG_SPLIT]第三条[MSG_SPLIT]第四条[MSG_SPLIT]第五条"
        messages, full_content = self.parse_multi_message_response(response)
        
        # Should be limited to 3 messages
        assert len(messages) == 3
        assert messages[0] == "第一条"
        assert messages[1] == "第二条"
        assert messages[2] == "第三条"
    
    def test_empty_response(self):
        """测试空响应"""
        messages, full_content = self.parse_multi_message_response("")
        
        assert len(messages) == 0
        assert full_content == ""
    
    def test_none_response(self):
        """测试None响应"""
        messages, full_content = self.parse_multi_message_response(None)
        
        assert len(messages) == 0
        assert full_content == ""
    
    def test_whitespace_around_split(self):
        """测试分隔符周围有空白"""
        response = "你好啊  [MSG_SPLIT]  今天天气真好！"
        messages, full_content = self.parse_multi_message_response(response)
        
        assert len(messages) == 2
        assert messages[0] == "你好啊"
        assert messages[1] == "今天天气真好！"
    
    def test_empty_parts_filtered(self):
        """测试空部分被过滤"""
        response = "[MSG_SPLIT]你好啊[MSG_SPLIT][MSG_SPLIT]今天天气真好！[MSG_SPLIT]"
        messages, full_content = self.parse_multi_message_response(response)
        
        assert len(messages) == 2
        assert messages[0] == "你好啊"
        assert messages[1] == "今天天气真好！"
    
    def test_with_emotion_prefix(self):
        """测试带语气前缀的多消息"""
        response = "（语气：开心）你好啊[MSG_SPLIT]今天天气真好！"
        messages, full_content = self.parse_multi_message_response(response)
        
        assert len(messages) == 2
        # The emotion prefix is preserved in the first message
        assert "（语气：开心）" in messages[0]
        assert messages[1] == "今天天气真好！"
