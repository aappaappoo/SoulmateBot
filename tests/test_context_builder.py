"""
Unit tests for UnifiedContextBuilder
"""
import pytest
from src.conversation.context_builder import (
    UnifiedContextBuilder,
    ContextConfig,
    BuilderResult
)
from src.conversation.summary_service import ConversationSummaryService
from src.conversation.proactive_strategy import ProactiveDialogueStrategyAnalyzer


@pytest.mark.asyncio
class TestUnifiedContextBuilder:
    """Test suite for UnifiedContextBuilder"""
    
    async def test_basic_context_building(self):
        """Test basic context building with minimal history"""
        builder = UnifiedContextBuilder()
        
        result = await builder.build_context(
            bot_system_prompt="你是一个友好的AI助手。",
            conversation_history=[
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好！很高兴见到你！"}
            ],
            current_message="今天天气怎么样？"
        )
        
        assert isinstance(result, BuilderResult)
        assert len(result.messages) >= 2  # At least system + current
        assert result.messages[0]["role"] == "system"
        assert result.messages[-1]["role"] == "user"
        assert result.messages[-1]["content"] == "今天天气怎么样？"
        assert result.token_estimate > 0
    
    async def test_split_history(self):
        """Test conversation history splitting"""
        builder = UnifiedContextBuilder(
            config=ContextConfig(
                short_term_rounds=2,
                mid_term_start=2,
                mid_term_end=5
            )
        )
        
        # Create 10 rounds of conversation
        history = []
        for i in range(10):
            history.append({"role": "user", "content": f"用户消息{i+1}"})
            history.append({"role": "assistant", "content": f"AI回复{i+1}"})
        
        short_term, mid_term = builder._split_history(history)
        
        # Short term should be last 2 rounds (4 messages)
        assert len(short_term) == 4
        assert short_term[-1]["content"] == "AI回复10"
        
        # Mid term should be rounds 2-5
        assert len(mid_term) > 0
    
    async def test_with_user_memories(self):
        """Test context building with user memories"""
        builder = UnifiedContextBuilder()
        
        user_memories = [
            {
                "event_summary": "用户喜欢玩游戏",
                "event_date": "2026年1月20日",
                "event_type": "preference",
                "keywords": ["游戏"]
            },
            {
                "event_summary": "用户的生日是3月15日",
                "event_date": None,
                "event_type": "birthday",
                "keywords": ["生日"]
            }
        ]
        
        result = await builder.build_context(
            bot_system_prompt="你是团团。",
            conversation_history=[
                {"role": "user", "content": "我今天很开心"},
                {"role": "assistant", "content": "太好了！"}
            ],
            current_message="你记得我的爱好吗？",
            user_memories=user_memories
        )
        
        # Check that memories are in system prompt
        system_content = result.messages[0]["content"]
        assert "关于这位用户的记忆" in system_content or "玩游戏" in system_content
    
    async def test_mid_term_summary(self):
        """Test mid-term conversation summarization"""
        builder = UnifiedContextBuilder(
            config=ContextConfig(
                short_term_rounds=2,
                mid_term_start=1,
                mid_term_end=8
            )
        )
        
        # Create conversation with 10 rounds
        history = []
        for i in range(10):
            history.append({"role": "user", "content": f"我今天工作很累，第{i+1}天"})
            history.append({"role": "assistant", "content": f"辛苦了！要注意休息哦。"})
        
        result = await builder.build_context(
            bot_system_prompt="你是AI助手。",
            conversation_history=history,
            current_message="我需要放松一下"
        )
        
        # Check that mid-term summary exists in system prompt
        system_content = result.messages[0]["content"]
        # Should have summary section
        assert len(system_content) > len("你是AI助手。")
        assert result.metadata.get("mid_term_count", 0) > 0
    
    async def test_token_budget_management(self):
        """Test token budget enforcement"""
        builder = UnifiedContextBuilder(
            config=ContextConfig(
                max_total_tokens=500,
                reserved_output_tokens=100,
                short_term_rounds=10
            )
        )
        
        # Create a lot of history
        history = []
        for i in range(50):
            history.append({
                "role": "user",
                "content": f"这是一条很长的消息内容，包含很多字符，用于测试token预算管理功能。消息编号：{i+1}"
            })
            history.append({
                "role": "assistant",
                "content": f"我理解你的意思。这是一条详细的回复内容。回复编号：{i+1}"
            })
        
        result = await builder.build_context(
            bot_system_prompt="你是AI助手。" * 10,  # Make system prompt longer
            conversation_history=history,
            current_message="当前消息"
        )
        
        # Token budget should be respected
        budget_info = builder.get_token_budget_info(result)
        assert budget_info["estimated_tokens"] <= budget_info["available_for_context"]
    
    async def test_proactive_guidance_enabled(self):
        """Test proactive strategy guidance generation"""
        builder = UnifiedContextBuilder(
            config=ContextConfig(enable_proactive_strategy=True)
        )
        
        history = [
            {"role": "user", "content": "我喜欢玩游戏"},
            {"role": "assistant", "content": "哇，什么类型的游戏呀？"},
            {"role": "user", "content": "RPG游戏"},
            {"role": "assistant", "content": "很棒！"}
        ]
        
        result = await builder.build_context(
            bot_system_prompt="你是团团。",
            conversation_history=history,
            current_message="今天心情不错"
        )
        
        system_content = result.messages[0]["content"]
        # Should contain proactive guidance
        assert result.metadata.get("has_proactive_guidance", False) or len(system_content) > 100
    
    async def test_proactive_guidance_disabled(self):
        """Test with proactive strategy disabled"""
        builder = UnifiedContextBuilder(
            config=ContextConfig(enable_proactive_strategy=False)
        )
        
        result = await builder.build_context(
            bot_system_prompt="你是AI助手。",
            conversation_history=[
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好！"}
            ],
            current_message="今天天气怎么样？"
        )
        
        assert result.metadata.get("has_proactive_guidance") == False
    
    async def test_empty_history(self):
        """Test with empty conversation history"""
        builder = UnifiedContextBuilder()
        
        result = await builder.build_context(
            bot_system_prompt="你是AI助手。",
            conversation_history=[],
            current_message="第一次见面！"
        )
        
        assert len(result.messages) == 2  # system + current
        assert result.messages[0]["role"] == "system"
        assert result.messages[1]["role"] == "user"
        assert result.token_estimate > 0
    
    async def test_format_memories(self):
        """Test memory formatting"""
        builder = UnifiedContextBuilder(
            config=ContextConfig(max_memories=3)
        )
        
        memories = [
            {"event_summary": "用户喜欢游戏", "event_date": "2026-01-20"},
            {"event_summary": "用户有一只猫", "event_date": None},
            {"event_summary": "用户学习Python", "event_date": "2026-01-15"}
        ]
        
        formatted = builder._format_memories(memories)
        
        assert "关于这位用户的记忆" in formatted
        assert "游戏" in formatted
        # All 3 should be included since we only have 3
        assert formatted.count("-") >= 3
    
    def test_estimate_tokens(self):
        """Test token estimation"""
        builder = UnifiedContextBuilder()
        
        messages = [
            {"role": "system", "content": "你是一个友好的AI助手。"},
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！很高兴见到你！"}
        ]
        
        tokens = builder._estimate_tokens(messages)
        
        # Should estimate something reasonable
        assert tokens > 10
        assert tokens < 1000


@pytest.mark.asyncio
class TestContextConfig:
    """Test suite for ContextConfig"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = ContextConfig()
        
        assert config.short_term_rounds == 5
        assert config.mid_term_start == 3
        assert config.mid_term_end == 20
        assert config.max_memories == 8
        assert config.max_total_tokens == 8000
        assert config.reserved_output_tokens == 1000
        assert config.use_llm_summary == False
        assert config.enable_proactive_strategy == True
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = ContextConfig(
            short_term_rounds=3,
            max_memories=5,
            use_llm_summary=True
        )
        
        assert config.short_term_rounds == 3
        assert config.max_memories == 5
        assert config.use_llm_summary == True


@pytest.mark.asyncio
class TestBuilderResult:
    """Test suite for BuilderResult"""
    
    def test_builder_result_structure(self):
        """Test BuilderResult dataclass"""
        messages = [
            {"role": "system", "content": "test"},
            {"role": "user", "content": "hello"}
        ]
        
        result = BuilderResult(
            messages=messages,
            token_estimate=100,
            metadata={"test": "value"}
        )
        
        assert result.messages == messages
        assert result.token_estimate == 100
        assert result.metadata["test"] == "value"
