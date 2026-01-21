"""
LLM Providers - 各LLM服务提供商的实现

支持的Provider:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude-3)
- vLLM (自托管模型)
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import asyncio
import openai
import anthropic
import aiohttp
from loguru import logger


@dataclass
class ProviderConfig:
    """Provider配置"""
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    model: str = "gpt-4"
    max_tokens: int = 1000
    temperature: float = 0.8
    timeout: int = 60


class LLMProvider(ABC):
    """LLM Provider抽象基类"""
    
    def __init__(self, config: ProviderConfig):
        self.config = config
        self._name = "base"
    
    @property
    def name(self) -> str:
        """Provider名称"""
        return self._name
    
    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成响应
        
        Args:
            messages: 对话消息列表
            **kwargs: 额外参数
            
        Returns:
            包含content, usage等信息的字典
        """
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        计算文本的token数量
        
        Args:
            text: 文本内容
            
        Returns:
            Token数量
        """
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI GPT Provider"""
    
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._name = "openai"
        if not config.api_key:
            raise ValueError("OpenAI API key is required")
        self.client = openai.AsyncOpenAI(api_key=config.api_key)
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """使用OpenAI生成响应"""
        try:
            model = kwargs.get("model", self.config.model)
            max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
            temperature = kwargs.get("temperature", self.config.temperature)
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            return {
                "content": response.choices[0].message.content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                "model": response.model,
                "finish_reason": response.choices[0].finish_reason
            }
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
    
    def count_tokens(self, text: str) -> int:
        """估算token数（简单实现）"""
        # 简单估算：英文约4字符/token，中文约1.5字符/token
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude Provider"""
    
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._name = "anthropic"
        if not config.api_key:
            raise ValueError("Anthropic API key is required")
        self.client = anthropic.AsyncAnthropic(api_key=config.api_key)
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """使用Anthropic Claude生成响应"""
        try:
            model = kwargs.get("model", self.config.model)
            max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
            
            # 提取system message
            system_prompt = None
            claude_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system_prompt = msg["content"]
                else:
                    role = "user" if msg["role"] == "user" else "assistant"
                    claude_messages.append({
                        "role": role,
                        "content": msg["content"]
                    })
            
            response = await self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt or "",
                messages=claude_messages
            )
            
            return {
                "content": response.content[0].text,
                "usage": {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                },
                "model": response.model,
                "finish_reason": response.stop_reason
            }
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise
    
    def count_tokens(self, text: str) -> int:
        """估算token数"""
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)


class VLLMProvider(LLMProvider):
    """vLLM自托管模型Provider"""
    
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._name = "vllm"
        if not config.api_url:
            raise ValueError("vLLM API URL is required")
        self.api_url = config.api_url.rstrip('/')
        self.api_token = config.api_key
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """使用vLLM生成响应"""
        model = kwargs.get("model", self.config.model)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        temperature = kwargs.get("temperature", self.config.temperature)
        
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"vLLM API error: {response.status} - {error_text}")
                    
                    result = await response.json()
                    
                    usage = result.get("usage", {})
                    return {
                        "content": result["choices"][0]["message"]["content"],
                        "usage": {
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0),
                            "total_tokens": usage.get("total_tokens", 0)
                        },
                        "model": result.get("model", model),
                        "finish_reason": result["choices"][0].get("finish_reason", "stop")
                    }
        except Exception as e:
            logger.error(f"vLLM API error: {e}")
            raise
    
    def count_tokens(self, text: str) -> int:
        """估算token数"""
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)
