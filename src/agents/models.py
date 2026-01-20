"""
Data models for the multi-agent group chat system.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from enum import Enum


class MessageType(str, Enum):
    """Message type enumeration."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    FILE = "file"


@dataclass
class Message:
    """
    Represents a message in the group chat.
    
    Attributes:
        content: The message content/text
        user_id: ID of the user who sent the message
        chat_id: ID of the chat/group where message was sent
        message_type: Type of message (text, image, etc.)
        timestamp: When the message was sent
        metadata: Additional metadata (e.g., file_path for images, @mentions)
    """
    content: str
    user_id: str
    chat_id: str
    message_type: MessageType = MessageType.TEXT
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def has_mention(self, agent_name: str) -> bool:
        """
        Check if this message mentions a specific agent.
        
        Args:
            agent_name: The agent name to check for
            
        Returns:
            True if the agent is mentioned, False otherwise
        """
        mentions = self.metadata.get("mentions", [])
        # Check for @agent_name in mentions
        return f"@{agent_name}" in mentions or agent_name in mentions
    
    def get_clean_content(self) -> str:
        """
        Get message content with @mentions removed.
        
        Returns:
            Clean message content
        """
        content = self.content
        mentions = self.metadata.get("mentions", [])
        for mention in mentions:
            content = content.replace(mention, "").strip()
        return content


@dataclass
class ChatContext:
    """
    Context information for a chat session.
    
    Attributes:
        chat_id: ID of the chat/group
        conversation_history: Recent message history
        active_users: List of active user IDs in this chat
        chat_metadata: Additional chat information
    """
    chat_id: str
    conversation_history: List[Message] = field(default_factory=list)
    active_users: List[str] = field(default_factory=list)
    chat_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, message: Message) -> None:
        """Add a message to conversation history."""
        self.conversation_history.append(message)
        
        # Keep only recent messages (e.g., last 50)
        if len(self.conversation_history) > 50:
            self.conversation_history = self.conversation_history[-50:]
    
    def get_recent_messages(self, count: int = 10) -> List[Message]:
        """Get the most recent N messages."""
        return self.conversation_history[-count:]


@dataclass
class AgentResponse:
    """
    Response from an agent.
    
    Attributes:
        content: The response content/text
        agent_name: Name of the agent that generated this response
        confidence: Confidence score (0.0 to 1.0) of this response
        metadata: Additional response metadata
        should_continue: Whether other agents should also respond
    """
    content: str
    agent_name: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    should_continue: bool = False
    
    def __post_init__(self):
        """Validate confidence score."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")
