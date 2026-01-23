"""
情感支持Agent

专门处理情感相关的对话，提供心理支持和陪伴服务。
这是SoulmateBot提供情感价值的核心Agent。

设计理念:
- Agent专注于提供技能（情感支持、情绪追踪等）
- Bot作为人格外壳，通过配置选择启用Agent的技能
"""
from typing import Dict, Any, List, Optional
from src.agents import BaseAgent, Message, ChatContext, AgentResponse, MemoryStore, SQLiteMemoryStore


class EmotionalAgent(BaseAgent):
    """
    情感支持Agent - 提供情感价值的核心
    
    专长领域:
    - 情绪识别：悲伤、焦虑、快乐、愤怒等
    - 情感倾诉：倾听用户的烦恼和困扰
    - 心理疏导：提供安慰、鼓励和支持
    - 日常陪伴：温暖的日常对话
    
    适用场景:
    - 用户表达情绪（"我很难过"、"今天很开心"）
    - 寻求安慰和理解
    - 需要倾诉对象
    - 心理压力疏导
    """
    
    def __init__(self, memory_store: MemoryStore = None):
        """
        初始化情感支持Agent
        
        参数:
            memory_store: 可选的记忆存储实例，用于记住用户的情感历史
        """
        self._name = "EmotionalAgent"
        self._description = (
            "提供情感支持和共情响应。"
            "专注于理解和回应用户的感受、"
            "心理健康问题和个人困扰。"
        )
        self._memory = memory_store or SQLiteMemoryStore()
        
        # 情感相关的关键词库 - 用于识别情感内容
        self._emotional_keywords = [
            # 情绪词汇
            "feel", "feeling", "felt", "emotion", "emotional",
            "sad", "happy", "angry", "anxious", "worried", "stressed",
            "depressed", "lonely", "tired", "exhausted", "frustrated",
            "excited", "nervous", "scared", "afraid", "hopeful",
            
            # 中文情绪词
            "感觉", "情绪", "心情", "难过", "开心", "快乐", "生气",
            "焦虑", "担心", "压力", "抑郁", "孤独", "累", "疲惫",
            "沮丧", "兴奋", "紧张", "害怕", "希望",
            
            # 心理健康
            "mental", "health", "therapy", "counseling", "depression",
            "anxiety", "panic", "overwhelmed", "burnout",
            
            # 个人问题
            "problem", "issue", "struggle", "difficult", "hard",
            "upset", "hurt", "pain", "suffering",
            
            # 寻求支持
            "help", "support", "advice", "listen", "talk",
            "understand", "comfort", "care",
            
            # 情感表达
            "cry", "crying", "tears", "smile", "laugh", "sigh",
        ]
    
    @property
    def name(self) -> str:
        """Agent名称"""
        return self._name
    
    @property
    def description(self) -> str:
        """Agent描述"""
        return self._description
    
    @property
    def skills(self) -> List[str]:
        """
        Agent提供的技能列表
        
        EmotionalAgent提供以下技能:
        - emotional_support: 情感支持
        - mood_tracking: 情绪追踪
        """
        return ["emotional_support", "mood_tracking"]
    
    @property
    def skill_keywords(self) -> Dict[str, List[str]]:
        """
        技能对应的关键词映射
        """
        return {
            "emotional_support": [
                "难过", "开心", "焦虑", "压力", "心情", "feel", "sad", "happy",
                "孤独", "累", "疲惫", "抑郁", "担心", "紧张"
            ],
            "mood_tracking": [
                "心情", "情绪", "记录", "追踪", "变化", "mood", "track", "log"
            ]
        }
    
    def get_skill_description(self, skill_id: str) -> Optional[str]:
        """获取指定技能的描述"""
        skill_descriptions = {
            "emotional_support": "倾听心声，提供情感陪伴和支持",
            "mood_tracking": "记录和追踪情绪变化，帮助了解情绪规律"
        }
        return skill_descriptions.get(skill_id)
    
    def can_handle(self, message: Message, context: ChatContext) -> float:
        """
        判断是否能处理此消息
        
        对于包含情感内容的消息返回高置信度。
        
        判断逻辑:
        1. 检查是否被@提及（返回1.0）
        2. 统计情感关键词出现次数
        3. 根据关键词数量返回置信度
        4. 检查对话历史中的情感上下文
        
        返回值:
            float: 置信度分数 (0.0-1.0)
        """
        # 检查显式@提及
        if message.has_mention(self.name):
            return 1.0
        
        content = message.content.lower()
        
        # 统计情感关键词匹配数
        keyword_matches = sum(1 for keyword in self._emotional_keywords if keyword in content)
        
        # 根据匹配数计算置信度
        # 更多关键词 = 更高置信度
        if keyword_matches >= 3:
            confidence = 0.9   # 3个以上关键词 - 高置信度
        elif keyword_matches == 2:
            confidence = 0.7   # 2个关键词 - 中高置信度
        elif keyword_matches == 1:
            confidence = 0.5   # 1个关键词 - 中等置信度
        else:
            confidence = 0.0   # 无关键词 - 无法处理
        
        # 如果有问号且有情感关键词，提升置信度（寻求帮助）
        if "?" in content and keyword_matches > 0:
            confidence = min(1.0, confidence + 0.1)
        
        # 检查最近对话历史中的情感上下文
        recent_messages = context.get_recent_messages(5)
        for msg in recent_messages:
            msg_content = msg.content.lower()
            # 如果最近的对话包含情感内容，提升置信度
            if any(keyword in msg_content for keyword in self._emotional_keywords[:20]):
                confidence = min(1.0, confidence + 0.1)
                break
        
        return confidence
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        """
        生成富有共情的响应
        
        处理流程:
        1. 读取用户的情感历史
        2. 识别当前的主要情绪
        3. 生成个性化的共情响应
        4. 更新用户记忆
        """
        # 读取用户的情感交互历史
        user_memory = self.memory_read(message.user_id)
        interaction_count = user_memory.get("interaction_count", 0)
        
        # 分析消息内容
        content = message.get_clean_content().lower()
        
        # 识别主要情绪并生成对应响应
        if any(word in content for word in ["sad", "depressed", "down", "unhappy", "难过", "抑郁"]):
            emotion = "sadness"
            response = self._respond_to_sadness(message, interaction_count)
        elif any(word in content for word in ["anxious", "worried", "nervous", "stressed", "焦虑", "担心", "紧张", "压力"]):
            emotion = "anxiety"
            response = self._respond_to_anxiety(message, interaction_count)
        elif any(word in content for word in ["happy", "excited", "great", "wonderful", "开心", "快乐", "兴奋"]):
            emotion = "happiness"
            response = self._respond_to_happiness(message, interaction_count)
        elif any(word in content for word in ["angry", "frustrated", "mad", "annoyed", "生气", "沮丧", "愤怒"]):
            emotion = "anger"
            response = self._respond_to_anger(message, interaction_count)
        else:
            emotion = "general"
            response = self._respond_general(message, interaction_count)
        
        # 更新用户记忆
        user_memory["interaction_count"] = interaction_count + 1
        user_memory["last_emotion"] = emotion
        user_memory["last_message"] = message.content
        self.memory_write(message.user_id, user_memory)
        
        return AgentResponse(
            content=response,
            agent_name=self.name,
            confidence=0.85,
            metadata={"emotion_detected": emotion},
            should_continue=False  # 情感支持通常是独占的
        )
    
    def _respond_to_sadness(self, message: Message, interaction_count: int) -> str:
        """
        生成针对悲伤情绪的响应
        
        根据交互次数调整响应内容，提供个性化支持
        """
        if interaction_count == 0:
            return (
                "⬇️_respond_to_sadness固定模板"
                "很抱歉你现在感到难过。感到悲伤是很正常的，"
                "每个人都会有情绪低落的时候。"
                "你愿意和我聊聊是什么让你烦恼吗？我在这里倾听。"
            )
        else:
            return (
                "⬇️_respond_to_sadness固定模板"
                "我理解你正在经历一段艰难的时期。"
                "请记住，这些感受是暂时的，而且你愿意分享已经很勇敢了。"
                "现在有什么能让你感觉好一点的吗？"
            )
    
    def _respond_to_anxiety(self, message: Message, interaction_count: int) -> str:
        """
        生成针对焦虑情绪的响应
        
        提供平静和支持，帮助用户缓解焦虑
        """
        return (
            "听起来你现在感到焦虑或担心。这种感觉确实很难受。"
            "让我们一步一步来处理。"
            "能告诉我是什么让你有这种感觉吗？"
            "有时候，仅仅是把它说出来就会有帮助。"
        )
    
    def _respond_to_happiness(self, message: Message, interaction_count: int) -> str:
        """
        生成针对快乐情绪的响应
        
        分享用户的喜悦，强化积极情绪
        """
        return (
            "太棒了！我真为你感到高兴！"
            "听到好消息真是令人开心。"
            "是什么让你今天这么开心呢？我很想听听更多！"
        )
    
    def _respond_to_anger(self, message: Message, interaction_count: int) -> str:
        """
        生成针对愤怒情绪的响应
        
        理解并验证用户的情绪，提供宣泄渠道
        """
        return (
            "我能感觉到你现在很沮丧或生气。"
            "这些感受是完全正当的，承认它们很重要。"
            "愿意谈谈发生了什么吗？"
            "我会不带评判地倾听。"
        )
    
    def _respond_general(self, message: Message, interaction_count: int) -> str:
        """
        生成通用的共情响应
        
        用于无明确情绪或首次交互的情况
        """
        if interaction_count == 0:
            return (
                "你好！我是情感支持助手，"
                "我在这里倾听你想分享的任何事情。"
                "你今天感觉怎么样？"
            )
        else:
            return (
                "我在这里支持你。告诉我你在想什么。"
                "无论你正在经历什么，我都会倾听并尽我所能提供帮助。"
            )
    
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        """
        读取用户的情感历史记忆
        
        存储内容包括：
        - interaction_count: 交互次数
        - last_emotion: 上次识别的情绪
        - last_message: 上次的消息内容
        """
        return self._memory.read(self.name, user_id)
    
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        """
        保存用户的情感历史记忆
        
        用于持久化用户的情感状态和交互历史，
        以便下次交互时提供更个性化的支持
        """
        self._memory.write(self.name, user_id, data)
