# Changelog

所有重要的项目变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 计划中
- Stripe 支付集成
- 多语言支持
- 语音消息支持
- 管理后台界面

## [0.1.1] - 2026-01-16

### 安全 (Security)
- 🔒 更新 aiohttp 从 3.9.3 到 3.13.3 (修复 zip bomb 漏洞和 DoS 漏洞)
- 🔒 更新 pillow 从 10.2.0 到 10.3.0 (修复 buffer overflow 漏洞)

## [0.1.0] - 2026-01-16

### 新增 (Added)

#### 核心功能
- ✨ Telegram Bot 基础框架
- ✨ AI 对话功能 (支持 OpenAI GPT-4 和 Anthropic Claude)
- ✨ 图片服务基础架构
- ✨ 用户会话管理
- ✨ 对话历史记录

#### 订阅系统
- ✨ 三层订阅计划 (免费版/基础版/高级版)
- ✨ 使用限额管理
- ✨ 每日使用统计
- ✨ 订阅状态查询
- ✨ 订阅升级功能

#### 数据库
- ✨ User 模型 - 用户信息和订阅
- ✨ Conversation 模型 - 对话历史
- ✨ UsageRecord 模型 - 使用记录
- ✨ Payment 模型 - 支付记录
- ✨ SQLAlchemy ORM 集成
- ✨ 支持 PostgreSQL 和 SQLite

#### 命令
- ✨ /start - 欢迎新用户
- ✨ /help - 帮助信息
- ✨ /status - 查看订阅状态
- ✨ /subscribe - 订阅计划
- ✨ /image - 获取温馨图片

#### 开发工具
- ✨ Docker 支持
- ✨ Docker Compose 配置
- ✨ 测试框架 (pytest)
- ✨ CI/CD 配置 (GitHub Actions)
- ✨ Demo 脚本

#### 文档
- 📚 完整的 README 文档
- 📚 API 文档
- 📚 部署指南
- 📚 快速开始指南
- 📚 贡献指南
- 📚 架构文档

#### 配置
- ⚙️ 环境变量配置
- ⚙️ Pydantic 配置管理
- ⚙️ 订阅限额配置
- ⚙️ 速率限制配置

### 技术细节

#### 依赖
- python-telegram-bot 20.7
- openai 1.12.0
- anthropic 0.18.1
- sqlalchemy 2.0.25
- pydantic 2.6.1
- loguru 0.7.2

#### 架构
- 模块化设计
- 清晰的层次结构
- 依赖注入支持
- 异步处理

### 文件结构
```
37 个新文件:
- 核心代码: 13 个 Python 文件
- 配置文件: 4 个
- 文档文件: 7 个
- 测试文件: 3 个
- 部署文件: 3 个
```

---

## 版本说明

### [0.1.0] - MVP 版本
第一个可用的基础版本，包含核心功能：
- ✅ 基本对话功能
- ✅ 订阅系统
- ✅ 数据库集成
- ✅ Docker 部署
- ✅ 完整文档

### 未来版本计划

#### [0.2.0] - 图片增强
- DALL-E 图片生成完整集成
- 情感图片库
- 图片缓存系统

#### [0.3.0] - 支付集成
- Stripe 支付
- 订阅自动续费
- 发票生成

#### [0.4.0] - 高级功能
- 情感分析
- 多语言支持
- 语音消息

#### [1.0.0] - 生产就绪
- 性能优化
- 监控告警
- 完整测试
- 安全加固

---

## 贡献者

感谢所有贡献者！

---

[Unreleased]: https://github.com/aappaappoo/SoulmateBot/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/aappaappoo/SoulmateBot/releases/tag/v0.1.0
