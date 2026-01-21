"""
LLM Gateway - 统一的大语言模型调用层

这是多机器人平台的核心模块，提供：
- 统一的LLM调用接口
- Token统计和成本追踪
- 限流和失败重试机制
- 多Provider支持（OpenAI, Anthropic, vLLM）
"""

from .gateway import LLMGateway, LLMRequest, LLMResponse, get_llm_gateway
from .providers import LLMProvider, OpenAIProvider, AnthropicProvider, VLLMProvider, ProviderConfig
from .rate_limiter import RateLimiter, TokenBucket
from .token_counter import TokenCounter, UsageStats

__all__ = [
    'LLMGateway',
    'LLMRequest',
    'LLMResponse',
    'get_llm_gateway',
    'LLMProvider',
    'OpenAIProvider',
    'AnthropicProvider',
    'VLLMProvider',
    'ProviderConfig',
    'RateLimiter',
    'TokenBucket',
    'TokenCounter',
    'UsageStats',
]
