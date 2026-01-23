"""
Tests for Agent Skills functionality.

测试Agent的技能相关功能，包括：
- skills property (技能列表)
- skill_keywords property (技能关键词)
- get_skill_description method (获取技能描述)
- can_provide_skill method (判断是否能提供技能)
"""
import pytest
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add src to path for imports
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

# Also add the agents directory to sys.path for importing EmotionalAgent
agents_path = src_path / "agents"
sys.path.insert(0, str(agents_path))

from src.agents.models import Message, ChatContext, AgentResponse
from src.agents.base_agent import BaseAgent


class MockAgentWithSkills(BaseAgent):
    """Mock agent implementation with skills for testing."""
    
    def __init__(self):
        self._skills = ["skill_a", "skill_b", "skill_c"]
        self._skill_keywords = {
            "skill_a": ["keyword1", "keyword2"],
            "skill_b": ["keyword3"],
            "skill_c": ["keyword4", "keyword5", "keyword6"]
        }
        self._skill_descriptions = {
            "skill_a": "技能A的描述",
            "skill_b": "技能B的描述",
            "skill_c": "技能C的描述"
        }
    
    @property
    def name(self) -> str:
        return "MockAgentWithSkills"
    
    @property
    def description(self) -> str:
        return "Mock agent for testing skills functionality"
    
    @property
    def skills(self) -> List[str]:
        return self._skills
    
    @property
    def skill_keywords(self) -> Dict[str, List[str]]:
        return self._skill_keywords
    
    def get_skill_description(self, skill_id: str) -> Optional[str]:
        return self._skill_descriptions.get(skill_id)
    
    def can_handle(self, message: Message, context: ChatContext) -> float:
        return 0.5
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        return AgentResponse(
            content="Mock response",
            agent_name=self.name,
            confidence=0.5
        )
    
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        return {}
    
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        pass


class MockAgentWithoutSkills(BaseAgent):
    """Mock agent implementation without skills (using defaults)."""
    
    @property
    def name(self) -> str:
        return "MockAgentWithoutSkills"
    
    @property
    def description(self) -> str:
        return "Mock agent without skills"
    
    def can_handle(self, message: Message, context: ChatContext) -> float:
        return 0.5
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        return AgentResponse(
            content="Mock response",
            agent_name=self.name,
            confidence=0.5
        )
    
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        return {}
    
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        pass


class TestAgentSkills:
    """Tests for Agent skills functionality."""
    
    def test_agent_with_skills_property(self):
        """Test agent that provides skills list."""
        agent = MockAgentWithSkills()
        
        assert len(agent.skills) == 3
        assert "skill_a" in agent.skills
        assert "skill_b" in agent.skills
        assert "skill_c" in agent.skills
    
    def test_agent_default_skills_is_empty(self):
        """Test that default skills property returns empty list."""
        agent = MockAgentWithoutSkills()
        
        assert agent.skills == []
    
    def test_agent_skill_keywords(self):
        """Test agent skill keywords mapping."""
        agent = MockAgentWithSkills()
        
        keywords = agent.skill_keywords
        assert "skill_a" in keywords
        assert len(keywords["skill_a"]) == 2
        assert "keyword1" in keywords["skill_a"]
    
    def test_agent_default_skill_keywords_is_empty(self):
        """Test that default skill_keywords returns empty dict."""
        agent = MockAgentWithoutSkills()
        
        assert agent.skill_keywords == {}
    
    def test_agent_get_skill_description(self):
        """Test getting skill description."""
        agent = MockAgentWithSkills()
        
        desc = agent.get_skill_description("skill_a")
        assert desc == "技能A的描述"
    
    def test_agent_get_skill_description_not_found(self):
        """Test getting description for non-existent skill."""
        agent = MockAgentWithSkills()
        
        desc = agent.get_skill_description("non_existent")
        assert desc is None
    
    def test_agent_default_get_skill_description(self):
        """Test default get_skill_description returns None."""
        agent = MockAgentWithoutSkills()
        
        desc = agent.get_skill_description("any_skill")
        assert desc is None
    
    def test_agent_can_provide_skill(self):
        """Test can_provide_skill method."""
        agent = MockAgentWithSkills()
        
        assert agent.can_provide_skill("skill_a") is True
        assert agent.can_provide_skill("skill_b") is True
        assert agent.can_provide_skill("non_existent") is False
    
    def test_agent_can_provide_skill_default(self):
        """Test can_provide_skill returns False for empty skills."""
        agent = MockAgentWithoutSkills()
        
        assert agent.can_provide_skill("any_skill") is False


class TestEmotionalAgentSkills:
    """Tests for EmotionalAgent skills implementation."""
    
    def test_emotional_agent_skills(self):
        """Test EmotionalAgent provides correct skills."""
        # Import EmotionalAgent directly
        from agents.emotional_agent import EmotionalAgent
        
        agent = EmotionalAgent()
        
        # Check skills
        assert "emotional_support" in agent.skills
        assert "mood_tracking" in agent.skills
    
    def test_emotional_agent_skill_keywords(self):
        """Test EmotionalAgent skill keywords."""
        from agents.emotional_agent import EmotionalAgent
        
        agent = EmotionalAgent()
        
        keywords = agent.skill_keywords
        assert "emotional_support" in keywords
        assert "mood_tracking" in keywords
        assert "难过" in keywords["emotional_support"]
    
    def test_emotional_agent_skill_description(self):
        """Test EmotionalAgent skill descriptions."""
        from agents.emotional_agent import EmotionalAgent
        
        agent = EmotionalAgent()
        
        desc = agent.get_skill_description("emotional_support")
        assert desc is not None
        assert len(desc) > 0
        
        desc_tracking = agent.get_skill_description("mood_tracking")
        assert desc_tracking is not None
    
    def test_emotional_agent_can_provide_skill(self):
        """Test EmotionalAgent can_provide_skill."""
        from agents.emotional_agent import EmotionalAgent
        
        agent = EmotionalAgent()
        
        assert agent.can_provide_skill("emotional_support") is True
        assert agent.can_provide_skill("mood_tracking") is True
        assert agent.can_provide_skill("tech_help") is False
