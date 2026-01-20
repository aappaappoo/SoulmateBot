"""
Emotional Support Agent

Handles emotional and mental health related conversations.
Provides empathetic responses and emotional support.
"""
from typing import Dict, Any
from src.agents import BaseAgent, Message, ChatContext, AgentResponse, MemoryStore, SQLiteMemoryStore


class EmotionalAgent(BaseAgent):
    """
    Agent specialized in emotional support and empathetic conversations.
    
    This agent is best suited for:
    - Emotional expressions (happy, sad, anxious, etc.)
    - Personal problems and concerns
    - Mental health discussions
    - Seeking comfort or encouragement
    """
    
    def __init__(self, memory_store: MemoryStore = None):
        """
        Initialize the Emotional Agent.
        
        Args:
            memory_store: Optional memory store for persistence
        """
        self._name = "EmotionalAgent"
        self._description = (
            "Provides emotional support and empathetic responses. "
            "Specializes in understanding and responding to feelings, "
            "mental health concerns, and personal problems."
        )
        self._memory = memory_store or SQLiteMemoryStore()
        
        # Keywords that indicate emotional content
        self._emotional_keywords = [
            # Feelings
            "feel", "feeling", "felt", "emotion", "emotional",
            "sad", "happy", "angry", "anxious", "worried", "stressed",
            "depressed", "lonely", "tired", "exhausted", "frustrated",
            "excited", "nervous", "scared", "afraid", "hopeful",
            
            # Mental health
            "mental", "health", "therapy", "counseling", "depression",
            "anxiety", "panic", "overwhelmed", "burnout",
            
            # Personal issues
            "problem", "issue", "struggle", "difficult", "hard",
            "upset", "hurt", "pain", "suffering",
            
            # Support seeking
            "help", "support", "advice", "listen", "talk",
            "understand", "comfort", "care",
            
            # Emotional expressions
            "cry", "crying", "tears", "smile", "laugh", "sigh",
        ]
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    def can_handle(self, message: Message, context: ChatContext) -> float:
        """
        Determine confidence for handling this message.
        
        Returns high confidence for emotionally-charged messages.
        """
        # Check for explicit mention
        if message.has_mention(self.name):
            return 1.0
        
        content = message.content.lower()
        
        # Count emotional keywords
        keyword_matches = sum(1 for keyword in self._emotional_keywords if keyword in content)
        
        # Calculate base confidence from keyword matches
        # More keywords = higher confidence
        if keyword_matches >= 3:
            confidence = 0.9
        elif keyword_matches == 2:
            confidence = 0.7
        elif keyword_matches == 1:
            confidence = 0.5
        else:
            confidence = 0.0
        
        # Boost confidence for question marks (seeking help)
        if "?" in content and keyword_matches > 0:
            confidence = min(1.0, confidence + 0.1)
        
        # Check conversation history for emotional context
        recent_messages = context.get_recent_messages(5)
        for msg in recent_messages:
            msg_content = msg.content.lower()
            if any(keyword in msg_content for keyword in self._emotional_keywords[:20]):
                # Boost confidence if recent conversation was emotional
                confidence = min(1.0, confidence + 0.1)
                break
        
        return confidence
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        """Generate an empathetic response."""
        # Read user's emotional history
        user_memory = self.memory_read(message.user_id)
        interaction_count = user_memory.get("interaction_count", 0)
        
        # Create empathetic response
        content = message.get_clean_content().lower()
        
        # Detect primary emotion
        if any(word in content for word in ["sad", "depressed", "down", "unhappy"]):
            emotion = "sadness"
            response = self._respond_to_sadness(message, interaction_count)
        elif any(word in content for word in ["anxious", "worried", "nervous", "stressed"]):
            emotion = "anxiety"
            response = self._respond_to_anxiety(message, interaction_count)
        elif any(word in content for word in ["happy", "excited", "great", "wonderful"]):
            emotion = "happiness"
            response = self._respond_to_happiness(message, interaction_count)
        elif any(word in content for word in ["angry", "frustrated", "mad", "annoyed"]):
            emotion = "anger"
            response = self._respond_to_anger(message, interaction_count)
        else:
            emotion = "general"
            response = self._respond_general(message, interaction_count)
        
        # Update memory
        user_memory["interaction_count"] = interaction_count + 1
        user_memory["last_emotion"] = emotion
        user_memory["last_message"] = message.content
        self.memory_write(message.user_id, user_memory)
        
        return AgentResponse(
            content=response,
            agent_name=self.name,
            confidence=0.85,
            metadata={"emotion_detected": emotion},
            should_continue=False  # Emotional support is typically exclusive
        )
    
    def _respond_to_sadness(self, message: Message, interaction_count: int) -> str:
        """Generate response for sadness."""
        if interaction_count == 0:
            return (
                "I'm sorry you're feeling down. It's okay to feel sad sometimes. "
                "Would you like to talk about what's bothering you? I'm here to listen."
            )
        else:
            return (
                "I hear that you're going through a difficult time. "
                "Remember that these feelings are temporary, and it's brave of you to share. "
                "What would help you feel a little better right now?"
            )
    
    def _respond_to_anxiety(self, message: Message, interaction_count: int) -> str:
        """Generate response for anxiety."""
        return (
            "It sounds like you're feeling anxious or worried. That can be really overwhelming. "
            "Let's take this one step at a time. "
            "Can you tell me what's making you feel this way? "
            "Sometimes just talking about it can help."
        )
    
    def _respond_to_happiness(self, message: Message, interaction_count: int) -> str:
        """Generate response for happiness."""
        return (
            "That's wonderful! I'm so glad you're feeling happy! "
            "It's great to hear positive news. "
            "What made your day special? I'd love to hear more about it!"
        )
    
    def _respond_to_anger(self, message: Message, interaction_count: int) -> str:
        """Generate response for anger."""
        return (
            "I can sense that you're feeling frustrated or angry. "
            "Those feelings are valid, and it's important to acknowledge them. "
            "Would it help to talk about what happened? "
            "I'm here to listen without judgment."
        )
    
    def _respond_general(self, message: Message, interaction_count: int) -> str:
        """Generate general empathetic response."""
        if interaction_count == 0:
            return (
                "Hello! I'm here to provide emotional support and listen to whatever you'd like to share. "
                "How are you feeling today?"
            )
        else:
            return (
                "I'm here to support you. Tell me what's on your mind. "
                "Whatever you're going through, I'm here to listen and help however I can."
            )
    
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        """Read user's emotional history."""
        return self._memory.read(self.name, user_id)
    
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        """Write user's emotional history."""
        self._memory.write(self.name, user_id, data)
