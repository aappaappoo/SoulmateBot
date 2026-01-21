"""
Rate Limiter - 请求限流器

实现基于令牌桶算法的限流机制，防止API调用超限
"""
import asyncio
import time
from typing import Dict, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class TokenBucket:
    """
    令牌桶算法实现
    
    Attributes:
        capacity: 桶容量（最大令牌数）
        refill_rate: 令牌补充速率（每秒补充的令牌数）
        tokens: 当前令牌数
        last_refill: 上次补充时间
    """
    capacity: float
    refill_rate: float  # tokens per second
    tokens: float = field(default=0.0)
    last_refill: float = field(default_factory=time.time)
    
    def __post_init__(self):
        # 初始化时填满令牌桶
        self.tokens = self.capacity
    
    def _refill(self) -> None:
        """补充令牌"""
        now = time.time()
        time_passed = now - self.last_refill
        new_tokens = time_passed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill = now
    
    def consume(self, tokens: float = 1.0) -> bool:
        """
        消费令牌
        
        Args:
            tokens: 需要消费的令牌数
            
        Returns:
            True如果有足够令牌，False如果令牌不足
        """
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def wait_time(self, tokens: float = 1.0) -> float:
        """
        计算需要等待的时间
        
        Args:
            tokens: 需要的令牌数
            
        Returns:
            需要等待的秒数
        """
        self._refill()
        
        if self.tokens >= tokens:
            return 0.0
        
        needed = tokens - self.tokens
        return needed / self.refill_rate


class RateLimiter:
    """
    多维度限流器
    
    支持按用户、按Bot、按Provider等多维度进行限流
    """
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        tokens_per_minute: int = 100000,
        concurrent_requests: int = 10
    ):
        """
        初始化限流器
        
        Args:
            requests_per_minute: 每分钟最大请求数
            tokens_per_minute: 每分钟最大token数
            concurrent_requests: 最大并发请求数
        """
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.concurrent_requests = concurrent_requests
        
        # 全局请求限流桶
        self._global_bucket = TokenBucket(
            capacity=requests_per_minute,
            refill_rate=requests_per_minute / 60.0
        )
        
        # Token限流桶
        self._token_bucket = TokenBucket(
            capacity=tokens_per_minute,
            refill_rate=tokens_per_minute / 60.0
        )
        
        # 用户级别限流桶
        self._user_buckets: Dict[str, TokenBucket] = {}
        
        # 并发控制信号量
        self._semaphore = asyncio.Semaphore(concurrent_requests)
        
        # 统计信息
        self._request_count = 0
        self._rejected_count = 0
    
    def _get_user_bucket(self, user_id: str) -> TokenBucket:
        """获取用户的限流桶"""
        if user_id not in self._user_buckets:
            # 用户级别：每分钟10个请求
            self._user_buckets[user_id] = TokenBucket(
                capacity=10,
                refill_rate=10 / 60.0
            )
        return self._user_buckets[user_id]
    
    async def acquire(
        self,
        user_id: Optional[str] = None,
        estimated_tokens: int = 0
    ) -> bool:
        """
        获取限流许可
        
        Args:
            user_id: 用户ID（可选）
            estimated_tokens: 预估token数量
            
        Returns:
            True如果获得许可，False如果被限流
        """
        # 检查全局请求限制
        if not self._global_bucket.consume(1):
            self._rejected_count += 1
            logger.warning("Global rate limit exceeded")
            return False
        
        # 检查token限制
        if estimated_tokens > 0:
            if not self._token_bucket.consume(estimated_tokens):
                self._rejected_count += 1
                logger.warning(f"Token rate limit exceeded: {estimated_tokens} tokens requested")
                return False
        
        # 检查用户限制
        if user_id:
            user_bucket = self._get_user_bucket(user_id)
            if not user_bucket.consume(1):
                self._rejected_count += 1
                logger.warning(f"User rate limit exceeded for user: {user_id}")
                return False
        
        self._request_count += 1
        return True
    
    async def wait_and_acquire(
        self,
        user_id: Optional[str] = None,
        estimated_tokens: int = 0,
        timeout: float = 30.0
    ) -> bool:
        """
        等待并获取限流许可
        
        Args:
            user_id: 用户ID
            estimated_tokens: 预估token数量
            timeout: 最大等待时间（秒）
            
        Returns:
            True如果成功获取，False如果超时
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if await self.acquire(user_id, estimated_tokens):
                return True
            
            # 计算需要等待的时间
            wait_time = max(
                self._global_bucket.wait_time(1),
                self._token_bucket.wait_time(estimated_tokens) if estimated_tokens > 0 else 0
            )
            
            if user_id:
                user_bucket = self._get_user_bucket(user_id)
                wait_time = max(wait_time, user_bucket.wait_time(1))
            
            # 等待一段时间后重试
            await asyncio.sleep(min(wait_time, 1.0))
        
        return False
    
    def get_stats(self) -> Dict[str, int]:
        """获取限流统计信息"""
        return {
            "total_requests": self._request_count,
            "rejected_requests": self._rejected_count,
            "active_users": len(self._user_buckets)
        }
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._semaphore.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        self._semaphore.release()
