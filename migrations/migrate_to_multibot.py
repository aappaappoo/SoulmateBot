"""
数据库迁移脚本 - 多机器人架构
此脚本用于将现有数据库升级到多机器人架构
"""
import sys
sys.path.append("/Users/apapoo/Desktop/Github_Hub/SolumateBot/")
from sqlalchemy import text
from src.database import engine, get_db_session
from src.models.database import Base, Bot, Channel, ChannelBotMapping, BotStatus
from config import settings
from loguru import logger


def create_new_tables():
    """创建新的数据库表"""
    logger.info("Creating new tables for multi-bot architecture...")
    
    try:
        # 创建新表
        Base.metadata.create_all(bind=engine)
        logger.info("✅ New tables created successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        return False


def migrate_existing_data():
    """迁移现有数据"""
    logger.info("Migrating existing data...")
    
    db = get_db_session()
    try:
        # 检查是否已有Bot记录
        existing_bots = db.query(Bot).count()
        if existing_bots > 0:
            logger.info(f"Found {existing_bots} existing bots, skipping default bot creation")
            return True
        
        # 创建默认机器人（使用当前配置的Bot Token）
        default_bot = Bot(
            bot_token=settings.telegram_bot_token,
            bot_name="SoulmateBot",
            bot_username="soulmatebot",  # 需要根据实际情况修改
            description="默认情感陪伴机器人",
            personality="温暖、友善、善于倾听",
            system_prompt="你是一个温暖友善的情感陪伴机器人，善于倾听用户的心声，提供情感支持和陪伴。",
            ai_model=settings.openai_model if settings.openai_api_key else settings.anthropic_model,
            ai_provider="openai" if settings.openai_api_key else "anthropic",
            is_public=True,
            status=BotStatus.ACTIVE.value,
            created_by=1,  # 假设第一个用户是管理员
            settings={}
        )
        
        db.add(default_bot)
        db.commit()
        db.refresh(default_bot)
        
        logger.info(f"✅ Created default bot with ID: {default_bot.id}")
        
        # 为所有现有用户创建私聊频道并关联默认机器人
        from src.models.database import User
        users = db.query(User).all()
        
        for user in users:
            # 创建私聊频道
            channel = Channel(
                telegram_chat_id=user.telegram_id,
                chat_type="private",
                title=f"Private chat with {user.first_name or 'User'}",
                username=user.username,
                owner_id=user.id,
                subscription_tier=user.subscription_tier,
                subscription_start_date=user.subscription_start_date,
                subscription_end_date=user.subscription_end_date,
                is_active=user.is_active,
                settings={}
            )
            db.add(channel)
            db.commit()
            db.refresh(channel)
            
            # 关联默认机器人
            mapping = ChannelBotMapping(
                channel_id=channel.id,
                bot_id=default_bot.id,
                is_active=True,
                priority=0,
                routing_mode="auto",  # 私聊默认使用auto模式
                keywords=[],
                settings={}
            )
            db.add(mapping)
            
        db.commit()
        logger.info(f"✅ Migrated {len(users)} user channels")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error migrating data: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def verify_migration():
    """验证迁移结果"""
    logger.info("Verifying migration...")
    
    db = get_db_session()
    try:
        # 检查表是否存在
        bot_count = db.query(Bot).count()
        channel_count = db.query(Channel).count()
        mapping_count = db.query(ChannelBotMapping).count()
        
        logger.info(f"📊 Migration results:")
        logger.info(f"   Bots: {bot_count}")
        logger.info(f"   Channels: {channel_count}")
        logger.info(f"   Mappings: {mapping_count}")
        
        if bot_count > 0:
            logger.info("✅ Migration verification successful")
            return True
        else:
            logger.warning("⚠️ No bots found after migration")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error verifying migration: {e}")
        return False
    finally:
        db.close()


def main():
    """主迁移流程"""
    logger.info("=" * 50)
    logger.info("Starting database migration to multi-bot architecture")
    logger.info("=" * 50)
    
    # 步骤1：创建新表
    if not create_new_tables():
        logger.error("Failed to create new tables, aborting migration")
        sys.exit(1)
    
    # 步骤2：迁移数据
    if not migrate_existing_data():
        logger.error("Failed to migrate data, aborting migration")
        sys.exit(1)
    
    # 步骤3：验证迁移
    if not verify_migration():
        logger.error("Migration verification failed")
        sys.exit(1)
    
    logger.info("=" * 50)
    logger.info("✅ Database migration completed successfully!")
    logger.info("=" * 50)
    logger.info("\n📝 Next steps:")
    logger.info("1. Update your bot username in the Bot table")
    logger.info("2. Review the default bot configuration")
    logger.info("3. Create additional bots if needed")
    logger.info("4. Test the multi-bot functionality")


if __name__ == "__main__":
    main()
