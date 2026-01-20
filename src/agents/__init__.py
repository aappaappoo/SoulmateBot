"""
Multi-agent group chat system for SoulmateBot.

This module provides a production-grade multi-agent architecture where
multiple AI agents can join the same group chat session with intelligent routing.

Key components:
- BaseAgent: Abstract base class for all agents
- Message/ChatContext/AgentResponse: Core data models
- Router: Intelligent message routing system
- AgentLoader: Dynamic agent discovery and loading
- MemoryStore: Persistent and session memory management

Example usage:
    from src.agents import Router, AgentLoader, RouterConfig, Message, ChatContext
    
    # Load agents dynamically
    loader = AgentLoader(agents_dir="agents")
    agents = loader.load_agents()
    
    # Create router with configuration
    config = RouterConfig(min_confidence=0.5, max_agents=2)
    router = Router(agents, config)
    
    # Route a message
    message = Message(content="I'm feeling sad today", user_id="123", chat_id="456")
    context = ChatContext(chat_id="456")
    responses = router.route(message, context)
"""
from .models import Message, ChatContext, AgentResponse, MessageType
from .base_agent import BaseAgent
from .router import Router, RouterConfig
from .loader import AgentLoader
from .memory import MemoryStore, FileMemoryStore, SQLiteMemoryStore, InMemoryStore

__all__ = [
    # Data models
    "Message",
    "ChatContext",
    "AgentResponse",
    "MessageType",
    
    # Core classes
    "BaseAgent",
    "Router",
    "RouterConfig",
    "AgentLoader",
    
    # Memory stores
    "MemoryStore",
    "FileMemoryStore",
    "SQLiteMemoryStore",
    "InMemoryStore",
]

__version__ = "0.1.0"
