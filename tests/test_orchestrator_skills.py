"""
Tests for the Agent Orchestrator and Skills System

测试Agent编排器和技能系统
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.agents.orchestrator import (
    AgentOrchestrator, OrchestratorResult, IntentType, AgentCapability
)
from src.agents.skills import (
    Skill, SkillCategory, SkillRegistry, SkillButtonGenerator,
    skill_registry, register_skill
)
from src.agents import Message, ChatContext, AgentResponse, BaseAgent


class MockAgent(BaseAgent):
    """Mock agent for testing"""
    
    def __init__(self, name: str, confidence: float = 0.5):
        self._name = name
        self._description = f"Mock agent {name}"
        self._confidence = confidence
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    def can_handle(self, message: Message, context: ChatContext) -> float:
        return self._confidence
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        return AgentResponse(
            content=f"Response from {self.name}",
            agent_name=self.name,
            confidence=self._confidence
        )
    
    def memory_read(self, user_id: str) -> dict:
        return {}
    
    def memory_write(self, user_id: str, data: dict) -> None:
        pass


class TestSkill:
    """Test Skill class"""
    
    def test_skill_creation(self):
        """Test basic skill creation"""
        skill = Skill(
            id="test_skill",
            name="Test Skill",
            description="A test skill",
            category=SkillCategory.TOOLS
        )
        
        assert skill.id == "test_skill"
        assert skill.name == "Test Skill"
        assert skill.category == SkillCategory.TOOLS
        assert skill.is_active is True
    
    def test_skill_with_keywords(self):
        """Test skill with keywords"""
        skill = Skill(
            id="coding",
            name="Coding Help",
            description="Help with coding",
            category=SkillCategory.TECH,
            keywords=["code", "python", "javascript"]
        )
        
        assert len(skill.keywords) == 3
        assert "python" in skill.keywords
    
    def test_to_button_data(self):
        """Test converting skill to button data"""
        skill = Skill(
            id="test",
            name="Test",
            description="Test skill",
            icon="🔧"
        )
        
        button = skill.to_button_data()
        
        assert "text" in button
        assert "callback_data" in button
        assert button["callback_data"] == "skill:test"
        assert "🔧" in button["text"]


class TestSkillRegistry:
    """Test SkillRegistry class"""
    
    def test_registry_has_default_skills(self):
        """Test that registry has default skills"""
        # Use the global registry
        skills = skill_registry.get_all()
        
        assert len(skills) >= 3  # At least emotional, tech, tool
    
    def test_register_skill(self):
        """Test registering a new skill"""
        registry = SkillRegistry()
        
        # Registry should have default skills
        initial_count = len(registry.get_all())
        
        # Register a new skill
        registry.register(Skill(
            id="custom_skill",
            name="Custom",
            description="Custom skill"
        ))
        
        assert len(registry.get_all()) == initial_count + 1
        assert registry.get("custom_skill") is not None
    
    def test_unregister_skill(self):
        """Test unregistering a skill"""
        registry = SkillRegistry()
        
        # Register then unregister
        registry.register(Skill(
            id="temp_skill",
            name="Temp",
            description="Temporary"
        ))
        
        result = registry.unregister("temp_skill")
        
        assert result is True
        assert registry.get("temp_skill") is None
    
    def test_get_by_category(self):
        """Test getting skills by category"""
        registry = SkillRegistry()
        
        emotional_skills = registry.get_by_category(SkillCategory.EMOTIONAL)
        
        assert len(emotional_skills) >= 1
        for skill in emotional_skills:
            assert skill.category == SkillCategory.EMOTIONAL
    
    def test_match_skills(self):
        """Test matching skills by text"""
        registry = SkillRegistry()
        
        # Should match emotional agent
        matches = registry.match_skills("我今天很难过，感觉心情不好")
        
        assert len(matches) >= 1
        # First match should be emotional related
        assert matches[0].category == SkillCategory.EMOTIONAL
    
    def test_match_skills_tech(self):
        """Test matching tech skills"""
        registry = SkillRegistry()
        
        # Should match tech agent
        matches = registry.match_skills("帮我看看这个Python代码有什么问题")
        
        assert len(matches) >= 1
        assert matches[0].category == SkillCategory.TECH


class TestSkillButtonGenerator:
    """Test SkillButtonGenerator class"""
    
    def test_generate_main_menu(self):
        """Test generating main menu buttons"""
        generator = SkillButtonGenerator(skill_registry)
        
        buttons = generator.generate_main_menu(columns=2)
        
        assert len(buttons) >= 1
        for row in buttons:
            assert len(row) <= 2
    
    def test_generate_matched_skills(self):
        """Test generating buttons for matched skills"""
        generator = SkillButtonGenerator(skill_registry)
        
        buttons = generator.generate_matched_skills("coding help")
        
        assert len(buttons) >= 1
        # Should have cancel button at the end
        last_row = buttons[-1]
        assert any("cancel" in btn.get("callback_data", "") for btn in last_row)


class TestAgentCapability:
    """Test AgentCapability class"""
    
    def test_capability_creation(self):
        """Test creating an agent capability"""
        cap = AgentCapability(
            name="TestAgent",
            description="A test agent",
            keywords=["test", "mock"],
            is_tool=False
        )
        
        assert cap.name == "TestAgent"
        assert cap.description == "A test agent"
        assert len(cap.keywords) == 2


class TestAgentOrchestrator:
    """Test AgentOrchestrator class"""
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initialization"""
        agents = [
            MockAgent("Agent1", 0.8),
            MockAgent("Agent2", 0.5)
        ]
        
        orchestrator = AgentOrchestrator(agents, llm_provider=None)
        
        assert len(orchestrator.agents) == 2
        assert "Agent1" in orchestrator.agents
        assert "Agent2" in orchestrator.agents
    
    def test_add_agent(self):
        """Test adding an agent to orchestrator"""
        orchestrator = AgentOrchestrator([], llm_provider=None)
        
        orchestrator.add_agent(MockAgent("NewAgent", 0.7))
        
        assert "NewAgent" in orchestrator.agents
    
    def test_remove_agent(self):
        """Test removing an agent from orchestrator"""
        agents = [MockAgent("Agent1", 0.8)]
        orchestrator = AgentOrchestrator(agents, llm_provider=None)
        
        result = orchestrator.remove_agent("Agent1")
        
        assert result is True
        assert "Agent1" not in orchestrator.agents
    
    def test_generate_skill_options(self):
        """Test generating skill options"""
        agents = [
            MockAgent("Agent1", 0.8),
            MockAgent("Agent2", 0.6)
        ]
        orchestrator = AgentOrchestrator(agents, llm_provider=None)
        
        message = Message(content="test message", user_id="123", chat_id="456")
        context = ChatContext(chat_id="456")
        
        options = orchestrator.generate_skill_options(message, context)
        
        assert len(options) >= 1
        for option in options:
            assert "button_text" in option
            assert "callback_data" in option


class TestOrchestratorResult:
    """Test OrchestratorResult class"""
    
    def test_result_creation(self):
        """Test creating an orchestrator result"""
        result = OrchestratorResult(intent_type=IntentType.SINGLE_AGENT)
        
        assert result.intent_type == IntentType.SINGLE_AGENT
        assert result.selected_agents == []
        assert result.final_response == ""
    
    def test_result_with_data(self):
        """Test result with all data"""
        result = OrchestratorResult(
            intent_type=IntentType.MULTI_AGENT,
            selected_agents=["Agent1", "Agent2"],
            final_response="Combined response",
            metadata={"test": "value"}
        )
        
        assert len(result.selected_agents) == 2
        assert result.final_response == "Combined response"
        assert result.metadata["test"] == "value"


class TestIntentType:
    """Test IntentType enum"""
    
    def test_intent_types(self):
        """Test all intent types exist"""
        assert IntentType.DIRECT_RESPONSE == "direct_response"
        assert IntentType.SINGLE_AGENT == "single_agent"
        assert IntentType.MULTI_AGENT == "multi_agent"
        assert IntentType.TOOL_CALL == "tool_call"
        assert IntentType.SKILL_SELECTION == "skill_selection"


@pytest.mark.asyncio
class TestOrchestratorAsync:
    """Async tests for orchestrator"""
    
    async def test_analyze_intent_without_llm(self):
        """Test intent analysis without LLM"""
        agents = [MockAgent("Agent1", 0.8)]
        orchestrator = AgentOrchestrator(agents, llm_provider=None)
        
        message = Message(content="test", user_id="123", chat_id="456")
        context = ChatContext(chat_id="456")
        
        intent, agents_list, metadata = await orchestrator.analyze_intent(message, context)
        
        assert intent in [IntentType.SINGLE_AGENT, IntentType.DIRECT_RESPONSE]
    
    async def test_execute_agents(self):
        """Test executing agents"""
        agents = [MockAgent("Agent1", 0.8)]
        orchestrator = AgentOrchestrator(agents, llm_provider=None)
        
        message = Message(content="test", user_id="123", chat_id="456")
        context = ChatContext(chat_id="456")
        
        responses = await orchestrator.execute_agents(message, context, ["Agent1"])
        
        assert len(responses) == 1
        assert responses[0].agent_name == "Agent1"
    
    async def test_synthesize_response_single(self):
        """Test synthesizing single response"""
        orchestrator = AgentOrchestrator([], llm_provider=None)
        
        message = Message(content="test", user_id="123", chat_id="456")
        responses = [
            AgentResponse(content="Response 1", agent_name="Agent1", confidence=0.8)
        ]
        context = ChatContext(chat_id="456")
        
        result = await orchestrator.synthesize_response(message, responses, context)
        
        assert result == "Response 1"
    
    async def test_synthesize_response_multiple(self):
        """Test synthesizing multiple responses without LLM"""
        orchestrator = AgentOrchestrator([], llm_provider=None)
        
        message = Message(content="test", user_id="123", chat_id="456")
        responses = [
            AgentResponse(content="Response 1", agent_name="Agent1", confidence=0.8),
            AgentResponse(content="Response 2", agent_name="Agent2", confidence=0.6)
        ]
        context = ChatContext(chat_id="456")
        
        result = await orchestrator.synthesize_response(message, responses, context)
        
        assert "Agent1" in result
        assert "Agent2" in result
    
    async def test_process_no_agents(self):
        """Test processing with no agents"""
        orchestrator = AgentOrchestrator([], llm_provider=None)
        
        message = Message(content="test", user_id="123", chat_id="456")
        context = ChatContext(chat_id="456")
        
        result = await orchestrator.process(message, context)
        
        assert result.intent_type == IntentType.DIRECT_RESPONSE
        assert result.final_response != ""
    
    async def test_process_skill_callback(self):
        """Test processing skill callback"""
        agents = [MockAgent("Agent1", 0.8)]
        orchestrator = AgentOrchestrator(agents, llm_provider=None)
        
        message = Message(content="test", user_id="123", chat_id="456")
        context = ChatContext(chat_id="456")
        
        result = await orchestrator.process_skill_callback("Agent1", message, context)
        
        assert result.intent_type == IntentType.SINGLE_AGENT
        assert "Agent1" in result.selected_agents
        assert result.final_response == "Response from Agent1"
