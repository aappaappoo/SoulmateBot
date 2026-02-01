"""
Tests for SearchAgent and SERP API Service.

测试搜索Agent和SERP API服务的功能，包括：
- SearchAgent 意图识别
- SearchAgent 响应生成
- SERP API key 轮用
- 搜索结果缓存
- 网页抓取和清洗
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

# Add src to path for imports
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

# Also add the agents directory to sys.path for importing SearchAgent
agents_path = src_path / "agents"
sys.path.insert(0, str(agents_path))

from src.agents.models import Message, ChatContext, AgentResponse


class TestSearchAgent:
    """Tests for SearchAgent functionality."""
    
    @pytest.fixture
    def search_agent(self):
        """Create a SearchAgent instance for testing."""
        from agents.search_agent import SearchAgent
        return SearchAgent()
    
    @pytest.fixture
    def sample_message(self):
        """Create a sample message for testing."""
        return Message(
            content="梅西最近动态是什么？",
            user_id="test_user_123",
            chat_id="test_chat_456"
        )
    
    @pytest.fixture
    def sample_context(self):
        """Create a sample chat context."""
        return ChatContext(chat_id="test_chat_456")
    
    def test_agent_name_and_description(self, search_agent):
        """Test agent has correct name and description."""
        assert search_agent.name == "SearchAgent"
        assert len(search_agent.description) > 0
        assert "搜索" in search_agent.description or "search" in search_agent.description.lower()
    
    def test_can_handle_with_search_keywords(self, search_agent, sample_context):
        """Test can_handle returns high confidence for search-related messages."""
        # 包含多个搜索关键词的消息
        message = Message(
            content="帮我搜索一下最新的新闻动态",
            user_id="test_user",
            chat_id="test_chat"
        )
        confidence = search_agent.can_handle(message, sample_context)
        assert confidence >= 0.6
    
    def test_can_handle_with_realtime_topics(self, search_agent, sample_context):
        """Test can_handle returns confidence for realtime topics."""
        message = Message(
            content="今天的天气怎么样？",
            user_id="test_user",
            chat_id="test_chat"
        )
        confidence = search_agent.can_handle(message, sample_context)
        # 天气是实时话题，应该有一定置信度
        assert confidence >= 0.5
    
    def test_can_handle_with_mention(self, search_agent, sample_context):
        """Test can_handle returns 1.0 when agent is mentioned."""
        message = Message(
            content="@SearchAgent 帮我查一下",
            user_id="test_user",
            chat_id="test_chat",
            metadata={"mentions": ["@SearchAgent"]}
        )
        confidence = search_agent.can_handle(message, sample_context)
        assert confidence == 1.0
    
    def test_can_handle_with_no_keywords(self, search_agent, sample_context):
        """Test can_handle returns 0 for unrelated messages."""
        message = Message(
            content="你好，心情不错",
            user_id="test_user",
            chat_id="test_chat"
        )
        confidence = search_agent.can_handle(message, sample_context)
        assert confidence == 0.0
    
    def test_skills_property(self, search_agent):
        """Test agent provides correct skills."""
        skills = search_agent.skills
        assert "web_search" in skills
        assert "news_query" in skills
        assert "realtime_info" in skills
    
    def test_skill_keywords(self, search_agent):
        """Test agent skill keywords."""
        keywords = search_agent.skill_keywords
        assert "web_search" in keywords
        assert "搜索" in keywords["web_search"]
    
    def test_skill_description(self, search_agent):
        """Test agent skill descriptions."""
        desc = search_agent.get_skill_description("web_search")
        assert desc is not None
        assert len(desc) > 0
    
    def test_can_provide_skill(self, search_agent):
        """Test can_provide_skill method."""
        assert search_agent.can_provide_skill("web_search") is True
        assert search_agent.can_provide_skill("news_query") is True
        assert search_agent.can_provide_skill("non_existent") is False
    
    def test_extract_query(self, search_agent):
        """Test query extraction from user message."""
        # 测试移除常见搜索指令词
        query1 = search_agent._extract_query("帮我搜索梅西")
        assert "梅西" in query1
        
        query2 = search_agent._extract_query("查一下北京天气")
        assert "北京天气" in query2
    
    def test_should_fetch_content(self, search_agent):
        """Test should_fetch_content detection."""
        # 需要详细内容
        assert search_agent._should_fetch_content("请给我详细信息") is True
        assert search_agent._should_fetch_content("我想要更多内容") is True
        
        # 不需要详细内容
        assert search_agent._should_fetch_content("简单查一下") is False
    
    @patch('agents.search_agent.serp_api_service')
    def test_respond_success(self, mock_serp_service, search_agent, sample_message, sample_context):
        """Test respond generates proper response on successful search."""
        # Mock successful search result
        mock_serp_service.search_with_content.return_value = {
            "success": True,
            "query": "梅西最近动态",
            "snippets": [
                {
                    "title": "梅西最新消息",
                    "snippet": "梅西在迈阿密国际表现出色...",
                    "link": "https://example.com/news1"
                }
            ],
            "provider": "mock"
        }
        
        response = search_agent.respond(sample_message, sample_context)
        
        assert isinstance(response, AgentResponse)
        assert response.agent_name == "SearchAgent"
        assert response.confidence >= 0.5
        assert "梅西" in response.content or "搜索" in response.content
    
    @patch('agents.search_agent.serp_api_service')
    def test_respond_error(self, mock_serp_service, search_agent, sample_message, sample_context):
        """Test respond handles search errors gracefully."""
        # Mock failed search result
        mock_serp_service.search_with_content.return_value = {
            "success": False,
            "error": "API key invalid",
            "snippets": []
        }
        
        response = search_agent.respond(sample_message, sample_context)
        
        assert isinstance(response, AgentResponse)
        assert "问题" in response.content or "错误" in response.content or "error" in response.content.lower()


class TestSerpApiKeyManager:
    """Tests for SERP API Key Manager."""
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        with patch('src.services.serp_api_service.settings') as mock:
            mock.serp_api_keys = "key1,key2,key3"
            mock.redis_url = None
            mock.serp_cache_ttl = 3600
            mock.serp_top_k = 5
            mock.serp_api_provider = "mock"
            yield mock
    
    def test_init_api_keys(self, mock_settings):
        """Test API keys are correctly parsed."""
        from src.services.serp_api_service import SerpApiKeyManager
        
        manager = SerpApiKeyManager()
        assert len(manager._api_keys) == 3
        assert "key1" in manager._api_keys
        assert "key2" in manager._api_keys
        assert "key3" in manager._api_keys
    
    def test_get_next_key_rotation(self, mock_settings):
        """Test key rotation without Redis."""
        from src.services.serp_api_service import SerpApiKeyManager
        
        manager = SerpApiKeyManager()
        
        # Get keys and verify rotation
        key1 = manager.get_next_key()
        key2 = manager.get_next_key()
        key3 = manager.get_next_key()
        key4 = manager.get_next_key()  # Should wrap around
        
        assert key1 == "key1"
        assert key2 == "key2"
        assert key3 == "key3"
        assert key4 == "key1"  # Rotation
    
    def test_get_next_key_no_keys(self):
        """Test get_next_key returns None when no keys configured."""
        with patch('src.services.serp_api_service.settings') as mock:
            mock.serp_api_keys = ""
            mock.redis_url = None
            mock.serp_cache_ttl = 3600
            mock.serp_top_k = 5
            mock.serp_api_provider = "mock"
            
            from src.services.serp_api_service import SerpApiKeyManager
            manager = SerpApiKeyManager()
            
            assert manager.get_next_key() is None
    
    def test_health_check(self, mock_settings):
        """Test health check returns proper status."""
        from src.services.serp_api_service import SerpApiKeyManager
        
        manager = SerpApiKeyManager()
        status = manager.health_check()
        
        assert "api_keys_count" in status
        assert status["api_keys_count"] == 3
        assert "redis_available" in status
        assert "mode" in status


class TestSerpSearchCache:
    """Tests for SERP Search Cache."""
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        with patch('src.services.serp_api_service.settings') as mock:
            mock.redis_url = None
            mock.serp_cache_ttl = 3600
            mock.serp_api_provider = "mock"
            yield mock
    
    def test_cache_set_and_get(self, mock_settings):
        """Test cache set and get operations."""
        from src.services.serp_api_service import SerpSearchCache
        
        cache = SerpSearchCache()
        
        # Set cache
        result = {"snippets": [{"title": "Test"}]}
        cache.set("test query", result)
        
        # Get cache
        cached = cache.get("test query")
        assert cached is not None
        assert cached["snippets"][0]["title"] == "Test"
    
    def test_cache_miss(self, mock_settings):
        """Test cache returns None on miss."""
        from src.services.serp_api_service import SerpSearchCache
        
        cache = SerpSearchCache()
        cached = cache.get("non-existent query")
        assert cached is None
    
    def test_cache_clear(self, mock_settings):
        """Test cache clear operation."""
        from src.services.serp_api_service import SerpSearchCache
        
        cache = SerpSearchCache()
        
        # Set cache
        cache.set("query1", {"data": 1})
        cache.set("query2", {"data": 2})
        
        # Clear specific query
        cleared = cache.clear("query1")
        assert cleared == 1
        assert cache.get("query1") is None
        assert cache.get("query2") is not None
        
        # Clear all
        cache.set("query1", {"data": 1})
        cleared = cache.clear()
        assert cache.get("query1") is None
        assert cache.get("query2") is None


class TestSerpApiService:
    """Tests for SERP API Service."""
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        with patch('src.services.serp_api_service.settings') as mock:
            mock.serp_api_keys = "test_key"
            mock.redis_url = None
            mock.serp_cache_ttl = 3600
            mock.serp_top_k = 5
            mock.serp_api_provider = "mock"
            yield mock
    
    def test_mock_search(self, mock_settings):
        """Test mock search functionality."""
        from src.services.serp_api_service import SerpApiService
        
        service = SerpApiService()
        result = service.search("test query")
        
        assert result["success"] is True
        assert "snippets" in result
        assert len(result["snippets"]) > 0
    
    def test_search_with_cache(self, mock_settings):
        """Test search uses cache."""
        from src.services.serp_api_service import SerpApiService
        
        service = SerpApiService()
        
        # First search
        result1 = service.search("cached query")
        
        # Second search should hit cache
        result2 = service.search("cached query")
        
        assert result1["success"] is True
        assert result2["success"] is True
    
    def test_search_no_cache(self, mock_settings):
        """Test search without cache."""
        from src.services.serp_api_service import SerpApiService
        
        service = SerpApiService()
        
        # Search without cache
        result = service.search("test query", use_cache=False)
        
        assert result["success"] is True
    
    def test_health_check(self, mock_settings):
        """Test health check."""
        from src.services.serp_api_service import SerpApiService
        
        service = SerpApiService()
        status = service.health_check()
        
        assert "key_manager" in status
        assert "provider" in status
        assert "top_k" in status
    
    @patch('src.services.serp_api_service.requests.get')
    def test_fetch_and_clean_webpage(self, mock_get, mock_settings):
        """Test webpage fetching and cleaning."""
        from src.services.serp_api_service import SerpApiService
        
        # Mock response
        mock_response = MagicMock()
        mock_response.text = """
        <html>
        <head><style>body{color:red}</style></head>
        <body>
            <script>alert('test')</script>
            <p>This is the main content.</p>
            <div>More content here.</div>
        </body>
        </html>
        """
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        service = SerpApiService()
        content = service.fetch_and_clean_webpage("https://example.com")
        
        assert content is not None
        assert "main content" in content
        assert "<script>" not in content
        assert "<style>" not in content


class TestSkillRegistryWithSearchAgent:
    """Tests for SkillRegistry with SearchAgent skill."""
    
    def test_search_skill_registered(self):
        """Test that web_search skill is registered in skill registry."""
        from src.agents.skills import skill_registry
        
        skill = skill_registry.get("web_search")
        assert skill is not None
        assert skill.agent_name == "SearchAgent"
        assert "搜索" in skill.keywords or "search" in skill.keywords
    
    def test_search_skill_priority(self):
        """Test that web_search skill has high priority."""
        from src.agents.skills import skill_registry
        
        skill = skill_registry.get("web_search")
        assert skill.priority == 10  # Highest priority
    
    def test_match_skills_with_search_text(self):
        """Test skill matching with search-related text."""
        from src.agents.skills import skill_registry
        
        matched = skill_registry.match_skills("帮我搜索一下最新新闻")
        skill_ids = [s.id for s in matched]
        
        assert "web_search" in skill_ids
