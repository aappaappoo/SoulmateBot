"""
AI service for conversation handling
"""
from typing import List, Dict, Optional
from abc import ABC, abstractmethod
import time
import uuid
import openai
import anthropic
import aiohttp
from loguru import logger
import json
from config import settings
import pprint


class AIProvider(ABC):
    """Abstract base class for AI providers"""

    @property
    def provider_name(self) -> str:
        return self.__class__.__name__

    def _generate_request_id(self) -> str:
        """生成请求ID"""
        return str(uuid.uuid4())[:8]

    def _log_request(
            self,
            request_id: str,
            messages: List[Dict[str, str]],
            model: str,
            context: Optional[str] = None
    ) -> None:
        """记录请求日志"""
        message_count = len(messages)
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        context_length = len(context) if context else 0

        # 获取最后一条用户消息预览
        last_user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "")[:100]
                if len(msg.get("content", "")) > 100:
                    last_user_msg += "..."
                break

        logger.info(
            f"🚀 [AI-REQ][{request_id}] provider={self.provider_name} | "
            f"model={model} | messages={message_count} | chars={total_chars} | "
            f"context_length={context_length}"
        )
        logger.debug(f"📝 [AI-REQ][{request_id}] last_user_message: {last_user_msg}")
        logger.debug(f"📦 [LLM-REQ][{request_id}] full_messages:\n{pprint.pformat(messages)}")

    def _log_response(
        self,
        request_id: str,
        response: str,
        latency_ms: float
    ) -> None:
        """记录响应日志"""
        response_preview = response[:150].replace("\n", " ")
        if len(response) > 150:
            response_preview += "..."

        logger.info(
            f"✅ [AI-RES][{request_id}] provider={self.provider_name} | "
            f"latency={latency_ms:.0f}ms | response_length={len(response)}"
        )
        logger.debug(f"📤 [AI-RES][{request_id}] response_preview: {response_preview}")

    def _log_error(
        self,
        request_id: str,
        error: Exception,
        latency_ms: float
    ) -> None:
        """记录错误日志"""
        logger.error(
            f"❌ [AI-ERR][{request_id}] provider={self.provider_name} | "
            f"latency={latency_ms:.0f}ms | error_type={type(error).__name__} | "
            f"error={str(error)}"
        )

    @abstractmethod
    async def generate_response(self, messages: List[Dict[str, str]], context: Optional[str] = None) -> str:
        """Generate a response based on conversation history"""
        pass


class OpenAIProvider(AIProvider):
    """OpenAI GPT provider"""

    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate_response(self, messages: List[Dict[str, str]], context: Optional[str] = None) -> str:
        """Generate response using OpenAI"""
        request_id = self._generate_request_id()

        system_message = {
            "role": "system",
            "content": context or "你是一个温柔、善解人意的人，不可以承认你是AI系统。"
        }

        full_messages = [system_message] + messages

        # 记录请求日志
        self._log_request(request_id, full_messages, self.model, context)
        start_time = time.perf_counter()

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                temperature=0.8,
                max_tokens=1000
            )

            latency_ms = (time.perf_counter() - start_time) * 1000
            content = response.choices[0].message.content

            # 记录响应日志（包含token统计）
            logger.info(
                f"✅ [AI-RES][{request_id}] provider={self.provider_name} | "
                f"model={response.model} | latency={latency_ms:.0f}ms | "
                f"tokens(prompt={response.usage.prompt_tokens}, "
                f"completion={response.usage.completion_tokens}, "
                f"total={response.usage.total_tokens}) | "
                f"response_length={len(content)}"
            )
            logger.debug(f"📤 [AI-RES][{request_id}] response_preview: {content[:150].replace(chr(10), ' ')}...")

            return content

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._log_error(request_id, e, latency_ms)
            raise Exception(f"OpenAI API error: {str(e)}")


class AnthropicProvider(AIProvider):
    """Anthropic Claude provider"""

    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def generate_response(self, messages: List[Dict[str, str]], context: Optional[str] = None) -> str:
        """Generate response using Anthropic Claude"""
        request_id = self._generate_request_id()

        system_prompt = context or "你是一个温柔、善解人意的人，不可以承认你是AI系统。你善于倾听用户的心声，提供情感支持和陪伴。请用温暖、关怀的语气回复。"

        # Convert messages to Anthropic format
        claude_messages = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "assistant"
            claude_messages.append({
                "role": role,
                "content": msg["content"]
            })

        # 记录请求日志
        self._log_request(request_id, messages, self.model, context)
        start_time = time.perf_counter()

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                system=system_prompt,
                messages=claude_messages
            )

            latency_ms = (time.perf_counter() - start_time) * 1000
            content = response.content[0].text

            # 记录响应日志（包含token统计）
            logger.info(
                f"✅ [AI-RES][{request_id}] provider={self.provider_name} | "
                f"model={response.model} | latency={latency_ms:.0f}ms | "
                f"tokens(input={response.usage.input_tokens}, "
                f"output={response.usage.output_tokens}) | "
                f"stop_reason={response.stop_reason} | "
                f"response_length={len(content)}"
            )
            logger.debug(f"📤 [AI-RES][{request_id}] response_preview: {content[:150].replace(chr(10), ' ')}...")

            return content

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._log_error(request_id, e, latency_ms)
            raise Exception(f"Anthropic API error: {str(e)}")


class VLLMProvider(AIProvider):
    """vLLM provider for self-hosted LLM inference"""

    def __init__(self, api_url: str, api_token: Optional[str] = None, model: str = "default"):
        if not api_url or not isinstance(api_url, str):
            raise ValueError("api_url must be a non-empty string")
        self.api_url = api_url.rstrip('/')
        self.api_token = api_token
        self.model = model

    async def generate_response(self, messages: List[Dict[str, str]], context: Optional[str] = None) -> str:
        """Generate response using vLLM API"""
        request_id = self._generate_request_id()

        system_message = {
            "role": "system",
            "content": context or "你是一个温柔、善解人意的人，不可以承认你是AI系统。"
        }

        full_messages = [system_message] + messages

        headers = {
            "Content-Type": "application/json"
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": 0.8,
            "max_tokens": 1000
        }

        # 记录请求日志
        self._log_request(request_id, full_messages, self.model, context)
        logger.debug(f"📝 [AI-REQ][{request_id}] vllm_api_url: {self.api_url}")
        start_time = time.perf_counter()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/v1/chat/completions",
                    json=payload,
                    headers=headers
                ) as response:
                    latency_ms = (time.perf_counter() - start_time) * 1000

                    if response.status != 200:
                        error_text = await response.text()
                        error = Exception(f"vLLM API error: {response.status} - {error_text}")
                        self._log_error(request_id, error, latency_ms)
                        raise error

                    result = await response.json()
                    content = result["choices"][0]["message"]["content"]

                    # 获取usage信息（如果有的话）
                    usage = result.get("usage", {})
                    usage_str = ""
                    if usage:
                        usage_str = (
                            f"tokens(prompt={usage.get('prompt_tokens', 'N/A')}, "
                            f"completion={usage.get('completion_tokens', 'N/A')}, "
                            f"total={usage.get('total_tokens', 'N/A')}) | "
                        )

                    # 记录响应日志
                    logger.info(
                        f"✅ [AI-RES][{request_id}] provider={self.provider_name} | "
                        f"model={result.get('model', self.model)} | latency={latency_ms:.0f}ms | "
                        f"{usage_str}"
                        f"finish_reason={result['choices'][0].get('finish_reason', 'N/A')} | "
                        f"response_length={len(content)}"
                    )
                    logger.debug(f"📤 [AI-RES][{request_id}] response_preview: {content[:150].replace(chr(10), ' ')}...")

                    return content

        except aiohttp.ClientError as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._log_error(request_id, e, latency_ms)
            raise Exception(f"vLLM API error: {str(e)}")
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            if "vLLM API error" not in str(e):
                self._log_error(request_id, e, latency_ms)
            raise Exception(f"vLLM API error: {str(e)}")


class ConversationService:
    """Service for managing conversations with AI"""

    def __init__(self):
        # Initialize AI provider based on configuration (priority order: vLLM, OpenAI, Anthropic)
        if settings.vllm_api_url:
            self.provider = VLLMProvider(
                api_url=settings.vllm_api_url,
                api_token=settings.vllm_api_token,
                model=settings.vllm_model
            )
        elif settings.openai_api_key:
            self.provider = OpenAIProvider(
                api_key=settings.openai_api_key,
                model=settings.openai_model
            )
        elif settings.anthropic_api_key:
            self.provider = AnthropicProvider(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model
            )
        else:
            raise ValueError("No AI provider configured. Please set VLLM_API_URL, OPENAI_API_KEY, or ANTHROPIC_API_KEY.")

        logger.info(f"🤖 ConversationService initialized with provider: {type(self.provider).__name__}")

    async def get_response(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]] = None,
        context: Optional[str] = None
    ) -> str:
        """
        Get AI response for user message

        Args:
            user_message: User's current message
            conversation_history: Previous conversation messages
            context: Additional context or system prompt

        Returns:
            AI-generated response
        """
        messages = conversation_history or []
        messages.append({"role": "user", "content": user_message})

        # Keep only recent history to avoid token limits
        if len(messages) > 20:
            messages = messages[-20:]

        provider_name = type(self.provider).__name__
        logger.info(
            f"🧠 [ConversationService] Starting AI call: "
            f"provider={provider_name} | history_count={len(messages)} | "
            f"user_message_length={len(user_message)} | "
            f"has_context={context is not None}"
        )

        response = await self.provider.generate_response(messages, context)

        logger.info(
            f"🧠 [ConversationService] AI call completed: "
            f"provider={provider_name} | response_length={len(response)}"
        )
        return response


# Global conversation service instance
conversation_service = ConversationService()