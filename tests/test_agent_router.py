"""
Tests for the Router component.
"""
import pytest
from src.agents import Router, RouterConfig, Message, ChatContext, AgentResponse
from src.agents.base_agent import BaseAgent
from typing import Dict, Any


class MockAgent(BaseAgent):
    """Mock agent for testing."""
    
    def __init__(self, name: str, description: str, confidence_func=None):
        self._name = name
        self._description = description
        self._confidence_func = confidence_func or (lambda m, c: 0.5)
        self._memory = {}
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    def can_handle(self, message: Message, context: ChatContext) -> float:
        return self._confidence_func(message, context)
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        return AgentResponse(
            content=f"Response from {self.name}",
            agent_name=self.name,
            confidence=self._confidence_func(message, context),
            should_continue=True  # Allow multiple agents to respond
        )
    
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        return self._memory.get(user_id, {})
    
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        self._memory[user_id] = data


class TestRouterConfig:
    """Tests for RouterConfig."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = RouterConfig()
        
        assert config.min_confidence == 0.5
        assert config.max_agents == 1
        assert config.exclusive_mention is True
        assert config.enable_parallel is False
        assert config.cooldown_seconds == 0.0
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = RouterConfig(
            min_confidence=0.7,
            max_agents=3,
            exclusive_mention=False,
            enable_parallel=True,
            cooldown_seconds=5.0
        )
        
        assert config.min_confidence == 0.7
        assert config.max_agents == 3
        assert config.exclusive_mention is False
        assert config.enable_parallel is True
        assert config.cooldown_seconds == 5.0
    
    def test_invalid_confidence(self):
        """Test validation of confidence threshold."""
        with pytest.raises(ValueError):
            RouterConfig(min_confidence=1.5)
        
        with pytest.raises(ValueError):
            RouterConfig(min_confidence=-0.1)
    
    def test_invalid_max_agents(self):
        """Test validation of max_agents."""
        with pytest.raises(ValueError):
            RouterConfig(max_agents=0)


class TestRouter:
    """Tests for Router."""
    
    def test_router_initialization(self):
        """Test router initialization."""
        agent1 = MockAgent("Agent1", "Test agent 1")
        agent2 = MockAgent("Agent2", "Test agent 2")
        
        router = Router([agent1, agent2])
        
        assert len(router.agents) == 2
        assert "Agent1" in router.agents
        assert "Agent2" in router.agents
    
    def test_add_agent(self):
        """Test adding agents dynamically."""
        router = Router([])
        agent = MockAgent("TestAgent", "Test")
        
        router.add_agent(agent)
        
        assert "TestAgent" in router.agents
        assert len(router.agents) == 1
    
    def test_remove_agent(self):
        """Test removing agents."""
        agent = MockAgent("TestAgent", "Test")
        router = Router([agent])
        
        result = router.remove_agent("TestAgent")
        
        assert result is True
        assert "TestAgent" not in router.agents
        
        # Try removing non-existent agent
        result = router.remove_agent("NonExistent")
        assert result is False
    
    def test_extract_mentions(self):
        """Test mention extraction."""
        agent1 = MockAgent("Agent1", "Test")
        agent2 = MockAgent("Agent2", "Test")
        router = Router([agent1, agent2])
        
        # Test with @mention in content
        msg = Message(
            content="@Agent1 help me please",
            user_id="user1",
            chat_id="chat1"
        )
        mentions = router.extract_mentions(msg)
        assert "Agent1" in mentions
        
        # Test with mention in metadata
        msg = Message(
            content="help me please",
            user_id="user1",
            chat_id="chat1",
            metadata={"mentions": ["@Agent2"]}
        )
        mentions = router.extract_mentions(msg)
        assert "Agent2" in mentions
    
    def test_select_agents_by_confidence(self):
        """Test agent selection by confidence score."""
        # Create agents with different confidence levels
        high_conf_agent = MockAgent("HighAgent", "High", lambda m, c: 0.9)
        medium_conf_agent = MockAgent("MediumAgent", "Medium", lambda m, c: 0.6)
        low_conf_agent = MockAgent("LowAgent", "Low", lambda m, c: 0.3)
        
        config = RouterConfig(min_confidence=0.5, max_agents=2)
        router = Router([high_conf_agent, medium_conf_agent, low_conf_agent], config)
        
        msg = Message(content="test message", user_id="user1", chat_id="chat1")
        ctx = ChatContext(chat_id="chat1")
        
        selected = router.select_agents(msg, ctx)
        
        # Should select top 2 agents above threshold
        assert len(selected) == 2
        assert selected[0][0].name == "HighAgent"
        assert selected[0][1] == 0.9
        assert selected[1][0].name == "MediumAgent"
        assert selected[1][1] == 0.6
    
    def test_exclusive_mention_mode(self):
        """Test exclusive mention mode."""
        agent1 = MockAgent("Agent1", "Test", lambda m, c: 0.9)
        agent2 = MockAgent("Agent2", "Test", lambda m, c: 0.8)
        
        config = RouterConfig(exclusive_mention=True)
        router = Router([agent1, agent2], config)
        
        msg = Message(
            content="@Agent2 help me",
            user_id="user1",
            chat_id="chat1"
        )
        ctx = ChatContext(chat_id="chat1")
        
        selected = router.select_agents(msg, ctx)
        
        # Should only select mentioned agent
        assert len(selected) == 1
        assert selected[0][0].name == "Agent2"
        assert selected[0][1] == 1.0  # Full confidence for explicit mention
    
    def test_max_agents_limit(self):
        """Test max_agents configuration."""
        agents = [
            MockAgent(f"Agent{i}", f"Test {i}", lambda m, c: 0.8)
            for i in range(5)
        ]
        
        config = RouterConfig(min_confidence=0.5, max_agents=2)
        router = Router(agents, config)
        
        msg = Message(content="test", user_id="user1", chat_id="chat1")
        ctx = ChatContext(chat_id="chat1")
        
        selected = router.select_agents(msg, ctx)
        
        assert len(selected) <= 2
    
    def test_fallback_agent(self):
        """Test fallback agent when no agents meet threshold."""
        fallback = MockAgent("FallbackAgent", "Fallback", lambda m, c: 0.3)
        low_conf = MockAgent("LowAgent", "Low", lambda m, c: 0.2)
        
        config = RouterConfig(
            min_confidence=0.5,
            fallback_agent_name="FallbackAgent"
        )
        router = Router([fallback, low_conf], config)
        
        msg = Message(content="test", user_id="user1", chat_id="chat1")
        ctx = ChatContext(chat_id="chat1")
        
        selected = router.select_agents(msg, ctx)
        
        # Should use fallback agent
        assert len(selected) == 1
        assert selected[0][0].name == "FallbackAgent"
    
    def test_route_synchronous(self):
        """Test synchronous routing."""
        agent = MockAgent("TestAgent", "Test", lambda m, c: 0.8)
        router = Router([agent])
        
        msg = Message(content="test message", user_id="user1", chat_id="chat1")
        ctx = ChatContext(chat_id="chat1")
        
        responses = router.route(msg, ctx)
        
        assert len(responses) == 1
        assert responses[0].agent_name == "TestAgent"
        assert "Response from TestAgent" in responses[0].content
    
    def test_route_with_no_qualifying_agents(self):
        """Test routing when no agents qualify."""
        agent = MockAgent("TestAgent", "Test", lambda m, c: 0.2)
        config = RouterConfig(min_confidence=0.5)
        router = Router([agent], config)
        
        msg = Message(content="test", user_id="user1", chat_id="chat1")
        ctx = ChatContext(chat_id="chat1")
        
        responses = router.route(msg, ctx)
        
        assert len(responses) == 0
    
    def test_response_ordering(self):
        """Test that responses are ordered by confidence."""
        agent1 = MockAgent("Agent1", "Test", lambda m, c: 0.7)
        agent2 = MockAgent("Agent2", "Test", lambda m, c: 0.9)
        agent3 = MockAgent("Agent3", "Test", lambda m, c: 0.6)
        
        config = RouterConfig(min_confidence=0.5, max_agents=3)
        router = Router([agent1, agent2, agent3], config)
        
        msg = Message(content="test", user_id="user1", chat_id="chat1")
        ctx = ChatContext(chat_id="chat1")
        
        responses = router.route(msg, ctx)
        
        assert len(responses) == 3
        # Should be sorted by confidence (highest first)
        assert responses[0].agent_name == "Agent2"  # 0.9
        assert responses[1].agent_name == "Agent1"  # 0.7
        assert responses[2].agent_name == "Agent3"  # 0.6
