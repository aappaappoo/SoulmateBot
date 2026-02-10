## 📊 完整逻辑链路图

````markdown
handle_message_with_agents()                          # 入口 → agent_integration.py:108
│
│  ══════════════════════════════════════════════════════════════
│  ═══ 阶段零：消息接收 & Bot 选择 ═══
│  ══════════════════════════════════════════════════════════════
│
├── 提取 chat_type / chat_id / user_id / message_text
├── [私聊] → 直接查 DB 获取当前 bot
│       └── select(Bot).where(Bot.bot_username == current_bot_username)
├── [群聊/频道] → MessageRouter 路由选择
│       ├── channel_service.get_or_create_channel()
│       ├── channel_service.get_channel_bots()
│       ├── MessageRouter.should_respond_in_channel()
│       ├── MessageRouter.extract_mention()
│       └── MessageRouter.select_bot() → selected_bot
│
├── 加载 system_prompt
│       ├── 优先：context.bot_data["bot_config"].get_system_prompt()  (YAML 配置)
│       └── 回退：selected_bot.system_prompt                          (数据库)
│
│  ══════════════════════════════════════════════════════════════
│  ═══ 阶段一：用户验证 & 前置拦截 ═══
│  ══════════════════════════════════════════════════════════════
│
├── AsyncSubscriptionService
│       ├── get_user_by_telegram_id()              → db_user
│       ├── update_user_info()                      # 更新用户资料
│       ├── check_subscription_status() ──┐
│       │       └── 过期 → 回复提示 & return        │
│       └── check_usage_limit() ──────────┘
│               └── 超限 → 回复提示 & return
│
├── [提醒拦截] ReminderService
│       └── parse_and_create_reminder()
│               ├── 匹配到提醒 → format_reminder_confirmation() → reply & return
│               └── 未匹配    → 继续往下执行
│
│  ══════════════════════════════════════════════════════════════
│  ═══ 阶段二：获取对话历史（从 DB） ═══
│  ══════════════════════════════════════════════════════════════
│
├── select(Conversation).where(user_id & session_id)
│       .order_by(timestamp.desc()).limit(50)
│       │
│       ├── → history_messages: List[AgentMessage]         # 给 AgentOrchestrator 用
│       │       └── user_id="user" / "assistant"
│       │
│       └── → conversation_history_for_builder: List[Dict] # 给 UnifiedContextBuilder 用
│               └── {"role": "user"/"assistant", "content": "..."}
│
│  ══════════════════════════════════════════════════════════════
│  ═══ 阶段三：长期记忆检索（RAG） ═══
│  ══════════════════════════════════════════════════════════════
│
├── get_conversation_memory_service(db, llm_provider) → memory_service
│
└── memory_service.retrieve_memories()
        ├── user_id, bot_id, current_message, skip_llm_analysis=True
        │
        ├── [优先] _retrieve_by_vector_similarity()
        │       ├── embedding_service.embed_text(current_message)  → query_embedding
        │       ├── select(UserMemory) WHERE user_id & bot_id
        │       ├── 逐条计算 cosine_similarity(query_embedding, memory.embedding)
        │       ├── 过滤 similarity >= similarity_threshold (0.5)
        │       └── 按相似度降序排序 → top N memories
        │
        ├── [回退] _retrieve_by_metadata()
        │       ├── 基于 event_types 过滤
        │       └── 按 importance + created_at 排序
        │
        └── → user_memories: List[Dict]
                └── {"event_summary", "event_date", "event_type", "keywords"}

│  ══════════════════════════════════════════════════════════════
│  ═══ 阶段四：对话策略生成 ═══
│  ══════════════════════════════════════════════════════════════
│
├── bot_values = get_bot_values(context)               # 从 YAML config 中读取
│
└── enhance_prompt_with_strategy()                     # dialogue_strategy.py 入口
        │
        └── DialogueStrategyInjector.inject_strategy()
                │
                ├── ══ 1. 统一分析层（只做一次，产出共享上下文） ══
                │
                ├── 1a. DialoguePhaseAnalyzer.analyze_phase(conversation_history)
                │       └── 统计 user 消息轮数 + 平均回复长度 → 判断对话阶段
                │           ├── ≤2 轮  → OPENING    (开场)
                │           ├── ≤5 轮  → LISTENING   (倾听)
                │           ├── ≤8 轮  → DEEPENING   (深入)
                │           └── >8 轮  → SUPPORTING   (支持引导)
                │           └── → (phase, {user_turn_count, avg_reply_length})
                │
                ├── 1b. DialoguePhaseAnalyzer.analyze_emotion(current_message)
                │       └── 关键词匹配 → (emotion_type, emotion_intensity)
                │           ├── emotion_type: "positive" / "negative" / "neutral"
                │           └── emotion_intensity: "low" / "medium" / "high"
                │
                ├── 1c. ConversationTypeAnalyzer.analyze_type(current_message, history)
                │       └── 关键词分类 → ConversationType
                │           ├── EMOTIONAL_VENT       # 情绪倾诉 → 暂不反驳
                │           ├── OPINION_DISCUSSION   # 观点讨论 → 可表达立场
                │           ├── INFO_REQUEST          # 信息需求 → 可触发搜索
                │           ├── DECISION_CONSULTING   # 决策咨询 → 分析+建议
                │           └── CASUAL_CHAT           # 日常闲聊 → 轻松互动
                │
                ├── 1d. ConversationTypeAnalyzer.analyze_interests(history, current_message)
                │       └── 兴趣关键词匹配 → {interests, potential_interests}
                │           ├── interests: 已识别的用户兴趣列表
                │           └── potential_interests: 可探索的兴趣方向
                │
                ├── 1e. [如果有 bot_values & conversation_type == OPINION_DISCUSSION]
                │       └── StanceAnalyzer.analyze_stance(message, bot_values)
                │               └── → StanceAnalysis (立场分析结果)
                │
                ├── ══ 2. 生成策略层（基于分析结果生成应对策略） ══
                │
                ├── 2a. 根据对话阶段给出回应策略
                │       └── suggest_response_type(phase, emotion, intensity, history)
                │           └── STRATEGY_TEMPLATES[response_type] → phase_strategy 文本
                │
                ├── 2b. 根据用户情绪给出应对策略
                │       └── 已融合在 response_type 中（负面情绪自动选 COMFORT/VALIDATION）
                │
                ├── 2c. 根据用户兴趣点给出应对策略
                │       └── _build_interest_guidance(interests, potential_interests)
                │               └── → interest_guidance 文本
                │
                ├── 2d. 根据冲突程度给出机器人应对策略
                │       └── _build_stance_guidance(stance_analysis)
                │               └── → stance_guidance 文本
                │
                ├── ══ 主动策略层（基于统一分析结果生成主动互动建议） ══
                │
                ├── _generate_proactive_guidance(history, memories, interest_analysis, response_type)
                │       ├── 构建用户画像并复用兴趣分析结果
                │       ├── analyze_topic() → topic_analysis
                │       ├── generate_proactive_strategy() → proactive_action
                │       └── format_proactive_guidance() → proactive_guidance 文本
                │
                ├── 去重逻辑
                │       └── 如果回应策略已选 PROACTIVE_INQUIRY 且主动策略为 EXPLORE_INTEREST
                │           → 跳过主动策略中的通用追问模板，避免重复输出
                │
                └── ══ 合并输出 ══
                        original_prompt + phase_strategy + interest_guidance + stance_guidance + proactive_guidance
                        │
                        └── → enhanced_with_strategy (完整增强 prompt)

│
│  ── 提取策略文本（去掉原 system_prompt 前缀）──
│
├── dialogue_strategy_text = enhanced_with_strategy[len(base_system_prompt):]
│       └── 仅保留策略增量部分
│
│  ══════════════════════════════════════════════════════════════
│  ═══ 阶段五：读取上一轮 LLM 摘要（内存缓存） ═══
│  ══════════════════════════════════════════════════════════════
│
├── summary_key = f"llm_summary_{chat_id}_{db_user.id}"
└── previous_summary = context.bot_data.get(summary_key)
        └── Dict: {summary_text, key_elements, topics, user_state}

│  ══════════════════════════════════════════════════════════════
│  ═══ 阶段六：统一上下文构建 ═══
│  ══════════════════════════════════════════════════════════════
│
└── UnifiedContextBuilder(config=ContextConfig(...))
        │
        └── build_context(
                bot_system_prompt,
                conversation_history,
                current_message,
                user_memories,
                dialogue_strategy = dialogue_strategy_text,
                llm_generated_summary = previous_summary
            )
            │
            │  ── Step 0：历史过滤 ──
            ├── HistoryFilter.filter_history(conversation_history)
            │       └── _should_filter(content, role)
            │           ├── 空内容       → 过滤
            │           ├── 简单语气词    → 过滤 (r'^哦[。！]?$')
            │           ├── URL 占比 ≥ 70% → 过滤 → placeholder: "[用户分享了N个链接]"
            │           ├── 长度 < 5 (user) → 过滤
            │           └── 其他           → 保留 (清理内联URL → "[链接]")
            │       └── [enable_disk_storage]
            │               └── _store_filtered_content() → JSON 文件
            │
            │  ── Step 1：分割对话历史 ──
            ├── _split_history(filtered_history)
            │       ├── 统计 user 消息数
            │       ├── short_term = 最近 5 轮 user 消息及之后的所有消息
            │       └── mid_term   = short_term 之前的, 最多 (20-5)=15 轮
            │
            │  ── Step 2：生成中期摘要 ──
            ├── ConversationSummaryService.summarize_conversations(mid_term)
            │       ├── [use_llm=True & llm_provider] → _summarize_with_llm()
            │       │       └── 调用 LLM → JSON {summary_text, key_topics, emotion_trajectory, user_needs}
            │       └── [默认/回退]       → _summarize_with_rules()
            │               ├── _extract_topics()              # 关键词匹配 → 话题列表
            │               ├── _analyze_emotion_trajectory()  # 情绪关键词 → "整体积极/消极/波动/平稳"
            │               ├── _identify_user_needs()         # 需求关键词 → ["倾诉","建议",...]
            │               └── _generate_rule_based_summary() # 拼装文本
            │
            │  ── Step 3：格式化长期记忆 ──
            ├── _format_memories(user_memories)
            │       └── 最多 max_memories(8) 条
            │           └── "- 用户在{date}时间表示{summary}" 或 "- {summary}"
            │
            │  ── Step 4：生成主动策略（ProactiveDialogueStrategy）──
            ├── _generate_proactive_guidance(conversation_history, user_memories, user_profile, response_type)
            │       │
            │       ├── 复用统一分析层构建的 user_profile（不再重复构建）
            │       │
            │       ├── ProactiveDialogueStrategyAnalyzer.analyze_topic()
            │       │       ├── _identify_topic_from_messages() # 最后一条 user 消息的话题（后备方法，优先使用统一分析层）
            │       │       ├── _calculate_topic_depth()     # 连续同话题轮数
            │       │       ├── _identify_topics_to_explore()# 未深入的兴趣
            │       │       └── → TopicAnalysis
            │       │
            │       ├── ProactiveDialogueStrategyAnalyzer.generate_proactive_strategy()
            │       │       ├── _determine_stage(user_profile)
            │       │       │       ├── depth ≤1 → OPENING
            │       │       │       ├── depth ≤2 → EXPLORING
            │       │       │       ├── depth ≤3 → DEEPENING
            │       │       │       └── depth ≥4 → ESTABLISHED
            │       │       │
            │       │       ├── _select_proactive_mode(stage, profile, topic, memories)
            │       │       │       ├── 情绪 negative        → SUPPORTIVE
            │       │       │       ├── 参与度 LOW            → GENTLE_GUIDE
            │       │       │       ├── OPENING               → EXPLORE_INTEREST
            │       │       │       ├── EXPLORING + 有话题    → DEEPEN_TOPIC
            │       │       │       ├── EXPLORING + 无话题    → EXPLORE_INTEREST
            │       │       │       ├── DEEPENING + 共同兴趣  → FIND_COMMON
            │       │       │       ├── DEEPENING + HIGH 参与 → SHOW_CURIOSITY
            │       │       │       ├── DEEPENING + 其他      → DEEPEN_TOPIC
            │       │       │       ├── ESTABLISHED + 有记忆  → RECALL_MEMORY
            │       │       │       ├── ESTABLISHED + 有话题  → SHARE_AND_ASK
            │       │       │       └── ESTABLISHED + 其他    → FIND_COMMON
            │       │       │
            │       │       └── _build_proactive_action(mode, ...) → ProactiveAction
            │       │
            │       ├── 去重：如果 response_type == PROACTIVE_INQUIRY 且 mode == EXPLORE_INTEREST
            │       │       └── 跳过主动策略输出，避免与回应策略重复
            │       │
            │       └── format_proactive_guidance(action)
            │               └── → "【当前对话情境】+ 【主动互动建议】+ 【可以这样回复】"
            │
            │  ── Step 5：构建增强 System Prompt ──
            └── _build_enhanced_system_prompt()
                    │
                    ├── [组件 1] bot_system_prompt（原始人设）
                    │
                    ├── [组件 2] ═══ 对话相关记忆 ═══
                    │       ├── 【历史重要记忆】    ← _format_memories() 结果
                    │       ├── 【中期摘要记忆】    ← LLM 摘要 (previous_summary) 或 规则摘要 (mid_term_summary)
                    │       └── 【近期对话记录】    ← _format_history_for_system_prompt(short_term)
                    │                                   └── <history>User:... / Assistant:...</history>
                    │
                    ├── [组件 3] ═══ 对话策略管理 ═══
                    │       ├── 【当前对话情境】    ← proactive_guidance (主动策略)
                    │       └── 【当前对话策略】    ← dialogue_strategy (对话策略文本)
                    │
                    └── [组件 4] ═══ 强制输出格式 ═══
                            └── JSON 格式指令
                                {intent, agents, direct_reply, emotion, memory, conversation_summary}

│  ══════════════════════════════════════════════════════════════
│  ═══ 阶段七：Agent 编排 & LLM 调用 ═══
│  ══════════════════════════════════════════════════════════════
│
├── AgentMessage(content, user_id, chat_id, metadata)
├── ChatContext(chat_id, conversation_history=history_messages, system_prompt=enhanced_system_prompt)
│
├── AgentOrchestrator.process(agent_message, chat_context)
│       └── → OrchestrationResult
│               ├── intent_type: DIRECT_RESPONSE / SINGLE_AGENT / MULTI_AGENT / SKILL_SELECTION
│               ├── final_response
│               ├── agent_responses
│               ├── skill_options
│               ├── memory_analysis        ← 统一模式从 LLM JSON 中直接提取
│               └── metadata
│                       └── conversation_summary ← LLM 返回的摘要
│
│  ══════════════════════════════════════════════════════════════
│  ═══ 阶段八：结果处理 & 持久化 ═══
│  ══════════════════════════════════════════════════════════════
│
├── [回写 LLM 摘要到内存]
│       └── context.bot_data[summary_key] = result.metadata["conversation_summary"]
│               └── 自动清理：保留最近 100 个 summary_key
│
├── [SKILL_SELECTION] → build_skill_keyboard() → reply_text(keyboard)
│
├── [其他意图] → send_voice_or_text_reply()
│       └── 根据 bot 语音设置决定 voice / text
│
├── [保存对话到 DB]
│       ├── user_conv  = Conversation(is_user_message=True, message_type="text")
│       └── bot_conv   = Conversation(is_user_message=False, message_type=message_type)
│       └── subscription_service.record_usage()
│       └── db.commit()
│
└── [保存记忆]
        ├── [统一模式] result.memory_analysis is not None
        │       ├── is_important = True & importance >= medium
        │       │       ├── 解析日期：event_date → DateParser → parse_from_message
        │       │       ├── 生成 Embedding：memory_service.embedding_service.embed_text()
        │       │       └── db.add(UserMemory(...))
        │       └── is_important = False → skip
        │
        └── [回退模式] result.memory_analysis is None & memory_service
                └── memory_service.extract_and_save_important_events()
                        ├── analyze_importance() → LLM 分析 or 规则分析
                        ├── _parse_event_date()
                        ├── embedding_service.embed_text()
                        └── db.add(UserMemory(...))
```
````

---

## 📋 对话管理决策逻辑表

### 表 1：对话阶段判定（DialoguePhaseAnalyzer + ProactiveDialogueStrategyAnalyzer）


| 判定维度              | 判定来源       | 用于 dialogue_strategy     | 用于 proactive_strategy                      |
| --------------------- | -------------- | -------------------------- | -------------------------------------------- |
| **OPENING / 开场**    | user 轮数 ≤ 2 | `DialoguePhase.OPENING`    | `ConversationStage.OPENING` (depth ≤ 1)     |
| **LISTENING / 探索**  | user 轮数 3~5  | `DialoguePhase.LISTENING`  | `ConversationStage.EXPLORING` (depth ≤ 2)   |
| **DEEPENING / 深入**  | user 轮数 6~8  | `DialoguePhase.DEEPENING`  | `ConversationStage.DEEPENING` (depth ≤ 3)   |
| **SUPPORTING / 支持** | user 轮数 > 8  | `DialoguePhase.SUPPORTING` | `ConversationStage.ESTABLISHED` (depth ≥ 4) |

> ⚠️ **注意**：两个子系统各自维护了一套阶段判定逻辑，`dialogue_strategy` 按绝对轮数，`proactive_strategy` 按 relationship_depth（也是基于轮数映射的 1~5 级），两者的轮次阈值略有差异。已通过统一分析层合并用户画像构建，避免重复分析。

---

### 表 2：情绪分析与影响


| 分析环节                                                   | 分析范围            | 正面关键词                   | 负面关键词                     | 输出格式                                       | 影响域                                             |
| ---------------------------------------------------------- | ------------------- | ---------------------------- | ------------------------------ | ---------------------------------------------- | -------------------------------------------------- |
| `DialoguePhaseAnalyzer.analyze_emotion()`                  | 仅当前消息          | 开心/高兴/太好了/哈哈…      | 难过/痛苦/焦虑/好累…          | `(type, intensity)`                            | →`suggest_response_type()` → strategy_guidance   |
| `ProactiveDialogueStrategy._analyze_emotional_state()`     | 最近 3 条 user 消息 | 开心/高兴/喜欢/爱/棒/好/不错 | 难过/伤心/焦虑/累/烦/失落/孤独 | `str`: positive/negative/transitioning/neutral | →`_select_proactive_mode()` → proactive_guidance |
| `ConversationSummaryService._analyze_emotion_trajectory()` | 中期全部 user 消息  | 同上                         | 同上                           | `str`: 整体积极/消极/波动/平稳                 | → mid_term_summary → 嵌入 system_prompt          |

---

### 表 3：对话类型判定（ConversationTypeAnalyzer）


| 对话类型              | 触发信号词示例                    | 策略含义                   | 是否触发立场分析     |
| --------------------- | --------------------------------- | -------------------------- | -------------------- |
| `EMOTIONAL_VENT`      | 好累/烦死了/想哭/难过/受不了      | 暂不反驳，以倾听和共情为主 | ❌                   |
| `OPINION_DISCUSSION`  | 我觉得/你怎么看/有没有觉得/不同意 | 可以表达自己的立场和观点   | ✅ → StanceAnalyzer |
| `INFO_REQUEST`        | 怎么/如何/什么是/帮我查/告诉我    | 可触发搜索技能             | ❌                   |
| `DECISION_CONSULTING` | 怎么选/哪个好/纠结/犹豫/要不要    | 提供分析 + 给出建议        | ❌                   |
| `CASUAL_CHAT`         | (不匹配以上任何类型)              | 轻松互动，保持自然         | ❌                   |

---

### 表 4：主动策略模式选择决策（ProactiveDialogueStrategyAnalyzer）


| 优先级  | 判定条件                                  | 选择模式           | 策略说明                     |
| ------- | ----------------------------------------- | ------------------ | ---------------------------- |
| **P0**  | `emotional_state == "negative"`           | `SUPPORTIVE`       | 倾听支持，少主动，温暖不施压 |
| **P1**  | `engagement == LOW`                       | `GENTLE_GUIDE`     | 简短回应，不追问，给空间     |
| **P2**  | `stage == OPENING`                        | `EXPLORE_INTEREST` | 主动问兴趣爱好               |
| **P3**  | `stage == EXPLORING` + 有话题 + depth < 3 | `DEEPEN_TOPIC`     | 追问话题细节                 |
| **P4**  | `stage == EXPLORING` + 无话题             | `EXPLORE_INTEREST` | 继续探索兴趣                 |
| **P5**  | `stage == DEEPENING` + 有共同兴趣         | `FIND_COMMON`      | 表达共鸣，建立连接           |
| **P6**  | `stage == DEEPENING` + 高参与度           | `SHOW_CURIOSITY`   | 表达好奇，鼓励继续           |
| **P7**  | `stage == DEEPENING` + 其他               | `DEEPEN_TOPIC`     | 深入当前话题                 |
| **P8**  | `stage == ESTABLISHED` + 有记忆           | `RECALL_MEMORY`    | 回忆之前提到的事并追问       |
| **P9**  | `stage == ESTABLISHED` + 有当前话题       | `SHARE_AND_ASK`    | 分享观点并提问               |
| **P10** | `stage == ESTABLISHED` + 其他             | `FIND_COMMON`      | 寻找共同点                   |

---

### 表 5：用户参与度判定


| 指标         | 计算方式                                  | HIGH      | MEDIUM     | LOW       |
| ------------ | ----------------------------------------- | --------- | ---------- | --------- |
| 消息平均长度 | 最近 6 条中 user 消息的 avg(len(content)) | > 50 字符 | 20~50 字符 | < 20 字符 |

---

### 表 6：历史过滤决策（HistoryFilter）


| 过滤条件        | 检测规则                              | 过滤行为                 | 占位符                |
| --------------- | ------------------------------------- | ------------------------ | --------------------- |
| 空内容          | `content.strip()` 为空                | 完全移除                 | 无                    |
| 简单语气词      | 匹配`^哦[。！]?$` 等正则 + 长度 ≤ 20 | 完全移除                 | 无                    |
| URL 主导        | URL 字符占比 ≥ 70%                   | 替换为占位符             | `[用户分享了N个链接]` |
| 过短内容        | 长度 < 5 且 role == "user"            | 完全移除                 | 无                    |
| 含 URL 但非主导 | URL 占比 < 70%                        | 保留，URL 替换为`[链接]` | 无                    |

---

### 表 7：记忆存储决策


| 模式                 | 触发条件                                                 | 重要性判定                                           | 日期解析                                                                      | Embedding                 |
| -------------------- | -------------------------------------------------------- | ---------------------------------------------------- | ----------------------------------------------------------------------------- | ------------------------- |
| **统一模式（优先）** | `result.memory_analysis is not None`                     | LLM JSON 直接返回`is_important` + `importance_level` | ① event_date → ② raw_date_expression + DateParser → ③ parse_from_message | embed_text(event_summary) |
| **回退模式**         | `result.memory_analysis is None` & `memory_service` 存在 | `analyze_importance()` → LLM 分析或规则关键词匹配   | `_parse_event_date()` 三级回退                                                | embed_text(event_summary) |
| **跳过**             | 统一模式判定`is_important=False`                         | —                                                   | —                                                                            | —                        |
| **存储阈值**         | `importance_level` ≥ `"medium"`                         | low=0, medium=1, high=2, critical=3                  | —                                                                            | —                        |

---

### 表 8：最终 System Prompt 结构


| 区块顺序 | 区块标题                     | 内容来源                                        | 是否必选       |
| -------- | ---------------------------- | ----------------------------------------------- | -------------- |
| 1        | *(原始人设)*                 | `bot_system_prompt` (YAML / DB)                 | ✅             |
| 2        | `═══ 对话相关记忆 ═══` | —                                              | 有内容时才添加 |
| 2.1      | 【历史重要记忆】             | `_format_memories(user_memories)`               | 有记忆时       |
| 2.2      | 【中期摘要记忆】             | `llm_generated_summary` 或 `mid_term_summary`   | 有摘要时       |
| 2.3      | 【近期对话记录】             | `_format_history_for_system_prompt(short_term)` | 有短期历史时   |
| 3        | `═══ 对话策略管理 ═══` | —                                              | 有内容时才添加 |
| 3.1      | 【当前对话情境】             | `proactive_guidance` (主动策略)                 | 启用且有结果时 |
| 3.2      | 【当前对话策略】             | `dialogue_strategy_text` (对话策略)             | 有历史时       |
| 4        | `═══ 强制输出格式 ═══` | `_get_json_format_instruction()`                | ✅             |

---

### 表 9：数据在各组件间的流转


| 数据                          | 产生位置                                               | 消费位置                                           | 存储介质                    |
| ----------------------------- | ------------------------------------------------------ | -------------------------------------------------- | --------------------------- |
| `conversation_history`        | DB`Conversation` 表 → reversed()                      | dialogue_strategy / context_builder / orchestrator | DB                          |
| `user_memories`               | DB`UserMemory` 表 → `retrieve_memories()`             | `_format_memories()` → system_prompt              | DB + Vector                 |
| `dialogue_strategy_text`      | `enhance_prompt_with_strategy()`                       | `build_context(dialogue_strategy=...)`             | 运行时                      |
| `previous_summary` (LLM摘要)  | 上轮`result.metadata["conversation_summary"]`          | `build_context(llm_generated_summary=...)`         | `context.bot_data` 内存缓存 |
| `mid_term_summary` (规则摘要) | `ConversationSummaryService.summarize_conversations()` | `_build_enhanced_system_prompt()`                  | 运行时                      |
| `proactive_guidance`          | `_generate_proactive_guidance()`                       | `_build_enhanced_system_prompt()`                  | 运行时                      |
| `memory_analysis`             | LLM JSON →`OrchestrationResult.memory_analysis`       | `handle_message_with_agents()` → 写 `UserMemory`  | 运行时 → DB                |
