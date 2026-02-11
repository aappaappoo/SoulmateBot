"""
Conversation Summary Service - 对话摘要服务

提供对话历史的摘要功能，支持：
1. 规则摘要（不消耗 token）- 基于启发式规则提取关键信息
2. LLM 摘要（可选）- 使用 LLM 生成高质量摘要
3. 返回结构化的摘要数据（摘要文本、关键话题、情绪轨迹、用户需求）

用于节省 token，将中期对话（第 3-20 轮）压缩为摘要

回退行为：
- 当 use_llm=True 但 llm_provider 不可用时，自动回退到规则摘要
- 当 LLM API 调用失败时，记录警告并回退到规则摘要
- 规则摘要始终可用，不依赖外部服务
"""
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger


@dataclass
class ConversationSummary:
    """
    对话摘要结构
    
    Attributes:
        summary_text: 摘要文本
        key_topics: 关键话题列表
        emotion_trajectory: 情绪轨迹（用户情绪变化）
        user_needs: 用户需求或关注点
        turn_range: 摘要涵盖的对话轮次范围 (start, end)
        metadata: 额外元数据
    """
    summary_text: str
    key_topics: List[str] = field(default_factory=list)
    emotion_trajectory: str = ""
    user_needs: List[str] = field(default_factory=list)
    turn_range: tuple = (0, 0)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationSummaryService:
    """
    对话摘要服务
    
    支持两种模式：
    1. 规则摘要（默认）- 不消耗 token，基于启发式规则
    2. LLM 摘要（可选）- 使用 LLM 生成更高质量的摘要
    """
    
    # 情绪关键词库（用于规则摘要）
    EMOTION_KEYWORDS = {
        "positive": ["开心", "高兴", "快乐", "喜欢", "爱", "棒", "好", "不错", "满意"],
        "negative": ["难过", "伤心", "焦虑", "压力", "累", "烦", "失落", "孤独", "迷茫", "担心"],
        "neutral": ["还好", "一般", "还行", "可以"]
    }
    
    # 话题关键词库（用于规则摘要）
    TOPIC_KEYWORDS = {
        "工作": ["工作", "加班", "同事", "老板", "项目", "任务", "职场"],
        "学习": ["学习", "考试", "作业", "课程", "老师", "学校", "成绩"],
        "情感": ["喜欢", "爱", "恋爱", "分手", "单身", "暗恋", "表白"],
        "家庭": ["家人", "父母", "妈妈", "爸爸", "家", "回家"],
        "健康": ["健康", "生病", "医院", "感冒", "头痛", "身体"],
        "兴趣": ["爱好", "游戏", "电影", "音乐", "运动", "旅游", "看书"],
        "生活": ["吃饭", "睡觉", "购物", "出门", "在家", "休息"]
    }
    
    # 需求关键词库
    NEED_KEYWORDS = {
        "倾诉": ["想说", "想聊", "听我说", "告诉你"],
        "建议": ["怎么办", "建议", "意见", "看法", "觉得"],
        "陪伴": ["陪我", "陪着", "在吗", "聊天"],
        "理解": ["理解", "懂我", "明白", "知道"],
        "鼓励": ["鼓励", "支持", "加油", "相信"]
    }
    
    def __init__(self, llm_provider=None):
        """
        初始化摘要服务
        
        Args:
            llm_provider: LLM 提供者（可选，用于 LLM 摘要模式）
        """
        self.llm_provider = llm_provider
        config = self._load_summary_config()
        self.EMOTION_KEYWORDS = config.get("emotion", {})
        self.TOPIC_KEYWORDS = config.get("topic", {})
        self.NEED_KEYWORDS = config.get("need", {})

    @staticmethod
    def _load_summary_config() -> Dict:
        """从统一 YAML 加载摘要相关配置"""
        from pathlib import Path
        import yaml

        config_path = Path(__file__).parent.parent.parent / "configs" / "dialogue_strategy.yaml"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            return config.get("summary_keywords", {})
        except (FileNotFoundError, yaml.YAMLError) as e:
            from loguru import logger
            logger.error(f"❌ 摘要配置加载失败: {e}")
            # 返回空字典，使用空关键词库（降级运行）
            return {}

    async def summarize_conversations(
        self,
        conversations: List[Dict[str, str]],
        use_llm: bool = False,
        max_summary_length: int = 200
    ) -> ConversationSummary:
        """
        对对话历史进行摘要

        Args:
            conversations: 对话历史列表，格式 [{"role": "user", "content": "..."}, ...]
            use_llm: 是否使用 LLM 摘要（消耗 token）
            max_summary_length: 摘要最大长度
            
        Returns:
            ConversationSummary: 结构化的摘要对象
        """
        if not conversations:
            return ConversationSummary(
                summary_text="暂无对话历史",
                turn_range=(0, 0)
            )
        
        # 如果启用 LLM 且有 LLM 提供者，使用 LLM 摘要
        if use_llm and self.llm_provider:
            try:
                return await self._summarize_with_llm(conversations, max_summary_length)
            except Exception as e:
                logger.warning(f"LLM 摘要失败，回退到规则摘要: {e}")
                # 回退到规则摘要
        
        # 默认使用规则摘要
        return self._summarize_with_rules(conversations, max_summary_length)
    
    def _summarize_with_rules(
        self,
        conversations: List[Dict[str, str]],
        max_summary_length: int
    ) -> ConversationSummary:
        """
        基于规则的摘要（不消耗 token）
        
        使用启发式规则提取：
        1. 关键话题（基于关键词匹配）
        2. 情绪轨迹（基于情绪关键词）
        3. 用户需求（基于需求关键词）
        4. 生成简洁的摘要文本
        """
        logger.debug(f"使用规则摘要，对话数量: {len(conversations)}")
        
        # 统计用户消息轮次
        user_messages = [c for c in conversations if c.get("role") == "user"]
        turn_range = (1, len(user_messages))
        
        # 提取关键话题
        topics = self._extract_topics(conversations)
        
        # 分析情绪轨迹
        emotion_trajectory = self._analyze_emotion_trajectory(conversations)
        
        # 识别用户需求
        user_needs = self._identify_user_needs(conversations)
        
        # 生成摘要文本
        summary_text = self._generate_rule_based_summary(
            conversations, topics, emotion_trajectory, user_needs, max_summary_length
        )
        
        return ConversationSummary(
            summary_text=summary_text,
            key_topics=topics[:5],  # 最多 5 个话题
            emotion_trajectory=emotion_trajectory,
            user_needs=user_needs[:3],  # 最多 3 个需求
            turn_range=turn_range,
            metadata={"method": "rule_based"}
        )
    
    async def _summarize_with_llm(
        self,
        conversations: List[Dict[str, str]],
        max_summary_length: int
    ) -> ConversationSummary:
        """
        使用 LLM 生成摘要（消耗 token）
        
        LLM 能更好地理解上下文和生成连贯的摘要
        """
        logger.debug(f"使用 LLM 摘要，对话数量: {len(conversations)}")
        
        # 构建对话文本
        conversation_text = "\n".join([
            f"{'用户' if c.get('role') == 'user' else 'Bot'}: {c.get('content', '')}"
            for c in conversations
        ])
        
        # 构建摘要提示词
        prompt = f"""请对以下对话进行摘要，要求：
1. 提取关键话题（3-5个）
2. 分析用户情绪变化
3. 识别用户需求或关注点
4. 生成简洁的摘要文本（不超过{max_summary_length}字）

对话内容：
{conversation_text}

请以 JSON 格式返回：
```json
{{
    "summary_text": "摘要文本",
    "key_topics": ["话题1", "话题2"],
    "emotion_trajectory": "情绪变化描述",
    "user_needs": ["需求1", "需求2"]
}}
```
"""
        
        try:
            # 调用 LLM
            response = await self.llm_provider.generate_response(
                [{"role": "user", "content": prompt}],
                context="你是一个对话摘要助手。"
            )
            
            # 解析 JSON 响应
            import json
            response_text = response.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            data = json.loads(response_text.strip())
            
            user_messages = [c for c in conversations if c.get("role") == "user"]
            
            return ConversationSummary(
                summary_text=data.get("summary_text", ""),
                key_topics=data.get("key_topics", []),
                emotion_trajectory=data.get("emotion_trajectory", ""),
                user_needs=data.get("user_needs", []),
                turn_range=(1, len(user_messages)),
                metadata={"method": "llm_based"}
            )
            
        except Exception as e:
            logger.error(f"LLM 摘要解析失败: {e}")
            raise
    
    def _extract_topics(self, conversations: List[Dict[str, str]]) -> List[str]:
        """提取对话中的关键话题"""
        topics_count = {}
        
        for conv in conversations:
            content = conv.get("content", "").lower()
            for topic, keywords in self.TOPIC_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in content:
                        topics_count[topic] = topics_count.get(topic, 0) + 1
                        break
        
        # 按频次排序
        sorted_topics = sorted(topics_count.items(), key=lambda x: x[1], reverse=True)
        return [topic for topic, _ in sorted_topics]
    
    def _analyze_emotion_trajectory(self, conversations: List[Dict[str, str]]) -> str:
        """分析情绪轨迹"""
        emotions = []
        
        for conv in conversations:
            if conv.get("role") != "user":
                continue
            
            content = conv.get("content", "").lower()
            
            # 检测情绪
            emotion = "neutral"
            for keyword in self.EMOTION_KEYWORDS["positive"]:
                if keyword in content:
                    emotion = "positive"
                    break
            
            if emotion == "neutral":
                for keyword in self.EMOTION_KEYWORDS["negative"]:
                    if keyword in content:
                        emotion = "negative"
                        break
            
            emotions.append(emotion)
        
        # 生成情绪轨迹描述
        if not emotions:
            return "情绪平稳"
        
        # 统计情绪分布
        positive_count = emotions.count("positive")
        negative_count = emotions.count("negative")
        
        if positive_count > negative_count * 2:
            return "整体积极"
        elif negative_count > positive_count * 2:
            return "整体消极"
        elif negative_count > 0 and positive_count > 0:
            return "情绪有波动"
        else:
            return "情绪平稳"
    
    def _identify_user_needs(self, conversations: List[Dict[str, str]]) -> List[str]:
        """识别用户需求"""
        needs_count = {}
        
        for conv in conversations:
            if conv.get("role") != "user":
                continue
            
            content = conv.get("content", "").lower()
            for need, keywords in self.NEED_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in content:
                        needs_count[need] = needs_count.get(need, 0) + 1
                        break
        
        # 按频次排序
        sorted_needs = sorted(needs_count.items(), key=lambda x: x[1], reverse=True)
        return [need for need, _ in sorted_needs]
    
    def _generate_rule_based_summary(
        self,
        conversations: List[Dict[str, str]],
        topics: List[str],
        emotion_trajectory: str,
        user_needs: List[str],
        max_length: int
    ) -> str:
        """生成基于规则的摘要文本"""
        summary_parts = []
        
        # 话题部分
        if topics:
            topic_str = "、".join(topics[:3])
            summary_parts.append(f"讨论话题：{topic_str}")
        
        # 情绪部分
        if emotion_trajectory and emotion_trajectory != "情绪平稳":
            summary_parts.append(f"情绪：{emotion_trajectory}")
        
        # 需求部分
        if user_needs:
            need_str = "、".join(user_needs[:2])
            summary_parts.append(f"用户希望得到：{need_str}")
        
        # 组合摘要
        if not summary_parts:
            return "用户进行了日常交流"
        
        summary = "。".join(summary_parts) + "。"
        
        # 截断到最大长度
        if len(summary) > max_length:
            summary = summary[:max_length - 3] + "..."
        
        return summary
    
    def get_short_summary(self, summary: ConversationSummary) -> str:
        """
        获取简短版摘要（用于注入到 system prompt）
        
        Args:
            summary: 完整摘要对象
            
        Returns:
            简短的摘要文本
        """
        parts = []
        
        if summary.summary_text:
            parts.append(summary.summary_text)
        
        if summary.emotion_trajectory:
            parts.append(f"情绪变化：{summary.emotion_trajectory}")
        
        return "；".join(parts) if parts else "暂无历史摘要"
