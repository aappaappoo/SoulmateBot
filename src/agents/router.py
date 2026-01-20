"""
多Agent消息路由系统

Router负责智能地将用户消息路由到最合适的Agent：
- 解析@提及
- 查询所有Agent的can_handle()获取置信度
- 根据配置策略选择Agent
- 管理并行执行
- 合并并返回响应
"""
from typing import List, Optional, Dict, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import asyncio
from loguru import logger

from .models import Message, ChatContext, AgentResponse
from .base_agent import BaseAgent


@dataclass
class RouterConfig:
    """
    路由器配置类
    
    属性说明:
        min_confidence: 最低置信度阈值 (0.0-1.0)，低于此值的Agent不会被选中
        max_agents: 单条消息最多允许几个Agent响应
        exclusive_mention: 当消息@提及某Agent时，是否只让该Agent响应
        enable_parallel: 是否启用并行执行（允许多个Agent同时处理）
        cooldown_seconds: 同一Agent对同一用户的最小响应间隔（秒）
        fallback_agent_name: 当没有Agent满足阈值时的备用Agent名称
        
    使用示例:
        config = RouterConfig(
            min_confidence=0.6,     # 只选择置信度>=0.6的Agent
            max_agents=2,           # 最多2个Agent响应
            exclusive_mention=True, # @提及时独占
        )
    """
    min_confidence: float = 0.5
    max_agents: int = 1
    exclusive_mention: bool = True
    enable_parallel: bool = False
    cooldown_seconds: float = 0.0
    fallback_agent_name: Optional[str] = None
    
    def __post_init__(self):
        """验证配置参数的有效性"""
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError(f"min_confidence必须在0.0-1.0之间，当前值: {self.min_confidence}")
        if self.max_agents < 1:
            raise ValueError(f"max_agents必须至少为1，当前值: {self.max_agents}")


class Router:
    """
    消息路由器 - 多Agent系统的核心
    
    根据置信度分数、@提及和配置策略，将消息路由到最合适的Agent。
    
    主要职责:
    1. 解析消息中的@提及
    2. 查询所有Agent的处理能力（置信度）
    3. 按配置选择合适的Agent
    4. 执行Agent并收集响应
    5. 应用冷却时间限制
    
    使用示例:
        agents = [EmotionalAgent(), TechAgent(), ToolAgent()]
        config = RouterConfig(min_confidence=0.5, max_agents=1)
        router = Router(agents, config)
        
        message = Message(content="我今天很难过", user_id="123", chat_id="456")
        context = ChatContext(chat_id="456")
        responses = router.route(message, context)
    """
    
    def __init__(
        self,
        agents: List[BaseAgent],
        config: Optional[RouterConfig] = None
    ):
        """
        初始化路由器
        
        参数:
            agents: 可用的Agent列表
            config: 路由配置（如果为None则使用默认配置）
        """
        # 使用Agent名称作为key构建字典，便于快速查找
        self.agents = {agent.name: agent for agent in agents}
        self.config = config or RouterConfig()
        # 记录每个Agent对每个用户的最后响应时间（用于冷却）
        self._last_response_times: Dict[str, Dict[str, datetime]] = {}
        
        logger.info(f"Router初始化完成，加载了 {len(self.agents)} 个Agent")
        logger.info(f"Router配置: {self.config}")
    
    def add_agent(self, agent: BaseAgent) -> None:
        """
        添加一个Agent到路由器
        
        参数:
            agent: 要添加的Agent实例
            
        注意:
            如果Agent名称已存在，会替换原有Agent
        """
            agent: Agent to add
        """
        if agent.name in self.agents:
            logger.warning(f"Agent '{agent.name}' already exists, replacing")
        
        self.agents[agent.name] = agent
        logger.info(f"Added agent: {agent.name}")
    
    def remove_agent(self, agent_name: str) -> bool:
        """
        Remove an agent from the router.
        
        Args:
            agent_name: Name of agent to remove
            
        Returns:
            True if agent was removed, False if not found
        """
        if agent_name in self.agents:
            del self.agents[agent_name]
            logger.info(f"Removed agent: {agent_name}")
            return True
        return False
    
    def extract_mentions(self, message: Message) -> List[str]:
        """
        Extract @mentions from a message.
        
        Args:
            message: The message to parse
            
        Returns:
            List of mentioned agent names (without @)
        """
        mentions = []
        words = message.content.split()
        
        for word in words:
            if word.startswith('@'):
                # Remove @ and any trailing punctuation
                agent_name = word[1:].rstrip(',.!?;:')
                if agent_name in self.agents:
                    mentions.append(agent_name)
        
        # Also check metadata
        if "mentions" in message.metadata:
            for mention in message.metadata["mentions"]:
                agent_name = mention.lstrip('@')
                if agent_name in self.agents and agent_name not in mentions:
                    mentions.append(agent_name)
        
        return mentions
    
    def _check_cooldown(self, agent_name: str, user_id: str) -> bool:
        """
        Check if agent is in cooldown period for this user.
        
        Args:
            agent_name: Name of the agent
            user_id: User ID
            
        Returns:
            True if cooldown has passed, False if still in cooldown
        """
        if self.config.cooldown_seconds <= 0:
            return True
        
        if agent_name not in self._last_response_times:
            return True
        
        if user_id not in self._last_response_times[agent_name]:
            return True
        
        last_time = self._last_response_times[agent_name][user_id]
        elapsed = (datetime.now(timezone.utc) - last_time).total_seconds()
        
        return elapsed >= self.config.cooldown_seconds
    
    def _update_cooldown(self, agent_name: str, user_id: str) -> None:
        """Update the last response time for cooldown tracking."""
        if agent_name not in self._last_response_times:
            self._last_response_times[agent_name] = {}
        
        self._last_response_times[agent_name][user_id] = datetime.now(timezone.utc)
    
    def select_agents(
        self,
        message: Message,
        context: ChatContext
    ) -> List[Tuple[BaseAgent, float]]:
        """
        Select which agents should respond to a message.
        
        Args:
            message: The incoming message
            context: Chat context
            
        Returns:
            List of (agent, confidence) tuples, sorted by confidence (highest first)
        """
        mentions = self.extract_mentions(message)
        
        # Handle explicit @mentions
        if mentions and self.config.exclusive_mention:
            logger.info(f"Exclusive mention mode: routing to mentioned agents: {mentions}")
            selected = []
            for agent_name in mentions:
                agent = self.agents[agent_name]
                # Check cooldown
                if not self._check_cooldown(agent_name, message.user_id):
                    logger.info(f"Agent {agent_name} is in cooldown for user {message.user_id}")
                    continue
                selected.append((agent, 1.0))  # Full confidence for explicit mentions
            return selected
        
        # Query all agents for their confidence scores
        candidates: List[tuple[BaseAgent, float]] = []
        
        for agent_name, agent in self.agents.items():
            # Check cooldown
            if not self._check_cooldown(agent_name, message.user_id):
                logger.debug(f"Agent {agent_name} is in cooldown for user {message.user_id}")
                continue
            
            try:
                confidence = agent.can_handle(message, context)
                
                # Validate confidence score
                if not 0.0 <= confidence <= 1.0:
                    logger.warning(
                        f"Agent {agent_name} returned invalid confidence {confidence}, "
                        f"clamping to [0.0, 1.0]"
                    )
                    confidence = max(0.0, min(1.0, confidence))
                
                logger.debug(f"Agent {agent_name} confidence: {confidence:.2f}")
                
                # Apply minimum confidence threshold
                if confidence >= self.config.min_confidence:
                    candidates.append((agent, confidence))
                    
            except Exception as e:
                logger.error(f"Error getting confidence from agent {agent_name}: {e}")
        
        # Sort by confidence (highest first)
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # Apply max_agents limit
        selected = candidates[:self.config.max_agents]
        
        # If no agents selected and fallback is configured
        if not selected and self.config.fallback_agent_name:
            fallback = self.agents.get(self.config.fallback_agent_name)
            if fallback and self._check_cooldown(self.config.fallback_agent_name, message.user_id):
                logger.info(f"Using fallback agent: {self.config.fallback_agent_name}")
                selected = [(fallback, self.config.min_confidence)]
        
        if selected:
            agent_info = ", ".join([f"{a.name}({c:.2f})" for a, c in selected])
            logger.info(f"Selected agents: {agent_info}")
        else:
            logger.info("No agents selected to respond")
        
        return selected
    
    async def route_async(
        self,
        message: Message,
        context: ChatContext
    ) -> List[AgentResponse]:
        """
        Route a message to appropriate agents asynchronously.
        
        Args:
            message: The incoming message
            context: Chat context
            
        Returns:
            List of agent responses, ordered deterministically
        """
        selected_agents = self.select_agents(message, context)
        
        if not selected_agents:
            return []
        
        responses: List[AgentResponse] = []
        
        if self.config.enable_parallel and len(selected_agents) > 1:
            # Execute agents in parallel
            logger.info(f"Executing {len(selected_agents)} agents in parallel")
            
            async def get_response(agent: BaseAgent) -> Optional[AgentResponse]:
                try:
                    # Run synchronous respond() in thread pool
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(None, agent.respond, message, context)
                except Exception as e:
                    logger.error(f"Error getting response from agent {agent.name}: {e}")
                    return None
            
            tasks = [get_response(agent) for agent, _ in selected_agents]
            results = await asyncio.gather(*tasks)
            
            responses = [r for r in results if r is not None]
        else:
            # Execute agents sequentially
            for agent, confidence in selected_agents:
                try:
                    logger.info(f"Getting response from agent: {agent.name}")
                    response = agent.respond(message, context)
                    responses.append(response)
                    
                    # Update cooldown
                    self._update_cooldown(agent.name, message.user_id)
                    
                    # Check if we should stop (agent says no other agents should respond)
                    if not response.should_continue:
                        logger.info(f"Agent {agent.name} requested exclusive response")
                        break
                        
                except Exception as e:
                    logger.error(f"Error getting response from agent {agent.name}: {e}")
        
        # Sort responses by confidence (highest first) for deterministic ordering
        responses.sort(key=lambda r: r.confidence, reverse=True)
        
        return responses
    
    def route(
        self,
        message: Message,
        context: ChatContext
    ) -> List[AgentResponse]:
        """
        Route a message to appropriate agents synchronously.
        
        Args:
            message: The incoming message
            context: Chat context
            
        Returns:
            List of agent responses, ordered deterministically
        """
        selected_agents = self.select_agents(message, context)
        
        if not selected_agents:
            return []
        
        responses: List[AgentResponse] = []
        
        for agent, confidence in selected_agents:
            try:
                logger.info(f"Getting response from agent: {agent.name}")
                response = agent.respond(message, context)
                responses.append(response)
                
                # Update cooldown
                self._update_cooldown(agent.name, message.user_id)
                
                # Check if we should stop
                if not response.should_continue:
                    logger.info(f"Agent {agent.name} requested exclusive response")
                    break
                    
            except Exception as e:
                logger.error(f"Error getting response from agent {agent.name}: {e}")
        
        # Sort responses by confidence for deterministic ordering
        responses.sort(key=lambda r: r.confidence, reverse=True)
        
        return responses
