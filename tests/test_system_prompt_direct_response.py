"""
Tests for system_prompt usage in DIRECT_RESPONSE intent type

This test validates that when IntentType.DIRECT_RESPONSE is triggered,
the orchestrator uses the system_prompt from ChatContext.
"""
import pytest
from unittest.mock import AsyncMock, Mock

from src.agents.orchestrator import AgentOrchestrator, IntentType
from src.agents.models import Message, ChatContext


class MockLLMProvider:
    """Mock LLM provider for testing"""
    
    def __init__(self):
        self.last_messages = None
        self.response = "我是测试机器人，来自YAML配置的system_prompt"
    
    async def generate_response(self, messages, context=None):
        """Mock generate_response that captures the messages"""
        self.last_messages = messages
        return self.response


@pytest.mark.asyncio
class TestSystemPromptDirectResponse:
    """Test that system_prompt is used in DIRECT_RESPONSE"""
    
    async def test_direct_response_with_system_prompt(self):
        """Test that DIRECT_RESPONSE uses system_prompt from context"""
        # Create mock LLM provider
        llm_provider = MockLLMProvider()
        
        # Create orchestrator with no agents (to trigger DIRECT_RESPONSE)
        orchestrator = AgentOrchestrator(
            agents=[],
            llm_provider=llm_provider,
            enable_skills=False
        )
        
        # Create message and context with system_prompt
        message = Message(
            content="你是谁",
            user_id="test_user",
            chat_id="test_chat"
        )
        
        system_prompt = "你是小智助手，一个友善的AI助手。"
        context = ChatContext(
            chat_id="test_chat",
            system_prompt=system_prompt
        )
        
        # Process the message
        result = await orchestrator.process(message, context)
        
        # Verify the result
        assert result.intent_type == IntentType.DIRECT_RESPONSE
        assert result.final_response == llm_provider.response
        
        # Verify that system_prompt was included in the messages
        assert llm_provider.last_messages is not None
        assert len(llm_provider.last_messages) == 2
        assert llm_provider.last_messages[0]["role"] == "system"
        assert llm_provider.last_messages[0]["content"] == system_prompt
        assert llm_provider.last_messages[1]["role"] == "user"
        assert llm_provider.last_messages[1]["content"] == "你是谁"
    
    async def test_direct_response_without_system_prompt(self):
        """Test that DIRECT_RESPONSE works without system_prompt"""
        # Create mock LLM provider
        llm_provider = MockLLMProvider()
        
        # Create orchestrator with no agents
        orchestrator = AgentOrchestrator(
            agents=[],
            llm_provider=llm_provider,
            enable_skills=False
        )
        
        # Create message and context WITHOUT system_prompt
        message = Message(
            content="你是谁",
            user_id="test_user",
            chat_id="test_chat"
        )
        
        context = ChatContext(
            chat_id="test_chat",
            system_prompt=None  # No system prompt
        )
        
        # Process the message
        result = await orchestrator.process(message, context)
        
        # Verify the result
        assert result.intent_type == IntentType.DIRECT_RESPONSE
        assert result.final_response == llm_provider.response
        
        # Verify that only user message was included (no system prompt)
        assert llm_provider.last_messages is not None
        assert len(llm_provider.last_messages) == 1
        assert llm_provider.last_messages[0]["role"] == "user"
        assert llm_provider.last_messages[0]["content"] == "你是谁"
    
    async def test_direct_response_with_empty_system_prompt(self):
        """Test that DIRECT_RESPONSE handles empty system_prompt"""
        # Create mock LLM provider
        llm_provider = MockLLMProvider()
        
        # Create orchestrator with no agents
        orchestrator = AgentOrchestrator(
            agents=[],
            llm_provider=llm_provider,
            enable_skills=False
        )
        
        # Create message and context with empty system_prompt
        message = Message(
            content="你是谁",
            user_id="test_user",
            chat_id="test_chat"
        )
        
        context = ChatContext(
            chat_id="test_chat",
            system_prompt=""  # Empty system prompt
        )
        
        # Process the message
        result = await orchestrator.process(message, context)
        
        # Verify the result
        assert result.intent_type == IntentType.DIRECT_RESPONSE
        assert result.final_response == llm_provider.response
        
        # Verify that only user message was included (empty string is falsy)
        assert llm_provider.last_messages is not None
        assert len(llm_provider.last_messages) == 1
        assert llm_provider.last_messages[0]["role"] == "user"
