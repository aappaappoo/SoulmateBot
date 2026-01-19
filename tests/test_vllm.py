"""
Tests for vLLM provider
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.ai.conversation import VLLMProvider, ConversationService


@pytest.mark.asyncio
async def test_vllm_provider_initialization():
    """Test vLLM provider initialization"""
    provider = VLLMProvider(
        api_url="http://localhost:8000",
        api_token="test_token",
        model="test_model"
    )
    
    assert provider.api_url == "http://localhost:8000"
    assert provider.api_token == "test_token"
    assert provider.model == "test_model"


@pytest.mark.asyncio
async def test_vllm_provider_generate_response():
    """Test vLLM provider response generation"""
    provider = VLLMProvider(
        api_url="http://localhost:8000",
        api_token="test_token",
        model="test_model"
    )
    
    messages = [
        {"role": "user", "content": "Hello"}
    ]
    
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": "Hi there!"
                }
            }
        ]
    }
    
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.status = 200
        mock_context.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
        mock_post.return_value = mock_context
        
        response = await provider.generate_response(messages)
        assert response == "Hi there!"


@pytest.mark.asyncio
async def test_vllm_provider_api_error():
    """Test vLLM provider handles API errors"""
    provider = VLLMProvider(
        api_url="http://localhost:8000",
        api_token="test_token",
        model="test_model"
    )
    
    messages = [
        {"role": "user", "content": "Hello"}
    ]
    
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.status = 500
        mock_context.__aenter__.return_value.text = AsyncMock(return_value="Internal Server Error")
        mock_post.return_value = mock_context
        
        with pytest.raises(Exception) as exc_info:
            await provider.generate_response(messages)
        
        assert "vLLM API error" in str(exc_info.value)


def test_vllm_provider_url_normalization():
    """Test vLLM provider normalizes URLs correctly"""
    provider = VLLMProvider(
        api_url="http://localhost:8000/",
        api_token="test_token",
        model="test_model"
    )
    
    # URL should be normalized (trailing slash removed)
    assert provider.api_url == "http://localhost:8000"
