# SoulmateBot —— AI 情感陪伴机器人平台

> 基于 Telegram 的多机器人 AI 情感陪伴平台，集成语音对话、情绪感知、记忆管理、桌面自动化等能力，为用户提供个性化的智能陪伴体验。

---

## 📋 目录

- [功能总览](#功能总览)
- [功能点与逻辑链路](#功能点与逻辑链路)
- [项目目录结构](#项目目录结构)
- [示例：用户输入"帮我查看明天天气"的完整流程](#示例用户输入帮我查看明天天气的完整流程)
- [快速开始](#快速开始)

---

## 功能总览

| 序号 | 功能模块 | 简要说明 |
|------|----------|----------|
| 1 | 智能语音对话 | 语音识别（普通话）、语音聊天记录保存、自然语言理解与语音回复 |
| 2 | 对话意图识别 | 基于 LLM 的意图分类（日常交互/应用请求/健康管理/服务预约等），并触发后台数据操作 |
| 3 | 情绪感知 | 通过文本关键词 + LLM 分析识别用户情绪状态 |
| 4 | 智能语音回复 | 带情感语气的 TTS 合成（多音色、情绪映射），支持表情展示 |
| 5 | 语音调用应用程序 | 查天气、播放音乐、打开视频 APP、用药提醒等——通过 Agent + 搜索/桌面自动化实现 |
| 6 | 历史对话管理与结构化 | 对话摘要、记忆提取（兴趣爱好/人生经历/情感需求/健康状况等）、向量化存储与检索 |
| 7 | 多机器人个性化 | 支持多个性格迥异的 Bot 并行运行（胖胖/琪琪/团团等），每个 Bot 有独立人设、语气和音色 |
| 8 | 主动对话策略 | 基于用户画像、记忆、情绪状态，主动发起关怀对话或生日/纪念日提醒 |
| 9 | 提醒与定时任务 | 解析自然语言提醒指令，定时推送提醒消息 |
| 10 | 订阅与付费 | 分层订阅体系（免费/基础/高级），支持微信支付/Stripe |
| 11 | 桌面自动化（Task Engine） | 基于截图 + 视觉 LLM + GUI 操作的桌面任务执行引擎 |
| 12 | Web 搜索 | SerpAPI 集成，实时获取天气/新闻等网络信息 |

---

## 功能点与逻辑链路

### 1. 智能语音对话

```
用户发送语音消息
  → [voice_handler] 下载 OGG 文件，使用 ffmpeg 转换为 WAV（16kHz 单声道）
  → [voice_recognition_service] 调用 DashScope ASR 进行语音识别，返回文本 + 初步情绪推断
  → [voice_handler] 将识别文本注入消息处理流程（同文本消息一致）
  → [agent_integration] 统一处理：构建上下文 → 意图分析 → 生成回复
  → 对话文本与音频均保存至 data/voice/{user_id}/{date}/ 及数据库 Conversation 表
```

### 2. 对话意图识别

```
用户消息进入
  → [orchestrator.analyze_intent_unified] LLM 同步执行四项分析：
      ① 意图识别：direct_response（直接回复）/ agents_response（需调用工具/Agent）
      ② Agent 选择：根据描述匹配最合适的 Agent（WebSearch/TaskEngine 等）
      ③ 会话摘要：生成累计对话摘要
      ④ 记忆分析：判断是否包含重要事件需持久化
  → 若为 agents_response → [orchestrator.execute_agents] 并行执行选中 Agent
  → 若为 direct_response → 直接由 LLM 结合对话策略生成回复
  → [conversation_memory_service] 根据分析结果执行后台数据增删改查（保存记忆/创建提醒等）
```

### 3. 情绪感知

```
输入文本/语音
  → [voice_recognition_service._infer_emotion_from_text] 关键词匹配（开心/难过/生气/兴奋/温柔/哭泣等）
  → [dialogue_strategy.yaml] 情绪词典分级（高能量积极/低能量消极等）
  → [ConversationTypeAnalyzer] LLM 综合分析当前情绪状态
  → 情绪标签传递至 TTS 服务和对话策略，影响回复语气和内容风格
```

### 4. 智能语音回复

```
LLM 生成带情感标记的回复文本，如 "（语气：开心、轻快）你好呀！"
  → [emotion_parser.parse_llm_response_with_emotion] 提取情感标签与纯净文本
  → [tts_service] 根据 Bot 配置选择音色（Cherry/Serena/Ethan/Chelsie 等）
  → [qwen_tts_service] WebSocket 连接 DashScope，将情绪映射为语气描述注入 SSML
      情绪映射示例：happy → "（语气：开心、轻快、兴奋，语速稍快，语调上扬）"
  → 生成 PCM 音频 → ffmpeg 转 OGG/Opus → 发送至 Telegram
  → 同时可展示对应表情（通过 emotion_type 字段传递到前端）
```

### 5. 语音调用应用程序

```
用户说 "帮我查看明天天气" / "播放一首音乐"
  → [orchestrator] 意图识别 → agents_response
  → 信息查询类 → [WebSearchAgent] → [serp_api_service] 调用 SerpAPI 搜索并返回结果
  → 桌面操作类 → [TaskEngineAgent] → [task_engine]：
      Plan（规划步骤）→ Execute（截图→视觉分析→点击/输入）→ Verify（验证完成）→ Polish（输出摘要）
  → 提醒类 → [reminder_service] 解析时间 + 内容 → 存入数据库 → [reminder_scheduler] 定时推送
```

### 6. 历史对话管理与结构化

```
每轮对话完成后
  → [conversation_memory_service.analyze_importance] LLM 判断是否包含重要信息
  → 若重要 → [extract_and_save_important_events] 提取结构化标签：
      · event_summary（事件摘要）
      · keywords（关键词）
      · event_type（兴趣爱好/人生经历/近期关注/情感需求/健康状况等）
      · event_date（智能日期解析，支持"下周三""明年3月"等中文相对日期）
      · importance_level（重要程度评分）
  → [embedding_service] 向量化事件摘要 → [vector_store_service] 存入向量数据库
  → 后续对话时 → [retrieve_memories] 通过语义相似度召回相关记忆，注入上下文
  → [summary_service] 定期生成对话摘要，用于中长期记忆压缩
  → [redis_conversation_history] 短期历史缓存，加速读取
```

### 7. 多机器人个性化

```
系统启动
  → [main.py MultiBotLauncher] 从数据库加载活跃 Bot 列表
  → 每个 Bot 加载独立 YAML 配置（src/bot/configs/{bot_name}/config.yaml）：
      · 人设（性格特征/口头禅/价值观/兴趣爱好）
      · 语言风格（语气/emoji 使用/句式长度）
      · AI 参数（模型/温度/最大 token）
      · 音色（Qwen TTS voice_id）
      · 情绪回复模板（针对 sad/angry/happy 等场景的定制回复）
  → 各 Bot 并行运行，独立处理消息，个性化回复
```

### 8. 主动对话策略

```
[proactive_strategy.ProactiveDialogueStrategyAnalyzer]
  → 分析用户画像：兴趣偏好、参与度、情绪状态
  → 分析当前话题：主题、深度、话题流变
  → 选择主动模式：
      · EXPLORE_INTEREST — 初识阶段探索用户兴趣
      · DEEPEN_TOPIC — 深入当前话题
      · SHARE_AND_ASK — 分享观点并征询反馈
      · FIND_COMMON — 表达共同兴趣
      · RECALL_MEMORY — 引用历史记忆（如"还记得半年前你完成了半马吗？"）
      · SUPPORTIVE — 低落时共情陪伴
      · GENTLE_GUIDE — 低参与度时温和引导
  → 生成引导提示注入 LLM system prompt，驱动主动发言
```

### 9. 提醒与定时任务

```
用户说 "5分钟后提醒我吃药"
  → [reminder_service.ReminderParser] 正则匹配 + 中文数字解析
      支持格式："X分钟/小时后提醒我…" / "提醒我X分钟后…"
  → 创建 Reminder 记录（text/remind_at/status=PENDING）
  → [reminder_scheduler] 每 60 秒轮询数据库
  → 到时后通过 Telegram Bot API 发送提醒 → 标记为 SENT
```

### 10. 订阅与付费

```
用户发送 /subscribe → 展示订阅计划（免费/基础¥9.99/高级¥19.99）
  → /pay_basic 或 /pay_premium → [wechat_pay] 创建微信支付订单
  → /check_payment → 查询支付状态 → 成功则 [subscription_service.upgrade_subscription]
  → [subscription_service] 管理每日用量限制：
      免费 100 条/天 → 基础 100 条/天 → 高级 1000 条/天
  → 到期自动降级至免费层
```

### 11. 桌面自动化（Task Engine）

```
用户指令 → [TaskEngineAgent]
  → [task_engine.engine] 主流程：
      ① Plan — LLM 将任务分解为步骤序列
      ② Execute — [executor_router] 路由至合适执行器：
         · ShellExecutor — 执行 Shell 命令
         · LLMExecutor — LLM 推理型任务
         · DesktopExecutor — GUI 自动化：
           screenshot → vision_analyze（视觉 LLM 分析 UI）→ click/type_text/key_press/app_open
         · AgentExecutor — Agent 协作执行
      ③ Verify — [verifier] 截图验证任务是否完成
      ④ Polish — [polisher] 生成用户友好的结果摘要
```

### 12. Web 搜索

```
Agent 发起搜索请求
  → [serp_api_service] Redis 缓存检查（命中则直接返回，TTL 6 小时）
  → [SerpApiKeyManager] API Key 轮转（支持多 Key 负载均衡）
  → 调用 Google/Bing/SerpAPI 获取搜索结果
  → 解析 snippets/answer_box → 返回结构化结果 → 缓存至 Redis
```

---

## 项目目录结构

```
SoulmateBot/
├── main.py                              # 🚀 主入口：多机器人启动器（MultiBotLauncher）
├── browser_server.py                    # 🌐 浏览器服务器（桌面自动化辅助）
├── requirements.txt                     # 📦 Python 依赖清单
├── .env.example                         # ⚙️ 环境变量模板（API Key/数据库/支付等配置）
├── BROWSER_SERVER_README.md             # 📖 浏览器服务器说明文档
├── LICENSE                              # 📜 开源许可证
│
├── config/                              # ═══ 全局配置目录 ═══
│   ├── settings.py                      #   Pydantic 配置类，加载 .env 中所有设置
│   └── dialogue_strategy.yaml           #   对话策略配置（情绪词典/会话类型/策略模板/兴趣分类等）
│
├── src/                                 # ═══ 核心业务代码 ═══
│   ├── __init__.py
│   │
│   ├── agents/                          # --- Agent 智能体系统 ---
│   │   ├── orchestrator.py              #   Agent 编排器：LLM 意图分析 + Agent 选择 + 并行执行
│   │   ├── router.py                    #   Agent 路由器：基于规则的 Agent 匹配与排序
│   │   ├── base_agent.py               #   Agent 基类：定义名称/描述/技能/can_handle 接口
│   │   ├── models.py                    #   数据模型：Message、ChatContext、AgentResponse 等
│   │   ├── skills.py                    #   技能管理：Agent 可用技能的注册与查询
│   │   ├── memory.py                    #   Agent 记忆：对话历史在 Agent 间的传递
│   │   ├── loader.py                    #   Agent 加载器：动态扫描 plugins 目录加载 Agent
│   │   └── plugins/                     #   Agent 插件目录
│   │       └── task_engine_agent.py     #     桌面自动化 Agent（桥接 Task Engine）
│   │
│   ├── ai/                              # --- AI/LLM 网关 ---
│   │   └── conversation.py              #   LLM 调用封装（OpenAI/Claude/vLLM 多供应商）
│   │
│   ├── bot/                             # --- Bot 实例管理 ---
│   │   ├── main.py                      #   单 Bot 启动入口（旧版/调试用）
│   │   ├── platform.py                  #   Bot 平台逻辑
│   │   ├── config_loader.py             #   YAML 配置加载器
│   │   └── configs/                     #   各 Bot 的个性化配置
│   │       ├── pangpang_bot/
│   │       │   └── config.yaml          #     胖胖：幽默毒舌型，男性，Ethan 音色
│   │       ├── qiqi_bot/
│   │       │   └── config.yaml          #     琪琪：温柔共情型，女性，Serena 音色
│   │       └── tuantuan_bot/
│   │           └── config.yaml          #     团团：活泼可爱型，女性，Chelsie 音色
│   │
│   ├── conversation/                    # --- 对话管理引擎 ---
│   │   ├── dialogue_strategy.py         #   对话策略生成（情绪分析/会话类型/回复风格）
│   │   ├── dialogue_strategy_config.py  #   策略配置常量
│   │   ├── proactive_strategy.py        #   主动对话策略（探索兴趣/深入话题/记忆回顾等）
│   │   ├── context_builder.py           #   上下文构建器（短期历史/中期摘要/记忆/策略融合）
│   │   ├── context_manager.py           #   上下文管理器
│   │   ├── session_manager.py           #   会话管理（session 生命周期）
│   │   ├── summary_service.py           #   对话摘要服务（压缩长对话为摘要）
│   │   ├── prompt_template.py           #   Prompt 模板管理（6 种预设人设模板）
│   │   └── README.md                    #   对话模块说明
│   │
│   ├── database/                        # --- 数据库连接 ---
│   │   ├── __init__.py
│   │   ├── connection.py                #   同步数据库连接（SQLAlchemy）
│   │   └── async_connection.py          #   异步数据库连接（AsyncSession）
│   │
│   ├── models/                          # --- 数据模型 ---
│   │   └── database.py                  #   ORM 模型：User/Conversation/UserMemory/Bot/Payment 等
│   │
│   ├── handlers/                        # --- Telegram 消息处理器 ---
│   │   ├── __init__.py
│   │   ├── agent_integration.py         #   核心消息处理：Agent 编排 + 上下文 + 对话策略 + 回复生成
│   │   ├── commands.py                  #   命令处理（/start /help /status /subscribe /pay 等）
│   │   ├── bot_commands.py              #   Bot 管理命令（/list_bots /add_bot /config_bot）
│   │   ├── messages.py                  #   消息路由（按类型分发到对应处理器）
│   │   ├── voice_handler.py             #   语音消息处理（下载/转码/识别/回复）
│   │   ├── chat_member_handler.py       #   群聊成员状态追踪
│   │   └── feedback.py                  #   用户反馈收集与统计
│   │
│   ├── services/                        # --- 业务服务层 ---
│   │   ├── __init__.py
│   │   ├── voice_recognition_service.py #   语音识别服务（DashScope ASR + 情绪推断）
│   │   ├── tts_service.py               #   TTS 总服务（多供应商适配：OpenAI/Qwen/iFlytek）
│   │   ├── qwen_tts_service.py          #   Qwen TTS 实现（WebSocket + 情绪语气映射）
│   │   ├── voice_preference_service.py  #   用户语音偏好管理（Redis 存储）
│   │   ├── conversation_memory_service.py # 记忆提取与存储（LLM 分析 + 日期解析 + 向量化）
│   │   ├── embedding_service.py         #   向量嵌入服务（DashScope/OpenAI，支持缓存）
│   │   ├── vector_store_service.py      #   向量数据库服务（语义相似度检索）
│   │   ├── serp_api_service.py          #   Web 搜索服务（SerpAPI，支持缓存 + Key 轮转）
│   │   ├── reminder_service.py          #   提醒服务（自然语言解析 + CRUD）
│   │   ├── reminder_scheduler.py        #   提醒调度器（异步轮询 + Telegram 推送）
│   │   ├── redis_conversation_history.py #  Redis 对话历史缓存
│   │   ├── bot_manager.py               #   Bot 生命周期管理
│   │   ├── channel_manager.py           #   频道路由管理
│   │   ├── async_channel_manager.py     #   异步频道管理
│   │   ├── feedback_service.py          #   反馈管理服务
│   │   ├── image_service.py             #   图片处理服务
│   │   └── message_router.py            #   消息类型路由
│   │
│   ├── subscription/                    # --- 订阅系统 ---
│   │   ├── __init__.py
│   │   ├── service.py                   #   订阅管理（用量限制/升降级/到期处理）
│   │   └── async_service.py             #   异步订阅服务
│   │
│   ├── payment/                         # --- 支付系统 ---
│   │   ├── __init__.py
│   │   ├── wechat_pay.py                #   微信支付集成
│   │   └── mock_gateway.py              #   模拟支付网关（测试用）
│   │
│   └── utils/                           # --- 工具函数 ---
│       ├── __init__.py
│       ├── emotion_parser.py            #   情绪解析（从 LLM 回复提取情感标签与纯净文本）
│       ├── history_filter.py            #   历史过滤（清理 URL/简短消息等噪声）
│       ├── voice_helper.py              #   语音辅助工具
│       └── config_helper.py             #   配置辅助工具
│
├── task_engine/                         # ═══ 桌面自动化任务引擎 ═══
│   ├── __init__.py
│   ├── engine.py                        #   主引擎：Plan → Execute → Verify → Polish
│   ├── executor_router.py               #   执行器路由（Shell/LLM/Desktop/Agent）
│   ├── verifier.py                      #   任务验证器（截图对比验证完成度）
│   ├── polisher.py                      #   结果润色器（生成用户友好摘要）
│   ├── models.py                        #   任务数据模型
│   │
│   └── executors/                       #   执行器集合
│       ├── __init__.py
│       ├── base.py                      #     执行器基类接口
│       ├── shell_executor.py            #     Shell 命令执行器
│       ├── llm_executor.py              #     LLM 推理执行器
│       │
│       ├── desktop_executor/            #     桌面 GUI 自动化执行器
│       │   ├── executor.py              #       主执行逻辑（截图→分析→操作循环）
│       │   ├── guard.py                 #       安全守卫（危险操作拦截）
│       │   ├── platform.py              #       平台检测（macOS/Linux/Windows）
│       │   └── tools/                   #       GUI 操作工具集
│       │       ├── __init__.py
│       │       ├── screenshot.py        #         屏幕截图
│       │       ├── click.py             #         鼠标点击
│       │       ├── key_press.py         #         键盘按键
│       │       ├── type_text.py         #         文本输入
│       │       ├── app_open.py          #         应用启动
│       │       ├── shell_run.py         #         Shell 命令执行
│       │       ├── vision_analyze.py    #         视觉 LLM 分析截图
│       │       └── page_analyze.py      #         页面内容分析
│       │
│       └── agent_executor/              #     Agent 协作执行器
│           ├── __init__.py
│           ├── executor.py              #       异步 Agent 执行逻辑
│           └── tools.py                 #       Agent 工具/插件注册
│
├── scripts/                             # ═══ 脚本工具 ═══
│   ├── db_manager.py                    #   数据库管理 CLI 入口
│   ├── bot_template.py                  #   Bot 配置模板生成器
│   └── db_manager/                      #   数据库管理子模块
│       ├── __init__.py
│       ├── base.py                      #     基础 CRUD 操作
│       ├── user_crud.py                 #     用户管理
│       ├── conversation_crud.py         #     对话记录管理
│       ├── bot_crud.py                  #     Bot 管理
│       ├── channel_crud.py              #     频道管理
│       ├── token_manager.py             #     Token 操作
│       └── cli.py                       #     CLI 命令行界面
│
├── tests/                               # ═══ 测试套件 ═══
│   ├── conftest.py                      #   Pytest 公共 fixtures
│   ├── test_agent_*.py                  #   Agent 系统测试
│   ├── test_llm_*.py                    #   LLM 集成测试
│   ├── test_task_engine.py              #   Task Engine 测试
│   ├── test_conversation_*.py           #   对话逻辑测试
│   ├── test_services_*.py              #   服务层测试
│   └── ...                              #   更多测试文件（50+）
│
├── notebooks/                           # ═══ Jupyter 笔记本 ═══
│   ├── README.md
│   └── data/
│       └── voice_preferences.json       #   语音偏好测试数据
│
└── data/                                # ═══ 数据目录 ═══
    └── uploads/                         #   用户上传文件存储
```

---

## 示例：用户输入"帮我查看明天天气"的完整流程

以下逐步展示当用户在 Telegram 中发送 **"帮我查看明天天气"** 时，整个工程的处理流程：

### Step 1：消息接收

```
Telegram 服务器 → python-telegram-bot 轮询接收
  → main.py 中注册的 MessageHandler 触发
  → 路由到 src/handlers/agent_integration.py :: handle_message_with_agents()
```

- 提取 `user_id`、`chat_id`、`message_text = "帮我查看明天天气"`
- 检查用户是否存在，不存在则自动创建（免费层）
- 检查每日用量限额（免费 100 条/天）

### Step 2：加载上下文

```python
# src/handlers/agent_integration.py
# 1. 从 Redis 加载近期对话历史
history = redis_conversation_history.get_history(user_id, bot_id)

# 2. 从向量数据库检索相关记忆
memories = conversation_memory_service.retrieve_memories("明天天气", user_id)

# 3. 构建统一上下文
context = UnifiedContextBuilder.build(
    short_term=history[-5:],        # 最近 5 轮完整对话
    mid_term=summary_of_older,       # 更早对话的摘要
    memories=memories,               # 相关记忆片段
    bot_config=pangpang_config       # Bot 人设配置
)
```

### Step 3：对话策略生成

```
[dialogue_strategy.py]
  → ConversationTypeAnalyzer 分析：
      · 会话类型 = INFO_REQUEST（信息查询）
      · 情绪状态 = neutral（中性）
      · 对话阶段 = OPENING / MIDWAY（取决于历史轮次）
  → 生成策略指导："保持简洁、信息导向的回复风格，提供准确信息"
```

### Step 4：LLM 统一意图分析

```
[orchestrator.py :: analyze_intent_unified()]
  → 向 LLM（GPT-4o）发送包含以下内容的请求：
      · System Prompt（Bot 人设 + 策略指导）
      · 对话历史
      · 当前消息："帮我查看明天天气"
      · 可用 Agent 列表及其描述

  → LLM 返回结构化分析结果：
  {
      "intent": "agents_response",          // 需要调用外部工具
      "selected_agents": ["WebSearchAgent"], // 选择搜索 Agent
      "reasoning": "用户需要实时天气信息，需要联网搜索",
      "task_input": "查询明天的天气预报",
      "memory_analysis": {
          "is_important": false              // 天气查询不需要持久化记忆
      },
      "conversation_summary": "用户询问明天天气情况"
  }
```

### Step 5：Agent 执行——Web 搜索

```
[orchestrator.py :: execute_agents()]
  → 调用 WebSearchAgent
  → [serp_api_service.py]：
      ① Redis 缓存检查 → 未命中
      ② SerpApiKeyManager 获取下一个可用 API Key
      ③ 发送搜索请求：query = "明天天气预报"
      ④ 解析返回结果：
         - answer_box: "明天 晴转多云，气温 15°C~25°C，东南风 2-3 级"
         - snippets: ["中国天气网：明日天气...", ...]
      ⑤ 缓存结果至 Redis（TTL=6h）
      ⑥ 返回搜索结果摘要
```

### Step 6：生成最终回复

```
[orchestrator.py]
  → 将搜索结果 + 对话历史 + Bot 人设 + 对话策略 融合
  → 再次调用 LLM 生成自然语言回复

  → LLM 输出（以胖胖 Bot 为例）：
    "（语气：轻松、随意）明天天气还不错嘛～晴转多云，15 到 25 度，
     东南风 2-3 级。出门不用带伞，不过早晚温差有点大，别感冒了哦 😎"
```

### Step 7：情绪解析与语音合成（若开启语音）

```
[emotion_parser.py]
  → 提取：emotion_type = "轻松", text = "明天天气还不错嘛～..."

[tts_service.py]（如果用户开启了语音回复）
  → 选择 Ethan 音色（胖胖 Bot 配置）
  → [qwen_tts_service.py] 注入情绪语气：
    "（语气：轻松、随意，语速适中）明天天气还不错嘛～..."
  → WebSocket 连接 DashScope → 生成 PCM 音频 → 转 OGG/Opus
```

### Step 8：发送回复与持久化

```
→ Telegram Bot API 发送文本消息（+ 语音消息，如果开启）
→ 保存到数据库 Conversation 表（role=assistant, content=回复内容）
→ 更新 Redis 对话历史缓存
→ 更新当日用量计数（UsageRecord +1）
→ 记忆分析结果 is_important=false → 不保存为长期记忆
```

### 完整流程图

```
┌─────────────┐
│  用户发送     │  "帮我查看明天天气"
│  Telegram    │
└──────┬──────┘
       │
       ▼
┌──────────────────┐     ┌─────────────────────┐
│ agent_integration │────▶│  Redis 对话历史       │
│ 消息处理入口       │     │  向量数据库记忆检索    │
└──────┬───────────┘     └─────────────────────┘
       │
       ▼
┌──────────────────┐     ┌─────────────────────┐
│ dialogue_strategy │────▶│  情绪分析             │
│ 对话策略生成       │     │  会话类型 = INFO_REQ  │
└──────┬───────────┘     └─────────────────────┘
       │
       ▼
┌──────────────────┐     ┌─────────────────────┐
│  orchestrator     │────▶│  LLM 意图分析         │
│  Agent 编排器     │     │  → agents_response   │
└──────┬───────────┘     │  → WebSearchAgent    │
       │                 └─────────────────────┘
       ▼
┌──────────────────┐     ┌─────────────────────┐
│ WebSearchAgent   │────▶│  SerpAPI 搜索         │
│ 执行搜索          │     │  "明天天气预报"       │
└──────┬───────────┘     └─────────────────────┘
       │
       ▼
┌──────────────────┐     ┌─────────────────────┐
│  LLM 回复生成     │────▶│  Bot 人设 + 策略融合   │
│  自然语言输出      │     │  带情感标记的文本      │
└──────┬───────────┘     └─────────────────────┘
       │
       ▼
┌──────────────────┐     ┌─────────────────────┐
│ emotion_parser   │────▶│  提取情感 + 纯净文本   │
│ tts_service      │     │  语音合成（可选）      │
└──────┬───────────┘     └─────────────────────┘
       │
       ▼
┌──────────────────┐     ┌─────────────────────┐
│  发送回复         │────▶│  数据库持久化          │
│  Telegram API    │     │  Redis 缓存更新       │
└─────────────────┘     │  用量计数 +1          │
                         └─────────────────────┘
```

---

## 快速开始

### 环境要求

- Python 3.10+
- PostgreSQL（数据库）
- Redis（缓存）
- ffmpeg（音频转码）

### 安装

```bash
# 克隆项目
git clone https://github.com/aappaappoo/SoulmateBot.git
cd SoulmateBot

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Key、数据库地址等配置
```

### 配置

编辑 `.env` 文件，填入以下关键配置：

```env
# Telegram Bot Token
TELEGRAM_BOT_TOKEN=your_bot_token

# LLM 供应商
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o

# 数据库
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/soulmate

# Redis
REDIS_URL=redis://localhost:6379/0

# TTS（语音合成）
DASHSCOPE_API_KEY=your_dashscope_key

# Web 搜索
SERP_API_KEY=your_serpapi_key
```

### 启动

```bash
# 启动多机器人
python main.py

# 或启动单个 Bot（调试用）
python -m src.bot.main
```

### 数据库管理

```bash
# 使用数据库管理 CLI
python scripts/db_manager.py
```
