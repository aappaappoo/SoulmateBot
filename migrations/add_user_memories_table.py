"""
Database Migration: Add user_memories table for conversation memory
迁移脚本：添加用户记忆表，用于存储对话中的重要事件

此脚本创建 user_memories 表，用于存储用户与Bot的重要对话事件，
支持RAG技术驱动的对话记忆功能。

运行方法:
    python migrations/add_user_memories_table.py
    
回滚方法:
    python migrations/add_user_memories_table.py --rollback
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, inspect
from config import settings
from loguru import logger


def get_engine():
    """获取数据库引擎"""
    return create_engine(settings.database_url)


def table_exists(inspector, table_name: str) -> bool:
    """检查表是否已存在"""
    return table_name in inspector.get_table_names()


def migrate():
    """执行迁移 - 创建 user_memories 表"""
    engine = get_engine()
    inspector = inspect(engine)
    
    # 检查表是否已存在
    if table_exists(inspector, 'user_memories'):
        logger.info("⏭️ Table 'user_memories' already exists, skipping")
        return True
    
    with engine.connect() as conn:
        logger.info("Creating table 'user_memories'...")
        
        # 根据数据库类型使用不同的SQL
        if 'sqlite' in settings.database_url:
            # SQLite 版本
            conn.execute(text("""
                CREATE TABLE user_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid VARCHAR(36) NOT NULL UNIQUE,
                    user_id INTEGER NOT NULL,
                    bot_id INTEGER,
                    event_summary TEXT NOT NULL,
                    user_message TEXT,
                    bot_response TEXT,
                    importance VARCHAR(20) DEFAULT 'medium',
                    event_type VARCHAR(50),
                    keywords TEXT DEFAULT '[]',
                    event_date TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    access_count INTEGER DEFAULT 0,
                    last_accessed_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE SET NULL
                )
            """))
            
            # 创建索引
            conn.execute(text("""
                CREATE INDEX idx_user_memories_uuid ON user_memories(uuid)
            """))
            conn.execute(text("""
                CREATE INDEX idx_user_memories_user_bot ON user_memories(user_id, bot_id, is_active)
            """))
            conn.execute(text("""
                CREATE INDEX idx_user_memories_importance ON user_memories(user_id, importance, created_at)
            """))
            conn.execute(text("""
                CREATE INDEX idx_user_memories_event_type ON user_memories(user_id, event_type, is_active)
            """))
            
        else:
            # PostgreSQL 版本
            conn.execute(text("""
                CREATE TABLE user_memories (
                    id SERIAL PRIMARY KEY,
                    uuid VARCHAR(36) NOT NULL UNIQUE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    bot_id INTEGER REFERENCES bots(id) ON DELETE SET NULL,
                    event_summary TEXT NOT NULL,
                    user_message TEXT,
                    bot_response TEXT,
                    importance VARCHAR(20) DEFAULT 'medium',
                    event_type VARCHAR(50),
                    keywords JSONB DEFAULT '[]'::jsonb,
                    event_date TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    access_count INTEGER DEFAULT 0,
                    last_accessed_at TIMESTAMP
                )
            """))
            
            # 创建索引
            conn.execute(text("""
                CREATE INDEX idx_user_memories_uuid ON user_memories(uuid)
            """))
            conn.execute(text("""
                CREATE INDEX idx_user_bot_memory ON user_memories(user_id, bot_id, is_active)
            """))
            conn.execute(text("""
                CREATE INDEX idx_memory_importance ON user_memories(user_id, importance, created_at)
            """))
            conn.execute(text("""
                CREATE INDEX idx_memory_event_type ON user_memories(user_id, event_type, is_active)
            """))
            
            # 添加字段注释
            conn.execute(text("""
                COMMENT ON TABLE user_memories IS '用户长期记忆表 - 存储用户与Bot的重要对话事件'
            """))
            conn.execute(text("COMMENT ON COLUMN user_memories.id IS '内部自增主键'"))
            conn.execute(text("COMMENT ON COLUMN user_memories.uuid IS '外部引用UUID'"))
            conn.execute(text("COMMENT ON COLUMN user_memories.user_id IS '关联的用户ID'"))
            conn.execute(text("COMMENT ON COLUMN user_memories.bot_id IS '关联的机器人ID'"))
            conn.execute(text("COMMENT ON COLUMN user_memories.event_summary IS '事件摘要，用于快速检索'"))
            conn.execute(text("COMMENT ON COLUMN user_memories.user_message IS '用户原始消息'"))
            conn.execute(text("COMMENT ON COLUMN user_memories.bot_response IS '机器人回复'"))
            conn.execute(text("COMMENT ON COLUMN user_memories.importance IS '重要性级别：low/medium/high/critical'"))
            conn.execute(text("COMMENT ON COLUMN user_memories.event_type IS '事件类型：birthday, preference, goal等'"))
            conn.execute(text("COMMENT ON COLUMN user_memories.keywords IS '关键词列表，用于检索匹配'"))
            conn.execute(text("COMMENT ON COLUMN user_memories.event_date IS '事件发生的日期'"))
            conn.execute(text("COMMENT ON COLUMN user_memories.is_active IS '记忆是否有效'"))
            conn.execute(text("COMMENT ON COLUMN user_memories.access_count IS '记忆被访问次数'"))
            conn.execute(text("COMMENT ON COLUMN user_memories.last_accessed_at IS '最后访问时间'"))
        
        conn.commit()
    
    logger.info("✅ Table 'user_memories' created successfully!")
    logger.info("✅ Migration completed successfully!")
    return True


def rollback():
    """回滚迁移 - 删除 user_memories 表"""
    engine = get_engine()
    inspector = inspect(engine)
    
    if not table_exists(inspector, 'user_memories'):
        logger.info("⏭️ Table 'user_memories' does not exist, nothing to rollback")
        return True
    
    with engine.connect() as conn:
        logger.info("Dropping table 'user_memories'...")
        conn.execute(text("DROP TABLE IF EXISTS user_memories"))
        conn.commit()
    
    logger.info("✅ Table 'user_memories' dropped successfully!")
    logger.info("✅ Rollback completed successfully!")
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Add user_memories table for conversation memory")
    parser.add_argument("--rollback", action="store_true", help="Rollback the migration")
    args = parser.parse_args()
    
    if args.rollback:
        rollback()
    else:
        migrate()
