"""
Tests for the memory storage system.
"""
import pytest
import tempfile
import shutil
from pathlib import Path

from src.agents.memory import (
    FileMemoryStore,
    SQLiteMemoryStore,
    InMemoryStore
)


class TestFileMemoryStore:
    """Tests for file-based memory storage."""
    
    def setup_method(self):
        """Create a temporary directory for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.store = FileMemoryStore(base_path=self.temp_dir)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)
    
    def test_write_and_read(self):
        """Test writing and reading memory."""
        data = {"key": "value", "count": 42}
        
        self.store.write("TestAgent", "user123", data)
        result = self.store.read("TestAgent", "user123")
        
        assert result == data
    
    def test_read_nonexistent(self):
        """Test reading non-existent memory returns empty dict."""
        result = self.store.read("TestAgent", "nonexistent")
        
        assert result == {}
    
    def test_overwrite(self):
        """Test overwriting existing memory."""
        self.store.write("TestAgent", "user123", {"count": 1})
        self.store.write("TestAgent", "user123", {"count": 2})
        
        result = self.store.read("TestAgent", "user123")
        
        assert result["count"] == 2
    
    def test_delete(self):
        """Test deleting memory."""
        self.store.write("TestAgent", "user123", {"key": "value"})
        self.store.delete("TestAgent", "user123")
        
        result = self.store.read("TestAgent", "user123")
        
        assert result == {}
    
    def test_multiple_agents(self):
        """Test that different agents have separate storage."""
        self.store.write("Agent1", "user123", {"agent": "one"})
        self.store.write("Agent2", "user123", {"agent": "two"})
        
        result1 = self.store.read("Agent1", "user123")
        result2 = self.store.read("Agent2", "user123")
        
        assert result1["agent"] == "one"
        assert result2["agent"] == "two"
    
    def test_multiple_users(self):
        """Test that different users have separate storage."""
        self.store.write("TestAgent", "user1", {"user": "one"})
        self.store.write("TestAgent", "user2", {"user": "two"})
        
        result1 = self.store.read("TestAgent", "user1")
        result2 = self.store.read("TestAgent", "user2")
        
        assert result1["user"] == "one"
        assert result2["user"] == "two"
    
    def test_file_structure(self):
        """Test that files are organized correctly."""
        self.store.write("TestAgent", "user123", {"key": "value"})
        
        expected_path = Path(self.temp_dir) / "TestAgent" / "user123.json"
        assert expected_path.exists()


class TestSQLiteMemoryStore:
    """Tests for SQLite-based memory storage."""
    
    def setup_method(self):
        """Create a temporary database for testing."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_file.close()
        self.store = SQLiteMemoryStore(db_path=self.temp_file.name)
    
    def teardown_method(self):
        """Clean up temporary database."""
        Path(self.temp_file.name).unlink(missing_ok=True)
    
    def test_write_and_read(self):
        """Test writing and reading memory."""
        data = {"key": "value", "count": 42}
        
        self.store.write("TestAgent", "user123", data)
        result = self.store.read("TestAgent", "user123")
        
        assert result == data
    
    def test_read_nonexistent(self):
        """Test reading non-existent memory returns empty dict."""
        result = self.store.read("TestAgent", "nonexistent")
        
        assert result == {}
    
    def test_overwrite(self):
        """Test overwriting existing memory."""
        self.store.write("TestAgent", "user123", {"count": 1})
        self.store.write("TestAgent", "user123", {"count": 2})
        
        result = self.store.read("TestAgent", "user123")
        
        assert result["count"] == 2
    
    def test_delete(self):
        """Test deleting memory."""
        self.store.write("TestAgent", "user123", {"key": "value"})
        self.store.delete("TestAgent", "user123")
        
        result = self.store.read("TestAgent", "user123")
        
        assert result == {}
    
    def test_multiple_agents(self):
        """Test that different agents have separate storage."""
        self.store.write("Agent1", "user123", {"agent": "one"})
        self.store.write("Agent2", "user123", {"agent": "two"})
        
        result1 = self.store.read("Agent1", "user123")
        result2 = self.store.read("Agent2", "user123")
        
        assert result1["agent"] == "one"
        assert result2["agent"] == "two"
    
    def test_multiple_users(self):
        """Test that different users have separate storage."""
        self.store.write("TestAgent", "user1", {"user": "one"})
        self.store.write("TestAgent", "user2", {"user": "two"})
        
        result1 = self.store.read("TestAgent", "user1")
        result2 = self.store.read("TestAgent", "user2")
        
        assert result1["user"] == "one"
        assert result2["user"] == "two"
    
    def test_unicode_support(self):
        """Test that Unicode data is properly stored."""
        data = {"message": "你好世界", "emoji": "😀"}
        
        self.store.write("TestAgent", "user123", data)
        result = self.store.read("TestAgent", "user123")
        
        assert result == data


class TestInMemoryStore:
    """Tests for in-memory storage."""
    
    def setup_method(self):
        """Create a new in-memory store for each test."""
        self.store = InMemoryStore()
    
    def test_write_and_read(self):
        """Test writing and reading memory."""
        data = {"key": "value", "count": 42}
        
        self.store.write("TestAgent", "user123", data)
        result = self.store.read("TestAgent", "user123")
        
        assert result == data
    
    def test_read_nonexistent(self):
        """Test reading non-existent memory returns empty dict."""
        result = self.store.read("TestAgent", "nonexistent")
        
        assert result == {}
    
    def test_overwrite(self):
        """Test overwriting existing memory."""
        self.store.write("TestAgent", "user123", {"count": 1})
        self.store.write("TestAgent", "user123", {"count": 2})
        
        result = self.store.read("TestAgent", "user123")
        
        assert result["count"] == 2
    
    def test_delete(self):
        """Test deleting memory."""
        self.store.write("TestAgent", "user123", {"key": "value"})
        self.store.delete("TestAgent", "user123")
        
        result = self.store.read("TestAgent", "user123")
        
        assert result == {}
    
    def test_multiple_agents(self):
        """Test that different agents have separate storage."""
        self.store.write("Agent1", "user123", {"agent": "one"})
        self.store.write("Agent2", "user123", {"agent": "two"})
        
        result1 = self.store.read("Agent1", "user123")
        result2 = self.store.read("Agent2", "user123")
        
        assert result1["agent"] == "one"
        assert result2["agent"] == "two"
    
    def test_multiple_users(self):
        """Test that different users have separate storage."""
        self.store.write("TestAgent", "user1", {"user": "one"})
        self.store.write("TestAgent", "user2", {"user": "two"})
        
        result1 = self.store.read("TestAgent", "user1")
        result2 = self.store.read("TestAgent", "user2")
        
        assert result1["user"] == "one"
        assert result2["user"] == "two"
    
    def test_isolation_between_instances(self):
        """Test that different store instances are isolated."""
        store1 = InMemoryStore()
        store2 = InMemoryStore()
        
        store1.write("TestAgent", "user123", {"store": "one"})
        store2.write("TestAgent", "user123", {"store": "two"})
        
        result1 = store1.read("TestAgent", "user123")
        result2 = store2.read("TestAgent", "user123")
        
        assert result1["store"] == "one"
        assert result2["store"] == "two"
