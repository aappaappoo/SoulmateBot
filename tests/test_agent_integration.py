"""
Integration tests for the complete multi-agent system.

Tests the full flow from message input to agent responses.
"""
import pytest
from src.agents import (
    Router,
    RouterConfig,
    AgentLoader,
    Message,
    ChatContext,
    MessageType,
)


class TestIntegration:
    """Integration tests for the multi-agent system."""
    
    def test_load_example_agents(self):
        """Test loading the example agents (EmotionalAgent, TechAgent)."""
        loader = AgentLoader(agents_dir="agents")
        agents = loader.load_agents(instantiate=True)
        
        # Should load at least EmotionalAgent and TechAgent
        assert len(agents) >= 2
        
        agent_names = [agent.name for agent in agents]
        assert "EmotionalAgent" in agent_names
        assert "TechAgent" in agent_names
    
    def test_emotional_message_routing(self):
        """Test that emotional messages route to EmotionalAgent."""
        loader = AgentLoader(agents_dir="agents")
        agents = loader.load_agents(instantiate=True)
        
        config = RouterConfig(min_confidence=0.4)
        router = Router(agents, config)
        
        # Create an emotional message
        message = Message(
            content="I'm feeling really sad and lonely today",
            user_id="user123",
            chat_id="chat456",
            message_type=MessageType.TEXT
        )
        context = ChatContext(chat_id="chat456")
        
        # Route the message
        responses = router.route(message, context)
        
        # Should get at least one response
        assert len(responses) > 0
        
        # The emotional agent should have high confidence
        for response in responses:
            if response.agent_name == "EmotionalAgent":
                assert response.confidence >= 0.4
                assert len(response.content) > 0
                break
        else:
            pytest.fail("EmotionalAgent did not respond to emotional message")
    
    def test_technical_message_routing(self):
        """Test that technical messages route to TechAgent."""
        loader = AgentLoader(agents_dir="agents")
        agents = loader.load_agents(instantiate=True)
        
        config = RouterConfig(min_confidence=0.4)
        router = Router(agents, config)
        
        # Create a technical message
        message = Message(
            content="How do I fix a Python import error?",
            user_id="user123",
            chat_id="chat456",
            message_type=MessageType.TEXT
        )
        context = ChatContext(chat_id="chat456")
        
        # Route the message
        responses = router.route(message, context)
        
        # Should get at least one response
        assert len(responses) > 0
        
        # The tech agent should have high confidence
        for response in responses:
            if response.agent_name == "TechAgent":
                assert response.confidence >= 0.4
                assert len(response.content) > 0
                break
        else:
            pytest.fail("TechAgent did not respond to technical message")
    
    def test_explicit_mention_routing(self):
        """Test that @mentions route to specific agents."""
        loader = AgentLoader(agents_dir="agents")
        agents = loader.load_agents(instantiate=True)
        
        config = RouterConfig(exclusive_mention=True)
        router = Router(agents, config)
        
        # Mention TechAgent explicitly
        message = Message(
            content="@TechAgent I'm feeling sad but need Python help",
            user_id="user123",
            chat_id="chat456",
            message_type=MessageType.TEXT
        )
        context = ChatContext(chat_id="chat456")
        
        # Route the message
        responses = router.route(message, context)
        
        # Should only get response from TechAgent
        assert len(responses) == 1
        assert responses[0].agent_name == "TechAgent"
    
    def test_conversation_context(self):
        """Test that agents can use conversation context."""
        loader = AgentLoader(agents_dir="agents")
        agents = loader.load_agents(instantiate=True)
        
        router = Router(agents, RouterConfig(min_confidence=0.4))
        
        context = ChatContext(chat_id="chat456")
        
        # First message about Python
        msg1 = Message(
            content="I need help with Python programming",
            user_id="user123",
            chat_id="chat456"
        )
        context.add_message(msg1)
        responses1 = router.route(msg1, context)
        
        # Should get response from TechAgent
        assert len(responses1) > 0
        assert any(r.agent_name == "TechAgent" for r in responses1)
        
        # Add response to context
        if responses1:
            for resp in responses1:
                resp_msg = Message(
                    content=resp.content,
                    user_id=f"agent_{resp.agent_name}",
                    chat_id="chat456"
                )
                context.add_message(resp_msg)
        
        # Second message with technical follow-up
        msg2 = Message(
            content="Can you explain more about Python functions?",
            user_id="user123",
            chat_id="chat456"
        )
        context.add_message(msg2)
        responses2 = router.route(msg2, context)
        
        # Should still route to TechAgent
        assert len(responses2) > 0
        assert any(r.agent_name == "TechAgent" for r in responses2)
    
    def test_agent_memory_persistence(self):
        """Test that agents persist memory across interactions."""
        loader = AgentLoader(agents_dir="agents")
        agents = loader.load_agents(instantiate=True)
        
        # Find EmotionalAgent
        emotional_agent = None
        for agent in agents:
            if agent.name == "EmotionalAgent":
                emotional_agent = agent
                break
        
        assert emotional_agent is not None
        
        # First interaction
        msg1 = Message(
            content="I'm feeling sad",
            user_id="user123",
            chat_id="chat456"
        )
        ctx1 = ChatContext(chat_id="chat456")
        
        response1 = emotional_agent.respond(msg1, ctx1)
        
        # Check that memory was updated
        memory = emotional_agent.memory_read("user123")
        assert "interaction_count" in memory
        assert memory["interaction_count"] >= 1
        
        # Second interaction
        msg2 = Message(
            content="Still feeling down",
            user_id="user123",
            chat_id="chat456"
        )
        ctx2 = ChatContext(chat_id="chat456")
        
        response2 = emotional_agent.respond(msg2, ctx2)
        
        # Memory should be updated
        memory2 = emotional_agent.memory_read("user123")
        assert memory2["interaction_count"] > memory["interaction_count"]
    
    def test_multi_user_isolation(self):
        """Test that different users have isolated memory."""
        loader = AgentLoader(agents_dir="agents")
        agents = loader.load_agents(instantiate=True)
        
        emotional_agent = None
        for agent in agents:
            if agent.name == "EmotionalAgent":
                emotional_agent = agent
                break
        
        assert emotional_agent is not None
        
        # User 1 interaction
        msg1 = Message(content="I'm sad", user_id="user1", chat_id="chat1")
        ctx1 = ChatContext(chat_id="chat1")
        emotional_agent.respond(msg1, ctx1)
        
        # User 2 interaction
        msg2 = Message(content="I'm happy", user_id="user2", chat_id="chat2")
        ctx2 = ChatContext(chat_id="chat2")
        emotional_agent.respond(msg2, ctx2)
        
        # Check memories are separate
        memory1 = emotional_agent.memory_read("user1")
        memory2 = emotional_agent.memory_read("user2")
        
        assert memory1.get("last_emotion") == "sadness"
        assert memory2.get("last_emotion") == "happiness"
