"""
群组监控Agent

用于监控Telegram群组讨论，收集消息，并总结主要话题。

功能：
1. 接收群组监控请求
2. 管理监控配置
3. 分析群组讨论
4. 生成话题总结报告
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import re
from src.agents import BaseAgent, Message, ChatContext, AgentResponse, SQLiteMemoryStore


class GroupMonitorAgent(BaseAgent):
    """
    群组监控Agent - 监控群组讨论并总结话题
    
    专长领域:
    - 群组消息监控
    - 话题识别与总结
    - 讨论分析报告
    - 活跃用户统计
    
    适用场景:
    - "监控这个群组的讨论"
    - "总结群里最近的讨论"
    - "分析群聊话题"
    """
    
    def __init__(self, memory_store=None):
        """
        初始化群组监控Agent
        
        Args:
            memory_store: 可选的记忆存储实例
        """
        self._name = "GroupMonitorAgent"
        self._description = (
            "监控Telegram群组讨论，收集消息并分析总结主要话题。"
            "可以帮助了解群组讨论内容，识别热门话题和活跃用户。"
        )
        self._memory = memory_store or SQLiteMemoryStore()
        
        # 监控相关的关键词
        self._monitor_keywords = [
            # 监控动作
            "监控", "monitor", "监听", "观察", "追踪", "track",
            "watch", "observe",
            
            # 群组相关
            "群", "群组", "群聊", "group", "chat", "频道", "channel",
            
            # 分析动作
            "分析", "总结", "summarize", "summary", "analyze", "analysis",
            "报告", "report",
            
            # 话题相关
            "话题", "topic", "讨论", "discussion", "主题", "subject",
            
            # 时间相关
            "最近", "今天", "昨天", "这周", "recent", "today", "yesterday",
        ]
        
        # 群组链接正则
        self._group_link_pattern = re.compile(
            r'(https?://)?t\.me/([a-zA-Z0-9_]+)',
            re.IGNORECASE
        )
    
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
        
        对于监控和分析群组相关的消息返回高置信度。
        
        返回值:
            float: 置信度分数 (0.0-1.0)
        """
        # 检查@提及
        if message.has_mention(self.name):
            return 1.0
        
        content = message.content.lower()
        
        # 检查是否包含群组链接
        if self._group_link_pattern.search(message.content):
            # 包含群组链接，检查是否有监控/分析意图
            if any(kw in content for kw in ["监控", "monitor", "分析", "总结", "analyze", "summary"]):
                return 0.95
        
        # 统计关键词匹配
        keyword_matches = sum(1 for kw in self._monitor_keywords if kw in content)
        
        if keyword_matches >= 3:
            confidence = 0.9
        elif keyword_matches == 2:
            confidence = 0.7
        elif keyword_matches == 1:
            confidence = 0.5
        else:
            confidence = 0.0
        
        return confidence
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        """
        生成响应
        
        处理群组监控相关的请求。
        """
        # 读取用户记忆
        user_memory = self.memory_read(message.user_id)
        interaction_count = user_memory.get("interaction_count", 0)
        
        content = message.get_clean_content().lower()
        
        # 提取群组链接
        group_link = self._extract_group_link(message.content)
        
        # 判断请求类型
        if "开始" in content or "监控" in content or "start" in content or "monitor" in content:
            response = self._handle_start_monitor(message, group_link, user_memory)
            action = "start_monitor"
        elif "停止" in content or "结束" in content or "stop" in content or "end" in content:
            response = self._handle_stop_monitor(message, user_memory)
            action = "stop_monitor"
        elif "总结" in content or "分析" in content or "报告" in content or "summary" in content or "report" in content:
            response = self._handle_generate_summary(message, user_memory)
            action = "generate_summary"
        elif "状态" in content or "status" in content:
            response = self._handle_check_status(message, user_memory)
            action = "check_status"
        else:
            response = self._handle_general_request(message, interaction_count)
            action = "general"
        
        # 更新用户记忆
        user_memory["interaction_count"] = interaction_count + 1
        user_memory["last_action"] = action
        user_memory["last_message"] = message.content
        if group_link:
            user_memory["last_group_link"] = group_link
        self.memory_write(message.user_id, user_memory)
        
        return AgentResponse(
            content=response,
            agent_name=self.name,
            confidence=0.85,
            metadata={
                "action": action,
                "group_link": group_link,
            },
            should_continue=False
        )
    
    def _extract_group_link(self, text: str) -> Optional[str]:
        """提取群组链接"""
        match = self._group_link_pattern.search(text)
        if match:
            return f"https://t.me/{match.group(2)}"
        return None
    
    def _handle_start_monitor(
        self,
        message: Message,
        group_link: Optional[str],
        user_memory: Dict[str, Any]
    ) -> str:
        """处理开始监控请求"""
        if not group_link:
            # 检查是否有之前保存的群组链接
            saved_link = user_memory.get("last_group_link")
            if saved_link:
                group_link = saved_link
            else:
                return (
                    "📡 **开始群组监控**\n\n"
                    "请提供群组链接来开始监控：\n\n"
                    "格式：\n"
                    "• `监控 https://t.me/群组名`\n"
                    "• `监控 t.me/群组名`\n\n"
                    "可选参数：\n"
                    "• 开始时间：`从今天开始`\n"
                    "• 结束时间：`到明天结束`\n"
                    "• 关键词：`关注：比特币,以太坊`\n\n"
                    "示例：\n"
                    "`监控 https://t.me/crypto_group 从今天开始`"
                )
        
        return (
            f"📡 **群组监控配置**\n\n"
            f"🔗 目标群组: {group_link}\n"
            f"📅 开始时间: 现在\n"
            f"📊 状态: 准备就绪\n\n"
            f"⚠️ **注意事项:**\n"
            f"1. Bot需要加入目标群组才能监控\n"
            f"2. 确保Bot有读取消息的权限\n\n"
            f"🚀 请使用以下命令确认启动监控：\n"
            f"`/start_monitor {group_link}`\n\n"
            f"或者回复\"确认\"开始监控。"
        )
    
    def _handle_stop_monitor(
        self,
        message: Message,
        user_memory: Dict[str, Any]
    ) -> str:
        """处理停止监控请求"""
        # 检查是否有活跃的监控
        active_monitors = user_memory.get("active_monitors", [])
        
        if not active_monitors:
            return (
                "⏹️ **停止监控**\n\n"
                "当前没有活跃的监控任务。\n\n"
                "使用以下命令查看所有监控：\n"
                "`/my_monitors`"
            )
        
        return (
            "⏹️ **停止监控**\n\n"
            f"发现 {len(active_monitors)} 个活跃的监控任务。\n\n"
            "请选择要停止的监控：\n"
            + "\n".join([f"• {m.get('group_link', '未知')}" for m in active_monitors[:5]])
            + "\n\n使用命令 `/stop_monitor <id>` 停止指定监控。"
        )
    
    def _handle_generate_summary(
        self,
        message: Message,
        user_memory: Dict[str, Any]
    ) -> str:
        """处理生成总结请求"""
        group_link = self._extract_group_link(message.content)
        
        if not group_link:
            group_link = user_memory.get("last_group_link")
        
        if not group_link:
            return (
                "📊 **生成话题总结**\n\n"
                "请指定要总结的群组：\n\n"
                "格式：\n"
                "• `总结 https://t.me/群组名`\n"
                "• `分析最近7天的讨论 t.me/群组名`\n\n"
                "可选时间范围：\n"
                "• `最近24小时` / `今天`\n"
                "• `最近7天` / `这周`\n"
                "• `从2024-01-01到2024-01-07`"
            )
        
        return (
            f"📊 **话题总结生成中...**\n\n"
            f"🔗 群组: {group_link}\n"
            f"📅 时间范围: 最近7天\n\n"
            f"正在分析群组讨论内容...\n"
            f"请稍候，这可能需要一些时间。\n\n"
            f"💡 完成后，您将收到包含以下内容的报告：\n"
            f"• 主要讨论话题\n"
            f"• 话题摘要\n"
            f"• 活跃用户统计\n"
            f"• 情感分析\n\n"
            f"使用 `/report {group_link}` 查看详细报告。"
        )
    
    def _handle_check_status(
        self,
        message: Message,
        user_memory: Dict[str, Any]
    ) -> str:
        """处理查看状态请求"""
        active_monitors = user_memory.get("active_monitors", [])
        total_messages = user_memory.get("total_messages_collected", 0)
        
        if not active_monitors:
            return (
                "📈 **监控状态**\n\n"
                "当前没有活跃的监控任务。\n\n"
                "使用以下命令开始新的监控：\n"
                "`监控 https://t.me/群组名`"
            )
        
        status_lines = [
            "📈 **监控状态**\n",
            f"🔄 活跃监控: {len(active_monitors)}",
            f"📝 已收集消息: {total_messages}",
            "",
            "**活跃监控列表:**"
        ]
        
        for i, monitor in enumerate(active_monitors[:5], 1):
            status_lines.append(f"{i}. {monitor.get('group_link', '未知')}")
            status_lines.append(f"   消息: {monitor.get('message_count', 0)}")
        
        return "\n".join(status_lines)
    
    def _handle_general_request(
        self,
        message: Message,
        interaction_count: int
    ) -> str:
        """处理一般请求"""
        if interaction_count == 0:
            return (
                "👋 **你好！我是群组监控助手**\n\n"
                "我可以帮助您监控Telegram群组的讨论，并总结主要话题。\n\n"
                "🔹 **主要功能：**\n"
                "• 监控群组消息\n"
                "• 分析讨论话题\n"
                "• 生成话题报告\n"
                "• 识别活跃用户\n\n"
                "🔹 **常用命令：**\n"
                "• `监控 <群组链接>` - 开始监控\n"
                "• `总结 <群组链接>` - 生成话题总结\n"
                "• `状态` - 查看监控状态\n"
                "• `停止` - 停止监控\n\n"
                "告诉我您想监控哪个群组？"
            )
        else:
            return (
                "📊 **群组监控助手**\n\n"
                "请告诉我您需要什么帮助：\n\n"
                "• `监控 <群组链接>` - 开始监控新群组\n"
                "• `总结` - 分析已监控的群组\n"
                "• `状态` - 查看当前监控状态\n"
                "• `停止` - 停止现有监控"
            )
    
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        """读取用户的监控历史"""
        return self._memory.read(self.name, user_id)
    
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        """保存用户的监控历史"""
        self._memory.write(self.name, user_id, data)
