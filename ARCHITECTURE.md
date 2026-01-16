# 项目架构总结 (Project Architecture Summary)

## 📋 项目概览

SoulmateBot 是一个完整的 Telegram 情感陪伴机器人系统，采用模块化架构设计，支持 AI 对话、图片分享和订阅管理。

## 🏗️ 架构设计

### 1. 核心模块

#### Bot 层 (`src/bot/`)
- **main.py**: 机器人主程序，负责初始化和启动
- 处理 Telegram 连接和事件循环
- 集成所有处理器和服务

#### 处理器层 (`src/handlers/`)
- **commands.py**: 命令处理器
  - `/start` - 欢迎新用户
  - `/help` - 显示帮助信息
  - `/status` - 查看订阅状态
  - `/subscribe` - 订阅计划
  - `/image` - 获取图片

- **messages.py**: 消息处理器
  - 处理文本消息
  - 处理图片消息
  - 处理表情包
  - 错误处理

#### 数据层 (`src/models/`, `src/database/`)
- **database.py**: SQLAlchemy ORM 模型
  - User: 用户信息和订阅
  - Conversation: 对话历史
  - UsageRecord: 使用记录
  - Payment: 支付记录

- **connection.py**: 数据库连接管理
  - 连接池配置
  - 会话管理
  - 初始化脚本

#### AI 服务层 (`src/ai/`)
- **conversation.py**: AI 对话服务
  - OpenAI GPT-4 集成
  - Anthropic Claude 集成
  - 对话历史管理
  - 上下文维护

#### 业务服务层 (`src/services/`, `src/subscription/`)
- **image_service.py**: 图片服务
  - AI 图片生成
  - 情感图片库
  - 图片下载和存储

- **subscription/service.py**: 订阅管理
  - 用户管理
  - 使用限额检查
  - 使用记录追踪
  - 订阅升级/降级

#### 配置层 (`config/`)
- **settings.py**: 配置管理
  - 环境变量加载
  - 配置验证
  - 默认值设置

## 📊 数据模型

### User (用户)
```python
- telegram_id: int (唯一)
- username: str
- first_name: str
- last_name: str
- language_code: str
- subscription_tier: Enum (FREE, BASIC, PREMIUM)
- subscription_start_date: datetime
- subscription_end_date: datetime
- is_active: bool
```

### Conversation (对话)
```python
- user_id: int (外键)
- message: str
- response: str
- is_user_message: bool
- message_type: str
- timestamp: datetime
```

### UsageRecord (使用记录)
```python
- user_id: int (外键)
- action_type: str (message/image)
- count: int
- date: datetime
```

## 🔄 数据流

### 用户发送消息流程:
```
1. 用户在 Telegram 发送消息
   ↓
2. Telegram Bot API 接收
   ↓
3. MessageHandler 处理
   ↓
4. SubscriptionService 检查限额
   ↓
5. ConversationService 获取 AI 响应
   ↓
6. 保存对话到数据库
   ↓
7. 记录使用情况
   ↓
8. 返回响应给用户
```

## 🎯 订阅系统

### 订阅层级
| 层级 | 日消息限额 | 特性 |
|-----|----------|------|
| FREE | 10 | 基础对话 |
| BASIC | 100 | +图片功能 |
| PREMIUM | 1000 | +无限图片+优先响应 |

### 限额管理
- 每日重置
- 实时检查
- 自动记录
- 统计查询

## 🔧 技术栈

### 后端
- **Python 3.11+**: 主要编程语言
- **python-telegram-bot 20.7**: Telegram Bot 框架
- **SQLAlchemy 2.0**: ORM
- **PostgreSQL/SQLite**: 数据库
- **Redis**: 缓存 (可选)

### AI 集成
- **OpenAI GPT-4**: 对话生成
- **Anthropic Claude**: 备选对话引擎
- **DALL-E 3**: 图片生成 (可选)

### 部署
- **Docker**: 容器化
- **Docker Compose**: 多容器编排
- **Nginx**: 反向代理 (webhook 模式)

## 📁 目录结构

```
SoulmateBot/
├── src/                    # 源代码
│   ├── bot/               # Bot 核心
│   ├── handlers/          # 消息处理
│   ├── models/            # 数据模型
│   ├── database/          # 数据库
│   ├── ai/                # AI 服务
│   ├── services/          # 业务服务
│   ├── subscription/      # 订阅管理
│   └── utils/             # 工具函数
├── config/                # 配置
├── tests/                 # 测试
├── data/                  # 数据目录
│   └── uploads/          # 上传文件
├── logs/                  # 日志 (运行时生成)
├── alembic/              # 数据库迁移
├── .github/              # GitHub Actions
│   └── workflows/        # CI/CD
├── main.py               # 入口文件
├── demo.py               # Demo 脚本
├── requirements.txt      # 依赖
├── Dockerfile           # Docker 配置
├── docker-compose.yml   # Docker Compose
├── .env.example         # 环境变量示例
├── README.md            # 项目文档
├── API.md               # API 文档
├── DEPLOYMENT.md        # 部署指南
├── QUICKSTART.md        # 快速开始
├── CONTRIBUTING.md      # 贡献指南
└── LICENSE              # MIT 许可证
```

## 🚀 部署选项

### 1. 本地开发
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### 2. Docker
```bash
docker-compose up -d
```

### 3. 云服务器
- AWS EC2
- Google Cloud
- DigitalOcean
- 任何支持 Docker 的平台

## 🔒 安全特性

- 环境变量管理敏感信息
- API 密钥隔离
- SQL 注入防护 (SQLAlchemy ORM)
- 请求速率限制
- 用户数据加密存储

## 📈 扩展性

### 水平扩展
- 多实例部署
- 负载均衡
- Redis 会话共享

### 垂直扩展
- 数据库优化
- 缓存策略
- 异步处理

### 功能扩展
- 支付网关集成 (Stripe)
- 多语言支持
- 语音消息
- 视频消息
- 群组支持
- 管理后台

## 🧪 测试

### 单元测试
```bash
pytest tests/
```

### 覆盖率
```bash
pytest --cov=src tests/
```

### CI/CD
- GitHub Actions 自动化
- 代码风格检查 (Black, Flake8)
- 类型检查 (MyPy)
- 自动测试

## 📝 配置说明

### 必需配置
- `TELEGRAM_BOT_TOKEN`: Telegram Bot Token
- `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`: AI API Key
- `DATABASE_URL`: 数据库连接

### 可选配置
- `REDIS_URL`: Redis 缓存
- `STRIPE_API_KEY`: 支付集成
- 订阅限额自定义
- 速率限制配置

## 🔄 未来规划

### v0.2.0
- [ ] 完整图片生成功能
- [ ] 情感图片库
- [ ] 图片缓存系统

### v0.3.0
- [ ] Stripe 支付集成
- [ ] 订阅自动续费
- [ ] 发票生成

### v0.4.0
- [ ] 情感分析增强
- [ ] 多语言支持
- [ ] 语音消息

### v1.0.0
- [ ] 性能优化
- [ ] 监控告警
- [ ] 完整测试覆盖
- [ ] 生产就绪

## 💡 设计原则

1. **模块化**: 清晰的模块边界，便于维护和扩展
2. **可配置**: 通过环境变量灵活配置
3. **可测试**: 依赖注入，便于单元测试
4. **可扩展**: 支持水平和垂直扩展
5. **安全性**: 多层安全防护
6. **文档化**: 完整的代码和 API 文档

## 🤝 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md)

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

---

**用 ❤️ 打造的情感陪伴机器人**
