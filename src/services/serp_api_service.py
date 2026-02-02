"""
SERP API Service - 搜索API服务

提供以下功能：
1. 多 API Key 轮用管理（使用 Redis）
2. 搜索结果缓存（减少重复查询的 API 调用）
3. 网页抓取和文本清洗
4. 支持多种搜索提供商（SerpAPI, Google, Bing）
"""
import json
import hashlib
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
import redis
import requests
from loguru import logger

from config.settings import settings


class SerpApiKeyManager:
    """
    SERP API Key 管理器
    
    使用 Redis 管理多个 API key 的轮用，确保负载均衡和限流保护。
    """
    
    # Redis key 前缀
    KEY_PREFIX = "serp_api_key"
    CURRENT_KEY_INDEX = "serp_current_key_index"
    KEY_USAGE_COUNT = "serp_key_usage"
    
    def __init__(self):
        """初始化 API Key 管理器"""
        self._redis: Optional[redis.Redis] = None
        self._api_keys: List[str] = []
        self._current_index: int = 0
        self._fallback_usage: Dict[str, int] = {}
        
        self._init_api_keys()
        self._init_redis()
    
    def _init_api_keys(self):
        """解析配置中的 API keys"""
        if settings.serp_api_keys:
            keys = settings.serp_api_keys.split(",")
            self._api_keys = [k.strip() for k in keys if k.strip()]
            logger.info(f"SerpApiKeyManager: Loaded {len(self._api_keys)} API keys")
        else:
            logger.warning("SerpApiKeyManager: No SERP API keys configured")
    
    def _init_redis(self):
        """初始化 Redis 连接"""
        if settings.redis_url:
            try:
                self._redis = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5
                )
                self._redis.ping()
                logger.info("SerpApiKeyManager: Redis connected successfully")
            except Exception as e:
                logger.warning(f"SerpApiKeyManager: Redis connection failed: {e}, using fallback mode")
                self._redis = None
        else:
            logger.warning("SerpApiKeyManager: redis_url not configured, using fallback mode")
    
    def get_next_key(self) -> Optional[str]:
        """
        获取下一个可用的 API key（轮用策略）
        
        Returns:
            str: 可用的 API key，如果没有配置则返回 None
        """
        if not self._api_keys:
            return None
        
        if self._redis:
            try:
                # 使用 Redis 原子操作来轮用 key
                index = self._redis.incr(self.CURRENT_KEY_INDEX)
                key_index = (index - 1) % len(self._api_keys)
                selected_key = self._api_keys[key_index]
                
                # 记录使用次数
                self._redis.hincrby(self.KEY_USAGE_COUNT, str(key_index), 1)
                
                logger.debug(f"SerpApiKeyManager: Using key index {key_index}")
                return selected_key
            except Exception as e:
                logger.error(f"Redis error getting next key: {e}")
        
        # Fallback: 使用内存中的计数
        key_index = self._current_index % len(self._api_keys)
        self._current_index += 1
        selected_key = self._api_keys[key_index]
        
        # 记录使用
        self._fallback_usage[str(key_index)] = self._fallback_usage.get(str(key_index), 0) + 1
        
        return selected_key
    
    def get_key_usage_stats(self) -> Dict[str, int]:
        """
        获取各 key 的使用统计
        
        Returns:
            Dict[str, int]: key 索引到使用次数的映射
        """
        if self._redis:
            try:
                stats = self._redis.hgetall(self.KEY_USAGE_COUNT)
                return {k: int(v) for k, v in stats.items()}
            except Exception as e:
                logger.error(f"Redis error getting usage stats: {e}")
        
        return self._fallback_usage.copy()
    
    def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        
        Returns:
            dict: 包含健康状态信息
        """
        status = {
            "api_keys_count": len(self._api_keys),
            "redis_available": False,
            "mode": "fallback"
        }
        
        if self._redis:
            try:
                self._redis.ping()
                status["redis_available"] = True
                status["mode"] = "redis"
            except Exception:
                pass
        
        return status


class SerpSearchCache:
    """
    搜索结果缓存
    
    使用 Redis 缓存搜索结果，减少对相同查询的重复 API 调用。
    特别适合热门话题（如"梅西最近动态"）的缓存。
    """
    
    # Redis key 前缀
    CACHE_PREFIX = "serp_cache"
    
    def __init__(self, ttl: int = None):
        """
        初始化搜索缓存
        
        Args:
            ttl: 缓存过期时间（秒），默认使用配置值
        """
        self._redis: Optional[redis.Redis] = None
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._ttl = ttl or settings.serp_cache_ttl
        self._init_redis()
    
    def _init_redis(self):
        """初始化 Redis 连接"""
        if settings.redis_url:
            try:
                self._redis = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5
                )
                self._redis.ping()
                logger.info("SerpSearchCache: Redis connected successfully")
            except Exception as e:
                logger.warning(f"SerpSearchCache: Redis connection failed: {e}, using memory cache")
                self._redis = None
        else:
            logger.warning("SerpSearchCache: redis_url not configured, using memory cache")
    
    def _generate_cache_key(self, query: str, provider: str = None) -> str:
        """
        生成缓存键
        
        Args:
            query: 搜索查询
            provider: 搜索提供商
            
        Returns:
            str: 缓存键
        """
        provider = provider or settings.serp_api_provider
        # 使用 MD5 哈希来生成固定长度的键
        query_hash = hashlib.md5(query.lower().encode()).hexdigest()
        return f"{self.CACHE_PREFIX}:{provider}:{query_hash}"
    
    def get(self, query: str, provider: str = None) -> Optional[Dict[str, Any]]:
        """
        获取缓存的搜索结果
        
        Args:
            query: 搜索查询
            provider: 搜索提供商
            
        Returns:
            Dict: 缓存的搜索结果，如果没有则返回 None
        """
        cache_key = self._generate_cache_key(query, provider)
        
        if self._redis:
            try:
                cached = self._redis.get(cache_key)
                if cached:
                    logger.info(f"SerpSearchCache: Cache hit for query: {query[:50]}...")
                    return json.loads(cached)
            except Exception as e:
                logger.error(f"Redis cache get error: {e}")
        
        # Fallback: 内存缓存
        if cache_key in self._memory_cache:
            cached_item = self._memory_cache[cache_key]
            # 检查是否过期
            if datetime.now().timestamp() - cached_item.get("timestamp", 0) < self._ttl:
                logger.info(f"SerpSearchCache: Memory cache hit for query: {query[:50]}...")
                return cached_item.get("data")
            else:
                del self._memory_cache[cache_key]
        
        return None
    
    def set(self, query: str, result: Dict[str, Any], provider: str = None, ttl: int = None) -> bool:
        """
        缓存搜索结果
        
        Args:
            query: 搜索查询
            result: 搜索结果
            provider: 搜索提供商
            ttl: 自定义过期时间（秒）
            
        Returns:
            bool: 是否成功缓存
        """
        cache_key = self._generate_cache_key(query, provider)
        cache_ttl = ttl or self._ttl
        
        if self._redis:
            try:
                self._redis.setex(cache_key, cache_ttl, json.dumps(result, ensure_ascii=False))
                logger.info(f"SerpSearchCache: Cached result for query: {query[:50]}...")
                return True
            except Exception as e:
                logger.error(f"Redis cache set error: {e}")
        
        # Fallback: 内存缓存
        self._memory_cache[cache_key] = {
            "data": result,
            "timestamp": datetime.now().timestamp()
        }
        logger.info(f"SerpSearchCache: Memory cached result for query: {query[:50]}...")
        return True
    
    def clear(self, query: str = None, provider: str = None) -> int:
        """
        清除缓存
        
        Args:
            query: 特定查询（如果为 None，则清除所有）
            provider: 搜索提供商
            
        Returns:
            int: 清除的缓存数量
        """
        if query:
            cache_key = self._generate_cache_key(query, provider)
            if self._redis:
                try:
                    return self._redis.delete(cache_key)
                except Exception as e:
                    logger.error(f"Redis cache clear error: {e}")
            
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]
                return 1
            return 0
        
        # 清除所有缓存
        cleared = 0
        if self._redis:
            try:
                for key in self._redis.scan_iter(match=f"{self.CACHE_PREFIX}:*"):
                    self._redis.delete(key)
                    cleared += 1
            except Exception as e:
                logger.error(f"Redis cache clear all error: {e}")
        
        memory_cleared = len(self._memory_cache)
        self._memory_cache.clear()
        
        return cleared + memory_cleared


class SerpApiService:
    """
    搜索 API 服务
    
    整合 API key 管理、缓存和搜索功能，提供完整的搜索服务。
    """
    
    def __init__(self):
        """初始化搜索服务"""
        self.key_manager = SerpApiKeyManager()
        self.cache = SerpSearchCache()
        self.provider = settings.serp_api_provider
        self.top_k = settings.serp_top_k
    
    def search(self, query: str, use_cache: bool = True, top_k: int = None) -> Dict[str, Any]:
        """
        执行搜索
        
        Args:
            query: 搜索查询
            use_cache: 是否使用缓存
            top_k: 返回结果数量
            
        Returns:
            Dict: 搜索结果
        """
        top_k = top_k or self.top_k
        
        # 检查缓存
        if use_cache:
            cached = self.cache.get(query)
            if cached:
                return cached
        
        # 获取 API key
        api_key = self.key_manager.get_next_key()
        if not api_key:
            logger.error("SerpApiService: No API key available")
            return {
                "success": False,
                "error": "No SERP API key configured",
                "snippets": []
            }
        
        # 执行搜索
        try:
            result = self._execute_search(query, api_key, top_k)
            
            # 缓存成功的结果
            if result.get("success") and use_cache:
                self.cache.set(query, result)
            
            return result
        except Exception as e:
            logger.error(f"SerpApiService: Search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "snippets": []
            }
    
    def _execute_search(self, query: str, api_key: str, top_k: int) -> Dict[str, Any]:
        """
        执行实际的搜索请求
        
        Args:
            query: 搜索查询
            api_key: API key
            top_k: 返回结果数量
            
        Returns:
            Dict: 搜索结果
        """
        if self.provider == "serpapi":
            return self._search_serpapi(query, api_key, top_k)
        elif self.provider == "google":
            return self._search_google(query, api_key, top_k)
        elif self.provider == "bing":
            return self._search_bing(query, api_key, top_k)
        else:
            # 默认使用模拟搜索（用于测试）
            return self._mock_search(query, top_k)
    
    def _search_serpapi(self, query: str, api_key: str, top_k: int) -> Dict[str, Any]:
        """
        使用 SerpAPI 搜索
        
        SerpAPI 官网: https://serpapi.com/
        """
        try:
            url = "https://serpapi.com/search"
            params = {
                "q": query,
                "api_key": api_key,
                "engine": "google",
                "num": top_k,
                "gl": "cn",  # 中国区域
                "hl": "zh-cn"  # 中文
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            snippets = []
            for result in data.get("organic_results", [])[:top_k]:
                snippets.append({
                    "title": result.get("title", ""),
                    "snippet": result.get("snippet", ""),
                    "link": result.get("link", ""),
                    "source": result.get("source", "")
                })
            
            return {
                "success": True,
                "query": query,
                "snippets": snippets,
                "provider": "serpapi",
                "timestamp": datetime.now().isoformat()
            }
        except requests.RequestException as e:
            logger.error(f"SerpAPI request error: {e}")
            return {
                "success": False,
                "error": str(e),
                "snippets": []
            }
    
    def _search_google(self, query: str, api_key: str, top_k: int) -> Dict[str, Any]:
        """
        使用 Google Custom Search API
        
        需要配置 Google Custom Search Engine ID
        """
        # TODO: 实现 Google Custom Search API
        logger.warning("Google Custom Search API not implemented, using mock search")
        return self._mock_search(query, top_k)
    
    def _search_bing(self, query: str, api_key: str, top_k: int) -> Dict[str, Any]:
        """
        使用 Bing Web Search API
        
        Azure Bing Search: https://azure.microsoft.com/services/cognitive-services/bing-web-search-api/
        """
        try:
            url = "https://api.bing.microsoft.com/v7.0/search"
            headers = {
                "Ocp-Apim-Subscription-Key": api_key
            }
            params = {
                "q": query,
                "count": top_k,
                "mkt": "zh-CN"
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            snippets = []
            for result in data.get("webPages", {}).get("value", [])[:top_k]:
                snippets.append({
                    "title": result.get("name", ""),
                    "snippet": result.get("snippet", ""),
                    "link": result.get("url", ""),
                    "source": result.get("displayUrl", "")
                })
            
            return {
                "success": True,
                "query": query,
                "snippets": snippets,
                "provider": "bing",
                "timestamp": datetime.now().isoformat()
            }
        except requests.RequestException as e:
            logger.error(f"Bing API request error: {e}")
            return {
                "success": False,
                "error": str(e),
                "snippets": []
            }
    
    def _mock_search(self, query: str, top_k: int) -> Dict[str, Any]:
        """
        模拟搜索（用于测试和开发）
        """
        logger.info(f"SerpApiService: Using mock search for query: {query}")
        
        mock_snippets = []
        for i in range(min(top_k, 3)):
            mock_snippets.append({
                "title": f"关于 {query} 的搜索结果 {i+1}",
                "snippet": f"这是关于 {query} 的模拟搜索结果摘要。包含了相关信息和最新动态...",
                "link": f"https://example.com/result/{i+1}",
                "source": "example.com"
            })
        
        return {
            "success": True,
            "query": query,
            "snippets": mock_snippets,
            "provider": "mock",
            "timestamp": datetime.now().isoformat(),
            "note": "这是模拟搜索结果，请配置真实的 SERP API key"
        }
    
    def fetch_and_clean_webpage(self, url: str, max_length: int = 2000) -> Optional[str]:
        """
        抓取网页并清洗文本
        
        Args:
            url: 网页 URL
            max_length: 最大返回文本长度
            
        Returns:
            str: 清洗后的文本，失败则返回 None
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 简单的 HTML 文本提取
            content = response.text
            
            # 移除 script 和 style 标签（处理各种格式的闭合标签）
            content = re.sub(r'<script\b[^>]*>.*?</script[^>]*>', '', content, flags=re.DOTALL | re.IGNORECASE)
            content = re.sub(r'<style\b[^>]*>.*?</style[^>]*>', '', content, flags=re.DOTALL | re.IGNORECASE)
            
            # 移除所有 HTML 标签
            content = re.sub(r'<[^>]+>', ' ', content)
            
            # 清理空白字符
            content = re.sub(r'\s+', ' ', content).strip()
            
            # 解码 HTML 实体
            content = content.replace('&nbsp;', ' ')
            content = content.replace('&lt;', '<')
            content = content.replace('&gt;', '>')
            content = content.replace('&amp;', '&')
            content = content.replace('&quot;', '"')
            
            # 截断到最大长度
            if len(content) > max_length:
                content = content[:max_length] + "..."
            
            return content
        except Exception as e:
            logger.error(f"Webpage fetch error for {url}: {e}")
            return None
    
    def search_with_content(self, query: str, fetch_content: bool = False, 
                           use_cache: bool = True, top_k: int = None) -> Dict[str, Any]:
        """
        搜索并可选抓取网页内容
        
        Args:
            query: 搜索查询
            fetch_content: 是否抓取网页内容
            use_cache: 是否使用缓存
            top_k: 返回结果数量
            
        Returns:
            Dict: 搜索结果（可能包含网页内容）
        """
        result = self.search(query, use_cache, top_k)
        
        if not result.get("success") or not fetch_content:
            return result
        
        # 抓取网页内容
        for snippet in result.get("snippets", []):
            if snippet.get("link"):
                content = self.fetch_and_clean_webpage(snippet["link"])
                if content:
                    snippet["full_content"] = content
        
        return result
    
    def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        
        Returns:
            dict: 健康状态信息
        """
        return {
            "key_manager": self.key_manager.health_check(),
            "provider": self.provider,
            "top_k": self.top_k,
            "cache_ttl": self.cache._ttl
        }


# 全局服务实例
serp_api_service = SerpApiService()
