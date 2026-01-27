"""
Conversation Memory Service - 对话记忆服务

提供RAG技术驱动的对话记忆功能：
1. 分析对话，判断是否包含重要事件（过滤日常寒暄）
2. 提取并保存重要事件到数据库
3. 检索与当前对话相关的历史记忆
4. 用于增强Bot的个性化对话能力

使用方法：
    from src.services.conversation_memory_service import ConversationMemoryService
    
    service = ConversationMemoryService(db_session, llm_provider)
    
    # 保存重要对话事件
    await service.extract_and_save_important_events(
        user_id=123,
        bot_id=456,
        user_message="我下个月15号生日",
        bot_response="太棒了！我记住了，下个月15号是你的生日..."
    )
    
    # 检索相关记忆
    memories = await service.retrieve_memories(
        user_id=123,
        bot_id=456,
        current_message="你还记得我的生日吗？"
    )
"""
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, func
from loguru import logger

from src.models.database import UserMemory, MemoryImportance


class ConversationMemoryService:
    """
    对话记忆服务
    
    使用LLM分析对话重要性，存储重要事件，并在需要时检索相关记忆。
    """
    
    # 用于判断重要性的系统提示词
    IMPORTANCE_ANALYSIS_PROMPT = """你是一个智能记忆分析助手。你的任务是分析用户和AI助手之间的对话，判断是否包含值得记住的重要事件。

重要事件包括：
- 个人信息：生日、年龄、职业、家庭成员、居住地等
- 重要偏好：喜欢/不喜欢的事物、兴趣爱好、习惯等
- 重要目标：学习计划、工作目标、人生规划等
- 情感事件：重要的情感表达、心理状态变化等
- 生活事件：毕业、求职、结婚、生病、搬家等重大事件
- 人际关系：朋友、家人、同事等重要关系

不重要的事件（应该过滤）：
- 日常寒暄：你好、再见、谢谢、早上好等
- 简单问答：今天天气怎么样、现在几点了等
- 无个人信息的技术问题：如何写代码、解释概念等
- 一次性话题：无需长期记忆的临时话题

请以JSON格式返回分析结果：
{
    "is_important": true/false,
    "importance_level": "low/medium/high/critical",
    "event_type": "preference/birthday/goal/emotion/life_event/relationship/other",
    "event_summary": "简洁的事件摘要（如果重要的话）",
    "keywords": ["关键词1", "关键词2"],
    "event_date": "YYYY-MM-DD（如果提到具体日期）或 null"
}

只返回JSON，不要其他内容。"""

    # 用于检索相关记忆的系统提示词
    MEMORY_RETRIEVAL_PROMPT = """你是一个智能记忆检索助手。根据用户当前的消息，从历史记忆中找出最相关的记忆。

请分析当前消息可能需要回忆的内容类型，例如：
- 用户询问"你还记得我吗"时，需要回忆用户的基本信息
- 用户提到生日相关话题时，需要回忆生日相关的记忆
- 用户讨论工作时，需要回忆职业和工作目标相关的记忆

请以JSON格式返回检索建议：
{
    "should_retrieve": true/false,
    "relevance_keywords": ["关键词1", "关键词2"],
    "event_types": ["preference", "goal", "emotion"]
}

只返回JSON，不要其他内容。"""

    def __init__(
        self,
        db: AsyncSession,
        llm_provider=None,
        max_memories_per_query: int = 5,
        importance_threshold: str = "medium"
    ):
        """
        初始化对话记忆服务
        
        Args:
            db: 异步数据库会话
            llm_provider: LLM提供者（用于重要性分析和记忆检索）
            max_memories_per_query: 每次检索返回的最大记忆数量
            importance_threshold: 保存记忆的最低重要性阈值
        """
        self.db = db
        self.llm_provider = llm_provider
        self.max_memories_per_query = max_memories_per_query
        self.importance_threshold = importance_threshold
        
        # 重要性级别排序
        self._importance_order = {
            MemoryImportance.LOW.value: 0,
            MemoryImportance.MEDIUM.value: 1,
            MemoryImportance.HIGH.value: 2,
            MemoryImportance.CRITICAL.value: 3
        }
        
        logger.info("ConversationMemoryService initialized")
    
    async def analyze_importance(
        self,
        user_message: str,
        bot_response: str
    ) -> Dict[str, Any]:
        """
        分析对话的重要性
        
        使用LLM分析用户消息和Bot回复，判断是否包含重要事件。
        
        Args:
            user_message: 用户消息
            bot_response: Bot回复
            
        Returns:
            Dict包含分析结果：is_important, importance_level, event_type等
        """
        if not self.llm_provider:
            # 如果没有LLM，使用简单的规则判断
            return self._analyze_importance_rule_based(user_message)
        
        try:
            analysis_prompt = f"""用户消息: {user_message}
AI回复: {bot_response}

请分析这段对话是否包含值得记住的重要事件。"""
            
            response = await self.llm_provider.generate_response(
                [{"role": "user", "content": analysis_prompt}],
                context=self.IMPORTANCE_ANALYSIS_PROMPT
            )
            
            # 解析JSON响应
            response_text = response.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            result = json.loads(response_text.strip())
            logger.debug(f"Importance analysis result: {result}")
            return result
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse importance analysis response: {e}")
            return {"is_important": False}
        except Exception as e:
            logger.error(f"Error in importance analysis: {e}")
            return {"is_important": False}
    
    def _analyze_importance_rule_based(self, user_message: str) -> Dict[str, Any]:
        """
        基于规则的重要性分析（当没有LLM时使用）
        
        使用关键词匹配进行简单的重要性判断。
        """
        message_lower = user_message.lower()
        
        # 日常寒暄关键词（低重要性）
        greetings = ["你好", "hello", "hi", "再见", "bye", "谢谢", "thanks", 
                     "早上好", "晚上好", "早安", "晚安", "good morning", "good night"]
        
        if any(greeting in message_lower for greeting in greetings) and len(user_message) < 20:
            return {"is_important": False}
        
        # 重要事件关键词
        important_keywords = {
            "birthday": ["生日", "birthday", "出生"],
            "preference": ["喜欢", "不喜欢", "爱好", "兴趣", "喜好", "favorite", "prefer"],
            "goal": ["目标", "计划", "打算", "想要", "希望", "goal", "plan"],
            "life_event": ["毕业", "工作", "结婚", "搬家", "生病", "恋爱"],
            "emotion": ["难过", "开心", "焦虑", "压力", "担心", "害怕"],
            "relationship": ["朋友", "家人", "父母", "孩子", "男朋友", "女朋友"]
        }
        
        for event_type, keywords in important_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                return {
                    "is_important": True,
                    "importance_level": MemoryImportance.MEDIUM.value,
                    "event_type": event_type,
                    "event_summary": user_message[:100],
                    "keywords": [kw for kw in keywords if kw in message_lower],
                    "event_date": None
                }
        
        return {"is_important": False}
    
    async def extract_and_save_important_events(
        self,
        user_id: int,
        bot_id: Optional[int],
        user_message: str,
        bot_response: str
    ) -> Optional[UserMemory]:
        """
        提取并保存重要对话事件
        
        分析对话内容，如果包含重要事件则保存到数据库。
        
        Args:
            user_id: 用户ID
            bot_id: Bot ID
            user_message: 用户消息
            bot_response: Bot回复
            
        Returns:
            保存的UserMemory对象，如果不重要则返回None
        """
        # 分析重要性
        analysis = await self.analyze_importance(user_message, bot_response)
        
        if not analysis.get("is_important", False):
            logger.debug(f"Message not important, skipping memory save for user {user_id}")
            return None
        
        # 检查重要性级别是否达到阈值
        importance_level = analysis.get("importance_level", MemoryImportance.MEDIUM.value)
        if self._importance_order.get(importance_level, 0) < self._importance_order.get(self.importance_threshold, 1):
            logger.debug(f"Importance level {importance_level} below threshold {self.importance_threshold}")
            return None
        
        # 解析事件日期
        event_date = None
        if analysis.get("event_date"):
            try:
                event_date = datetime.strptime(analysis["event_date"], "%Y-%m-%d")
            except (ValueError, TypeError):
                pass
        
        # 创建记忆对象
        memory = UserMemory(
            user_id=user_id,
            bot_id=bot_id,
            event_summary=analysis.get("event_summary", user_message[:200]),
            user_message=user_message,
            bot_response=bot_response,
            importance=importance_level,
            event_type=analysis.get("event_type"),
            keywords=analysis.get("keywords", []),
            event_date=event_date
        )
        
        self.db.add(memory)
        await self.db.commit()
        await self.db.refresh(memory)
        
        logger.info(f"Saved important memory for user {user_id}: {memory.event_summary[:50]}...")
        return memory
    
    async def retrieve_memories(
        self,
        user_id: int,
        bot_id: Optional[int] = None,
        current_message: Optional[str] = None,
        event_types: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[UserMemory]:
        """
        检索用户的相关记忆
        
        根据当前消息内容或指定条件检索用户的历史记忆。
        
        Args:
            user_id: 用户ID
            bot_id: Bot ID（可选，指定则只检索该Bot相关的记忆）
            current_message: 当前消息（用于智能匹配相关记忆）
            event_types: 事件类型过滤列表
            limit: 返回数量限制
            
        Returns:
            相关记忆列表
        """
        limit = limit or self.max_memories_per_query
        
        # 构建基础查询
        query = select(UserMemory).where(
            and_(
                UserMemory.user_id == user_id,
                UserMemory.is_active == True
            )
        )
        
        # 如果指定了Bot ID，添加过滤
        if bot_id is not None:
            query = query.where(
                or_(
                    UserMemory.bot_id == bot_id,
                    UserMemory.bot_id.is_(None)  # 也包括通用记忆
                )
            )
        
        # 如果指定了事件类型，添加过滤
        if event_types:
            query = query.where(UserMemory.event_type.in_(event_types))
        
        # 如果有当前消息，尝试智能匹配
        relevant_keywords = []
        if current_message and self.llm_provider:
            try:
                retrieval_analysis = await self._analyze_retrieval_needs(current_message)
                if retrieval_analysis.get("should_retrieve", False):
                    relevant_keywords = retrieval_analysis.get("relevance_keywords", [])
                    if retrieval_analysis.get("event_types"):
                        query = query.where(
                            UserMemory.event_type.in_(retrieval_analysis["event_types"])
                        )
            except Exception as e:
                logger.warning(f"Error in retrieval analysis: {e}")
        
        # 按重要性和访问时间排序
        query = query.order_by(
            UserMemory.importance.desc(),
            UserMemory.last_accessed_at.desc().nullsfirst(),
            UserMemory.created_at.desc()
        ).limit(limit)
        
        result = await self.db.execute(query)
        memories = list(result.scalars().all())
        
        # 更新访问计数和时间
        if memories:
            memory_ids = [m.id for m in memories]
            await self.db.execute(
                update(UserMemory)
                .where(UserMemory.id.in_(memory_ids))
                .values(
                    access_count=UserMemory.access_count + 1,
                    last_accessed_at=datetime.now(timezone.utc)
                )
            )
            await self.db.commit()
        
        logger.info(f"Retrieved {len(memories)} memories for user {user_id}")
        return memories
    
    async def _analyze_retrieval_needs(self, current_message: str) -> Dict[str, Any]:
        """
        分析当前消息的记忆检索需求
        
        使用LLM判断当前消息是否需要回忆历史记忆。
        """
        try:
            response = await self.llm_provider.generate_response(
                [{"role": "user", "content": f"用户消息: {current_message}"}],
                context=self.MEMORY_RETRIEVAL_PROMPT
            )
            
            response_text = response.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            return json.loads(response_text.strip())
            
        except Exception as e:
            logger.warning(f"Error in retrieval analysis: {e}")
            return {"should_retrieve": False}
    
    async def format_memories_for_context(
        self,
        memories: List[UserMemory],
        max_chars: int = 1000
    ) -> str:
        """
        将记忆格式化为可注入到对话上下文的字符串
        
        Args:
            memories: 记忆列表
            max_chars: 最大字符数限制
            
        Returns:
            格式化的记忆字符串
        """
        if not memories:
            return ""
        
        memory_texts = []
        current_length = 0
        
        for memory in memories:
            memory_text = f"- {memory.event_summary}"
            if memory.event_date:
                memory_text += f" (日期: {memory.event_date.strftime('%Y-%m-%d')})"
            
            if current_length + len(memory_text) > max_chars:
                break
            
            memory_texts.append(memory_text)
            current_length += len(memory_text)
        
        if not memory_texts:
            return ""
        
        return "【关于这位用户的记忆】\n" + "\n".join(memory_texts)
    
    async def delete_memory(self, memory_id: int) -> bool:
        """
        软删除指定记忆
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            是否删除成功
        """
        result = await self.db.execute(
            update(UserMemory)
            .where(UserMemory.id == memory_id)
            .values(is_active=False, updated_at=datetime.now(timezone.utc))
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def get_user_memory_stats(self, user_id: int) -> Dict[str, Any]:
        """
        获取用户记忆统计信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            统计信息字典
        """
        # 总记忆数
        total_query = select(func.count(UserMemory.id)).where(
            and_(UserMemory.user_id == user_id, UserMemory.is_active == True)
        )
        total_result = await self.db.execute(total_query)
        total_count = total_result.scalar() or 0
        
        # 按事件类型分组统计
        type_query = select(
            UserMemory.event_type,
            func.count(UserMemory.id)
        ).where(
            and_(UserMemory.user_id == user_id, UserMemory.is_active == True)
        ).group_by(UserMemory.event_type)
        
        type_result = await self.db.execute(type_query)
        type_counts = {row[0]: row[1] for row in type_result.all()}
        
        return {
            "total_memories": total_count,
            "by_event_type": type_counts
        }


# 全局服务实例获取函数
_memory_service_cache: Dict[str, ConversationMemoryService] = {}


def get_conversation_memory_service(
    db: AsyncSession,
    llm_provider=None
) -> ConversationMemoryService:
    """
    获取对话记忆服务实例
    
    Args:
        db: 数据库会话
        llm_provider: LLM提供者
        
    Returns:
        ConversationMemoryService实例
    """
    return ConversationMemoryService(db, llm_provider)
