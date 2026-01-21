"""
Conversation Module - 多轮对话管理

提供：
- 会话管理
- Prompt模板管理
- 上下文窗口管理
"""

from .session_manager import SessionManager, Session, Message, get_session_manager
from .prompt_template import PromptTemplate, PromptTemplateManager, get_template_manager
from .context_manager import ContextManager, ContextWindow, get_context_manager

__all__ = [
    'SessionManager',
    'Session',
    'Message',
    'get_session_manager',
    'PromptTemplate',
    'PromptTemplateManager',
    'get_template_manager',
    'ContextManager',
    'ContextWindow',
    'get_context_manager',
]
