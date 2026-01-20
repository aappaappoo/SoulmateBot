"""
工具调用Agent

这个Agent展示了如何集成外部工具和API，提供实用功能。
这是SoulmateBot提供实际帮助能力的核心示例。
"""
from typing import Dict, Any, Optional
from datetime import datetime
from src.agents import BaseAgent, Message, ChatContext, AgentResponse, SQLiteMemoryStore


class ToolAgent(BaseAgent):
    """
    工具调用Agent - 提供实用工具能力
    
    专长领域:
    - 信息查询：天气、时间、日期等
    - 实用计算：简单数学计算
    - 文本处理：翻译、格式转换等
    - API集成：可扩展对接各种第三方服务
    
    适用场景:
    - "今天天气怎么样？"
    - "现在几点了？"
    - "帮我计算一下..."
    - "翻译这段话..."
    
    扩展指南:
    - 添加新工具：在_tools字典中注册新的工具函数
    - 对接API：在对应的工具函数中调用外部API
    - 工具组合：可以在一次响应中调用多个工具
    """
    
    def __init__(self, memory_store=None):
        """
        初始化工具Agent
        
        参数:
            memory_store: 可选的记忆存储实例
        """
        self._name = "ToolAgent"
        self._description = (
            "提供实用工具功能的Agent。"
            "可以查询信息、执行计算、调用外部API等。"
            "帮助用户完成各种实际任务。"
        )
        self._memory = memory_store or SQLiteMemoryStore()
        
        # 工具相关的关键词库
        self._tool_keywords = [
            # 信息查询
            "天气", "weather", "温度", "temperature",
            "时间", "time", "日期", "date",
            "查询", "查", "search", "find",
            
            # 计算
            "计算", "算", "calculate", "computation",
            "加", "减", "乘", "除", "plus", "minus",
            
            # 翻译
            "翻译", "translate", "translation",
            
            # 提醒
            "提醒", "remind", "reminder", "alarm",
            
            # 帮助
            "帮我", "帮忙", "help me", "can you",
        ]
        
        # 工具注册表 - 可以动态添加新工具
        self._tools = {
            "weather": self._get_weather,
            "time": self._get_time,
            "calculate": self._calculate,
            "translate": self._translate,
        }
    
    @property
    def name(self) -> str:
        """Agent名称"""
        return self._name
    
    @property
    def description(self) -> str:
        """Agent描述"""
        return self._description
    
    def can_handle(self, message: Message, context: ChatContext) -> float:
        """
        判断是否能处理此消息
        
        检查消息是否包含工具调用的意图
        
        返回值:
            float: 置信度分数 (0.0-1.0)
        """
        # 检查@提及
        if message.has_mention(self.name):
            return 1.0
        
        content = message.content.lower()
        
        # 统计工具关键词匹配数
        keyword_matches = sum(1 for keyword in self._tool_keywords if keyword in content)
        
        # 根据匹配数计算置信度
        if keyword_matches >= 2:
            confidence = 0.9
        elif keyword_matches == 1:
            confidence = 0.7
        else:
            confidence = 0.0
        
        # 检查问号（询问类消息）
        if "?" in content or "？" in content:
            if keyword_matches > 0:
                confidence = min(1.0, confidence + 0.1)
        
        return confidence
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        """
        调用相应的工具并返回结果
        
        处理流程:
        1. 识别用户想要使用的工具
        2. 调用对应的工具函数
        3. 返回工具执行结果
        4. 更新使用记录
        """
        # 读取用户历史
        user_memory = self.memory_read(message.user_id)
        usage_count = user_memory.get("tool_usage_count", 0)
        
        content = message.content.lower()
        
        # 识别需要调用的工具并执行
        tool_used = None
        result = None
        
        if any(word in content for word in ["天气", "weather"]):
            tool_used = "weather"
            result = self._get_weather()
        elif any(word in content for word in ["时间", "time", "几点"]):
            tool_used = "time"
            result = self._get_time()
        elif any(word in content for word in ["计算", "算", "calculate"]):
            tool_used = "calculate"
            result = self._calculate(content)
        elif any(word in content for word in ["翻译", "translate"]):
            tool_used = "translate"
            result = self._translate(content)
        else:
            # 没有匹配到具体工具，返回可用工具列表
            result = self._list_available_tools()
        
        # 更新使用记录
        user_memory["tool_usage_count"] = usage_count + 1
        user_memory["last_tool"] = tool_used
        user_memory["last_use_time"] = datetime.now().isoformat()
        self.memory_write(message.user_id, user_memory)
        
        return AgentResponse(
            content=result,
            agent_name=self.name,
            confidence=0.85,
            metadata={
                "tool_used": tool_used,
                "usage_count": usage_count + 1
            },
            should_continue=False
        )
    
    # ========== 工具实现函数 ==========
    # 以下是各种工具的具体实现
    # 可以根据需要扩展或对接真实的API
    
    def _get_weather(self) -> str:
        """
        获取天气信息
        
        TODO: 对接真实的天气API（如OpenWeatherMap、和风天气等）
        当前返回示例数据
        """
        # 这里应该调用真实的天气API
        # 示例：
        # import requests
        # response = requests.get(f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}")
        # data = response.json()
        
        return (
            "🌤️ 今天天气情况：\n"
            "- 天气：晴转多云\n"
            "- 温度：22°C\n"
            "- 湿度：60%\n"
            "- 风力：3级\n\n"
            "💡 提示：记得带伞，下午可能有小雨哦！\n\n"
            "⚠️ 注意：这是示例数据，请在配置中添加真实的天气API密钥"
        )
    
    def _get_time(self) -> str:
        """
        获取当前时间
        
        返回格式化的当前日期和时间
        """
        now = datetime.now()
        
        # 星期映射
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday = weekdays[now.weekday()]
        
        return (
            f"🕐 当前时间信息：\n"
            f"📅 日期：{now.strftime('%Y年%m月%d日')} {weekday}\n"
            f"⏰ 时间：{now.strftime('%H:%M:%S')}\n"
        )
    
    def _calculate(self, expression: str) -> str:
        """
        执行数学计算
        
        TODO: 使用安全的表达式解析器（如sympy）
        当前仅返回提示信息
        
        参数:
            expression: 包含数学表达式的消息
        """
        # 安全提示：不要直接使用eval()，容易被注入攻击
        # 应该使用专门的数学表达式解析库，如：
        # from sympy import sympify
        # result = sympify(expression).evalf()
        
        return (
            "🧮 计算功能：\n\n"
            "很抱歉，计算功能正在开发中。\n"
            "未来版本将支持：\n"
            "- 基础运算（加减乘除）\n"
            "- 高级数学函数\n"
            "- 单位转换\n"
            "- 方程求解\n\n"
            "💡 开发提示：使用sympy或其他安全的数学库实现"
        )
    
    def _translate(self, text: str) -> str:
        """
        翻译文本
        
        TODO: 对接翻译API（如百度翻译、谷歌翻译、DeepL等）
        当前返回提示信息
        
        参数:
            text: 要翻译的文本
        """
        # 这里应该调用翻译API
        # 示例（使用googletrans）：
        # from googletrans import Translator
        # translator = Translator()
        # result = translator.translate(text, dest='zh-cn')
        
        return (
            "🌐 翻译功能：\n\n"
            "翻译功能即将上线！\n"
            "将支持：\n"
            "- 中英互译\n"
            "- 多语言支持\n"
            "- 专业术语翻译\n\n"
            "💡 开发提示：对接百度翻译、DeepL或GPT翻译API"
        )
    
    def _list_available_tools(self) -> str:
        """
        列出所有可用的工具
        
        当用户的请求不明确时，显示工具列表
        """
        return (
            "🔧 我可以帮你：\n\n"
            "📊 信息查询：\n"
            "  • 查天气 - 获取天气预报\n"
            "  • 查时间 - 获取当前日期时间\n\n"
            "🧮 实用工具：\n"
            "  • 计算 - 数学计算\n"
            "  • 翻译 - 文本翻译\n\n"
            "💡 提示：直接告诉我你需要什么，比如：\n"
            "  \"今天天气怎么样？\"\n"
            "  \"现在几点了？\"\n\n"
            "🔨 扩展提示：\n"
            "  可以在agents/tool_agent.py中添加更多工具！"
        )
    
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        """
        读取用户的工具使用历史
        
        存储内容：
        - tool_usage_count: 工具使用次数
        - last_tool: 最后使用的工具
        - last_use_time: 最后使用时间
        """
        return self._memory.read(self.name, user_id)
    
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        """
        保存用户的工具使用历史
        
        用于统计和个性化服务
        """
        self._memory.write(self.name, user_id, data)
