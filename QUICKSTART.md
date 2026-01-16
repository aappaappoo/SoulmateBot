# SoulmateBot 快速开始指南

欢迎使用 SoulmateBot！这是一个基于 Telegram 的情感陪伴机器人。

## 5 分钟快速开始

### 步骤 1: 获取 Bot Token

1. 打开 Telegram，搜索 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot` 命令
3. 按提示设置机器人名称
4. 保存获取的 Token (格式: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

### 步骤 2: 获取 OpenAI API Key

1. 访问 [OpenAI Platform](https://platform.openai.com/api-keys)
2. 登录或注册账号
3. 点击 "Create new secret key"
4. 保存 API Key (格式: `sk-...`)

> **注意**: OpenAI API 需要付费使用。如果不想使用，可以选择 Anthropic Claude。

### 步骤 3: 克隆项目

```bash
git clone https://github.com/aappaappoo/SoulmateBot.git
cd SoulmateBot
```

### 步骤 4: 配置环境

```bash
# 复制配置文件
cp .env.example .env

# 编辑配置文件，填入你的 Token 和 API Key
nano .env  # 或使用其他编辑器
```

最小配置:
```env
TELEGRAM_BOT_TOKEN=你的_Telegram_Bot_Token
OPENAI_API_KEY=你的_OpenAI_API_Key
DATABASE_URL=sqlite:///./soulmatebot.db
```

### 步骤 5: 安装依赖

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 步骤 6: 运行机器人

```bash
python main.py
```

看到以下输出表示成功:
```
Starting SoulmateBot...
Initializing database...
Database initialized
Bot initialized successfully
Bot username: @your_bot_username
Starting polling...
```

### 步骤 7: 测试机器人

1. 在 Telegram 中搜索你的机器人
2. 发送 `/start` 开始对话
3. 发送任意消息测试对话功能

## 常用命令

```bash
# 启动机器人
python main.py

# 运行测试
pytest tests/

# 查看日志
tail -f logs/bot_*.log

# 停止机器人
Ctrl + C
```

## Docker 快速启动

如果你熟悉 Docker:

```bash
# 1. 配置环境变量
cp .env.example .env
nano .env

# 2. 启动所有服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f bot
```

## 故障排除

### 问题: "Token is invalid"

**解决**: 检查 `.env` 文件中的 `TELEGRAM_BOT_TOKEN` 是否正确

### 问题: "OpenAI API error"

**解决**: 
- 检查 API Key 是否正确
- 确认账户有足够额度
- 检查网络连接

### 问题: 机器人不响应

**解决**:
1. 检查机器人是否在运行 (`python main.py`)
2. 查看日志文件 `logs/bot_*.log`
3. 确认在 Telegram 中给机器人发送了 `/start`

## 下一步

- 📖 阅读完整 [README.md](README.md)
- 🚀 查看 [DEPLOYMENT.md](DEPLOYMENT.md) 了解部署
- 📚 参考 [API.md](API.md) 了解 API

## 需要帮助?

- 💬 [提交 Issue](https://github.com/aappaappoo/SoulmateBot/issues)
- 📧 联系开发者

---

祝你使用愉快！ 🎉
