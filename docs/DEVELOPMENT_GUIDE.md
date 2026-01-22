# SoulmateBot 二次开发完整指南

## 目录

1. [系统架构概述](#系统架构概述)
2. [Agent开发详解](#agent开发详解)
3. [工具集成指南](#工具集成指南)
4. [数据库扩展](#数据库扩展)
5. [配置管理](#配置管理)
6. [最佳实践](#最佳实践)
7. [常见问题](#常见问题)

---

## 系统架构概述

### 核心组件

SoulmateBot采用模块化设计，主要包含以下核心组件：

```
SoulmateBot/
├── src/
│   ├── bot/           # Bot核心 - Telegram Bot主程序
│   ├── agents/        # Agent系统 - 多Agent架构核心
│   ├── handlers/      # 消息处理器 - 命令和消息处理
│   ├── models/        # 数据模型 - ORM模型定义
│   ├── database/      # 数据库 - 连接和管理
│   └── services/      # 业务服务 - 各种业务逻辑
├── agents/            # Agent实现 - 自定义Agent放这里
│   ├── emotional_agent.py  # 情感支持Agent
│   ├── tech_agent.py       # 技术支持Agent
│   └── tool_agent.py       # 工具调用Agent
├── config/            # 配置 - 系统配置管理
└── main.py           # 入口文件
```

### 双核心能力架构

```
┌─────────────────────────────────────┐
│         用户消息输入                 │
└──────────────┬──────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│         Router 智能路由              │
│    ┌──────────────────────────┐     │
│    │ 1. 解析@提及             │     │
│    │ 2. 计算置信度            │     │
│    │ 3. 选择Agent             │     │
│    └──────────────────────────┘     │
└──────────────┬───────────────────────┘
               │
        ┌──────┴──────┐
        ▼             ▼
┌──────────────┐  ┌──────────────┐
│ 情感价值核心  │  │ 工具调用核心  │
├──────────────┤  ├──────────────┤
│EmotionalAgent│  │  ToolAgent   │
│ - 情绪识别   │  │ - API调用    │
│ - 共情响应   │  │ - 信息查询   │
│ - 心理支持   │  │ - 任务执行   │
│ - 记忆系统   │  │ - 工具集成   │
└──────────────┘  └──────────────┘
        │             │
        └──────┬──────┘
               ▼
      ┌────────────────┐
      │  响应合并返回   │
      └────────────────┘
```

---

## Agent开发详解

### 基础概念

Agent是SoulmateBot的核心概念，每个Agent负责处理特定类型的消息。

**核心接口**：
- `name`: Agent的唯一名称
- `description`: Agent的功能描述
- `can_handle()`: 判断能否处理消息（返回0-1的置信度）
- `respond()`: 生成响应
- `memory_read()/write()`: 读写用户记忆

### 创建自定义Agent

#### 步骤1：创建Agent文件

在 `agents/` 目录下创建新文件，例如 `agents/weather_agent.py`：

```python
"""
天气查询Agent - 示例
"""
from typing import Dict, Any
import requests
from src.agents import BaseAgent, Message, ChatContext, AgentResponse, SQLiteMemoryStore


class WeatherAgent(BaseAgent):
    """天气查询专用Agent"""
    
    def __init__(self, api_key: str = None):
        """初始化"""
        self._name = "WeatherAgent"
        self._description = "提供天气查询服务"
        self._api_key = api_key or os.getenv("WEATHER_API_KEY")
        self._memory = SQLiteMemoryStore()
        
        # 关键词库
        self._keywords = ["天气", "weather", "温度", "气温", "下雨", "晴天"]
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    def can_handle(self, message: Message, context: ChatContext) -> float:
        """判断置信度"""
        # @提及 -> 1.0
        if message.has_mention(self.name):
            return 1.0
        
        # 关键词匹配
        content = message.content.lower()
        matches = sum(1 for kw in self._keywords if kw in content)
        
        if matches >= 2:
            return 0.95
        elif matches == 1:
            return 0.8
        
        return 0.0
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        """生成响应"""
        # 提取城市名称
        city = self._extract_city(message.content)
        
        # 调用天气API
        weather_data = self._get_weather(city)
        
        # 格式化响应
        response_text = self._format_weather(weather_data, city)
        
        return AgentResponse(
            content=response_text,
            agent_name=self.name,
            confidence=0.9,
            metadata={"city": city}
        )
    
    def _extract_city(self, text: str) -> str:
        """从文本中提取城市名"""
        # 简单实现：可以使用NLP或正则表达式
        # 这里返回默认城市
        return "北京"
    
    def _get_weather(self, city: str) -> dict:
        """调用天气API"""
        if not self._api_key:
            return {"error": "未配置API密钥"}
        
        # 调用实际的天气API
        # 例如：OpenWeatherMap, 和风天气等
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather"
            params = {
                "q": city,
                "appid": self._api_key,
                "units": "metric",
                "lang": "zh_cn"
            }
            response = requests.get(url, params=params)
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def _format_weather(self, data: dict, city: str) -> str:
        """格式化天气数据"""
        if "error" in data:
            return f"抱歉，无法获取{city}的天气信息: {data['error']}"
        
        # 解析并格式化天气数据
        temp = data.get("main", {}).get("temp", "N/A")
        desc = data.get("weather", [{}])[0].get("description", "未知")
        
        return (
            f"🌤️ {city}天气：\n"
            f"温度：{temp}°C\n"
            f"天气：{desc}\n"
        )
    
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        """读取记忆"""
        return self._memory.read(self.name, user_id)
    
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        """写入记忆"""
        self._memory.write(self.name, user_id, data)
```

#### 步骤2：Agent自动加载

系统会自动加载 `agents/` 目录下的所有Agent，无需手动注册！

#### 步骤3：配置API密钥

在 `.env` 文件中添加：

```env
WEATHER_API_KEY=your_api_key_here
```

### Agent最佳实践

#### 1. 合理设置置信度

```python
def can_handle(self, message: Message, context: ChatContext) -> float:
    """
    置信度设置原则：
    - 1.0: 被@提及
    - 0.8-0.95: 高度匹配（多个关键词、专业术语）
    - 0.6-0.7: 中等匹配（少量关键词）
    - 0.3-0.5: 低匹配（模糊相关）
    - 0.0: 不相关
    """
    pass
```

#### 2. 使用记忆系统

```python
def respond(self, message: Message, context: ChatContext) -> AgentResponse:
    # 读取用户历史
    memory = self.memory_read(message.user_id)
    last_city = memory.get("last_city", "北京")
    visit_count = memory.get("visit_count", 0)
    
    # 使用历史信息个性化响应
    if visit_count > 0:
        response = f"欢迎回来！上次查询的是{last_city}的天气..."
    
    # 更新记忆
    memory["visit_count"] = visit_count + 1
    memory["last_city"] = current_city
    self.memory_write(message.user_id, memory)
    
    return AgentResponse(...)
```

#### 3. 错误处理

```python
def respond(self, message: Message, context: ChatContext) -> AgentResponse:
    try:
        # 尝试执行任务
        result = self._call_external_api()
        return AgentResponse(content=result, ...)
    except APIError as e:
        # API错误
        return AgentResponse(
            content=f"抱歉，服务暂时不可用：{e}",
            confidence=0.5
        )
    except Exception as e:
        # 其他错误
        logger.error(f"Agent错误: {e}")
        return AgentResponse(
            content="抱歉，处理时出现了问题",
            confidence=0.3
        )
```

---

## 工具集成指南

### 集成外部API

#### 示例：集成搜索API

```python
"""
搜索Agent - 集成搜索引擎
"""
import requests
from src.agents import BaseAgent, Message, ChatContext, AgentResponse


class SearchAgent(BaseAgent):
    """网络搜索Agent"""
    
    def __init__(self):
        self._name = "SearchAgent"
        self._api_key = os.getenv("SEARCH_API_KEY")
        # 可以使用 Google Custom Search, Bing Search 等
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        # 提取搜索关键词
        query = self._extract_query(message.content)
        
        # 调用搜索API
        results = self._search(query)
        
        # 格式化结果
        formatted = self._format_results(results)
        
        return AgentResponse(content=formatted, ...)
    
    def _search(self, query: str) -> list:
        """调用搜索API"""
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self._api_key,
            "cx": "your_search_engine_id",
            "q": query,
            "num": 5  # 返回5条结果
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        return data.get("items", [])
    
    def _format_results(self, results: list) -> str:
        """格式化搜索结果"""
        if not results:
            return "没有找到相关结果"
        
        output = "🔍 搜索结果：\n\n"
        for i, item in enumerate(results, 1):
            title = item.get("title", "")
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            
            output += f"{i}. {title}\n"
            output += f"   {snippet}\n"
            output += f"   🔗 {link}\n\n"
        
        return output
```

### 工具链模式

创建可组合的工具链：

```python
class ToolChainAgent(BaseAgent):
    """支持工具链的Agent"""
    
    def __init__(self):
        self._tools = {
            "search": SearchTool(),
            "summarize": SummarizeTool(),
            "translate": TranslateTool(),
        }
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        # 分析需要哪些工具
        steps = self._plan_steps(message.content)
        
        # 执行工具链
        result = message.content
        for step in steps:
            tool = self._tools[step["tool"]]
            result = tool.execute(result, step["params"])
        
        return AgentResponse(content=result, ...)
    
    def _plan_steps(self, query: str) -> list:
        """规划执行步骤"""
        # 可以使用LLM来规划工具调用顺序
        # 例如："搜索最新的AI新闻并翻译成中文"
        # -> [{"tool": "search", "params": {...}}, 
        #     {"tool": "translate", "params": {"to": "zh"}}]
        pass
```

---

## 数据库扩展

### 添加自定义表

#### 步骤1：定义模型

在 `src/models/` 创建新模型：

```python
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from src.database import Base
from datetime import datetime


class UserPreference(Base):
    """用户偏好设置表"""
    __tablename__ = "user_preferences"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, unique=True, nullable=False, index=True)
    
    # 偏好设置
    language = Column(String, default="zh")
    timezone = Column(String, default="Asia/Shanghai")
    notification_enabled = Column(Boolean, default=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConversationHistory(Base):
    """对话历史表"""
    __tablename__ = "conversation_history"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    agent_name = Column(String, nullable=False)
    
    # 对话内容
    user_message = Column(Text, nullable=False)
    agent_response = Column(Text, nullable=False)
    
    # 元数据
    confidence = Column(Float)
    emotion = Column(String)  # 检测到的情绪
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
```

#### 步骤2：创建迁移

```bash
# 使用Alembic创建迁移
alembic revision --autogenerate -m "Add user preferences and conversation history"
alembic upgrade head
```

#### 步骤3：使用模型

```python
from src.database import get_db
from src.models import UserPreference

def save_user_preference(user_id: str, language: str):
    """保存用户偏好"""
    db = next(get_db())
    
    # 查找或创建
    pref = db.query(UserPreference).filter_by(user_id=user_id).first()
    if not pref:
        pref = UserPreference(user_id=user_id)
        db.add(pref)
    
    # 更新
    pref.language = language
    db.commit()
```

---

## 配置管理

### 环境变量

在 `.env` 文件中添加配置：

```env
# Telegram配置
TELEGRAM_BOT_TOKEN=your_bot_token

# AI提供商
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

# 自定义Agent配置
WEATHER_API_KEY=your_weather_key
SEARCH_API_KEY=your_search_key
NEWS_API_KEY=your_news_key

# Agent Router配置
ROUTER_MIN_CONFIDENCE=0.5
ROUTER_MAX_AGENTS=1
ROUTER_ENABLE_PARALLEL=false

# 数据库
DATABASE_URL=sqlite:///./soulmatebot.db

# 日志
LOG_LEVEL=INFO
```

### 在代码中读取

```python
import os
from config import settings

# 方式1：使用os.getenv
api_key = os.getenv("WEATHER_API_KEY")
if not api_key:
    raise ValueError("未配置WEATHER_API_KEY")

# 方式2：使用settings对象
min_confidence = float(settings.get("ROUTER_MIN_CONFIDENCE", 0.5))
```

---

## 最佳实践

### 1. Agent设计原则

✅ **DO：**
- 单一职责：每个Agent专注一个领域
- 清晰命名：使用描述性的Agent名称
- 错误处理：优雅地处理所有异常
- 记忆利用：使用记忆系统个性化体验
- 文档完整：添加详细的中文注释

❌ **DON'T：**
- 不要让Agent职责过于宽泛
- 不要硬编码配置信息
- 不要忽略错误处理
- 不要在响应中暴露敏感信息

### 2. 性能优化

```python
# 缓存API结果
from functools import lru_cache

class WeatherAgent(BaseAgent):
    @lru_cache(maxsize=100)
    def _get_weather(self, city: str) -> dict:
        """缓存天气查询结果（避免频繁API调用）"""
        return self._call_weather_api(city)
```

### 3. 安全性

```python
# 1. 验证用户输入
def _validate_input(self, text: str) -> bool:
    """验证输入是否安全"""
    # 防止注入攻击
    dangerous_patterns = ["<script>", "DROP TABLE", "'; --"]
    return not any(pattern in text for pattern in dangerous_patterns)

# 2. 限流
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_requests=10, time_window=60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = {}
    
    def is_allowed(self, user_id: str) -> bool:
        now = datetime.now()
        
        # 清理过期记录
        if user_id in self.requests:
            self.requests[user_id] = [
                t for t in self.requests[user_id]
                if now - t < timedelta(seconds=self.time_window)
            ]
        
        # 检查是否超限
        user_requests = self.requests.get(user_id, [])
        if len(user_requests) >= self.max_requests:
            return False
        
        # 记录请求
        self.requests.setdefault(user_id, []).append(now)
        return True
```

---

## 常见问题

### Q1: 如何调试Agent？

```python
# 启用详细日志
from loguru import logger

logger.add("logs/agent_{time}.log", level="DEBUG")

# 在Agent中添加日志
def can_handle(self, message: Message, context: ChatContext) -> float:
    confidence = self._calculate_confidence(message)
    logger.debug(f"{self.name} confidence: {confidence} for message: {message.content}")
    return confidence
```

### Q2: 多个Agent置信度相同怎么办？

Router会按照Agent添加的顺序选择。可以通过调整置信度或Agent注册顺序来控制优先级。

### Q3: 如何实现Agent间协作？

```python
def respond(self, message: Message, context: ChatContext) -> AgentResponse:
    # 调用其他Agent获取信息
    tech_agent = context.get_agent("TechAgent")
    tech_info = tech_agent.get_technical_details(topic)
    
    # 结合自己的处理
    emotional_response = self._generate_empathetic_response(tech_info)
    
    return AgentResponse(content=emotional_response, ...)
```

### Q4: 如何添加新的AI模型？

在 `src/ai/` 中创建新的提供商：

```python
class CustomAIProvider:
    def __init__(self, api_key):
        self.api_key = api_key
    
    def generate_response(self, prompt: str) -> str:
        # 调用你的AI模型API
        pass
```

---

## 总结

通过本指南，你应该能够：

1. ✅ 理解SoulmateBot的架构
2. ✅ 创建自定义Agent提供情感价值和工具能力
3. ✅ 集成外部API和服务
4. ✅ 扩展数据库模型
5. ✅ 遵循最佳实践

需要更多帮助？查看代码中的注释或创建Issue！

---

**SoulmateBot - 专业智能陪伴机器人系统**

版权所有 © 2026
