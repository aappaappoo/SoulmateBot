# 对话策略系统 2.0 文档

## 概述

对话策略系统 2.0 为 SoulmateBot 带来了更丰富的人格表达能力，使 Bot 不再是"顺从的工具"，而是具有独立观点和价值观的"智能对话体"。

## 核心特性

### 1. 价值观系统 (Values System)

Bot 现在可以配置自己的价值观维度、预设立场和回应偏好，形成稳定的人格特征。

#### 价值观维度 (Value Dimensions)

使用 1-10 的评分定义 Bot 的人格维度：

```yaml
dimensions:
  rationality: 7       # 理性 vs 感性（1=极感性, 10=极理性）
  openness: 8          # 保守 vs 开放（1=保守, 10=开放）
  assertiveness: 7     # 顺从 vs 坚持（1=顺从, 10=坚持）← 关键参数！
  optimism: 5          # 悲观 vs 乐观
  depth_preference: 6  # 浅聊 vs 深度
```

- **rationality**: 影响 Bot 是更注重逻辑分析还是情感共鸣
- **openness**: 影响 Bot 对新观点的接受程度
- **assertiveness**: **关键参数**，决定 Bot 是否敢于表达不同意见
- **optimism**: 影响 Bot 看待问题的角度
- **depth_preference**: 影响 Bot 是喜欢轻松闲聊还是深度探讨

#### 预设立场 (Stances)

Bot 可以对特定话题持有自己的观点：

```yaml
stances:
  - topic: "加班文化"
    position: "反对无效加班，效率比时长重要"
    confidence: 0.8  # 坚持程度 0-1
  
  - topic: "完美主义"
    position: "差不多就行，别太卷自己"
    confidence: 0.7
```

- **topic**: 话题关键词（用于匹配用户消息）
- **position**: Bot 的观点
- **confidence**: Bot 对这个立场的坚持程度（0-1），配合 assertiveness 决定表达策略

#### 回应偏好 (Response Preferences)

定义 Bot 的表达风格：

```yaml
response_preferences:
  agree_first: false   # 是否倾向先认同再表达不同
  use_examples: true   # 是否喜欢用例子说明
  ask_back: true       # 是否倾向反问用户
  use_humor: true      # 是否用幽默化解分歧
```

### 2. 对话类型识别 (Conversation Type Detection)

系统自动识别 5 种对话类型：

1. **情绪倾诉 (EMOTIONAL_VENT)**: 用户在宣泄情绪
   - 信号词：难过、烦、累、不知道怎么办、压力大等
   - 策略：优先安慰，暂不反驳

2. **观点讨论 (OPINION_DISCUSSION)**: 用户在表达观点并寻求交流
   - 信号词：我觉得、你怎么看、是不是应该等
   - 策略：可以表达立场，触发立场分析

3. **信息需求 (INFO_REQUEST)**: 用户在寻求信息
   - 信号词：最近、有什么、推荐、是不是真的等
   - 策略：可触发搜索技能（如果启用）

4. **决策咨询 (DECISION_CONSULTING)**: 用户在寻求建议
   - 信号词：该不该、怎么选、帮我分析等
   - 策略：分析利弊，提供建议

5. **日常闲聊 (CASUAL_CHAT)**: 轻松的日常交流
   - 策略：轻松互动，保持对话流畅

### 3. 立场策略系统 (Stance Strategy)

根据对话类型、价值观维度和冲突程度，系统选择合适的立场表达策略：

1. **完全同意 (AGREE)**: 用户观点与 Bot 立场一致
2. **先同意再补充 (AGREE_AND_ADD)**: 认可用户，温和补充不同视角
3. **部分同意 (PARTIAL_AGREE)**: 明确指出认同和不同的部分
4. **尊重地表达不同意见 (RESPECTFUL_DISAGREE)**: 明确表达不同看法，但保持尊重
5. **温和质疑 (CHALLENGE)**: 通过提问引导用户重新思考

策略选择逻辑：
- 低冲突 + agree_first=true → AGREE_AND_ADD
- 中等冲突 + 高 assertiveness → PARTIAL_AGREE
- 高冲突 + 高 assertiveness + 高 confidence → RESPECTFUL_DISAGREE
- 情绪倾诉 → 优先安慰，不表达反对立场

### 4. 技能分层体系 (Skill Tier System)

支持将技能分为基础技能（免费）和高级技能（付费）：

```yaml
skills:
  tier_system:
    basic:
      - emotional_support
      - daily_chat
      - short_term_memory
    premium:
      - web_search
      - deep_analysis
      - long_term_memory
      - voice_reply
```

## 使用示例

### 配置 Bot 价值观

在 `config.yaml` 中添加 `values` 配置块：

```yaml
# 团团 - 活泼可爱，适度表达
values:
  dimensions:
    rationality: 3       # 偏感性
    openness: 7          # 较开放
    assertiveness: 5     # 适度表达
    optimism: 8          # 乐观
    depth_preference: 4  # 偏浅，但能深

  stances:
    - topic: "努力与休息"
      position: "努力很重要，但也要好好休息呀~"
      confidence: 0.7

  response_preferences:
    agree_first: true
    use_examples: true
    ask_back: true
    use_humor: false
  
  default_behavior: "curious"  # 对没有预设立场的话题保持好奇
```

### 在代码中使用

```python
from src.bot.config_loader import get_config_loader
from src.conversation.dialogue_strategy import enhance_prompt_with_strategy

# 加载 Bot 配置
loader = get_config_loader()
config = loader.load_config("tuantuan_bot")

# 增强 prompt（带价值观）
enhanced_prompt = enhance_prompt_with_strategy(
    original_prompt=config.get_system_prompt(),
    conversation_history=history,
    current_message=user_message,
    bot_values=config.values  # 传入价值观配置
)

# 使用增强后的 prompt 调用 LLM
response = llm.chat(enhanced_prompt, history, user_message)
```

## 向后兼容性

所有新功能都保持向后兼容：

1. **不配置 values**: Bot 行为与之前一致，只使用基础对话策略
2. **部分配置 values**: 未配置的部分使用默认值
3. **不传入 bot_values 参数**: `enhance_prompt_with_strategy()` 仍然正常工作

示例：

```python
# 不传入 bot_values，保持向后兼容
enhanced_prompt = enhance_prompt_with_strategy(
    original_prompt=config.get_system_prompt(),
    conversation_history=history,
    current_message=user_message
    # bot_values=None (默认值)
)
```

## 工作原理

### Prompt 构建流程

1. **基础 Prompt**: Bot 的原始人设（从 config 中加载）
2. **价值观注入**: 如果提供了 bot_values，添加价值观维度描述
3. **立场策略**: 如果是观点讨论类型，添加立场策略指导
4. **对话策略**: 根据对话阶段和情绪添加对话策略指导
5. **多消息指令**: 添加多消息回复格式说明

最终 Prompt 结构：

```
[原始人设]

=========================
🎭 你的价值观和立场
=========================
[价值观维度描述]
[预设立场列表]

=========================
💭 关于当前话题的立场
=========================
[用户观点]
[Bot观点]
[立场策略指导]

=========================
【当前对话策略：XXX】
=========================
[对话策略指导]

=========================
📝 回复格式说明
=========================
[多消息回复指令]
```

**关键原则**: 策略是 **APPEND** 而非 REPLACE，原有人设完全保留！

## 测试

运行测试验证功能：

```bash
# 测试配置加载
python -m pytest tests/test_config_values.py -v

# 测试对话策略 2.0
python -m pytest tests/test_dialogue_strategy_2.py -v

# 测试向后兼容性
python -m pytest tests/test_dialogue_strategy.py -v
```

## 配置参考

### 团团 (tuantuan_bot) - 活泼可爱型

```yaml
values:
  dimensions:
    rationality: 3       # 偏感性
    assertiveness: 5     # 适度表达
    optimism: 8          # 很乐观
  response_preferences:
    agree_first: true    # 先认同
    use_humor: false     # 不太用幽默
```

### 胖胖 (pangpang_bot) - 幽默吐槽型

```yaml
values:
  dimensions:
    rationality: 7       # 偏理性
    assertiveness: 7     # 更敢表达
    optimism: 5          # 务实
  response_preferences:
    agree_first: false   # 可以直接表达不同
    use_humor: true      # 善用幽默
```

## 注意事项

1. **assertiveness 是关键**: 这个参数决定 Bot 是否敢于表达不同意见
   - 低 (1-4): Bot 更顺从，很少反驳
   - 中 (5-6): Bot 适度表达，有分寸
   - 高 (7-10): Bot 敢于坚持，会明确表达不同意见

2. **情绪倾诉优先**: 即使 Bot 有不同立场，在情绪倾诉场景也会优先安慰而非反驳

3. **confidence 配合 assertiveness**: 
   - 高 assertiveness + 高 confidence = 更坚定的表达
   - 低 assertiveness 或低 confidence = 更温和的表达

4. **保持人设一致性**: 价值观配置应该与 Bot 的基础人设相匹配

## 未来扩展

系统设计时已考虑未来扩展：

1. **更丰富的对话类型**: 可以添加更多对话类型及其识别逻辑
2. **更精确的立场匹配**: 可以集成 NLP 模型进行语义匹配
3. **动态价值观调整**: 可以根据用户反馈调整 Bot 的价值观
4. **个性化立场学习**: 可以让 Bot 学习用户偏好，动态调整表达策略

## 技术架构

```
BotConfig (config_loader.py)
  └── ValuesConfig
      ├── ValueDimensionsConfig
      ├── StanceConfig (list)
      └── ResponsePreferencesConfig

DialogueStrategyInjector (dialogue_strategy.py)
  ├── DialoguePhaseAnalyzer
  ├── ConversationTypeAnalyzer
  └── StanceAnalyzer
      └── StanceAnalysis
```

所有组件都独立可测试，松耦合设计。
