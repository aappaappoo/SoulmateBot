# 工程结构说明文档

## 📁 项目概览

SoulmateBot 是一个采用**多机器人架构**的 Telegram 情感陪伴机器人系统。本文档详细说明项目的完整工程结构。

## 🏗️ 目录结构

```
SoulmateBot/
├── 📄 README.md                      # 项目说明文档（中文）
├── 📄 ARCHITECTURE.md                # 架构设计文档（中文）
├── 📄 MULTI_BOT_GUIDE.md            # 多机器人使用指南（中文）
├── 📄 API.md                         # API 接口文档
├── 📄 DEPLOYMENT.md                  # 部署指南
├── 📄 QUICKSTART.md                  # 快速开始指南
├── 📄 CONTRIBUTING.md                # 贡献指南
├── 📄 CHANGELOG.md                   # 变更日志
├── 📄 MIGRATION_GUIDE.md            # 数据库迁移指南
├── 📄 PROJECT_SUMMARY.md            # 项目总结
├── 📄 LICENSE                        # MIT 许可证
│
├── 📄 main.py                        # 应用程序入口文件
├── 📄 demo.py                        # 演示脚本
├── 📄 requirements.txt               # Python 依赖包列表
├── 📄 .env.example                   # 环境变量示例文件
├── 📄 .gitignore                     # Git 忽略文件配置
│
├── 🐳 Dockerfile                     # Docker 镜像构建文件
├── 🐳 docker-compose.yml            # Docker Compose 配置
│
├── 📁 config/                        # 配置模块
│   ├── __init__.py
│   └── settings.py                   # 应用程序配置管理
│
├── 📁 src/                           # 源代码目录
│   ├── __init__.py
│   │
│   ├── 📁 bot/                       # 机器人核心模块
│   │   ├── __init__.py
│   │   └── main.py                   # 机器人主程序，初始化和启动
│   │
│   ├── 📁 handlers/                  # 消息和命令处理器
│   │   ├── __init__.py
│   │   ├── commands.py               # 基础命令处理器
│   │   │                             #   - /start, /help, /status, /subscribe
│   │   │                             #   - /image, /pay_basic, /pay_premium
│   │   ├── bot_commands.py           # 机器人管理命令（新增）
│   │   │                             #   - /list_bots, /add_bot, /remove_bot
│   │   │                             #   - /my_bots, /config_bot
│   │   ├── feedback.py               # 反馈处理器（新增）
│   │   │                             #   - 消息反应处理（👍、❤️、👎等）
│   │   │                             #   - 交互行为记录（复制、回复、置顶等）
│   │   │                             #   - /feedback_stats, /my_feedback
│   │   └── messages.py               # 消息处理器
│   │                                 #   - 文本/图片/表情包处理
│   │                                 #   - 多机器人消息路由
│   │
│   ├── 📁 models/                    # 数据模型
│   │   ├── __init__.py
│   │   └── database.py               # SQLAlchemy ORM 模型
│   │                                 #   - User（用户）
│   │                                 #   - Bot（机器人）- 新增
│   │                                 #   - Channel（频道）- 新增
│   │                                 #   - ChannelBotMapping（映射）- 新增
│   │                                 #   - Conversation（对话）
│   │                                 #   - UsageRecord（使用记录）
│   │                                 #   - Payment（支付）
│   │                                 #   - MessageReaction（消息反应）- 新增
│   │                                 #   - MessageInteraction（消息交互）- 新增
│   │                                 #   - FeedbackSummary（反馈汇总）- 新增
│   │
│   ├── 📁 database/                  # 数据库连接
│   │   ├── __init__.py
│   │   └── connection.py             # 数据库连接管理
│   │
│   ├── 📁 services/                  # 业务服务层
│   │   ├── __init__.py
│   │   ├── bot_manager.py            # 机器人管理服务（新增）
│   │   │                             #   - 创建/更新/删除机器人
│   │   │                             #   - 机器人配置管理
│   │   ├── channel_manager.py        # 频道管理服务（新增）
│   │   │                             #   - 频道注册和管理
│   │   │                             #   - 机器人添加/移除
│   │   ├── message_router.py         # 消息路由器（新增）
│   │   │                             #   - 消息路由逻辑
│   │   │                             #   - 机器人选择算法
│   │   ├── feedback_service.py       # 反馈服务（新增）
│   │   │                             #   - 反应管理（添加/移除/查询）
│   │   │                             #   - 交互记录（复制/回复/置顶等）
│   │   │                             #   - 反馈统计和汇总
│   │   │                             #   - 满意度分析
│   │   └── image_service.py          # 图片服务
│   │
│   ├── 📁 subscription/              # 订阅管理
│   │   ├── __init__.py
│   │   └── service.py                # 订阅服务
│   │                                 #   - 用户管理
│   │                                 #   - 限额检查
│   │                                 #   - 使用记录
│   │
│   ├── 📁 ai/                        # AI 服务
│   │   ├── __init__.py
│   │   └── conversation.py           # AI 对话服务
│   │                                 #   - OpenAI 集成
│   │                                 #   - Anthropic 集成
│   │                                 #   - vLLM 集成
│   │
│   ├── 📁 payment/                   # 支付集成
│   │   ├── __init__.py
│   │   └── wechat_pay.py            # 微信支付服务
│   │
│   └── 📁 utils/                     # 工具函数
│       └── __init__.py
│
├── 📁 migrations/                    # 数据库迁移脚本
│   ├── README.md
│   ├── migrate_to_multibot.py        # 多机器人架构迁移（新增）
│   ├── add_feedback_tables.py        # 反馈表迁移脚本（新增）
│   │                                 #   - message_reactions（消息反应表）
│   │                                 #   - message_interactions（消息交互表）
│   │                                 #   - feedback_summaries（反馈汇总表）
│   └── fix_subscription_tier_enum.sql # 订阅层级修复
│
├── 📁 tests/                         # 测试文件
│   ├── __init__.py
│   ├── conftest.py                   # pytest 配置
│   ├── test_subscription.py          # 订阅测试
│   ├── test_vllm.py                 # vLLM 测试
│   ├── test_wechat_pay.py           # 微信支付测试
│   └── test_feedback.py              # 反馈功能测试（新增）
│
├── 📁 data/                          # 数据目录
│   └── uploads/                      # 用户上传文件
│
├── 📁 logs/                          # 日志目录（运行时生成）
│   └── bot_*.log
│
└── 📁 .github/                       # GitHub 配置
    └── workflows/                    # GitHub Actions
        └── ci.yml                    # CI/CD 配置
```

## 📦 核心模块说明

### 1. 配置模块 (`config/`)

#### `settings.py`
负责加载和管理应用程序配置，使用 `pydantic-settings` 进行类型验证。

**主要配置项**：
- Telegram Bot Token
- AI 提供商配置（OpenAI/Anthropic/vLLM）
- 数据库连接
- 支付集成
- 订阅限额
- 安全设置

### 2. 机器人核心 (`src/bot/`)

#### `main.py`
机器人的主要入口点，负责：
- 初始化 Telegram Application
- 注册所有命令和消息处理器
- 启动轮询或 Webhook
- 管理应用程序生命周期

### 3. 处理器层 (`src/handlers/`)

#### `commands.py` - 基础命令处理器
处理用户的基本命令：
- `/start` - 欢迎新用户，创建用户记录
- `/help` - 显示帮助信息
- `/status` - 查看订阅状态和使用情况
- `/subscribe` - 查看订阅计划
- `/image` - 获取图片
- `/pay_basic` - 订阅基础版
- `/pay_premium` - 订阅高级版
- `/check_payment` - 查询支付状态

#### `bot_commands.py` - 机器人管理命令（新增）
处理多机器人架构相关命令：
- `/list_bots` - 列出所有可用的公开机器人
- `/add_bot <bot_id> [mode]` - 添加机器人到当前频道
- `/remove_bot <bot_id>` - 从频道移除机器人
- `/my_bots` - 查看当前频道的所有机器人
- `/config_bot <bot_id> [key] [value]` - 配置机器人参数

#### `messages.py` - 消息处理器
处理所有非命令消息：
- 文本消息处理
- 图片消息处理
- 表情包处理
- **多机器人消息路由（新增）**
- 错误处理

**路由逻辑**：
1. 识别消息来源（私聊/群组/频道）
2. 获取频道中的活跃机器人
3. 根据路由模式选择响应机器人
4. 使用选定机器人的配置生成回复

### 4. 数据模型 (`src/models/`)

#### `database.py` - ORM 模型

**User（用户模型）**
```python
- telegram_id: 唯一的 Telegram 用户 ID
- username: 用户名
- first_name, last_name: 姓名
- subscription_tier: 订阅等级（FREE/BASIC/PREMIUM）
- subscription_start_date: 订阅开始日期
- subscription_end_date: 订阅结束日期
- is_active: 是否激活
```

**Bot（机器人模型）- 新增**
```python
- bot_token: Telegram Bot Token
- bot_name: 机器人名称
- bot_username: 机器人用户名（@xxx）
- description: 描述
- personality: 个性描述
- system_prompt: AI 系统提示词
- ai_model: 使用的 AI 模型
- ai_provider: AI 提供商
- is_public: 是否公开
- created_by: 创建者用户 ID
- status: 状态（active/inactive/maintenance）
- settings: JSON 配置
```

**Channel（频道模型）- 新增**
```python
- telegram_chat_id: Telegram 聊天 ID
- chat_type: 类型（private/group/supergroup/channel）
- title: 标题
- username: 用户名
- owner_id: 所有者 ID
- subscription_tier: 频道级订阅
- settings: JSON 配置
```

**ChannelBotMapping（映射模型）- 新增**
```python
- channel_id: 频道 ID
- bot_id: 机器人 ID
- is_active: 是否激活
- priority: 优先级（数字越大越高）
- routing_mode: 路由模式（mention/auto/keyword）
- keywords: 关键词列表（用于 keyword 模式）
- settings: JSON 配置
```

**Conversation（对话模型）**
```python
- user_id: 用户 ID
- message: 用户消息
- response: 机器人回复
- is_user_message: 是否为用户消息
- message_type: 消息类型
- timestamp: 时间戳
```

**UsageRecord（使用记录模型）**
```python
- user_id: 用户 ID
- action_type: 动作类型（message/image）
- count: 计数
- date: 日期
```

**Payment（支付模型）**
```python
- user_id: 用户 ID
- amount: 金额
- currency: 货币
- provider: 支付提供商
- provider_order_id: 订单 ID
- subscription_tier: 订阅等级
- status: 状态
```

**MessageReaction（消息反应模型）- 新增**
```python
- user_id: 用户 ID
- message_id: Telegram消息ID
- chat_id: Telegram聊天ID
- reaction_emoji: 反应表情（👍、❤️、👎等）
- reaction_type: 反应类型（positive/negative/neutral）
- is_active: 反应是否有效
- created_at: 反应时间
- removed_at: 取消反应时间
```

**MessageInteraction（消息交互模型）- 新增**
```python
- user_id: 用户 ID
- message_id: Telegram消息ID
- chat_id: Telegram聊天ID
- interaction_type: 交互类型（copy/reply/pin/report/forward等）
- extra_data: 额外元数据（JSON）
- source_platform: 来源平台
- created_at: 交互时间
```

**FeedbackSummary（反馈汇总模型）- 新增**
```python
- bot_id: 机器人 ID
- channel_id: 频道 ID
- period_type: 统计周期（hourly/daily/weekly/monthly）
- period_start: 周期开始时间
- total_reactions: 总反应数
- positive_reactions: 正面反应数
- negative_reactions: 负面反应数
- satisfaction_score: 满意度分数
- engagement_score: 参与度分数
```

### 5. 业务服务层 (`src/services/`)

#### `bot_manager.py` - 机器人管理服务（新增）
提供机器人管理的核心功能：
- `create_bot()` - 创建新机器人
- `get_bot_by_id()` - 根据 ID 获取机器人
- `get_bot_by_username()` - 根据用户名获取机器人
- `list_public_bots()` - 列出公开机器人
- `list_bots_by_creator()` - 列出某用户创建的机器人
- `update_bot()` - 更新机器人配置
- `activate_bot()` / `deactivate_bot()` - 激活/停用
- `delete_bot()` - 删除机器人

#### `channel_manager.py` - 频道管理服务（新增）
管理频道和机器人的关系：
- `get_or_create_channel()` - 获取或创建频道
- `add_bot_to_channel()` - 添加机器人到频道
- `remove_bot_from_channel()` - 从频道移除机器人
- `get_channel_bots()` - 获取频道中的机器人
- `update_mapping_settings()` - 更新映射配置
- `check_bot_in_channel()` - 检查机器人是否在频道中

#### `message_router.py` - 消息路由器（新增）
智能路由消息到合适的机器人：
- `select_bot()` - 根据规则选择机器人
- `extract_mention()` - 提取 @mention
- `should_respond_in_channel()` - 判断是否响应
- `_check_keywords()` - 关键词匹配

**路由模式**：
1. **Mention 模式**：需要 @机器人 才响应
2. **Auto 模式**：自动响应，按优先级选择
3. **Keyword 模式**：根据关键词匹配

#### `image_service.py` - 图片服务
处理图片相关功能（待完善）。

#### `feedback_service.py` - 反馈服务（新增）
管理用户对消息的反馈和交互：
- `add_reaction()` - 添加或更新消息反应
- `remove_reaction()` - 移除消息反应
- `get_message_reactions()` - 获取消息的所有反应
- `get_reaction_summary()` - 获取消息反应统计摘要
- `record_interaction()` - 记录用户交互行为
- `record_copy()` / `record_reply()` / `record_pin()` - 特定交互快捷方法
- `get_user_interactions()` - 获取用户交互历史
- `get_bot_feedback_stats()` - 获取机器人反馈统计
- `generate_feedback_summary()` - 生成反馈汇总报告
- `get_trending_reactions()` - 获取热门反应趋势

**反应分类**：
- 正面反应：👍、❤️、🔥、👏、🎉、🤩、👌、💯、😂
- 负面反应：👎、💩、🤮、😡
- 中性反应：👀、🤔、😱、😢、😔

### 6. 订阅管理 (`src/subscription/`)

#### `service.py` - 订阅服务
管理用户订阅和使用限额：
- 用户注册和信息更新
- 订阅状态检查
- 使用限额验证
- 使用记录追踪
- 订阅升级/降级

### 7. AI 服务 (`src/ai/`)

#### `conversation.py` - AI 对话服务
集成多个 AI 提供商：
- **OpenAI**: GPT-4, GPT-3.5
- **Anthropic**: Claude-3
- **vLLM**: 自托管大语言模型

自动选择可用的 AI 提供商，优先级：vLLM > OpenAI > Anthropic

### 8. 支付集成 (`src/payment/`)

#### `wechat_pay.py` - 微信支付服务
集成微信支付 Native 支付：
- 创建支付订单
- 生成支付二维码
- 查询订单状态
- 处理支付回调

### 9. 数据库迁移 (`migrations/`)

#### `migrate_to_multibot.py` - 多机器人架构迁移（新增）
将旧版数据库升级到多机器人架构：
1. 创建新表（Bot, Channel, ChannelBotMapping）
2. 创建默认机器人
3. 为现有用户创建私聊频道
4. 关联默认机器人
5. 验证迁移结果

**运行方法**：
```bash
python migrations/migrate_to_multibot.py
```

### 10. 测试 (`tests/`)

目前包含的测试：
- `test_subscription.py` - 订阅功能测试
- `test_vllm.py` - vLLM 集成测试
- `test_wechat_pay.py` - 微信支付测试

## 🔄 数据流程

### 消息处理流程（多机器人）

```
1. 用户发送消息到 Telegram
   ↓
2. Telegram Bot API 推送 Update
   ↓
3. MessageHandler 接收并解析
   ↓
4. ChannelManager 获取/创建频道记录
   ↓
5. ChannelManager 获取频道中的活跃机器人
   ↓
6. MessageRouter 根据路由模式选择机器人
   │
   ├─ Mention 模式: 检查 @mention
   ├─ Auto 模式: 按优先级选择
   └─ Keyword 模式: 匹配关键词
   ↓
7. 如果选中机器人，继续处理
   ↓
8. SubscriptionService 检查用户订阅和限额
   ↓
9. AI Conversation Service 生成回复
   ├─ 使用机器人的 system_prompt
   ├─ 使用机器人的 ai_model
   └─ 调用对应的 AI 提供商
   ↓
10. 保存对话记录到数据库
    ↓
11. 记录使用情况
    ↓
12. 发送回复给用户
```

### 机器人添加流程

```
1. 用户在群组/频道发送 /add_bot <bot_id>
   ↓
2. CommandHandler 解析命令
   ↓
3. BotManager 验证机器人是否存在和公开
   ↓
4. ChannelManager 获取/创建频道记录
   ↓
5. ChannelManager 创建映射关系
   ├─ 设置路由模式
   ├─ 设置优先级
   └─ 保存到数据库
   ↓
6. 返回成功消息给用户
```

## 🔐 安全性

### 数据保护
- 使用环境变量管理敏感信息
- API 密钥不存储在代码中
- 数据库连接加密

### 权限管理
- 机器人创建者有完全控制权
- 频道管理员可以添加/移除公开机器人
- 普通用户只能使用机器人

### 输入验证
- 所有用户输入都经过验证
- SQL 注入防护（使用 ORM）
- 命令参数类型检查

## 📚 依赖管理

主要依赖（见 `requirements.txt`）：
- `python-telegram-bot` - Telegram Bot API
- `sqlalchemy` - ORM
- `pydantic-settings` - 配置管理
- `openai` - OpenAI API
- `anthropic` - Anthropic API
- `loguru` - 日志
- `pytest` - 测试框架

## 🚀 部署

### 开发环境
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 配置
python python main_bot_launcher.py
```

### 生产环境（Docker）
```bash
docker-compose up -d
```

## 📝 开发指南

### 添加新命令
1. 在 `src/handlers/commands.py` 或 `bot_commands.py` 添加处理函数
2. 在 `src/bot/main.py` 的 `setup_handlers()` 中注册
3. 更新文档

### 添加新服务
1. 在 `src/services/` 创建新的服务文件
2. 在 `src/services/__init__.py` 导出
3. 在需要的地方导入使用

### 添加新数据模型
1. 在 `src/models/database.py` 定义模型
2. 创建数据库迁移脚本
3. 更新相关服务

## 🎯 未来扩展

### 计划功能
- [ ] 完整的图片生成功能
- [ ] 语音消息支持
- [ ] 多语言支持
- [ ] Web 管理后台
- [ ] 更多 AI 模型集成
- [ ] 群组机器人权限管理
- [ ] 统计和分析仪表板

### 技术优化
- [ ] 缓存系统（Redis）
- [ ] 消息队列（Celery）
- [ ] 负载均衡
- [ ] 监控和告警
- [ ] 日志聚合

## 📞 联系方式

- 项目主页: https://github.com/aappaappoo/SoulmateBot
- Issue 反馈: https://github.com/aappaappoo/SoulmateBot/issues

---

**最后更新**: 2024年（多机器人架构版本）
