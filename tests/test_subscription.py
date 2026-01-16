"""
Tests for subscription service
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base, User, SubscriptionTier
from src.subscription.service import SubscriptionService


@pytest.fixture
def db_session():
    """Create a test database session"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_create_user(db_session):
    """Test user creation"""
    service = SubscriptionService(db_session)
    user = service.get_user_by_telegram_id(123456789)
    
    assert user is not None
    assert user.telegram_id == 123456789
    assert user.subscription_tier == SubscriptionTier.FREE
    assert user.is_active is True


def test_update_user_info(db_session):
    """Test updating user information"""
    service = SubscriptionService(db_session)
    user = service.update_user_info(
        telegram_id=123456789,
        username="testuser",
        first_name="Test",
        last_name="User"
    )
    
    assert user.username == "testuser"
    assert user.first_name == "Test"
    assert user.last_name == "User"


def test_usage_limit_check(db_session):
    """Test usage limit checking"""
    service = SubscriptionService(db_session)
    user = service.get_user_by_telegram_id(123456789)
    
    # User should be able to send messages initially
    assert service.check_usage_limit(user, "message") is True
    
    # Record usage up to limit
    for _ in range(10):
        service.record_usage(user, "message")
    
    # Should now be at limit
    assert service.check_usage_limit(user, "message") is False


def test_upgrade_subscription(db_session):
    """Test subscription upgrade"""
    service = SubscriptionService(db_session)
    user = service.get_user_by_telegram_id(123456789)
    
    # Upgrade to basic
    upgraded_user = service.upgrade_subscription(
        user,
        SubscriptionTier.BASIC,
        duration_days=30
    )
    
    assert upgraded_user.subscription_tier == SubscriptionTier.BASIC
    assert upgraded_user.subscription_start_date is not None
    assert upgraded_user.subscription_end_date is not None


def test_get_usage_stats(db_session):
    """Test getting usage statistics"""
    service = SubscriptionService(db_session)
    user = service.get_user_by_telegram_id(123456789)
    
    # Record some usage
    service.record_usage(user, "message", count=5)
    service.record_usage(user, "image", count=2)
    
    stats = service.get_usage_stats(user)
    
    assert stats["messages_used"] == 5
    assert stats["images_used"] == 2
    assert stats["subscription_tier"] == "free"
    assert stats["messages_limit"] == 10


def test_subscription_expiry(db_session):
    """Test subscription expiry check"""
    service = SubscriptionService(db_session)
    user = service.get_user_by_telegram_id(123456789)
    
    # Set expired subscription
    user.subscription_tier = SubscriptionTier.BASIC
    user.subscription_end_date = datetime.utcnow() - timedelta(days=1)
    db_session.commit()
    
    # Check status should downgrade to free
    is_active = service.check_subscription_status(user)
    
    assert is_active is False
    assert user.subscription_tier == SubscriptionTier.FREE
