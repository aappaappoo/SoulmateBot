"""
Base agent interface that all agents must implement.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from .models import Message, ChatContext, AgentResponse


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the multi-agent system.
    
    Every agent must implement:
    - name: str property
    - description: str property
    - can_handle(message, context) -> float
    - respond(message, context) -> AgentResponse
    - memory_read(user_id) -> dict
    - memory_write(user_id, data) -> None
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        The unique name of this agent.
        
        Returns:
            Agent name (e.g., "EmotionalAgent", "TechAgent")
        """
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """
        A description of what this agent does.
        
        Returns:
            Agent description explaining its purpose and capabilities
        """
        pass
    
    @abstractmethod
    def can_handle(self, message: Message, context: ChatContext) -> float:
        """
        Determine if and how well this agent can handle the given message.
        
        This method is called by the Router to select appropriate agents.
        Return a confidence score between 0.0 and 1.0:
        - 0.0: Cannot handle this message at all
        - 0.1-0.4: Low confidence, only respond if no better agent
        - 0.5-0.7: Moderate confidence, can handle adequately
        - 0.8-1.0: High confidence, well-suited for this message
        
        Args:
            message: The incoming message
            context: The chat context with conversation history
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        pass
    
    @abstractmethod
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        """
        Generate a response to the message.
        
        This method is called when the Router has selected this agent
        to respond to a message.
        
        Args:
            message: The message to respond to
            context: The chat context with conversation history
            
        Returns:
            AgentResponse containing the response and metadata
        """
        pass
    
    @abstractmethod
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        """
        Read persistent memory for a specific user.
        
        Args:
            user_id: The user ID to read memory for
            
        Returns:
            Dictionary containing user-specific memory data
        """
        pass
    
    @abstractmethod
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        """
        Write persistent memory for a specific user.
        
        Args:
            user_id: The user ID to write memory for
            data: Dictionary of data to store
        """
        pass
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}')>"
