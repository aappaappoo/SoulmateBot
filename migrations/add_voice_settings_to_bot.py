"""
Database Migration: Add voice settings to Bot model
迁移脚本：为Bot模型添加语音设置字段

此脚本添加以下字段到 bots 表：
- voice_enabled: 是否启用语音回复功能
- voice_id: 语音音色ID

运行方法:
    python migrations/add_voice_settings_to_bot.py
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


def migrate():
    """执行迁移"""
    engine = get_engine()
    inspector = inspect(engine)
    
    # 检查 bots 表是否存在
    if 'bots' not in inspector.get_table_names():
        logger.error("❌ Table 'bots' does not exist. Please run the initial migration first.")
        return False
    
    with engine.connect() as conn:
        # 添加 voice_enabled 列
        if not column_exists(inspector, 'bots', 'voice_enabled'):
            logger.info("Adding column 'voice_enabled' to 'bots' table...")
            
            # 根据数据库类型使用不同的SQL
            if 'sqlite' in settings.database_url:
                conn.execute(text("""
                    ALTER TABLE bots 
                    ADD COLUMN voice_enabled BOOLEAN DEFAULT FALSE
                """))
            else:  # PostgreSQL
                conn.execute(text("""
                    ALTER TABLE bots 
                    ADD COLUMN voice_enabled BOOLEAN DEFAULT FALSE
                """))
            
            logger.info("✅ Column 'voice_enabled' added successfully")
        else:
            logger.info("⏭️ Column 'voice_enabled' already exists, skipping")
        
        # 添加 voice_id 列
        if not column_exists(inspector, 'bots', 'voice_id'):
            logger.info("Adding column 'voice_id' to 'bots' table...")
            
            if 'sqlite' in settings.database_url:
                conn.execute(text("""
                    ALTER TABLE bots 
                    ADD COLUMN voice_id VARCHAR(100) DEFAULT NULL
                """))
            else:  # PostgreSQL
                conn.execute(text("""
                    ALTER TABLE bots 
                    ADD COLUMN voice_id VARCHAR(100) DEFAULT NULL
                """))
            
            logger.info("✅ Column 'voice_id' added successfully")
        else:
            logger.info("⏭️ Column 'voice_id' already exists, skipping")
        
        conn.commit()
    
    logger.info("✅ Migration completed successfully!")
    return True


def rollback():
    """回滚迁移"""
    engine = get_engine()
    inspector = inspect(engine)
    
    if 'bots' not in inspector.get_table_names():
        logger.error("❌ Table 'bots' does not exist")
        return False
    
    with engine.connect() as conn:
        # SQLite 不支持 DROP COLUMN，需要特殊处理
        if 'sqlite' in settings.database_url:
            logger.warning("⚠️ SQLite does not support DROP COLUMN. Rollback requires recreating the table.")
            logger.warning("Please manually handle the rollback for SQLite databases.")
            return False
        
        # PostgreSQL 支持 DROP COLUMN
        if column_exists(inspector, 'bots', 'voice_enabled'):
            logger.info("Dropping column 'voice_enabled' from 'bots' table...")
            conn.execute(text("ALTER TABLE bots DROP COLUMN voice_enabled"))
            logger.info("✅ Column 'voice_enabled' dropped successfully")
        
        if column_exists(inspector, 'bots', 'voice_id'):
            logger.info("Dropping column 'voice_id' from 'bots' table...")
            conn.execute(text("ALTER TABLE bots DROP COLUMN voice_id"))
            logger.info("✅ Column 'voice_id' dropped successfully")
        
        conn.commit()
    
    logger.info("✅ Rollback completed successfully!")
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Add voice settings to Bot model")
    parser.add_argument("--rollback", action="store_true", help="Rollback the migration")
    args = parser.parse_args()
    
    if args.rollback:
        rollback()
    else:
        migrate()
