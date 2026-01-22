# Claude Skills 集成指南

本文档说明如何在 SoulmateBot 中使用和集成 Claude Skills 功能。

## 什么是 Claude Skills

Claude Skills 是一种将 AI 能力模块化的机制，允许 Agent 系统根据用户需求动态选择和调用特定的技能模块。在 SoulmateBot 中，Skills 系统提供以下核心功能：

1. **技能注册与管理**：统一管理所有可用技能
2. **智能匹配**：根据用户输入自动匹配最相关的技能
3. **Telegram 按钮生成**：为用户提供可视化的技能选择界面
4. **与 Agent 系统集成**：技能可以关联到特定 Agent

## 核心组件

### 1. Skill（技能定义）

```python
from src.agents import Skill, SkillCategory

skill = Skill(
    id="my_skill",              # 唯一标识
    name="我的技能",            # 显示名称
    description="技能描述",     # 功能描述
    category=SkillCategory.TOOLS,  # 分类
    icon="🔧",                  # 图标（emoji）
    agent_name="MyAgent",       # 关联的Agent名称
    keywords=["关键词1", "关键词2"],  # 触发关键词
    priority=5                  # 显示优先级
)
```

### 2. SkillCategory（技能分类）

```python
from src.agents import SkillCategory

# 可用分类
SkillCategory.EMOTIONAL  # 情感支持类
SkillCategory.TECH       # 技术帮助类
SkillCategory.TOOLS      # 实用工具类
SkillCategory.ANALYSIS   # 分析任务类
SkillCategory.CREATIVE   # 创意任务类
SkillCategory.OTHER      # 其他类
```

### 3. SkillRegistry（技能注册表）

```python
from src.agents import skill_registry, register_skill

# 使用便捷函数注册技能
register_skill(
    id="weather_check",
    name="天气查询",
    description="查询实时天气信息",
    category=SkillCategory.TOOLS,
    icon="🌤️",
    agent_name="ToolAgent",
    keywords=["天气", "weather", "温度"],
    priority=8
)

# 或直接使用注册表
skill_registry.register(skill)

# 获取技能
skill = skill_registry.get("weather_check")

# 根据Agent名称获取
skill = skill_registry.get_by_agent("ToolAgent")

# 获取所有活跃技能
all_skills = skill_registry.get_all(active_only=True)

# 根据用户输入匹配技能
matched = skill_registry.match_skills("帮我查一下明天的天气", top_n=3)
```

### 4. SkillButtonGenerator（按钮生成器）

```python
from src.agents import skill_button_generator

# 生成主菜单按钮（Telegram InlineKeyboard 格式）
buttons = skill_button_generator.generate_main_menu(columns=2)

# 生成分类菜单
buttons = skill_button_generator.generate_category_menu(
    SkillCategory.TOOLS, 
    columns=2
)

# 根据用户输入生成匹配的技能按钮
buttons = skill_button_generator.generate_matched_skills(
    text="我想学习编程",
    include_cancel=True,
    columns=2
)
```

## 如何创建自定义 Agent 并关联 Skill

### 步骤 1：创建 Agent

在 `agents/` 目录下创建新的 Agent 文件：

```python
# agents/my_custom_agent.py
from typing import Dict, Any
from src.agents import BaseAgent, Message, ChatContext, AgentResponse, SQLiteMemoryStore

class MyCustomAgent(BaseAgent):
    def __init__(self, memory_store=None, llm_provider=None):
        self._name = "MyCustomAgent"
        self._description = "我的自定义Agent描述"
        self._memory = memory_store or SQLiteMemoryStore()
        self._llm_provider = llm_provider
        
        # 定义触发关键词
        self._keywords = ["关键词1", "关键词2", "keyword1"]
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    def can_handle(self, message: Message, context: ChatContext) -> float:
        """返回处理此消息的置信度 (0.0-1.0)"""
        if message.has_mention(self.name):
            return 1.0
        
        content = message.content.lower()
        matches = sum(1 for kw in self._keywords if kw in content)
        
        if matches >= 2:
            return 0.9
        elif matches == 1:
            return 0.6
        return 0.0
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        """生成响应"""
        # 可以使用 LLM 或规则生成响应
        if self._llm_provider:
            # 使用 LLM 生成响应
            response = await self._generate_with_llm(message)
        else:
            # 使用规则生成响应
            response = self._generate_rule_based(message)
        
        return AgentResponse(
            content=response,
            agent_name=self.name,
            confidence=0.85,
            metadata={},
            should_continue=False
        )
    
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        return self._memory.read(self.name, user_id)
    
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        self._memory.write(self.name, user_id, data)
```

### 步骤 2：注册对应的 Skill

在 `src/agents/skills.py` 的 `_register_default_skills` 方法中添加：

```python
Skill(
    id="my_custom_skill",
    name="我的技能",
    description="技能的详细描述",
    category=SkillCategory.OTHER,
    icon="🎯",
    agent_name="MyCustomAgent",
    keywords=["关键词1", "关键词2"],
    priority=5
),
```

或者在运行时动态注册：

```python
from src.agents import register_skill, SkillCategory

register_skill(
    id="my_custom_skill",
    name="我的技能",
    description="技能的详细描述",
    category=SkillCategory.OTHER,
    icon="🎯",
    agent_name="MyCustomAgent",
    keywords=["关键词1", "关键词2"],
    priority=5
)
```

### 步骤 3：使用 Skill 选择功能

在 Telegram Bot 处理器中：

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from src.agents import skill_button_generator

async def handle_skills_command(update, context):
    # 生成技能选择按钮
    buttons_data = skill_button_generator.generate_main_menu()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn["text"], callback_data=btn["callback_data"]) 
         for btn in row]
        for row in buttons_data
    ])
    
    await update.message.reply_text(
        "请选择需要的服务：",
        reply_markup=keyboard
    )
```

## AgentOrchestrator 集成

AgentOrchestrator 已经集成了 Skills 系统，会自动：

1. 当多个 Agent 可以处理时，生成技能选择按钮
2. 处理用户的技能选择回调
3. 执行选中的 Agent 并返回结果

```python
from src.agents import AgentOrchestrator, AgentLoader

# 加载所有 Agent
loader = AgentLoader(agents_dir="agents")
agents = loader.load_agents()

# 创建编排器（启用技能选择）
orchestrator = AgentOrchestrator(
    agents=agents,
    llm_provider=your_llm_provider,
    enable_skills=True,      # 启用技能选择
    skill_threshold=3        # 当超过3个Agent可用时显示选择菜单
)

# 处理消息
result = await orchestrator.process(message, context)

if result.intent_type == IntentType.SKILL_SELECTION:
    # 需要用户选择技能
    skill_options = result.skill_options
    # 生成 Telegram 按钮让用户选择
else:
    # 直接返回响应
    final_response = result.final_response
```

## 意图识别来源

从 v0.3.0 开始，系统会记录意图识别的来源：

```python
from src.agents import IntentSource

# 意图识别来源
IntentSource.RULE_BASED  # 基于规则（关键词匹配、置信度评分）
IntentSource.LLM_BASED   # 基于大模型推理
IntentSource.FALLBACK    # 回退机制（LLM失败时回退到规则）

# 在日志中会显示
# 🎯 Intent type: IntentType.SINGLE_AGENT | Source: rule_based
# 📌 意图识别来源: 基于LLM推理
```

## 最佳实践

### 1. 合理设置优先级

- 核心功能设置较高优先级（8-10）
- 通用功能设置中等优先级（4-7）
- 辅助功能设置较低优先级（1-3）

### 2. 关键词覆盖

- 包含中英文关键词
- 考虑用户可能的表达方式
- 避免关键词重叠过多

### 3. 技能分类

- 使用合适的分类便于管理
- 同分类技能可以组织在一起展示

### 4. 与 LLM 结合

- 当 LLM 提供者可用时，优先使用 LLM 生成响应
- 规则响应作为后备方案
- 在系统提示词中明确 Agent 的角色和限制

## 示例：完整集成流程

```python
# 1. 定义 Agent
class WeatherAgent(BaseAgent):
    def __init__(self, llm_provider=None):
        self._name = "WeatherAgent"
        self._description = "提供天气查询服务"
        self._llm_provider = llm_provider
        self._keywords = ["天气", "weather", "温度", "下雨"]
    
    def can_handle(self, message, context):
        # 检查关键词匹配
        ...
    
    def respond(self, message, context):
        # 调用天气 API 或使用 LLM 生成响应
        ...

# 2. 注册技能
from src.agents import register_skill, SkillCategory

register_skill(
    id="weather_query",
    name="天气查询",
    description="查询城市天气预报",
    category=SkillCategory.TOOLS,
    icon="🌤️",
    agent_name="WeatherAgent",
    keywords=["天气", "weather", "温度"],
    priority=8
)

# 3. 在 Bot 中使用
from src.handlers.agent_integration import handle_message_with_agents

# 消息处理器会自动使用 Skills 系统
application.add_handler(MessageHandler(
    filters.TEXT & ~filters.COMMAND,
    handle_message_with_agents
))
```

## 总结

Claude Skills 系统为 SoulmateBot 提供了灵活的技能管理和智能路由机制。通过合理使用 Skills，可以：

- 提升用户体验：让用户清楚知道可用的服务
- 减少 Token 消耗：避免不必要的 LLM 调用
- 方便扩展：轻松添加新的 Agent 和技能
- 智能路由：自动匹配最合适的处理方式
