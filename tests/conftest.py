"""
Test configuration
"""
import pytest
import sys
import os
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

# Set minimal environment variables for testing
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_key")  # Set a dummy key for testing


@pytest.fixture
def test_config():
    """Test configuration"""
    return {
        "database_url": "sqlite:///:memory:",
        "debug": True
    }
