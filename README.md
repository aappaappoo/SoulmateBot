# SoulmateBot - 情感陪伴机器人

<div align="center">

一个基于 Telegram 的智能情感陪伴机器人，提供温暖的对话、图片分享和订阅管理功能。

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)](https://telegram.org/)

</div>

---

## 📖 目录

- [功能特性](#功能特性)
- [技术架构](#技术架构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [部署指南](#部署指南)
- [API文档](#api文档)
- [项目结构](#项目结构)
- [开发计划](#开发计划)

---

## ✨ 功能特性

### 核心功能

- 💬 **智能对话** - 基于 GPT/Claude/vLLM 的情感陪伴对话
- 🖼️ **图片分享** - 温馨图片生成与发送
- 📊 **订阅管理** - 完整的订阅系统和使用限额
- 💳 **支付集成** - 支持微信支付和 Stripe
- 👤 **用户管理** - 用户信息存储和会话管理
- 📈 **使用统计** - 实时使用情况追踪

### 订阅计划

| 计划 | 价格 | 日消息限额 | 特性 |
|-----|------|----------|------|
| 🆓 免费版 | ¥0/月 | 10条 | 基础对话 |
| 💎 基础版 | ¥9.99/月 | 100条 | 图片功能、优先响应 |
| 👑 高级版 | ¥19.99/月 | 1000条 | 无限图片、个性化体验 |

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

### 系统架构

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
┌─────────────────────────────────┐
│      SoulmateBot Core           │
│  ┌──────────────────────────┐   │
│  │  Handlers Layer          │   │
│  │  - Commands              │   │
│  │  - Messages              │   │
│  └──────────┬───────────────┘   │
│             │                   │
│  ┌──────────▼───────────────┐   │
│  │  Services Layer          │   │
│  │  - AI Conversation       │   │
│  │  - Image Service         │   │
│  │  - Subscription Service  │   │
│  └──────────┬───────────────┘   │
│             │                   │
│  ┌──────────▼───────────────┐   │
│  │  Database Layer          │   │
│  │  - User Management       │   │
│  │  - Conversation History  │   │
│  │  - Usage Tracking        │   │
│  └──────────────────────────┘   │
└─────────────────────────────────┘
       │           │
       ▼           ▼
┌───────────┐  ┌─────────┐
│PostgreSQL │  │  Redis  │
└───────────┘  └─────────┘
       │
       ▼
┌─────────────┐
│  OpenAI/    │
│  Anthropic  │
│     API     │
└─────────────┘
```

---

## 🚀 快速开始

## Database Migration

⚠️ **Important:** If you're upgrading from an earlier version, you may need to migrate your database.

If you see this error:
```
invalid input value for enum subscriptiontier: "free"
```

Please follow the [Migration Guide](MIGRATION_GUIDE.md) to update your database schema.

Quick fix:
```bash
psql -U your_username -d your_database -f migrations/fix_subscription_tier_enum.sql
```

### 前置要求

- Python 3.11 或更高版本
- PostgreSQL 15+ (可选，默认使用 SQLite)
- Redis (可选)
- Telegram Bot Token
- OpenAI API Key 或 Anthropic API Key

### 本地开发

1. **克隆仓库**

```bash
git clone https://github.com/aappaappoo/SoulmateBot.git
cd SoulmateBot
```

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
# 编辑 .env 文件，填入你的配置
```

5. **初始化数据库**

```bash
python -c "from src.database import init_db; init_db()"
```

6. **运行机器人**

```bash
python main.py
```

### Docker 部署

1. **配置环境变量**

```bash
cp .env.example .env
# 编辑 .env 文件
```

2. **启动服务**

```bash
docker-compose up -d
```

3. **查看日志**

```bash
docker-compose logs -f bot
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

## 🤝 贡献指南

欢迎贡献！请遵循以下步骤：

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

## 🙏 致谢

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [OpenAI](https://openai.com/)
- [Anthropic](https://www.anthropic.com/)

---

<div align="center">

**用 ❤️ 打造的情感陪伴机器人**

</div>
