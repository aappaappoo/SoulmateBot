"""
内存对话记录服务的单元测试

测试内容：
- 内存存储下的消息增删查
- 消息数量限制
- 会话清空
- 多用户多Bot隔离
"""
import pytest


class TestInMemoryConversationHistory:
    """测试内存对话记录存储"""

    @pytest.fixture
    def history_service(self):
        """创建内存对话记录服务"""
        from src.services.redis_conversation_history import InMemoryConversationHistory
        return InMemoryConversationHistory()

    def test_add_and_get_message(self, history_service):
        """添加消息后应能正确获取"""
        session_id = "user1_bot1"
        msg = {"role": "user", "content": "你好"}
        history_service.add_message(session_id, msg)

        history = history_service.get_history(session_id)
        assert len(history) == 1
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "你好"

    def test_get_empty_history(self, history_service):
        """获取不存在的会话应返回空列表"""
        history = history_service.get_history("nonexistent")
        assert history == []

    def test_multiple_messages(self, history_service):
        """添加多条消息后应按顺序返回"""
        session_id = "user1_bot1"
        history_service.add_message(session_id, {"role": "user", "content": "你好"})
        history_service.add_message(session_id, {"role": "assistant", "content": "你好！"})
        history_service.add_message(session_id, {"role": "user", "content": "今天天气怎么样？"})

        history = history_service.get_history(session_id)
        assert len(history) == 3
        assert history[0]["content"] == "你好"
        assert history[2]["content"] == "今天天气怎么样？"

    def test_get_history_with_limit(self, history_service):
        """使用 limit 参数应只返回最近的消息"""
        session_id = "user1_bot1"
        for i in range(10):
            history_service.add_message(session_id, {"role": "user", "content": f"消息{i}"})

        history = history_service.get_history(session_id, limit=3)
        assert len(history) == 3
        assert history[0]["content"] == "消息7"
        assert history[2]["content"] == "消息9"

    def test_max_messages_limit(self, history_service):
        """超过最大消息数时应自动截断"""
        session_id = "user1_bot1"
        for i in range(60):
            history_service.add_message(session_id, {"role": "user", "content": f"消息{i}"})

        history = history_service.get_history(session_id)
        assert len(history) == history_service.MAX_MESSAGES

    def test_clear_history(self, history_service):
        """清空对话记录后应返回空列表"""
        session_id = "user1_bot1"
        history_service.add_message(session_id, {"role": "user", "content": "你好"})
        history_service.clear_history(session_id)

        history = history_service.get_history(session_id)
        assert history == []

    def test_separate_sessions(self, history_service):
        """不同会话的消息应隔离"""
        history_service.add_message("session1", {"role": "user", "content": "会话1"})
        history_service.add_message("session2", {"role": "user", "content": "会话2"})

        history1 = history_service.get_history("session1")
        history2 = history_service.get_history("session2")

        assert len(history1) == 1
        assert len(history2) == 1
        assert history1[0]["content"] == "会话1"
        assert history2[0]["content"] == "会话2"

    def test_message_with_timestamp(self, history_service):
        """带 timestamp 的消息应正确存储和检索"""
        session_id = "user1_bot1"
        msg = {"role": "user", "content": "你好", "timestamp": "2026-02-15 10:00:00"}
        history_service.add_message(session_id, msg)

        history = history_service.get_history(session_id)
        assert history[0]["timestamp"] == "2026-02-15 10:00:00"

    def test_multi_user_multi_bot_isolation(self, history_service):
        """不同用户和Bot组合的对话应完全隔离"""
        # user1_bot1
        history_service.add_message("1_1", {"role": "user", "content": "用户1对Bot1"})
        # user1_bot2
        history_service.add_message("1_2", {"role": "user", "content": "用户1对Bot2"})
        # user2_bot1
        history_service.add_message("2_1", {"role": "user", "content": "用户2对Bot1"})

        h1_1 = history_service.get_history("1_1")
        h1_2 = history_service.get_history("1_2")
        h2_1 = history_service.get_history("2_1")

        assert len(h1_1) == 1
        assert len(h1_2) == 1
        assert len(h2_1) == 1
        assert h1_1[0]["content"] == "用户1对Bot1"
        assert h1_2[0]["content"] == "用户1对Bot2"
        assert h2_1[0]["content"] == "用户2对Bot1"

    def test_backward_compat_aliases(self):
        """向后兼容别名应可用"""
        from src.services.redis_conversation_history import (
            RedisConversationHistory,
            get_redis_conversation_history,
            InMemoryConversationHistory,
            get_conversation_history,
        )
        assert RedisConversationHistory is InMemoryConversationHistory
        assert get_redis_conversation_history is get_conversation_history
