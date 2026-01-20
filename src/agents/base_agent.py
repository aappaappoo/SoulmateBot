"""
Agent基础类接口

所有Agent都必须继承并实现这个基类。
这是多Agent系统的核心抽象，定义了Agent的标准接口。
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from .models import Message, ChatContext, AgentResponse


class BaseAgent(ABC):
    """
    Agent抽象基类
    
    所有自定义Agent必须继承此类并实现以下方法：
    - name: str property - Agent的唯一名称
    - description: str property - Agent的功能描述
    - can_handle(message, context) -> float - 判断能否处理消息（返回0-1的置信度）
    - respond(message, context) -> AgentResponse - 生成响应
    - memory_read(user_id) -> dict - 读取用户记忆
    - memory_write(user_id, data) -> None - 保存用户记忆
    
    使用示例:
        class MyAgent(BaseAgent):
            @property
            def name(self):
                return "MyAgent"
            
            def can_handle(self, message, context):
                return 0.8  # 高置信度
            
            def respond(self, message, context):
                return AgentResponse(content="响应内容", ...)
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Agent的唯一名称
        
        返回值:
            Agent名称，如 "EmotionalAgent", "TechAgent"
            
        注意:
            - 名称必须唯一，用于路由和@提及
            - 建议使用驼峰命名法
        """
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """
        Agent的功能描述
        
        返回值:
            描述Agent的用途和能力的文本
            
        示例:
            "提供情感支持和心理疏导的专业Agent"
        """
        pass
    
    @abstractmethod
    def can_handle(self, message: Message, context: ChatContext) -> float:
        """
        判断此Agent能否处理给定的消息
        
        Router会调用所有Agent的此方法来选择最合适的Agent。
        返回一个0.0到1.0之间的置信度分数：
        
        置信度等级:
        - 0.0: 完全无法处理此消息
        - 0.1-0.4: 低置信度，仅在没有更好的Agent时响应
        - 0.5-0.7: 中等置信度，可以adequately处理
        - 0.8-1.0: 高置信度，非常适合处理此消息
        
        参数:
            message: 收到的消息对象
            context: 聊天上下文，包含历史对话
            
        返回值:
            float: 置信度分数 (0.0 - 1.0)
            
        实现建议:
        - 检查消息是否@提及了此Agent（返回1.0）
        - 分析消息内容中的关键词
        - 考虑对话历史和上下文
        - 使用机器学习模型进行意图识别
        """
        pass
    
    @abstractmethod
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        """
        生成对消息的响应
        
        当Router选中此Agent后，会调用此方法生成响应。
        
        参数:
            message: 要响应的消息
            context: 聊天上下文，包含历史对话
            
        返回值:
            AgentResponse: 包含响应内容和元数据的响应对象
            
        实现建议:
        1. 读取用户的历史记忆（memory_read）
        2. 分析消息内容和上下文
        3. 生成个性化的响应
        4. 更新用户记忆（memory_write）
        5. 返回AgentResponse对象
        
        注意:
        - 响应应该与Agent的专长一致
        - 考虑用户的历史交互
        - 适当处理异常情况
        """
        pass
    
    @abstractmethod
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        """
        读取特定用户的持久化记忆
        
        记忆系统允许Agent记住用户的偏好、历史对话等信息，
        从而提供更个性化的服务。
        
        参数:
            user_id: 用户唯一标识符
            
        返回值:
            Dict[str, Any]: 包含用户数据的字典
            
        典型用例:
        - 记住用户偏好（如编程语言、兴趣等）
        - 追踪交互次数
        - 存储上次对话的情绪状态
        """
        pass
    
    @abstractmethod
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        """
        写入特定用户的持久化记忆
        
        保存用户数据，供下次交互时使用。
        
        参数:
            user_id: 用户唯一标识符
            data: 要保存的数据字典
            
        注意:
        - 数据会被持久化存储
        - 注意数据隐私和安全
        - 避免存储敏感信息
        """
        pass
    
    def __repr__(self) -> str:
        """Agent的字符串表示"""
        return f"<{self.__class__.__name__}(name='{self.name}')>"
