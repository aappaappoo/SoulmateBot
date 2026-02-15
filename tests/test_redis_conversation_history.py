"""
Redis 近期对话记录服务的单元测试

测试内容：
- 内存降级模式下的消息增删查
- 消息数量限制
- 会话清空
"""
import pytest
from unittest.mock import patch, MagicMock


class TestRedisConversationHistory:
    """测试 Redis 对话记录存储（降级到内存模式）"""

    @pytest.fixture
    def history_service(self):
        """创建使用内存降级的对话记录服务"""
        with patch("src.services.redis_conversation_history.settings") as mock_settings:
            mock_settings.redis_url = None
            from src.services.redis_conversation_history import RedisConversationHistory
            service = RedisConversationHistory()
        return service

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
