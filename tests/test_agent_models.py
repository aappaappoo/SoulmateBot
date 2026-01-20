"""
Tests for the multi-agent group chat system core models.
"""
import pytest
from datetime import datetime

from src.agents.models import Message, ChatContext, AgentResponse, MessageType


class TestMessage:
    """Tests for Message model."""
    
    def test_message_creation(self):
        """Test basic message creation."""
        msg = Message(
            content="Hello world",
            user_id="user123",
            chat_id="chat456"
        )
        
        assert msg.content == "Hello world"
        assert msg.user_id == "user123"
        assert msg.chat_id == "chat456"
        assert msg.message_type == MessageType.TEXT
        assert isinstance(msg.timestamp, datetime)
    
    def test_message_with_metadata(self):
        """Test message with metadata."""
        msg = Message(
            content="@TechAgent help me",
            user_id="user123",
            chat_id="chat456",
            metadata={"mentions": ["@TechAgent"]}
        )
        
        assert msg.metadata["mentions"] == ["@TechAgent"]
    
    def test_has_mention(self):
        """Test mention detection."""
        msg = Message(
            content="@TechAgent help me",
            user_id="user123",
            chat_id="chat456",
            metadata={"mentions": ["@TechAgent"]}
        )
        
        assert msg.has_mention("TechAgent") is True
        assert msg.has_mention("EmotionalAgent") is False
    
    def test_get_clean_content(self):
        """Test cleaning mentions from content."""
        msg = Message(
            content="@TechAgent help me with Python",
            user_id="user123",
            chat_id="chat456",
            metadata={"mentions": ["@TechAgent"]}
        )
        
        clean = msg.get_clean_content()
        assert "@TechAgent" not in clean
        assert "help me with Python" in clean


class TestChatContext:
    """Tests for ChatContext model."""
    
    def test_context_creation(self):
        """Test basic context creation."""
        ctx = ChatContext(chat_id="chat123")
        
        assert ctx.chat_id == "chat123"
        assert len(ctx.conversation_history) == 0
        assert len(ctx.active_users) == 0
    
    def test_add_message(self):
        """Test adding messages to context."""
        ctx = ChatContext(chat_id="chat123")
        msg = Message(content="Hello", user_id="user1", chat_id="chat123")
        
        ctx.add_message(msg)
        
        assert len(ctx.conversation_history) == 1
        assert ctx.conversation_history[0] == msg
    
    def test_message_history_limit(self):
        """Test that history is limited to 50 messages."""
        ctx = ChatContext(chat_id="chat123")
        
        # Add 60 messages
        for i in range(60):
            msg = Message(content=f"Message {i}", user_id="user1", chat_id="chat123")
            ctx.add_message(msg)
        
        # Should only keep last 50
        assert len(ctx.conversation_history) == 50
        assert ctx.conversation_history[0].content == "Message 10"
        assert ctx.conversation_history[-1].content == "Message 59"
    
    def test_get_recent_messages(self):
        """Test getting recent messages."""
        ctx = ChatContext(chat_id="chat123")
        
        for i in range(20):
            msg = Message(content=f"Message {i}", user_id="user1", chat_id="chat123")
            ctx.add_message(msg)
        
        recent = ctx.get_recent_messages(5)
        
        assert len(recent) == 5
        assert recent[0].content == "Message 15"
        assert recent[-1].content == "Message 19"


class TestAgentResponse:
    """Tests for AgentResponse model."""
    
    def test_response_creation(self):
        """Test basic response creation."""
        response = AgentResponse(
            content="Hello, I can help!",
            agent_name="TechAgent",
            confidence=0.85
        )
        
        assert response.content == "Hello, I can help!"
        assert response.agent_name == "TechAgent"
        assert response.confidence == 0.85
        assert response.should_continue is False
    
    def test_confidence_validation(self):
        """Test confidence score validation."""
        # Valid confidence
        response = AgentResponse(
            content="Test",
            agent_name="TestAgent",
            confidence=0.5
        )
        assert response.confidence == 0.5
        
        # Invalid confidence (too high)
        with pytest.raises(ValueError):
            AgentResponse(
                content="Test",
                agent_name="TestAgent",
                confidence=1.5
            )
        
        # Invalid confidence (negative)
        with pytest.raises(ValueError):
            AgentResponse(
                content="Test",
                agent_name="TestAgent",
                confidence=-0.1
            )
    
    def test_response_with_metadata(self):
        """Test response with metadata."""
        response = AgentResponse(
            content="Debug info",
            agent_name="TechAgent",
            confidence=0.9,
            metadata={"language": "python", "topic": "debugging"}
        )
        
        assert response.metadata["language"] == "python"
        assert response.metadata["topic"] == "debugging"
