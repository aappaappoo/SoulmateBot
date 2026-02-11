"""
Agent plugin loader for dynamic agent discovery.

Automatically discovers and loads agents from the agents/ directory.
"""
import importlib
import inspect
from pathlib import Path
from typing import List, Type, Optional, Set
from loguru import logger

from .base_agent import BaseAgent


class AgentLoader:
    """
    Dynamic agent loader with plugin discovery.
    
    Discovers and loads agent implementations from a specified directory.
    Each agent should be in its own module/package under the agents directory.
    """
    
    def __init__(self, agents_dir: str = "src/agents/plugins"):
        """
        Initialize the agent loader.
        
        Args:
            agents_dir: Directory to search for agent plugins
        """
        self.agents_dir = Path(agents_dir)
        self._loaded_agents: Set[str] = set()
        
        if not self.agents_dir.exists():
            logger.warning(f"Agents directory does not exist: {self.agents_dir}")
            self.agents_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created agents directory: {self.agents_dir}")
    
    def discover_agents(self) -> List[Type[BaseAgent]]:
        """
        Discover all agent classes in the agents directory.
        
        Searches for Python modules/packages in the agents directory and
        looks for classes that inherit from BaseAgent.
        
        Returns:
            List of agent classes (not instances)
        """
        agent_classes: List[Type[BaseAgent]] = []
        
        if not self.agents_dir.exists():
            logger.warning(f"Agents directory not found: {self.agents_dir}")
            return agent_classes
        
        # Search for Python files and packages
        for path in self.agents_dir.iterdir():
            # Skip __pycache__ and hidden files
            if path.name.startswith('_') or path.name.startswith('.'):
                continue
            
            # Handle both .py files and directories (packages)
            if path.is_file() and path.suffix == '.py':
                module_name = path.stem
                agent_class = self._load_agent_from_module(module_name)
                if agent_class:
                    agent_classes.append(agent_class)
                    
            elif path.is_dir() and (path / '__init__.py').exists():
                # It's a package
                package_name = path.name
                agent_class = self._load_agent_from_package(package_name)
                if agent_class:
                    agent_classes.append(agent_class)
        
        logger.info(f"Discovered {len(agent_classes)} agent classes")
        return agent_classes
    
    def _load_agent_from_module(self, module_name: str) -> Optional[Type[BaseAgent]]:
        """
        Load an agent class from a Python module.
        
        Args:
            module_name: Name of the module (without .py extension)
            
        Returns:
            Agent class if found, None otherwise
        """
        try:
            # Import the module
            module_path = f"src.agents.plugins.{module_name}"
            module = importlib.import_module(module_path)
            
            # Look for BaseAgent subclasses
            agent_class = self._find_agent_class_in_module(module)
            
            if agent_class:
                logger.info(f"Loaded agent from module '{module_name}': {agent_class.__name__}")
                self._loaded_agents.add(module_name)
                return agent_class
            else:
                logger.debug(f"No agent class found in module '{module_name}'")
                
        except Exception as e:
            logger.error(f"Error loading agent from module '{module_name}': {e}")
        
        return None
    
    def _load_agent_from_package(self, package_name: str) -> Optional[Type[BaseAgent]]:
        """
        Load an agent class from a Python package.
        
        Args:
            package_name: Name of the package directory
            
        Returns:
            Agent class if found, None otherwise
        """
        try:
            # Import the package
            package_path = f"agents.{package_name}"
            package = importlib.import_module(package_path)
            
            # Look for BaseAgent subclasses
            agent_class = self._find_agent_class_in_module(package)
            
            if agent_class:
                logger.info(f"Loaded agent from package '{package_name}': {agent_class.__name__}")
                self._loaded_agents.add(package_name)
                return agent_class
            else:
                logger.debug(f"No agent class found in package '{package_name}'")
                
        except Exception as e:
            logger.error(f"Error loading agent from package '{package_name}': {e}")
        
        return None
    
    def _find_agent_class_in_module(self, module) -> Optional[Type[BaseAgent]]:
        """
        Find a BaseAgent subclass in a module.
        
        Args:
            module: The imported module
            
        Returns:
            First BaseAgent subclass found, or None
        """
        for name, obj in inspect.getmembers(module):
            # Check if it's a class
            if not inspect.isclass(obj):
                continue
            
            # Skip BaseAgent itself
            if obj is BaseAgent:
                continue
            
            # Check if it's a subclass of BaseAgent
            if issubclass(obj, BaseAgent):
                # Make sure it's defined in this module (not imported)
                if obj.__module__ == module.__name__:
                    return obj
        
        return None
    
    def load_agents(self, instantiate: bool = True, **agent_kwargs) -> List[BaseAgent]:
        """
        Load all discovered agents.
        
        Args:
            instantiate: If True, return agent instances; if False, return classes
            **agent_kwargs: Keyword arguments to pass to agent constructors
            
        Returns:
            List of agent instances or classes
        """
        agent_classes = self.discover_agents()
        
        if not instantiate:
            return agent_classes
        
        agents: List[BaseAgent] = []
        
        for agent_class in agent_classes:
            try:
                # Try to instantiate the agent
                # Some agents might need specific initialization parameters
                agent = agent_class(**agent_kwargs)
                agents.append(agent)
                logger.info(f"Instantiated agent: {agent.name}")
                
            except Exception as e:
                logger.error(f"Error instantiating agent {agent_class.__name__}: {e}")
        
        return agents
    
    def load_agent_by_name(self, agent_name: str, **agent_kwargs) -> Optional[BaseAgent]:
        """
        Load a specific agent by its class name or module name.
        
        Args:
            agent_name: Name of the agent class or module
            **agent_kwargs: Keyword arguments to pass to agent constructor
            
        Returns:
            Agent instance if found, None otherwise
        """
        agent_classes = self.discover_agents()
        
        for agent_class in agent_classes:
            if agent_class.__name__ == agent_name or agent_class.__module__.endswith(agent_name):
                try:
                    agent = agent_class(**agent_kwargs)
                    logger.info(f"Loaded agent by name '{agent_name}': {agent.name}")
                    return agent
                except Exception as e:
                    logger.error(f"Error instantiating agent {agent_name}: {e}")
                    return None
        
        logger.warning(f"Agent not found: {agent_name}")
        return None
    
    def reload_agents(self) -> List[BaseAgent]:
        """
        Reload all agents (useful for development).
        
        Returns:
            List of reloaded agent instances
        """
        # Clear the loaded agents set
        self._loaded_agents.clear()
        
        # Reload importlib to refresh module cache
        importlib.invalidate_caches()
        
        return self.load_agents()
