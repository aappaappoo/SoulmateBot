"""
AI service for conversation handling
"""
from typing import List, Dict, Optional, Any
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
        logger.debug(f"📦 [LLM-REQ][{request_id}] full_messages:\n{pprint.pformat(messages)}")

    def _log_response(
            self,
            request_id: str,
            response: str,
            latency_ms: float
    ) -> None:
        """记录响应日志"""
        logger.info(
            f"✅ [AI-RES][{request_id}] provider={self.provider_name} | "
            f"latency={latency_ms:.0f}ms | response_length={len(response)}"
        )
        # DEBUG 级别：输出完整回复
        if logger.level("DEBUG").no >= logger._core.min_level:
            logger.debug(f"📤 [AI-RES][{request_id}] full_response:\n{pprint.pformat(response)}")
        else:
            response_preview = response[:150].replace("\n", " ")
            if len(response) > 150:
                response_preview += "..."
            logger.info(f"📤 [AI-RES][{request_id}] response_preview: {response_preview}")

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
        has_system = any(msg.get("role") == "system" for msg in messages)
        if has_system:
            full_messages = messages
        else:
            system_message = {
                "role": "system",
                "content": context or "你是一个温柔、善解人意的人"
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
            "max_tokens": 1000,
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
                    if logger.level("DEBUG").no >= logger._core.min_level:
                        if hasattr(response, 'json'):
                            response_data = await response.json()
                            content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                            logger.debug(
                                f"📤 [AI-RES][{request_id}] full_response:\n{pprint.pformat(content)}"
                            )
                    else:
                        response_preview = response[:150].replace("\n", " ")
                        if len(response) > 150:
                            response_preview += "..."
                        logger.info(f"📤 [AI-RES][{request_id}] response_preview: {response_preview}")
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
        else:
            raise ValueError(
                "No AI provider configured. Please set VLLM_API_URL, OPENAI_API_KEY, or ANTHROPIC_API_KEY.")

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

    async def get_response_with_emotion(
            self,
            user_message: str,
            conversation_history: List[Dict[str, str]] = None,
            context: Optional[str] = None,
            enable_emotion_detection: bool = True
    ) -> Dict[str, Any]:
        """
        Get AI response with emotion detection.
        
        通过LLM API检测情绪类型和强度，返回结构化的响应数据。
        情绪信息不会包含在回复文本中，而是作为独立的字段返回。

        Args:
            user_message: User's current message
            conversation_history: Previous conversation messages  
            context: Additional context or system prompt
            enable_emotion_detection: Whether to enable LLM-based emotion detection

        Returns:
            Dict containing:
            - response: Clean response text (without emotion prefix)
            - emotion_info: Dict with emotion_type, intensity, tone_description, or None if no emotion detected
        """
        from src.utils.emotion_parser import parse_llm_response_with_emotion

        # Create a copy of the list to avoid mutating the input
        messages = list(conversation_history) if conversation_history else []
        messages.append({"role": "user", "content": user_message})

        # Keep only recent history to avoid token limits
        if len(messages) > 20:
            messages = messages[-20:]

        # Enhance context with emotion detection instruction if enabled
        enhanced_context = context
        if enable_emotion_detection:
            enhanced_context = self._add_emotion_instruction(context)

        provider_name = type(self.provider).__name__
        logger.info(
            f"🧠 [ConversationService] Starting AI call with emotion detection: "
            f"provider={provider_name} | history_count={len(messages)} | "
            f"user_message_length={len(user_message)} | "
            f"emotion_detection={enable_emotion_detection}"
        )

        raw_response = await self.provider.generate_response(messages, enhanced_context)

        # Parse the response to extract emotion info
        parsed = parse_llm_response_with_emotion(raw_response)

        logger.info(
            f"🧠 [ConversationService] AI call with emotion completed: "
            f"provider={provider_name} | response_length={len(parsed.clean_text)} | "
            f"emotion_type={parsed.emotion_type} | intensity={parsed.intensity}"
        )

        return {
            "response": parsed.clean_text,
            "emotion_info": parsed.get_emotion_info_dict()
        }

    def _add_emotion_instruction(self, context: Optional[str]) -> str:
        """
        在系统提示中添加情绪检测指令。
        
        指导LLM在回复时同时返回情绪信息，使用JSON格式返回结构化数据。
        
        Args:
            context: 原始系统提示
            
        Returns:
            增强后的系统提示
        """
        emotion_instruction = """

=========================
📊 情绪表达指令
=========================
请在回复时同时分析你要表达的情绪，并以JSON格式返回。

返回格式：
{
    "response": "你的回复内容（不要包含语气前缀）",
    "emotion_info": {
        "emotion_type": "情绪类型",
        "intensity": "强度级别",
        "tone_description": "语气描述"
    }
}

情绪类型(emotion_type)可选值：
- happy: 开心、愉悦
- gentle: 温柔、柔和
- sad: 低落、伤感
- excited: 兴奋、激动
- angry: 生气、愤怒
- crying: 委屈、哭泣
- neutral: 平静、中性

强度级别(intensity)可选值：
- high: 情绪强烈
- medium: 情绪适中
- low: 情绪轻微

语气描述(tone_description)：用自然语言简短描述语气特点，如"温柔、轻声、放慢语速"。

请确保只返回JSON格式的内容，不要在JSON之外添加任何文本。"""

        base_context = context if context else ""
        return base_context + emotion_instruction


# Global conversation service instance
conversation_service = ConversationService()
