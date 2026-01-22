"""
Tests for the Group Monitor Agent

测试群组监控Agent
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from agents.group_monitor_agent import GroupMonitorAgent
from src.agents import Message, ChatContext, InMemoryStore


class TestGroupMonitorAgent:
    """Test GroupMonitorAgent class"""
    
    @pytest.fixture
    def agent(self):
        """Create a test agent with in-memory storage"""
        return GroupMonitorAgent(memory_store=InMemoryStore())
    
    @pytest.fixture
    def message(self):
        """Create a test message"""
        return Message(
            content="监控这个群组 https://t.me/test_group",
            user_id="123",
            chat_id="456"
        )
    
    @pytest.fixture
    def context(self):
        """Create a test context"""
        return ChatContext(chat_id="456")
    
    def test_agent_initialization(self, agent):
        """Test agent initialization"""
        assert agent.name == "GroupMonitorAgent"
        assert "监控" in agent.description or "monitor" in agent.description.lower()
    
    def test_can_handle_with_mention(self, agent, context):
        """Test can_handle with explicit mention"""
        message = Message(
            content="@GroupMonitorAgent 帮我监控群组",
            user_id="123",
            chat_id="456",
            metadata={"mentions": ["@GroupMonitorAgent"]}
        )
        
        confidence = agent.can_handle(message, context)
        
        assert confidence == 1.0
    
    def test_can_handle_with_group_link(self, agent, context):
        """Test can_handle with group link and monitor intent"""
        message = Message(
            content="监控这个群组 https://t.me/test_group",
            user_id="123",
            chat_id="456"
        )
        
        confidence = agent.can_handle(message, context)
        
        assert confidence >= 0.9
    
    def test_can_handle_with_keywords(self, agent, context):
        """Test can_handle with monitor keywords"""
        message = Message(
            content="帮我分析这个群的讨论",
            user_id="123",
            chat_id="456"
        )
        
        confidence = agent.can_handle(message, context)
        
        assert confidence >= 0.5
    
    def test_can_handle_low_confidence(self, agent, context):
        """Test can_handle with irrelevant content"""
        message = Message(
            content="我喜欢吃苹果",
            user_id="123",
            chat_id="456"
        )
        
        confidence = agent.can_handle(message, context)
        
        assert confidence <= 0.5
    
    def test_respond_start_monitor(self, agent, context):
        """Test response for start monitor request"""
        message = Message(
            content="开始监控 https://t.me/test_group",
            user_id="123",
            chat_id="456"
        )
        
        response = agent.respond(message, context)
        
        assert response.agent_name == "GroupMonitorAgent"
        assert "t.me/test_group" in response.content
        assert response.metadata.get("action") == "start_monitor"
    
    def test_respond_without_group_link(self, agent, context):
        """Test response when no group link provided"""
        message = Message(
            content="开始监控群组",
            user_id="123",
            chat_id="456"
        )
        
        response = agent.respond(message, context)
        
        assert "链接" in response.content or "格式" in response.content
    
    def test_respond_generate_summary(self, agent, context):
        """Test response for summary request"""
        message = Message(
            content="总结群组讨论 https://t.me/test_group",
            user_id="123",
            chat_id="456"
        )
        
        response = agent.respond(message, context)
        
        assert response.metadata.get("action") == "generate_summary"
        assert "分析" in response.content or "总结" in response.content
    
    def test_respond_check_status(self, agent, context):
        """Test response for status check"""
        message = Message(
            content="status",  # Use English keyword for clearer test
            user_id="123",
            chat_id="456"
        )
        
        response = agent.respond(message, context)
        
        assert response.metadata.get("action") == "check_status"
    
    def test_respond_general_first_interaction(self, agent, context):
        """Test response for first interaction"""
        message = Message(
            content="你好",
            user_id="123",
            chat_id="456"
        )
        
        response = agent.respond(message, context)
        
        assert response.metadata.get("action") == "general"
        # Should contain introduction
        assert "群组" in response.content or "监控" in response.content
    
    def test_memory_persistence(self, agent, context):
        """Test that agent remembers interactions"""
        message = Message(
            content="查看状态",
            user_id="user_123",
            chat_id="456"
        )
        
        # First interaction
        agent.respond(message, context)
        
        # Check memory was updated
        memory = agent.memory_read("user_123")
        
        assert memory.get("interaction_count") == 1
        assert memory.get("last_action") is not None
    
    def test_extract_group_link(self, agent):
        """Test group link extraction"""
        # Full URL
        link = agent._extract_group_link("监控 https://t.me/test_group")
        assert link == "https://t.me/test_group"
        
        # Short format
        link = agent._extract_group_link("监控 t.me/another_group")
        assert link == "https://t.me/another_group"
        
        # No link
        link = agent._extract_group_link("监控群组")
        assert link is None
    
    def test_respond_stop_monitor(self, agent, context):
        """Test response for stop monitor request"""
        message = Message(
            content="stop",  # Use English keyword for clearer test
            user_id="123",
            chat_id="456"
        )
        
        response = agent.respond(message, context)
        
        assert response.metadata.get("action") == "stop_monitor"


class TestGroupMonitorAgentIntegration:
    """Integration tests for group monitor agent"""
    
    def test_full_workflow(self):
        """Test a complete monitoring workflow"""
        agent = GroupMonitorAgent(memory_store=InMemoryStore())
        context = ChatContext(chat_id="456")
        user_id = "workflow_user"
        
        # Step 1: Initial greeting
        message1 = Message(content="你好", user_id=user_id, chat_id="456")
        response1 = agent.respond(message1, context)
        assert response1.content != ""
        
        # Step 2: Request to start monitoring
        message2 = Message(
            content="监控 https://t.me/crypto_chat",
            user_id=user_id,
            chat_id="456"
        )
        response2 = agent.respond(message2, context)
        assert "crypto_chat" in response2.content
        
        # Step 3: Check status
        message3 = Message(content="状态", user_id=user_id, chat_id="456")
        response3 = agent.respond(message3, context)
        assert response3.metadata.get("action") == "check_status"
        
        # Verify memory has been updated
        memory = agent.memory_read(user_id)
        assert memory.get("interaction_count") == 3
        assert memory.get("last_group_link") == "https://t.me/crypto_chat"
