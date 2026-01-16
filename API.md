# API 文档

## 目录
- [Telegram Bot 命令](#telegram-bot-命令)
- [内部 API](#内部-api)
- [数据模型](#数据模型)
- [错误处理](#错误处理)

---

## Telegram Bot 命令

### /start
开始使用机器人

**响应**: 欢迎消息和功能介绍

**示例**:
```
用户: /start
Bot: 👋 你好！欢迎来到情感陪伴机器人 SoulmateBot！
```

---

### /help
获取帮助信息

**响应**: 功能说明和订阅计划介绍

---

### /status
查看当前订阅状态和使用情况

**响应**:
- 用户信息
- 订阅层级
- 今日使用量
- 剩余额度

**示例**:
```
📊 你的状态

👤 用户：张三
🎫 订阅：🆓 免费版
✅ 状态：激活

📈 今日使用情况：
💬 消息：5 / 10
🖼️ 图片：0
```

---

### /subscribe
查看订阅计划

**响应**: 所有可用订阅计划详情

---

### /image
获取温馨图片

**前置条件**: 
- 用户未超过每日图片限额
- 订阅层级允许使用图片功能

**响应**: 一张情感支持图片

---

## 内部 API

### ConversationService

#### `get_response(user_message, conversation_history, context)`

获取 AI 生成的对话响应

**参数**:
- `user_message` (str): 用户消息
- `conversation_history` (List[Dict]): 对话历史
- `context` (str, optional): 额外上下文

**返回**: 
- `str`: AI 生成的响应

**示例**:
```python
from src.ai import conversation_service

response = await conversation_service.get_response(
    user_message="今天心情不好",
    conversation_history=[
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！有什么可以帮你的吗？"}
    ]
)
```

---

### SubscriptionService

#### `get_user_by_telegram_id(telegram_id)`

获取或创建用户

**参数**:
- `telegram_id` (int): Telegram 用户 ID

**返回**: 
- `User`: 用户对象

---

#### `check_usage_limit(user, action_type)`

检查用户是否超过使用限额

**参数**:
- `user` (User): 用户对象
- `action_type` (str): 操作类型 ("message" 或 "image")

**返回**: 
- `bool`: True 如果未超限，False 如果已超限

**示例**:
```python
from src.subscription import SubscriptionService

service = SubscriptionService(db)
can_proceed = service.check_usage_limit(user, "message")
```

---

#### `record_usage(user, action_type, count)`

记录用户使用情况

**参数**:
- `user` (User): 用户对象
- `action_type` (str): 操作类型
- `count` (int): 使用次数

---

#### `get_usage_stats(user)`

获取用户使用统计

**返回**:
```python
{
    "subscription_tier": "free",
    "messages_used": 5,
    "messages_limit": 10,
    "images_used": 0,
    "is_active": True
}
```

---

#### `upgrade_subscription(user, new_tier, duration_days)`

升级用户订阅

**参数**:
- `user` (User): 用户对象
- `new_tier` (SubscriptionTier): 新订阅层级
- `duration_days` (int): 订阅天数

---

### ImageService

#### `generate_image(prompt, user_id)`

使用 AI 生成图片

**参数**:
- `prompt` (str): 图片生成提示词
- `user_id` (int): 用户 ID

**返回**: 
- `str`: 图片文件路径

---

#### `send_daily_image(user_mood)`

发送每日激励图片

**参数**:
- `user_mood` (str): 用户情绪 ("positive", "sad", "anxious", etc.)

**返回**: 
- `str`: 图片文件路径

---

## 数据模型

### User

用户模型

**字段**:
```python
id: int                           # 主键
telegram_id: int                  # Telegram 用户 ID
username: str                     # 用户名
first_name: str                   # 名
last_name: str                    # 姓
language_code: str                # 语言代码
subscription_tier: SubscriptionTier  # 订阅层级
subscription_start_date: datetime    # 订阅开始日期
subscription_end_date: datetime      # 订阅结束日期
is_active: bool                   # 是否激活
created_at: datetime              # 创建时间
updated_at: datetime              # 更新时间
```

---

### Conversation

对话记录模型

**字段**:
```python
id: int                    # 主键
user_id: int              # 用户 ID (外键)
message: str              # 消息内容
response: str             # 响应内容
is_user_message: bool     # 是否为用户消息
message_type: str         # 消息类型
timestamp: datetime       # 时间戳
```

---

### UsageRecord

使用记录模型

**字段**:
```python
id: int              # 主键
user_id: int        # 用户 ID (外键)
action_type: str    # 操作类型 (message/image)
count: int          # 使用次数
date: datetime      # 日期
```

---

### Payment

支付记录模型

**字段**:
```python
id: int                      # 主键
user_id: int                # 用户 ID (外键)
amount: int                 # 金额 (分)
currency: str               # 货币
provider: str               # 支付提供商
provider_payment_id: str    # 支付 ID
status: str                 # 状态 (pending/succeeded/failed)
created_at: datetime        # 创建时间
updated_at: datetime        # 更新时间
```

---

### SubscriptionTier

订阅层级枚举

**值**:
- `FREE`: 免费版
- `BASIC`: 基础版
- `PREMIUM`: 高级版

---

## 错误处理

### 错误类型

#### UsageLimitExceeded

用户超过使用限额

**响应**:
```
⚠️ 你今天的消息额度已用完。
升级订阅以获取更多额度！
```

#### SubscriptionExpired

订阅已过期

**响应**:
```
⚠️ 你的订阅已过期。
使用 /subscribe 续订以继续使用高级功能。
```

#### AIProviderError

AI 服务提供商错误

**处理**: 返回友好的错误消息给用户

---

## 使用示例

### 完整对话流程

```python
from telegram import Update
from telegram.ext import ContextTypes
from src.database import get_db_session
from src.subscription import SubscriptionService
from src.ai import conversation_service

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    
    db = get_db_session()
    try:
        # 1. 获取用户
        service = SubscriptionService(db)
        db_user = service.get_user_by_telegram_id(user.id)
        
        # 2. 检查限额
        if not service.check_usage_limit(db_user, "message"):
            await update.message.reply_text("已达使用限额")
            return
        
        # 3. 获取 AI 响应
        response = await conversation_service.get_response(message_text)
        
        # 4. 记录使用
        service.record_usage(db_user, "message")
        
        # 5. 发送响应
        await update.message.reply_text(response)
        
    finally:
        db.close()
```

---

## 配置参数

### 订阅限额

在 `config/settings.py` 中配置:

```python
FREE_PLAN_DAILY_LIMIT = 10      # 免费版每日消息限额
BASIC_PLAN_DAILY_LIMIT = 100    # 基础版每日消息限额
PREMIUM_PLAN_DAILY_LIMIT = 1000 # 高级版每日消息限额
```

### 速率限制

```python
RATE_LIMIT_MESSAGES_PER_MINUTE = 10  # 每分钟消息数
RATE_LIMIT_IMAGES_PER_HOUR = 5       # 每小时图片数
```

---

## Webhook 配置 (可选)

如果使用 webhook 而不是 polling:

```python
from src.bot import SoulmateBot

bot = SoulmateBot()
bot.run_webhook(
    listen="0.0.0.0",
    port=8080,
    url_path="webhook",
    webhook_url="https://your-domain.com/webhook"
)
```

---

更多信息请参考源码或提交 Issue。
