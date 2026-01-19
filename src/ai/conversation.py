"""
AI service for conversation handling
"""
from typing import List, Dict, Optional
from abc import ABC, abstractmethod
import openai
import anthropic
import aiohttp

from config import settings


class AIProvider(ABC):
    """Abstract base class for AI providers"""
    
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
        system_message = {
            "role": "system",
            "content": context or "你是一个温柔、善解人意的情感陪伴助手。你的任务是倾听用户的心声，提供情感支持和陪伴。请用温暖、关怀的语气回复用户。"
        }
        
        full_messages = [system_message] + messages
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                temperature=0.8,
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")


class AnthropicProvider(AIProvider):
    """Anthropic Claude provider"""
    
    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
    
    async def generate_response(self, messages: List[Dict[str, str]], context: Optional[str] = None) -> str:
        """Generate response using Anthropic Claude"""
        system_prompt = context or "你是一个温柔、善解人意的情感陪伴助手。你的任务是倾听用户的心声，提供情感支持和陪伴。请用温暖、关怀的语气回复用户。"
        
        # Convert messages to Anthropic format
        claude_messages = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "assistant"
            claude_messages.append({
                "role": role,
                "content": msg["content"]
            })
        
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                system=system_prompt,
                messages=claude_messages
            )
            return response.content[0].text
        except Exception as e:
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
        system_message = {
            "role": "system",
            "content": context or "你是一个温柔、善解人意的情感陪伴助手。你的任务是倾听用户的心声，提供情感支持和陪伴。请用温暖、关怀的语气回复用户。"
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
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/v1/chat/completions",
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"vLLM API error: {response.status} - {error_text}")
                    
                    result = await response.json()
                    return result["choices"][0]["message"]["content"]
        except Exception as e:
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
        
        response = await self.provider.generate_response(messages, context)
        return response


# Global conversation service instance
conversation_service = ConversationService()
