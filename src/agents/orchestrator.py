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
from datetime import datetime
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


class IntentSource(str, Enum):
    """意图识别来源"""
    RULE_BASED = "rule_based"  # 基于规则（关键词匹配、置信度评分）
    LLM_BASED = "llm_based"    # 基于大模型推理
    LLM_UNIFIED = "llm_unified" # 基于大模型统一推理
    FALLBACK = "fallback"      # 回退机制


@dataclass
class MemoryAnalysis:
    """记忆分析结果（统一模式返回）"""
    is_important: bool = False
    importance_level: Optional[str] = None
    event_type: Optional[str] = None
    event_summary: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    event_date: Optional[str] = None
    raw_date_expression: Optional[str] = None

@dataclass
class OrchestratorResult:
    """编排器处理结果"""
    intent_type: IntentType
    intent_source: IntentSource = IntentSource.RULE_BASED  # 意图识别来源
    selected_agents: List[str] = field(default_factory=list)
    agent_responses: List[AgentResponse] = field(default_factory=list)
    final_response: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    skill_options: List[Dict[str, str]] = field(default_factory=list)
    memory_analysis: Optional[MemoryAnalysis] = None


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
    # 支持的情感标签
    SUPPORTED_EMOTIONS = ["happy", "gentle", "sad", "excited", "angry", "crying"]

    UNIFIED_PROMPT_TEMPLATE = """
请根据规则完成任务，并【只输出合法 JSON】。
=========================
【最高优先级硬约束】
=========================
1. 你【只能】输出 JSON，不允许包含任何解释性文字、标点或注释
2. JSON 必须能被标准 json.loads 直接解析
3. 除 direct_reply 字段外，禁止生成任何自然语言回复
4. 严格按照“强制格式要求”中的字段返回，不得增减字段

=========================
【任务总览】
=========================
你需要同时完成 4 个任务：
1. 意图识别
2. 回复生成（仅在特定条件下）
3. 对话摘要生成
4. 记忆分析

=========================
【任务 1：意图识别】
=========================
判断用户消息应如何处理，intent 只能是以下三种之一：

- "direct_response"：
  日常闲聊、问候、简单问答，你可以直接回复用户

- "single_agent"：
  需要某一个专业 Agent 处理的问题

- "multi_agent"：
  需要多个 Agent 协作的问题

可用 Agent 能力如下：
{agent_capabilities}

当 intent 为：
- direct_response → agents 设为空数组 []
- single_agent / multi_agent → agents 填写需要调用的 Agent 名称

=========================
【任务 2：生成回复】
=========================
⚠️【关键条件规则】⚠️

- 仅当 intent == "direct_response" 时：
  - 才允许在 direct_reply 中生成回复文本
  - emotion / emotion_description 才允许填写

- 当 intent != "direct_response" 时：
  - direct_reply 必须为 ""
  - emotion 必须为 null
  - emotion_description 必须为 null

回复生成规则：
- 回复内容中【不要】包含情绪说明或语气描述
- 回复必须是纯文本
- 不要出现表情符号解释、情绪标签或括号说明

多消息规则：
- 如需拆分为多条消息，用 [MSG_SPLIT] 分隔
- 最多拆分为 3 条
- 仅在自然需要时拆分

可用系统风格约束：
{system_prompt}

=========================
【任务 3：对话摘要生成】
=========================
基于【完整对话历史 + 当前消息】生成一个“累积摘要”。

摘要要求：
- 描述的是“到目前为止的整体对话”
- 不仅是当前这一轮
- summary_text 控制在 100 字以内

需提取的关键要素：
- 时间（如：今天、昨天、具体日期）
- 地点
- 人物
- 事件
- 用户情绪

同时给出：
- topics：对话核心话题
- user_state：用户当前状态的客观描述

=========================
【任务 4：记忆分析】
=========================
判断是否存在“值得长期记忆”的信息。

不需要记忆的情况：
- 日常寒暄
- 已在历史中完整重复的信息

需要记忆的情况示例：
- 用户偏好
- 长期目标
- 重要情绪状态
- 重要生活事件

若 is_important 为 false：
- 其余 memory 字段全部设为 null 或空数组

=========================
【当前时间】
=========================
{current_time}

=========================
【强制 JSON 输出格式】
=========================

你必须严格按以下格式输出：

```json
    {{
    "intent": "direct_response" | "single_agent" | "multi_agent",
    "agents": [],
    "reasoning": "判断理由",
    
    "conversation_summary": {{
        "summary_text": "综合整个对话的摘要文本（100字以内）",
        "key_elements": {{
            "time": ["时间点1", "时间点2"],
            "place": ["地点1", "地点2"],
            "people": ["人物1", "人物2"],
            "events": ["事件1", "事件2"],
            "emotions": ["情绪1", "情绪2"]
        }},
        "topics": ["话题1", "话题2", "话题3"],
        "user_state": "用户当前状态描述"
    }},
    
    "direct_reply": "纯文本回复内容，按照上面回复内容格式说明进行",
    "emotion": "happy" | "gentle" | "sad" | "excited" | "angry" | "crying" | null,
    "emotion_description": "详细的语气描述，如：开心、轻快，语速稍快，语调上扬" | null,
    "memory": {{
        "is_important": false,
        "importance_level": "low" | "medium" | "high" | null,
        "event_type": "preference" | "birthday" | "goal" | "emotion" | "life_event" | null,
        "event_summary": "事件摘要" | null,
        "keywords": [],
        "event_date": "YYYY-MM-DD" | null,
        "raw_date_expression": "原始时间表达" | null
    }}
}}
```
"""
    def __init__(
        self,
        agents: List[BaseAgent],
        llm_provider=None,
        enable_skills: bool = True,
        skill_threshold: int = 3,  # 超过此数量的可选Agent时使用技能选择
        enable_unified_mode: bool = True
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
        self.enable_unified_mode = enable_unified_mode

        # 构建Agent能力描述
        self._capabilities = self._build_capabilities()
        
        # 创建内部Router用于基于置信度的Agent选择
        self._router = Router(agents, RouterConfig(
            min_confidence=0.3,
            max_agents=5,
            enable_parallel=True
        ))
        
        logger.info(f"AgentOrchestrator初始化完成，加载了{len(self.agents)}个Agent")

    # 统一分析
    async def analyze_intent_unified(
            self,
            message: Message,
            context: ChatContext
    ) -> Tuple[IntentType, List[str], Dict[str, Any], IntentSource, Optional[str], Optional[MemoryAnalysis]]:
        """
        统一分析：一次 LLM 调用完成意图识别 + 回复生成 + 记忆分析
        """
        selected_by_confidence = self._router.select_agents(message, context)

        if not self.llm_provider:
            if not selected_by_confidence:
                return IntentType.DIRECT_RESPONSE, [], {}, IntentSource.RULE_BASED, None, None
            elif len(selected_by_confidence) == 1:
                return IntentType.SINGLE_AGENT, [
                    selected_by_confidence[0][0].name], {}, IntentSource.RULE_BASED, None, None
            else:
                return IntentType.MULTI_AGENT, [a.name for a, _ in
                                                selected_by_confidence], {}, IntentSource.RULE_BASED, None, None

        try:
            # ========== 构建完整的消息列表 ==========
            messages = []
            
            # 1. 构建增强的 System Prompt
            # 包含：Bot人设 + 用户记忆 + 对话策略 + UNIFIED_PROMPT_TEMPLATE任务要求 + 返回格式
            base_system_prompt = context.system_prompt if context and context.system_prompt else ""
            
            # 将 UNIFIED_PROMPT_TEMPLATE 整合到 System Prompt 中
            unified_task_prompt = self.UNIFIED_PROMPT_TEMPLATE.format(
                agent_capabilities=self._get_capabilities_prompt(),
                system_prompt="（参见上方的人设设定）",
                current_time=datetime.now().strftime("%Y年%m月%d日 %H:%M"),
            )
            # 组合完整的 System Prompt
            # base_system_prompt 已包含：人设 + 记忆 + 策略 + 对话历史提示
            # unified_task_prompt 包含：任务要求 + 返回格式
            enhanced_system_prompt = f"""{base_system_prompt}
=========================
📋 任务指令
=========================
{unified_task_prompt}"""
            print("111111111")
            print(enhanced_system_prompt)
            messages.append({
                "role": "system",
                "content": enhanced_system_prompt
            })

            # 2. 短期对话历史（最近 5 轮，即 10 条消息）
            if context and context.conversation_history:
                recent_history = context.conversation_history[-10:]  # 最多10条（5轮对话）
                for hist_msg in recent_history:
                    if hasattr(hist_msg, 'content') and hasattr(hist_msg, 'user_id'):
                        # 判断是用户还是助手
                        user_id_str = str(hist_msg.user_id).lower()
                        if "agent" in user_id_str or "bot" in user_id_str or "assistant" in user_id_str:
                            role = "assistant"
                        else:
                            role = "user"
                        messages.append({
                            "role": role,
                            "content": hist_msg.content
                        })
                    elif isinstance(hist_msg, dict):
                        # 如果已经是 dict 格式，直接使用
                        messages.append(hist_msg)
            
            # 3. 当前用户消息（纯用户消息，任务指令已在 system prompt 中）
            messages.append({
                "role": "user",
                "content": message.content
            })
            
            # 添加日志，方便调试
            logger.info(f"📨 [Orchestrator] Sending {len(messages)} messages to LLM")
            logger.debug(f"📨 [Orchestrator] Message roles: {[m['role'] for m in messages]}")
            
            # 调用 LLM（使用完整的消息列表）
            response = await self.llm_provider.generate_response(
                messages,  # ← 完整的消息列表，不是只有一条
                context=None  # context 已经在 system prompt 中
            )

            # 验证响应不为空
            if not response:
                logger.error(f"❌ [Orchestrator] LLM returned empty response! Messages count: {len(messages)}")
                logger.debug(f"📝 [Orchestrator] Last message content preview: {messages[-1].get('content', '')[:200]}...")
                raise ValueError("LLM returned empty response")
            
            # 解析 JSON
            response_text = response.strip()
            
            # 检查响应是否为空字符串
            if not response_text:
                logger.error(f"❌ [Orchestrator] LLM response is empty after strip! Original response: {repr(response)}")
                raise ValueError("LLM response is empty after processing")
            
            logger.debug(f"📤 [Orchestrator] Raw LLM response (first 500 chars): {response_text[:500]}...")
            
            # 尝试多种方式提取JSON
            json_text = None
            
            # 方式1: 从 ```json 代码块提取
            if "```json" in response_text:
                json_text = response_text.split("```json")[1].split("```")[0].strip()
            # 方式2: 从 ``` 代码块提取
            elif "```" in response_text:
                json_text = response_text.split("```")[1].split("```")[0].strip()
            # 方式3: 查找JSON对象（使用括号匹配而非正则）
            else:
                # 尝试找到平衡的 {} 括号对
                start_idx = response_text.find('{')
                if start_idx != -1:
                    depth = 0
                    end_idx = start_idx
                    for i, char in enumerate(response_text[start_idx:], start_idx):
                        if char == '{':
                            depth += 1
                        elif char == '}':
                            depth -= 1
                            if depth == 0:
                                end_idx = i
                                break
                    if depth == 0:
                        json_text = response_text[start_idx:end_idx + 1].strip()
            
            # 如果仍未找到，尝试直接解析（可能响应本身就是JSON）
            if not json_text:
                json_text = response_text.strip()
            
            # 验证提取后的JSON不为空
            if not json_text:
                logger.error(f"❌ [Orchestrator] Extracted JSON content is empty! Full response: {response[:500]}...")
                raise ValueError("Extracted JSON content is empty")

            try:
                data = json.loads(json_text)
            except json.JSONDecodeError as je:
                logger.error(f"❌ [Orchestrator] JSON parse error: {je}")
                logger.error(f"📝 [Orchestrator] Failed JSON text: {json_text[:500]}...")
                raise

            intent = IntentType(data.get("intent", "direct_response"))
            agents = [a for a in data.get("agents", []) if a in self.agents]
            metadata = {"reasoning": data.get("reasoning", "")}
            direct_reply = data.get("direct_reply")

            # 提取情感标签并添加DEBUG日志
            emotion = data.get("emotion")
            emotion_description = None
            if emotion and emotion in self.SUPPORTED_EMOTIONS:
                emotion_description = data.get("emotion_description")
                logger.debug(f"🎭 [EMOTION EXTRACT] Extracted emotion from LLM response: emotion={emotion}, emotion_description={emotion_description}")
                metadata["emotion"] = emotion
                if emotion_description:
                    metadata["emotion_description"] = emotion_description
            else:
                logger.debug(f"🎭 [EMOTION EXTRACT] No valid emotion extracted from LLM response: raw_emotion={emotion}")

            memory_data = data.get("memory", {})
            memory_analysis = MemoryAnalysis(
                is_important=memory_data.get("is_important", False),
                importance_level=memory_data.get("importance_level"),
                event_type=memory_data.get("event_type"),
                event_summary=memory_data.get("event_summary"),
                keywords=memory_data.get("keywords", []),
                event_date=memory_data.get("event_date"),
                raw_date_expression=memory_data.get("raw_date_expression"),
            )

            # 解析对话摘要
            conversation_summary = data.get("conversation_summary")
            if conversation_summary:
                # 验证摘要结构
                if isinstance(conversation_summary, dict):
                    required_fields = ['summary_text', 'key_elements', 'topics', 'user_state']
                    if all(field in conversation_summary for field in required_fields):
                        metadata["conversation_summary"] = conversation_summary
                        logger.debug(f"📝 [SUMMARY] Generated summary: {conversation_summary.get('summary_text', '')[:50]}...")
                    else:
                        logger.warning(f"📝 [SUMMARY] Incomplete summary structure, missing fields: {[f for f in required_fields if f not in conversation_summary]}")
                else:
                    logger.warning(f"📝 [SUMMARY] Invalid summary type: {type(conversation_summary)}")

            logger.info(f"📌 统一模式 | intent={intent} | is_important={memory_analysis.is_important} | emotion={emotion}" + (f" | emotion_description={emotion_description}" if emotion_description else ""))
            return intent, agents, metadata, IntentSource.LLM_UNIFIED, direct_reply, memory_analysis

        except Exception as e:
            import traceback
            logger.error(f"❌ 统一分析出错: {e}")
            logger.error(f"📝 错误类型: {type(e).__name__}")
            logger.debug(f"📝 完整堆栈: {traceback.format_exc()}")
            logger.info(f"⚠️ 回退到规则模式，selected_by_confidence has {len(selected_by_confidence) if selected_by_confidence else 0} agents")
            if selected_by_confidence:
                return IntentType.SINGLE_AGENT, [
                    selected_by_confidence[0][0].name], {}, IntentSource.FALLBACK, None, None
            return IntentType.DIRECT_RESPONSE, [], {}, IntentSource.FALLBACK, None, None

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
    ) -> Tuple[IntentType, List[str], Dict[str, Any], IntentSource]:
        """
        分析用户消息的意图
        
        使用LLM分析消息内容，判断需要调用哪些Agent。
        
        Args:
            message: 用户消息
            context: 对话上下文
            
        Returns:
            Tuple[IntentType, List[str], Dict, IntentSource]: 
                (意图类型, 选中的Agent名称列表, 元数据, 意图识别来源)
        """
        # 首先使用Router的基于规则的置信度评估
        selected_by_confidence = self._router.select_agents(message, context)
        
        # 如果没有LLM提供者，直接使用基于规则的结果
        if not self.llm_provider:
            logger.info("📌 意图识别来源: 基于规则 (无LLM提供者)")
            if not selected_by_confidence:
                return IntentType.DIRECT_RESPONSE, [], {}, IntentSource.RULE_BASED
            elif len(selected_by_confidence) == 1:
                return IntentType.SINGLE_AGENT, [selected_by_confidence[0][0].name], {}, IntentSource.RULE_BASED
            else:
                agent_names = [agent.name for agent, _ in selected_by_confidence]
                return IntentType.MULTI_AGENT, agent_names, {}, IntentSource.RULE_BASED
        
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
                
                logger.info("📌 意图识别来源: 基于LLM推理")
                return intent, valid_agents, metadata, IntentSource.LLM_BASED
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"解析LLM意图响应失败: {e}")
                logger.info("📌 意图识别来源: 回退到规则 (LLM解析失败)")
                # 回退到基于规则的结果
                if selected_by_confidence:
                    agent_names = [agent.name for agent, _ in selected_by_confidence]
                    intent = IntentType.SINGLE_AGENT if len(agent_names) == 1 else IntentType.MULTI_AGENT
                    return intent, agent_names, {}, IntentSource.FALLBACK
                return IntentType.DIRECT_RESPONSE, [], {}, IntentSource.FALLBACK
                
        except Exception as e:
            logger.error(f"LLM意图分析出错: {e}")
            logger.info("📌 意图识别来源: 回退到规则 (LLM调用失败)")
            # 回退到基于规则的结果
            if selected_by_confidence:
                agent_names = [agent.name for agent, _ in selected_by_confidence]
                intent = IntentType.SINGLE_AGENT if len(agent_names) == 1 else IntentType.MULTI_AGENT
                return intent, agent_names, {}, IntentSource.FALLBACK
            return IntentType.DIRECT_RESPONSE, [], {}, IntentSource.FALLBACK
    
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
4. 直接回答用户的问题
5. 回复内容中不要包含语气标注，直接输出纯文本回复"""

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
        """处理用户消息的主入口"""
        result = OrchestratorResult(intent_type=IntentType.DIRECT_RESPONSE)

        # 根据配置选择处理模式
        if self.enable_unified_mode and self.llm_provider:
            # 🔑 统一模式
            intent_type, agent_names, metadata, intent_source, direct_reply, memory_analysis = \
                await self.analyze_intent_unified(message, context)

            result.intent_type = intent_type
            result.intent_source = intent_source
            result.selected_agents = agent_names
            result.metadata = metadata
            result.metadata["intent_source"] = intent_source.value
            result.memory_analysis = memory_analysis
        else:
            # 原有模式
            intent_type, agent_names, metadata, intent_source = await self.analyze_intent(message, context)
            result.intent_type = intent_type
            result.intent_source = intent_source
            result.selected_agents = agent_names
            result.metadata = metadata
            result.metadata["intent_source"] = intent_source.value
            direct_reply = None

        logger.info(f"🎯 Intent type: {result.intent_type} | Source: {result.intent_source}")

        # 技能选择检查
        if self.enable_skills and (force_skill_selection or len(result.selected_agents) >= self.skill_threshold):
            skill_options = self.generate_skill_options(message, context)
            if skill_options:
                result.intent_type = IntentType.SKILL_SELECTION
                result.skill_options = skill_options
                result.final_response = "请选择您需要的服务："
                return result

        # 直接响应
        if result.intent_type == IntentType.DIRECT_RESPONSE or not result.selected_agents:
            if direct_reply:
                result.final_response = direct_reply
            elif self.llm_provider:
                try:
                    messages = []
                    if context and context.system_prompt:
                        messages.append({"role": "system", "content": context.system_prompt})
                    messages.append({"role": "user", "content": message.content})
                    result.final_response = await self.llm_provider.generate_response(messages, context=None)
                except Exception as e:
                    logger.error(f"直接响应生成失败: {e}")
                    result.final_response = "你好！有什么我可以帮助你的吗？"
            else:
                result.final_response = "你好！有什么我可以帮助你的吗？"
            return result

        # Agent 处理
        agent_responses = await self.execute_agents(message, context, result.selected_agents)
        result.agent_responses = agent_responses
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
