# 多机器人平台指南 (Multi-Bot Platform Guide)

## 📋 平台概述

本平台是一个可扩展的 Telegram 多机器人平台（Platform MVP），支持多个 Bot 独立运行但共享统一核心功能。

### 核心特性

- **多 Bot 独立运行**：每个 Bot 通过配置和插件定义差异化能力
- **统一 LLM 调用网关**：封装模型调用、Token 统计、限流和失败重试
- **多轮对话管理**：会话管理、上下文窗口、Prompt 模板
- **数据存储和审计**：消息存储、使用统计、成本追踪
- **支付/额度管理**：Mock 支付网关，可扩展至真实支付

## 🏗️ 平台架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Multi-Bot Platform                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ SoulmateBot  │  │ AssistantBot │  │   其他 Bot   │       │
│  │  (情感陪伴)  │  │  (智能助手)  │  │    ...       │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                 │                 │                │
│  ┌──────▼─────────────────▼─────────────────▼───────┐       │
│  │                Platform Core                       │       │
│  │  ┌─────────────┐ ┌─────────────┐ ┌──────────────┐ │       │
│  │  │ LLM Gateway │ │  Dialogue   │ │   Payment    │ │       │
│  │  │   统一调用  │ │   Engine    │ │   Gateway    │ │       │
│  │  └─────────────┘ └─────────────┘ └──────────────┘ │       │
│  └───────────────────────┬───────────────────────────┘       │
│                          │                                   │
│  ┌───────────────────────▼───────────────────────────┐       │
│  │              Data Storage Layer                    │       │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │       │
│  │  │ Database │  │  Redis   │  │  Audit Logs  │    │       │
│  │  └──────────┘  └──────────┘  └──────────────┘    │       │
│  └───────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## 📁 目录结构

```
SoulmateBot/
├── bots/                          # Bot 模板目录
│   ├── soulmate_bot/             # 情感陪伴 Bot
│   │   ├── config.yaml           # Bot 配置
│   │   └── __init__.py
│   └── assistant_bot/            # 智能助手 Bot
│       ├── config.yaml
│       └── __init__.py
│
├── src/
│   ├── bot/                      # Bot 核心
│   │   ├── main.py              # 主程序
│   │   ├── config_loader.py     # 配置加载器
│   │   └── platform.py          # 多 Bot 平台
│   │
│   ├── llm_gateway/             # LLM 统一网关
│   │   ├── gateway.py           # 网关核心
│   │   ├── providers.py         # Provider 实现
│   │   ├── rate_limiter.py      # 限流器
│   │   └── token_counter.py     # Token 统计
│   │
│   ├── conversation/            # 对话管理
│   │   ├── session_manager.py   # 会话管理
│   │   ├── prompt_template.py   # 提示词模板
│   │   └── context_manager.py   # 上下文管理
│   │
│   ├── payment/                 # 支付模块
│   │   ├── wechat_pay.py       # 微信支付
│   │   └── mock_gateway.py     # Mock 支付网关
│   │
│   └── ...
│
├── tests/                        # 单元测试
│   ├── test_llm_gateway.py
│   ├── test_conversation.py
│   └── test_bot_platform.py
│
└── docker-compose.yml
```

## 🚀 快速开始

### 1. 环境配置

```bash
# 复制环境变量模板
cp .env.example .env

# 配置必要的环境变量
# TELEGRAM_BOT_TOKEN=your_bot_token
# OPENAI_API_KEY=your_openai_key (或其他 LLM 配置)
```

### 2. 运行平台

```bash
# 使用 Docker Compose
docker-compose up -d

# 或直接运行
python python main_bot_launcher.py
```

### 3. 创建新 Bot

1. 在 `bots/` 目录创建新目录
2. 添加 `config.yaml` 配置文件
3. 重启平台

## ⚙️ Bot 配置文件

每个 Bot 的 `config.yaml` 包含以下配置：

```yaml
bot:
  name: "MyBot"
  description: "我的机器人"
  username: "my_bot"
  type: "assistant"  # companion, assistant, service
  language: "zh"

ai:
  provider: "openai"  # openai, anthropic, vllm
  model: "gpt-4o"
  temperature: 0.8
  max_tokens: 1000

prompt:
  template: "general_assistant"  # 使用预定义模板
  # 或自定义:
  # custom: |
  #   你是一个...

routing:
  mode: "auto"  # mention, auto, keyword
  private_chat_auto_reply: true
  group_chat_mention_required: true

limits:
  free_tier:
    messages: 10
  basic_tier:
    messages: 100
  premium_tier:
    messages: 1000
```

## 🔌 LLM Gateway

### 使用示例

```python
from src.llm_gateway import get_llm_gateway, LLMRequest

# 获取网关实例
gateway = get_llm_gateway()

# 创建请求
request = LLMRequest(
    messages=[
        {"role": "system", "content": "你是一个助手"},
        {"role": "user", "content": "你好"}
    ],
    user_id="user123",
    bot_id="my_bot"
)

# 生成响应
response = await gateway.generate(request)

if response.success:
    print(response.content)
    print(f"Token使用: {response.usage.total_tokens}")
    print(f"成本: ${response.usage.cost}")
```

### 支持的 Provider

| Provider | 模型 | 配置 |
|----------|------|------|
| OpenAI | GPT-4, GPT-3.5 | `OPENAI_API_KEY` |
| Anthropic | Claude-3 | `ANTHROPIC_API_KEY` |
| vLLM | 自托管模型 | `VLLM_API_URL` |

### 限流和重试

- **限流**：基于令牌桶算法，支持全局/用户级限流
- **重试**：自动重试失败请求，可配置重试次数

## 💬 会话管理

### SessionManager 使用

```python
from src.conversation import get_session_manager

manager = get_session_manager()

# 获取或创建会话
session = manager.get_or_create_session(
    user_id="user123",
    bot_id="my_bot",
    system_prompt="你是一个助手"
)

# 添加消息
session.add_user_message("你好")
session.add_assistant_message("你好！有什么可以帮你的？")

# 获取 LLM 格式的消息
messages = session.get_messages_for_llm()
```

### 提示词模板

```python
from src.conversation import get_template_manager

manager = get_template_manager()

# 使用预定义模板
prompt = manager.create_system_prompt(
    template_name="emotional_companion",
    bot_name="暖心助手",
    user_name="用户"
)

# 注册自定义模板
from src.conversation import PromptTemplate

manager.register_template(PromptTemplate(
    name="my_template",
    content="你是{{bot_name}}，专门帮助用户{{task}}。"
))
```

## 💰 支付/额度管理

### Mock 支付网关

```python
from src.payment.mock_gateway import get_mock_payment_gateway, SubscriptionTier

gateway = get_mock_payment_gateway()

# 检查额度
has_quota = gateway.check_quota("user123", "message")

# 消费额度
gateway.consume_quota("user123", "message", 1)

# 创建支付订单
payment = gateway.create_payment(
    user_id="user123",
    tier=SubscriptionTier.PREMIUM,
    duration_days=30
)

# 完成支付（Mock 直接成功）
gateway.complete_payment(payment.payment_id)

# 获取用户额度信息
quota = gateway.get_user_quota("user123")
print(f"剩余消息: {quota.messages_limit - quota.messages_used}")
```

## 📊 统计和监控

### Gateway 统计

```python
gateway = get_llm_gateway()
stats = gateway.get_stats()

print(f"总请求数: {stats['total_requests']}")
print(f"成功率: {stats['success_rate']:.2%}")
print(f"Token统计: {stats['token_stats']}")
```

### Token 使用统计

```python
from src.llm_gateway import TokenCounter

counter = TokenCounter()

# 记录使用
stats = counter.record_usage(
    prompt_tokens=100,
    completion_tokens=50,
    model="gpt-4",
    provider="openai",
    user_id="user123"
)

# 获取统计
total = counter.get_total_stats()
user_stats = counter.get_user_stats("user123")
model_stats = counter.get_model_stats("gpt-4")
```

## 🧪 测试

```bash
# 运行所有新增测试
python -m pytest tests/test_llm_gateway.py tests/test_conversation.py tests/test_bot_platform.py -v

# 运行全部测试
python -m pytest tests/ -v

# 生成覆盖率报告
python -m pytest tests/ --cov=src --cov-report=html
```

## 🔒 安全考虑

1. **API 密钥**：通过环境变量配置，不要硬编码
2. **限流保护**：防止 API 调用过载
3. **用户数据**：敏感数据加密存储
4. **审计日志**：记录所有 API 调用

## 📈 扩展计划

### 第二阶段
- [ ] Web UI 管理界面
- [ ] 真实支付网关集成
- [ ] Telegram Mini App

### 第三阶段
- [ ] 多语言支持
- [ ] 高级分析仪表板
- [ ] A/B 测试框架

## 🤝 贡献

欢迎贡献代码！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 📄 许可证

MIT License
