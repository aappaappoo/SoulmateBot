"""
Add Group Monitor Tables Migration

添加群组监控相关的数据库表。

使用方法:
    python migrations/add_group_monitor_tables.py
"""
from sqlalchemy import create_engine, text
from config import settings
from loguru import logger


def run_migration():
    """执行群组监控表的创建迁移"""
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        # 创建 group_monitor_configs 表
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS group_monitor_configs (
                id SERIAL PRIMARY KEY,
                uuid VARCHAR(36) UNIQUE NOT NULL,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                group_link VARCHAR(255) NOT NULL,
                group_chat_id BIGINT,
                group_title VARCHAR(255),
                group_username VARCHAR(255),
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                keywords JSON DEFAULT '[]',
                min_message_length INTEGER DEFAULT 5,
                include_media BOOLEAN DEFAULT FALSE,
                version INTEGER DEFAULT 1 NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        # 创建索引
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_monitor_user_active 
            ON group_monitor_configs(user_id, is_active);
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_monitor_group 
            ON group_monitor_configs(group_chat_id, is_active);
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_monitor_uuid
            ON group_monitor_configs(uuid);
        """))
        
        logger.info("✅ Created group_monitor_configs table")
        
        # 创建 topic_summaries 表（需要先创建，因为 group_messages 引用它）
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS topic_summaries (
                id SERIAL PRIMARY KEY,
                uuid VARCHAR(36) UNIQUE NOT NULL,
                config_id INTEGER NOT NULL REFERENCES group_monitor_configs(id) ON DELETE CASCADE,
                topic_title VARCHAR(255) NOT NULL,
                topic_summary TEXT,
                keywords JSON DEFAULT '[]',
                message_count INTEGER DEFAULT 0,
                participant_count INTEGER DEFAULT 0,
                active_participants JSON DEFAULT '[]',
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                sentiment VARCHAR(50),
                importance_score INTEGER DEFAULT 50,
                ai_analysis JSON DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        # 创建索引
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_topic_config_time 
            ON topic_summaries(config_id, start_time);
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_topic_importance 
            ON topic_summaries(config_id, importance_score);
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_topic_uuid
            ON topic_summaries(uuid);
        """))
        
        logger.info("✅ Created topic_summaries table")
        
        # 创建 group_messages 表
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS group_messages (
                id SERIAL PRIMARY KEY,
                config_id INTEGER NOT NULL REFERENCES group_monitor_configs(id) ON DELETE CASCADE,
                message_id BIGINT NOT NULL,
                chat_id BIGINT NOT NULL,
                sender_id BIGINT,
                sender_username VARCHAR(255),
                sender_name VARCHAR(255),
                content TEXT,
                message_type VARCHAR(50) DEFAULT 'text',
                reply_to_message_id BIGINT,
                forward_from VARCHAR(255),
                is_processed BOOLEAN DEFAULT FALSE,
                topic_id INTEGER REFERENCES topic_summaries(id) ON DELETE SET NULL,
                message_date TIMESTAMP NOT NULL,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        # 创建索引
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_message_config_date 
            ON group_messages(config_id, message_date);
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_message_chat_date 
            ON group_messages(chat_id, message_date);
        """))
        
        # 创建唯一约束
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_config_message 
            ON group_messages(config_id, message_id, chat_id);
        """))
        
        logger.info("✅ Created group_messages table")
        
        conn.commit()
        logger.info("✅ Group monitor migration completed successfully")


if __name__ == "__main__":
    logger.info("Starting group monitor tables migration...")
    run_migration()
