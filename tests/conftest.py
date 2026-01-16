"""
Test configuration
"""
import pytest
import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))


@pytest.fixture
def test_config():
    """Test configuration"""
    return {
        "database_url": "sqlite:///:memory:",
        "debug": True
    }
