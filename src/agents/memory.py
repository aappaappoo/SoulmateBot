"""
Memory storage system for agents.

Provides an abstract interface for storing and retrieving agent memory.
Currently supports file-based and SQLite storage, with future support
for Redis and vector databases.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json
import sqlite3
from pathlib import Path
from loguru import logger


class MemoryStore(ABC):
    """Abstract base class for memory storage."""
    
    @abstractmethod
    def read(self, agent_name: str, user_id: str) -> Dict[str, Any]:
        """
        Read memory for a specific agent and user.
        
        Args:
            agent_name: Name of the agent
            user_id: User ID
            
        Returns:
            Dictionary containing memory data
        """
        pass
    
    @abstractmethod
    def write(self, agent_name: str, user_id: str, data: Dict[str, Any]) -> None:
        """
        Write memory for a specific agent and user.
        
        Args:
            agent_name: Name of the agent
            user_id: User ID
            data: Dictionary of data to store
        """
        pass
    
    @abstractmethod
    def delete(self, agent_name: str, user_id: str) -> None:
        """
        Delete memory for a specific agent and user.
        
        Args:
            agent_name: Name of the agent
            user_id: User ID
        """
        pass


class FileMemoryStore(MemoryStore):
    """
    File-based memory storage.
    
    Stores each agent's memory in separate JSON files organized by user.
    """
    
    def __init__(self, base_path: str = "data/agent_memory"):
        """
        Initialize file-based memory store.
        
        Args:
            base_path: Base directory for storing memory files
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_file_path(self, agent_name: str, user_id: str) -> Path:
        """Get the file path for a specific agent and user."""
        agent_dir = self.base_path / agent_name
        agent_dir.mkdir(exist_ok=True)
        return agent_dir / f"{user_id}.json"
    
    def read(self, agent_name: str, user_id: str) -> Dict[str, Any]:
        """Read memory from file."""
        file_path = self._get_file_path(agent_name, user_id)
        
        if not file_path.exists():
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading memory from {file_path}: {e}")
            return {}
    
    def write(self, agent_name: str, user_id: str, data: Dict[str, Any]) -> None:
        """Write memory to file."""
        file_path = self._get_file_path(agent_name, user_id)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error writing memory to {file_path}: {e}")
    
    def delete(self, agent_name: str, user_id: str) -> None:
        """Delete memory file."""
        file_path = self._get_file_path(agent_name, user_id)
        
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Error deleting memory at {file_path}: {e}")


class SQLiteMemoryStore(MemoryStore):
    """
    SQLite-based memory storage.
    SQLite 内存存储实现。
    
    Stores agent memory in a SQLite database with a simple schema.
    使用简单的表结构在 SQLite 数据库中存储代理记忆。
    """
    
    def __init__(self, db_path: str = "data/agent_memory.db"):
        """
        Initialize SQLite memory store.
        初始化 SQLite 内存存储。
        
        Args:
            db_path: Path to SQLite database file / SQLite 数据库文件路径
        """
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """
        Initialize database schema.
        初始化数据库表结构。
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_memory (
                    agent_name TEXT NOT NULL,    -- 代理名称，用于区分不同AI代理
                    user_id TEXT NOT NULL,       -- 用户标识，支持字符串格式（可为UUID/MD5）
                    data TEXT NOT NULL,          -- 存储的记忆数据（JSON格式）
                    session_id TEXT,             -- 会话标识，用于并发场景下的会话隔离
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 最后更新时间
                    PRIMARY KEY (agent_name, user_id)
                )
            """)
            # 为并发场景添加会话索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_user_session 
                ON agent_memory(agent_name, user_id, session_id)
            """)
            conn.commit()
    
    def read(self, agent_name: str, user_id: str) -> Dict[str, Any]:
        """Read memory from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT data FROM agent_memory WHERE agent_name = ? AND user_id = ?",
                    (agent_name, user_id)
                )
                row = cursor.fetchone()
                
                if row:
                    return json.loads(row[0])
                return {}
        except Exception as e:
            logger.error(f"Error reading memory from database: {e}")
            return {}
    
    def write(self, agent_name: str, user_id: str, data: Dict[str, Any]) -> None:
        """Write memory to database."""
        try:
            json_data = json.dumps(data, ensure_ascii=False)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO agent_memory (agent_name, user_id, data)
                    VALUES (?, ?, ?)
                    ON CONFLICT(agent_name, user_id) 
                    DO UPDATE SET data = ?, updated_at = CURRENT_TIMESTAMP
                """, (agent_name, user_id, json_data, json_data))
                conn.commit()
        except Exception as e:
            logger.error(f"Error writing memory to database: {e}")
    
    def delete(self, agent_name: str, user_id: str) -> None:
        """Delete memory from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM agent_memory WHERE agent_name = ? AND user_id = ?",
                    (agent_name, user_id)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error deleting memory from database: {e}")


class InMemoryStore(MemoryStore):
    """
    In-memory storage for short-term session context.
    
    This is useful for temporary data that doesn't need persistence.
    """
    
    def __init__(self):
        """Initialize in-memory store."""
        self._storage: Dict[str, Dict[str, Dict[str, Any]]] = {}
    
    def read(self, agent_name: str, user_id: str) -> Dict[str, Any]:
        """Read from memory."""
        return self._storage.get(agent_name, {}).get(user_id, {})
    
    def write(self, agent_name: str, user_id: str, data: Dict[str, Any]) -> None:
        """Write to memory."""
        if agent_name not in self._storage:
            self._storage[agent_name] = {}
        self._storage[agent_name][user_id] = data
    
    def delete(self, agent_name: str, user_id: str) -> None:
        """Delete from memory."""
        if agent_name in self._storage:
            self._storage[agent_name].pop(user_id, None)
