# 多机器人架构改造总结

## 📋 改造概述

本次改造将 SoulmateBot 从**单机器人架构**升级为**多机器人架构**，使其支持在一个频道或群组中同时配置和使用多个机器人实例。

## ✨ 核心功能

### 改造前（v0.2.0）
```
一个频道 → 一个机器人
```

### 改造后（v0.3.0）
```
一个频道 → 多个机器人
         ├─ Bot1 (客服助手，mention 模式)
         ├─ Bot2 (新闻播报，keyword 模式)
         └─ Bot3 (通用助手，auto 模式)
```

## 🔧 技术改造

### 1. 数据库架构 ✅

#### 新增表结构

**Bot 表** - 存储机器人配置
```sql
CREATE TABLE bots (
    id SERIAL PRIMARY KEY,
    bot_token VARCHAR(255) UNIQUE NOT NULL,
    bot_name VARCHAR(255) NOT NULL,
    bot_username VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    personality TEXT,
    system_prompt TEXT,
    ai_model VARCHAR(100) DEFAULT 'gpt-4',
    ai_provider VARCHAR(50) DEFAULT 'openai',
    is_public BOOLEAN DEFAULT TRUE,
    created_by INTEGER REFERENCES users(id),
    status VARCHAR(20) DEFAULT 'active',
    settings JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Channel 表** - 存储频道信息
```sql
CREATE TABLE channels (
    id SERIAL PRIMARY KEY,
    telegram_chat_id BIGINT UNIQUE NOT NULL,
    chat_type VARCHAR(50) NOT NULL,
    title VARCHAR(255),
    username VARCHAR(255),
    owner_id INTEGER REFERENCES users(id),
    subscription_tier VARCHAR(20) DEFAULT 'free',
    subscription_start_date TIMESTAMP,
    subscription_end_date TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    settings JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**ChannelBotMapping 表** - 存储频道-机器人映射关系
```sql
CREATE TABLE channel_bot_mappings (
    id SERIAL PRIMARY KEY,
    channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
    bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0,
    routing_mode VARCHAR(50) DEFAULT 'mention',
    keywords JSON DEFAULT '[]',
    settings JSON DEFAULT '{}',
    added_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 2. 服务层 ✅

#### BotManagerService - 机器人管理服务
文件：`src/services/bot_manager.py`

**主要功能**：
- `create_bot()` - 创建新机器人
- `get_bot_by_id()` - 根据 ID 获取机器人
- `get_bot_by_username()` - 根据用户名获取机器人
- `list_public_bots()` - 列出所有公开机器人
- `update_bot()` - 更新机器人配置
- `activate_bot()` / `deactivate_bot()` - 激活/停用机器人
- `delete_bot()` - 删除机器人（需要创建者权限）

#### ChannelManagerService - 频道管理服务
文件：`src/services/channel_manager.py`

**主要功能**：
- `get_or_create_channel()` - 获取或创建频道
- `add_bot_to_channel()` - 添加机器人到频道
- `remove_bot_from_channel()` - 从频道移除机器人
- `get_channel_bots()` - 获取频道中的所有机器人
- `update_mapping_settings()` - 更新映射配置
- `check_bot_in_channel()` - 检查机器人是否在频道中

#### MessageRouter - 消息路由器
文件：`src/services/message_router.py`

**主要功能**：
- `select_bot()` - 根据路由规则选择机器人
- `extract_mention()` - 从消息中提取 @mention
- `should_respond_in_channel()` - 判断是否应该在频道中响应
- `_check_keywords()` - 检查关键词匹配

**路由模式**：
1. **Mention 模式**：需要 @机器人用户名 才会响应
2. **Auto 模式**：自动响应所有消息，按优先级选择
3. **Keyword 模式**：根据关键词匹配触发

### 3. 命令系统 ✅

#### 新增命令处理器
文件：`src/handlers/bot_commands.py`

**新增命令**：

1. `/list_bots` - 列出所有可用的机器人
   ```
   显示所有公开的活跃机器人及其信息
   ```

2. `/add_bot <bot_id> [routing_mode]` - 添加机器人到频道
   ```
   示例：
   /add_bot 1 mention
   /add_bot 2 auto
   /add_bot 3 keyword
   ```

3. `/remove_bot <bot_id>` - 从频道移除机器人
   ```
   示例：/remove_bot 1
   ```

4. `/my_bots` - 查看当前频道的机器人
   ```
   显示频道中所有机器人的配置信息
   ```

5. `/config_bot <bot_id> [key] [value]` - 配置机器人参数
   ```
   示例：
   /config_bot 1                        # 查看配置
   /config_bot 1 routing_mode auto      # 修改路由模式
   /config_bot 1 priority 10            # 设置优先级
   ```

### 4. 消息处理 ✅

#### 更新消息处理器
文件：`src/handlers/messages.py`

**新增功能**：
- 自动获取或创建频道记录
- 获取频道中的活跃机器人
- 调用消息路由器选择响应机器人
- 使用选定机器人的配置生成回复
- 支持机器人个性化 system_prompt

**处理流程**：
```
用户消息 → 频道识别 → 获取活跃机器人 → 路由选择 → 
订阅检查 → AI响应生成 → 保存记录 → 返回回复
```

### 5. 数据库迁移 ✅

#### 迁移脚本
文件：`migrations/migrate_to_multibot.py`

**迁移步骤**：
1. 创建新表（Bot、Channel、ChannelBotMapping）
2. 创建默认机器人（使用当前配置）
3. 为所有现有用户创建私聊频道
4. 关联默认机器人到私聊频道
5. 验证迁移结果

**运行方法**：
```bash
python migrations/migrate_to_multibot.py
```

## 📚 文档更新 ✅

### 新增文档

1. **MULTI_BOT_GUIDE.md** - 多机器人使用指南
   - 完整的功能介绍
   - 详细的使用方法
   - 配置说明
   - 使用场景示例
   - 故障排查
   - API 参考

2. **PROJECT_STRUCTURE.md** - 工程结构说明
   - 完整的目录结构
   - 核心模块说明
   - 数据流程图
   - 开发指南

### 更新文档

1. **README.md** - 添加多机器人架构说明
   - 新特性亮点
   - 快速使用示例
   - 架构图更新

2. **ARCHITECTURE.md** - 架构文档更新
   - 新架构设计说明
   - 数据模型扩展
   - 数据流程更新

## 🎯 使用场景

### 场景 1：专业分工
```
频道：技术支持群
├─ 客服机器人（关键词：咨询、帮助、问题）
├─ 技术机器人（关键词：bug、报错、调试）
└─ 文档机器人（关键词：文档、教程、指南）
```

### 场景 2：多语言支持
```
频道：国际交流群
├─ 中文机器人（使用中文 system_prompt）
├─ 英文机器人（使用英文 system_prompt）
└─ 日文机器人（使用日文 system_prompt）
```

### 场景 3：不同AI模型对比
```
频道：AI测试群
├─ GPT-4 机器人
├─ Claude-3 机器人
└─ 自托管模型机器人
```

## 🚀 快速开始

### 1. 运行数据库迁移
```bash
python migrations/migrate_to_multibot.py
```

### 2. 查看可用机器人
```
/list_bots
```

### 3. 在群组中添加机器人
```
/add_bot 1 mention
```

### 4. 开始使用
```
# Mention 模式
@bot1 你好

# Auto 模式（直接发送）
今天天气怎么样？

# Keyword 模式
查询天气  # 如果配置了"天气"关键词
```

## 📊 改造统计

### 代码变更
- 新增文件：10 个
- 修改文件：5 个
- 新增代码行数：约 2,500 行
- 新增数据表：3 个

### 文件清单

**新增文件**：
1. `src/models/database.py` - 扩展了3个新模型
2. `src/services/bot_manager.py` - 机器人管理服务（202行）
3. `src/services/channel_manager.py` - 频道管理服务（228行）
4. `src/services/message_router.py` - 消息路由器（139行）
5. `src/handlers/bot_commands.py` - 机器人管理命令（495行）
6. `migrations/migrate_to_multibot.py` - 数据库迁移脚本（139行）
7. `MULTI_BOT_GUIDE.md` - 多机器人使用指南（487行）
8. `PROJECT_STRUCTURE.md` - 工程结构说明（499行）

**修改文件**：
1. `src/bot/main.py` - 注册新命令
2. `src/handlers/__init__.py` - 导出新命令
3. `src/handlers/messages.py` - 集成消息路由
4. `README.md` - 更新项目说明
5. `ARCHITECTURE.md` - 更新架构文档

## ✅ 兼容性

### 向后兼容
- ✅ 现有用户数据完全兼容
- ✅ 现有命令继续工作
- ✅ 私聊功能不受影响
- ✅ 订阅系统正常运行

### 迁移说明
- 运行迁移脚本后，所有现有用户会自动关联到默认机器人
- 私聊对话体验保持不变
- 新功能仅在群组/频道中启用

## 🎉 核心优势

1. **灵活性** - 一个频道可以配置多个专业化的机器人
2. **可扩展** - 易于添加新机器人和新功能
3. **可共享** - 公开机器人可被其他用户添加到他们的频道
4. **智能路由** - 三种路由模式满足不同场景需求
5. **个性化** - 每个机器人可以有独特的个性和AI模型
6. **权限管理** - 清晰的权限体系保护机器人配置

## 🔮 未来扩展

### 短期计划
- [ ] 添加单元测试
- [ ] 添加集成测试
- [ ] 性能优化
- [ ] 监控和日志增强

### 长期计划
- [ ] Web 管理后台
- [ ] 机器人市场
- [ ] 高级路由策略（基于时间、用户等）
- [ ] 机器人间协作
- [ ] 统计和分析功能

## 📝 注意事项

1. **数据库迁移**：升级前务必备份数据库
2. **Bot Token**：需要为每个机器人准备独立的 Bot Token
3. **性能考虑**：频道机器人数量建议不超过10个
4. **权限管理**：只有频道管理员可以添加/移除机器人

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

**版本**: v0.3.0 (Multi-Bot Architecture)  
**发布日期**: 2024年  
**作者**: SoulmateBot Team
