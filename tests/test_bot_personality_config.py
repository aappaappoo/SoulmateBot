"""
Tests for the Bot Personality Configuration.

测试Bot的人格配置，包括：
- 性格特点 (character, traits)
- 外貌特征 (appearance)
- 口头禅 (catchphrases)
- 理想和人生规划 (ideals, life_goals)
- 爱好和讨厌点 (likes, dislikes)
- 居住环境 (living_environment)
- 技能配置 (skills)
"""
import pytest
import tempfile
import shutil
import sys
from pathlib import Path
import importlib.util

# Add src to path for imports
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

# Import yaml directly
import yaml

# Import config loader classes using importlib.util to avoid telegram dependency in __init__.py
_config_loader_path = src_path / "src" / "bot" / "config_loader.py"
_spec = importlib.util.spec_from_file_location("config_loader", _config_loader_path)
config_loader_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(config_loader_module)

# Import classes from the loaded module
BotConfigLoader = config_loader_module.BotConfigLoader
BotConfig = config_loader_module.BotConfig
PersonalityConfig = config_loader_module.PersonalityConfig
AppearanceConfig = config_loader_module.AppearanceConfig
SkillsConfig = config_loader_module.SkillsConfig
SkillConfig = config_loader_module.SkillConfig


class TestPersonalityConfig:
    """Tests for PersonalityConfig model."""
    
    def test_personality_config_creation(self):
        """Test basic personality config creation."""
        personality = PersonalityConfig(
            character="一个温暖的陪伴者",
            traits=["温柔", "耐心", "共情"],
        )
        
        assert personality.character == "一个温暖的陪伴者"
        assert len(personality.traits) == 3
        assert "温柔" in personality.traits
    
    def test_personality_with_appearance(self):
        """Test personality config with appearance."""
        appearance = AppearanceConfig(
            avatar="温暖的笑容",
            physical_description="25岁的年轻人",
            style="简约舒适",
            distinctive_features=["温暖的笑容", "专注的眼神"]
        )
        
        personality = PersonalityConfig(
            character="温暖的陪伴者",
            appearance=appearance
        )
        
        assert personality.appearance.avatar == "温暖的笑容"
        assert personality.appearance.physical_description == "25岁的年轻人"
        assert len(personality.appearance.distinctive_features) == 2
    
    def test_personality_with_catchphrases(self):
        """Test personality config with catchphrases."""
        personality = PersonalityConfig(
            character="温暖的陪伴者",
            catchphrases=["我在这里", "慢慢说", "你很棒"]
        )
        
        assert len(personality.catchphrases) == 3
        assert "我在这里" in personality.catchphrases
    
    def test_personality_with_ideals_and_goals(self):
        """Test personality config with ideals and life goals."""
        personality = PersonalityConfig(
            character="温暖的陪伴者",
            ideals="成为心灵的避风港",
            life_goals=["倾听心声", "传递温暖", "帮助他人"]
        )
        
        assert personality.ideals == "成为心灵的避风港"
        assert len(personality.life_goals) == 3
        assert "传递温暖" in personality.life_goals
    
    def test_personality_with_likes_dislikes(self):
        """Test personality config with likes and dislikes."""
        personality = PersonalityConfig(
            character="温暖的陪伴者",
            likes=["安静的交流", "真诚的表达"],
            dislikes=["敷衍的对话", "情感操控"]
        )
        
        assert len(personality.likes) == 2
        assert len(personality.dislikes) == 2
        assert "真诚的表达" in personality.likes
        assert "情感操控" in personality.dislikes
    
    def test_personality_with_living_environment(self):
        """Test personality config with living environment."""
        personality = PersonalityConfig(
            character="温暖的陪伴者",
            living_environment="一个温馨的小房间"
        )
        
        assert personality.living_environment == "一个温馨的小房间"


class TestSkillsConfig:
    """Tests for SkillsConfig model."""
    
    def test_skills_config_creation(self):
        """Test basic skills config creation."""
        skills = SkillsConfig(
            enabled=[
                SkillConfig(
                    id="emotional_support",
                    name="情感支持",
                    description="情感陪伴和支持",
                    agent_name="EmotionalAgent"
                )
            ],
            default_skill="emotional_support"
        )
        
        assert len(skills.enabled) == 1
        assert skills.default_skill == "emotional_support"
    
    def test_skill_config_defaults(self):
        """Test skill config default values."""
        skill = SkillConfig(
            id="test_skill",
            name="测试技能"
        )
        
        assert skill.enabled is True
        assert skill.priority == 0
        assert skill.agent_name is None
        assert skill.description == ""
    
    def test_multiple_skills(self):
        """Test config with multiple skills."""
        skills = SkillsConfig(
            enabled=[
                SkillConfig(id="skill1", name="技能1", priority=10),
                SkillConfig(id="skill2", name="技能2", priority=5),
                SkillConfig(id="skill3", name="技能3", priority=1)
            ],
            default_skill="skill1"
        )
        
        assert len(skills.enabled) == 3
        # Check priorities
        priorities = [s.priority for s in skills.enabled]
        assert priorities == [10, 5, 1]


class TestBotConfigLoader:
    """Tests for BotConfigLoader with new personality fields."""
    
    def setup_method(self):
        """Create a temporary bots directory for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.bots_dir = Path(self.temp_dir) / "bots"
        self.bots_dir.mkdir()
    
    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)
    
    def _create_bot_config(self, bot_id: str, config_data: dict):
        """Helper to create a bot config file."""
        bot_dir = self.bots_dir / bot_id
        bot_dir.mkdir()
        
        config_path = bot_dir / "config.yaml"
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True)
    
    def test_load_bot_with_full_personality(self):
        """Test loading bot config with full personality configuration."""
        config_data = {
            "bot": {
                "name": "test_bot",
                "description": "测试机器人"
            },
            "personality": {
                "character": "温暖的陪伴者",
                "traits": ["温柔", "耐心"],
                "appearance": {
                    "avatar": "温暖的笑容",
                    "physical_description": "25岁的年轻人",
                    "style": "简约",
                    "distinctive_features": ["笑容", "眼神"]
                },
                "catchphrases": ["我在这里", "慢慢说"],
                "ideals": "成为心灵避风港",
                "life_goals": ["倾听心声", "传递温暖"],
                "likes": ["安静", "真诚"],
                "dislikes": ["敷衍", "操控"],
                "living_environment": "温馨小房间"
            }
        }
        
        self._create_bot_config("test_bot", config_data)
        
        loader = BotConfigLoader(str(self.bots_dir))
        config = loader.load_config("test_bot")
        
        assert config is not None
        assert config.name == "test_bot"
        
        # Verify personality
        assert config.personality.character == "温暖的陪伴者"
        assert len(config.personality.traits) == 2
        assert config.personality.appearance.avatar == "温暖的笑容"
        assert len(config.personality.catchphrases) == 2
        assert config.personality.ideals == "成为心灵避风港"
        assert len(config.personality.life_goals) == 2
        assert len(config.personality.likes) == 2
        assert len(config.personality.dislikes) == 2
        assert config.personality.living_environment == "温馨小房间"
    
    def test_load_bot_with_skills(self):
        """Test loading bot config with skills configuration."""
        config_data = {
            "bot": {
                "name": "skill_bot",
                "description": "技能机器人"
            },
            "skills": {
                "enabled": [
                    {
                        "id": "emotional_support",
                        "name": "情感支持",
                        "description": "提供情感陪伴",
                        "agent_name": "EmotionalAgent",
                        "priority": 10
                    },
                    {
                        "id": "daily_companion",
                        "name": "日常陪伴",
                        "priority": 5
                    }
                ],
                "default_skill": "emotional_support"
            }
        }
        
        self._create_bot_config("skill_bot", config_data)
        
        loader = BotConfigLoader(str(self.bots_dir))
        config = loader.load_config("skill_bot")
        
        assert config is not None
        assert len(config.skills.enabled) == 2
        assert config.skills.default_skill == "emotional_support"
        
        # Verify first skill
        first_skill = config.skills.enabled[0]
        assert first_skill.id == "emotional_support"
        assert first_skill.agent_name == "EmotionalAgent"
        assert first_skill.priority == 10
    
    def test_load_bot_with_empty_personality(self):
        """Test loading bot config with no personality (uses defaults)."""
        config_data = {
            "bot": {
                "name": "minimal_bot",
                "description": "极简机器人"
            }
        }
        
        self._create_bot_config("minimal_bot", config_data)
        
        loader = BotConfigLoader(str(self.bots_dir))
        config = loader.load_config("minimal_bot")
        
        assert config is not None
        assert config.name == "minimal_bot"
        
        # Verify default personality values
        assert config.personality.character == ""
        assert config.personality.traits == []
        assert config.personality.catchphrases == []
        assert config.personality.likes == []
        assert config.personality.dislikes == []
    
    def test_load_solin_bot_config(self):
        """Test loading actual solin_bot configuration."""
        # Use the actual bots directory
        loader = BotConfigLoader("bots")
        config = loader.load_config("solin_bot")
        
        assert config is not None
        assert config.name == "solin_bot"
        
        # Verify personality fields are loaded
        assert config.personality.character != ""
        assert len(config.personality.traits) > 0
        assert len(config.personality.catchphrases) > 0
        assert len(config.personality.likes) > 0
        assert len(config.personality.dislikes) > 0
        assert config.personality.living_environment != ""
        
        # Verify skills are loaded
        assert len(config.skills.enabled) > 0
        assert config.skills.default_skill is not None
