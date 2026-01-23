# Bot 配置文件说明文档

本文档详细说明了 SoulmateBot 机器人的 YAML 配置文件结构，以及每个配置项在代码中的使用位置。

## 📁 配置文件位置

每个 Bot 的配置文件位于 `bots/{bot_id}/config.yaml`

配置文件由 `src/bot/config_loader.py` 中的 `BotConfigLoader` 类加载和解析。

---

## 📋 配置项一览表

| 配置项 | 说明 | 使用位置 |
|--------|------|----------|
| `bot` | Bot基础信息 | `BotConfig` 类 |
| `personality` | 人格配置（性格、外貌、爱好等） | `PersonalityConfig` 类 |
| `ai` | AI模型配置 | `AIConfig` 类 |
| `prompt` | 系统提示词配置 | `PromptConfig` 类 |
| `features` | 功能开关配置 | `BotConfig.features_enabled/disabled` |
| `routing` | 消息路由配置 | `RoutingConfig` 类 |
| `limits` | 使用限额配置 | `LimitsConfig` 类 |
| `messages` | 消息模板配置 | `MessagesConfig` 类 |
| `metadata` | 元数据 | `BotConfig.version` |

---

## 🤖 bot - 基础信息配置

定义 Bot 的基本身份信息。

```yaml
bot:
  name: "琪琪"                    # Bot名称，用于对话中自我介绍
  description: "温柔陪伴型机器人"  # Bot描述，用于展示给用户
  type: "companion"               # Bot类型: companion/assistant/service
  language: "zh"                  # 语言: zh/en
  gender: "female"                # 性别: female/male
  is_public: true                 # 是否公开可被添加
```

**代码使用位置：**
- `src/bot/config_loader.py` → `BotConfig` 类
- 加载方法：`BotConfigLoader.load_config()`
- 获取：`config.name`, `config.description`, `config.bot_type`

---

## 🎭 personality - 人格配置

定义 Bot 的独特个性，包括性格、外貌、爱好等个人特征。

### character - 基础人设描述

```yaml
personality:
  character: |
    她是一名非常温柔、耐心、擅长倾听的陪伴型机器人...
```

Bot 的核心性格描述，用于构建 AI 的角色认知。

### traits - 性格特点

```yaml
personality:
  traits:
    - "温柔体贴"
    - "耐心倾听"
    - "高度共情"
```

以列表形式定义的性格特点关键词。

### appearance - 外貌特征

```yaml
personality:
  appearance:
    avatar: "柔和温暖的少女形象"           # 头像描述
    physical_description: |               # 详细外貌描述
      一位约22岁的温柔女孩...
    style: "偏爱柔和色调的衣服"            # 穿着风格
    distinctive_features:                 # 独特特征列表
      - "说话时会轻轻点头"
      - "微笑时眼睛会弯成月牙"
```

**代码使用位置：**
- `src/bot/config_loader.py` → `AppearanceConfig` 类
- 解析方法：`BotConfigLoader._parse_appearance_config()`

### catchphrases - 口头禅

```yaml
personality:
  catchphrases:
    - "慢慢说，我在听呢 🌸"
    - "这样啊，我懂你的感受"
    - "没关系的，这很正常"
```

Bot 的标志性语句，增加角色个性。

### ideals & life_goals - 理想和人生规划

```yaml
personality:
  ideals: |
    希望成为一个能让人感到安心的存在...
  
  life_goals:
    - "成为让人放松的陪伴者"
    - "开一家安静的咖啡馆"
```

定义 Bot 的价值观和人生目标，让角色更加真实丰满。

### likes & dislikes - 爱好和讨厌点

```yaml
personality:
  likes:
    - "温暖的阳光"
    - "雨天的窗边"
    - "治愈系的音乐"

  dislikes:
    - "大声争吵"
    - "催促和逼迫"
    - "说教和批判"
```

Bot 的喜好和厌恶，丰富角色人设。

### living_environment - 居住环境

```yaml
personality:
  living_environment: |
    一个温馨的小公寓，装修风格偏向日式简约...
```

描述 Bot 的生活空间，增加真实感。

### speaking_style - 语言风格

```yaml
personality:
  speaking_style:
    tone: "柔和温暖"           # 语气：柔和/轻快/活泼等
    formality: "自然亲切"      # 正式程度
    use_emoji: true            # 是否使用emoji
    emoji_frequency: "low"     # emoji频率: low/medium/high
    sentence_length: "short"   # 句子长度: short/medium/long
    avoid:                     # 避免的表达方式
      - "命令式语气"
      - "居高临下的态度"
```

**代码使用位置：**
- `src/bot/config_loader.py` → `PersonalityConfig.speaking_style`

### interaction_style - 交互偏好

```yaml
personality:
  interaction_style:
    ask_clarifying_questions: true   # 是否追问澄清
    provide_examples: false          # 是否提供例子
    use_analogies: low               # 使用类比: low/medium/high
    summarize_key_points: false      # 是否总结要点
    encourage_user: true             # 是否鼓励用户
    emotional_reflection: true       # 是否情绪反馈
    boundary_awareness: high         # 边界意识: low/medium/high
```

### emotional_response - 情绪应对策略

```yaml
personality:
  emotional_response:
    priority:                       # 情绪应对优先级
      - "先倾听"
      - "复述感受"
      - "温和安抚"
    avoid_actions:                  # 避免的行为
      - "快速给解决方案"
      - "否定用户感受"
```

### safety_policy - 安全策略

```yaml
personality:
  safety_policy:
    avoid_topics:                   # 需要避开的话题
      - "医疗诊断"
      - "法律判断"
    high_risk_keywords:             # 高风险关键词
      - "自杀"
      - "不想活了"
    response_strategy:              # 高风险场景应对策略
      - "保持冷静和温和"
      - "建议寻求专业帮助"
```

**代码使用位置：**
- `src/bot/config_loader.py` → `PersonalityConfig` 类
- 解析方法：`BotConfigLoader._parse_personality_config()`

---

## 🧠 ai - AI模型配置

配置 AI 模型的参数。

```yaml
ai:
  provider: "openai"           # AI提供商: openai/anthropic/vllm
  model: "gpt-4o"              # 模型名称
  temperature: 0.7             # 生成温度 (0-1)
  max_tokens: 800              # 最大token数
  context_window: 4096         # 上下文窗口大小
```

**代码使用位置：**
- `src/bot/config_loader.py` → `AIConfig` 类
- `src/llm_gateway/providers.py` → AI服务调用
- 解析方法：`BotConfigLoader._parse_ai_config()`

---

## 📝 prompt - 提示词配置

定义系统提示词。

```yaml
prompt:
  template: "gentle_companion"    # 使用预定义模板（可选）
  custom: |                       # 自定义系统提示词
    你是琪琪，一位温柔、耐心的陪伴型伙伴...
  variables:                      # 模板变量
    bot_name: "琪琪"
```

**代码使用位置：**
- `src/bot/config_loader.py` → `PromptConfig` 类
- `BotConfig.get_system_prompt()` → 获取最终系统提示词
- `src/conversation/prompt_template.py` → 模板渲染

---

## ⚡ features - 功能配置

控制 Bot 的功能开关。

```yaml
features:
  enabled:                        # 启用的功能
    - "emotional_support"
    - "daily_companion"
    - "conversation_memory"
  
  disabled:                       # 禁用的功能
    - "code_execution"
    - "web_search"
```

**代码使用位置：**
- `src/bot/config_loader.py` → `BotConfig.features_enabled/disabled`
- 检查方法：`BotConfig.is_feature_enabled(feature)`

---

## 🔀 routing - 消息路由配置

控制消息如何触发 Bot 响应。

```yaml
routing:
  mode: "auto"                          # 路由模式: mention/auto/keyword
  private_chat_auto_reply: true         # 私聊是否自动回复
  group_chat_mention_required: true     # 群聊是否需要@
```

**代码使用位置：**
- `src/bot/config_loader.py` → `RoutingConfig` 类
- `src/agents/router.py` → 消息路由逻辑

---

## 📊 limits - 限额配置

设置不同订阅等级的使用限额。

```yaml
limits:
  free_tier:
    messages: 20         # 免费用户每日消息限额
    images: 0            # 免费用户每日图片限额
  
  basic_tier:
    messages: 200
    images: 5
  
  premium_tier:
    messages: 2000
    images: 50
```

**代码使用位置：**
- `src/bot/config_loader.py` → `LimitsConfig`, `LimitConfig` 类
- 获取方法：`BotConfig.get_limit(tier, limit_type)`
- `src/subscription/service.py` → 限额检查

---

## 💬 messages - 消息模板配置

定义 Bot 在特定场景使用的固定消息。

```yaml
messages:
  welcome: |                  # 欢迎消息
    🌸 你好呀，我是琪琪~
    
  help: |                     # 帮助消息
    我可以帮你：
    💕 倾听你的心情
    
  limit_reached: |            # 限额用尽消息
    今天聊得好开心呢~
    不过需要休息一下了...
```

**代码使用位置：**
- `src/bot/config_loader.py` → `MessagesConfig` 类
- `src/handlers/commands.py` → /start, /help 命令响应

---

## 📎 metadata - 元数据

配置文件的版本和作者信息。

```yaml
metadata:
  version: "1.0.0"
  author: "SoulmateBot Team"
  created_at: "2025-01-23"
  updated_at: "2025-01-23"
```

**代码使用位置：**
- `src/bot/config_loader.py` → `BotConfig.version`

---

## 🔧 配置加载流程

```
1. 程序启动
   │
   ▼
2. BotConfigLoader 初始化
   │
   ▼
3. 扫描 bots/ 目录下的子目录
   │
   ▼
4. 读取各 Bot 的 config.yaml
   │
   ▼
5. 使用 _parse_xxx_config() 方法解析各配置块
   │
   ▼
6. 创建 BotConfig 对象
   │
   ▼
7. 缓存配置供后续使用
```

---

## 📂 相关代码文件

| 文件 | 说明 |
|------|------|
| `src/bot/config_loader.py` | 配置加载器，所有配置类定义 |
| `src/agents/skills.py` | 技能系统（如使用技能功能） |
| `src/llm_gateway/providers.py` | AI服务提供者配置 |
| `src/handlers/commands.py` | 命令处理，使用 messages 配置 |
| `src/subscription/service.py` | 订阅服务，使用 limits 配置 |

---

## 📝 创建新 Bot 的步骤

1. 在 `bots/` 目录下创建新目录，如 `bots/my_bot/`
2. 创建 `__init__.py` 文件（可为空）
3. 创建 `config.yaml` 配置文件
4. 填写必要的配置项：
   - `bot` - 基础信息
   - `personality` - 人格配置（推荐完整填写）
   - `ai` - AI模型配置
   - `prompt` - 系统提示词
   - `messages` - 消息模板

5. 重启程序或调用 `config_loader.reload_config(bot_id)` 加载配置

---

## 💡 配置最佳实践

1. **人格配置要完整**：完整的人格配置能让 Bot 更有个性
2. **系统提示词要详细**：`prompt.custom` 是 Bot 行为的核心定义
3. **安全策略要设置**：明确需要避开的话题和高风险词汇
4. **消息模板要友好**：welcome/help 消息是用户的第一印象
5. **限额要合理**：根据实际使用场景设置合理的限额

---

## 🎯 配置项与人设规划对应

根据问题需求，Bot 是一个个体机器人，需要包含：

| 需求 | 对应配置项 |
|------|-----------|
| 性格 | `personality.character`, `personality.traits` |
| 性别 | `bot.gender` |
| 独特外貌特征 | `personality.appearance` |
| 口头禅 | `personality.catchphrases` |
| 理想和人生规划 | `personality.ideals`, `personality.life_goals` |
| 爱好和讨厌点 | `personality.likes`, `personality.dislikes` |
| 居住环境 | `personality.living_environment` |
