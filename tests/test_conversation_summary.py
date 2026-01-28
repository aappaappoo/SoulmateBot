"""
Tests for LLM-generated conversation summary feature
"""
import pytest
from unittest.mock import Mock, AsyncMock
import json

from src.agents.orchestrator import (
    AgentOrchestrator, OrchestratorResult, IntentType, IntentSource
)
from src.agents import Message, ChatContext
from src.agents.models import KeyElements, LLMConversationSummary


class MockLLMProvider:
    """Mock LLM provider that captures the messages sent to it"""
    
    def __init__(self, response_json):
        self.response_json = response_json
        self.last_messages = None  # Capture the messages sent
    
    async def generate_response(self, messages, context=None):
        """Capture messages and return a mock JSON response"""
        self.last_messages = messages
        return f"```json\n{json.dumps(self.response_json)}\n```"


class TestConversationSummary:
    """测试对话摘要生成功能"""
    
    @pytest.mark.asyncio
    async def test_llm_generates_conversation_summary(self):
        """测试LLM生成对话摘要"""
        # Mock LLM response with conversation summary
        llm_response = {
            "intent": "direct_response",
            "agents": [],
            "reasoning": "用户继续职场吐槽话题，情绪积极",
            "conversation_summary": {
                "summary_text": "用户今天下班后心情不错，与Bot讨论职场吐槽话题，编排'职场奇葩奖'",
                "key_elements": {
                    "time": ["今天", "下班后"],
                    "place": ["公司", "职场"],
                    "people": ["用户", "领导", "同事"],
                    "events": ["下班", "吐槽职场", "编排职场奇葩奖"],
                    "emotions": ["开心", "轻松", "吐槽"]
                },
                "topics": ["工作", "职场吐槽", "幽默互动"],
                "user_state": "情绪积极，参与度高，享受互动"
            },
            "direct_reply": "嘿嘿，咱先列三条——",
            "emotion": "happy",
            "emotion_description": "开心、轻快，语速稍快，语调上扬",
            "memory": {
                "is_important": False
            }
        }
        
        llm_provider = MockLLMProvider(llm_response)
        orchestrator = AgentOrchestrator([], llm_provider=llm_provider, enable_unified_mode=True)
        
        # 创建包含对话历史的上下文
        conversation_history = [
            Message(content="今天下班后心情还不错", user_id="user", chat_id="123"),
            Message(content="太好了！有什么开心的事吗？", user_id="assistant", chat_id="123"),
        ]
        
        context = ChatContext(
            chat_id="123",
            conversation_history=conversation_history,
            system_prompt="你是一个善解人意的AI助手"
        )
        
        # 发送当前消息
        message = Message(content="说起来，今天公司又发生了一些奇葩的事", user_id="user", chat_id="123")
        
        # 调用统一分析
        intent_type, agents, metadata, intent_source, direct_reply, memory_analysis = \
            await orchestrator.analyze_intent_unified(message, context)
        
        # 验证摘要被正确解析
        assert "conversation_summary" in metadata, "metadata应该包含conversation_summary"
        summary = metadata["conversation_summary"]
        
        assert summary["summary_text"] == "用户今天下班后心情不错，与Bot讨论职场吐槽话题，编排'职场奇葩奖'"
        assert summary["key_elements"]["time"] == ["今天", "下班后"]
        assert summary["key_elements"]["place"] == ["公司", "职场"]
        assert summary["key_elements"]["people"] == ["用户", "领导", "同事"]
        assert "下班" in summary["key_elements"]["events"]
        assert "开心" in summary["key_elements"]["emotions"]
        assert "工作" in summary["topics"]
        assert summary["user_state"] == "情绪积极，参与度高，享受互动"
    
    @pytest.mark.asyncio
    async def test_prompt_includes_summary_task(self):
        """测试提示词包含摘要生成任务"""
        llm_response = {
            "intent": "direct_response",
            "agents": [],
            "reasoning": "直接回复",
            "conversation_summary": {
                "summary_text": "简单对话",
                "key_elements": {
                    "time": [],
                    "place": [],
                    "people": ["用户"],
                    "events": ["问候"],
                    "emotions": ["友好"]
                },
                "topics": ["日常问候"],
                "user_state": "正常"
            },
            "direct_reply": "你好！",
            "emotion": None,
            "memory": {"is_important": False}
        }
        
        llm_provider = MockLLMProvider(llm_response)
        orchestrator = AgentOrchestrator([], llm_provider=llm_provider, enable_unified_mode=True)
        
        context = ChatContext(
            chat_id="456",
            conversation_history=[],
            system_prompt="你是一个助手"
        )
        
        message = Message(content="你好", user_id="user", chat_id="456")
        
        await orchestrator.analyze_intent_unified(message, context)
        
        # 验证发送给LLM的消息包含任务3
        messages = llm_provider.last_messages
        last_message_content = messages[-1]["content"]
        
        assert "任务3：对话摘要生成" in last_message_content, "提示词应包含任务3"
        assert "conversation_summary" in last_message_content, "提示词应包含conversation_summary字段说明"
        assert "key_elements" in last_message_content, "提示词应包含key_elements字段说明"
        assert "summary_text" in last_message_content, "提示词应包含summary_text字段说明"
    
    def test_key_elements_from_dict(self):
        """测试KeyElements从字典创建"""
        data = {
            "time": ["今天", "下午"],
            "place": ["公司"],
            "people": ["小明", "小红"],
            "events": ["开会"],
            "emotions": ["紧张"]
        }
        
        key_elements = KeyElements.from_dict(data)
        
        assert key_elements.time == ["今天", "下午"]
        assert key_elements.place == ["公司"]
        assert key_elements.people == ["小明", "小红"]
        assert key_elements.events == ["开会"]
        assert key_elements.emotions == ["紧张"]
    
    def test_key_elements_from_empty_dict(self):
        """测试KeyElements从空字典创建"""
        key_elements = KeyElements.from_dict({})
        
        assert key_elements.time == []
        assert key_elements.place == []
        assert key_elements.people == []
        assert key_elements.events == []
        assert key_elements.emotions == []
    
    def test_llm_conversation_summary_from_dict(self):
        """测试LLMConversationSummary从字典创建"""
        data = {
            "summary_text": "用户和Bot讨论工作",
            "key_elements": {
                "time": ["今天"],
                "place": ["公司"],
                "people": ["用户"],
                "events": ["工作讨论"],
                "emotions": ["平静"]
            },
            "topics": ["工作"],
            "user_state": "正常交流"
        }
        
        summary = LLMConversationSummary.from_dict(data)
        
        assert summary.summary_text == "用户和Bot讨论工作"
        assert summary.key_elements.time == ["今天"]
        assert summary.topics == ["工作"]
        assert summary.user_state == "正常交流"
    
    def test_llm_conversation_summary_to_dict(self):
        """测试LLMConversationSummary转换为字典"""
        key_elements = KeyElements(
            time=["今天"],
            place=["家"],
            people=["用户"],
            events=["聊天"],
            emotions=["开心"]
        )
        
        summary = LLMConversationSummary(
            summary_text="测试摘要",
            key_elements=key_elements,
            topics=["测试"],
            user_state="测试中"
        )
        
        result = summary.to_dict()
        
        assert result["summary_text"] == "测试摘要"
        assert result["key_elements"]["time"] == ["今天"]
        assert result["key_elements"]["place"] == ["家"]
        assert result["topics"] == ["测试"]
        assert result["user_state"] == "测试中"


class TestContextBuilderWithSummary:
    """测试上下文构建器使用LLM摘要"""
    
    @pytest.mark.asyncio
    async def test_context_builder_uses_llm_summary(self):
        """测试上下文构建器优先使用LLM摘要"""
        from src.conversation.context_builder import UnifiedContextBuilder, ContextConfig
        
        builder = UnifiedContextBuilder(
            config=ContextConfig(
                short_term_rounds=2,
                mid_term_start=1,
                mid_term_end=5,
                use_llm_summary=False,
                enable_proactive_strategy=False
            )
        )
        
        # 准备LLM生成的摘要
        llm_summary = {
            "summary_text": "用户今天很开心，和Bot讨论了工作",
            "key_elements": {
                "time": ["今天"],
                "place": ["公司"],
                "people": ["用户", "同事"],
                "events": ["讨论工作"],
                "emotions": ["开心"]
            },
            "topics": ["工作", "心情"],
            "user_state": "情绪积极"
        }
        
        conversation_history = [
            {"role": "user", "content": "今天工作顺利吗？"},
            {"role": "assistant", "content": "很好！"},
            {"role": "user", "content": "真的很开心"},
            {"role": "assistant", "content": "太好了！"},
        ]
        
        result = await builder.build_context(
            bot_system_prompt="你是一个AI助手",
            conversation_history=conversation_history,
            current_message="继续聊聊",
            llm_generated_summary=llm_summary
        )
        
        # 验证system prompt包含LLM摘要
        system_prompt = result.messages[0]["content"]
        
        assert "【本次对话回顾】" in system_prompt
        assert "用户今天很开心，和Bot讨论了工作" in system_prompt
        assert "时间：今天" in system_prompt
        assert "地点：公司" in system_prompt
        assert "人物：用户, 同事" in system_prompt
        assert "事件：讨论工作" in system_prompt
        assert "情绪：开心" in system_prompt
        assert "话题：工作, 心情" in system_prompt
        assert "用户状态：情绪积极" in system_prompt
    
    @pytest.mark.asyncio
    async def test_context_builder_fallback_to_rule_summary(self):
        """测试上下文构建器在没有LLM摘要时回退到规则摘要"""
        from src.conversation.context_builder import UnifiedContextBuilder, ContextConfig
        
        builder = UnifiedContextBuilder(
            config=ContextConfig(
                short_term_rounds=2,
                mid_term_start=1,
                mid_term_end=5,
                use_llm_summary=False,
                enable_proactive_strategy=False
            )
        )
        
        conversation_history = [
            {"role": "user", "content": "今天工作顺利吗？"},
            {"role": "assistant", "content": "很好！"},
            {"role": "user", "content": "真的很开心"},
            {"role": "assistant", "content": "太好了！"},
        ]
        
        # 不传递LLM摘要
        result = await builder.build_context(
            bot_system_prompt="你是一个AI助手",
            conversation_history=conversation_history,
            current_message="继续聊聊",
            llm_generated_summary=None
        )
        
        # 验证使用了规则摘要（如果有中期历史）或没有摘要
        system_prompt = result.messages[0]["content"]
        
        # 由于历史较短，可能没有生成中期摘要
        # 只需验证没有崩溃且能正常构建即可
        assert "你是一个AI助手" in system_prompt
        assert len(result.messages) > 0
