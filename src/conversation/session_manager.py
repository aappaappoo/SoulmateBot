"""
Session Manager - 会话管理器

管理用户对话会话，包括：
- 会话创建和销毁
- 会话状态追踪
- 对话历史管理
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from loguru import logger


@dataclass
class Message:
    """对话消息"""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, str]:
        """转换为LLM API格式"""
        return {
            "role": self.role,
            "content": self.content
        }


@dataclass
class Session:
    """
    用户会话
    
    Attributes:
        session_id: 会话唯一ID
        user_id: 用户ID
        bot_id: Bot ID
        messages: 对话消息列表
        context: 会话上下文数据
        created_at: 创建时间
        updated_at: 最后更新时间
        expires_at: 过期时间
        is_active: 是否活跃
    """
    session_id: str
    user_id: str
    bot_id: str
    messages: List[Message] = field(default_factory=list)
    system_prompt: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    max_messages: int = 50  # 最大消息数限制
    is_active: bool = True

    def _trim_messages(self) -> None:
        """
        修剪消息列表，保持在最大限制内

        只保留最近的 max_messages 条消息
        """
        if len(self.messages) > self.max_messages:
            # 保留最新的消息
            self.messages = self.messages[-self.max_messages:]

    def set_system_prompt(self, content: str) -> None:
        """设置系统提示词（不放入消息列表）"""
        self.system_prompt = content
        self.updated_at = datetime.now(timezone.utc)

    def add_user_message(self, content: str, metadata: Optional[Dict] = None) -> Message:
        """添加用户消息"""
        message = Message(role="user", content=content, metadata=metadata or {})
        self.messages.append(message)
        self._trim_messages()
        return message

    def add_assistant_message(self, content: str, metadata: Optional[Dict] = None) -> Message:
        """添加助手回复"""
        message = Message(role="assistant", content=content, metadata=metadata or {})
        self.messages.append(message)
        self._trim_messages()
        return message

    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None) -> Message:
        """添加消息到会话"""
        message = Message(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc)
        return message

    
    def get_messages(self, limit: Optional[int] = None) -> List[Message]:
        """获取消息列表"""
        if limit:
            return self.messages[-limit:]
        return self.messages
    

    def get_messages_for_llm(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """获取适用于LLM API的消息格式"""
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        history = self.get_messages(limit)
        for msg in history:
            if msg.role in ("user", "assistant"):
                messages.append(msg.to_dict())
        return messages

    def get_conversation_history(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """获取纯对话历史（不含 system prompt）"""
        history = self.get_messages(limit)
        return [msg.to_dict() for msg in history if msg.role in ("user", "assistant")]

    def get_last_message(self) -> Optional[Message]:
        """获取最后一条消息"""
        return self.messages[-1] if self.messages else None
    
    def clear_messages(self) -> None:
        """清空消息历史"""
        self.messages = []
        self.updated_at = datetime.now(timezone.utc)
    
    def is_expired(self) -> bool:
        """检查会话是否已过期"""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def extend_expiry(self, minutes: int = 30) -> None:
        """延长会话过期时间"""
        self.expires_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        self.updated_at = datetime.now(timezone.utc)
    
    def set_context(self, key: str, value: Any) -> None:
        """设置上下文数据"""
        self.context[key] = value
        self.updated_at = datetime.now(timezone.utc)
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """获取上下文数据"""
        return self.context.get(key, default)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "bot_id": self.bot_id,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "metadata": m.metadata
                }
                for m in self.messages
            ],
            "context": self.context,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active
        }


class SessionManager:
    """
    会话管理器
    
    负责创建、存储和管理用户会话
    """
    
    def __init__(
        self,
        default_expiry_minutes: int = 30,
        max_sessions_per_user: int = 5,
        max_messages_per_session: int = 100
    ):
        """
        初始化会话管理器
        
        Args:
            default_expiry_minutes: 默认会话过期时间（分钟）
            max_sessions_per_user: 每用户最大会话数
            max_messages_per_session: 每会话最大消息数
        """
        self.default_expiry_minutes = default_expiry_minutes
        self.max_sessions_per_user = max_sessions_per_user
        self.max_messages_per_session = max_messages_per_session
        
        # 会话存储: session_id -> Session
        self._sessions: Dict[str, Session] = {}
        
        # 用户索引: user_id -> List[session_id]
        self._user_sessions: Dict[str, List[str]] = {}
        
        logger.info(
            f"SessionManager initialized: expiry={default_expiry_minutes}min, "
            f"max_sessions={max_sessions_per_user}, max_messages={max_messages_per_session}"
        )
    
    def _generate_session_id(self, user_id: str, bot_id: str) -> str:
        """生成会话ID"""
        import uuid
        return f"{user_id}:{bot_id}:{uuid.uuid4().hex[:8]}"
    
    def create_session(
        self,
        user_id: str,
        bot_id: str,
        system_prompt: Optional[str] = None,
        context: Optional[Dict] = None,
        expiry_minutes: Optional[int] = None
    ) -> Session:
        """
        创建新会话
        
        Args:
            user_id: 用户ID
            bot_id: Bot ID
            system_prompt: 系统提示词
            context: 初始上下文
            expiry_minutes: 过期时间（分钟）
            
        Returns:
            新创建的会话
        """
        # 检查用户会话数量限制
        if user_id in self._user_sessions:
            if len(self._user_sessions[user_id]) >= self.max_sessions_per_user:
                # 清理最旧的会话
                oldest_session_id = self._user_sessions[user_id][0]
                self.delete_session(oldest_session_id)
        
        session_id = self._generate_session_id(user_id, bot_id)
        expiry = expiry_minutes or self.default_expiry_minutes
        
        session = Session(
            session_id=session_id,
            user_id=user_id,
            bot_id=bot_id,
            context=context or {},
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=expiry)
        )
        
        # 添加系统提示词
        if system_prompt:
            session.add_system_message(system_prompt)
        
        # 存储会话
        self._sessions[session_id] = session
        
        # 更新用户索引
        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = []
        self._user_sessions[user_id].append(session_id)
        
        logger.info(f"Created session: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        session = self._sessions.get(session_id)
        
        if session and session.is_expired():
            logger.info(f"Session expired: {session_id}")
            self.delete_session(session_id)
            return None
        
        return session
    
    def get_or_create_session(
        self,
        user_id: str,
        bot_id: str,
        system_prompt: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> Session:
        """
        获取或创建会话
        
        如果用户与指定Bot有活跃会话则返回，否则创建新会话
        """
        # 查找用户与该Bot的现有会话
        if user_id in self._user_sessions:
            for session_id in self._user_sessions[user_id]:
                session = self.get_session(session_id)
                if session and session.bot_id == bot_id and session.is_active:
                    # 延长过期时间
                    session.extend_expiry(self.default_expiry_minutes)
                    return session
        
        # 创建新会话
        return self.create_session(user_id, bot_id, system_prompt, context)
    
    def get_user_sessions(self, user_id: str) -> List[Session]:
        """获取用户的所有会话"""
        sessions = []
        if user_id in self._user_sessions:
            for session_id in self._user_sessions[user_id]:
                session = self.get_session(session_id)
                if session:
                    sessions.append(session)
        return sessions
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id not in self._sessions:
            return False
        
        session = self._sessions[session_id]
        
        # 从用户索引中移除
        if session.user_id in self._user_sessions:
            if session_id in self._user_sessions[session.user_id]:
                self._user_sessions[session.user_id].remove(session_id)
            if not self._user_sessions[session.user_id]:
                del self._user_sessions[session.user_id]
        
        # 删除会话
        del self._sessions[session_id]
        logger.info(f"Deleted session: {session_id}")
        return True
    
    def add_message_to_session(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> Optional[Message]:
        """向会话添加消息"""
        session = self.get_session(session_id)
        if not session:
            return None
        
        # 检查消息数量限制
        if len(session.messages) >= self.max_messages_per_session:
            # 保留system消息，删除最早的用户/助手消息
            non_system_start = next(
                (i for i, m in enumerate(session.messages) if m.role != "system"),
                0
            )
            if non_system_start < len(session.messages):
                session.messages.pop(non_system_start)
        
        return session.add_message(role, content, metadata)
    
    def cleanup_expired(self) -> int:
        """清理过期会话"""
        expired = []
        for session_id, session in self._sessions.items():
            if session.is_expired():
                expired.append(session_id)
        
        for session_id in expired:
            self.delete_session(session_id)
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")
        
        return len(expired)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        active_sessions = sum(1 for s in self._sessions.values() if s.is_active and not s.is_expired())
        total_messages = sum(len(s.messages) for s in self._sessions.values())
        
        return {
            "total_sessions": len(self._sessions),
            "active_sessions": active_sessions,
            "total_users": len(self._user_sessions),
            "total_messages": total_messages
        }


# 全局会话管理器实例
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """获取全局会话管理器"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
