"""
Tests for value configuration in config_loader module
测试config_loader模块中的价值观配置功能
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.bot.config_loader import (
    ValueDimensionsConfig,
    StanceConfig,
    ResponsePreferencesConfig,
    ValuesConfig,
    SkillTierConfig,
    BotConfigLoader
)


class TestValueDimensionsConfig:
    """测试ValueDimensionsConfig类"""
    
    def test_default_values(self):
        """测试默认值"""
        config = ValueDimensionsConfig()
        assert config.rationality == 5
        assert config.openness == 5
        assert config.assertiveness == 5
        assert config.optimism == 5
        assert config.depth_preference == 5
    
    def test_custom_values(self):
        """测试自定义值"""
        config = ValueDimensionsConfig(
            rationality=3,
            openness=7,
            assertiveness=6,
            optimism=8,
            depth_preference=4
        )
        assert config.rationality == 3
        assert config.openness == 7
        assert config.assertiveness == 6
        assert config.optimism == 8
        assert config.depth_preference == 4


class TestStanceConfig:
    """测试StanceConfig类"""
    
    def test_stance_config_creation(self):
        """测试立场配置创建"""
        stance = StanceConfig(
            topic="加班文化",
            position="反对无效加班",
            confidence=0.8
        )
        assert stance.topic == "加班文化"
        assert stance.position == "反对无效加班"
        assert stance.confidence == 0.8
    
    def test_stance_default_confidence(self):
        """测试默认confidence值"""
        stance = StanceConfig(
            topic="测试话题",
            position="测试观点"
        )
        assert stance.confidence == 0.5


class TestResponsePreferencesConfig:
    """测试ResponsePreferencesConfig类"""
    
    def test_default_preferences(self):
        """测试默认偏好"""
        prefs = ResponsePreferencesConfig()
        assert prefs.agree_first is True
        assert prefs.use_examples is True
        assert prefs.ask_back is True
        assert prefs.use_humor is False
    
    def test_custom_preferences(self):
        """测试自定义偏好"""
        prefs = ResponsePreferencesConfig(
            agree_first=False,
            use_examples=True,
            ask_back=True,
            use_humor=True
        )
        assert prefs.agree_first is False
        assert prefs.use_humor is True


class TestValuesConfig:
    """测试ValuesConfig类"""
    
    def test_default_values_config(self):
        """测试默认值配置"""
        config = ValuesConfig()
        assert isinstance(config.dimensions, ValueDimensionsConfig)
        assert isinstance(config.response_preferences, ResponsePreferencesConfig)
        assert config.stances == []
        assert config.default_behavior == "curious"
    
    def test_values_config_with_stances(self):
        """测试包含立场的值配置"""
        stances = [
            StanceConfig(topic="话题1", position="观点1", confidence=0.7),
            StanceConfig(topic="话题2", position="观点2", confidence=0.8)
        ]
        config = ValuesConfig(
            stances=stances,
            default_behavior="neutral"
        )
        assert len(config.stances) == 2
        assert config.stances[0].topic == "话题1"
        assert config.default_behavior == "neutral"


class TestSkillTierConfig:
    """测试SkillTierConfig类"""
    
    def test_default_skill_tiers(self):
        """测试默认技能分层"""
        config = SkillTierConfig()
        assert "emotional_support" in config.basic
        assert "daily_chat" in config.basic
        assert "web_search" in config.premium
        assert "long_term_memory" in config.premium
    
    def test_custom_skill_tiers(self):
        """测试自定义技能分层"""
        config = SkillTierConfig(
            basic=["skill1", "skill2"],
            premium=["skill3", "skill4"]
        )
        assert config.basic == ["skill1", "skill2"]
        assert config.premium == ["skill3", "skill4"]


class TestBotConfigLoaderValues:
    """测试BotConfigLoader对values的解析"""
    
    def setup_method(self):
        """初始化测试"""
        self.loader = BotConfigLoader(bots_dir="bots")
    
    def test_parse_values_config_with_empty_data(self):
        """测试解析空values数据"""
        data = {}
        values = self.loader._parse_values_config(data)
        
        assert isinstance(values, ValuesConfig)
        assert values.dimensions.rationality == 5
        assert values.stances == []
        assert values.default_behavior == "curious"
    
    def test_parse_values_config_with_dimensions(self):
        """测试解析包含维度的values数据"""
        data = {
            "dimensions": {
                "rationality": 7,
                "openness": 8,
                "assertiveness": 6,
                "optimism": 9,
                "depth_preference": 5
            }
        }
        values = self.loader._parse_values_config(data)
        
        assert values.dimensions.rationality == 7
        assert values.dimensions.openness == 8
        assert values.dimensions.assertiveness == 6
        assert values.dimensions.optimism == 9
        assert values.dimensions.depth_preference == 5
    
    def test_parse_values_config_with_stances(self):
        """测试解析包含立场的values数据"""
        data = {
            "stances": [
                {
                    "topic": "加班文化",
                    "position": "反对无效加班",
                    "confidence": 0.8
                },
                {
                    "topic": "完美主义",
                    "position": "差不多就行",
                    "confidence": 0.7
                }
            ]
        }
        values = self.loader._parse_values_config(data)
        
        assert len(values.stances) == 2
        assert values.stances[0].topic == "加班文化"
        assert values.stances[0].position == "反对无效加班"
        assert values.stances[0].confidence == 0.8
        assert values.stances[1].topic == "完美主义"
    
    def test_parse_values_config_with_preferences(self):
        """测试解析包含偏好的values数据"""
        data = {
            "response_preferences": {
                "agree_first": False,
                "use_examples": True,
                "ask_back": True,
                "use_humor": True
            }
        }
        values = self.loader._parse_values_config(data)
        
        assert values.response_preferences.agree_first is False
        assert values.response_preferences.use_examples is True
        assert values.response_preferences.ask_back is True
        assert values.response_preferences.use_humor is True
    
    def test_parse_values_config_complete(self):
        """测试解析完整的values配置"""
        data = {
            "dimensions": {
                "rationality": 7,
                "openness": 8,
                "assertiveness": 7,
                "optimism": 5,
                "depth_preference": 6
            },
            "stances": [
                {
                    "topic": "加班文化",
                    "position": "反对无效加班",
                    "confidence": 0.8
                }
            ],
            "response_preferences": {
                "agree_first": False,
                "use_examples": True,
                "ask_back": True,
                "use_humor": True
            },
            "default_behavior": "neutral"
        }
        values = self.loader._parse_values_config(data)
        
        assert values.dimensions.rationality == 7
        assert len(values.stances) == 1
        assert values.response_preferences.agree_first is False
        assert values.default_behavior == "neutral"
    
    def test_load_tuantuan_config_with_values(self):
        """测试加载团团配置（包含values）"""
        config = self.loader.load_config("tuantuan_bot")
        
        if config:  # 如果配置文件存在
            assert hasattr(config, 'values')
            assert isinstance(config.values, ValuesConfig)
            # 检查团团的价值观配置
            assert config.values.dimensions.rationality == 3  # 偏感性
            assert config.values.dimensions.optimism == 8  # 很乐观
            assert len(config.values.stances) >= 1  # 至少有一个立场
    
    def test_load_pangpang_config_with_values(self):
        """测试加载胖胖配置（包含values）"""
        config = self.loader.load_config("pangpang_bot")
        
        if config:  # 如果配置文件存在
            assert hasattr(config, 'values')
            assert isinstance(config.values, ValuesConfig)
            # 检查胖胖的价值观配置
            assert config.values.dimensions.rationality == 7  # 偏理性
            assert config.values.dimensions.assertiveness == 7  # 更敢表达
            assert len(config.values.stances) >= 1  # 至少有一个立场
            assert config.values.response_preferences.use_humor is True


class TestBackwardCompatibility:
    """测试向后兼容性"""
    
    def setup_method(self):
        """初始化测试"""
        self.loader = BotConfigLoader(bots_dir="bots")
    
    def test_bot_without_values_config(self):
        """测试没有values配置的Bot也能正常加载"""
        # 模拟一个没有values字段的配置
        data = {}
        values = self.loader._parse_values_config(data)
        
        # 应该有默认值
        assert isinstance(values, ValuesConfig)
        assert values.dimensions.rationality == 5
        assert values.stances == []
