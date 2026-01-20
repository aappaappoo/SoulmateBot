# SoulmateBot - 智能情感陪伴机器人

<div align="center">

基于 Telegram 的专业智能情感陪伴机器人系统，支持**多Agent架构**，提供情感价值和工具调用能力。

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)](https://telegram.org/)

**商业软件 - 版权所有 © 2026**

</div>

---

## 📖 目录

- [核心特性](#核心特性)
- [Agent系统架构](#agent系统架构)
- [技术架构](#技术架构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [二次开发指南](#二次开发指南)
- [项目结构](#项目结构)

---

## ✨ 核心特性

### 双核心能力

**1. 情感价值提供**
- 💬 **智能情感对话** - 基于先进AI模型的情感陪伴
- 🎭 **情感识别与响应** - 识别用户情绪并提供针对性支持
- 💭 **记忆系统** - 记住用户偏好和历史对话
- 🤗 **共情能力** - 提供温暖、理解和支持

**2. 工具调用能力**
- 🔧 **技术支持** - 编程、技术问题解答
- 🛠️ **工具集成** - 可扩展的工具调用系统
- 📊 **多Agent协作** - 不同Agent处理不同类型任务
- 🔀 **智能路由** - 自动选择最合适的Agent响应

### 系统功能

- 🤖 **多Agent架构** - 情感Agent、技术Agent、工具Agent等
- 📊 **订阅管理** - 完整的订阅系统和使用限额
- 💳 **支付集成** - 支持多种支付方式
- 👤 **用户管理** - 用户数据和会话持久化
- 📈 **使用统计** - 实时追踪和分析

### 订阅计划

| 计划 | 价格 | 日消息限额 | 特性 |
|-----|------|----------|------|
| 🆓 免费版 | ¥0/月 | 10条 | 基础对话 |
| 💎 基础版 | ¥9.99/月 | 100条 | 图片功能、优先响应 |
| 👑 高级版 | ¥19.99/月 | 1000条 | 无限图片、个性化体验 |

---

## 🏗️ Agent系统架构

### 核心设计理念

本系统采用**多Agent协作**架构，每个Agent专注于特定领域，通过智能路由系统协同工作：

```
用户消息 → 路由器 → [情感Agent | 技术Agent | 工具Agent] → 响应合并 → 返回用户
```

### 内置Agent

#### 1. 情感支持Agent (EmotionalAgent)
**专长**：提供情感价值和心理支持
- 识别情绪：悲伤、焦虑、快乐、愤怒等
- 共情响应：理解并回应用户感受
- 记忆系统：记住用户的情感历史
- 支持场景：情感倾诉、心理疏导、日常陪伴

#### 2. 技术支持Agent (TechAgent)  
**专长**：解决技术问题和提供编程帮助
- 编程语言：Python、JavaScript、Java等
- 问题类型：调试、优化、教程、解释
- 代码支持：提供示例和最佳实践
- 支持场景：技术咨询、代码审查、学习指导

#### 3. 工具调用Agent (ToolAgent) 🆕
**专长**：调用外部工具完成实际任务
- 信息查询：天气、新闻、搜索等
- 任务执行：提醒、计算、转换等
- API集成：第三方服务调用
- 支持场景：实用工具、生产力提升

### Agent路由机制

```python
# 智能选择最合适的Agent
1. 解析@提及 → 直接调用指定Agent
2. 关键词匹配 → 计算每个Agent的置信度
3. 上下文分析 → 考虑历史对话内容
4. 置信度排序 → 选择最合适的Agent(s)
5. 并行执行 → 可配置多Agent同时响应
```

### 扩展性设计

系统支持轻松添加新的Agent：

```python
from src.agents import BaseAgent

class CustomAgent(BaseAgent):
    def can_handle(self, message, context) -> float:
        # 返回0.0-1.0的置信度分数
        pass
    
    def respond(self, message, context) -> AgentResponse:
        # 生成响应
        pass
```

---

## 🏗️ 技术架构

### 技术栈

- **后端框架**: Python 3.11+
- **Bot 框架**: python-telegram-bot 20.7
- **AI 集成**: OpenAI GPT-4 / Anthropic Claude / vLLM
- **支付集成**: 微信支付 / Stripe
- **数据库**: PostgreSQL + SQLAlchemy ORM
- **缓存**: Redis
- **任务队列**: Celery (可选)
- **容器化**: Docker + Docker Compose

### 系统架构（多机器人版）

```
┌─────────────┐
│  Telegram   │
│   Users     │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────┐
│      Telegram Bot API           │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────┐
│      SoulmateBot Core (Multi-Bot)               │
│  ┌──────────────────────────────────────────┐   │
│  │  Handlers Layer                          │   │
│  │  - Commands                              │   │
│  │  - Bot Management (NEW)                  │   │
│  │  - Message Router (NEW)                  │   │
│  └──────────┬───────────────────────────────┘   │
│             │                                    │
│  ┌──────────▼───────────────────────────────┐   │
│  │  Services Layer                          │   │
│  │  - Bot Manager (NEW)                     │   │
│  │  - Channel Manager (NEW)                 │   │
│  │  - Message Router (NEW)                  │   │
│  │  - AI Conversation                       │   │
│  │  - Image Service                         │   │
│  │  - Subscription Service                  │   │
│  └──────────┬───────────────────────────────┘   │
│             │                                    │
│  ┌──────────▼───────────────────────────────┐   │
│  │  Database Layer                          │   │
│  │  - Bot Configuration (NEW)               │   │
│  │  - Channel Management (NEW)              │   │
│  │  - Bot-Channel Mapping (NEW)             │   │
│  │  - User Management                       │   │
│  │  - Conversation History                  │   │
│  │  - Usage Tracking                        │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
       │           │
       ▼           ▼
┌───────────┐  ┌─────────┐
│PostgreSQL │  │  Redis  │
└───────────┘  └─────────┘
       │
       ▼
┌─────────────────────────┐
│  Multiple AI Providers  │
│  - OpenAI GPT-4         │
│  - Anthropic Claude     │
│  - vLLM (Self-hosted)   │
└─────────────────────────┘
```

---

## 🚀 快速开始

### 前置要求

- Python 3.11 或更高版本
- PostgreSQL 15+ (可选，默认使用 SQLite)
- Telegram Bot Token
- OpenAI/Anthropic API Key

### 本地开发

1. **克隆仓库**（需要授权）

2. **创建虚拟环境**

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

3. **安装依赖**

```bash
pip install -r requirements.txt
```

4. **配置环境变量**

```bash
cp .env.example .env
# 编辑 .env 文件，填入配置信息
```

5. **初始化数据库**

```bash
python -c "from src.database import init_db; init_db()"
```

6. **运行机器人**

```bash
python main.py
```

---

## ⚙️ 配置说明

### 环境变量

在 `.env` 文件中配置以下变量：

#### Telegram 配置

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook  # 可选
```

#### AI 提供商配置

```env
# OpenAI
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4

# 或使用 Anthropic Claude
ANTHROPIC_API_KEY=your_anthropic_api_key
ANTHROPIC_MODEL=claude-3-sonnet-20240229

# 或使用 vLLM (自托管 LLM 推理服务器)
VLLM_API_URL=http://localhost:8000
VLLM_API_TOKEN=your_vllm_api_token
VLLM_MODEL=your_model_name
```

#### 数据库配置

```env
# PostgreSQL (生产环境推荐)
DATABASE_URL=postgresql://user:password@localhost:5432/soulmatebot

# 或使用 SQLite (开发环境)
DATABASE_URL=sqlite:///./soulmatebot.db
```

#### 订阅限额配置

```env
FREE_PLAN_DAILY_LIMIT=10
BASIC_PLAN_DAILY_LIMIT=100
PREMIUM_PLAN_DAILY_LIMIT=1000
```

#### 支付配置

**微信支付**

```env
WECHAT_PAY_APP_ID=your_wechat_app_id
WECHAT_PAY_MCH_ID=your_merchant_id
WECHAT_PAY_API_KEY=your_api_key
WECHAT_PAY_API_V3_KEY=your_api_v3_key
WECHAT_PAY_CERT_SERIAL_NO=your_cert_serial_no
WECHAT_PAY_PRIVATE_KEY_PATH=/path/to/apiclient_key.pem
WECHAT_PAY_NOTIFY_URL=https://your-domain.com/wechat/notify
```

**Stripe (可选)**

```env
STRIPE_API_KEY=your_stripe_api_key
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret
```

---

## 📦 项目结构

```
SoulmateBot/
├── src/                          # 源代码目录
│   ├── bot/                      # Bot 核心
│   │   ├── __init__.py
│   │   └── main.py              # Bot 主程序
│   ├── handlers/                 # 消息处理器
│   │   ├── __init__.py
│   │   ├── commands.py          # 命令处理
│   │   └── messages.py          # 消息处理
│   ├── models/                   # 数据模型
│   │   ├── __init__.py
│   │   └── database.py          # ORM 模型
│   ├── database/                 # 数据库连接
│   │   ├── __init__.py
│   │   └── connection.py
│   ├── ai/                       # AI 服务
│   │   ├── __init__.py
│   │   └── conversation.py      # 对话服务
│   ├── services/                 # 业务服务
│   │   ├── __init__.py
│   │   └── image_service.py     # 图片服务
│   ├── subscription/             # 订阅管理
│   │   ├── __init__.py
│   │   └── service.py           # 订阅服务
│   └── utils/                    # 工具函数
│       └── __init__.py
├── config/                       # 配置文件
│   ├── __init__.py
│   └── settings.py              # 配置管理
├── tests/                        # 测试文件
├── data/                         # 数据目录
│   └── uploads/                 # 上传文件
├── alembic/                      # 数据库迁移
│   └── versions/
├── logs/                         # 日志文件
├── main.py                       # 入口文件
├── requirements.txt              # 依赖列表
├── .env.example                  # 环境变量示例
├── .gitignore
├── Dockerfile                    # Docker 配置
├── docker-compose.yml            # Docker Compose 配置
└── README.md                     # 项目文档
```

---

## 🎯 二次开发指南

### Agent开发指南

#### 1. 创建自定义Agent

在 `agents/` 目录创建新的Agent文件，例如 `agents/my_agent.py`：

```python
"""
自定义Agent示例 - 根据业务需求定制
"""
from typing import Dict, Any
from src.agents import BaseAgent, Message, ChatContext, AgentResponse, SQLiteMemoryStore


class MyCustomAgent(BaseAgent):
    """
    自定义Agent类
    
    实现特定领域的功能，如：
    - 客服支持
    - 专业咨询
    - 工具集成
    """
    
    def __init__(self, memory_store=None):
        """初始化Agent"""
        self._name = "MyCustomAgent"
        self._description = "提供XXX服务的专业Agent"
        self._memory = memory_store or SQLiteMemoryStore()
        
        # 定义触发关键词
        self._keywords = ["关键词1", "关键词2", "关键词3"]
    
    @property
    def name(self) -> str:
        """Agent名称"""
        return self._name
    
    @property  
    def description(self) -> str:
        """Agent描述"""
        return self._description
    
    def can_handle(self, message: Message, context: ChatContext) -> float:
        """
        判断能否处理消息
        
        返回置信度分数：
        - 0.0: 不能处理
        - 0.5-0.7: 中等置信度
        - 0.8-1.0: 高置信度
        """
        # 检查@提及
        if message.has_mention(self.name):
            return 1.0
        
        content = message.content.lower()
        
        # 关键词匹配
        matches = sum(1 for kw in self._keywords if kw in content)
        
        if matches >= 2:
            return 0.9
        elif matches == 1:
            return 0.6
        
        return 0.0
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        """生成响应"""
        # 读取用户历史
        user_memory = self.memory_read(message.user_id)
        interaction_count = user_memory.get("count", 0)
        
        # 生成响应
        response_text = f"收到消息：{message.content}"
        
        # 更新记忆
        user_memory["count"] = interaction_count + 1
        user_memory["last_message"] = message.content
        self.memory_write(message.user_id, user_memory)
        
        return AgentResponse(
            content=response_text,
            agent_name=self.name,
            confidence=0.85,
            should_continue=False
        )
    
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        """读取用户记忆"""
        return self._memory.read(self.name, user_id)
    
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        """保存用户记忆"""
        self._memory.write(self.name, user_id, data)
```

#### 2. 工具集成Agent示例

创建能调用外部API的工具Agent：

```python
"""
工具调用Agent - 集成外部服务
"""
import requests
from src.agents import BaseAgent, Message, ChatContext, AgentResponse


class ToolAgent(BaseAgent):
    """工具调用Agent - 提供实用功能"""
    
    def __init__(self):
        self._name = "ToolAgent"
        self._description = "调用工具完成实际任务"
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    def can_handle(self, message: Message, context: ChatContext) -> float:
        """判断是否需要工具"""
        content = message.content.lower()
        
        # 工具相关关键词
        tools = ["天气", "搜索", "计算", "翻译"]
        if any(tool in content for tool in tools):
            return 0.9
        
        return 0.0
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        """调用工具并返回结果"""
        content = message.content.lower()
        
        if "天气" in content:
            result = self._get_weather()
        elif "搜索" in content:
            result = self._web_search(message.content)
        elif "计算" in content:
            result = self._calculate(message.content)
        else:
            result = "我可以帮你：查天气、搜索、计算等"
        
        return AgentResponse(
            content=result,
            agent_name=self.name,
            confidence=0.85
        )
    
    def _get_weather(self):
        """查询天气 - 对接天气API"""
        # TODO: 调用真实天气API
        return "今天天气：晴，温度22°C"
    
    def _web_search(self, query):
        """网络搜索 - 对接搜索API"""
        # TODO: 调用搜索API
        return f"搜索结果：{query}"
    
    def _calculate(self, expression):
        """计算 - 使用eval或专业计算库"""
        # TODO: 实现安全的计算功能
        return "计算结果：42"
    
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        return {}
    
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        pass
```

#### 3. 配置Router

在代码中配置Router行为（`src/bot/main.py`）：

```python
from src.agents import Router, RouterConfig, AgentLoader

# 加载所有Agent
loader = AgentLoader(agents_dir="agents")
agents = loader.load_agents()

# 配置Router
config = RouterConfig(
    min_confidence=0.5,      # 最低置信度阈值
    max_agents=1,            # 同时响应的Agent数量
    exclusive_mention=True,  # @提及时独占响应
    enable_parallel=False,   # 是否并行执行
)

router = Router(agents, config)
```

### 数据库扩展

添加自定义数据表：

```python
from sqlalchemy import Column, Integer, String, DateTime, Text
from src.database import Base
from datetime import datetime


class CustomData(Base):
    """自定义数据模型"""
    __tablename__ = "custom_data"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, index=True, nullable=False)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 环境配置扩展

在 `.env` 添加自定义配置：

```env
# 自定义Agent配置
CUSTOM_AGENT_ENABLED=true
CUSTOM_API_KEY=your_api_key
CUSTOM_API_URL=https://api.example.com
```

在代码中读取配置：

```python
import os
from config import settings

# 读取环境变量
api_key = os.getenv("CUSTOM_API_KEY")
api_url = os.getenv("CUSTOM_API_URL")
enabled = os.getenv("CUSTOM_AGENT_ENABLED", "false").lower() == "true"
```

### 添加新命令

在 `src/handlers/commands.py` 添加新命令：

```python
async def custom_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """自定义命令处理器"""
    await update.message.reply_text("这是自定义命令的响应")

# 在 main.py 中注册
app.add_handler(CommandHandler("custom", custom_command))
```

---

## 🎯 开发计划

### v0.1.0 - 基础版本 (当前) ✅

- [x] 项目结构搭建
- [x] Telegram Bot 基础功能
- [x] AI 对话集成
- [x] 订阅系统基础
- [x] 数据库模型
- [x] Docker 部署配置

### v0.2.0 - 支付与 AI 扩展 (当前) ✅

- [x] 微信支付集成
- [x] vLLM 提供商支持
- [x] 支付命令和处理
- [x] 测试覆盖

### v0.3.0 - 图片功能

- [ ] 图片生成 (DALL-E)
- [ ] 情感图片库
- [ ] 图片缓存系统

### v0.4.0 - 支付增强

- [ ] Stripe 支付集成
- [ ] 订阅自动续费
- [ ] 发票生成
- [ ] 微信支付回调处理

### v0.5.0 - 高级功能

- [ ] 情感分析
- [ ] 个性化对话
- [ ] 多语言支持
- [ ] 语音消息支持

### v1.0.0 - 生产就绪

- [ ] 性能优化
- [ ] 监控告警
- [ ] 完整测试覆盖
- [ ] API 文档
- [ ] 用户文档

---

## 📝 使用示例

### 基础对话

```
用户: 你好
Bot: 👋 你好！我是你的情感陪伴助手。今天过得怎么样？

用户: 今天有点累
Bot: 听起来你今天很辛苦呢。工作或者生活上遇到什么压力了吗？
    我在这里，可以和我聊聊。
```

### 命令使用

```
/start  - 开始使用机器人
/help   - 查看帮助信息
/status - 查看订阅状态和使用情况
/subscribe - 查看订阅计划
/pay_basic - 订阅基础版（¥9.99/月）
/pay_premium - 订阅高级版（¥19.99/月）
/check_payment - 查询支付状态
/image  - 获取温馨图片
```

### 订阅流程

**使用微信支付订阅：**

1. 发送 `/pay_basic` 或 `/pay_premium` 命令
2. 收到支付二维码链接
3. 使用微信扫码支付
4. 发送 `/check_payment` 确认支付
5. 立即享受高级功能

---

## 🔧 高级配置

### vLLM 集成

如果您有自己的 LLM 推理服务器（基于 vLLM），可以这样配置：

1. **启动 vLLM 服务器**

```bash
python -m vllm.entrypoints.openai.api_server \
    --model your-model-name \
    --host 0.0.0.0 \
    --port 8000
```

2. **配置环境变量**

```env
VLLM_API_URL=http://your-vllm-server:8000
VLLM_API_TOKEN=your_optional_token  # 可选
VLLM_MODEL=your-model-name
```

3. **优先级**

系统会按以下顺序选择 AI 提供商：
- vLLM（如果配置了 VLLM_API_URL）
- OpenAI（如果配置了 OPENAI_API_KEY）
- Anthropic（如果配置了 ANTHROPIC_API_KEY）

### 微信支付配置

1. **申请微信支付商户号**
   - 访问 [微信支付商户平台](https://pay.weixin.qq.com/)
   - 注册并申请商户号

2. **获取配置信息**
   - APP ID
   - 商户号 (MCH ID)
   - API 密钥 (API Key)
   - API v3 密钥
   - 证书序列号
   - API 私钥文件路径

3. **配置回调 URL**
   
   在微信支付商户平台设置支付回调 URL：
   ```
   https://your-domain.com/wechat/notify
   ```

4. **设置环境变量**（参见上面的支付配置部分）

---

## 🔒 安全性

- 使用环境变量管理敏感信息
- API 密钥加密存储
- 用户数据隐私保护
- 请求速率限制
- SQL 注入防护

---

## 📄 许可证

本项目为专有软件，版权所有 © 2026 SoulmateBot 团队。详见 [LICENSE](LICENSE) 文件。

未经授权，禁止复制、修改或分发本软件。

---

<div align="center">

**SoulmateBot - 专业智能陪伴机器人系统**

版权所有 © 2026

</div>
