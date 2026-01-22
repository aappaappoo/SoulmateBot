# 部署指南

## 目录
- [本地开发部署](#本地开发部署)
- [Docker 部署](#docker-部署)
- [云服务器部署](#云服务器部署)
- [常见问题](#常见问题)

---

## 本地开发部署

### 步骤 1: 准备环境

```bash
# 检查 Python 版本
python --version  # 需要 3.11+

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
```

### 步骤 2: 配置 Telegram Bot

1. 访问 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot` 创建新机器人
3. 按提示设置机器人名称和用户名
4. 保存获取的 Bot Token

### 步骤 3: 配置 AI API

#### 使用 OpenAI

1. 访问 [OpenAI Platform](https://platform.openai.com/)
2. 创建 API Key
3. 确保账户有足够的额度

#### 或使用 Anthropic Claude

1. 访问 [Anthropic Console](https://console.anthropic.com/)
2. 创建 API Key
3. 选择合适的模型

### 步骤 4: 配置环境变量

```bash
# 复制示例配置
cp .env.example .env

# 编辑 .env 文件
nano .env  # 或使用其他编辑器
```

必填配置:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
OPENAI_API_KEY=your_openai_key_here
# 或
ANTHROPIC_API_KEY=your_anthropic_key_here
```

### 步骤 5: 初始化数据库

```bash
# 使用 SQLite (默认)
python -c "from src.database import init_db; init_db()"

# 或使用 PostgreSQL
# 1. 创建数据库
createdb soulmatebot

# 2. 更新 .env 中的 DATABASE_URL
DATABASE_URL=postgresql://user:password@localhost:5432/soulmatebot

# 3. 初始化
python -c "from src.database import init_db; init_db()"
```

### 步骤 6: 运行机器人

```bash
python main.py
```

成功启动后，你会看到:
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
3. 尝试发送消息测试对话功能
4. 使用 `/help` 查看所有命令

---

## Docker 部署

### 使用 Docker Compose (推荐)

#### 步骤 1: 准备配置

```bash
# 复制环境变量文件
cp .env.example .env

# 编辑配置
nano .env
```

更新以下配置:
```env
TELEGRAM_BOT_TOKEN=your_token
OPENAI_API_KEY=your_key
DATABASE_URL=postgresql://soulmatebot:changeme@db:5432/soulmatebot
REDIS_URL=redis://redis:6379/0
DB_PASSWORD=your_secure_password
```

#### 步骤 2: 启动服务

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f bot

# 检查服务状态
docker-compose ps
```

#### 步骤 3: 初始化数据库

```bash
# 进入容器
docker-compose exec bot bash

# 初始化数据库
python -c "from src.database import init_db; init_db()"

# 退出容器
exit
```

#### 步骤 4: 管理服务

```bash
# 停止服务
docker-compose stop

# 重启服务
docker-compose restart

# 查看日志
docker-compose logs -f

# 停止并删除容器
docker-compose down

# 停止并删除容器和数据卷
docker-compose down -v
```

### 单独使用 Docker

```bash
# 构建镜像
docker build -t soulmatebot .

# 运行容器
docker run -d \
  --name soulmatebot \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  soulmatebot
```

---

## 云服务器部署

### AWS EC2 部署

#### 步骤 1: 启动 EC2 实例

1. 选择 Ubuntu 22.04 LTS
2. 实例类型: t3.small 或更高
3. 配置安全组:
   - SSH (22)
   - HTTPS (443) - 如果使用 webhook

#### 步骤 2: 连接服务器

```bash
ssh -i your-key.pem ubuntu@your-server-ip
```

#### 步骤 3: 安装依赖

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Python 和依赖
sudo apt install -y python3.11 python3.11-venv python3-pip git

# 安装 Docker (可选)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# 安装 Docker Compose
sudo apt install -y docker-compose
```

#### 步骤 4: 部署应用

```bash
# 克隆代码
git clone https://github.com/aappaappoo/SoulmateBot.git
cd SoulmateBot

# 配置环境变量
cp .env.example .env
nano .env

# 使用 Docker Compose 部署
docker-compose up -d

# 或手动部署
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

#### 步骤 5: 配置进程管理 (systemd)

创建服务文件:
```bash
sudo nano /etc/systemd/system/soulmatebot.service
```

添加以下内容:
```ini
[Unit]
Description=SoulmateBot Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/SoulmateBot
Environment="PATH=/home/ubuntu/SoulmateBot/venv/bin"
ExecStart=/home/ubuntu/SoulmateBot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务:
```bash
sudo systemctl daemon-reload
sudo systemctl enable soulmatebot
sudo systemctl start soulmatebot
sudo systemctl status soulmatebot
```

查看日志:
```bash
sudo journalctl -u soulmatebot -f
```

### 使用 Webhook (可选)

如果你想使用 webhook 而不是 polling:

#### 步骤 1: 配置 Nginx

```bash
sudo apt install -y nginx certbot python3-certbot-nginx

# 配置 SSL
sudo certbot --nginx -d yourdomain.com
```

#### 步骤 2: 修改代码

在 `src/bot/main.py` 中添加 webhook 支持:

```python
# 使用 webhook 而不是 polling
self.app.run_webhook(
    listen="0.0.0.0",
    port=8080,
    webhook_url=settings.telegram_webhook_url
)
```

---

## 常见问题

### Q: 如何更新代码？

```bash
# 拉取最新代码
git pull

# 使用 Docker
docker-compose down
docker-compose build
docker-compose up -d

# 手动部署
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart soulmatebot
```

### Q: 如何备份数据？

```bash
# 备份 SQLite 数据库
cp soulmatebot.db soulmatebot_backup_$(date +%Y%m%d).db

# 备份 PostgreSQL
docker-compose exec db pg_dump -U soulmatebot soulmatebot > backup.sql

# 或直接备份数据卷
docker run --rm -v soulmatebot_postgres_data:/data -v $(pwd):/backup ubuntu tar czf /backup/db_backup.tar.gz /data
```

### Q: 如何查看日志？

```bash
# Docker Compose
docker-compose logs -f bot

# systemd
sudo journalctl -u soulmatebot -f

# 应用日志
tail -f logs/bot_*.log
```

### Q: 机器人不响应怎么办？

1. 检查 Bot Token 是否正确
2. 检查网络连接
3. 查看日志文件
4. 确认 API 密钥有效且有额度
5. 检查数据库连接

### Q: 如何限制某些用户访问？

在 `.env` 中配置:
```env
ADMIN_USER_IDS=123456789,987654321
```

然后在代码中添加验证逻辑。

---

## 监控和维护

### 日志管理

```bash
# 定期清理旧日志
find logs/ -name "*.log" -mtime +7 -delete

# 配置日志轮转
sudo apt install logrotate
```

### 性能监控

```bash
# 安装监控工具
pip install prometheus-client grafana-api

# 查看资源使用
docker stats
htop
```

### 数据库维护

```bash
# 清理旧数据 (超过 30 天)
docker-compose exec db psql -U soulmatebot -d soulmatebot -c "DELETE FROM conversations WHERE timestamp < NOW() - INTERVAL '30 days';"

# 分析数据库
docker-compose exec db psql -U soulmatebot -d soulmatebot -c "VACUUM ANALYZE;"
```

---

## 安全建议

1. **使用强密码** - 数据库和 API 密钥
2. **定期更新** - 保持系统和依赖最新
3. **配置防火墙** - 只开放必要端口
4. **SSL/TLS** - 使用 HTTPS 和 webhook
5. **备份数据** - 定期备份数据库
6. **监控日志** - 及时发现异常
7. **限制访问** - 使用白名单或认证

---

需要帮助？请在 GitHub 上提交 Issue 或查看文档。
