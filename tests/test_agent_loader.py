"""
Tests for the AgentLoader.
"""
import pytest
import tempfile
import shutil
import sys
from pathlib import Path

from src.agents import AgentLoader, BaseAgent
from src.agents.models import Message, ChatContext, AgentResponse
from typing import Dict, Any


def create_test_agent_file(agents_dir: Path, filename: str, agent_code: str):
    """Helper to create a test agent file."""
    file_path = agents_dir / filename
    file_path.write_text(agent_code)


class TestAgentLoader:
    """Tests for AgentLoader."""
    
    def setup_method(self):
        """Create a temporary agents directory for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.agents_dir = Path(self.temp_dir) / "agents"
        self.agents_dir.mkdir()
        
        # Add temp_dir to sys.path so imports work
        sys.path.insert(0, self.temp_dir)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        # Remove from sys.path
        if self.temp_dir in sys.path:
            sys.path.remove(self.temp_dir)
        shutil.rmtree(self.temp_dir)
    
    def test_loader_creates_directory(self):
        """Test that loader creates agents directory if it doesn't exist."""
        new_dir = Path(self.temp_dir) / "new_agents"
        loader = AgentLoader(agents_dir=str(new_dir))
        
        assert new_dir.exists()
    
    def test_discover_no_agents(self):
        """Test discovery when no agents exist."""
        loader = AgentLoader(agents_dir=str(self.agents_dir))
        agents = loader.discover_agents()
        
        assert len(agents) == 0
    
    def test_discover_single_agent(self):
        """Test discovering a single agent module."""
        # Create a simple agent
        agent_code = '''
from src.agents import BaseAgent, Message, ChatContext, AgentResponse
from typing import Dict, Any

class SimpleAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "SimpleAgent"
    
    @property
    def description(self) -> str:
        return "A simple test agent"
    
    def can_handle(self, message: Message, context: ChatContext) -> float:
        return 0.5
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        return AgentResponse(content="Simple response", agent_name=self.name)
    
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        return {}
    
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        pass
'''
        create_test_agent_file(self.agents_dir, "simple_agent.py", agent_code)
        
        loader = AgentLoader(agents_dir=str(self.agents_dir))
        agent_classes = loader.discover_agents()
        
        assert len(agent_classes) == 1
        assert agent_classes[0].__name__ == "SimpleAgent"
    
    def test_load_agents_instantiate(self):
        """Test loading and instantiating agents."""
        agent_code = '''
from src.agents import BaseAgent, Message, ChatContext, AgentResponse
from typing import Dict, Any

class TestAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "TestAgent"
    
    @property
    def description(self) -> str:
        return "Test"
    
    def can_handle(self, message: Message, context: ChatContext) -> float:
        return 0.5
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        return AgentResponse(content="Test", agent_name=self.name)
    
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        return {}
    
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        pass
'''
        create_test_agent_file(self.agents_dir, "test_agent.py", agent_code)
        
        loader = AgentLoader(agents_dir=str(self.agents_dir))
        agents = loader.load_agents(instantiate=True)
        
        assert len(agents) == 1
        assert isinstance(agents[0], BaseAgent)
        assert agents[0].name == "TestAgent"
    
    def test_skip_invalid_files(self):
        """Test that loader skips non-agent files."""
        # Create a file without an agent
        non_agent_code = '''
def some_function():
    pass
'''
        create_test_agent_file(self.agents_dir, "helper.py", non_agent_code)
        
        loader = AgentLoader(agents_dir=str(self.agents_dir))
        agents = loader.discover_agents()
        
        assert len(agents) == 0
    
    def test_skip_private_files(self):
        """Test that loader skips files starting with underscore."""
        # Create __init__.py
        create_test_agent_file(self.agents_dir, "__init__.py", "")
        
        # Create _private.py
        create_test_agent_file(self.agents_dir, "_private.py", "")
        
        loader = AgentLoader(agents_dir=str(self.agents_dir))
        agents = loader.discover_agents()
        
        assert len(agents) == 0
    
    def test_multiple_agents_same_file(self):
        """Test that only one agent per module is loaded."""
        # Even if multiple agents are in the file, only the first found is loaded
        agent_code = '''
from src.agents import BaseAgent, Message, ChatContext, AgentResponse
from typing import Dict, Any

class Agent1(BaseAgent):
    @property
    def name(self) -> str:
        return "Agent1"
    
    @property
    def description(self) -> str:
        return "First agent"
    
    def can_handle(self, message: Message, context: ChatContext) -> float:
        return 0.5
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        return AgentResponse(content="Response1", agent_name=self.name)
    
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        return {}
    
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        pass

class Agent2(BaseAgent):
    @property
    def name(self) -> str:
        return "Agent2"
    
    @property
    def description(self) -> str:
        return "Second agent"
    
    def can_handle(self, message: Message, context: ChatContext) -> float:
        return 0.5
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        return AgentResponse(content="Response2", agent_name=self.name)
    
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        return {}
    
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        pass
'''
        create_test_agent_file(self.agents_dir, "multi_agent.py", agent_code)
        
        loader = AgentLoader(agents_dir=str(self.agents_dir))
        agent_classes = loader.discover_agents()
        
        # Should only load one agent (the first one found)
        assert len(agent_classes) == 1
        assert agent_classes[0].__name__ in ["Agent1", "Agent2"]
