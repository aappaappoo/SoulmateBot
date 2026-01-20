# 多机器人架构使用指南

## 📋 概述

本项目已升级为**多机器人架构**，支持在一个频道或群组中同时使用多个机器人。每个机器人可以有不同的个性、AI模型和配置。

## 🏗️ 架构设计

### 核心概念

1. **Bot（机器人）**：独立的机器人实例，拥有自己的Token、配置和个性
2. **Channel（频道）**：Telegram的频道、群组或私聊
3. **ChannelBotMapping（映射）**：频道和机器人之间的关联关系

### 数据模型

```
┌─────────────┐         ┌──────────────────────┐         ┌─────────────┐
│   Channel   │◄───────►│ ChannelBotMapping    │◄───────►│    Bot      │
│  (频道)     │  1:N    │    (映射关系)        │   N:1   │  (机器人)   │
└─────────────┘         └──────────────────────┘         └─────────────┘
      │                           │                              │
      │                           │                              │
   chat_id                   routing_mode                   bot_token
   chat_type                  priority                       bot_name
   owner_id                   keywords                       personality
   settings                   is_active                      ai_model
```

## 🎯 功能特性

### 1. 机器人管理

- ✅ 创建多个机器人实例
- ✅ 配置机器人个性和AI模型
- ✅ 公开或私有机器人
- ✅ 激活/停用机器人

### 2. 频道管理

- ✅ 将机器人添加到频道/群组
- ✅ 从频道移除机器人
- ✅ 查看频道中的所有机器人
- ✅ 配置机器人在频道中的行为

### 3. 路由模式

机器人支持三种路由模式：

#### Mention 模式（默认）
- 需要 @机器人名 才会响应
- 适合多机器人共存的场景
- 用户可以指定与哪个机器人对话

```
示例：
用户: @bot1 你好
Bot1: 你好！我是Bot1，很高兴为你服务。
```

#### Auto 模式
- 自动响应频道中的所有消息
- 适合只有一个活跃机器人的场景
- 优先级高的机器人优先响应

```
示例：
用户: 今天天气怎么样？
Bot1: 让我帮你查询一下天气...
```

#### Keyword 模式
- 根据关键词触发响应
- 可以为不同机器人设置不同的关键词
- 适合专业化分工的场景

```
示例（配置关键词）：
Bot1: ["天气", "温度", "降雨"]
Bot2: ["新闻", "资讯", "热点"]

用户: 今天天气怎么样？
Bot1: （被关键词"天气"触发）...
```

## 📝 使用方法

### 管理员命令

#### 1. 查看可用机器人
```
/list_bots
```
显示所有可以添加到频道的公开机器人。

#### 2. 添加机器人到频道
```
/add_bot <bot_id> [routing_mode]
```

示例：
```
/add_bot 1 mention          # 添加Bot1，使用mention模式
/add_bot 2 auto             # 添加Bot2，使用auto模式
/add_bot 3 keyword          # 添加Bot3，使用keyword模式
```

#### 3. 查看频道中的机器人
```
/my_bots
```
显示当前频道中所有已添加的机器人及其配置。

#### 4. 配置机器人
```
/config_bot <bot_id> [key] [value]
```

示例：
```
/config_bot 1                           # 查看Bot1的配置
/config_bot 1 routing_mode auto         # 修改为auto模式
/config_bot 1 priority 10               # 设置优先级为10
/config_bot 1 active false              # 停用机器人
```

#### 5. 移除机器人
```
/remove_bot <bot_id>
```

示例：
```
/remove_bot 1    # 从当前频道移除Bot1
```

### 用户命令

#### 私聊模式
在私聊中，直接发送消息即可与机器人对话：
```
用户: 你好
机器人: 你好！我能帮你什么？
```

#### 群组/频道模式

**Mention模式**：
```
用户: @bot1 你好
Bot1: 你好！有什么可以帮助你的？
```

**Auto模式**：
```
用户: 今天天气怎么样？
Bot: 让我帮你查询...（按优先级响应）
```

**Keyword模式**：
```
用户: 查询今天的天气
Bot1: （检测到关键词"天气"）正在为你查询...
```

## 🔧 配置说明

### 机器人配置

每个机器人可以配置以下参数：

```python
{
    "bot_name": "小助手",           # 机器人名称
    "bot_username": "helper_bot",   # 机器人用户名（不含@）
    "description": "通用助手",       # 描述
    "personality": "友善、专业",     # 个性
    "system_prompt": "...",         # AI系统提示词
    "ai_model": "gpt-4",           # AI模型
    "ai_provider": "openai",       # AI提供商
    "is_public": true,             # 是否公开
    "settings": {                   # 其他配置
        "temperature": 0.7,
        "max_tokens": 2000
    }
}
```

### 映射配置

每个频道-机器人映射可以配置：

```python
{
    "is_active": true,              # 是否激活
    "priority": 0,                  # 优先级（数字越大越高）
    "routing_mode": "mention",      # 路由模式
    "keywords": ["天气", "温度"],   # 关键词列表
    "settings": {}                  # 特定配置
}
```

## 💡 使用场景

### 场景1：专业分工

为不同的任务创建专门的机器人：

```
Bot1 - 客服助手（关键词：咨询、帮助、问题）
Bot2 - 新闻播报（关键词：新闻、资讯、热点）
Bot3 - 天气查询（关键词：天气、温度、降雨）
```

### 场景2：多语言支持

为不同语言创建专门的机器人：

```
Bot1 - 中文助手（使用中文system_prompt）
Bot2 - English Assistant（使用英文system_prompt）
Bot3 - 日本語アシスタント（使用日文system_prompt）
```

### 场景3：不同个性

创建不同个性的机器人满足不同需求：

```
Bot1 - 严肃专业型（适合工作讨论）
Bot2 - 轻松幽默型（适合闲聊娱乐）
Bot3 - 情感陪伴型（适合心理疏导）
```

### 场景4：不同AI模型

使用不同的AI模型进行对比：

```
Bot1 - GPT-4（OpenAI）
Bot2 - Claude-3（Anthropic）
Bot3 - 自托管模型（vLLM）
```

## 🚀 快速开始

### 步骤1：创建机器人

使用BotManagerService创建机器人：

```python
from src.services.bot_manager import BotManagerService
from src.database import get_db_session

db = get_db_session()
bot_service = BotManagerService(db)

# 创建机器人
bot = bot_service.create_bot(
    bot_token="YOUR_BOT_TOKEN",
    bot_name="小助手",
    bot_username="helper_bot",
    creator_id=user_id,
    description="通用助手机器人",
    personality="友善、专业、乐于助人",
    system_prompt="你是一个友善的助手...",
    ai_model="gpt-4",
    ai_provider="openai",
    is_public=True
)
```

### 步骤2：添加到频道

在Telegram中使用命令：

```
/add_bot 1 mention
```

### 步骤3：开始使用

在频道中@机器人即可：

```
@helper_bot 你好
```

## 📊 架构图

### 消息处理流程

```
用户发送消息
    ↓
Telegram Bot API
    ↓
消息路由器
    ↓
  ┌──────────────┐
  │ 路由模式判断  │
  └──────┬───────┘
         │
    ┌────┴────┬─────────┬────────┐
    │         │         │        │
 Mention    Auto    Keyword   直接
  模式      模式      模式     模式
    │         │         │        │
    └────┬────┴─────────┴────┬───┘
         │                   │
    选择机器人            获取AI响应
         │                   │
         └───────┬───────────┘
                 │
            返回给用户
```

### 数据库关系

```
┌──────────┐
│  User    │ 创建者
│  (用户)  │
└────┬─────┘
     │ 1:N
     │
┌────▼──────────┐
│  Bot          │
│  (机器人)     │◄─────┐
└────┬──────────┘      │
     │ N:M             │ N:1
     │                 │
┌────▼─────────────────▼──┐
│  ChannelBotMapping       │
│  (映射)                  │
└────┬─────────────────────┘
     │ N:1
     │
┌────▼─────┐
│  Channel │
│  (频道)  │
└──────────┘
```

## 🔐 权限管理

### 机器人创建者权限
- 修改机器人配置
- 删除机器人
- 设置机器人公开/私有

### 频道管理员权限
- 添加公开机器人到频道
- 移除频道中的机器人
- 配置机器人在频道中的行为

### 普通用户权限
- 查看公开机器人列表
- 在有权限的频道中使用机器人
- 与机器人私聊

## 🎓 最佳实践

### 1. 合理设置优先级

为机器人设置合适的优先级，避免冲突：

```
优先级设置建议：
- 专用机器人：priority = 10
- 通用机器人：priority = 5
- 备用机器人：priority = 1
```

### 2. 明确路由模式

根据使用场景选择合适的路由模式：

- **单机器人场景**：使用 auto 模式
- **多机器人场景**：使用 mention 模式
- **专业分工场景**：使用 keyword 模式

### 3. 优化System Prompt

为每个机器人定制专门的系统提示词：

```python
# 客服机器人
system_prompt = """
你是一个专业的客服助手。
你的任务是：
1. 解答用户问题
2. 提供技术支持
3. 友善且专业
"""

# 新闻机器人
system_prompt = """
你是一个新闻播报助手。
你的任务是：
1. 播报最新新闻
2. 分析热点事件
3. 客观中立
"""
```

### 4. 定期维护

- 定期检查机器人状态
- 更新系统提示词
- 优化关键词配置
- 分析使用数据

## 🔍 故障排查

### 问题1：机器人不响应

**可能原因**：
- 机器人未激活
- 路由模式配置错误
- 关键词不匹配

**解决方法**：
```
/my_bots                     # 查看机器人状态
/config_bot <bot_id>         # 检查配置
/config_bot <bot_id> active true  # 激活机器人
```

### 问题2：多个机器人同时响应

**可能原因**：
- 多个机器人使用 auto 模式
- 优先级设置不合理

**解决方法**：
```
# 修改为mention模式
/config_bot 1 routing_mode mention
/config_bot 2 routing_mode mention

# 或设置不同优先级
/config_bot 1 priority 10
/config_bot 2 priority 5
```

### 问题3：无法添加机器人

**可能原因**：
- 机器人不是公开的
- 机器人状态为inactive

**解决方法**：
- 联系机器人创建者
- 检查机器人状态

## 📚 API参考

### BotManagerService

```python
# 创建机器人
bot = bot_service.create_bot(...)

# 获取机器人
bot = bot_service.get_bot_by_id(bot_id)
bot = bot_service.get_bot_by_username(username)

# 列出机器人
bots = bot_service.list_public_bots()
bots = bot_service.list_bots_by_creator(creator_id)

# 更新机器人
bot = bot_service.update_bot(bot_id, **kwargs)

# 激活/停用
bot_service.activate_bot(bot_id)
bot_service.deactivate_bot(bot_id)

# 删除机器人
bot_service.delete_bot(bot_id, creator_id)
```

### ChannelManagerService

```python
# 获取或创建频道
channel = channel_service.get_or_create_channel(...)

# 添加机器人到频道
mapping = channel_service.add_bot_to_channel(...)

# 移除机器人
channel_service.remove_bot_from_channel(channel_id, bot_id)

# 获取频道机器人
mappings = channel_service.get_channel_bots(channel_id)

# 更新配置
mapping = channel_service.update_mapping_settings(...)
```

## 🎉 总结

多机器人架构为SoulmateBot带来了更强的灵活性和扩展性：

- ✅ 支持多机器人共存
- ✅ 灵活的路由模式
- ✅ 可配置的机器人个性
- ✅ 多种AI模型支持
- ✅ 完善的权限管理

开始使用多机器人架构，打造更加智能和个性化的Telegram机器人体验！
