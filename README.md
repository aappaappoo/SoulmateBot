span

# 🤖 SoulmateBot - 智能多Agent对话机器人平台

一个基于 Telegram 的智能对话机器人平台，采用多Agent架构，支持多种AI服务商，提供情感陪伴、技术支持、金融理财、健康顾问等多领域服务。

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)](https://telegram.org/)

</div>

---

## 📖 目录

- [功能特性](#-功能特性)
- [系统架构](#-系统架构)
- [数据流程](#-数据流程)
- [核心组件](#-核心组件)
- [快速开始](#-快速开始)
- [Agent系统详解](#-agent系统详解)
- [Skills技能系统](#-skills技能系统)
- [配置说明](#-配置说明)
- [项目结构](#-项目结构)
- [开发指南](#-开发指南)
- [部署指南](#-部署指南)
- [常见问题](#-常见问题)

---

## ✨ 功能特性

### 🎯 核心功能


| 功能               | 描述                                    |
| ------------------ | --------------------------------------- |
| 💬**智能对话**     | 基于 GPT-4/Claude/vLLM 的智能对话系统   |
| 🤖**多Agent协作**  | 情感支持、技术帮助、金融理财等专业Agent |
| 🔀**智能路由**     | LLM + 规则双模式意图识别与Agent选择     |
| 🎛️**Skills系统** | Telegram按钮式技能选择，减少Token消耗   |
| 🔧**工具调用**     | 支持天气查询、时间获取、计算等外部工具  |
| 📊**订阅管理**     | 完整的订阅系统和使用限额管理            |
| 💳**支付集成**     | 支持微信支付和 Stripe                   |
| 🗄️**记忆系统**   | 用户记忆持久化，提供个性化服务          |
| 🎤**语音回复**     | 支持TTS语音回复，每个Bot可配置不同音色  |

### 🧠 内置Agent


| Agent             | 功能领域 | 适用场景                     |
| ----------------- | -------- | ---------------------------- |
| 💝 EmotionalAgent | 情感支持 | 倾诉烦恼、情绪疏导、日常陪伴 |
| 💻 TechAgent      | 技术帮助 | 编程问题、代码调试、技术指导 |
| 🔧 ToolAgent      | 实用工具 | 天气查询、时间获取、翻译计算 |
| 💰 FinanceAgent   | 金融理财 | 投资咨询、理财规划、市场分析 |
| 🏥 HealthAgent    | 健康顾问 | 健康指导、运动饮食、睡眠改善 |
| ⚖️ LegalAgent   | 法律咨询 | 法律知识、权益保护、维权指导 |
| 📚 EducationAgent | 学习指导 | 学习方法、考试准备、知识问答 |

### 🔧 技术特性

- **多AI服务商支持**：OpenAI、Anthropic Claude、vLLM
- **异步架构**：基于 asyncio 的高性能处理
- **插件化Agent**：自动发现和加载Agent
- **灵活的记忆存储**：支持内存、文件、SQLite
- **统一LLM网关**：自动重试、限流、Token统计

---

## 🏗️ 系统架构

### 整体架构图

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              用户层 (Users)                                   │
│                         Telegram 客户端用户                                   │
└────────────────────────────────────┬─────────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           Telegram Bot API                                    │
└────────────────────────────────────┬─────────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        SoulmateBot 核心 (main.py)                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                      Handlers 层 (消息处理)                              │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌───────────────────┐               │ │
│  │  │ commands.py  │ │ messages.py  │ │agent_integration.py│               │ │
│  │  │  命令处理    │ │  消息处理    │ │    Agent集成处理   │               │ │
│  │  └──────────────┘ └──────────────┘ └───────────────────┘               │ │
│  └──────────────────────────────────┬──────────────────────────────────────┘ │
│                                     │                                         │
│                                     ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                  Agent Orchestrator (智能编排器)                         │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │ │
│  │  │意图分析     │ │Agent选择    │ │多Agent协调  │ │响应综合     │       │ │
│  │  │(LLM/规则)  │ │(Router)     │ │(并行/串行)  │ │(最终回复)   │       │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘       │ │
│  └──────────────────────────────────┬──────────────────────────────────────┘ │
│                                     │                                         │
│                                     ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         Agent 层 (专业能力)                              │ │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ │ │
│  │  │Emotional  │ │  Tech     │ │  Tool     │ │ Finance   │ │  Health   │ │ │
│  │  │  Agent    │ │  Agent    │ │  Agent    │ │  Agent    │ │  Agent    │ │ │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘ │ │
│  │  ┌───────────┐ ┌───────────┐                                            │ │
│  │  │  Legal    │ │Education  │ │ ... 更多Agent                            │ │
│  │  │  Agent    │ │  Agent    │                                            │ │
│  │  └───────────┘ └───────────┘                                            │ │
│  └──────────────────────────────────┬──────────────────────────────────────┘ │
│                                     │                                         │
│                                     ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                      LLM Gateway (统一AI接口)                            │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │ │
│  │  │   OpenAI    │ │  Anthropic  │ │    vLLM     │ │ RateLimiter │       │ │
│  │  │  Provider   │ │  Provider   │ │  Provider   │ │  限流控制   │       │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘       │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
└───────────────────────────────────────┬──────────────────────────────────────┘
                                        │
                   ┌────────────────────┼────────────────────┐
                   ▼                    ▼                    ▼
            ┌──────────┐         ┌──────────┐         ┌──────────┐
            │PostgreSQL│         │  Redis   │         │ AI APIs  │
            │  数据库   │         │   缓存   │         │(外部服务) │
            └──────────┘         └──────────┘         └──────────┘
```

### 技术栈


| 层级        | 技术选型                               |
| ----------- | -------------------------------------- |
| **运行时**  | Python 3.11+                           |
| **Bot框架** | python-telegram-bot 20.7               |
| **AI集成**  | OpenAI GPT-4 / Anthropic Claude / vLLM |
| **数据库**  | PostgreSQL + SQLAlchemy ORM            |
| **缓存**    | Redis                                  |
| **支付**    | 微信支付 / Stripe                      |
| **容器化**  | Docker + Docker Compose                |

---

## 📊 数据流程

### 消息处理流程

```
用户发送消息
      │
      ▼
┌─────────────────┐
│ Telegram Handler │
│   接收消息       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 权限与限额检查   │──── 超限 ──→ 返回提示信息
│ (订阅/使用量)   │
└────────┬────────┘
         │ 通过
         ▼
┌─────────────────────────────────────┐
│        AgentOrchestrator            │
│                                     │
│  1. 意图分析 (analyze_intent)       │
│     ├─ 有LLM → LLM推理              │
│     └─ 无LLM → 规则匹配             │
│                                     │
│  2. Agent选择 (Router)              │
│     ├─ 单Agent → 直接执行           │
│     ├─ 多Agent → 技能选择/并行执行  │
│     └─ 无匹配 → 直接LLM回复         │
│                                     │
│  3. 执行Agent (execute_agents)      │
│     └─ 调用选中Agent的respond方法   │
│                                     │
│  4. 响应综合 (synthesize_response)  │
│     └─ 多Agent时由LLM整合回复       │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────┐
│  发送回复给用户  │
│  保存对话记录   │
└─────────────────┘
```

### 意图识别机制

系统采用**双模式意图识别**：

1. **LLM推理模式** (`IntentSource.LLM_BASED`)

   - 当配置了LLM提供者时使用
   - 通过LLM分析用户意图，选择合适的Agent
   - 更智能，但消耗Token
2. **规则匹配模式** (`IntentSource.RULE_BASED`)

   - 基于关键词匹配和置信度评分
   - 调用每个Agent的 `can_handle()` 方法
   - 选择置信度最高的Agent(s)
   - 快速，无额外Token消耗
3. **回退机制** (`IntentSource.FALLBACK`)

   - LLM调用失败时自动回退到规则模式
   - 确保系统稳定性

日志示例：

```
🎯 Intent type: IntentType.SINGLE_AGENT | Source: llm_based
📋 Selected agents: ['TechAgent']
```

---

## 🧩 核心组件

### AgentOrchestrator（编排器）

负责协调整个Agent系统的核心组件：

```python
from src.agents import AgentOrchestrator, AgentLoader

# 加载Agent
loader = AgentLoader(agents_dir="agents")
agents = loader.load_agents()

# 创建编排器
orchestrator = AgentOrchestrator(
    agents=agents,
    llm_provider=llm_provider,
    enable_skills=True,      # 启用技能选择
    skill_threshold=3        # 多于3个可选Agent时显示选择菜单
)

# 处理消息
result = await orchestrator.process(message, context)
```

### Router（路由器）

基于置信度的消息路由：

```python
from src.agents import Router, RouterConfig

config = RouterConfig(
    min_confidence=0.5,      # 最低置信度阈值
    max_agents=2,            # 最多响应的Agent数
    exclusive_mention=True,  # @提及时独占响应
    enable_parallel=True,    # 启用并行执行
)

router = Router(agents, config)
responses = router.route(message, context)
```

### Memory（记忆系统）

支持多种存储后端：

```python
from src.agents import InMemoryStore, FileMemoryStore, SQLiteMemoryStore

# 内存存储（会话级）
memory = InMemoryStore()

# 文件存储（JSON）
memory = FileMemoryStore(base_path="data/memory")

# SQLite存储（推荐）
memory = SQLiteMemoryStore(db_path="data/agent_memory.db")
```

---

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆仓库
git clone https://github.com/aappaappoo/SoulmateBot.git
cd SoulmateBot

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# Telegram Bot Token（必填）
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# AI 配置（至少配置一个）
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4

# 或使用 Anthropic
# ANTHROPIC_API_KEY=your_anthropic_api_key
# ANTHROPIC_MODEL=claude-3-sonnet-20240229

# 数据库
DATABASE_URL=sqlite:///./soulmatebot.db
```

### 3. 初始化数据库

```bash
span
```

### 4. 启动机器人

```bash
python main.py
```

---

## 🤖 Agent系统详解

### Agent生命周期

```
1. 发现阶段
   AgentLoader 扫描 agents/ 目录
   ↓
2. 实例化阶段
   创建Agent实例，注入依赖（memory_store, llm_provider）
   ↓
3. 注册阶段
   Agent注册到Router和Orchestrator
   ↓
4. 运行阶段
   处理消息: can_handle() → respond()
   ↓
5. 记忆更新
   memory_write() 保存用户状态
```

### 创建自定义Agent

在 `agents/` 目录创建新文件：

```python
# agents/my_agent.py
from typing import Dict, Any
from src.agents import BaseAgent, Message, ChatContext, AgentResponse, SQLiteMemoryStore

class MyAgent(BaseAgent):
    def __init__(self, memory_store=None, llm_provider=None):
        self._name = "MyAgent"
        self._description = "我的自定义Agent"
        self._memory = memory_store or SQLiteMemoryStore()
        self._llm_provider = llm_provider
        self._keywords = ["关键词1", "关键词2"]
  
    @property
    def name(self) -> str:
        return self._name
  
    @property
    def description(self) -> str:
        return self._description
  
    def can_handle(self, message: Message, context: ChatContext) -> float:
        """返回处理置信度 (0.0-1.0)"""
        content = message.content.lower()
        matches = sum(1 for kw in self._keywords if kw in content)
    
        if matches >= 2:
            return 0.9
        elif matches == 1:
            return 0.6
        return 0.0
  
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        """生成响应"""
        response_text = "这是我的回复"
    
        return AgentResponse(
            content=response_text,
            agent_name=self.name,
            confidence=0.85,
            should_continue=False
        )
  
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        return self._memory.read(self.name, user_id)
  
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        self._memory.write(self.name, user_id, data)
```

Agent会被自动发现和加载！

---

## 🎛️ Skills技能系统

Skills系统提供Telegram按钮界面，让用户选择服务，减少Token消耗。

### 注册技能

```python
from src.agents import register_skill, SkillCategory

register_skill(
    id="my_skill",
    name="我的技能",
    description="技能描述",
    category=SkillCategory.TOOLS,
    icon="🔧",
    agent_name="MyAgent",
    keywords=["关键词"],
    priority=5
)
```

### 技能选择流程

```
用户发送消息
    ↓
多个Agent可处理 (超过阈值)
    ↓
生成技能选择按钮
    ↓
用户点击选择
    ↓
执行对应Agent
    ↓
返回结果
```

详细文档：[Claude Skills 集成指南](docs/CLAUDE_SKILLS_GUIDE.md)

---

## 🎤 语音回复系统

SoulmateBot 支持为每个 Bot 配置独立的语音回复功能。当启用时，Bot 的文本回复会自动转换为语音消息发送给用户。

### TTS 服务提供商

系统支持两种 TTS 服务提供商：

- **科大讯飞 (iFlytek)** - 推荐使用，支持丰富的中文音色
- **OpenAI TTS** - 备选方案

### 科大讯飞可用音色（推荐）


| 音色ID      | 名称 | 性别 | 特点     | 适用场景          |
| ----------- | ---- | ---- | -------- | ----------------- |
| `xiaoyan`   | 小燕 | 女   | 温柔亲切 | 通用女声          |
| `xiaoyu`    | 小宇 | 男   | 阳光开朗 | 幽默/活泼男性角色 |
| `vixy`      | 小研 | 女   | 知性大方 | 专业顾问          |
| `vixq`      | 小琪 | 女   | 活泼可爱 | 活泼可爱角色      |
| `vixf`      | 小峰 | 男   | 成熟稳重 | 专业/成熟男性角色 |
| `aisjinger` | 小婧 | 女   | 温婉动人 | 温柔陪伴型角色    |
| `aisjiuxu`  | 许久 | 男   | 温暖磁性 | 深沉有力角色      |
| `vinn`      | 楠楠 | 女   | 可爱甜美 | 童声角色          |
| `aisxping`  | 小萍 | 女   | 甜美清新 | 年轻女性角色      |

### 配置方式

1. 在 `.env` 文件中配置讯飞 TTS 凭证：

```env
# 科大讯飞 TTS 配置
IFLYTEK_APP_ID=your_app_id
IFLYTEK_API_KEY=your_api_key
IFLYTEK_API_SECRET=your_api_secret
DEFAULT_IFLYTEK_VOICE_ID=xiaoyan
TTS_PROVIDER=iflytek
```

2. 在 Bot 的 `config.yaml` 中配置语音：

```yaml
# 语音配置
voice:
  enabled: true          # 启用语音回复
  voice_id: "xiaoyu"     # 科大讯飞音色ID
```

### 音色推荐

根据 Bot 角色特点选择合适的音色：


| Bot类型      | 推荐音色                                 |
| ------------ | ---------------------------------------- |
| 幽默男性角色 | `xiaoyu` (小宇，阳光开朗)                |
| 温柔女性角色 | `aisjinger` (小婧，温婉动人)             |
| 活泼可爱角色 | `vixq` (小琪，活泼可爱)                  |
| 专业顾问     | `vixy` (小研，知性大方) 或 `vixf` (小峰) |

---

## ⚙️ 配置说明

### 必要配置


| 变量                 | 说明               | 示例                    |
| -------------------- | ------------------ | ----------------------- |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | `123456:ABC...`         |
| AI配置（任选一个）   |                    |                         |
| `OPENAI_API_KEY`     | OpenAI API密钥     | `sk-...`                |
| `ANTHROPIC_API_KEY`  | Anthropic API密钥  | `sk-ant-...`            |
| `VLLM_API_URL`       | vLLM服务地址       | `http://localhost:8000` |

### TTS 语音配置


| 变量                       | 说明           | 默认值    |
| -------------------------- | -------------- | --------- |
| `TTS_PROVIDER`             | TTS服务提供商  | `iflytek` |
| `IFLYTEK_APP_ID`           | 讯飞应用ID     | -         |
| `IFLYTEK_API_KEY`          | 讯飞API Key    | -         |
| `IFLYTEK_API_SECRET`       | 讯飞API Secret | -         |
| `DEFAULT_IFLYTEK_VOICE_ID` | 默认讯飞音色   | `xiaoyan` |

### 其他可选配置


| 变量                       | 说明         | 默认值                       |
| -------------------------- | ------------ | ---------------------------- |
| `DATABASE_URL`             | 数据库连接   | `sqlite:///./soulmatebot.db` |
| `FREE_PLAN_DAILY_LIMIT`    | 免费版日限额 | 10                           |
| `BASIC_PLAN_DAILY_LIMIT`   | 基础版日限额 | 100                          |
| `PREMIUM_PLAN_DAILY_LIMIT` | 高级版日限额 | 1000                         |

---

## 📁 项目结构

```
SoulmateBot/
├── main.py                      # 程序入口
├── requirements.txt             # 依赖列表
├── docker-compose.yml           # Docker编排
├── Dockerfile                   # Docker镜像
├── .env.example                 # 环境变量示例
│
├── agents/                      # Agent插件目录（自动发现）
│   ├── emotional_agent.py       # 情感支持Agent
│   ├── tech_agent.py            # 技术支持Agent
│   ├── tool_agent.py            # 工具Agent
│   ├── finance_agent.py         # 金融理财Agent
│   ├── health_agent.py          # 健康顾问Agent
│   ├── legal_agent.py           # 法律咨询Agent
│   └── education_agent.py       # 教育学习Agent
│
├── src/                         # 源代码
│   ├── agents/                  # Agent核心框架
│   │   ├── __init__.py          # 公共API导出
│   │   ├── base_agent.py        # Agent基类
│   │   ├── models.py            # 数据模型
│   │   ├── router.py            # 消息路由
│   │   ├── orchestrator.py      # 智能编排器
│   │   ├── loader.py            # Agent加载器
│   │   ├── memory.py            # 记忆系统
│   │   └── skills.py            # 技能系统
│   │
│   ├── bot/                     # Bot核心
│   │   └── main.py              # Bot主程序
│   │
│   ├── handlers/                # 消息处理器
│   │   ├── commands.py          # 命令处理
│   │   ├── messages.py          # 消息处理
│   │   └── agent_integration.py # Agent集成
│   │
│   ├── llm_gateway/             # LLM统一网关
│   │   ├── gateway.py           # 网关主类
│   │   ├── providers.py         # AI提供者
│   │   ├── rate_limiter.py      # 限流控制
│   │   └── token_counter.py     # Token统计
│   │
│   ├── ai/                      # AI服务
│   │   └── conversation.py      # 对话服务
│   │
│   ├── models/                  # 数据模型
│   │   └── database.py          # ORM模型
│   │
│   ├── services/                # 业务服务
│   │   ├── bot_manager.py       # Bot管理
│   │   ├── channel_manager.py   # 频道管理
│   │   ├── message_router.py    # 消息路由
│   │   └── image_service.py     # 图片服务
│   │
│   ├── subscription/            # 订阅管理
│   │   └── service.py           # 订阅服务
│   │
│   └── database/                # 数据库
│       └── connection.py        # 连接管理
│
├── config/                      # 配置
│   └── settings.py              # 配置管理
│
├── docs/                        # 文档
│   ├── AGENT_SYSTEM_README.md   # Agent系统文档
│   ├── CLAUDE_SKILLS_GUIDE.md   # Skills集成指南
│   ├── ARCHITECTURE.md          # 架构设计
│   └── ...                      # 其他文档
│
├── tests/                       # 测试
│   ├── test_agent_*.py          # Agent测试
│   └── ...                      # 其他测试
│
├── migrations/                  # 数据库迁移
├── scripts/                     # 脚本工具
└── data/                        # 数据目录
```

---

## 🛠️ 开发指南

### 运行测试

```bash
# 运行所有Agent测试
pytest tests/test_agent_*.py -v

# 运行特定测试
pytest tests/test_agent_router.py -v

# 带覆盖率
pytest tests/test_agent_*.py --cov=src.agents --cov-report=html
```

### 运行Demo

```bash
# 交互式CLI Demo
python agent_demo.py
```

### 添加新功能

1. 创建Agent：在 `agents/` 目录创建文件
2. 注册Skill：在 `src/agents/skills.py` 添加技能
3. 添加测试：在 `tests/` 创建测试文件
4. 更新文档：更新相关文档

---

## 🚢 部署指南

### Docker部署

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f bot
```

### 数据库迁移

升级到多机器人架构：

```bash
python migrations/migrate_to_multibot.py
```

---

## ❓ 常见问题

### Q: 如何切换AI提供商？

配置相应的环境变量即可，系统按以下优先级选择：

1. vLLM（如果配置了 `VLLM_API_URL`）
2. OpenAI（如果配置了 `OPENAI_API_KEY`）
3. Anthropic（如果配置了 `ANTHROPIC_API_KEY`）

### Q: 如何添加新的Agent？

在 `agents/` 目录创建继承 `BaseAgent` 的类，系统会自动发现并加载。

### Q: 意图识别是用规则还是LLM？

取决于是否配置了LLM提供者：

- 有LLM：使用LLM推理（更智能）
- 无LLM：使用规则匹配（更快速）
- LLM失败时自动回退到规则

### Q: 如何查看意图识别来源？

查看日志中的 `Source` 字段：

```
🎯 Intent type: IntentType.SINGLE_AGENT | Source: llm_based
```

---

## 📝 更新日志

### v0.5.0 (当前)

- ✅ 语音合成切换到科大讯飞 (iFlytek) TTS
- ✅ 支持多种中文音色（小燕、小宇、小琪、小婧等）
- ✅ 根据Bot角色自动推荐合适的音色
- ✅ 兼容OpenAI音色ID（自动映射到讯飞音色）

### v0.4.0

- ✅ 新增语音回复功能，支持TTS将文本转语音
- ✅ 每个Bot可配置独立的音色
- ✅ 新增语音配置字段（voice_enabled, voice_id）
- ✅ 语音生成失败时自动回退到文本回复

### v0.3.0

- ✅ 新增意图识别来源追踪（规则/LLM/回退）
- ✅ 新增商业价值Agent：金融、健康、法律、教育
- ✅ 完善Skills技能系统
- ✅ 优化Agent响应内容

### v0.2.0

- ✅ 多Agent编排系统
- ✅ LLM Gateway统一网关
- ✅ 支付集成

### v0.1.0

- ✅ 基础Bot框架
- ✅ AI对话集成
- ✅ 订阅系统

---

## 🤝 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 👥 联系方式

- 项目主页: https://github.com/aappaappoo/SoulmateBot
- Issue 反馈: https://github.com/aappaappoo/SoulmateBot/issues

---

<div align="center">

**用 ❤️ 打造的智能对话机器人平台**

</div>
