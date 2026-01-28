"""
Tests for LLM Gateway components
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from src.llm_gateway.rate_limiter import RateLimiter, TokenBucket
from src.llm_gateway.token_counter import TokenCounter, UsageStats
from src.llm_gateway.gateway import LLMGateway, LLMRequest, LLMResponse, EmotionInfo
from src.llm_gateway.providers import ProviderConfig, LLMProvider


class TestTokenBucket:
    """Tests for TokenBucket rate limiter"""
    
    def test_bucket_initialization(self):
        """Test bucket is initialized with full capacity"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.tokens == 10
        assert bucket.capacity == 10
    
    def test_consume_tokens(self):
        """Test token consumption"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        
        assert bucket.consume(5) is True
        assert bucket.tokens >= 4.9  # Allow for tiny refill
        
        assert bucket.consume(5) is True
        assert bucket.tokens < 1  # Should be near 0 (with possible tiny refill)
        
        assert bucket.consume(1) is False
    
    def test_wait_time_calculation(self):
        """Test wait time calculation when tokens insufficient"""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)  # 2 tokens per second
        bucket.tokens = 0
        
        wait_time = bucket.wait_time(4)
        assert 1.9 <= wait_time <= 2.1  # Need ~4 tokens at 2/sec = ~2 seconds


class TestRateLimiter:
    """Tests for RateLimiter"""
    
    @pytest.mark.asyncio
    async def test_acquire_success(self):
        """Test successful rate limit acquisition"""
        limiter = RateLimiter(requests_per_minute=60, tokens_per_minute=100000)
        
        result = await limiter.acquire(user_id="user1", estimated_tokens=100)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_user_rate_limit(self):
        """Test per-user rate limiting"""
        limiter = RateLimiter(requests_per_minute=1000)
        
        # User buckets allow 10 requests per minute
        for i in range(10):
            result = await limiter.acquire(user_id="user1")
            assert result is True
        
        # 11th request should fail
        result = await limiter.acquire(user_id="user1")
        assert result is False
    
    def test_get_stats(self):
        """Test statistics retrieval"""
        limiter = RateLimiter()
        stats = limiter.get_stats()
        
        assert "total_requests" in stats
        assert "rejected_requests" in stats
        assert "active_users" in stats


class TestTokenCounter:
    """Tests for TokenCounter"""
    
    def test_calculate_cost(self):
        """Test cost calculation for different models"""
        counter = TokenCounter()
        
        # GPT-4 pricing
        cost = counter.calculate_cost("gpt-4", prompt_tokens=1000, completion_tokens=500)
        assert cost > 0
        
        # Free vLLM model
        cost = counter.calculate_cost("default", prompt_tokens=1000, completion_tokens=500)
        assert cost == 0
    
    def test_record_usage(self):
        """Test usage recording"""
        counter = TokenCounter()
        
        stats = counter.record_usage(
            prompt_tokens=100,
            completion_tokens=50,
            model="gpt-4",
            provider="openai",
            user_id="user1",
            bot_id="bot1"
        )
        
        assert isinstance(stats, UsageStats)
        assert stats.prompt_tokens == 100
        assert stats.completion_tokens == 50
        assert stats.total_tokens == 150
        assert stats.user_id == "user1"
    
    def test_total_stats(self):
        """Test cumulative statistics"""
        counter = TokenCounter()
        
        counter.record_usage(100, 50, "gpt-4", "openai", "user1")
        counter.record_usage(200, 100, "gpt-4", "openai", "user2")
        
        total = counter.get_total_stats()
        assert total["prompt_tokens"] == 300
        assert total["completion_tokens"] == 150
        assert total["total_requests"] == 2
    
    def test_user_stats(self):
        """Test per-user statistics"""
        counter = TokenCounter()
        
        counter.record_usage(100, 50, "gpt-4", "openai", "user1")
        counter.record_usage(200, 100, "gpt-4", "openai", "user1")
        
        user_stats = counter.get_user_stats("user1")
        assert user_stats is not None
        assert user_stats["total_tokens"] == 450
        assert user_stats["requests"] == 2


class TestLLMRequest:
    """Tests for LLMRequest"""
    
    def test_request_creation(self):
        """Test request object creation"""
        request = LLMRequest(
            messages=[{"role": "user", "content": "Hello"}],
            user_id="user1",
            bot_id="bot1"
        )
        
        assert len(request.messages) == 1
        assert request.user_id == "user1"
        assert request.request_id is not None
    
    def test_request_defaults(self):
        """Test default values"""
        request = LLMRequest(messages=[])
        
        assert request.max_tokens == 1000
        assert request.temperature == 0.8
        assert request.model is None
        assert request.provider is None


class TestLLMResponse:
    """Tests for LLMResponse"""
    
    def test_response_creation(self):
        """Test response object creation"""
        usage = UsageStats(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )
        
        response = LLMResponse(
            content="Hello back!",
            model="gpt-4",
            provider="openai",
            usage=usage,
            success=True
        )
        
        assert response.content == "Hello back!"
        assert response.success is True
    
    def test_response_to_dict(self):
        """Test serialization to dict"""
        usage = UsageStats(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        response = LLMResponse(
            content="Test",
            model="gpt-4",
            provider="openai",
            usage=usage
        )
        
        data = response.to_dict()
        assert data["content"] == "Test"
        assert data["model"] == "gpt-4"
        assert "usage" in data
    
    def test_response_with_emotion_info(self):
        """Test response with emotion_info"""
        usage = UsageStats(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        emotion = EmotionInfo(
            emotion_type="happy",
            intensity="high",
            tone_description="开心、轻快"
        )
        response = LLMResponse(
            content="你好！",
            model="gpt-4",
            provider="openai",
            usage=usage,
            emotion_info=emotion
        )
        
        data = response.to_dict()
        assert "emotion_info" in data
        assert data["emotion_info"]["emotion_type"] == "happy"
        assert data["emotion_info"]["intensity"] == "high"
        assert data["emotion_info"]["tone_description"] == "开心、轻快"
    
    def test_response_without_emotion_info(self):
        """Test response without emotion_info doesn't include it in dict"""
        usage = UsageStats(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        response = LLMResponse(
            content="普通回复",
            model="gpt-4",
            provider="openai",
            usage=usage
        )
        
        data = response.to_dict()
        assert "emotion_info" not in data


class TestEmotionInfo:
    """Tests for EmotionInfo"""
    
    def test_emotion_info_creation(self):
        """Test emotion info creation"""
        emotion = EmotionInfo(
            emotion_type="happy",
            intensity="high",
            tone_description="开心、轻快"
        )
        
        assert emotion.emotion_type == "happy"
        assert emotion.intensity == "high"
        assert emotion.tone_description == "开心、轻快"
    
    def test_emotion_info_to_dict(self):
        """Test serialization to dict"""
        emotion = EmotionInfo(
            emotion_type="sad",
            intensity="medium",
            tone_description="低落、缓慢"
        )
        
        data = emotion.to_dict()
        assert data == {
            "emotion_type": "sad",
            "intensity": "medium",
            "tone_description": "低落、缓慢"
        }
    
    def test_emotion_info_from_dict(self):
        """Test creation from dict"""
        data = {
            "emotion_type": "gentle",
            "intensity": "low",
            "tone_description": "温柔"
        }
        
        emotion = EmotionInfo.from_dict(data)
        assert emotion.emotion_type == "gentle"
        assert emotion.intensity == "low"
        assert emotion.tone_description == "温柔"
    
    def test_emotion_info_from_none(self):
        """Test creation from None returns empty"""
        emotion = EmotionInfo.from_dict(None)
        assert emotion.emotion_type is None
        assert emotion.intensity is None
        assert emotion.tone_description is None
    
    def test_emotion_info_defaults(self):
        """Test default values"""
        emotion = EmotionInfo()
        assert emotion.emotion_type is None
        assert emotion.intensity is None
        assert emotion.tone_description is None


class TestLLMGateway:
    """Tests for LLMGateway"""
    
    def test_gateway_initialization(self):
        """Test gateway initialization"""
        gateway = LLMGateway()
        
        assert gateway.default_provider == "openai"
        assert gateway.max_retries == 3
        assert len(gateway._providers) == 0
    
    def test_register_provider(self):
        """Test provider registration"""
        gateway = LLMGateway()
        
        mock_provider = Mock(spec=LLMProvider)
        mock_provider.name = "mock"
        
        gateway.register_provider("mock", mock_provider)
        
        assert "mock" in gateway.list_providers()
        assert gateway.get_provider("mock") == mock_provider
    
    def test_get_nonexistent_provider(self):
        """Test error when getting non-existent provider"""
        gateway = LLMGateway()
        
        with pytest.raises(ValueError):
            gateway.get_provider("nonexistent")
    
    @pytest.mark.asyncio
    async def test_generate_with_mock_provider(self):
        """Test generation with mocked provider"""
        gateway = LLMGateway()
        
        # Create mock provider
        mock_provider = Mock(spec=LLMProvider)
        mock_provider.name = "mock"
        mock_provider.generate = AsyncMock(return_value={
            "content": "Test response",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            },
            "model": "mock-model",
            "finish_reason": "stop"
        })
        
        gateway.register_provider("mock", mock_provider)
        gateway.default_provider = "mock"
        
        request = LLMRequest(
            messages=[{"role": "user", "content": "Hello"}],
            user_id="user1"
        )
        
        response = await gateway.generate(request)
        
        assert response.success is True
        assert response.content == "Test response"
        assert response.usage.total_tokens == 15
    
    @pytest.mark.asyncio
    async def test_generate_with_retry(self):
        """Test retry mechanism on failure"""
        gateway = LLMGateway(max_retries=3, retry_delay=0.1)
        
        # Provider that fails twice then succeeds
        call_count = 0
        
        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary error")
            return {
                "content": "Success after retry",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                "model": "mock",
                "finish_reason": "stop"
            }
        
        mock_provider = Mock(spec=LLMProvider)
        mock_provider.name = "mock"
        mock_provider.generate = mock_generate
        
        gateway.register_provider("mock", mock_provider)
        gateway.default_provider = "mock"
        
        request = LLMRequest(messages=[{"role": "user", "content": "test"}])
        response = await gateway.generate(request)
        
        assert response.success is True
        assert call_count == 3
    
    def test_get_stats(self):
        """Test statistics retrieval"""
        gateway = LLMGateway()
        stats = gateway.get_stats()
        
        assert "total_requests" in stats
        assert "successful_requests" in stats
        assert "failed_requests" in stats
        assert "token_stats" in stats
