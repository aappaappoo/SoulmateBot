"""
Tests for Feedback Service and related components

测试反馈服务的核心功能：
1. Reaction（表情反应）管理
2. Interaction（交互行为）记录
3. 反馈统计和汇总
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set test environment variables before importing modules
import os
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_key")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import (
    Base, User, Bot, Channel, Conversation,
    MessageReaction, MessageInteraction, FeedbackSummary,
    ReactionType, InteractionType, generate_uuid
)


@pytest.fixture
def db_session():
    """Create an in-memory database session for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = User(
        telegram_id=123456789,
        username="testuser",
        first_name="Test",
        last_name="User"
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_bot(db_session, test_user):
    """Create a test bot"""
    bot = Bot(
        bot_token="test_bot_token",
        bot_name="TestBot",
        bot_username="testbot",
        created_by=test_user.id
    )
    db_session.add(bot)
    db_session.commit()
    return bot


@pytest.fixture
def test_channel(db_session, test_user):
    """Create a test channel"""
    channel = Channel(
        telegram_chat_id=-1001234567890,
        chat_type="supergroup",
        title="Test Channel",
        owner_id=test_user.id
    )
    db_session.add(channel)
    db_session.commit()
    return channel


@pytest.fixture
def test_conversation(db_session, test_user):
    """Create a test conversation"""
    conv = Conversation(
        user_id=test_user.id,
        message="Hello",
        response="Hi there!",
        is_user_message=True
    )
    db_session.add(conv)
    db_session.commit()
    return conv


class TestMessageReactionModel:
    """Tests for MessageReaction model"""
    
    def test_create_reaction(self, db_session, test_user, test_bot, test_channel):
        """Test creating a message reaction"""
        reaction = MessageReaction(
            user_id=test_user.id,
            message_id=12345,
            chat_id=-1001234567890,
            reaction_type="positive",
            reaction_emoji="👍",
            bot_id=test_bot.id,
            channel_id=test_channel.id
        )
        db_session.add(reaction)
        db_session.commit()
        
        assert reaction.id is not None
        assert reaction.uuid is not None
        assert reaction.reaction_emoji == "👍"
        assert reaction.is_active is True
    
    def test_reaction_with_custom_emoji(self, db_session, test_user):
        """Test reaction with custom emoji"""
        reaction = MessageReaction(
            user_id=test_user.id,
            message_id=12345,
            chat_id=-1001234567890,
            reaction_type="custom",
            reaction_emoji="custom",
            custom_emoji_id="5368324170671202286"
        )
        db_session.add(reaction)
        db_session.commit()
        
        assert reaction.custom_emoji_id == "5368324170671202286"
        assert reaction.reaction_type == "custom"
    
    def test_reaction_deactivation(self, db_session, test_user):
        """Test deactivating a reaction"""
        reaction = MessageReaction(
            user_id=test_user.id,
            message_id=12345,
            chat_id=-1001234567890,
            reaction_type="positive",
            reaction_emoji="👍"
        )
        db_session.add(reaction)
        db_session.commit()
        
        # Deactivate
        reaction.is_active = False
        reaction.removed_at = datetime.utcnow()
        db_session.commit()
        
        assert reaction.is_active is False
        assert reaction.removed_at is not None


class TestMessageInteractionModel:
    """Tests for MessageInteraction model"""
    
    def test_create_interaction(self, db_session, test_user, test_bot, test_channel):
        """Test creating a message interaction"""
        interaction = MessageInteraction(
            user_id=test_user.id,
            message_id=12345,
            chat_id=-1001234567890,
            interaction_type=InteractionType.COPY.value,
            bot_id=test_bot.id,
            channel_id=test_channel.id
        )
        db_session.add(interaction)
        db_session.commit()
        
        assert interaction.id is not None
        assert interaction.uuid is not None
        assert interaction.interaction_type == "copy"
        assert interaction.is_successful is True
    
    def test_interaction_with_metadata(self, db_session, test_user):
        """Test interaction with metadata"""
        metadata = {
            "reply_message_id": 67890,
            "reply_text": "This is a reply"
        }
        
        interaction = MessageInteraction(
            user_id=test_user.id,
            message_id=12345,
            chat_id=-1001234567890,
            interaction_type=InteractionType.REPLY.value,
            extra_data=metadata
        )
        db_session.add(interaction)
        db_session.commit()
        
        assert interaction.extra_data["reply_message_id"] == 67890
    
    def test_interaction_types(self, db_session, test_user):
        """Test all interaction types"""
        interaction_types = [
            InteractionType.COPY.value,
            InteractionType.COPY_LINK.value,
            InteractionType.REPLY.value,
            InteractionType.FORWARD.value,
            InteractionType.PIN.value,
            InteractionType.UNPIN.value,
            InteractionType.REPORT.value,
        ]
        
        for itype in interaction_types:
            interaction = MessageInteraction(
                user_id=test_user.id,
                message_id=12345,
                chat_id=-1001234567890,
                interaction_type=itype
            )
            db_session.add(interaction)
        
        db_session.commit()
        
        count = db_session.query(MessageInteraction).count()
        assert count == len(interaction_types)


class TestFeedbackSummaryModel:
    """Tests for FeedbackSummary model"""
    
    def test_create_summary(self, db_session, test_bot, test_channel):
        """Test creating a feedback summary"""
        summary = FeedbackSummary(
            bot_id=test_bot.id,
            channel_id=test_channel.id,
            period_type="daily",
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 1, 2),
            total_reactions=100,
            positive_reactions=80,
            negative_reactions=10,
            neutral_reactions=10
        )
        db_session.add(summary)
        db_session.commit()
        
        assert summary.id is not None
        assert summary.total_reactions == 100
        assert summary.positive_reactions == 80
    
    def test_summary_scores(self, db_session, test_bot):
        """Test summary satisfaction and engagement scores"""
        summary = FeedbackSummary(
            bot_id=test_bot.id,
            period_type="daily",
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 1, 2),
            total_reactions=100,
            positive_reactions=90,
            negative_reactions=10,
            satisfaction_score=90,
            engagement_score=75
        )
        db_session.add(summary)
        db_session.commit()
        
        assert summary.satisfaction_score == 90
        assert summary.engagement_score == 75
    
    def test_summary_breakdown(self, db_session, test_bot):
        """Test reaction and interaction breakdown"""
        reaction_breakdown = {"👍": 50, "❤️": 30, "👎": 10}
        interaction_breakdown = {"copy": 20, "reply": 15, "forward": 5}
        
        summary = FeedbackSummary(
            bot_id=test_bot.id,
            period_type="daily",
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 1, 2),
            reaction_breakdown=reaction_breakdown,
            interaction_breakdown=interaction_breakdown
        )
        db_session.add(summary)
        db_session.commit()
        
        assert summary.reaction_breakdown["👍"] == 50
        assert summary.interaction_breakdown["copy"] == 20


class TestReactionTypes:
    """Tests for ReactionType enum"""
    
    def test_positive_reactions(self):
        """Test positive reaction types"""
        positive = [
            ReactionType.THUMBS_UP,
            ReactionType.HEART,
            ReactionType.FIRE,
            ReactionType.CLAP,
            ReactionType.PARTY
        ]
        
        for reaction in positive:
            assert reaction.value is not None
    
    def test_negative_reactions(self):
        """Test negative reaction types"""
        negative = [
            ReactionType.THUMBS_DOWN,
            ReactionType.POOP,
            ReactionType.VOMIT
        ]
        
        for reaction in negative:
            assert reaction.value is not None


class TestInteractionTypes:
    """Tests for InteractionType enum"""
    
    def test_all_interaction_types(self):
        """Test all interaction type values"""
        expected_types = [
            "copy", "copy_link", "reply", "forward",
            "pin", "unpin", "report", "delete",
            "quote", "edit", "select", "translate",
            "share", "save"
        ]
        
        for itype in InteractionType:
            assert itype.value in expected_types


class TestFeedbackServiceIntegration:
    """Integration tests for FeedbackService"""
    
    def test_feedback_service_import(self):
        """Test that FeedbackService can be imported"""
        from src.services.feedback_service import FeedbackService
        assert FeedbackService is not None
    
    def test_reaction_classification(self):
        """Test reaction classification logic"""
        from src.services.feedback_service import (
            POSITIVE_REACTIONS,
            NEGATIVE_REACTIONS,
            NEUTRAL_REACTIONS
        )
        
        # Positive reactions should include thumbs up
        assert "👍" in POSITIVE_REACTIONS
        assert "❤️" in POSITIVE_REACTIONS
        
        # Negative reactions should include thumbs down
        assert "👎" in NEGATIVE_REACTIONS
        
        # Neutral reactions should include thinking
        assert "🤔" in NEUTRAL_REACTIONS


class TestFeedbackService:
    """Tests for FeedbackService"""
    
    def test_add_reaction(self, db_session, test_user):
        """Test adding a reaction through service"""
        from src.services.feedback_service import FeedbackService
        
        service = FeedbackService(db_session)
        
        reaction = service.add_reaction(
            user_id=test_user.id,
            message_id=12345,
            chat_id=-1001234567890,
            reaction_emoji="👍"
        )
        
        assert reaction is not None
        assert reaction.reaction_emoji == "👍"
        assert reaction.reaction_type == "positive"
        assert reaction.is_active is True
    
    def test_remove_reaction(self, db_session, test_user):
        """Test removing a reaction through service"""
        from src.services.feedback_service import FeedbackService
        
        service = FeedbackService(db_session)
        
        # Add reaction
        service.add_reaction(
            user_id=test_user.id,
            message_id=12345,
            chat_id=-1001234567890,
            reaction_emoji="👍"
        )
        
        # Remove reaction
        result = service.remove_reaction(
            user_id=test_user.id,
            message_id=12345,
            chat_id=-1001234567890,
            reaction_emoji="👍"
        )
        
        assert result is True
    
    def test_update_reaction(self, db_session, test_user):
        """Test updating a reaction (change emoji)"""
        from src.services.feedback_service import FeedbackService
        
        service = FeedbackService(db_session)
        
        # Add initial reaction
        service.add_reaction(
            user_id=test_user.id,
            message_id=12345,
            chat_id=-1001234567890,
            reaction_emoji="👍"
        )
        
        # Update to different reaction
        new_reaction = service.add_reaction(
            user_id=test_user.id,
            message_id=12345,
            chat_id=-1001234567890,
            reaction_emoji="❤️"
        )
        
        assert new_reaction.reaction_emoji == "❤️"
        
        # Check old reaction is deactivated
        reactions = service.get_message_reactions(12345, -1001234567890, active_only=False)
        active_count = sum(1 for r in reactions if r.is_active)
        assert active_count == 1
    
    def test_get_reaction_summary(self, db_session, test_user):
        """Test getting reaction summary"""
        from src.services.feedback_service import FeedbackService
        
        service = FeedbackService(db_session)
        
        # Add multiple reactions
        service.add_reaction(
            user_id=test_user.id,
            message_id=12345,
            chat_id=-1001234567890,
            reaction_emoji="👍"
        )
        
        summary = service.get_reaction_summary(12345, -1001234567890)
        
        assert "👍" in summary
        assert summary["👍"] == 1
    
    def test_record_interaction(self, db_session, test_user):
        """Test recording an interaction"""
        from src.services.feedback_service import FeedbackService
        
        service = FeedbackService(db_session)
        
        interaction = service.record_interaction(
            user_id=test_user.id,
            message_id=12345,
            chat_id=-1001234567890,
            interaction_type="copy"
        )
        
        assert interaction is not None
        assert interaction.interaction_type == "copy"
        assert interaction.is_successful is True
    
    def test_record_reply_interaction(self, db_session, test_user):
        """Test recording a reply interaction"""
        from src.services.feedback_service import FeedbackService
        
        service = FeedbackService(db_session)
        
        interaction = service.record_reply(
            user_id=test_user.id,
            message_id=12345,
            chat_id=-1001234567890,
            reply_message_id=67890
        )
        
        assert interaction.interaction_type == "reply"
        assert interaction.extra_data["reply_message_id"] == 67890
    
    def test_record_pin_interaction(self, db_session, test_user):
        """Test recording a pin interaction"""
        from src.services.feedback_service import FeedbackService
        
        service = FeedbackService(db_session)
        
        interaction = service.record_pin(
            user_id=test_user.id,
            message_id=12345,
            chat_id=-1001234567890
        )
        
        assert interaction.interaction_type == "pin"
    
    def test_get_user_interactions(self, db_session, test_user):
        """Test getting user interactions"""
        from src.services.feedback_service import FeedbackService
        
        service = FeedbackService(db_session)
        
        # Record multiple interactions
        service.record_copy(test_user.id, 12345, -1001234567890)
        service.record_reply(test_user.id, 12346, -1001234567890)
        service.record_pin(test_user.id, 12347, -1001234567890)
        
        interactions = service.get_user_interactions(test_user.id)
        
        assert len(interactions) == 3
    
    def test_get_user_feedback_history(self, db_session, test_user):
        """Test getting user feedback history"""
        from src.services.feedback_service import FeedbackService
        
        service = FeedbackService(db_session)
        
        # Add reactions and interactions
        service.add_reaction(test_user.id, 12345, -1001234567890, "👍")
        service.record_copy(test_user.id, 12345, -1001234567890)
        
        history = service.get_user_feedback_history(test_user.id)
        
        assert 'reactions' in history
        assert 'interactions' in history
        assert len(history['reactions']) == 1
        assert len(history['interactions']) == 1
    
    def test_get_trending_reactions(self, db_session, test_user):
        """Test getting trending reactions"""
        from src.services.feedback_service import FeedbackService
        
        service = FeedbackService(db_session)
        
        # Add multiple reactions
        for i in range(5):
            service.add_reaction(test_user.id, 12345 + i, -1001234567890, "👍")
        
        for i in range(3):
            # Need different users or messages for unique constraint
            pass
        
        trending = service.get_trending_reactions(hours=24, limit=5)
        
        assert len(trending) > 0
        assert trending[0]['emoji'] == "👍"


class TestFeedbackHandlers:
    """Tests for feedback handlers"""
    
    def test_feedback_handlers_import(self):
        """Test that feedback handlers can be imported"""
        from src.handlers.feedback import (
            handle_message_reaction,
            handle_message_reaction_count,
            handle_reply_interaction,
            handle_pinned_message,
            feedback_stats_command,
            my_feedback_command
        )
        
        assert handle_message_reaction is not None
        assert handle_message_reaction_count is not None
        assert handle_reply_interaction is not None
        assert handle_pinned_message is not None
        assert feedback_stats_command is not None
        assert my_feedback_command is not None
