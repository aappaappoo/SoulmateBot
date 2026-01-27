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
import time
import json
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

    def _log_request(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int,
        temperature: float,
        extra_params: Optional[Dict] = None
    ) -> str:
        """记录请求日志，返回请求ID用于关联响应"""
        import uuid
        request_id = str(uuid.uuid4())[:8]

        # 计算消息统计
        message_count = len(messages)
        total_chars = sum(len(msg.get("content", "")) for msg in messages)

        # 提取最后一条用户消息（截取前100字符）
        last_user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "")[:100]
                if len(msg.get("content", "")) > 100:
                    last_user_msg += "..."
                break

        logger.info(
            f"🚀 [LLM-REQ][{request_id}] provider={self._name} | "
            f"model={model} | messages={message_count} | chars={total_chars} | "
            f"max_tokens={max_tokens} | temperature={temperature}"
        )
        logger.debug(
            f"📝 [LLM-REQ][{request_id}] last_user_message: {last_user_msg}"
        )

        if extra_params:
            logger.debug(f"📝 [LLM-REQ][{request_id}] extra_params: {extra_params}")

        return request_id

    def _log_response(
        self,
        request_id: str,
        content: str,
        usage: Dict[str, int],
        model: str,
        finish_reason: str,
        latency_ms: float
    ) -> None:
        """记录响应日志"""
        response_preview = content[:150] + "..." if len(content) > 150 else content
        # 移除换行符以便日志更易读
        response_preview = response_preview.replace("\n", " ")

        logger.info(
            f"✅ [LLM-RES][{request_id}] provider={self._name} | "
            f"model={model} | latency={latency_ms:.0f}ms | "
            f"tokens(prompt={usage.get('prompt_tokens', 0)}, "
            f"completion={usage.get('completion_tokens', 0)}, "
            f"total={usage.get('total_tokens', 0)}) | "
            f"finish_reason={finish_reason}"
        )
        logger.debug(f"📤 [LLM-RES][{request_id}] response_preview: {response_preview}")

    def _log_error(
        self,
        request_id: str,
        error: Exception,
        latency_ms: float
    ) -> None:
        """记录错误日志"""
        logger.error(
            f"❌ [LLM-ERR][{request_id}] provider={self._name} | "
            f"latency={latency_ms:.0f}ms | error_type={type(error).__name__} | "
            f"error={str(error)}"
        )

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """生成响应"""
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """计算文本的token数量"""
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
        model = kwargs.get("model", self.config.model)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        temperature = kwargs.get("temperature", self.config.temperature)

        # 记录请求日志
        request_id = self._log_request(messages, model, max_tokens, temperature)
        start_time = time.perf_counter()

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )

            latency_ms = (time.perf_counter() - start_time) * 1000

            result = {
                "content": response.choices[0].message.content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                "model": response.model,
                "finish_reason": response.choices[0].finish_reason
            }

            # 记录响应日志
            self._log_response(
                request_id=request_id,
                content=result["content"],
                usage=result["usage"],
                model=result["model"],
                finish_reason=result["finish_reason"],
                latency_ms=latency_ms
            )

            return result

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._log_error(request_id, e, latency_ms)
            raise

    def count_tokens(self, text: str) -> int:
        """估算token数（简单实现）"""
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

        # 记录请求日志
        request_id = self._log_request(
            messages, model, max_tokens,
            self.config.temperature,
            {"has_system_prompt": system_prompt is not None}
        )
        start_time = time.perf_counter()

        try:
            response = await self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt or "",
                messages=claude_messages
            )

            latency_ms = (time.perf_counter() - start_time) * 1000

            result = {
                "content": response.content[0].text,
                "usage": {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                },
                "model": response.model,
                "finish_reason": response.stop_reason
            }

            # 记录响应日志
            self._log_response(
                request_id=request_id,
                content=result["content"],
                usage=result["usage"],
                model=result["model"],
                finish_reason=result["finish_reason"],
                latency_ms=latency_ms
            )

            return result

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._log_error(request_id, e, latency_ms)
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

        # 记录请求日志
        request_id = self._log_request(
            messages, model, max_tokens, temperature,
            {"api_url": self.api_url}
        )
        start_time = time.perf_counter()

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
                    latency_ms = (time.perf_counter() - start_time) * 1000

                    if response.status != 200:
                        error_text = await response.text()
                        error = Exception(f"vLLM API error: {response.status} - {error_text}")
                        self._log_error(request_id, error, latency_ms)
                        raise error

                    result_json = await response.json()

                    usage = result_json.get("usage", {})
                    result = {
                        "content": result_json["choices"][0]["message"]["content"],
                        "usage": {
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0),
                            "total_tokens": usage.get("total_tokens", 0)
                        },
                        "model": result_json.get("model", model),
                        "finish_reason": result_json["choices"][0].get("finish_reason", "stop")
                    }

                    # 记录响应日志
                    self._log_response(
                        request_id=request_id,
                        content=result["content"],
                        usage=result["usage"],
                        model=result["model"],
                        finish_reason=result["finish_reason"],
                        latency_ms=latency_ms
                    )

                    return result

        except aiohttp.ClientError as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._log_error(request_id, e, latency_ms)
            raise
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._log_error(request_id, e, latency_ms)
            raise

    def count_tokens(self, text: str) -> int:
        """估算token数"""
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)