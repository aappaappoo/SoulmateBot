"""
Tests for emotion extraction in Agent Orchestrator
测试Agent编排器中的情感提取功能
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
import json

from src.agents.orchestrator import (
    AgentOrchestrator, OrchestratorResult, IntentType, IntentSource, MemoryAnalysis
)
from src.agents import Message, ChatContext, BaseAgent


class MockLLMProvider:
    """Mock LLM provider for testing"""
    
    def __init__(self, response_json):
        self.response_json = response_json
    
    async def generate_response(self, messages, context=None):
        """Return a mock JSON response"""
        return f"```json\n{json.dumps(self.response_json)}\n```"


class TestOrchestratorEmotion:
    """测试编排器的情感提取功能"""
    
    @pytest.mark.asyncio
    async def test_emotion_extraction_happy(self):
        """测试提取happy情感"""
        # Mock LLM response with happy emotion
        llm_response = {
            "intent": "direct_response",
            "agents": [],
            "reasoning": "用户在打招呼，直接回复即可",
            "direct_reply": "（语气：开心、轻快）你好啊！",
            "emotion": "happy",
            "memory": {
                "is_important": False,
                "importance_level": None,
                "event_type": None,
                "event_summary": None,
                "keywords": [],
                "event_date": None,
                "raw_date_expression": None
            }
        }
        
        llm_provider = MockLLMProvider(llm_response)
        orchestrator = AgentOrchestrator([], llm_provider=llm_provider, enable_unified_mode=True)
        
        message = Message(content="你好", user_id="123", chat_id="456")
        context = ChatContext(chat_id="456", system_prompt="你是一个友好的助手")
        
        intent, agents, metadata, source, reply, memory = await orchestrator.analyze_intent_unified(message, context)
        
        # 验证情感被正确提取
        assert metadata.get("emotion") == "happy"
        assert source == IntentSource.LLM_UNIFIED
    
    @pytest.mark.asyncio
    async def test_emotion_extraction_gentle(self):
        """测试提取gentle情感"""
        llm_response = {
            "intent": "direct_response",
            "agents": [],
            "reasoning": "用户表达了负面情绪，需要温柔回应",
            "direct_reply": "（语气：温柔、轻声）我理解你的感受",
            "emotion": "gentle",
            "memory": {
                "is_important": False
            }
        }
        
        llm_provider = MockLLMProvider(llm_response)
        orchestrator = AgentOrchestrator([], llm_provider=llm_provider, enable_unified_mode=True)
        
        message = Message(content="我今天不开心", user_id="123", chat_id="456")
        context = ChatContext(chat_id="456")
        
        intent, agents, metadata, source, reply, memory = await orchestrator.analyze_intent_unified(message, context)
        
        assert metadata.get("emotion") == "gentle"
    
    @pytest.mark.asyncio
    async def test_emotion_extraction_excited(self):
        """测试提取excited情感"""
        llm_response = {
            "intent": "direct_response",
            "agents": [],
            "reasoning": "用户分享好消息，表达兴奋",
            "direct_reply": "（语气：兴奋、活跃）太棒了！",
            "emotion": "excited",
            "memory": {
                "is_important": True,
                "importance_level": "medium",
                "event_type": "life_event",
                "event_summary": "用户取得成就"
            }
        }
        
        llm_provider = MockLLMProvider(llm_response)
        orchestrator = AgentOrchestrator([], llm_provider=llm_provider, enable_unified_mode=True)
        
        message = Message(content="我考试通过了！", user_id="123", chat_id="456")
        context = ChatContext(chat_id="456")
        
        intent, agents, metadata, source, reply, memory = await orchestrator.analyze_intent_unified(message, context)
        
        assert metadata.get("emotion") == "excited"
    
    @pytest.mark.asyncio
    async def test_emotion_extraction_sad(self):
        """测试提取sad情感"""
        llm_response = {
            "intent": "direct_response",
            "agents": [],
            "reasoning": "用户表达悲伤",
            "direct_reply": "（语气：低落、伤感）我知道这对你来说很难...",
            "emotion": "sad",
            "memory": {
                "is_important": True,
                "importance_level": "high",
                "event_type": "emotion"
            }
        }
        
        llm_provider = MockLLMProvider(llm_response)
        orchestrator = AgentOrchestrator([], llm_provider=llm_provider, enable_unified_mode=True)
        
        message = Message(content="我失去了重要的东西", user_id="123", chat_id="456")
        context = ChatContext(chat_id="456")
        
        intent, agents, metadata, source, reply, memory = await orchestrator.analyze_intent_unified(message, context)
        
        assert metadata.get("emotion") == "sad"
    
    @pytest.mark.asyncio
    async def test_emotion_extraction_angry(self):
        """测试提取angry情感"""
        llm_response = {
            "intent": "direct_response",
            "agents": [],
            "reasoning": "用户表达愤怒",
            "direct_reply": "（语气：生气、愤怒）这太过分了！",
            "emotion": "angry",
            "memory": {
                "is_important": False
            }
        }
        
        llm_provider = MockLLMProvider(llm_response)
        orchestrator = AgentOrchestrator([], llm_provider=llm_provider, enable_unified_mode=True)
        
        message = Message(content="这件事让我很生气", user_id="123", chat_id="456")
        context = ChatContext(chat_id="456")
        
        intent, agents, metadata, source, reply, memory = await orchestrator.analyze_intent_unified(message, context)
        
        assert metadata.get("emotion") == "angry"
    
    @pytest.mark.asyncio
    async def test_emotion_extraction_crying(self):
        """测试提取crying情感"""
        llm_response = {
            "intent": "direct_response",
            "agents": [],
            "reasoning": "用户表达委屈",
            "direct_reply": "（语气：委屈、哭泣）为什么会这样...",
            "emotion": "crying",
            "memory": {
                "is_important": False
            }
        }
        
        llm_provider = MockLLMProvider(llm_response)
        orchestrator = AgentOrchestrator([], llm_provider=llm_provider, enable_unified_mode=True)
        
        message = Message(content="我好委屈", user_id="123", chat_id="456")
        context = ChatContext(chat_id="456")
        
        intent, agents, metadata, source, reply, memory = await orchestrator.analyze_intent_unified(message, context)
        
        assert metadata.get("emotion") == "crying"
    
    @pytest.mark.asyncio
    async def test_no_emotion_extraction(self):
        """测试没有情感标签的情况"""
        llm_response = {
            "intent": "direct_response",
            "agents": [],
            "reasoning": "普通对话",
            "direct_reply": "好的，我明白了",
            "emotion": None,
            "memory": {
                "is_important": False
            }
        }
        
        llm_provider = MockLLMProvider(llm_response)
        orchestrator = AgentOrchestrator([], llm_provider=llm_provider, enable_unified_mode=True)
        
        message = Message(content="知道了", user_id="123", chat_id="456")
        context = ChatContext(chat_id="456")
        
        intent, agents, metadata, source, reply, memory = await orchestrator.analyze_intent_unified(message, context)
        
        # 没有有效情感，metadata中不应包含emotion
        assert "emotion" not in metadata
    
    @pytest.mark.asyncio
    async def test_invalid_emotion_ignored(self):
        """测试无效情感标签被忽略"""
        llm_response = {
            "intent": "direct_response",
            "agents": [],
            "reasoning": "测试无效情感",
            "direct_reply": "测试回复",
            "emotion": "invalid_emotion",  # 无效的情感标签
            "memory": {
                "is_important": False
            }
        }
        
        llm_provider = MockLLMProvider(llm_response)
        orchestrator = AgentOrchestrator([], llm_provider=llm_provider, enable_unified_mode=True)
        
        message = Message(content="测试", user_id="123", chat_id="456")
        context = ChatContext(chat_id="456")
        
        intent, agents, metadata, source, reply, memory = await orchestrator.analyze_intent_unified(message, context)
        
        # 无效情感应该被忽略
        assert "emotion" not in metadata
    
    def test_supported_emotions_constant(self):
        """测试SUPPORTED_EMOTIONS常量存在且正确"""
        orchestrator = AgentOrchestrator([], llm_provider=None)
        
        # 验证常量存在
        assert hasattr(orchestrator, 'SUPPORTED_EMOTIONS')
        
        # 验证包含所有预期的情感
        expected_emotions = ["happy", "gentle", "sad", "excited", "angry", "crying"]
        assert orchestrator.SUPPORTED_EMOTIONS == expected_emotions
    
    @pytest.mark.asyncio
    async def test_process_with_emotion(self):
        """测试完整的process流程包含情感"""
        llm_response = {
            "intent": "direct_response",
            "agents": [],
            "reasoning": "友好问候",
            "direct_reply": "（语气：开心、轻快）很高兴见到你！",
            "emotion": "happy",
            "memory": {
                "is_important": False
            }
        }
        
        llm_provider = MockLLMProvider(llm_response)
        orchestrator = AgentOrchestrator([], llm_provider=llm_provider, enable_unified_mode=True)
        
        message = Message(content="你好", user_id="123", chat_id="456")
        context = ChatContext(chat_id="456")
        
        result = await orchestrator.process(message, context)
        
        # 验证结果
        assert result.intent_type == IntentType.DIRECT_RESPONSE
        assert result.metadata.get("emotion") == "happy"
        assert result.final_response == "（语气：开心、轻快）很高兴见到你！"
