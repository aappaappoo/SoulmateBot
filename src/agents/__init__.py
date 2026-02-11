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
- AgentOrchestrator: LLM-powered intelligent orchestration
- Skills: Token-efficient skill selection with Telegram buttons

Example usage:
    from src.agents import Router, AgentLoader, RouterConfig, Message, ChatContext
    
    # Load agents dynamically
    loader = AgentLoader(agents_dir="agents")
    agents = loader.load_agents()
    
    # Create router with configuration
    configs = RouterConfig(min_confidence=0.5, max_agents=2)
    router = Router(agents, configs)
    
    # Route a message
    message = Message(content="I'm feeling sad today", user_id="123", chat_id="456")
    context = ChatContext(chat_id="456")
    responses = router.route(message, context)
    
    # Or use the orchestrator for intelligent agent selection
    from src.agents import AgentOrchestrator
    orchestrator = AgentOrchestrator(agents, llm_provider=your_llm_provider)
    result = await orchestrator.process(message, context)
"""
from .models import Message, ChatContext, AgentResponse, MessageType
from .base_agent import BaseAgent
from .router import Router, RouterConfig
from .loader import AgentLoader
from .memory import MemoryStore, FileMemoryStore, SQLiteMemoryStore, InMemoryStore
from .orchestrator import AgentOrchestrator, OrchestratorResult, IntentType, IntentSource, AgentCapability
from .skills import (
    Skill, SkillCategory, SkillRegistry, SkillButtonGenerator,
    skill_registry, skill_button_generator, register_skill
)

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
    
    # Orchestrator
    "AgentOrchestrator",
    "OrchestratorResult",
    "IntentType",
    "IntentSource",
    "AgentCapability",
    
    # Skills
    "Skill",
    "SkillCategory",
    "SkillRegistry",
    "SkillButtonGenerator",
    "skill_registry",
    "skill_button_generator",
    "register_skill",
]

__version__ = "0.2.0"
