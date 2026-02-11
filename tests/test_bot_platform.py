"""
Tests for Bot Configuration and Platform components
"""
import pytest
import tempfile
import os
from pathlib import Path

from src.bot.config_loader import BotConfigLoader, BotConfig, AIConfig
from src.payment.mock_gateway import MockPaymentGateway, SubscriptionTier, PaymentStatus


class TestBotConfigLoader:
    """Tests for BotConfigLoader"""
    
    @pytest.fixture
    def temp_bots_dir(self):
        """Create a temporary bots directory with sample configs"""
        with tempfile.TemporaryDirectory() as tmpdir:
            bot_dir = Path(tmpdir) / "test_bot"
            bot_dir.mkdir()
            
            config_content = """
bot:
  name: "TestBot"
  description: "A test bot"
  username: "test_bot"
  type: "assistant"
  language: "zh"
  is_public: true

ai:
  provider: "openai"
  model: "gpt-4"
  temperature: 0.7
  max_tokens: 1500

prompt:
  template: "general_assistant"
  variables:
    bot_name: "TestBot"

routing:
  mode: "auto"
  private_chat_auto_reply: true

limits:
  free_tier:
    messages: 10
    images: 0
  basic_tier:
    messages: 100
    images: 5

messages:
  welcome: "Welcome to TestBot!"
  help: "I can help you."

metadata:
  version: "1.0.0"
"""
            (bot_dir / "configs.yaml").write_text(config_content)
            yield tmpdir
    
    def test_load_config(self, temp_bots_dir):
        """Test loading a single bot configs"""
        loader = BotConfigLoader(temp_bots_dir)
        
        config = loader.load_config("test_bot")
        
        assert config is not None
        assert config.name == "TestBot"
        assert config.description == "A test bot"
        assert config.bot_type == "assistant"
    
    def test_ai_config_loading(self, temp_bots_dir):
        """Test AI configuration loading"""
        loader = BotConfigLoader(temp_bots_dir)
        config = loader.load_config("test_bot")
        
        assert config.ai.provider == "openai"
        assert config.ai.model == "gpt-4"
        assert config.ai.temperature == 0.7
        assert config.ai.max_tokens == 1500
    
    def test_limits_config_loading(self, temp_bots_dir):
        """Test limits configuration loading"""
        loader = BotConfigLoader(temp_bots_dir)
        config = loader.load_config("test_bot")
        
        assert config.limits.free_tier.messages == 10
        assert config.limits.basic_tier.messages == 100
        assert config.get_limit("free", "messages") == 10
    
    def test_load_all_configs(self, temp_bots_dir):
        """Test loading all bot configs"""
        # Create another bot
        bot_dir = Path(temp_bots_dir) / "another_bot"
        bot_dir.mkdir()
        (bot_dir / "configs.yaml").write_text("""
bot:
  name: "AnotherBot"
""")
        
        loader = BotConfigLoader(temp_bots_dir)
        configs = loader.load_all_configs()
        
        assert len(configs) == 2
        assert "test_bot" in configs
        assert "another_bot" in configs
    
    def test_list_bots(self, temp_bots_dir):
        """Test listing available bots"""
        loader = BotConfigLoader(temp_bots_dir)
        bots = loader.list_bots()
        
        assert "test_bot" in bots
    
    def test_nonexistent_bot(self):
        """Test loading non-existent bot"""
        loader = BotConfigLoader("/nonexistent/path")
        config = loader.load_config("nonexistent")
        
        assert config is None
    
    def test_reload_config(self, temp_bots_dir):
        """Test reloading configuration"""
        loader = BotConfigLoader(temp_bots_dir)
        
        config1 = loader.load_config("test_bot")
        config2 = loader.reload_config("test_bot")
        
        assert config1 is not config2
        assert config2.name == "TestBot"


class TestBotConfig:
    """Tests for BotConfig dataclass"""
    
    def test_get_limit(self):
        """Test getting limits by tier"""
        config = BotConfig(name="Test")
        
        # Should return defaults
        assert config.get_limit("free", "messages") == 10
    
    def test_is_feature_enabled(self):
        """Test feature checking"""
        config = BotConfig(
            name="Test",
            features_enabled=["chat", "images"],
            features_disabled=["code_execution"]
        )
        
        assert config.is_feature_enabled("chat") is True
        assert config.is_feature_enabled("code_execution") is False
        assert config.is_feature_enabled("other") is False  # Not in enabled list


class TestMockPaymentGateway:
    """Tests for MockPaymentGateway"""
    
    @pytest.fixture
    def gateway(self):
        """Create a fresh gateway for each test"""
        return MockPaymentGateway()
    
    def test_get_user_quota_new_user(self, gateway):
        """Test getting quota for new user"""
        quota = gateway.get_user_quota("new_user")
        
        assert quota is not None
        assert quota.tier == SubscriptionTier.FREE
        assert quota.messages_limit == 10
        assert quota.messages_used == 0
    
    def test_check_quota(self, gateway):
        """Test quota checking"""
        assert gateway.check_quota("user1", "message") is True
        
        # Use up all quota
        quota = gateway.get_user_quota("user1")
        quota.messages_used = quota.messages_limit
        
        assert gateway.check_quota("user1", "message") is False
    
    def test_consume_quota(self, gateway):
        """Test quota consumption"""
        result = gateway.consume_quota("user1", "message", 1)
        assert result is True
        
        quota = gateway.get_user_quota("user1")
        assert quota.messages_used == 1
    
    def test_consume_quota_insufficient(self, gateway):
        """Test consuming more than available"""
        quota = gateway.get_user_quota("user1")
        quota.messages_used = quota.messages_limit - 1
        
        result = gateway.consume_quota("user1", "message", 5)
        assert result is False
    
    def test_create_payment(self, gateway):
        """Test payment creation"""
        payment = gateway.create_payment(
            user_id="user1",
            tier=SubscriptionTier.BASIC,
            duration_days=30
        )
        
        assert payment is not None
        assert payment.user_id == "user1"
        assert payment.tier == SubscriptionTier.BASIC
        assert payment.status == PaymentStatus.PENDING
    
    def test_complete_payment(self, gateway):
        """Test payment completion"""
        payment = gateway.create_payment("user1", SubscriptionTier.PREMIUM)
        
        result = gateway.complete_payment(payment.payment_id)
        
        assert result is True
        assert payment.status == PaymentStatus.COMPLETED
        
        # Check user quota was upgraded
        quota = gateway.get_user_quota("user1")
        assert quota.tier == SubscriptionTier.PREMIUM
        assert quota.messages_limit == 1000
    
    def test_complete_nonexistent_payment(self, gateway):
        """Test completing non-existent payment"""
        result = gateway.complete_payment("nonexistent")
        assert result is False
    
    def test_get_payment(self, gateway):
        """Test payment retrieval"""
        payment = gateway.create_payment("user1", SubscriptionTier.BASIC)
        
        retrieved = gateway.get_payment(payment.payment_id)
        
        assert retrieved is not None
        assert retrieved.payment_id == payment.payment_id
    
    def test_get_user_payments(self, gateway):
        """Test getting user's payments"""
        gateway.create_payment("user1", SubscriptionTier.BASIC)
        gateway.create_payment("user1", SubscriptionTier.PREMIUM)
        gateway.create_payment("user2", SubscriptionTier.BASIC)
        
        user1_payments = gateway.get_user_payments("user1")
        
        assert len(user1_payments) == 2
    
    def test_subscription_plans(self, gateway):
        """Test getting subscription plans"""
        plans = gateway.get_subscription_plans()
        
        assert "free" in plans
        assert "basic" in plans
        assert "premium" in plans
        assert plans["basic"]["price"] > 0
    
    def test_get_stats(self, gateway):
        """Test statistics retrieval"""
        gateway.get_user_quota("user1")
        gateway.get_user_quota("user2")
        
        payment = gateway.create_payment("user1", SubscriptionTier.BASIC)
        gateway.complete_payment(payment.payment_id)
        
        stats = gateway.get_stats()
        
        assert stats["total_users"] == 2
        assert stats["completed_payments"] == 1
        assert stats["total_revenue"] > 0
    
    def test_quota_daily_reset(self, gateway):
        """Test quota daily reset logic"""
        from datetime import timedelta
        
        quota = gateway.get_user_quota("user1")
        quota.messages_used = 5
        
        # Set reset date to past
        quota.reset_date = quota.reset_date - timedelta(days=1)
        
        # Get quota again - should trigger reset
        quota = gateway.get_user_quota("user1")
        
        assert quota.messages_used == 0
    
    def test_subscription_expiry(self, gateway):
        """Test subscription expiry handling"""
        from datetime import timedelta
        
        # Upgrade user
        payment = gateway.create_payment("user1", SubscriptionTier.PREMIUM)
        gateway.complete_payment(payment.payment_id)
        
        quota = gateway.get_user_quota("user1")
        assert quota.tier == SubscriptionTier.PREMIUM
        
        # Set subscription to expired
        quota.subscription_end = quota.subscription_end - timedelta(days=60)
        
        # Get quota again - should downgrade to free
        quota = gateway.get_user_quota("user1")
        
        assert quota.tier == SubscriptionTier.FREE
