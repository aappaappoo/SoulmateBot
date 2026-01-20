"""
技术支持Agent

专门处理技术和编程相关的问题，提供技术帮助和指导。
这个Agent展示了如何处理特定领域的专业内容。
"""
from typing import Dict, Any
from src.agents import BaseAgent, Message, ChatContext, AgentResponse, MemoryStore, SQLiteMemoryStore


class TechAgent(BaseAgent):
    """
    技术支持Agent - 提供编程和技术帮助
    
    专长领域:
    - 编程语言：Python, JavaScript, Java, C++等
    - 技术问题：调试、优化、架构设计
    - 学习指导：代码示例、最佳实践
    - 工具使用：框架、库、开发工具
    
    适用场景:
    - 编程问题咨询
    - 代码调试帮助
    - 技术概念解释
    - 最佳实践建议
    - 技术栈选择
    """
    
    def __init__(self, memory_store: MemoryStore = None):
        """
        初始化技术支持Agent
        
        参数:
            memory_store: 可选的记忆存储实例，用于记住用户的技术背景
        """
        self._name = "TechAgent"
        self._description = (
            "提供技术支持和编程帮助。"
            "专注于软件开发、调试、"
            "系统管理和技术解释。"
        )
        self._memory = memory_store or SQLiteMemoryStore()
        
        # 技术相关关键词库
        self._tech_keywords = [
            # 编程语言
            "python", "javascript", "java", "c++", "cpp", "c#", "csharp",
            "ruby", "php", "go", "golang", "rust", "kotlin", "swift",
            "typescript", "bash", "shell", "sql",
            
            # 框架和工具
            "react", "vue", "angular", "django", "flask", "fastapi",
            "node", "nodejs", "express", "spring", "docker", "kubernetes",
            "git", "github", "gitlab", "jenkins", "ci/cd",
            
            # 技术概念
            "code", "coding", "program", "programming", "script", "scripting",
            "function", "class", "method", "variable", "algorithm",
            "debug", "debugging", "error", "exception", "bug", "issue",
            "compile", "compiler", "interpreter", "runtime",
            "api", "rest", "graphql", "database", "db", "query",
            "server", "client", "frontend", "backend", "fullstack",
            "web", "website", "app", "application", "software",
            
            # 中文技术词汇
            "代码", "编程", "程序", "函数", "类", "方法", "变量",
            "调试", "错误", "异常", "Bug", "问题",
            "数据库", "服务器", "客户端", "前端", "后端",
            "网站", "应用", "软件", "开发",
            
            # 操作和概念
            "install", "configuration", "setup", "deploy", "deployment",
            "build", "compile", "run", "execute", "test", "testing",
            "performance", "optimization", "security", "authentication",
            
            # 技术动作
            "implement", "refactor", "migrate", "integrate", "develop",
            "how to", "how do i", "how can i",
        ]
        
        # 代码模式识别 - 用于识别消息中的代码片段
        self._code_patterns = [
            "```", "import", "export", "def ", "class ", "function",
            "const ", "let ", "var ", "if (", "for (", "while (",
            "try:", "except:", "catch", "throw", "return",
        ]
    
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
        
        对于技术和编程相关的消息返回高置信度。
        
        判断依据:
        1. 是否被@提及
        2. 是否包含代码片段
        3. 技术关键词数量
        4. "如何做"类型的问题
        5. 对话历史中的技术上下文
        
        返回值:
            float: 置信度分数 (0.0-1.0)
        """
        # 检查显式@提及
        if message.has_mention(self.name):
            return 1.0
        
        content = message.content.lower()
        
        # 检查是否包含代码块或代码模式
        has_code = any(pattern in message.content for pattern in self._code_patterns)
        if has_code:
            return 0.95  # 包含代码 = 非常高的置信度
        
        # 统计技术关键词匹配数
        keyword_matches = sum(1 for keyword in self._tech_keywords if keyword in content)
        
        # 根据关键词数量计算基础置信度
        if keyword_matches >= 3:
            confidence = 0.9    # 3+关键词 - 高置信度
        elif keyword_matches == 2:
            confidence = 0.75   # 2个关键词 - 中高置信度
        elif keyword_matches == 1:
            confidence = 0.6    # 1个关键词 - 中等置信度
        else:
            confidence = 0.0    # 无关键词 - 无法处理
        
        # 提升"如何做"类问题的置信度（技术教程）
        if any(phrase in content for phrase in ["how to", "how do i", "how can i", "what is", "如何", "怎么"]):
            if keyword_matches > 0:
                confidence = min(1.0, confidence + 0.15)
        
        # 检查对话历史中的技术上下文
        recent_messages = context.get_recent_messages(5)
        for msg in recent_messages:
            msg_content = msg.content.lower()
            # 如果最近的对话是技术相关的，提升置信度
            if any(keyword in msg_content for keyword in self._tech_keywords[:30]):
                confidence = min(1.0, confidence + 0.1)
                break
        
        return confidence
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        """
        生成技术相关的响应
        
        处理流程:
        1. 读取用户的技术背景
        2. 检测编程语言
        3. 识别问题类型（调试/教程/解释/优化）
        4. 生成针对性的技术指导
        5. 更新用户的技术档案
        """
        # 读取用户的技术上下文
        user_memory = self.memory_read(message.user_id)
        interaction_count = user_memory.get("interaction_count", 0)
        preferred_languages = user_memory.get("preferred_languages", [])
        
        # 分析消息内容
        content = message.get_clean_content().lower()
        
        # 检测涉及的编程语言
        detected_lang = self._detect_language(content)
        if detected_lang and detected_lang not in preferred_languages:
            preferred_languages.append(detected_lang)
        
        # 识别问题类型并生成相应响应
        if any(word in content for word in ["error", "exception", "bug", "crash", "fail", "错误", "异常", "崩溃"]):
            question_type = "debugging"
            response = self._respond_to_debugging(message, detected_lang)
        elif any(word in content for word in ["how to", "how do i", "how can i", "如何", "怎么做"]):
            question_type = "tutorial"
            response = self._respond_to_tutorial(message, detected_lang)
        elif any(word in content for word in ["what is", "explain", "difference", "什么是", "解释", "区别"]):
            question_type = "explanation"
            response = self._respond_to_explanation(message, detected_lang)
        elif any(word in content for word in ["optimize", "performance", "slow", "speed", "优化", "性能", "慢"]):
            question_type = "optimization"
            response = self._respond_to_optimization(message, detected_lang)
        else:
            question_type = "general"
            response = self._respond_general(message, interaction_count)
        
        # 更新用户记忆
        user_memory["interaction_count"] = interaction_count + 1
        user_memory["preferred_languages"] = preferred_languages[:5]  # 保留最近使用的5种语言
        user_memory["last_question_type"] = question_type
        self.memory_write(message.user_id, user_memory)
        
        return AgentResponse(
            content=response,
            agent_name=self.name,
            confidence=0.85,
            metadata={
                "question_type": question_type,
                "detected_language": detected_lang,
            },
            should_continue=False
        )
    
    def _detect_language(self, content: str) -> str:
        """
        从消息内容中检测编程语言
        
        参数:
            content: 消息内容（小写）
            
        返回值:
            str: 检测到的语言名称，如"python"、"javascript"等
        """
        languages = {
            "python": ["python", "py", "django", "flask", "fastapi", "pandas", "numpy"],
            "javascript": ["javascript", "js", "node", "react", "vue", "angular", "npm"],
            "java": ["java", "spring", "maven", "gradle"],
            "cpp": ["c++", "cpp"],
            "csharp": ["c#", "csharp", ".net", "dotnet"],
            "go": ["golang", "go"],
            "rust": ["rust", "cargo"],
        }
        
        for lang, keywords in languages.items():
            if any(kw in content for kw in keywords):
                return lang
        
        return "general"
    
    def _respond_to_debugging(self, message: Message, lang: str) -> str:
        """
        生成调试问题的响应
        
        提供系统的调试方法和步骤
        """
        lang_name = lang.title() if lang != "general" else "该语言"
        return (
            f"🐛 我来帮你调试{lang_name}问题！\n\n"
            f"让我们系统地分析：\n\n"
            f"1️⃣ 首先，识别错误信息或异常行为\n"
            f"2️⃣ 检查相关代码段，寻找常见问题\n"
            f"3️⃣ 验证输入和预期输出\n\n"
            f"📋 请提供以下信息以获得更精确的帮助：\n"
            f"• 完整的错误消息\n"
            f"• 相关的代码片段\n"
            f"• 你期望发生什么\n"
            f"• 实际发生了什么\n\n"
            f"💡 提示：越详细的信息，我越能提供针对性的解决方案！"
        )
    
    def _respond_to_tutorial(self, message: Message, lang: str) -> str:
        """
        生成教程/指导类问题的响应
        
        提供循序渐进的学习指导
        """
        lang_str = f"使用{lang.title()}" if lang != "general" else ""
        return (
            f"📚 很高兴为你{lang_str}提供指导！\n\n"
            f"我会采用循序渐进的方法：\n\n"
            f"1️⃣ 从基础配置和环境要求开始\n"
            f"2️⃣ 将任务拆解为小步骤\n"
            f"3️⃣ 实现每个步骤，添加适当的错误处理\n"
            f"4️⃣ 进行全面测试\n\n"
            f"📝 请告诉我更多信息：\n"
            f"• 你当前的开发环境和配置\n"
            f"• 你已经尝试过什么\n"
            f"• 是否有特定的约束或要求\n\n"
            f"💻 我会提供代码示例和最佳实践！"
        )
    
    def _respond_to_explanation(self, message: Message, lang: str) -> str:
        """
        生成概念解释类问题的响应
        
        清晰地解释技术概念
        """
        return (
            f"📖 好问题！让我清楚地解释这个概念：\n\n"
            f"我会从以下方面展开：\n\n"
            f"1️⃣ 定义：它是什么\n"
            f"2️⃣ 目的：为什么要使用它\n"
            f"3️⃣ 原理：它是如何工作的\n"
            f"4️⃣ 实践：何时使用它（最佳实践）\n\n"
            f"我可以提供示例和对比来帮助你更好地理解。\n"
            f"你想重点了解哪个方面？"
        )
    
    def _respond_to_optimization(self, message: Message, lang: str) -> str:
        """
        生成优化相关问题的响应
        
        提供性能优化建议
        """
        return (
            f"⚡ 让我们优化你的代码以获得更好的性能！\n\n"
            f"我的优化方法：\n\n"
            f"1️⃣ 识别瓶颈（性能分析）\n"
            f"2️⃣ 分析时间和空间复杂度\n"
            f"3️⃣ 应用适当的优化技术\n"
            f"4️⃣ 测量改进效果\n\n"
            f"🔧 常见优化策略：\n"
            f"• 算法改进\n"
            f"• 数据结构选择\n"
            f"• 缓存和记忆化\n"
            f"• 并行处理\n\n"
            f"📊 分享你的代码，我会提供具体的优化建议！"
        )
    
    def _respond_general(self, message: Message, interaction_count: int) -> str:
        """
        生成通用技术响应
        
        用于无明确问题类型的情况
        """
        if interaction_count == 0:
            return (
                "👨‍💻 你好！我是技术支持Agent。\n\n"
                "我可以帮助你：\n"
                "• 编程问题解答\n"
                "• 代码调试\n"
                "• 系统管理\n"
                "• 技术概念解释\n\n"
                "今天遇到什么技术问题了吗？"
            )
        else:
            return (
                "💡 我在这里帮助你解决技术问题。\n\n"
                "无论是编程、调试、架构还是技术解释，\n"
                "我都会尽力提供清晰实用的指导。\n\n"
                "你想了解什么？"
            )
    
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        """
        读取用户的技术档案
        
        存储内容：
        - interaction_count: 交互次数
        - preferred_languages: 偏好的编程语言
        - last_question_type: 最后的问题类型
        """
        return self._memory.read(self.name, user_id)
    
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        """
        保存用户的技术档案
        
        用于了解用户的技术背景，提供个性化帮助
        """
        self._memory.write(self.name, user_id, data)
