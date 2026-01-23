"""
Demo script for testing SoulmateBot components without running the full bot
"""
from src.models.database import User, Conversation, SubscriptionTier
from src.database import init_db, get_db_session
from src.subscription.service import SubscriptionService


def demo_database():
    """Demo database operations"""
    print("=== Database Demo ===\n")
    
    # Initialize database
    print("Initializing database...")
    init_db()
    print("✓ Database initialized\n")
    
    # Create a test user
    db = get_db_session()
    try:
        service = SubscriptionService(db)
        
        print("Creating test user...")
        user = service.update_user_info(
            telegram_id=123456789,
            username="demo_user",
            first_name="Demo",
            last_name="User"
        )
        print(f"✓ User created: {user.first_name} {user.last_name}")
        print(f"  - Telegram ID: {user.telegram_id}")
        print(f"  - Subscription: {user.subscription_tier.value}")
        print(f"  - Active: {user.is_active}\n")
        
        # Check usage stats
        print("Getting usage statistics...")
        stats = service.get_usage_stats(user)
        print(f"✓ Usage stats:")
        print(f"  - Messages used: {stats['messages_used']}/{stats['messages_limit']}")
        print(f"  - Images used: {stats['images_used']}")
        print(f"  - Subscription tier: {stats['subscription_tier']}\n")
        
        # Test usage recording
        print("Recording test usage...")
        service.record_usage(user, "message", count=3)
        service.record_usage(user, "image", count=1)
        print("✓ Usage recorded\n")
        
        # Check updated stats
        print("Getting updated statistics...")
        stats = service.get_usage_stats(user)
        print(f"✓ Updated stats:")
        print(f"  - Messages used: {stats['messages_used']}/{stats['messages_limit']}")
        print(f"  - Images used: {stats['images_used']}\n")
        
        # Test subscription upgrade
        print("Upgrading subscription to BASIC...")
        upgraded_user = service.upgrade_subscription(
            user,
            SubscriptionTier.BASIC,
            duration_days=30
        )
        print(f"✓ Subscription upgraded to: {upgraded_user.subscription_tier.value}")
        print(f"  - New daily limit: {service.get_daily_limit(upgraded_user.subscription_tier)}\n")
        
    finally:
        db.close()
    
    print("=== Demo completed successfully! ===\n")


def demo_config():
    """Demo configuration"""
    print("=== Configuration Demo ===\n")
    
    from config import settings
    
    print("Current configuration:")
    print(f"  - Environment: {settings.app_env.value}")
    print(f"  - Debug mode: {settings.debug}")
    print(f"  - Log level: {settings.log_level}")
    print(f"  - Database URL: {settings.database_url}")
    print(f"  - Free plan limit: {settings.free_plan_daily_limit}")
    print(f"  - Basic plan limit: {settings.basic_plan_daily_limit}")
    print(f"  - Premium plan limit: {settings.premium_plan_daily_limit}")
    print()


def main():
    """Main demo function"""
    print("\n" + "="*50)
    print("SoulmateBot Component Demo")
    print("="*50 + "\n")
    
    try:
        # Demo configuration
        demo_config()
        
        # Demo database operations
        demo_database()
        
        print("✓ All demos completed successfully!")
        print("\nNext steps:")
        print("1. Configure your .env file with Telegram Bot Token and OpenAI API Key")
        print("2. Run 'python main.py' to start the bot")
        print("3. Test the bot by sending messages in Telegram")
        
    except Exception as e:
        print(f"\n❌ Error during demo: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
