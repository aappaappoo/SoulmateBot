"""
搜索Agent - 实时网络搜索和信息检索

这个Agent实现了 RAG + Web Retrieval 的标准模式，提供实时资讯查询能力。
Agent 的选择完全由 LLM 根据 self._description 语义匹配决定，
不使用关键词列表或硬编码判断逻辑。

流程：
1. 编排器 LLM 判断用户意图匹配此 Agent 的 description
2. 调用搜索 API → 获取 top-k snippets
3. 网页抓取 + 文本清洗（可选）
4. 拼接 prompt → LLM 生成回答
5. 返回用户

特性：
- 多 SERP API key 轮用（Redis 管理）
- 搜索结果缓存（减少重复查询）
- 支持多种搜索提供商
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from loguru import logger

from src.agents import BaseAgent, Message, ChatContext, AgentResponse, SQLiteMemoryStore
from src.services.serp_api_service import serp_api_service
from telegram.constants import ParseMode


class SearchAgent(BaseAgent):
    """
    搜索Agent - 提供实时网络搜索能力
    
    专长领域:
    - 实时资讯查询：新闻、热点、最新动态
    - 事实性问题：人物、事件、地点信息
    - 最新信息：天气、股票、体育赛事结果
    - 知识问答：需要互联网信息补充的问题
    
    适用场景:
    - "梅西最近动态是什么？"
    - "今天有什么新闻？"
    - "iPhone 16 什么时候发布？"
    - "最近的科技新闻有哪些？"
    
    技术特点:
    - RAG + Web Retrieval 标准模式
    - 多 API key 轮用避免限流
    - Redis 缓存热门查询结果
    """

    def __init__(self, memory_store=None, llm_provider=None):
        """
        初始化搜索Agent
        
        参数:
            memory_store: 可选的记忆存储实例
            llm_provider: 可选的LLM服务提供者，用于生成最终回答
        """
        self._name = "SearchAgent"
        self._description = (
            "提供实时网络搜索能力的Agent。"
            "可以查询最新新闻、实时资讯、热点事件、事实性问题、天气、股票等。"
            "适用于需要互联网信息补充的问题。"
            "当用明确说明需要进行网络搜索时需要被调用"
        )
        self._memory = memory_store or SQLiteMemoryStore()
        self._llm_provider = llm_provider

        # 搜索技能定义
        self._skills = ["web_search", "news_query", "realtime_info"]
        self._skill_keywords = {}
        self._skill_descriptions = {
            "web_search": "网络搜索，获取互联网上的相关信息",
            "news_query": "新闻查询，获取最新的新闻资讯",
            "realtime_info": "实时信息查询，获取最新的实时数据"
        }

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
        """Agent提供的技能列表"""
        return self._skills

    @property
    def skill_keywords(self) -> Dict[str, List[str]]:
        """技能对应的关键词映射"""
        return self._skill_keywords

    def get_skill_description(self, skill_id: str) -> Optional[str]:
        """获取指定技能的描述"""
        return self._skill_descriptions.get(skill_id)

    def can_handle(self, message: Message, context: ChatContext) -> float:
        """
        返回基础置信度，实际选择由编排器中的 LLM 根据 description 决定。
        仅保留 @提及 的精确匹配。
        """
        # 检查@提及
        if message.has_mention(self.name):
            return 1.0

        return 0.0

    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        """
        执行搜索并生成响应

        处理流程:
        1. 提取搜索查询
        2. 执行搜索获取 top-k snippets
        3. 生成基于搜索结果的回答
        4. 更新使用记录
        """
        # 读取用户历史
        user_memory = self.memory_read(message.user_id)
        search_count = user_memory.get("search_count", 0)

        content = message.get_clean_content()

        # 提取搜索查询（简单处理：直接使用用户输入）
        query = self._extract_query(content)

        # 判断是否需要抓取网页内容
        fetch_content = self._should_fetch_content(content)

        # 执行搜索
        logger.info(f"SearchAgent: Searching for: {query}")
        search_result = serp_api_service.search_with_content(
            query=query,
            fetch_content=fetch_content,
            use_cache=True
        )

        # 生成响应
        if search_result.get("success"):
            response_content = self._generate_response(query, search_result, context)
            if isinstance(response_content, tuple):
                response_content, parse_mode = response_content
            else:
                response_content = response_content
                parse_mode = None

            metadata = {
                "search_query": query,
                "snippets_count": len(search_result.get("snippets", [])),
                "provider": search_result.get("provider"),
                "cached": search_result.get("cached", False)
            }
            if parse_mode:
                metadata["parse_mode"] = parse_mode
        else:
            response_content = self._generate_error_response(query, search_result.get("error"))
            metadata = {
                "search_query": query,
                "error": search_result.get("error")
            }

        # 更新使用记录
        user_memory["search_count"] = search_count + 1
        user_memory["last_query"] = query
        user_memory["last_search_time"] = datetime.now().isoformat()
        self.memory_write(message.user_id, user_memory)
        return AgentResponse(
            content=response_content,
            agent_name=self.name,
            confidence=0.85 if search_result.get("success") else 0.5,
            metadata=metadata,
            should_continue=False
        )

    def _extract_query(self, content: str) -> str:
        """
        从用户消息中提取搜索查询
        
        参数:
            content: 用户消息内容
            
        返回值:
            str: 提取的搜索查询
        """
        # 移除常见的搜索指令词
        query = content
        remove_phrases = [
            "帮我搜索", "帮我查", "帮我找", "搜索一下", "查一下", "查查",
            "搜一下", "找一下", "请问", "告诉我", "我想知道",
            "search for", "look up", "find", "google"
        ]

        for phrase in remove_phrases:
            query = query.replace(phrase, "").strip()

        # 如果处理后太短，使用原始内容
        if len(query) < 2:
            query = content

        return query

    def _should_fetch_content(self, content: str) -> bool:
        """
        判断是否需要抓取网页详细内容
        
        参数:
            content: 用户消息内容
            
        返回值:
            bool: 是否需要抓取详细内容
        """
        # 如果用户明确要求详细信息，则抓取
        detail_keywords = ["详细", "具体", "完整", "全部", "更多", "详情"]
        return any(keyword in content for keyword in detail_keywords)

    def _generate_response(self, query: str, search_result: Dict[str, Any],
                           context: ChatContext) -> str:
        """
        基于搜索结果生成响应
        
        参数:
            query: 搜索查询
            search_result: 搜索结果
            context: 聊天上下文
            
        返回值:
            str: 生成的响应文本
        """
        snippets = search_result.get("snippets", [])

        if not snippets:
            return f"🔍 抱歉，没有找到关于「{query}」的相关信息。\n请尝试换一个关键词搜索。"

        # 如果有LLM提供者，使用LLM生成更自然的回答
        if self._llm_provider:
            return self._generate_llm_response(query, snippets, context)
        template_result = self._generate_template_response(query, snippets, search_result)
        return template_result

    def _generate_llm_response(self, query: str, snippets: List[Dict],
                               context: ChatContext) -> str:
        """
        使用LLM基于搜索结果生成回答
        
        参数:
            query: 搜索查询
            snippets: 搜索结果摘要列表
            context: 聊天上下文
            
        返回值:
            str: LLM生成的回答
        """
        # 构建RAG prompt
        snippets_text = ""
        for i, snippet in enumerate(snippets, 1):
            snippets_text += f"\n[来源{i}] {snippet.get('title', '')}\n"
            snippets_text += f"摘要: {snippet.get('snippet', '')}\n"
            if snippet.get('full_content'):
                snippets_text += f"详细内容: {snippet.get('full_content', '')[:500]}...\n"

        prompt = f"""基于以下搜索结果，回答用户的问题。

用户问题: {query}

搜索结果:
{snippets_text}

请综合以上信息，生成一个准确、有帮助的回答。如果搜索结果不足以完整回答问题，请说明。
请用友好、专业的语气回答，适当引用信息来源。"""

        try:
            # 调用LLM生成回答
            response = self._llm_provider.generate(prompt)
            return f"🔍 关于「{query}」的搜索结果：\n\n{response}"
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            return self._generate_template_response(query, snippets, {})

    def _generate_template_response(self, query: str, snippets: List[Dict],
                                    search_result: Dict[str, Any]) -> Tuple[str, str]:
        """
        使用模板生成响应（HTML格式）
        """
        import html
        response = f"🔍 关于「{html.escape(query)}」的搜索结果：\n\n"
        for i, snippet in enumerate(snippets, 1):
            title = html.escape(snippet.get("title", "无标题"))
            text = html.escape(snippet.get("snippet", ""))
            link = snippet.get("link", "")
            response += f"📌 <b>{i}. {title}</b>\n"
            if text:
                response += f"{text}\n"
            if link:
                response += f'🔗 <a href="{html.escape(link)}">查看详情</a>\n'
            response += "\n"
        provider = search_result.get("provider", "unknown")
        if provider == "mock":
            response += "\n⚠️ 注意：这是模拟搜索结果。请配置真实的 SERP API key 获取实际搜索结果。"
        response += f"\n📅 搜索时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        return response, ParseMode.HTML

    def _generate_error_response(self, query: str, error: str) -> str:
        """
        生成错误响应
        
        参数:
            query: 搜索查询
            error: 错误信息
            
        返回值:
            str: 错误响应文本
        """
        return (
            f"🔍 搜索「{query}」时遇到问题：\n\n"
            f"❌ {error}\n\n"
            "请稍后重试，或者尝试换一个关键词搜索。"
        )

    def memory_read(self, user_id: str) -> Dict[str, Any]:
        """
        读取用户的搜索历史
        
        存储内容：
        - search_count: 搜索次数
        - last_query: 最后搜索的查询
        - last_search_time: 最后搜索时间
        """
        return self._memory.read(self.name, user_id)

    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        """
        保存用户的搜索历史
        
        用于统计和个性化服务
        """
        self._memory.write(self.name, user_id, data)

    def get_search_stats(self) -> Dict[str, Any]:
        """
        获取搜索服务统计信息
        
        Returns:
            Dict: 搜索服务状态和统计信息
        """
        return serp_api_service.health_check()
