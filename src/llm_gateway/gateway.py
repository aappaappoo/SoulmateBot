"""
LLM Gateway - 统一的大语言模型调用网关

这是多机器人平台的核心组件，提供：
- 统一的LLM调用接口
- 自动重试机制
- Token统计和成本追踪
- 限流控制
- 多Provider路由
"""
import asyncio
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from loguru import logger

from .providers import LLMProvider, ProviderConfig, OpenAIProvider, AnthropicProvider, VLLMProvider
from .rate_limiter import RateLimiter
from .token_counter import TokenCounter, UsageStats


@dataclass
class LLMRequest:
    """
    LLM请求对象
    
    Attributes:
        messages: 对话消息列表
        model: 模型名称（可选，使用默认）
        provider: Provider名称（可选，使用默认）
        max_tokens: 最大输出token数
        temperature: 温度参数
        user_id: 用户ID（用于统计和限流）
        bot_id: Bot ID（用于统计）
        request_id: 请求ID（用于追踪）
        metadata: 额外元数据
    """
    messages: List[Dict[str, str]]
    model: Optional[str] = None
    provider: Optional[str] = None
    max_tokens: int = 1000
    temperature: float = 0.8
    user_id: Optional[str] = None
    bot_id: Optional[str] = None
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmotionInfo:
    """
    情绪信息对象
    
    用于存储LLM检测到的情绪类型、强度和语气描述。
    这些信息不会包含在响应文本中，而是作为独立的元数据返回。
    
    Attributes:
        emotion_type: 情绪类型 (happy, sad, angry, gentle, excited, crying, neutral)
        intensity: 情绪强度 (high, medium, low)
        tone_description: 语气描述（中文自然语言描述）
    """
    emotion_type: Optional[str] = None
    intensity: Optional[str] = None
    tone_description: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "emotion_type": self.emotion_type,
            "intensity": self.intensity,
            "tone_description": self.tone_description
        }
    
    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "EmotionInfo":
        """从字典创建EmotionInfo对象"""
        if not data:
            return cls()
        return cls(
            emotion_type=data.get("emotion_type"),
            intensity=data.get("intensity"),
            tone_description=data.get("tone_description")
        )


@dataclass
class LLMResponse:
    """
    LLM响应对象
    
    Attributes:
        content: 响应内容（不包含情绪前缀的干净文本）
        model: 实际使用的模型
        provider: 实际使用的Provider
        usage: Token使用统计
        finish_reason: 结束原因
        request_id: 请求ID
        latency_ms: 响应延迟（毫秒）
        success: 是否成功
        error: 错误信息（如果失败）
        emotion_info: 情绪信息（包含情绪类型、强度和语气描述）
    """
    content: str
    model: str
    provider: str
    usage: UsageStats
    finish_reason: str = "stop"
    request_id: str = ""
    latency_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None
    emotion_info: Optional[EmotionInfo] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        result = {
            "content": self.content,
            "model": self.model,
            "provider": self.provider,
            "usage": self.usage.to_dict(),
            "finish_reason": self.finish_reason,
            "request_id": self.request_id,
            "latency_ms": self.latency_ms,
            "success": self.success,
            "error": self.error
        }
        if self.emotion_info:
            result["emotion_info"] = self.emotion_info.to_dict()
        return result


class LLMGateway:
    """
    统一的LLM调用网关
    
    提供统一的接口调用各种LLM服务，包括：
    - 多Provider支持（OpenAI, Anthropic, vLLM）
    - 自动重试机制
    - 限流控制
    - Token统计和成本追踪
    - 失败转移
    
    Usage:
        gateway = LLMGateway()
        gateway.register_provider("openai", OpenAIProvider(configs))
        
        request = LLMRequest(
            messages=[{"role": "user", "content": "你好"}],
            user_id="user123"
        )
        response = await gateway.generate(request)
    """
    
    def __init__(
        self,
        default_provider: str = "openai",
        max_retries: int = 3,
        retry_delay: float = 1.0,
        rate_limiter: Optional[RateLimiter] = None
    ):
        """
        初始化LLM Gateway
        
        Args:
            default_provider: 默认使用的Provider
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
            rate_limiter: 限流器实例
        """
        self.default_provider = default_provider
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Provider注册表
        self._providers: Dict[str, LLMProvider] = {}
        
        # 统计和限流组件
        self.token_counter = TokenCounter()
        self.rate_limiter = rate_limiter or RateLimiter()
        
        # 请求统计
        self._request_count = 0
        self._success_count = 0
        self._failure_count = 0
        
        logger.info("LLM Gateway initialized")
    
    def register_provider(self, name: str, provider: LLMProvider) -> None:
        """
        注册LLM Provider
        
        Args:
            name: Provider名称
            provider: Provider实例
        """
        self._providers[name] = provider
        logger.info(f"Registered LLM provider: {name}")
    
    def get_provider(self, name: Optional[str] = None) -> LLMProvider:
        """
        获取Provider
        
        Args:
            name: Provider名称，为空则使用默认
            
        Returns:
            LLMProvider实例
            
        Raises:
            ValueError: 如果Provider未找到
        """
        provider_name = name or self.default_provider
        
        if provider_name not in self._providers:
            raise ValueError(f"Provider not found: {provider_name}")
        
        return self._providers[provider_name]
    
    def list_providers(self) -> List[str]:
        """列出所有已注册的Provider"""
        return list(self._providers.keys())
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        生成LLM响应
        
        Args:
            request: LLM请求对象
            
        Returns:
            LLM响应对象
        """
        start_time = datetime.now(timezone.utc)
        self._request_count += 1
        
        # 估算输入token数
        total_content = " ".join(msg.get("content", "") for msg in request.messages)
        estimated_tokens = len(total_content) // 4  # 简单估算
        
        # 检查限流
        if not await self.rate_limiter.wait_and_acquire(
            user_id=request.user_id,
            estimated_tokens=estimated_tokens,
            timeout=30.0
        ):
            self._failure_count += 1
            return LLMResponse(
                content="",
                model=request.model or "",
                provider=request.provider or self.default_provider,
                usage=UsageStats(),
                request_id=request.request_id,
                success=False,
                error="Rate limit exceeded"
            )
        
        # 获取Provider
        try:
            provider = self.get_provider(request.provider)
        except ValueError as e:
            self._failure_count += 1
            return LLMResponse(
                content="",
                model=request.model or "",
                provider=request.provider or self.default_provider,
                usage=UsageStats(),
                request_id=request.request_id,
                success=False,
                error=str(e)
            )
        
        # 执行请求（带重试）
        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    f"LLM request attempt {attempt + 1}/{self.max_retries} "
                    f"(provider: {provider.name}, request_id: {request.request_id})"
                )
                
                result = await provider.generate(
                    messages=request.messages,
                    model=request.model,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature
                )
                
                # 计算延迟
                latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                
                # 记录token使用
                usage = self.token_counter.record_usage(
                    prompt_tokens=result["usage"]["prompt_tokens"],
                    completion_tokens=result["usage"]["completion_tokens"],
                    model=result["model"],
                    provider=provider.name,
                    user_id=request.user_id,
                    bot_id=request.bot_id,
                    request_id=request.request_id
                )
                
                self._success_count += 1
                
                logger.info(
                    f"LLM request completed: {result['usage']['total_tokens']} tokens, "
                    f"{latency_ms:.0f}ms (request_id: {request.request_id})"
                )
                
                return LLMResponse(
                    content=result["content"],
                    model=result["model"],
                    provider=provider.name,
                    usage=usage,
                    finish_reason=result.get("finish_reason", "stop"),
                    request_id=request.request_id,
                    latency_ms=latency_ms,
                    success=True
                )
                
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"LLM request failed (attempt {attempt + 1}): {e}"
                )
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        # 所有重试都失败
        self._failure_count += 1
        latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        logger.error(
            f"LLM request failed after {self.max_retries} retries: {last_error}"
        )
        
        return LLMResponse(
            content="",
            model=request.model or "",
            provider=provider.name,
            usage=UsageStats(),
            request_id=request.request_id,
            latency_ms=latency_ms,
            success=False,
            error=f"All retries failed: {last_error}"
        )
    
    async def generate_simple(
        self,
        messages: List[Dict[str, str]],
        user_id: Optional[str] = None,
        bot_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        简化的生成接口
        
        Args:
            messages: 对话消息列表
            user_id: 用户ID
            bot_id: Bot ID
            **kwargs: 额外参数
            
        Returns:
            生成的响应内容
            
        Raises:
            Exception: 如果生成失败
        """
        request = LLMRequest(
            messages=messages,
            user_id=user_id,
            bot_id=bot_id,
            **kwargs
        )
        
        response = await self.generate(request)
        
        if not response.success:
            raise Exception(response.error or "Unknown error")
        
        return response.content
    
    def get_stats(self) -> Dict:
        """获取Gateway统计信息"""
        return {
            "total_requests": self._request_count,
            "successful_requests": self._success_count,
            "failed_requests": self._failure_count,
            "success_rate": (
                self._success_count / self._request_count 
                if self._request_count > 0 else 0
            ),
            "token_stats": self.token_counter.get_total_stats(),
            "rate_limiter_stats": self.rate_limiter.get_stats(),
            "registered_providers": self.list_providers()
        }


# 全局Gateway实例
_gateway_instance: Optional[LLMGateway] = None


def get_llm_gateway() -> LLMGateway:
    """获取全局LLM Gateway实例"""
    global _gateway_instance
    
    if _gateway_instance is None:
        _gateway_instance = LLMGateway()
        
        # 自动注册可用的Provider
        try:
            from config import settings
            
            if settings.vllm_api_url:
                try:
                    config = ProviderConfig(
                        api_url=settings.vllm_api_url,
                        api_key=settings.vllm_api_token,
                        model=settings.vllm_model
                    )
                    _gateway_instance.register_provider("vllm", VLLMProvider(config))
                    _gateway_instance.default_provider = "vllm"
                except Exception as e:
                    logger.warning(f"Failed to register vLLM provider: {e}")
            
            if settings.openai_api_key:
                try:
                    config = ProviderConfig(
                        api_key=settings.openai_api_key,
                        model=settings.openai_model
                    )
                    _gateway_instance.register_provider("openai", OpenAIProvider(config))
                    if not _gateway_instance._providers:
                        _gateway_instance.default_provider = "openai"
                except Exception as e:
                    logger.warning(f"Failed to register OpenAI provider: {e}")
        
            if settings.anthropic_api_key:
                try:
                    config = ProviderConfig(
                        api_key=settings.anthropic_api_key,
                        model=settings.anthropic_model
                    )
                    _gateway_instance.register_provider("anthropic", AnthropicProvider(config))
                    if not _gateway_instance._providers:
                        _gateway_instance.default_provider = "anthropic"
                except Exception as e:
                    logger.warning(f"Failed to register Anthropic provider: {e}")
        
        except ImportError as e:
            logger.warning(f"Could not import configs settings: {e}")
        except Exception as e:
            logger.warning(f"Error auto-registering providers: {e}")
    
    return _gateway_instance
