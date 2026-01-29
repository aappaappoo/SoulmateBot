"""
Tests for Dialogue Strategy 2.0 features
测试对话策略2.0功能
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.conversation.dialogue_strategy import (
    ConversationType,
    StanceStrategy,
    ConversationTypeAnalyzer,
    StanceAnalyzer,
    StanceAnalysis,
    CONVERSATION_TYPE_SIGNALS,
    STANCE_STRATEGY_TEMPLATES,
    DialogueStrategyInjector
)
from src.bot.config_loader import (
    ValueDimensionsConfig,
    StanceConfig,
    ResponsePreferencesConfig,
    ValuesConfig
)


class TestConversationType:
    """测试ConversationType枚举"""
    
    def test_conversation_type_values(self):
        """测试对话类型枚举值"""
        assert ConversationType.EMOTIONAL_VENT.value == "emotional_vent"
        assert ConversationType.OPINION_DISCUSSION.value == "opinion_discussion"
        assert ConversationType.INFO_REQUEST.value == "info_request"
        assert ConversationType.DECISION_CONSULTING.value == "decision_consulting"
        assert ConversationType.CASUAL_CHAT.value == "casual_chat"


class TestStanceStrategy:
    """测试StanceStrategy枚举"""
    
    def test_stance_strategy_values(self):
        """测试立场策略枚举值"""
        assert StanceStrategy.AGREE.value == "agree"
        assert StanceStrategy.AGREE_AND_ADD.value == "agree_and_add"
        assert StanceStrategy.PARTIAL_AGREE.value == "partial_agree"
        assert StanceStrategy.RESPECTFUL_DISAGREE.value == "respectful_disagree"
        assert StanceStrategy.CHALLENGE.value == "challenge"


class TestConversationTypeSignals:
    """测试对话类型信号词配置"""
    
    def test_signal_words_exist(self):
        """测试信号词配置存在"""
        assert ConversationType.EMOTIONAL_VENT in CONVERSATION_TYPE_SIGNALS
        assert ConversationType.OPINION_DISCUSSION in CONVERSATION_TYPE_SIGNALS
        assert ConversationType.INFO_REQUEST in CONVERSATION_TYPE_SIGNALS
        assert ConversationType.DECISION_CONSULTING in CONVERSATION_TYPE_SIGNALS
    
    def test_emotional_vent_signals(self):
        """测试情绪倾诉信号词"""
        signals = CONVERSATION_TYPE_SIGNALS[ConversationType.EMOTIONAL_VENT]
        assert "难过" in signals
        assert "烦" in signals
        assert "累" in signals
        assert "不知道怎么办" in signals
    
    def test_opinion_discussion_signals(self):
        """测试观点讨论信号词"""
        signals = CONVERSATION_TYPE_SIGNALS[ConversationType.OPINION_DISCUSSION]
        assert "我觉得" in signals
        assert "你怎么看" in signals
        assert "是不是应该" in signals


class TestStanceStrategyTemplates:
    """测试立场策略模板"""
    
    def test_all_strategies_have_templates(self):
        """测试所有策略都有模板"""
        for strategy in StanceStrategy:
            assert strategy in STANCE_STRATEGY_TEMPLATES
            assert len(STANCE_STRATEGY_TEMPLATES[strategy]) > 0
    
    def test_template_contains_guidance(self):
        """测试模板包含指导内容"""
        template = STANCE_STRATEGY_TEMPLATES[StanceStrategy.AGREE_AND_ADD]
        assert "立场策略" in template
        assert "你的人设和性格保持不变" in template


class TestConversationTypeAnalyzer:
    """测试ConversationTypeAnalyzer类"""
    
    def setup_method(self):
        """初始化测试"""
        self.analyzer = ConversationTypeAnalyzer()
    
    def test_detect_emotional_vent(self):
        """测试识别情绪倾诉"""
        message = "今天工作压力好大，我真的很累"
        conv_type = self.analyzer.analyze_type(message)
        assert conv_type == ConversationType.EMOTIONAL_VENT
    
    def test_detect_opinion_discussion(self):
        """测试识别观点讨论"""
        message = "我觉得加班文化不太好，你怎么看？"
        conv_type = self.analyzer.analyze_type(message)
        assert conv_type == ConversationType.OPINION_DISCUSSION
    
    def test_detect_info_request(self):
        """测试识别信息需求"""
        message = "最近有什么好看的电影推荐吗？"
        conv_type = self.analyzer.analyze_type(message)
        assert conv_type == ConversationType.INFO_REQUEST
    
    def test_detect_decision_consulting(self):
        """测试识别决策咨询"""
        message = "我该不该换工作？帮我分析一下"
        conv_type = self.analyzer.analyze_type(message)
        assert conv_type == ConversationType.DECISION_CONSULTING
    
    def test_default_to_casual_chat(self):
        """测试默认识别为日常闲聊"""
        message = "今天天气真不错"
        conv_type = self.analyzer.analyze_type(message)
        assert conv_type == ConversationType.CASUAL_CHAT
    
    def test_emotional_vent_priority(self):
        """测试情绪倾诉优先级最高"""
        # 消息中同时包含情绪倾诉和其他类型的信号词
        message = "我今天很烦，你觉得我该怎么办？"
        conv_type = self.analyzer.analyze_type(message)
        # 应该优先识别为情绪倾诉
        assert conv_type == ConversationType.EMOTIONAL_VENT


class TestStanceAnalysis:
    """测试StanceAnalysis数据类"""
    
    def test_stance_analysis_creation(self):
        """测试立场分析结果创建"""
        analysis = StanceAnalysis(
            user_opinion="加班太多了",
            bot_stance="反对无效加班",
            conflict_level=0.2,
            suggested_strategy=StanceStrategy.AGREE_AND_ADD,
            topic="加班文化"
        )
        assert analysis.user_opinion == "加班太多了"
        assert analysis.bot_stance == "反对无效加班"
        assert analysis.conflict_level == 0.2
        assert analysis.suggested_strategy == StanceStrategy.AGREE_AND_ADD
        assert analysis.topic == "加班文化"


class TestStanceAnalyzer:
    """测试StanceAnalyzer类"""
    
    def setup_method(self):
        """初始化测试"""
        self.analyzer = StanceAnalyzer()
        
        # 创建测试用的bot_values
        self.bot_values = ValuesConfig(
            dimensions=ValueDimensionsConfig(
                rationality=7,
                openness=8,
                assertiveness=7,
                optimism=5,
                depth_preference=6
            ),
            stances=[
                StanceConfig(
                    topic="加班文化",
                    position="反对无效加班，效率比时长重要",
                    confidence=0.8
                ),
                StanceConfig(
                    topic="完美主义",
                    position="差不多就行，别太卷自己",
                    confidence=0.7
                )
            ],
            response_preferences=ResponsePreferencesConfig(
                agree_first=False,
                use_examples=True,
                ask_back=True,
                use_humor=True
            ),
            default_behavior="curious"
        )
    
    def test_analyze_stance_no_match(self):
        """测试没有匹配立场的情况"""
        message = "今天天气真好"
        analysis = self.analyzer.analyze_stance(message, self.bot_values)
        
        assert analysis.bot_stance is None
        assert analysis.suggested_strategy == StanceStrategy.AGREE_AND_ADD
    
    def test_analyze_stance_with_match(self):
        """测试匹配到立场的情况"""
        message = "公司要求加班太多了"
        analysis = self.analyzer.analyze_stance(message, self.bot_values)
        
        assert analysis.bot_stance is not None
        assert analysis.topic == "加班文化"
        assert "反对无效加班" in analysis.bot_stance
    
    def test_match_bot_stance(self):
        """测试匹配Bot立场"""
        message = "最近公司加班特别多"
        matched = self.analyzer._match_bot_stance(message, self.bot_values.stances)
        
        assert matched is not None
        assert matched.topic == "加班文化"
    
    def test_calculate_conflict_low(self):
        """测试计算低冲突"""
        user_message = "加班确实有点多"
        bot_position = "反对无效加班"
        conflict = self.analyzer._calculate_conflict(user_message, bot_position)
        
        assert conflict >= 0.0
        assert conflict <= 1.0
    
    def test_calculate_conflict_high(self):
        """测试计算高冲突"""
        user_message = "我不同意，我反对你的观点，不应该这样"
        bot_position = "某个观点"
        conflict = self.analyzer._calculate_conflict(user_message, bot_position)
        
        # 包含多个否定词，冲突应该较高
        assert conflict > 0.5
    
    def test_determine_strategy_low_conflict(self):
        """测试低冲突情况的策略选择"""
        strategy = self.analyzer._determine_strategy(
            conflict_level=0.2,
            assertiveness=7,
            confidence=0.8,
            preferences=self.bot_values.response_preferences
        )
        # 低冲突 + agree_first=False -> AGREE
        assert strategy == StanceStrategy.AGREE
    
    def test_determine_strategy_high_conflict_high_assertiveness(self):
        """测试高冲突高assertiveness情况"""
        strategy = self.analyzer._determine_strategy(
            conflict_level=0.8,
            assertiveness=8,
            confidence=0.8,
            preferences=self.bot_values.response_preferences
        )
        # 高冲突 + 高assertiveness + 高confidence -> RESPECTFUL_DISAGREE
        assert strategy == StanceStrategy.RESPECTFUL_DISAGREE
    
    def test_determine_strategy_medium_conflict(self):
        """测试中等冲突情况"""
        strategy = self.analyzer._determine_strategy(
            conflict_level=0.5,
            assertiveness=7,
            confidence=0.7,
            preferences=self.bot_values.response_preferences
        )
        # 中等冲突 + 中等assertiveness -> PARTIAL_AGREE
        assert strategy == StanceStrategy.PARTIAL_AGREE


class TestDialogueStrategyInjectorWithValues:
    """测试DialogueStrategyInjector与values的集成"""
    
    def setup_method(self):
        """初始化测试"""
        self.injector = DialogueStrategyInjector()
        self.original_prompt = "你是一个AI助手。"
        
        # 创建测试用的bot_values
        self.bot_values = ValuesConfig(
            dimensions=ValueDimensionsConfig(
                rationality=7,
                openness=8,
                assertiveness=7,
                optimism=5,
                depth_preference=6
            ),
            stances=[
                StanceConfig(
                    topic="加班文化",
                    position="反对无效加班",
                    confidence=0.8
                )
            ],
            response_preferences=ResponsePreferencesConfig(
                agree_first=False,
                use_examples=True,
                ask_back=True,
                use_humor=True
            )
        )
    
    def test_inject_strategy_without_values(self):
        """测试不提供values的情况（向后兼容）"""
        history = [{"role": "user", "content": "你好"}]
        message = "我今天心情不好"
        
        enhanced = self.injector.inject_strategy(
            self.original_prompt,
            history,
            message,
            bot_values=None
        )
        
        # 应该包含原始prompt和策略指导
        assert self.original_prompt in enhanced
        assert "当前对话策略" in enhanced
    
    def test_inject_strategy_with_values(self):
        """测试提供values的情况"""
        history = [{"role": "user", "content": "你好"}]
        message = "我觉得加班太多了"
        
        enhanced = self.injector.inject_strategy(
            self.original_prompt,
            history,
            message,
            bot_values=self.bot_values
        )
        
        # 应该包含原始prompt、价值观指导和策略指导
        assert self.original_prompt in enhanced
        assert "当前对话策略" in enhanced
        assert "你的价值观和立场" in enhanced or "人格维度" in enhanced
    
    def test_inject_strategy_with_opinion_discussion(self):
        """测试观点讨论类型会触发立场分析"""
        history = [{"role": "user", "content": "你好"}]
        message = "我觉得公司要求加班太多了，你怎么看？"
        
        enhanced = self.injector.inject_strategy(
            self.original_prompt,
            history,
            message,
            bot_values=self.bot_values
        )
        
        # 应该包含立场策略
        assert self.original_prompt in enhanced
        assert "立场策略" in enhanced or "关于当前话题的立场" in enhanced
    
    def test_build_values_guidance(self):
        """测试构建价值观指导"""
        guidance = self.injector._build_values_guidance(self.bot_values)
        
        assert len(guidance) > 0
        assert "价值观" in guidance or "人格维度" in guidance
    
    def test_build_stance_guidance(self):
        """测试构建立场指导"""
        stance_analysis = StanceAnalysis(
            user_opinion="加班太多了",
            bot_stance="反对无效加班",
            conflict_level=0.2,
            suggested_strategy=StanceStrategy.AGREE_AND_ADD,
            topic="加班文化"
        )
        
        guidance = self.injector._build_stance_guidance(stance_analysis)
        
        assert len(guidance) > 0
        assert "立场" in guidance
        assert "反对无效加班" in guidance
    
    def test_build_stance_guidance_no_stance(self):
        """测试没有立场时不构建指导"""
        stance_analysis = StanceAnalysis(
            user_opinion="今天天气真好",
            bot_stance=None,
            conflict_level=0.0,
            suggested_strategy=StanceStrategy.AGREE
        )
        
        guidance = self.injector._build_stance_guidance(stance_analysis)
        
        assert guidance == ""


class TestDialogueStrategy2Integration:
    """测试对话策略2.0的集成场景"""
    
    def test_emotional_vent_no_stance_challenge(self):
        """测试情绪倾诉时不会表达反对立场"""
        injector = DialogueStrategyInjector()
        
        bot_values = ValuesConfig(
            dimensions=ValueDimensionsConfig(assertiveness=8),
            stances=[
                StanceConfig(
                    topic="工作",
                    position="要积极面对工作",
                    confidence=0.8
                )
            ]
        )
        
        history = []
        message = "我工作压力好大，真的很累，快崩溃了"
        
        enhanced = injector.inject_strategy(
            "你是一个AI助手。",
            history,
            message,
            bot_values=bot_values
        )
        
        # 情绪倾诉应该优先安慰，不应该表达反对立场
        assert "安慰" in enhanced or "陪伴" in enhanced
    
    def test_opinion_discussion_with_high_assertiveness(self):
        """测试高assertiveness在观点讨论中的表现"""
        injector = DialogueStrategyInjector()
        
        bot_values = ValuesConfig(
            dimensions=ValueDimensionsConfig(assertiveness=8),
            stances=[
                StanceConfig(
                    topic="加班",
                    position="反对无效加班",
                    confidence=0.8
                )
            ],
            response_preferences=ResponsePreferencesConfig(agree_first=False)
        )
        
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好"}
        ]
        message = "我觉得公司要求加班是合理的，你怎么看？"
        
        enhanced = injector.inject_strategy(
            "你是一个AI助手。",
            history,
            message,
            bot_values=bot_values
        )
        
        # 高assertiveness应该能表达立场
        assert "立场" in enhanced
