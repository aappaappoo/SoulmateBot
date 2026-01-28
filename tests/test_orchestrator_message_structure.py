"""
Tests for LLM message structure in Agent Orchestrator
测试Agent编排器发送给LLM的消息结构
"""
import pytest
from unittest.mock import Mock, AsyncMock
import json

from src.agents.orchestrator import (
    AgentOrchestrator, OrchestratorResult, IntentType, IntentSource
)
from src.agents import Message, ChatContext, BaseAgent


class MockLLMProvider:
    """Mock LLM provider that captures the messages sent to it"""
    
    def __init__(self, response_json):
        self.response_json = response_json
        self.last_messages = None  # Capture the messages sent
    
    async def generate_response(self, messages, context=None):
        """Capture messages and return a mock JSON response"""
        self.last_messages = messages
        return f"```json\n{json.dumps(self.response_json)}\n```"


class TestOrchestratorMessageStructure:
    """测试编排器发送给LLM的消息结构"""
    
    @pytest.mark.asyncio
    async def test_message_structure_with_conversation_history(self):
        """测试包含对话历史时的消息结构"""
        # Mock LLM response
        llm_response = {
            "intent": "direct_response",
            "agents": [],
            "reasoning": "直接回复",
            "direct_reply": "好的，我理解了",
            "emotion": "gentle",
            "emotion_description": "温柔、轻声",
            "memory": {
                "is_important": False
            }
        }
        
        llm_provider = MockLLMProvider(llm_response)
        orchestrator = AgentOrchestrator([], llm_provider=llm_provider, enable_unified_mode=True)
        
        # 创建包含对话历史的上下文
        conversation_history = [
            Message(content="你好", user_id="user", chat_id="456"),
            Message(content="你好！很高兴见到你", user_id="assistant", chat_id="456"),
            Message(content="今天天气怎么样？", user_id="user", chat_id="456"),
            Message(content="今天天气很好，阳光明媚", user_id="assistant", chat_id="456"),
        ]
        
        context = ChatContext(
            chat_id="456",
            conversation_history=conversation_history,
            system_prompt="你是团团，一名活泼、天真的小陪伴女生"
        )
        
        # 发送当前消息
        message = Message(content="我想知道明天的计划", user_id="user", chat_id="456")
        
        await orchestrator.analyze_intent_unified(message, context)
        
        # 验证发送给LLM的消息结构
        assert llm_provider.last_messages is not None, "应该捕获到发送的消息"
        
        messages = llm_provider.last_messages
        print(f"\n📨 Total messages sent: {len(messages)}")
        for i, msg in enumerate(messages):
            print(f"  {i+1}. role={msg['role']}, content_preview={msg['content'][:50]}...")
        
        # 验证消息数量：1个system + 4个历史 + 1个当前用户消息 = 6条
        assert len(messages) == 6, f"应该有6条消息，实际有{len(messages)}条"
        
        # 验证第一条是 system
        assert messages[0]["role"] == "system", "第一条应该是system消息"
        assert "团团" in messages[0]["content"], "system消息应该包含完整的增强prompt"
        
        # 验证接下来是对话历史（4条）
        assert messages[1]["role"] == "user", "第2条应该是user消息"
        assert messages[1]["content"] == "你好", "内容应该匹配历史消息"
        
        assert messages[2]["role"] == "assistant", "第3条应该是assistant消息"
        assert messages[2]["content"] == "你好！很高兴见到你", "内容应该匹配历史回复"
        
        assert messages[3]["role"] == "user", "第4条应该是user消息"
        assert messages[3]["content"] == "今天天气怎么样？", "内容应该匹配历史消息"
        
        assert messages[4]["role"] == "assistant", "第5条应该是assistant消息"
        assert messages[4]["content"] == "今天天气很好，阳光明媚", "内容应该匹配历史回复"
        
        # 验证最后一条是当前用户消息（包含统一prompt模板）
        assert messages[5]["role"] == "user", "最后一条应该是user消息"
        assert "我想知道明天的计划" in messages[5]["content"], "应该包含当前用户消息"
        assert "任务1：意图识别" in messages[5]["content"], "应该包含统一prompt模板"
    
    @pytest.mark.asyncio
    async def test_message_structure_without_history(self):
        """测试没有对话历史时的消息结构"""
        llm_response = {
            "intent": "direct_response",
            "agents": [],
            "reasoning": "直接回复",
            "direct_reply": "你好！",
            "emotion": "happy",
            "emotion_description": "开心、轻快",
            "memory": {
                "is_important": False
            }
        }
        
        llm_provider = MockLLMProvider(llm_response)
        orchestrator = AgentOrchestrator([], llm_provider=llm_provider, enable_unified_mode=True)
        
        # 创建没有历史的上下文
        context = ChatContext(
            chat_id="456",
            conversation_history=[],
            system_prompt="你是一个友好的AI助手"
        )
        
        message = Message(content="你好", user_id="user", chat_id="456")
        
        await orchestrator.analyze_intent_unified(message, context)
        
        # 验证消息结构
        messages = llm_provider.last_messages
        
        # 没有历史时：1个system + 1个当前用户消息 = 2条
        assert len(messages) == 2, f"应该有2条消息，实际有{len(messages)}条"
        
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "你好" in messages[1]["content"]
    
    @pytest.mark.asyncio
    async def test_message_structure_with_long_history(self):
        """测试有很多对话历史时只取最近10条"""
        llm_response = {
            "intent": "direct_response",
            "agents": [],
            "reasoning": "直接回复",
            "direct_reply": "明白了",
            "emotion": None,
            "memory": {"is_important": False}
        }
        
        llm_provider = MockLLMProvider(llm_response)
        orchestrator = AgentOrchestrator([], llm_provider=llm_provider, enable_unified_mode=True)
        
        # 创建15条历史消息（应该只取最近10条）
        conversation_history = []
        for i in range(15):
            conversation_history.append(
                Message(content=f"用户消息{i}", user_id="user", chat_id="456")
            )
            conversation_history.append(
                Message(content=f"助手回复{i}", user_id="assistant", chat_id="456")
            )
        
        context = ChatContext(
            chat_id="456",
            conversation_history=conversation_history,
            system_prompt="你是一个助手"
        )
        
        message = Message(content="当前消息", user_id="user", chat_id="456")
        
        await orchestrator.analyze_intent_unified(message, context)
        
        messages = llm_provider.last_messages
        
        # 验证最多取10条历史：1个system + 10条历史 + 1个当前 = 12条
        assert len(messages) == 12, f"应该有12条消息（system + 10条历史 + 当前），实际有{len(messages)}条"
        
        # 验证取的是最近的10条（即最后的10条历史消息）
        # 15轮 = 30条历史消息，取最后10条即索引20-29，对应"用户消息10"到"助手回复14"
        assert "用户消息10" in messages[1]["content"], "应该从第10轮开始（最后10条消息）"
        assert "助手回复14" in messages[10]["content"], "应该包含最后一轮的回复"
    
    @pytest.mark.asyncio
    async def test_message_roles_correctly_identified(self):
        """测试消息角色被正确识别"""
        llm_response = {
            "intent": "direct_response",
            "agents": [],
            "reasoning": "直接回复",
            "direct_reply": "好的",
            "emotion": None,
            "memory": {"is_important": False}
        }
        
        llm_provider = MockLLMProvider(llm_response)
        orchestrator = AgentOrchestrator([], llm_provider=llm_provider, enable_unified_mode=True)
        
        # 测试不同的user_id识别
        conversation_history = [
            Message(content="消息1", user_id="user", chat_id="456"),
            Message(content="回复1", user_id="assistant", chat_id="456"),
            Message(content="消息2", user_id="bot", chat_id="456"),  # "bot"应该被识别为assistant
            Message(content="消息3", user_id="agent", chat_id="456"),  # "agent"应该被识别为assistant
        ]
        
        context = ChatContext(
            chat_id="456",
            conversation_history=conversation_history,
            system_prompt="测试"
        )
        
        message = Message(content="当前", user_id="user", chat_id="456")
        await orchestrator.analyze_intent_unified(message, context)
        
        messages = llm_provider.last_messages
        
        # 验证角色
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"
        assert messages[3]["role"] == "assistant"  # "bot"应该被识别为assistant
        assert messages[4]["role"] == "assistant"  # "agent"应该被识别为assistant
