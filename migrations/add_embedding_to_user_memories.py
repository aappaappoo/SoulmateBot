"""
Database Migration: Add embedding columns to user_memories table
迁移脚本：为用户记忆表添加向量嵌入字段

此脚本为 user_memories 表添加 embedding 和 embedding_model 字段，
用于支持基于向量相似度的RAG检索。

运行方法:
    python migrations/add_embedding_to_user_memories.py
    
回滚方法:
    python migrations/add_embedding_to_user_memories.py --rollback
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


def column_exists(inspector, table_name: str, column_name: str) -> bool:
    """检查列是否已存在"""
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def table_exists(inspector, table_name: str) -> bool:
    """检查表是否已存在"""
    return table_name in inspector.get_table_names()


def migrate():
    """执行迁移 - 添加 embedding 和 embedding_model 列"""
    engine = get_engine()
    inspector = inspect(engine)
    
    # 检查表是否存在
    if not table_exists(inspector, 'user_memories'):
        logger.warning("⏭️ Table 'user_memories' does not exist, please run add_user_memories_table.py first")
        return False
    
    with engine.connect() as conn:
        # 添加 embedding 列
        if not column_exists(inspector, 'user_memories', 'embedding'):
            logger.info("Adding column 'embedding' to 'user_memories' table...")
            
            if 'sqlite' in settings.database_url:
                # SQLite 版本
                conn.execute(text("""
                    ALTER TABLE user_memories ADD COLUMN embedding TEXT
                """))
            else:
                # PostgreSQL 版本
                conn.execute(text("""
                    ALTER TABLE user_memories ADD COLUMN embedding JSONB
                """))
                conn.execute(text("""
                    COMMENT ON COLUMN user_memories.embedding IS '事件摘要的向量嵌入，用于语义相似度检索'
                """))
            
            logger.info("✅ Column 'embedding' added successfully")
        else:
            logger.info("⏭️ Column 'embedding' already exists, skipping")
        
        # 添加 embedding_model 列
        if not column_exists(inspector, 'user_memories', 'embedding_model'):
            logger.info("Adding column 'embedding_model' to 'user_memories' table...")
            
            conn.execute(text("""
                ALTER TABLE user_memories ADD COLUMN embedding_model VARCHAR(50)
            """))
            
            if 'sqlite' not in settings.database_url:
                conn.execute(text("""
                    COMMENT ON COLUMN user_memories.embedding_model IS '生成嵌入向量使用的模型名称'
                """))
            
            logger.info("✅ Column 'embedding_model' added successfully")
        else:
            logger.info("⏭️ Column 'embedding_model' already exists, skipping")
        
        conn.commit()
    
    logger.info("✅ Migration completed successfully!")
    return True


def rollback():
    """回滚迁移 - 删除 embedding 和 embedding_model 列"""
    engine = get_engine()
    inspector = inspect(engine)
    
    if not table_exists(inspector, 'user_memories'):
        logger.info("⏭️ Table 'user_memories' does not exist, nothing to rollback")
        return True
    
    with engine.connect() as conn:
        if 'sqlite' in settings.database_url:
            # SQLite不支持DROP COLUMN，需要重建表
            logger.warning("SQLite does not support DROP COLUMN. Manual migration required.")
            logger.info("To rollback on SQLite:")
            logger.info("1. Create a new table without the columns")
            logger.info("2. Copy data from old table")
            logger.info("3. Drop old table and rename new table")
            return False
        
        # PostgreSQL 版本
        if column_exists(inspector, 'user_memories', 'embedding'):
            logger.info("Dropping column 'embedding' from 'user_memories' table...")
            conn.execute(text("""
                ALTER TABLE user_memories DROP COLUMN IF EXISTS embedding
            """))
            logger.info("✅ Column 'embedding' dropped successfully")
        
        if column_exists(inspector, 'user_memories', 'embedding_model'):
            logger.info("Dropping column 'embedding_model' from 'user_memories' table...")
            conn.execute(text("""
                ALTER TABLE user_memories DROP COLUMN IF EXISTS embedding_model
            """))
            logger.info("✅ Column 'embedding_model' dropped successfully")
        
        conn.commit()
    
    logger.info("✅ Rollback completed successfully!")
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Add embedding columns to user_memories table")
    parser.add_argument("--rollback", action="store_true", help="Rollback the migration")
    args = parser.parse_args()
    
    if args.rollback:
        rollback()
    else:
        migrate()
