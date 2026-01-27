"""
Conversation Memory Service - 对话记忆服务

提供RAG技术驱动的对话记忆功能：
1. 分析对话，判断是否包含重要事件（过滤日常寒暄）
2. 提取并保存重要事件到数据库（支持向量嵌入）
3. 使用向量相似度检索与当前对话相关的历史记忆
4. 用于增强Bot的个性化对话能力

向量检索说明：
- 使用Embedding向量化存储记忆摘要
- 支持语义相似度检索，提升检索精度
- 向后兼容：对于没有embedding的记忆，回退到关键词匹配
- 支持混合检索：向量相似度 + 元数据过滤

使用方法：
    from src.services.conversation_memory_service import ConversationMemoryService

    service = ConversationMemoryService(db_session, llm_provider, embedding_service)

    # 保存重要对话事件（自动生成向量嵌入）
    await service.extract_and_save_important_events(
        user_id=123,
        bot_id=456,
        user_message="我下个月15号生日",
        bot_response="太棒了！我记住了，下个月15号是你的生日..."
    )

    # 检索相关记忆（使用向量相似度）
    memories = await service.retrieve_memories(
        user_id=123,
        bot_id=456,
        current_message="你还记得我的生日吗？"
    )
"""
import json
import time
import uuid
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, func
from loguru import logger
import numpy as np

from src.models.database import UserMemory, MemoryImportance


class DateParser:
    """
    智能日期解析器

    支持解析各种中文和英文的相对时间表达，结合当前系统时间计算出准确日期。

    支持的表达式示例：
    - 相对日期：昨天、今天、明天、前天、后天、大前天、大后天
    - 相对周：上周、这周、下周、上上周、下下周
    - 相对月：上个月、这个月、下个月、上上个月
    - 相对年：去年、今年、明年、前年、后年
    - 具体日期：15号、3月15日、2026年3月15日
    - 组合表达：下个月15号、明年3月、去年12月25日
    - 星期表达：周一、星期三、下周五、上周日
    - 特殊表达：月底、月初、年底、年初
    """

    # 中文数字映射
    CN_NUMBERS = {
        '零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
        '十六': 16, '十七': 17, '十八': 18, '十九': 19, '二十': 20,
        '二十一': 21, '二十二': 22, '二十三': 23, '二十四': 24,
        '二十五': 25, '二十六': 26, '二十七': 27, '二十八': 28,
        '二十九': 29, '三十': 30, '三十一': 31
    }

    # 星期映射
    WEEKDAY_MAP = {
        '一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6, '天': 6,
        '1': 0, '2': 1, '3': 2, '4': 3, '5': 4, '6': 5, '7': 6
    }

    def __init__(self, reference_time: Optional[datetime] = None):
        """
        初始化日期解析器

        Args:
            reference_time: 参考时间，默认使用当前系统时间
        """
        self.reference_time = reference_time or datetime.now()
        self.today = self.reference_time.replace(hour=0, minute=0, second=0, microsecond=0)

    def parse(self, text: str) -> Optional[datetime]:
        """
        解析文本中的日期表达

        Args:
            text: 包含日期表达的文本

        Returns:
            解析出的日期，如果无法解析则返回None
        """
        if not text:
            return None

        text = text.strip()

        # 尝试各种解析策略
        result = None

        # 1. 尝试解析标准日期格式 (YYYY-MM-DD, YYYY/MM/DD, YYYY年MM月DD日)
        result = self._parse_standard_date(text)
        if result:
            return result

        # 2. 尝试解析相对日期表达
        result = self._parse_relative_date(text)
        if result:
            return result

        # 3. 尝试解析组合日期表达（如"下个月15号"）
        result = self._parse_combined_date(text)
        if result:
            return result

        # 4. 尝试解析星期表达
        result = self._parse_weekday(text)
        if result:
            return result

        # 5. 尝试解析特殊表达（月底、年初等）
        result = self._parse_special_date(text)
        if result:
            return result

        return None

    def _parse_standard_date(self, text: str) -> Optional[datetime]:
        """解析标准日期格式"""
        patterns = [
            # YYYY-MM-DD 或 YYYY/MM/DD
            (r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})',
             lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))),
            # YYYY年MM月DD日
            (r'(\d{4})年(\d{1,2})月(\d{1,2})[日号]?',
             lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))),
            # MM-DD 或 MM/DD (使用当前年份)
            (r'^(\d{1,2})[-/](\d{1,2})$', lambda m: datetime(self.today.year, int(m.group(1)), int(m.group(2)))),
            # MM月DD日 (使用当前年份)
            (r'^(\d{1,2})月(\d{1,2})[日号]$', lambda m: datetime(self.today.year, int(m.group(1)), int(m.group(2)))),
            # DD日 或 DD号 (使用当前年月)
            (r'^(\d{1,2})[日号]$', lambda m: datetime(self.today.year, self.today.month, int(m.group(1)))),
        ]

        for pattern, handler in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return handler(match)
                except ValueError:
                    continue

        return None

    def _parse_relative_date(self, text: str) -> Optional[datetime]:
        """解析相对日期表达"""

        # ==================== 模糊时间表达 ====================
        # 这些表达都指向"今天"
        today_expressions = [
            r'刚刚', r'刚才', r'方才',
            r'今天早上', r'今天上午', r'今天中午', r'今天下午', r'今天晚上', r'今天凌晨',
            r'今早', r'今晚',
            r'上午', r'下午', r'晚上', r'凌晨', r'中午',  # 不带"今天"默认指今天
            r'这会儿', r'现在', r'此刻',
            r'今日',
        ]

        for pattern in today_expressions:
            if re.search(pattern, text):
                return self.today

        # 这些表达指向"昨天"
        yesterday_expressions = [
            r'昨晚', r'昨天晚上', r'昨天下午', r'昨天上午', r'昨天早上',
            r'昨日',
        ]

        for pattern in yesterday_expressions:
            if re.search(pattern, text):
                return self.today + timedelta(days=-1)

        # 模糊的"最近"表达 - 默认指向今天
        recent_expressions = [
            r'最近', r'这几天', r'前几天', r'这段时间', r'近期', r'近来',
        ]

        for pattern in recent_expressions:
            if re.search(pattern, text):
                return self.today

        # ==================== 精确的相对天数 ====================
        day_patterns = {
            r'大前天': -3,
            r'前天': -2,
            r'昨天': -1,
            r'今天': 0,
            r'明天': 1,
            r'后天': 2,
            r'大后天': 3,
        }

        for pattern, days in day_patterns.items():
            if pattern in text:
                return self.today + timedelta(days=days)

        # ==================== 相对周 ====================
        week_patterns = {
            r'上上周': -2,
            r'上周': -1,
            r'这周|本周': 0,
            r'下周': 1,
            r'下下周': 2,
        }

        for pattern, weeks in week_patterns.items():
            if re.search(pattern, text):
                # 返回该周的周一
                target = self.today + timedelta(weeks=weeks)
                days_since_monday = target.weekday()
                return target - timedelta(days=days_since_monday)

        # ==================== 相对月 ====================
        month_patterns = {
            r'上上个?月': -2,
            r'上个?月': -1,
            r'这个?月|本月': 0,
            r'下个?月': 1,
            r'下下个?月': 2,
        }

        for pattern, months in month_patterns.items():
            if re.search(pattern, text):
                result = self.today + relativedelta(months=months)
                # 只匹配纯月份表达，返回该月1日
                if not re.search(r'\d+[日号]', text):
                    return result.replace(day=1)
                return result

        # ==================== 相对年 ====================
        year_patterns = {
            r'前年': -2,
            r'去年': -1,
            r'今年': 0,
            r'明年': 1,
            r'后年': 2,
        }

        for pattern, years in year_patterns.items():
            if re.search(pattern, text):
                result = self.today + relativedelta(years=years)
                # 只匹配纯年份表达，返回该年1月1日
                if not re.search(r'\d+月|\d+[日号]', text):
                    return result.replace(month=1, day=1)
                return result

        return None

    def _parse_combined_date(self, text: str) -> Optional[datetime]:
        """解析组合日期表达（如"下个月15号"、"明年3月15日"）"""

        # 基准日期
        base_date = self.today

        # 解析年份修饰
        year_offset = 0
        if '前年' in text:
            year_offset = -2
        elif '去年' in text:
            year_offset = -1
        elif '明年' in text:
            year_offset = 1
        elif '后年' in text:
            year_offset = 2

        # 解析月份修饰
        month_offset = 0
        if re.search(r'上上个?月', text):
            month_offset = -2
        elif re.search(r'上个?月', text):
            month_offset = -1
        elif re.search(r'下下个?月', text):
            month_offset = 2
        elif re.search(r'下个?月', text):
            month_offset = 1

        # 应用年月偏移
        if year_offset != 0 or month_offset != 0:
            base_date = base_date + relativedelta(years=year_offset, months=month_offset)

        # 解析具体月份 (如 "3月", "12月")
        month_match = re.search(r'(\d{1,2})月', text)
        if month_match:
            month = int(month_match.group(1))
            if 1 <= month <= 12:
                base_date = base_date.replace(month=month)

        # 解析具体日期 (如 "15号", "15日")
        day_match = re.search(r'(\d{1,2})[日号]', text)
        if day_match:
            day = int(day_match.group(1))
            if 1 <= day <= 31:
                try:
                    base_date = base_date.replace(day=day)
                except ValueError:
                    # 日期无效（如2月30日），尝试使用该月最后一天
                    next_month = base_date.replace(day=1) + relativedelta(months=1)
                    base_date = next_month - timedelta(days=1)

        # 解析中文日期 (如 "十五号", "二十日")
        for cn_num, num in self.CN_NUMBERS.items():
            if f'{cn_num}[日号]' in text or re.search(f'{cn_num}[日号]', text):
                try:
                    base_date = base_date.replace(day=num)
                except ValueError:
                    pass
                break

        # 如果有任何偏移或具体日期，返回结果
        if year_offset != 0 or month_offset != 0 or month_match or day_match:
            return base_date

        return None

    def _parse_weekday(self, text: str) -> Optional[datetime]:
        """解析星期表达（如"周一"、"下周五"、"上周日"）"""

        # 确定周偏移
        week_offset = 0
        if re.search(r'上上周', text):
            week_offset = -2
        elif re.search(r'上周', text):
            week_offset = -1
        elif re.search(r'下下周', text):
            week_offset = 2
        elif re.search(r'下周', text):
            week_offset = 1
        elif re.search(r'这周|本周', text):
            week_offset = 0

        # 解析星期几
        weekday_match = re.search(r'(?:周|星期)([一二三四五六日天1-7])', text)
        if weekday_match:
            weekday_str = weekday_match.group(1)
            target_weekday = self.WEEKDAY_MAP.get(weekday_str)

            if target_weekday is not None:
                # 计算目标日期
                current_weekday = self.today.weekday()
                days_diff = target_weekday - current_weekday + (week_offset * 7)

                # 如果没有周偏移且目标星期已过，默认指向下周
                if week_offset == 0 and days_diff < 0 and '这周' not in text and '本周' not in text:
                    days_diff += 7

                return self.today + timedelta(days=days_diff)

        return None

    def _parse_special_date(self, text: str) -> Optional[datetime]:
        """解析特殊日期表达（月底、年初等）"""

        base_date = self.today

        # 先处理年月偏移
        if '去年' in text:
            base_date = base_date + relativedelta(years=-1)
        elif '明年' in text:
            base_date = base_date + relativedelta(years=1)

        if re.search(r'上个?月', text):
            base_date = base_date + relativedelta(months=-1)
        elif re.search(r'下个?月', text):
            base_date = base_date + relativedelta(months=1)

        # 月初
        if '月初' in text:
            return base_date.replace(day=1)

        # 月底/月末
        if '月底' in text or '月末' in text:
            next_month = base_date.replace(day=1) + relativedelta(months=1)
            return next_month - timedelta(days=1)

        # 年初
        if '年初' in text:
            return base_date.replace(month=1, day=1)

        # 年底/年末
        if '年底' in text or '年末' in text:
            return base_date.replace(month=12, day=31)

        return None

    def parse_from_message(self, message: str) -> Optional[datetime]:
        """
        从用户消息中智能提取日期

        会尝试识别消息中的各种日期表达并解析

        Args:
            message: 用户消息

        Returns:
            解析出的日期，如果无法解析则返回None
        """
        if not message:
            return None

        # 常见的日期相关关键词模式
        date_patterns = [
            # ==================== 新增：模糊时间表达 ====================
            r'刚刚|刚才|方才',
            r'最近|这几天|前几天|这段时间|近期|近来|这两天',
            r'今天?早上|今天?上午|今天?中午|今天?下午|今天?晚上|今天?凌晨',
            r'今早|今晚|今日',
            r'昨天?晚上|昨天?下午|昨天?上午|昨天?早上|昨晚|昨早|昨日',
            r'前天晚上|前晚',
            r'这会儿|现在|此刻',
            # ==================== 完整日期表达 ====================
            r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?',
            r'\d{1,2}[-/月]\d{1,2}[日号]?',
            r'\d{1,2}[日号]',
            # 相对日期
            r'大?前天|昨天|今天|明天|大?后天',
            # 相对周
            r'上{1,2}周|这周|本周|下{1,2}周',
            # 相对月
            r'上{1,2}个?月|这个?月|本月|下{1,2}个?月',
            # 相对年
            r'前年|去年|今年|明年|后年',
            # 星期
            r'(?:上{1,2}周|这周|本周|下{1,2}周)?(?:周|星期)[一二三四五六日天1-7]',
            # 特殊表达
            r'月[初底末]|年[初底末]',
            # 组合表达 (如 "下个月15号")
            r'(?:上{1,2}个?月|下{1,2}个?月)\d{1,2}[日号]',
            r'(?:去年|明年|后年)\d{1,2}月(?:\d{1,2}[日号])?',
        ]

        # 找到所有可能的日期表达
        for pattern in date_patterns:
            matches = re.findall(pattern, message)
            for match in matches:
                result = self.parse(match)
                if result:
                    return result

        # 尝试直接解析整个消息
        return self.parse(message)


class ConversationMemoryService:
    """
    对话记忆服务

    使用LLM分析对话重要性，存储重要事件，并在需要时检索相关记忆。
    """

    # 用于判断重要性的系统提示词（更新以支持更灵活的日期提取）
    IMPORTANCE_ANALYSIS_PROMPT = """你是一个智能记忆分析助手。你的任务是分析用户和AI助手之间的对话，判断是否包含值得记住的重要事件。

    重要事件包括（以下的事件重要度为中等以及以上）：
    - 个人信息：生日、年龄、职业、家庭成员、居住地等
    - 重要偏好：喜欢/不喜欢的事物、兴趣爱好、习惯等
    - 重要目标：学习计划、工作目标、人生规划等
    - 情感事件：重要的情感表达、心理状态变化等
    - 生活事件：毕业、求职、结婚、生病、搬家等重大事件
    - 人际关系：朋友、家人、同事等重要关系
    - 生活小插曲：记录具有情绪价值和连续意义的日常小事件比如：捡到钱、失恋了、升职加薪了、吐槽朋友老板同事等等，用于追踪状态变化与后续关怀。

    不重要的事件（应该过滤）：
    - 日常寒暄：你好、再见、谢谢、早上好等
    - 简单问答：今天天气怎么样、现在几点了等
    - 无个人信息的技术问题：如何写代码、解释概念等
    - 一次性话题：无需长期记忆的临时话题

    关于日期提取：
    - 如果用户提到了具体日期，请提取为 YYYY-MM-DD 格式
    - 如果用户使用相对时间表达（如"昨天"、"下个月15号"、"明年3月"），请原样保留在 raw_date_expression 字段
    - 如果没有提到日期相关信息，event_date 和 raw_date_expression 都设为 null

    请以JSON格式返回分析结果：
    {
        "is_important": true/false,
        "importance_level": "low/medium/high/critical",
        "event_type": "preference/birthday/goal/emotion/life_event/relationship/other",
        "event_summary": "简洁的事件摘要（如果重要的话）",
        "keywords": ["关键词1", "关键词2"],
        "event_date": "YYYY-MM-DD格式的日期（如果是具体日期）或 null",
        "raw_date_expression": "用户原始的时间表达（如'昨天'、'下个月15号'）或 null"
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
            embedding_service=None,
            max_memories_per_query: int = 5,
            importance_threshold: str = "medium",
            similarity_threshold: float = 0.5
    ):
        """
        初始化对话记忆服务

        Args:
            db: 异步数据库会话
            llm_provider: LLM提供者（用于重要性分析）
            embedding_service: 向量嵌入服务（用于生成和检索向量）
            max_memories_per_query: 每次检索返回的最大记忆数量
            importance_threshold: 保存记忆的最低重要性阈值
            similarity_threshold: 向量相似度检索的最低阈值
        """
        self.db = db
        self.llm_provider = llm_provider
        self.embedding_service = embedding_service
        self.max_memories_per_query = max_memories_per_query
        self.importance_threshold = importance_threshold
        self.similarity_threshold = similarity_threshold

        # 重要性级别排序
        self._importance_order = {
            MemoryImportance.LOW.value: 0,
            MemoryImportance.MEDIUM.value: 1,
            MemoryImportance.HIGH.value: 2,
            MemoryImportance.CRITICAL.value: 3
        }

        logger.info(
            f"🧠 [Memory] ConversationMemoryService initialized | "
            f"embedding_enabled={embedding_service is not None} | "
            f"llm_enabled={llm_provider is not None} | "
            f"importance_threshold={importance_threshold} | "
            f"similarity_threshold={similarity_threshold}"
        )

    def _generate_trace_id(self) -> str:
        """生成追踪ID用于关联日志"""
        return str(uuid.uuid4())[:8]

    def _parse_event_date(
            self,
            analysis: Dict[str, Any],
            user_message: str,
            reference_time: Optional[datetime] = None,
            trace_id: str = ""
    ) -> Optional[datetime]:
        """
        智能解析事件日期

        优先使用LLM提取的日期，如果是相对时间表达则使用DateParser解析。
        如果LLM没有提取到日期，则尝试从用户消息中直接提取。

        Args:
            analysis: LLM分析结果
            user_message: 用户原始消息
            reference_time: 参考时间（默认使用当前系统时间）
            trace_id: 追踪ID用于日志

        Returns:
            解析出的日期，如果无法解析则返回None
        """
        reference_time = reference_time or datetime.now()
        parser = DateParser(reference_time)

        logger.debug(
            f"📅 [Memory-DateParse][{trace_id}] START date parsing | "
            f"reference_time={reference_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        # 1. 尝试使用LLM提取的具体日期 (YYYY-MM-DD格式)
        llm_date = analysis.get("event_date")
        if llm_date and isinstance(llm_date, str):
            try:
                parsed = datetime.strptime(llm_date, "%Y-%m-%d")
                logger.debug(
                    f"📅 [Memory-DateParse][{trace_id}] Parsed from LLM event_date | "
                    f"input={llm_date} | result={parsed.strftime('%Y-%m-%d')}"
                )
                return parsed
            except ValueError:
                logger.debug(
                    f"📅 [Memory-DateParse][{trace_id}] Failed to parse LLM event_date as YYYY-MM-DD | "
                    f"input={llm_date}"
                )

        # 2. 尝试使用LLM提取的原始时间表达
        raw_expression = analysis.get("raw_date_expression")
        if raw_expression and isinstance(raw_expression, str):
            parsed = parser.parse(raw_expression)
            if parsed:
                logger.debug(
                    f"📅 [Memory-DateParse][{trace_id}] Parsed from raw_date_expression | "
                    f"expression='{raw_expression}' | result={parsed.strftime('%Y-%m-%d')}"
                )
                return parsed
            else:
                logger.debug(
                    f"📅 [Memory-DateParse][{trace_id}] Failed to parse raw_date_expression | "
                    f"expression='{raw_expression}'"
                )

        # 3. 尝试从用户消息中直接提取日期
        parsed = parser.parse_from_message(user_message)
        if parsed:
            logger.debug(
                f"📅 [Memory-DateParse][{trace_id}] Parsed from user_message | "
                f"result={parsed.strftime('%Y-%m-%d')}"
            )
            return parsed

        logger.debug(f"📅 [Memory-DateParse][{trace_id}] No date found in message")
        return None

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
        trace_id = self._generate_trace_id()
        start_time = time.perf_counter()

        # 记录输入
        user_msg_preview = user_message[:100] + "..." if len(user_message) > 100 else user_message
        bot_resp_preview = bot_response[:100] + "..." if len(bot_response) > 100 else bot_response

        logger.debug(
            f"🔍 [Memory-Analyze][{trace_id}] START importance analysis | "
            f"user_message_length={len(user_message)} | bot_response_length={len(bot_response)}"
        )
        logger.debug(f"🔍 [Memory-Analyze][{trace_id}] user_message_preview: {user_msg_preview}")
        logger.debug(f"🔍 [Memory-Analyze][{trace_id}] bot_response_preview: {bot_resp_preview}")

        if not self.llm_provider:
            # 如果没有LLM，使用简单的规则判断
            logger.debug(f"🔍 [Memory-Analyze][{trace_id}] No LLM provider, using rule-based analysis")
            result = self._analyze_importance_rule_based(user_message, trace_id)
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(
                f"🔍 [Memory-Analyze][{trace_id}] END rule-based analysis | "
                f"latency={latency_ms:.1f}ms | result={json.dumps(result, ensure_ascii=False)}"
            )
            return result

        try:
            # 在prompt中包含当前时间，帮助LLM理解相对时间
            current_time_str = datetime.now().strftime("%Y年%m月%d日 %H:%M")
            analysis_prompt = f"""当前时间: {current_time_str}

用户消息: {user_message}
AI回复: {bot_response}

请分析这段对话是否包含值得记住的重要事件。"""

            logger.debug(f"🔍 [Memory-Analyze][{trace_id}] Calling LLM for importance analysis...")
            llm_start_time = time.perf_counter()

            response = await self.llm_provider.generate_response(
                [{"role": "user", "content": analysis_prompt}],
                context=self.IMPORTANCE_ANALYSIS_PROMPT
            )

            llm_latency_ms = (time.perf_counter() - llm_start_time) * 1000
            logger.debug(
                f"🔍 [Memory-Analyze][{trace_id}] LLM response received | "
                f"llm_latency={llm_latency_ms:.1f}ms | response_length={len(response)}"
            )
            logger.debug(f"🔍 [Memory-Analyze][{trace_id}] LLM raw response: {response[:500]}")

            # 解析JSON响应
            response_text = response.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]

            result = json.loads(response_text.strip())

            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(
                f"🔍 [Memory-Analyze][{trace_id}] END LLM analysis | "
                f"total_latency={latency_ms:.1f}ms | "
                f"is_important={result.get('is_important')} | "
                f"importance_level={result.get('importance_level')} | "
                f"event_type={result.get('event_type')} | "
                f"event_date={result.get('event_date')} | "
                f"raw_date_expression={result.get('raw_date_expression')}"
            )
            logger.debug(f"🔍 [Memory-Analyze][{trace_id}] Full result: {json.dumps(result, ensure_ascii=False)}")

            return result

        except json.JSONDecodeError as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(
                f"⚠️ [Memory-Analyze][{trace_id}] Failed to parse LLM response as JSON | "
                f"latency={latency_ms:.1f}ms | error={e}"
            )
            return {"is_important": False}
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"❌ [Memory-Analyze][{trace_id}] Error in importance analysis | "
                f"latency={latency_ms:.1f}ms | error_type={type(e).__name__} | error={e}"
            )
            return {"is_important": False}

    def _analyze_importance_rule_based(self, user_message: str, trace_id: str = "") -> Dict[str, Any]:
        """
        基于规则的重要性分析（当没有LLM时使用）

        使用关键词匹配进行简单的重要性判断。
        """
        message_lower = user_message.lower()

        # 日常寒暄关键词（低重要性）
        greetings = ["你好", "hello", "hi", "再见", "bye", "谢谢", "thanks",
                     "早上好", "晚上好", "早安", "晚安", "good morning", "good night"]

        if any(greeting in message_lower for greeting in greetings) and len(user_message) < 20:
            logger.debug(
                f"🔍 [Memory-Analyze][{trace_id}] Rule-based: detected greeting, marking as not important"
            )
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
            matched_keywords = [kw for kw in keywords if kw in message_lower]
            if matched_keywords:
                # 尝试从消息中提取日期
                parser = DateParser()
                parsed_date = parser.parse_from_message(user_message)
                raw_date_expr = None

                # 尝试找到原组合的时间表达
                date_patterns = [
                    r'大?前天|昨天|今天|明天|大?后天',
                    r'上{1,2}周|这周|本周|下{1,2}周',
                    r'上{1,2}个?月|这个?月|本月|下{1,2}个?月',
                    r'前年|去年|今年|明年|后年',
                    r'(?:上{1,2}周|这周|本周|下{1,2}周)?(?:周|星期)[一二三四五六日天]',
                    r'\d{1,2}月\d{1,2}[日号]',
                    r'\d{1,2}[日号]',
                ]
                for pattern in date_patterns:
                    match = re.search(pattern, user_message)
                    if match:
                        raw_date_expr = match.group()
                        break

                logger.debug(
                    f"🔍 [Memory-Analyze][{trace_id}] Rule-based: matched keywords {matched_keywords} | "
                    f"event_type={event_type} | "
                    f"parsed_date={parsed_date.strftime('%Y-%m-%d') if parsed_date else None} | "
                    f"raw_date_expression={raw_date_expr}"
                )

                return {
                    "is_important": True,
                    "importance_level": MemoryImportance.MEDIUM.value,
                    "event_type": event_type,
                    "event_summary": user_message[:100],
                    "keywords": matched_keywords,
                    "event_date": parsed_date.strftime("%Y-%m-%d") if parsed_date else None,
                    "raw_date_expression": raw_date_expr
                }

        logger.debug(f"🔍 [Memory-Analyze][{trace_id}] Rule-based: no important keywords found")
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
        如果配置了embedding_service，会自动生成向量嵌入。

        Args:
            user_id: 用户ID
            bot_id: Bot ID
            user_message: 用户消息
            bot_response: Bot回复

        Returns:
            保存的UserMemory对象，如果不重要则返回None
        """
        trace_id = self._generate_trace_id()
        start_time = time.perf_counter()
        reference_time = datetime.now()  # 记录处理时的参考时间

        logger.debug(
            f"📝 [Memory-Extract][{trace_id}] START extract_and_save_important_events | "
            f"user_id={user_id} | bot_id={bot_id} | "
            f"reference_time={reference_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        logger.debug(
            f"📝 [Memory-Extract][{trace_id}] Input lengths: "
            f"user_message={len(user_message)} chars | bot_response={len(bot_response)} chars"
        )

        # ==================== Step 1: 分析重要性 ====================
        logger.debug(f"📝 [Memory-Extract][{trace_id}] Step 1: Analyzing importance...")
        analysis_start = time.perf_counter()

        analysis = await self.analyze_importance(user_message, bot_response)

        analysis_latency = (time.perf_counter() - analysis_start) * 1000
        logger.debug(
            f"📝 [Memory-Extract][{trace_id}] Step 1 completed | "
            f"latency={analysis_latency:.1f}ms | "
            f"is_important={analysis.get('is_important')} | "
            f"importance_level={analysis.get('importance_level')}"
        )

        # ==================== Step 2: 检查是否重要 ====================
        if not analysis.get("is_important", False):
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(
                f"📝 [Memory-Extract][{trace_id}] END - Message not important | "
                f"total_latency={latency_ms:.1f}ms | action=skipped"
            )
            return None

        # ==================== Step 3: 检查重要性级别是否达到阈值 ====================
        importance_level = analysis.get("importance_level", MemoryImportance.MEDIUM.value)
        current_level_order = self._importance_order.get(importance_level, 0)
        threshold_order = self._importance_order.get(self.importance_threshold, 1)

        logger.debug(
            f"📝 [Memory-Extract][{trace_id}] Step 2: Checking threshold | "
            f"importance_level={importance_level} (order={current_level_order}) | "
            f"threshold={self.importance_threshold} (order={threshold_order})"
        )

        if current_level_order < threshold_order:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(
                f"📝 [Memory-Extract][{trace_id}] END - Importance level {importance_level} "
                f"below threshold {self.importance_threshold} | "
                f"total_latency={latency_ms:.1f}ms | action=skipped"
            )
            return None

        logger.debug(f"📝 [Memory-Extract][{trace_id}] Threshold check passed, continuing to save...")

        # ==================== Step 4: 智能解析事件日期 ====================
        logger.debug(f"📝 [Memory-Extract][{trace_id}] Step 3: Parsing event date...")

        event_date = self._parse_event_date(
            analysis=analysis,
            user_message=user_message,
            reference_time=reference_time,
            trace_id=trace_id
        )

        if event_date:
            logger.debug(
                f"📝 [Memory-Extract][{trace_id}] Event date parsed: {event_date.strftime('%Y-%m-%d')} | "
                f"raw_expression={analysis.get('raw_date_expression')}"
            )
        else:
            logger.debug(f"📝 [Memory-Extract][{trace_id}] No event date found")

        # ==================== Step 5: 获取事件摘要 ====================
        event_summary = analysis.get("event_summary", user_message[:200])
        logger.debug(
            f"📝 [Memory-Extract][{trace_id}] Step 4: Event summary | "
            f"length={len(event_summary)} | preview={event_summary[:80]}..."
        )

        # ==================== Step 6: 生成向量嵌入 ====================
        embedding = None
        embedding_model = None
        embedding_dim = 0

        logger.debug(
            f"📝 [Memory-Extract][{trace_id}] Step 5: Generating embedding | "
            f"embedding_service_available={self.embedding_service is not None} | "
            f"provider_available={self.embedding_service.provider is not None if self.embedding_service else False}"
        )

        if self.embedding_service and self.embedding_service.provider:
            try:
                embedding_start = time.perf_counter()
                logger.debug(
                    f"🔢 [Memory-Embedding][{trace_id}] START embedding generation | "
                    f"text_length={len(event_summary)}"
                )

                result = await self.embedding_service.embed_text(event_summary)

                embedding = result.embedding
                embedding_model = result.model
                embedding_dim = len(embedding) if embedding else 0
                embedding_latency = (time.perf_counter() - embedding_start) * 1000

                # 计算嵌入向量的一些统计信息用于调试
                if embedding:
                    embedding_array = np.array(embedding)
                    embedding_stats = {
                        "dim": embedding_dim,
                        "min": float(np.min(embedding_array)),
                        "max": float(np.max(embedding_array)),
                        "mean": float(np.mean(embedding_array)),
                        "std": float(np.std(embedding_array)),
                        "norm": float(np.linalg.norm(embedding_array))
                    }
                else:
                    embedding_stats = {}

                logger.debug(
                    f"🔢 [Memory-Embedding][{trace_id}] END embedding generation | "
                    f"latency={embedding_latency:.1f}ms | "
                    f"model={embedding_model} | dim={embedding_dim}"
                )
                logger.debug(
                    f"🔢 [Memory-Embedding][{trace_id}] Embedding stats: {json.dumps(embedding_stats)}"
                )

            except Exception as e:
                embedding_latency = (time.perf_counter() - embedding_start) * 1000
                logger.warning(
                    f"⚠️ [Memory-Embedding][{trace_id}] Failed to generate embedding | "
                    f"latency={embedding_latency:.1f}ms | error_type={type(e).__name__} | error={e}"
                )
        else:
            logger.debug(f"📝 [Memory-Extract][{trace_id}] Skipping embedding generation (service not available)")

        # ==================== Step 7: 创建并保存记忆对象 ====================
        logger.debug(f"📝 [Memory-Extract][{trace_id}] Step 6: Creating UserMemory object...")

        memory = UserMemory(
            user_id=user_id,
            bot_id=bot_id,
            event_summary=event_summary,
            user_message=user_message,
            bot_response=bot_response,
            importance=importance_level,
            event_type=analysis.get("event_type"),
            keywords=analysis.get("keywords", []),
            event_date=event_date,
            embedding=embedding,
            embedding_model=embedding_model
        )

        logger.debug(
            f"📝 [Memory-Extract][{trace_id}] UserMemory object created | "
            f"event_type={analysis.get('event_type')} | "
            f"keywords={analysis.get('keywords', [])} | "
            f"event_date={event_date.strftime('%Y-%m-%d') if event_date else None} | "
            f"has_embedding={embedding is not None} | "
            f"embedding_dim={embedding_dim}"
        )

        # ==================== Step 8: 保存到数据库 ====================
        db_start = time.perf_counter()
        logger.debug(f"💾 [Memory-DB][{trace_id}] START database save...")

        try:
            self.db.add(memory)
            await self.db.commit()
            await self.db.refresh(memory)

            db_latency = (time.perf_counter() - db_start) * 1000
            logger.debug(
                f"💾 [Memory-DB][{trace_id}] END database save | "
                f"latency={db_latency:.1f}ms | memory_id={memory.id} | uuid={memory.uuid}"
            )
        except Exception as e:
            db_latency = (time.perf_counter() - db_start) * 1000
            logger.error(
                f"❌ [Memory-DB][{trace_id}] Database save failed | "
                f"latency={db_latency:.1f}ms | error_type={type(e).__name__} | error={e}"
            )
            raise

        # ==================== 完成 ====================
        total_latency = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"✅ [Memory-Extract][{trace_id}] END extract_and_save_important_events | "
            f"total_latency={total_latency:.1f}ms | "
            f"user_id={user_id} | memory_id={memory.id} | "
            f"importance={importance_level} | event_type={analysis.get('event_type')} | "
            f"event_date={event_date.strftime('%Y-%m-%d') if event_date else None} | "
            f"has_embedding={embedding is not None}"
        )
        logger.debug(
            f"📝 [Memory-Extract][{trace_id}] Saved memory summary: {event_summary[:80]}..."
        )

        return memory

    async def retrieve_memories(
            self,
            user_id: int,
            bot_id: Optional[int] = None,
            current_message: Optional[str] = None,
            event_types: Optional[List[str]] = None,
            limit: Optional[int] = None,
            use_vector_search: bool = True,
            skip_llm_analysis: bool = False
    ) -> List[UserMemory]:
        """
        检索用户的相关记忆

        使用向量相似度检索与当前消息最相关的历史记忆。
        如果没有embedding或current_message为空，则回退到传统的基于规则的检索。

        Args:
            user_id: 用户ID
            bot_id: Bot ID（可选，指定则只检索该Bot相关的记忆）
            current_message: 当前消息（用于向量相似度匹配）
            event_types: 事件类型过滤列表
            limit: 返回数量限制
            use_vector_search: 是否使用向量相似度搜索
            skip_llm_analysis: 是否跳过LLM分析（避免额外的LLM调用）

        Returns:
            相关记忆列表（按相似度/重要性排序）
        """
        trace_id = self._generate_trace_id()
        start_time = time.perf_counter()
        limit = limit or self.max_memories_per_query

        logger.debug(
            f"🔎 [Memory-Retrieve][{trace_id}] START retrieve_memories | "
            f"user_id={user_id} | bot_id={bot_id} | limit={limit} | "
            f"use_vector_search={use_vector_search} | "
            f"has_current_message={current_message is not None}"
        )

        if current_message:
            logger.debug(
                f"🔎 [Memory-Retrieve][{trace_id}] current_message preview: "
                f"{current_message[:100]}{'...' if len(current_message) > 100 else ''}"
            )

        # 尝试使用向量相似度检索
        if (use_vector_search and
                current_message and
                self.embedding_service and
                self.embedding_service.provider):
            try:
                logger.debug(f"🔎 [Memory-Retrieve][{trace_id}] Attempting vector similarity search...")

                memories = await self._retrieve_by_vector_similarity(
                    user_id=user_id,
                    bot_id=bot_id,
                    current_message=current_message,
                    event_types=event_types,
                    limit=limit,
                    trace_id=trace_id
                )
                if memories:
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    logger.info(
                        f"✅ [Memory-Retrieve][{trace_id}] END vector search | "
                        f"latency={latency_ms:.1f}ms | retrieved={len(memories)} memories"
                    )
                    return memories

                logger.debug(f"🔎 [Memory-Retrieve][{trace_id}] Vector search returned no results, falling back...")

            except Exception as e:
                logger.warning(
                    f"⚠️ [Memory-Retrieve][{trace_id}] Vector search failed, falling back to metadata retrieval | "
                    f"error_type={type(e).__name__} | error={e}"
                )
        else:
            reasons = []
            if not use_vector_search:
                reasons.append("vector_search_disabled")
            if not current_message:
                reasons.append("no_current_message")
            if not self.embedding_service:
                reasons.append("no_embedding_service")
            elif not self.embedding_service.provider:
                reasons.append("no_embedding_provider")

            logger.debug(
                f"🔎 [Memory-Retrieve][{trace_id}] Skipping vector search | reasons={reasons}"
            )

        # 回退到传统检索
        logger.debug(f"🔎 [Memory-Retrieve][{trace_id}] Using metadata-based retrieval...")
        memories = await self._retrieve_by_metadata(
            user_id=user_id,
            bot_id=bot_id,
            current_message=current_message,
            event_types=event_types,
            limit=limit,
            skip_llm_analysis=skip_llm_analysis,
            trace_id=trace_id
        )

        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"✅ [Memory-Retrieve][{trace_id}] END metadata search | "
            f"latency={latency_ms:.1f}ms | retrieved={len(memories)} memories"
        )

        return memories

    async def _retrieve_by_vector_similarity(
            self,
            user_id: int,
            bot_id: Optional[int],
            current_message: str,
            event_types: Optional[List[str]],
            limit: int,
            trace_id: str = ""
    ) -> List[UserMemory]:
        """
        使用向量相似度检索记忆

        1. 生成查询消息的向量嵌入
        2. 从数据库获取用户的所有有embedding的记忆
        3. 计算相似度并排序
        4. 返回最相关的记忆
        """
        # 生成查询向量
        logger.debug(f"🔢 [Memory-VectorSearch][{trace_id}] Generating query embedding...")
        embedding_start = time.perf_counter()

        query_result = await self.embedding_service.embed_text(current_message)
        query_embedding = np.array(query_result.embedding, dtype=np.float32)

        embedding_latency = (time.perf_counter() - embedding_start) * 1000
        logger.debug(
            f"🔢 [Memory-VectorSearch][{trace_id}] Query embedding generated | "
            f"latency={embedding_latency:.1f}ms | dim={len(query_embedding)} | "
            f"model={query_result.model}"
        )

        # 构建基础查询 - 获取所有有embedding的记忆
        query = select(UserMemory).where(
            and_(
                UserMemory.user_id == user_id,
                UserMemory.is_active == True,
                UserMemory.embedding.isnot(None)
            )
        )

        # 如果指定了Bot ID，添加过滤
        if bot_id is not None:
            query = query.where(
                or_(
                    UserMemory.bot_id == bot_id,
                    UserMemory.bot_id.is_(None)
                )
            )

        # 如果指定了事件类型，添加过滤
        if event_types:
            query = query.where(UserMemory.event_type.in_(event_types))
            logger.debug(f"🔢 [Memory-VectorSearch][{trace_id}] Filtering by event_types: {event_types}")

        db_start = time.perf_counter()
        result = await self.db.execute(query)
        memories = list(result.scalars().all())
        db_latency = (time.perf_counter() - db_start) * 1000

        logger.debug(
            f"🔢 [Memory-VectorSearch][{trace_id}] Fetched {len(memories)} memories with embeddings | "
            f"db_latency={db_latency:.1f}ms"
        )

        if not memories:
            return []

        # 计算余弦相似度
        logger.debug(f"🔢 [Memory-VectorSearch][{trace_id}] Computing cosine similarities...")
        similarity_start = time.perf_counter()

        scored_memories: List[Tuple[UserMemory, float]] = []
        for memory in memories:
            if memory.embedding:
                memory_embedding = np.array(memory.embedding, dtype=np.float32)
                similarity = self._cosine_similarity(query_embedding, memory_embedding)

                logger.debug(
                    f"🔢 [Memory-VectorSearch][{trace_id}] Memory {memory.id}: "
                    f"similarity={similarity:.4f} | threshold={self.similarity_threshold} | "
                    f"preview={memory.event_summary[:50]}..."
                )

                if similarity >= self.similarity_threshold:
                    scored_memories.append((memory, similarity))

        similarity_latency = (time.perf_counter() - similarity_start) * 1000
        logger.debug(
            f"🔢 [Memory-VectorSearch][{trace_id}] Similarity computation done | "
            f"latency={similarity_latency:.1f}ms | "
            f"above_threshold={len(scored_memories)}/{len(memories)}"
        )

        # 按相似度排序并取top_k
        scored_memories.sort(key=lambda x: x[1], reverse=True)
        top_memories = [m for m, _ in scored_memories[:limit]]

        if top_memories:
            logger.debug(f"🔢 [Memory-VectorSearch][{trace_id}] Top {len(top_memories)} memories selected:")
            for i, (memory, score) in enumerate(scored_memories[:limit]):
                logger.debug(
                    f"  [{i + 1}] id={memory.id} | similarity={score:.4f} | "
                    f"type={memory.event_type} | summary={memory.event_summary[:60]}..."
                )

        # 更新访问计数和时间
        if top_memories:
            memory_ids = [m.id for m in top_memories]
            await self.db.execute(
                update(UserMemory)
                .where(UserMemory.id.in_(memory_ids))
                .values(
                    access_count=UserMemory.access_count + 1,
                    last_accessed_at=datetime.utcnow()
                )
            )
            await self.db.commit()
            logger.debug(f"🔢 [Memory-VectorSearch][{trace_id}] Updated access count for {len(memory_ids)} memories")

        return top_memories

    async def _retrieve_by_metadata(
            self,
            user_id: int,
            bot_id: Optional[int],
            current_message: Optional[str],
            event_types: Optional[List[str]],
            limit: int,
            skip_llm_analysis: bool = False,
            trace_id: str = ""
    ) -> List[UserMemory]:
        """
        使用元数据（关键词、事件类型等）检索记忆

        这是向量检索不可用时的回退方案。
        """
        logger.debug(f"📋 [Memory-MetadataSearch][{trace_id}] Building metadata query...")

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
            logger.debug(f"📋 [Memory-MetadataSearch][{trace_id}] Filtering by event_types: {event_types}")

        # 如果有当前消息且有LLM，且未设置跳过标志，尝试智能匹配
        if current_message and self.llm_provider and not skip_llm_analysis:
            try:
                logger.debug(f"📋 [Memory-MetadataSearch][{trace_id}] Analyzing retrieval needs with LLM...")
                retrieval_analysis = await self._analyze_retrieval_needs(current_message, trace_id)

                if retrieval_analysis.get("should_retrieve", False):
                    if retrieval_analysis.get("event_types"):
                        query = query.where(
                            UserMemory.event_type.in_(retrieval_analysis["event_types"])
                        )
                        logger.debug(
                            f"📋 [Memory-MetadataSearch][{trace_id}] LLM suggested event_types: "
                            f"{retrieval_analysis['event_types']}"
                        )
            except Exception as e:
                logger.warning(
                    f"⚠️ [Memory-MetadataSearch][{trace_id}] Error in retrieval analysis | error={e}"
                )
        elif skip_llm_analysis:
            logger.debug(f"📋 [Memory-MetadataSearch][{trace_id}] Skipping LLM analysis (skip_llm_analysis=True)")

        # 按重要性和访问时间排序
        query = query.order_by(
            UserMemory.importance.desc(),
            UserMemory.last_accessed_at.desc().nullsfirst(),
            UserMemory.created_at.desc()
        ).limit(limit)

        db_start = time.perf_counter()
        result = await self.db.execute(query)
        memories = list(result.scalars().all())
        db_latency = (time.perf_counter() - db_start) * 1000

        logger.debug(
            f"📋 [Memory-MetadataSearch][{trace_id}] Query executed | "
            f"db_latency={db_latency:.1f}ms | retrieved={len(memories)} memories"
        )

        if memories:
            logger.debug(f"📋 [Memory-MetadataSearch][{trace_id}] Retrieved memories:")
            for i, memory in enumerate(memories):
                logger.debug(
                    f"  [{i + 1}] id={memory.id} | importance={memory.importance} | "
                    f"type={memory.event_type} | summary={memory.event_summary[:60]}..."
                )

        # 更新访问计数和时间
        if memories:
            memory_ids = [m.id for m in memories]
            await self.db.execute(
                update(UserMemory)
                .where(UserMemory.id.in_(memory_ids))
                .values(
                    access_count=UserMemory.access_count + 1,
                    last_accessed_at=datetime.utcnow()
                )
            )
            await self.db.commit()
            logger.debug(f"📋 [Memory-MetadataSearch][{trace_id}] Updated access count for {len(memory_ids)} memories")

        return memories

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算两个向量的余弦相似度"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    async def _analyze_retrieval_needs(self, current_message: str, trace_id: str = "") -> Dict[str, Any]:
        """
        分析当前消息的记忆检索需求

        使用LLM判断当前消息是否需要回忆历史记忆。
        """
        start_time = time.perf_counter()
        logger.debug(f"🔍 [Memory-RetrievalAnalysis][{trace_id}] START analyzing retrieval needs...")

        try:
            response = await self.llm_provider.generate_response(
                [{"role": "user", "content": f"用户消息: {current_message}"}],
                context=self.MEMORY_RETRIEVAL_PROMPT
            )

            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(
                f"🔍 [Memory-RetrievalAnalysis][{trace_id}] LLM response received | "
                f"latency={latency_ms:.1f}ms"
            )

            response_text = response.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]

            result = json.loads(response_text.strip())
            logger.debug(
                f"🔍 [Memory-RetrievalAnalysis][{trace_id}] END analysis | "
                f"should_retrieve={result.get('should_retrieve')} | "
                f"event_types={result.get('event_types')}"
            )

            return result

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(
                f"⚠️ [Memory-RetrievalAnalysis][{trace_id}] Error in retrieval analysis | "
                f"latency={latency_ms:.1f}ms | error={e}"
            )
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
        trace_id = self._generate_trace_id()
        logger.debug(f"🗑️ [Memory-Delete][{trace_id}] Deleting memory_id={memory_id}")

        result = await self.db.execute(
            update(UserMemory)
            .where(UserMemory.id == memory_id)
            .values(is_active=False, updated_at=datetime.utcnow())
        )
        await self.db.commit()

        success = result.rowcount > 0
        logger.debug(
            f"🗑️ [Memory-Delete][{trace_id}] Delete {'succeeded' if success else 'failed'} | "
            f"memory_id={memory_id} | rows_affected={result.rowcount}"
        )

        return success

    async def get_user_memory_stats(self, user_id: int) -> Dict[str, Any]:
        """
        获取用户记忆统计信息

        Args:
            user_id: 用户ID

        Returns:
            统计信息字典
        """
        trace_id = self._generate_trace_id()
        logger.debug(f"📊 [Memory-Stats][{trace_id}] Getting stats for user_id={user_id}")

        # 总记忆数
        total_query = select(func.count(UserMemory.id)).where(
            and_(UserMemory.user_id == user_id, UserMemory.is_active == True)
        )
        total_result = await self.db.execute(total_query)
        total_count = total_result.scalar() or 0

        # 有embedding的记忆数
        embedded_query = select(func.count(UserMemory.id)).where(
            and_(
                UserMemory.user_id == user_id,
                UserMemory.is_active == True,
                UserMemory.embedding.isnot(None)
            )
        )
        embedded_result = await self.db.execute(embedded_query)
        embedded_count = embedded_result.scalar() or 0

        # 按事件类型分组统计
        type_query = select(
            UserMemory.event_type,
            func.count(UserMemory.id)
        ).where(
            and_(UserMemory.user_id == user_id, UserMemory.is_active == True)
        ).group_by(UserMemory.event_type)

        type_result = await self.db.execute(type_query)
        type_counts = {row[0]: row[1] for row in type_result.all()}

        stats = {
            "total_memories": total_count,
            "embedded_memories": embedded_count,
            "embedding_coverage": embedded_count / total_count if total_count > 0 else 0,
            "by_event_type": type_counts
        }

        logger.debug(f"📊 [Memory-Stats][{trace_id}] Stats: {json.dumps(stats)}")

        return stats

    async def backfill_embeddings(
            self,
            user_id: Optional[int] = None,
            batch_size: int = 50
    ) -> Dict[str, int]:
        """
        为没有embedding的记忆生成向量嵌入

        用于迁移现有数据或重新生成丢失的embedding。

        Args:
            user_id: 指定用户ID（可选，不指定则处理所有用户）
            batch_size: 每批处理的记忆数量

        Returns:
            处理统计信息
        """
        trace_id = self._generate_trace_id()
        logger.info(
            f"🔄 [Memory-Backfill][{trace_id}] START backfill_embeddings | "
            f"user_id={user_id} | batch_size={batch_size}"
        )

        if not self.embedding_service or not self.embedding_service.provider:
            logger.warning(
                f"⚠️ [Memory-Backfill][{trace_id}] No embedding service configured, cannot backfill"
            )
            return {"processed": 0, "failed": 0, "skipped": 0}

        # 构建查询 - 获取没有embedding的记忆
        query = select(UserMemory).where(
            and_(
                UserMemory.is_active == True,
                UserMemory.embedding.is_(None)
            )
        )

        if user_id is not None:
            query = query.where(UserMemory.user_id == user_id)

        query = query.limit(batch_size)

        result = await self.db.execute(query)
        memories = list(result.scalars().all())

        logger.debug(f"🔄 [Memory-Backfill][{trace_id}] Found {len(memories)} memories without embeddings")

        processed = 0
        failed = 0

        for memory in memories:
            try:
                logger.debug(
                    f"🔄 [Memory-Backfill][{trace_id}] Processing memory_id={memory.id} | "
                    f"summary={memory.event_summary[:50]}..."
                )

                # 生成embedding
                embed_result = await self.embedding_service.embed_text(memory.event_summary)

                # 更新记忆
                await self.db.execute(
                    update(UserMemory)
                    .where(UserMemory.id == memory.id)
                    .values(
                        embedding=embed_result.embedding,
                        embedding_model=embed_result.model,
                        updated_at=datetime.utcnow()
                    )
                )
                processed += 1

                logger.debug(
                    f"🔄 [Memory-Backfill][{trace_id}] memory_id={memory.id} embedding generated | "
                    f"dim={len(embed_result.embedding)}"
                )

            except Exception as e:
                logger.warning(
                    f"⚠️ [Memory-Backfill][{trace_id}] Failed to generate embedding for memory_id={memory.id} | "
                    f"error={e}"
                )
                failed += 1

        await self.db.commit()

        remaining = await self._count_memories_without_embedding(user_id)

        result_stats = {
            "processed": processed,
            "failed": failed,
            "remaining": remaining
        }

        logger.info(
            f"✅ [Memory-Backfill][{trace_id}] END backfill_embeddings | "
            f"processed={processed} | failed={failed} | remaining={remaining}"
        )

        return result_stats

    async def _count_memories_without_embedding(self, user_id: Optional[int] = None) -> int:
        """统计没有embedding的记忆数量"""
        query = select(func.count(UserMemory.id)).where(
            and_(
                UserMemory.is_active == True,
                UserMemory.embedding.is_(None)
            )
        )

        if user_id is not None:
            query = query.where(UserMemory.user_id == user_id)

        result = await self.db.execute(query)
        return result.scalar() or 0


# 全局服务实例获取函数
_memory_service_cache: Dict[str, ConversationMemoryService] = {}


def get_conversation_memory_service(
        db: AsyncSession,
        llm_provider=None,
        embedding_service=None
) -> ConversationMemoryService:
    """
    获取对话记忆服务实例

    Args:
        db: 数据库会话
        llm_provider: LLM提供者
        embedding_service: 向量嵌入服务（可选，不传则自动获取）

    Returns:
        ConversationMemoryService实例
    """
    # 如果没有传入embedding_service，尝试自动获取
    if embedding_service is None:
        try:
            from .embedding_service import get_embedding_service
            embedding_service = get_embedding_service()
        except Exception as e:
            logger.warning(f"Could not auto-configure embedding service: {e}")

    return ConversationMemoryService(db, llm_provider, embedding_service)
