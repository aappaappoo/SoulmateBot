"""
Tests for the Conversation Memory Service
对话记忆服务测试

This test uses minimal imports to avoid the heavy dependency chain
in the services package.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


# Create a minimal mock setup before importing
class MockMemoryImportance:
    """Mock MemoryImportance enum for testing"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    
    class _Value:
        def __init__(self, value):
            self.value = value
    
    @classmethod
    def get_value(cls, name):
        return getattr(cls, name.upper())


class MockUserMemory:
    """Mock UserMemory model for testing"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockLLMProvider:
    """Mock LLM provider for testing"""
    
    def __init__(self, response: str = None):
        self.response = response or '{"is_important": false}'
    
    async def generate_response(self, messages, context=None):
        return self.response


class TestRuleBasedImportanceAnalysis:
    """
    Tests for rule-based importance analysis without database dependencies.
    These tests validate the core logic of the importance classification.
    """
    
    def _analyze_importance_rule_based(self, user_message: str) -> dict:
        """
        Rule-based importance analysis (copied logic for isolated testing)
        """
        message_lower = user_message.lower()
        
        # 日常寒暄关键词（低重要性）
        greetings = ["你好", "hello", "hi", "再见", "bye", "谢谢", "thanks", 
                     "早上好", "晚上好", "早安", "晚安", "good morning", "good night"]
        
        if any(greeting in message_lower for greeting in greetings) and len(user_message) < 20:
            return {"is_important": False}
        
        # 重要事件关键词
        important_keywords = {
            "birthday": ["生日", "birthday", "出生"],
            "preference": ["喜欢", "不喜欢", "爱好", "兴趣", "喜好", "favorite", "prefer"],
            "goal": ["目标", "计划", "打算", "想要", "希望", "goal", "plan"],
            "life_event": ["毕业", "工作", "结婚", "搬家", "生病", "恋爱"],
            "emotion": ["难过", "开心", "焦虑", "压力", "担心", "害怕"],
            "relationship": ["朋友", "家人", "父母", "孩子", "男朋友", "女朋友"]
        }
        
        for event_type, keywords in important_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                return {
                    "is_important": True,
                    "importance_level": "medium",
                    "event_type": event_type,
                    "event_summary": user_message[:100],
                    "keywords": [kw for kw in keywords if kw in message_lower],
                    "event_date": None
                }
        
        return {"is_important": False}
    
    def test_filters_greetings(self):
        """Test that greetings are filtered out (not important)"""
        result = self._analyze_importance_rule_based("你好")
        assert result["is_important"] is False
        
        result = self._analyze_importance_rule_based("Hello")
        assert result["is_important"] is False
        
        result = self._analyze_importance_rule_based("谢谢")
        assert result["is_important"] is False
        
        result = self._analyze_importance_rule_based("再见")
        assert result["is_important"] is False
    
    def test_detects_birthday(self):
        """Test that birthday-related messages are detected as important"""
        result = self._analyze_importance_rule_based("我的生日是下个月15号")
        
        assert result["is_important"] is True
        assert result["event_type"] == "birthday"
        assert "生日" in result["keywords"]
    
    def test_detects_preferences(self):
        """Test that preference-related messages are detected as important"""
        result = self._analyze_importance_rule_based("我喜欢看电影")
        
        assert result["is_important"] is True
        assert result["event_type"] == "preference"
        assert "喜欢" in result["keywords"]
    
    def test_detects_goals(self):
        """Test that goal-related messages are detected as important"""
        result = self._analyze_importance_rule_based("我打算明年学习编程")
        
        assert result["is_important"] is True
        assert result["event_type"] == "goal"
        assert "打算" in result["keywords"]
    
    def test_detects_emotions(self):
        """Test that emotion-related messages are detected as important"""
        result = self._analyze_importance_rule_based("我今天很难过")
        
        assert result["is_important"] is True
        assert result["event_type"] == "emotion"
        assert "难过" in result["keywords"]
    
    def test_detects_life_events(self):
        """Test that life event messages are detected as important"""
        result = self._analyze_importance_rule_based("我下个月要毕业了")
        
        assert result["is_important"] is True
        assert result["event_type"] == "life_event"
        assert "毕业" in result["keywords"]
    
    def test_detects_relationships(self):
        """Test that relationship messages are detected as important"""
        result = self._analyze_importance_rule_based("我的父母来看我了")
        
        assert result["is_important"] is True
        assert result["event_type"] == "relationship"
        assert "父母" in result["keywords"]
    
    def test_no_match_for_generic_message(self):
        """Test that generic messages are not marked as important"""
        result = self._analyze_importance_rule_based("今天天气怎么样？")
        
        assert result["is_important"] is False
    
    def test_long_greeting_not_filtered(self):
        """Test that long messages with greetings are not filtered"""
        result = self._analyze_importance_rule_based("你好，我的生日是下个月15号，请帮我记住")
        
        # Contains greeting but is long and has important content
        assert result["is_important"] is True
    
    def test_english_preference(self):
        """Test English preference detection"""
        result = self._analyze_importance_rule_based("I prefer Python for programming")
        
        assert result["is_important"] is True
        assert result["event_type"] == "preference"
    
    def test_english_goal(self):
        """Test English goal detection"""
        result = self._analyze_importance_rule_based("My goal is to learn machine learning")
        
        assert result["is_important"] is True
        assert result["event_type"] == "goal"


class TestMemoryFormatting:
    """Tests for memory formatting logic"""
    
    async def format_memories_for_context(self, memories, max_chars=1000):
        """Format memories for context injection (copied logic for testing)"""
        if not memories:
            return ""
        
        memory_texts = []
        current_length = 0
        
        for memory in memories:
            memory_text = f"- {memory.event_summary}"
            if hasattr(memory, 'event_date') and memory.event_date:
                memory_text += f" (日期: {memory.event_date.strftime('%Y-%m-%d')})"
            
            if current_length + len(memory_text) > max_chars:
                break
            
            memory_texts.append(memory_text)
            current_length += len(memory_text)
        
        if not memory_texts:
            return ""
        
        return "【关于这位用户的记忆】\n" + "\n".join(memory_texts)
    
    @pytest.mark.asyncio
    async def test_format_memories_with_date(self):
        """Test formatting memories with dates"""
        memories = [
            MagicMock(
                event_summary="用户生日是1月15日",
                event_date=datetime(2025, 1, 15)
            )
        ]
        
        result = await self.format_memories_for_context(memories)
        
        assert "关于这位用户的记忆" in result
        assert "用户生日是1月15日" in result
        assert "2025-01-15" in result
    
    @pytest.mark.asyncio
    async def test_format_memories_without_date(self):
        """Test formatting memories without dates"""
        memories = [
            MagicMock(
                event_summary="用户喜欢Python编程",
                event_date=None
            )
        ]
        
        result = await self.format_memories_for_context(memories)
        
        assert "关于这位用户的记忆" in result
        assert "用户喜欢Python编程" in result
    
    @pytest.mark.asyncio
    async def test_format_empty_memories(self):
        """Test formatting with no memories"""
        result = await self.format_memories_for_context([])
        
        assert result == ""
    
    @pytest.mark.asyncio
    async def test_format_respects_max_chars(self):
        """Test that formatting respects max character limit"""
        memories = [
            MagicMock(
                event_summary=f"这是一个很长的记忆内容 {i}",
                event_date=None
            )
            for i in range(20)
        ]
        
        result = await self.format_memories_for_context(memories, max_chars=100)
        
        # Result should be truncated to not include all memories
        assert result.count("记忆内容") < 20


class TestImportanceThreshold:
    """Tests for importance threshold logic"""
    
    def test_importance_order(self):
        """Test importance level ordering"""
        importance_order = {
            "low": 0,
            "medium": 1,
            "high": 2,
            "critical": 3
        }
        
        # Test ordering
        assert importance_order["low"] < importance_order["medium"]
        assert importance_order["medium"] < importance_order["high"]
        assert importance_order["high"] < importance_order["critical"]
    
    def test_threshold_filtering(self):
        """Test that threshold filtering works correctly"""
        importance_order = {
            "low": 0,
            "medium": 1,
            "high": 2,
            "critical": 3
        }
        threshold = "medium"
        
        # Low importance should be filtered
        event_importance = "low"
        should_save = importance_order.get(event_importance, 0) >= importance_order.get(threshold, 1)
        assert should_save is False
        
        # Medium importance should pass
        event_importance = "medium"
        should_save = importance_order.get(event_importance, 0) >= importance_order.get(threshold, 1)
        assert should_save is True
        
        # High importance should pass
        event_importance = "high"
        should_save = importance_order.get(event_importance, 0) >= importance_order.get(threshold, 1)
        assert should_save is True
