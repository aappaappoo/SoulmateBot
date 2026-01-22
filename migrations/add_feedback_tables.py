"""
数据库迁移脚本 - 添加用户反馈跟踪表

本迁移脚本用于创建以下表：
1. message_reactions - 消息反应表（记录👍、❤️、👎等表情反应）
2. message_interactions - 消息交互表（记录复制、回复、置顶、举报等行为）
3. feedback_summaries - 反馈汇总表（定期汇总统计数据）

运行方式：
    python migrations/add_feedback_tables.py

前置条件：
    - 数据库连接已配置
    - users、conversations、bots、channels 表已存在
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text, inspect
from loguru import logger

from config import settings


def check_table_exists(engine, table_name: str) -> bool:
    """检查表是否存在"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def run_migration():
    """执行数据库迁移"""
    logger.info("开始执行反馈表迁移...")
    
    engine = create_engine(settings.database_url)
    
    with engine.begin() as conn:
        # 检查前置表是否存在
        required_tables = ['users', 'conversations', 'bots', 'channels']
        for table in required_tables:
            if not check_table_exists(engine, table):
                logger.error(f"前置表 '{table}' 不存在，请先运行基础迁移")
                return False
        
        # 1. 创建 message_reactions 表
        if check_table_exists(engine, 'message_reactions'):
            logger.info("表 'message_reactions' 已存在，跳过创建")
        else:
            logger.info("创建 'message_reactions' 表...")
            conn.execute(text("""
                CREATE TABLE message_reactions (
                    id SERIAL PRIMARY KEY,
                    uuid VARCHAR(36) UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
                    bot_id INTEGER REFERENCES bots(id) ON DELETE SET NULL,
                    channel_id INTEGER REFERENCES channels(id) ON DELETE SET NULL,
                    message_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    reaction_type VARCHAR(50) NOT NULL,
                    reaction_emoji VARCHAR(50) NOT NULL,
                    custom_emoji_id VARCHAR(255),
                    is_big BOOLEAN DEFAULT FALSE,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    removed_at TIMESTAMP,
                    
                    CONSTRAINT uq_user_message_active_reaction 
                        UNIQUE (user_id, message_id, chat_id, is_active)
                )
            """))
            
            # 创建索引
            conn.execute(text("""
                CREATE INDEX idx_message_reaction_lookup ON message_reactions(chat_id, message_id);
                CREATE INDEX idx_user_reactions ON message_reactions(user_id, created_at);
                CREATE INDEX idx_bot_reactions ON message_reactions(bot_id, reaction_type, is_active);
                CREATE INDEX idx_reaction_uuid ON message_reactions(uuid);
            """))
            logger.info("表 'message_reactions' 创建成功")
        
        # 2. 创建 message_interactions 表
        if check_table_exists(engine, 'message_interactions'):
            logger.info("表 'message_interactions' 已存在，跳过创建")
        else:
            logger.info("创建 'message_interactions' 表...")
            conn.execute(text("""
                CREATE TABLE message_interactions (
                    id SERIAL PRIMARY KEY,
                    uuid VARCHAR(36) UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
                    bot_id INTEGER REFERENCES bots(id) ON DELETE SET NULL,
                    channel_id INTEGER REFERENCES channels(id) ON DELETE SET NULL,
                    message_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    interaction_type VARCHAR(50) NOT NULL,
                    extra_data JSONB DEFAULT '{}',
                    is_successful BOOLEAN DEFAULT TRUE,
                    error_message TEXT,
                    source_platform VARCHAR(50) DEFAULT 'telegram',
                    client_info JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # 创建索引
            conn.execute(text("""
                CREATE INDEX idx_message_interaction_lookup ON message_interactions(chat_id, message_id);
                CREATE INDEX idx_user_interactions ON message_interactions(user_id, interaction_type, created_at);
                CREATE INDEX idx_bot_interactions ON message_interactions(bot_id, interaction_type);
                CREATE INDEX idx_interaction_analytics ON message_interactions(interaction_type, created_at, is_successful);
                CREATE INDEX idx_interaction_uuid ON message_interactions(uuid);
            """))
            logger.info("表 'message_interactions' 创建成功")
        
        # 3. 创建 feedback_summaries 表
        if check_table_exists(engine, 'feedback_summaries'):
            logger.info("表 'feedback_summaries' 已存在，跳过创建")
        else:
            logger.info("创建 'feedback_summaries' 表...")
            conn.execute(text("""
                CREATE TABLE feedback_summaries (
                    id SERIAL PRIMARY KEY,
                    bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE,
                    channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
                    period_type VARCHAR(20) NOT NULL,
                    period_start TIMESTAMP NOT NULL,
                    period_end TIMESTAMP NOT NULL,
                    total_reactions INTEGER DEFAULT 0,
                    positive_reactions INTEGER DEFAULT 0,
                    negative_reactions INTEGER DEFAULT 0,
                    neutral_reactions INTEGER DEFAULT 0,
                    reaction_breakdown JSONB DEFAULT '{}',
                    total_interactions INTEGER DEFAULT 0,
                    copy_count INTEGER DEFAULT 0,
                    reply_count INTEGER DEFAULT 0,
                    forward_count INTEGER DEFAULT 0,
                    pin_count INTEGER DEFAULT 0,
                    report_count INTEGER DEFAULT 0,
                    interaction_breakdown JSONB DEFAULT '{}',
                    satisfaction_score INTEGER,
                    engagement_score INTEGER,
                    version INTEGER DEFAULT 1 NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    CONSTRAINT uq_feedback_summary_period 
                        UNIQUE (bot_id, channel_id, period_type, period_start)
                )
            """))
            
            # 创建索引
            conn.execute(text("""
                CREATE INDEX idx_summary_period ON feedback_summaries(period_type, period_start);
                CREATE INDEX idx_summary_bot ON feedback_summaries(bot_id, period_type, period_start);
            """))
            logger.info("表 'feedback_summaries' 创建成功")
    
    logger.info("反馈表迁移完成！")
    return True


def run_migration_sqlite():
    """执行SQLite数据库迁移（用于测试）"""
    logger.info("开始执行SQLite反馈表迁移...")
    
    engine = create_engine(settings.database_url)
    
    with engine.begin() as conn:
        # 1. 创建 message_reactions 表
        if check_table_exists(engine, 'message_reactions'):
            logger.info("表 'message_reactions' 已存在，跳过创建")
        else:
            logger.info("创建 'message_reactions' 表...")
            conn.execute(text("""
                CREATE TABLE message_reactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid VARCHAR(36) UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
                    bot_id INTEGER REFERENCES bots(id) ON DELETE SET NULL,
                    channel_id INTEGER REFERENCES channels(id) ON DELETE SET NULL,
                    message_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    reaction_type VARCHAR(50) NOT NULL,
                    reaction_emoji VARCHAR(50) NOT NULL,
                    custom_emoji_id VARCHAR(255),
                    is_big BOOLEAN DEFAULT FALSE,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    removed_at TIMESTAMP
                )
            """))
            logger.info("表 'message_reactions' 创建成功")
        
        # 2. 创建 message_interactions 表
        if check_table_exists(engine, 'message_interactions'):
            logger.info("表 'message_interactions' 已存在，跳过创建")
        else:
            logger.info("创建 'message_interactions' 表...")
            conn.execute(text("""
                CREATE TABLE message_interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid VARCHAR(36) UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
                    bot_id INTEGER REFERENCES bots(id) ON DELETE SET NULL,
                    channel_id INTEGER REFERENCES channels(id) ON DELETE SET NULL,
                    message_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    interaction_type VARCHAR(50) NOT NULL,
                    extra_data TEXT DEFAULT '{}',
                    is_successful BOOLEAN DEFAULT TRUE,
                    error_message TEXT,
                    source_platform VARCHAR(50) DEFAULT 'telegram',
                    client_info TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            logger.info("表 'message_interactions' 创建成功")
        
        # 3. 创建 feedback_summaries 表
        if check_table_exists(engine, 'feedback_summaries'):
            logger.info("表 'feedback_summaries' 已存在，跳过创建")
        else:
            logger.info("创建 'feedback_summaries' 表...")
            conn.execute(text("""
                CREATE TABLE feedback_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE,
                    channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
                    period_type VARCHAR(20) NOT NULL,
                    period_start TIMESTAMP NOT NULL,
                    period_end TIMESTAMP NOT NULL,
                    total_reactions INTEGER DEFAULT 0,
                    positive_reactions INTEGER DEFAULT 0,
                    negative_reactions INTEGER DEFAULT 0,
                    neutral_reactions INTEGER DEFAULT 0,
                    reaction_breakdown TEXT DEFAULT '{}',
                    total_interactions INTEGER DEFAULT 0,
                    copy_count INTEGER DEFAULT 0,
                    reply_count INTEGER DEFAULT 0,
                    forward_count INTEGER DEFAULT 0,
                    pin_count INTEGER DEFAULT 0,
                    report_count INTEGER DEFAULT 0,
                    interaction_breakdown TEXT DEFAULT '{}',
                    satisfaction_score INTEGER,
                    engagement_score INTEGER,
                    version INTEGER DEFAULT 1 NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            logger.info("表 'feedback_summaries' 创建成功")
    
    logger.info("SQLite反馈表迁移完成！")
    return True


if __name__ == "__main__":
    if 'sqlite' in settings.database_url.lower():
        run_migration_sqlite()
    else:
        run_migration()
