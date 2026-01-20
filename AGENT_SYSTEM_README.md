# Multi-Agent Group Chat System

A production-grade multi-agent group chat system in Python where multiple AI agents can join the same group chat session with intelligent routing.

## Features

### Core Architecture

- **BaseAgent Interface**: Common interface for all agents with:
  - `name` and `description` properties
  - `can_handle(message, context) -> float` for confidence-based routing
  - `respond(message, context) -> AgentResponse` for generating responses
  - `memory_read/write(user_id)` for persistent user memory

- **Intelligent Router**: Routes messages to appropriate agents based on:
  - Explicit @mentions
  - Semantic confidence scores from `can_handle()`
  - Configurable policies (min confidence, max agents, exclusive mention mode)
  - Optional cooldown to prevent spam
  - Parallel or sequential execution

- **Plugin System**: Dynamic agent discovery and loading:
  - Agents are automatically discovered from the `agents/` directory
  - No hardcoded agent imports in core logic
  - Each agent can be in its own file or package
  - Hot-reload support for development

- **Memory System**: Flexible memory storage:
  - **InMemoryStore**: Short-term session memory
  - **FileMemoryStore**: JSON file-based persistence
  - **SQLiteMemoryStore**: Database-backed storage
  - Abstract interface for future Redis/vector DB support

## Installation

```bash
# Clone the repository
git clone https://github.com/aappaappoo/SoulmateBot.git
cd SoulmateBot

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

### 1. Run the Demo CLI

```bash
python agent_demo.py
```

This launches an interactive CLI where you can:
- Send messages to agents
- Use @mentions to target specific agents
- See how messages are routed based on content

### 2. Example Usage in Code

```python
from src.agents import Router, RouterConfig, AgentLoader, Message, ChatContext

# Load agents automatically from agents/ directory
loader = AgentLoader(agents_dir="agents")
agents = loader.load_agents()

# Configure routing behavior
config = RouterConfig(
    min_confidence=0.5,      # Minimum confidence threshold
    max_agents=2,            # Maximum agents to respond
    exclusive_mention=True,  # Only mentioned agent responds when @mentioned
    enable_parallel=False,   # Execute agents sequentially
    cooldown_seconds=0       # No cooldown between responses
)

# Create router
router = Router(agents, config)

# Create a message
message = Message(
    content="I'm feeling sad today",
    user_id="user123",
    chat_id="chat456"
)

# Create context
context = ChatContext(chat_id="chat456")

# Route the message and get responses
responses = router.route(message, context)

for response in responses:
    print(f"{response.agent_name}: {response.content}")
```

## Built-in Agents

### EmotionalAgent

Provides emotional support and empathetic responses.

**Triggers on:**
- Emotional keywords (sad, happy, anxious, stressed, etc.)
- Mental health discussions
- Personal problems and concerns
- Support-seeking phrases

**Example:**
```
User: I'm feeling really anxious about work
EmotionalAgent: It sounds like you're feeling anxious or worried. 
                That can be really overwhelming. Let's take this 
                one step at a time...
```

### TechAgent

Provides technical support and programming assistance.

**Triggers on:**
- Programming languages (Python, JavaScript, etc.)
- Technical keywords (debug, error, code, API, etc.)
- How-to questions
- Code snippets

**Example:**
```
User: How do I fix a Python import error?
TechAgent: I can help you debug this issue. Let me break down 
           the problem: 1. First, let's identify the error message...
```

## Creating Custom Agents

### 1. Create Agent File

Create a new file in the `agents/` directory:

```python
# agents/weather_agent.py

from typing import Dict, Any
from src.agents import BaseAgent, Message, ChatContext, AgentResponse
from src.agents import SQLiteMemoryStore

class WeatherAgent(BaseAgent):
    def __init__(self):
        self._name = "WeatherAgent"
        self._description = "Provides weather information and forecasts"
        self._memory = SQLiteMemoryStore()
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    def can_handle(self, message: Message, context: ChatContext) -> float:
        """Return confidence score for handling this message."""
        content = message.content.lower()
        
        # Check for explicit mention
        if message.has_mention(self.name):
            return 1.0
        
        # Check for weather keywords
        weather_keywords = ["weather", "temperature", "forecast", "rain", "sunny"]
        matches = sum(1 for kw in weather_keywords if kw in content)
        
        if matches >= 2:
            return 0.9
        elif matches == 1:
            return 0.6
        
        return 0.0
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        """Generate weather response."""
        # Your weather API logic here
        response_text = "I'd be happy to help with weather information!"
        
        return AgentResponse(
            content=response_text,
            agent_name=self.name,
            confidence=0.85,
            metadata={"query_type": "weather"}
        )
    
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        """Read user's weather preferences."""
        return self._memory.read(self.name, user_id)
    
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        """Save user's weather preferences."""
        self._memory.write(self.name, user_id, data)
```

### 2. Agent is Auto-Discovered

The `AgentLoader` automatically discovers and loads your agent:

```python
loader = AgentLoader(agents_dir="agents")
agents = loader.load_agents()  # Includes your WeatherAgent!
```

## Router Configuration

### RouterConfig Options

```python
from src.agents import RouterConfig

config = RouterConfig(
    # Minimum confidence threshold (0.0-1.0)
    # Agents below this threshold won't respond
    min_confidence=0.5,
    
    # Maximum number of agents that can respond to one message
    max_agents=1,
    
    # If True, only the mentioned agent responds when @mention exists
    exclusive_mention=True,
    
    # Enable parallel execution of multiple agents
    enable_parallel=False,
    
    # Cooldown period (seconds) between responses from same agent to same user
    cooldown_seconds=0.0,
    
    # Fallback agent name if no agents meet confidence threshold
    fallback_agent_name=None
)
```

### Trigger Modes

**1. Explicit Mention**
```
User: @TechAgent help me with Python
→ Routes only to TechAgent (confidence: 1.0)
```

**2. Semantic Routing**
```
User: How do I fix this bug?
→ Router calls can_handle() on all agents
→ Routes to agent(s) with highest confidence above threshold
```

**3. Keyword Subscription** (optional extension)
```python
# Agents can check for specific keywords in can_handle()
if "weather" in message.content.lower():
    return 0.9
```

## Memory System

### Using Different Memory Stores

```python
from src.agents.memory import FileMemoryStore, SQLiteMemoryStore, InMemoryStore

# File-based (JSON files per user per agent)
file_store = FileMemoryStore(base_path="data/agent_memory")

# SQLite database
sqlite_store = SQLiteMemoryStore(db_path="data/agent_memory.db")

# In-memory (session only, not persistent)
memory_store = InMemoryStore()

# Pass to agent
class MyAgent(BaseAgent):
    def __init__(self, memory_store=None):
        self._memory = memory_store or SQLiteMemoryStore()
```

### Memory Operations

```python
# Read user memory
data = agent.memory_read("user123")
# Returns: {"key": "value", ...}

# Write user memory
agent.memory_write("user123", {
    "last_query": "weather forecast",
    "preferences": {"units": "celsius"}
})
```

## Testing

Run the comprehensive test suite:

```bash
# Run all agent tests
pytest tests/test_agent_*.py -v

# Run specific test file
pytest tests/test_agent_router.py -v

# Run with coverage
pytest tests/test_agent_*.py --cov=src.agents --cov-report=html
```

## Architecture

```
src/agents/
├── __init__.py          # Public API exports
├── models.py            # Data models (Message, ChatContext, AgentResponse)
├── base_agent.py        # BaseAgent abstract class
├── router.py            # Router and RouterConfig
├── loader.py            # AgentLoader for plugin discovery
└── memory.py            # Memory storage implementations

agents/                  # Plugin directory (auto-discovered)
├── emotional_agent.py   # EmotionalAgent implementation
├── tech_agent.py        # TechAgent implementation
└── ...                  # Your custom agents

tests/
├── test_agent_models.py       # Tests for data models
├── test_agent_router.py       # Tests for router
├── test_agent_memory.py       # Tests for memory system
├── test_agent_loader.py       # Tests for loader
└── test_agent_integration.py  # Integration tests
```

## API Reference

### Message

```python
@dataclass
class Message:
    content: str                    # Message text
    user_id: str                    # User ID
    chat_id: str                    # Chat/group ID
    message_type: MessageType       # TEXT, IMAGE, etc.
    timestamp: datetime             # When sent
    metadata: Dict[str, Any]        # Additional data
    
    def has_mention(self, agent_name: str) -> bool
    def get_clean_content(self) -> str
```

### ChatContext

```python
@dataclass
class ChatContext:
    chat_id: str                           # Chat/group ID
    conversation_history: List[Message]    # Recent messages
    active_users: List[str]                # Active user IDs
    chat_metadata: Dict[str, Any]          # Additional data
    
    def add_message(self, message: Message) -> None
    def get_recent_messages(self, count: int = 10) -> List[Message]
```

### AgentResponse

```python
@dataclass
class AgentResponse:
    content: str                    # Response text
    agent_name: str                 # Agent that generated this
    confidence: float               # 0.0-1.0
    metadata: Dict[str, Any]        # Additional data
    should_continue: bool           # Allow other agents to respond?
```

## Best Practices

### 1. Agent Design

- **Single Responsibility**: Each agent should handle one domain
- **Clear Confidence Scores**: Return meaningful scores in `can_handle()`
- **Memory Management**: Clean up old memory periodically
- **Error Handling**: Handle errors gracefully in `respond()`

### 2. Routing Configuration

- **Start Conservative**: Begin with higher confidence thresholds (0.6-0.7)
- **Limit Max Agents**: Usually 1-2 agents per message is sufficient
- **Use Cooldowns**: Prevent rapid-fire responses to same user
- **Test Thoroughly**: Test routing with diverse message types

### 3. Performance

- **Use Parallel Execution**: For independent agents, enable parallel mode
- **Cache Heavy Operations**: Store expensive computations in memory
- **Batch Memory Updates**: Update memory less frequently for high-traffic
- **Profile Agent Latency**: Monitor `can_handle()` and `respond()` times

## License

MIT License - see LICENSE file for details

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Support

- Documentation: See this README and inline docstrings
- Issues: https://github.com/aappaappoo/SoulmateBot/issues
- Examples: See `agent_demo.py` and test files
