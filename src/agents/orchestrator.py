"""
LLM-Powered Agent Orchestrator

This module provides intelligent orchestration for the multi-agent system.
It uses LLM to automatically determine which agents/tools to invoke based on user requests,
and coordinates multiple agent responses into a final coherent reply.

核心功能：
1. 自动识别用户意图，判断是否需要调用Agent能力
2. 支持调用多个Agent并协调结果
3. 使用最终Agent生成统一回复
4. 支持Skills系统减少token消耗
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import asyncio
from loguru import logger

from .base_agent import BaseAgent
from .models import Message, ChatContext, AgentResponse
from .router import Router, RouterConfig


class IntentType(str, Enum):
    """用户意图类型"""
    DIRECT_RESPONSE = "direct_response"  # 直接回复，无需Agent
    SINGLE_AGENT = "single_agent"  # 需要单个Agent处理
    MULTI_AGENT = "multi_agent"  # 需要多个Agent协作
    TOOL_CALL = "tool_call"  # 需要调用工具
    SKILL_SELECTION = "skill_selection"  # 需要用户选择技能


@dataclass
class AgentCapability:
    """Agent能力描述"""
    name: str
    description: str
    keywords: List[str] = field(default_factory=list)
    is_tool: bool = False


@dataclass
class OrchestratorResult:
    """编排器处理结果"""
    intent_type: IntentType
    selected_agents: List[str] = field(default_factory=list)
    agent_responses: List[AgentResponse] = field(default_factory=list)
    final_response: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    skill_options: List[Dict[str, str]] = field(default_factory=list)


class AgentOrchestrator:
    """
    智能Agent编排器
    
    使用LLM自动分析用户请求，决定调用哪些Agent，
    并协调多个Agent的输出生成最终回复。
    
    工作流程:
    1. 分析用户消息，识别意图
    2. 根据意图选择合适的Agent(s)
    3. 调用选中的Agent获取响应
    4. 使用最终决策Agent整合所有响应
    5. 返回最终结果给用户
    """
    
    def __init__(
        self,
        agents: List[BaseAgent],
        llm_provider=None,
        enable_skills: bool = True,
        skill_threshold: int = 3,  # 超过此数量的可选Agent时使用技能选择
    ):
        """
        初始化编排器
        
        Args:
            agents: 可用的Agent列表
            llm_provider: LLM提供者实例（用于意图识别和最终决策）
            enable_skills: 是否启用技能选择模式（生成Telegram按钮）
            skill_threshold: 触发技能选择的Agent数量阈值
        """
        self.agents = {agent.name: agent for agent in agents}
        self.llm_provider = llm_provider
        self.enable_skills = enable_skills
        self.skill_threshold = skill_threshold
        
        # 构建Agent能力描述
        self._capabilities = self._build_capabilities()
        
        # 创建内部Router用于基于置信度的Agent选择
        self._router = Router(agents, RouterConfig(
            min_confidence=0.3,
            max_agents=5,
            enable_parallel=True
        ))
        
        logger.info(f"AgentOrchestrator初始化完成，加载了{len(self.agents)}个Agent")
    
    def _build_capabilities(self) -> List[AgentCapability]:
        """构建所有Agent的能力描述列表"""
        capabilities = []
        for name, agent in self.agents.items():
            cap = AgentCapability(
                name=name,
                description=agent.description,
                keywords=getattr(agent, '_emotional_keywords', []) or 
                         getattr(agent, '_tech_keywords', []) or 
                         getattr(agent, '_tool_keywords', []),
                is_tool=name.lower().endswith('agent') and 'tool' in name.lower()
            )
            capabilities.append(cap)
        return capabilities
    
    def _get_capabilities_prompt(self) -> str:
        """生成Agent能力描述的提示词"""
        cap_list = []
        for cap in self._capabilities:
            cap_type = "工具" if cap.is_tool else "Agent"
            cap_list.append(f"- {cap.name} ({cap_type}): {cap.description}")
        return "\n".join(cap_list)
    
    async def analyze_intent(
        self,
        message: Message,
        context: ChatContext
    ) -> Tuple[IntentType, List[str], Dict[str, Any]]:
        """
        分析用户消息的意图
        
        使用LLM分析消息内容，判断需要调用哪些Agent。
        
        Args:
            message: 用户消息
            context: 对话上下文
            
        Returns:
            Tuple[IntentType, List[str], Dict]: (意图类型, 选中的Agent名称列表, 元数据)
        """
        # 首先使用Router的基于规则的置信度评估
        selected_by_confidence = self._router.select_agents(message, context)
        
        # 如果没有LLM提供者，直接使用基于规则的结果
        if not self.llm_provider:
            if not selected_by_confidence:
                return IntentType.DIRECT_RESPONSE, [], {}
            elif len(selected_by_confidence) == 1:
                return IntentType.SINGLE_AGENT, [selected_by_confidence[0][0].name], {}
            else:
                agent_names = [agent.name for agent, _ in selected_by_confidence]
                return IntentType.MULTI_AGENT, agent_names, {}
        
        # 使用LLM进行更精确的意图识别
        try:
            intent_prompt = f"""分析以下用户消息，判断应该如何处理。

可用的Agent能力:
{self._get_capabilities_prompt()}

用户消息: {message.content}

请以JSON格式回复，包含以下字段:
- intent: "direct_response" | "single_agent" | "multi_agent" | "tool_call"
- agents: [选中的Agent名称列表]
- reasoning: 选择原因

只返回JSON，不要其他内容。"""

            response = await self.llm_provider.generate_response(
                [{"role": "user", "content": intent_prompt}],
                context="你是一个智能路由助手，负责分析用户意图并选择合适的处理方式。"
            )
            
            # 解析LLM响应
            try:
                # 尝试提取JSON
                response_text = response.strip()
                if response_text.startswith("```"):
                    response_text = response_text.split("```")[1]
                    if response_text.startswith("json"):
                        response_text = response_text[4:]
                
                result = json.loads(response_text)
                intent = IntentType(result.get("intent", "direct_response"))
                agents = result.get("agents", [])
                metadata = {"reasoning": result.get("reasoning", "")}
                
                # 验证Agent名称
                valid_agents = [a for a in agents if a in self.agents]
                
                return intent, valid_agents, metadata
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"解析LLM意图响应失败: {e}")
                # 回退到基于规则的结果
                if selected_by_confidence:
                    agent_names = [agent.name for agent, _ in selected_by_confidence]
                    intent = IntentType.SINGLE_AGENT if len(agent_names) == 1 else IntentType.MULTI_AGENT
                    return intent, agent_names, {}
                return IntentType.DIRECT_RESPONSE, [], {}
                
        except Exception as e:
            logger.error(f"LLM意图分析出错: {e}")
            # 回退到基于规则的结果
            if selected_by_confidence:
                agent_names = [agent.name for agent, _ in selected_by_confidence]
                intent = IntentType.SINGLE_AGENT if len(agent_names) == 1 else IntentType.MULTI_AGENT
                return intent, agent_names, {}
            return IntentType.DIRECT_RESPONSE, [], {}
    
    def generate_skill_options(
        self,
        message: Message,
        context: ChatContext
    ) -> List[Dict[str, str]]:
        """
        生成技能选项供用户选择
        
        当有多个可能的Agent时，生成Telegram按钮选项，
        让用户主动选择，以节省token消耗。
        
        Returns:
            List[Dict]: 包含button_text和callback_data的选项列表
        """
        options = []
        selected = self._router.select_agents(message, context)
        
        for agent, confidence in selected[:5]:  # 最多显示5个选项
            options.append({
                "button_text": f"{agent.name}",
                "callback_data": f"skill:{agent.name}",
                "description": agent.description[:50] + "..." if len(agent.description) > 50 else agent.description,
                "confidence": confidence
            })
        
        return options
    
    async def execute_agents(
        self,
        message: Message,
        context: ChatContext,
        agent_names: List[str]
    ) -> List[AgentResponse]:
        """
        执行指定的Agent并收集响应
        
        Args:
            message: 用户消息
            context: 对话上下文
            agent_names: 要执行的Agent名称列表
            
        Returns:
            List[AgentResponse]: Agent响应列表
        """
        responses = []
        
        for agent_name in agent_names:
            if agent_name not in self.agents:
                logger.warning(f"Agent未找到: {agent_name}")
                continue
            
            agent = self.agents[agent_name]
            try:
                response = agent.respond(message, context)
                responses.append(response)
                logger.info(f"Agent {agent_name} 响应成功")
            except Exception as e:
                logger.error(f"Agent {agent_name} 执行失败: {e}")
        
        return responses
    
    async def synthesize_response(
        self,
        message: Message,
        agent_responses: List[AgentResponse],
        context: ChatContext
    ) -> str:
        """
        综合多个Agent的响应生成最终回复
        
        使用LLM整合所有Agent的输出，生成统一连贯的回复。
        
        Args:
            message: 原始用户消息
            agent_responses: 各Agent的响应
            context: 对话上下文
            
        Returns:
            str: 最终综合回复
        """
        if not agent_responses:
            return "抱歉，我目前无法处理您的请求。请稍后再试。"
        
        # 如果只有一个响应，直接返回
        if len(agent_responses) == 1:
            return agent_responses[0].content
        
        # 如果没有LLM提供者，简单拼接响应
        if not self.llm_provider:
            combined = []
            for resp in agent_responses:
                combined.append(f"【{resp.agent_name}】\n{resp.content}")
            return "\n\n".join(combined)
        
        # 使用LLM综合多个响应
        try:
            responses_text = ""
            for resp in agent_responses:
                responses_text += f"\n[{resp.agent_name}的分析]:\n{resp.content}\n"
            
            synthesis_prompt = f"""用户问题: {message.content}

各专家的分析结果:
{responses_text}

请综合以上各专家的分析，生成一个完整、连贯的回复给用户。
要求：
1. 整合各专家的观点
2. 保持语气一致和自然
3. 不要提及"专家"或"分析结果"
4. 直接回答用户的问题"""

            final_response = await self.llm_provider.generate_response(
                [{"role": "user", "content": synthesis_prompt}],
                context="你是一个智能助手，负责整合多个专家的意见给用户提供完整的回答。"
            )
            
            return final_response
            
        except Exception as e:
            logger.error(f"综合响应生成失败: {e}")
            # 回退到简单拼接
            return agent_responses[0].content
    
    async def process(
        self,
        message: Message,
        context: ChatContext,
        force_skill_selection: bool = False
    ) -> OrchestratorResult:
        """
        处理用户消息的主入口
        
        完整的处理流程：
        1. 分析意图
        2. 决定是否使用技能选择
        3. 执行Agent
        4. 综合响应
        
        Args:
            message: 用户消息
            context: 对话上下文
            force_skill_selection: 强制使用技能选择模式
            
        Returns:
            OrchestratorResult: 处理结果
        """
        result = OrchestratorResult(intent_type=IntentType.DIRECT_RESPONSE)
        
        # 分析意图
        intent_type, agent_names, metadata = await self.analyze_intent(message, context)
        result.intent_type = intent_type
        result.selected_agents = agent_names
        result.metadata = metadata
        
        # 检查是否需要使用技能选择
        if self.enable_skills and (force_skill_selection or len(agent_names) >= self.skill_threshold):
            skill_options = self.generate_skill_options(message, context)
            if skill_options:
                result.intent_type = IntentType.SKILL_SELECTION
                result.skill_options = skill_options
                result.final_response = "请选择您需要的服务："
                return result
        
        # 如果是直接响应类型，不需要Agent
        if intent_type == IntentType.DIRECT_RESPONSE or not agent_names:
            # 使用LLM直接回复
            if self.llm_provider:
                try:
                    result.final_response = await self.llm_provider.generate_response(
                        [{"role": "user", "content": message.content}],
                        context=None
                    )
                except Exception as e:
                    logger.error(f"直接响应生成失败: {e}")
                    result.final_response = "你好！有什么我可以帮助你的吗？"
            else:
                result.final_response = "你好！有什么我可以帮助你的吗？"
            return result
        
        # 执行选中的Agent
        agent_responses = await self.execute_agents(message, context, agent_names)
        result.agent_responses = agent_responses
        
        # 综合响应
        result.final_response = await self.synthesize_response(message, agent_responses, context)
        
        return result
    
    async def process_skill_callback(
        self,
        skill_name: str,
        message: Message,
        context: ChatContext
    ) -> OrchestratorResult:
        """
        处理用户的技能选择回调
        
        当用户点击技能按钮后，执行相应的Agent。
        
        Args:
            skill_name: 用户选择的技能（Agent）名称
            message: 原始用户消息
            context: 对话上下文
            
        Returns:
            OrchestratorResult: 处理结果
        """
        result = OrchestratorResult(
            intent_type=IntentType.SINGLE_AGENT,
            selected_agents=[skill_name]
        )
        
        if skill_name not in self.agents:
            result.final_response = f"抱歉，技能 '{skill_name}' 不可用。"
            return result
        
        # 执行选中的Agent
        agent_responses = await self.execute_agents(message, context, [skill_name])
        result.agent_responses = agent_responses
        
        if agent_responses:
            result.final_response = agent_responses[0].content
        else:
            result.final_response = "抱歉，处理请求时发生错误。"
        
        return result
    
    def add_agent(self, agent: BaseAgent) -> None:
        """动态添加Agent"""
        self.agents[agent.name] = agent
        self._capabilities = self._build_capabilities()
        self._router.add_agent(agent)
        logger.info(f"添加Agent: {agent.name}")
    
    def remove_agent(self, agent_name: str) -> bool:
        """动态移除Agent"""
        if agent_name in self.agents:
            del self.agents[agent_name]
            self._capabilities = self._build_capabilities()
            self._router.remove_agent(agent_name)
            logger.info(f"移除Agent: {agent_name}")
            return True
        return False
