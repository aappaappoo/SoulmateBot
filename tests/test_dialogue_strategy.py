"""
Tests for dialogue strategy module
测试动态对话策略模块
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.conversation.dialogue_strategy import (
    DialoguePhase,
    ResponseType,
    DialoguePhaseAnalyzer,
    DialogueStrategyInjector,
    enhance_prompt_with_strategy,
    EMOTION_KEYWORDS,
    STRATEGY_TEMPLATES
)


class TestDialoguePhaseEnum:
    """测试DialoguePhase枚举"""
    
    def test_dialogue_phase_values(self):
        """测试对话阶段枚举值"""
        assert DialoguePhase.OPENING.value == "opening"
        assert DialoguePhase.LISTENING.value == "listening"
        assert DialoguePhase.DEEPENING.value == "deepening"
        assert DialoguePhase.SUPPORTING.value == "supporting"


class TestResponseTypeEnum:
    """测试ResponseType枚举"""
    
    def test_response_type_values(self):
        """测试回应类型枚举值"""
        assert ResponseType.ACTIVE_LISTENING.value == "active_listening"
        assert ResponseType.EMPATHIC_QUESTIONING.value == "empathic_questioning"
        assert ResponseType.VALIDATION.value == "validation"
        assert ResponseType.COMFORT.value == "comfort"
        assert ResponseType.GENTLE_GUIDANCE.value == "gentle_guidance"


class TestEmotionKeywords:
    """测试情绪关键词配置"""
    
    def test_emotion_keywords_structure(self):
        """测试情绪关键词结构"""
        assert "negative" in EMOTION_KEYWORDS
        assert "positive" in EMOTION_KEYWORDS
        assert "high" in EMOTION_KEYWORDS["negative"]
        assert "medium" in EMOTION_KEYWORDS["negative"]
        assert "low" in EMOTION_KEYWORDS["negative"]
    
    def test_negative_high_keywords(self):
        """测试高强度负面情绪关键词"""
        keywords = EMOTION_KEYWORDS["negative"]["high"]
        assert "崩溃" in keywords
        assert "绝望" in keywords
        assert "撑不下去" in keywords


class TestStrategyTemplates:
    """测试策略模板"""
    
    def test_all_response_types_have_templates(self):
        """测试所有回应类型都有对应模板"""
        for response_type in ResponseType:
            assert response_type in STRATEGY_TEMPLATES
            assert len(STRATEGY_TEMPLATES[response_type]) > 0
    
    def test_template_contains_guidance(self):
        """测试模板包含必要的指导内容"""
        template = STRATEGY_TEMPLATES[ResponseType.ACTIVE_LISTENING]
        assert "当前对话策略" in template
        assert "本轮重点" in template
        assert "你的人设和性格保持不变" in template


class TestDialoguePhaseAnalyzer:
    """测试DialoguePhaseAnalyzer类"""
    
    def setup_method(self):
        """初始化测试"""
        self.analyzer = DialoguePhaseAnalyzer()
    
    def test_analyze_phase_opening(self):
        """测试开场阶段识别（1-2轮）"""
        history = [
            {"role": "user", "content": "你好"},
        ]
        phase = self.analyzer.analyze_phase(history)
        assert phase == DialoguePhase.OPENING
        
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好啊"},
            {"role": "user", "content": "我今天心情不太好"},
        ]
        phase = self.analyzer.analyze_phase(history)
        assert phase == DialoguePhase.OPENING
    
    def test_analyze_phase_listening(self):
        """测试倾听阶段识别（3-5轮）"""
        history = [
            {"role": "user", "content": "消息1"},
            {"role": "assistant", "content": "回复1"},
            {"role": "user", "content": "消息2"},
            {"role": "assistant", "content": "回复2"},
            {"role": "user", "content": "消息3"},
        ]
        phase = self.analyzer.analyze_phase(history)
        assert phase == DialoguePhase.LISTENING
    
    def test_analyze_phase_deepening(self):
        """测试深入阶段识别（6-8轮）"""
        history = [{"role": "user", "content": f"消息{i}"} for i in range(6)]
        phase = self.analyzer.analyze_phase(history)
        assert phase == DialoguePhase.DEEPENING
    
    def test_analyze_phase_supporting(self):
        """测试支持阶段识别（9轮以上）"""
        history = [{"role": "user", "content": f"消息{i}"} for i in range(10)]
        phase = self.analyzer.analyze_phase(history)
        assert phase == DialoguePhase.SUPPORTING
    
    def test_analyze_phase_empty_history(self):
        """测试空对话历史"""
        history = []
        phase = self.analyzer.analyze_phase(history)
        assert phase == DialoguePhase.OPENING
    
    def test_analyze_emotion_negative_high(self):
        """测试识别高强度负面情绪"""
        message = "我真的崩溃了，完全撑不下去了"
        emotion_type, intensity = self.analyzer.analyze_emotion(message)
        assert emotion_type == "negative"
        assert intensity == "high"
    
    def test_analyze_emotion_negative_medium(self):
        """测试识别中等强度负面情绪"""
        message = "今天感觉很焦虑，压力很大"
        emotion_type, intensity = self.analyzer.analyze_emotion(message)
        assert emotion_type == "negative"
        assert intensity == "medium"
    
    def test_analyze_emotion_negative_low(self):
        """测试识别低强度负面情绪"""
        message = "感觉不太好，有点不舒服"
        emotion_type, intensity = self.analyzer.analyze_emotion(message)
        assert emotion_type == "negative"
        assert intensity == "low"
    
    def test_analyze_emotion_positive_high(self):
        """测试识别高强度正面情绪"""
        message = "太开心了！今天特别好！"
        emotion_type, intensity = self.analyzer.analyze_emotion(message)
        assert emotion_type == "positive"
        assert intensity == "high"
    
    def test_analyze_emotion_positive_medium(self):
        """测试识别中等强度正面情绪"""
        message = "今天很开心，心情不错"
        emotion_type, intensity = self.analyzer.analyze_emotion(message)
        assert emotion_type == "positive"
        assert intensity == "medium"
    
    def test_analyze_emotion_neutral(self):
        """测试识别中性情绪"""
        message = "今天天气怎么样？"
        emotion_type, intensity = self.analyzer.analyze_emotion(message)
        assert emotion_type == "neutral"
        assert intensity == "medium"
    
    def test_suggest_response_type_high_negative(self):
        """测试高强度负面情绪建议安慰"""
        response_type = self.analyzer.suggest_response_type(
            DialoguePhase.OPENING,
            "negative",
            "high"
        )
        assert response_type == ResponseType.COMFORT
    
    def test_suggest_response_type_opening_phase(self):
        """测试开场阶段建议主动倾听"""
        response_type = self.analyzer.suggest_response_type(
            DialoguePhase.OPENING,
            "neutral",
            "medium"
        )
        assert response_type == ResponseType.ACTIVE_LISTENING
    
    def test_suggest_response_type_listening_negative(self):
        """测试倾听阶段负面情绪建议验证"""
        response_type = self.analyzer.suggest_response_type(
            DialoguePhase.LISTENING,
            "negative",
            "medium"
        )
        assert response_type == ResponseType.VALIDATION
    
    def test_suggest_response_type_deepening(self):
        """测试深入阶段建议共情式提问或安慰"""
        # 低强度或中性情绪 -> 共情式提问
        response_type = self.analyzer.suggest_response_type(
            DialoguePhase.DEEPENING,
            "neutral",
            "medium"
        )
        assert response_type == ResponseType.EMPATHIC_QUESTIONING
        
        # 中高强度负面情绪 -> 安慰
        response_type = self.analyzer.suggest_response_type(
            DialoguePhase.DEEPENING,
            "negative",
            "high"
        )
        assert response_type == ResponseType.COMFORT
    
    def test_suggest_response_type_supporting_positive(self):
        """测试支持阶段正面情绪建议共情式提问"""
        response_type = self.analyzer.suggest_response_type(
            DialoguePhase.SUPPORTING,
            "positive",
            "medium"
        )
        assert response_type == ResponseType.EMPATHIC_QUESTIONING
    
    def test_suggest_response_type_supporting_neutral(self):
        """测试支持阶段中性情绪建议温和引导"""
        response_type = self.analyzer.suggest_response_type(
            DialoguePhase.SUPPORTING,
            "neutral",
            "medium"
        )
        assert response_type == ResponseType.GENTLE_GUIDANCE


class TestDialogueStrategyInjector:
    """测试DialogueStrategyInjector类"""
    
    def setup_method(self):
        """初始化测试"""
        self.injector = DialogueStrategyInjector()
        self.original_prompt = "你是一个温柔体贴的AI助手，名叫琪琪。"
    
    def test_inject_strategy_preserves_original_prompt(self):
        """测试策略注入保持原始prompt不变"""
        history = [{"role": "user", "content": "你好"}]
        current_message = "我今天心情不好"
        
        enhanced = self.injector.inject_strategy(
            self.original_prompt,
            history,
            current_message
        )
        
        # 原始prompt应该在增强后的prompt开头
        assert enhanced.startswith(self.original_prompt)
        # 应该包含策略指导
        assert "当前对话策略" in enhanced
    
    def test_inject_strategy_adds_strategy_guidance(self):
        """测试策略注入添加策略指导"""
        history = []
        current_message = "你好"
        
        enhanced = self.injector.inject_strategy(
            self.original_prompt,
            history,
            current_message
        )
        
        # 应该包含策略相关内容
        assert "本轮重点" in enhanced
        assert "你的人设和性格保持不变" in enhanced
    
    def test_inject_strategy_different_phases(self):
        """测试不同对话阶段产生不同策略"""
        # 开场阶段
        history_opening = [{"role": "user", "content": "你好"}]
        enhanced_opening = self.injector.inject_strategy(
            self.original_prompt,
            history_opening,
            "我今天不太好"
        )
        
        # 深入阶段
        history_deepening = [{"role": "user", "content": f"消息{i}"} for i in range(6)]
        enhanced_deepening = self.injector.inject_strategy(
            self.original_prompt,
            history_deepening,
            "我今天不太好"
        )
        
        # 两个增强后的prompt应该不同（因为阶段不同）
        assert enhanced_opening != enhanced_deepening
    
    def test_inject_strategy_with_empty_prompt(self):
        """测试空prompt的情况"""
        history = [{"role": "user", "content": "你好"}]
        current_message = "我今天心情不好"
        
        enhanced = self.injector.inject_strategy(
            "",
            history,
            current_message
        )
        
        # 即使原始prompt为空，也应该有策略指导
        assert "当前对话策略" in enhanced
        assert len(enhanced) > 0


class TestEnhancePromptWithStrategy:
    """测试enhance_prompt_with_strategy便捷函数"""
    
    def test_enhance_prompt_basic(self):
        """测试基本的prompt增强"""
        original_prompt = "你是一个AI助手。"
        history = [{"role": "user", "content": "你好"}]
        current_message = "我需要帮助"
        
        enhanced = enhance_prompt_with_strategy(
            original_prompt,
            history,
            current_message
        )
        
        assert original_prompt in enhanced
        assert "当前对话策略" in enhanced
    
    def test_enhance_prompt_with_empty_history(self):
        """测试空对话历史的prompt增强"""
        original_prompt = "你是一个AI助手。"
        history = []
        current_message = "你好"
        
        enhanced = enhance_prompt_with_strategy(
            original_prompt,
            history,
            current_message
        )
        
        assert original_prompt in enhanced
        assert "当前对话策略" in enhanced
    
    def test_enhance_prompt_maintains_personality(self):
        """测试增强后保持人设完整性"""
        original_prompt = """你是琪琪，一个温柔体贴的女孩。
你的性格特点：
1. 温柔细腻
2. 善于倾听
3. 富有同理心"""
        
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好啊"},
            {"role": "user", "content": "我今天有点难过"},
        ]
        current_message = "你能陪我聊聊吗"
        
        enhanced = enhance_prompt_with_strategy(
            original_prompt,
            history,
            current_message
        )
        
        # 原始人设应该完整保留
        assert "你是琪琪，一个温柔体贴的女孩" in enhanced
        assert "温柔细腻" in enhanced
        assert "善于倾听" in enhanced
        assert "富有同理心" in enhanced
        
        # 同时应该有策略指导
        assert "当前对话策略" in enhanced
        assert "你的人设和性格保持不变" in enhanced


class TestDialogueStrategyIntegration:
    """测试对话策略的集成场景"""
    
    def test_conversation_flow_evolution(self):
        """测试对话流程中策略的演进"""
        original_prompt = "你是一个温柔的AI助手。"
        
        # 第1轮：开场阶段
        history_1 = []
        message_1 = "你好"
        enhanced_1 = enhance_prompt_with_strategy(original_prompt, history_1, message_1)
        assert "主动倾听" in enhanced_1 or "当前对话策略" in enhanced_1
        
        # 第4轮：倾听阶段（需要至少3轮用户消息），使用负面情绪消息
        history_4 = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好"},
            {"role": "user", "content": "我今天心情不好"},
            {"role": "assistant", "content": "怎么了"},
            {"role": "user", "content": "我感觉很难过"},
            {"role": "assistant", "content": "我在听"},
            {"role": "user", "content": "工作压力好大"},
        ]
        message_4 = "我真的很焦虑"  # 负面情绪，会触发 VALIDATION 策略
        enhanced_4 = enhance_prompt_with_strategy(original_prompt, history_4, message_4)
        assert "当前对话策略" in enhanced_4
        # 倾听阶段+负面情绪应该是验证策略
        assert "认可" in enhanced_4 or "验证" in enhanced_4
        
        # 第6轮：深入阶段
        history_6 = [{"role": "user", "content": f"消息{i}"} for i in range(6)]
        message_6 = "你觉得我该怎么办"
        enhanced_6 = enhance_prompt_with_strategy(original_prompt, history_6, message_6)
        assert "当前对话策略" in enhanced_6
        
        # 验证每个阶段的prompt都不同
        assert enhanced_1 != enhanced_4
        assert enhanced_4 != enhanced_6
    
    def test_emotion_based_strategy_selection(self):
        """测试基于情绪的策略选择"""
        original_prompt = "你是一个AI助手。"
        history = [{"role": "user", "content": "你好"}]
        
        # 高强度负面情绪
        message_crisis = "我真的崩溃了，不想活了"
        enhanced_crisis = enhance_prompt_with_strategy(original_prompt, history, message_crisis)
        assert "安慰" in enhanced_crisis or "陪伴" in enhanced_crisis
        
        # 正面情绪
        message_happy = "我今天太开心了！"
        enhanced_happy = enhance_prompt_with_strategy(original_prompt, history, message_happy)
        assert "当前对话策略" in enhanced_happy
    
    def test_strategy_does_not_replace_personality(self):
        """测试策略不会替换原有人设"""
        # 琪琪的人设（温柔型）
        qiqi_prompt = "你是琪琪，一个温柔体贴的女孩。说话轻声细语。"
        
        # 胖胖的人设（幽默型）
        pangpang_prompt = "你是胖胖，一个幽默风趣的男生。说话诙谐有趣。"
        
        history = [{"role": "user", "content": "你好"}]
        message = "我今天心情不好"
        
        # 增强后两个Bot的人设应该仍然不同
        enhanced_qiqi = enhance_prompt_with_strategy(qiqi_prompt, history, message)
        enhanced_pangpang = enhance_prompt_with_strategy(pangpang_prompt, history, message)
        
        # 琪琪的人设保留
        assert "琪琪" in enhanced_qiqi
        assert "温柔体贴" in enhanced_qiqi
        
        # 胖胖的人设保留
        assert "胖胖" in enhanced_pangpang
        assert "幽默风趣" in enhanced_pangpang
        
        # 两者都应该有策略指导
        assert "当前对话策略" in enhanced_qiqi
        assert "当前对话策略" in enhanced_pangpang


class TestEdgeCases:
    """测试边界情况"""
    
    def test_very_long_conversation(self):
        """测试非常长的对话历史"""
        analyzer = DialoguePhaseAnalyzer()
        history = [{"role": "user", "content": f"消息{i}"} for i in range(50)]
        
        phase = analyzer.analyze_phase(history)
        # 应该识别为支持阶段
        assert phase == DialoguePhase.SUPPORTING
    
    def test_message_with_multiple_emotions(self):
        """测试包含多种情绪的消息"""
        analyzer = DialoguePhaseAnalyzer()
        message = "虽然今天有点开心，但还是感觉很焦虑和迷茫"
        
        emotion_type, intensity = analyzer.analyze_emotion(message)
        # 负面情绪应该被优先识别（因为需要更多关注）
        assert emotion_type == "negative"
    
    def test_empty_message(self):
        """测试空消息"""
        analyzer = DialoguePhaseAnalyzer()
        emotion_type, intensity = analyzer.analyze_emotion("")
        
        assert emotion_type == "neutral"
        assert intensity == "medium"
    
    def test_none_original_prompt(self):
        """测试None的original_prompt"""
        history = [{"role": "user", "content": "你好"}]
        message = "我需要帮助"
        
        # 应该不会抛出异常
        enhanced = enhance_prompt_with_strategy(None, history, message)
        assert enhanced is not None
        assert len(enhanced) > 0
        # 不应该包含字符串 "None"
        assert "None" not in enhanced
        # 应该包含策略指导
        assert "当前对话策略" in enhanced


class TestProactiveInquiry:
    """测试主动追问策略"""
    
    def setup_method(self):
        """初始化测试"""
        self.analyzer = DialoguePhaseAnalyzer()
    
    def test_proactive_inquiry_response_type_exists(self):
        """测试主动追问回应类型存在"""
        assert ResponseType.PROACTIVE_INQUIRY.value == "proactive_inquiry"
    
    def test_proactive_inquiry_template_exists(self):
        """测试主动追问模板存在"""
        assert ResponseType.PROACTIVE_INQUIRY in STRATEGY_TEMPLATES
        template = STRATEGY_TEMPLATES[ResponseType.PROACTIVE_INQUIRY]
        assert "主动追问" in template
        assert "兴趣爱好" in template
        assert "星座" in template
    
    def test_no_proactive_inquiry_in_opening_phase(self):
        """测试开场阶段不主动追问"""
        # 用户消息只有1轮，应该是开场阶段
        history = [{"role": "user", "content": "你好"}]
        phase = self.analyzer.analyze_phase(history)
        
        # 即使情绪正面，开场阶段也应该主动倾听而非追问
        response_type = self.analyzer.suggest_response_type(
            phase, "neutral", "medium", history
        )
        assert response_type != ResponseType.PROACTIVE_INQUIRY
    
    def test_no_proactive_inquiry_with_negative_emotion(self):
        """测试负面情绪时不主动追问"""
        # 在深入阶段但有负面情绪
        history = [{"role": "user", "content": f"消息{i}"} for i in range(6)]
        phase = self.analyzer.analyze_phase(history)
        
        response_type = self.analyzer.suggest_response_type(
            phase, "negative", "medium", history
        )
        # 负面情绪时应该安慰，不应追问
        assert response_type == ResponseType.COMFORT
    
    def test_proactive_inquiry_with_neutral_emotion_at_right_turn(self):
        """测试中性情绪且在合适轮次时可能主动追问"""
        # 3轮用户消息（应该在倾听阶段，且3能被3整除）
        history = [
            {"role": "user", "content": "消息1"},
            {"role": "assistant", "content": "回复1"},
            {"role": "user", "content": "消息2"},
            {"role": "assistant", "content": "回复2"},
            {"role": "user", "content": "消息3"},
        ]
        phase = self.analyzer.analyze_phase(history)
        assert phase == DialoguePhase.LISTENING
        
        response_type = self.analyzer.suggest_response_type(
            phase, "neutral", "medium", history
        )
        # 3轮用户消息，中性情绪，应该触发主动追问
        assert response_type == ResponseType.PROACTIVE_INQUIRY
    
    def test_proactive_inquiry_in_supporting_phase_positive(self):
        """测试支持阶段正面情绪时可能主动追问"""
        # 9轮用户消息（应该在支持阶段，且9能被3整除）
        history = [{"role": "user", "content": f"消息{i}"} for i in range(9)]
        phase = self.analyzer.analyze_phase(history)
        assert phase == DialoguePhase.SUPPORTING
        
        response_type = self.analyzer.suggest_response_type(
            phase, "positive", "medium", history
        )
        # 9轮用户消息，正面情绪，应该触发主动追问
        assert response_type == ResponseType.PROACTIVE_INQUIRY


class TestMultiMessageInstruction:
    """测试多消息指令"""
    
    def test_multi_message_instruction_in_enhanced_prompt(self):
        """测试增强后的prompt包含多消息指令"""
        original_prompt = "你是一个AI助手。"
        history = [{"role": "user", "content": "你好"}]
        current_message = "我需要帮助"
        
        enhanced = enhance_prompt_with_strategy(original_prompt, history, current_message)
        
        # 应该包含多消息指令
        assert "[MSG_SPLIT]" in enhanced
        assert "回复格式说明" in enhanced
    
    def test_multi_message_instruction_has_examples(self):
        """测试多消息指令包含示例"""
        original_prompt = "你是一个AI助手。"
        history = [{"role": "user", "content": "你好"}]
        current_message = "我需要帮助"
        
        enhanced = enhance_prompt_with_strategy(original_prompt, history, current_message)
        
        # 应该包含示例
        assert "示例" in enhanced
