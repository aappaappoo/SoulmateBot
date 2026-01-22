"""
Database package
"""
# 保留同步版本（用于脚本和迁移）
from .connection import engine, SessionLocal, init_db, get_db, get_db_session

# 新增异步版本
from . async_connection import (
    async_engine,
    AsyncSessionLocal,
    get_async_db,
    get_async_db_context,
    init_async_db,
    close_async_db
)

__all__ = [
    # 同步
    "engine", "SessionLocal", "init_db", "get_db", "get_db_session",
    # 异步
    "async_engine", "AsyncSessionLocal", "get_async_db", "get_async_db_context",
    "init_async_db", "close_async_db"
]