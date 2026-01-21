"""
Token Counter - Token统计和成本追踪

提供Token使用统计、成本计算和审计功能
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from datetime import datetime, timezone
from loguru import logger
import json


@dataclass
class UsageStats:
    """
    使用统计数据
    
    Attributes:
        prompt_tokens: 输入token数
        completion_tokens: 输出token数
        total_tokens: 总token数
        cost: 预估成本（美元）
        model: 使用的模型
        provider: 服务提供商
        timestamp: 时间戳
        request_id: 请求ID
        user_id: 用户ID
        bot_id: Bot ID
    """
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    model: str = ""
    provider: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    bot_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "model": self.model,
            "provider": self.provider,
            "timestamp": self.timestamp.isoformat(),
            "request_id": self.request_id,
            "user_id": self.user_id,
            "bot_id": self.bot_id
        }


# 模型定价表（每1000 tokens的价格，美元）
# 注意：价格会随时间变化，此表更新于 2024-01
# 建议定期检查并更新，或通过配置文件进行管理
MODEL_PRICING = {
    # OpenAI (价格更新于 2024-01)
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    
    # Anthropic (价格更新于 2024-01)
    "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
    "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
    
    # vLLM (自托管，成本接近0)
    "default": {"input": 0.0, "output": 0.0}
}


class TokenCounter:
    """
    Token统计器 - 追踪和统计token使用情况
    """
    
    def __init__(self):
        # 累计统计
        self._total_stats: Dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "total_requests": 0,
            "total_cost": 0.0
        }
        
        # 按用户统计
        self._user_stats: Dict[str, Dict[str, int]] = {}
        
        # 按Bot统计
        self._bot_stats: Dict[str, Dict[str, int]] = {}
        
        # 按模型统计
        self._model_stats: Dict[str, Dict[str, int]] = {}
        
        # 历史记录（最近1000条）
        self._history: List[UsageStats] = []
        self._max_history = 1000
    
    def calculate_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """
        计算API调用成本
        
        Args:
            model: 模型名称
            prompt_tokens: 输入token数
            completion_tokens: 输出token数
            
        Returns:
            预估成本（美元）
        """
        pricing = MODEL_PRICING.get(model, MODEL_PRICING.get("default", {"input": 0, "output": 0}))
        
        input_cost = (prompt_tokens / 1000) * pricing["input"]
        output_cost = (completion_tokens / 1000) * pricing["output"]
        
        return round(input_cost + output_cost, 6)
    
    def record_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        provider: str,
        user_id: Optional[str] = None,
        bot_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> UsageStats:
        """
        记录使用情况
        
        Args:
            prompt_tokens: 输入token数
            completion_tokens: 输出token数
            model: 模型名称
            provider: 服务提供商
            user_id: 用户ID
            bot_id: Bot ID
            request_id: 请求ID
            
        Returns:
            UsageStats对象
        """
        total_tokens = prompt_tokens + completion_tokens
        cost = self.calculate_cost(model, prompt_tokens, completion_tokens)
        
        stats = UsageStats(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            model=model,
            provider=provider,
            user_id=user_id,
            bot_id=bot_id,
            request_id=request_id
        )
        
        # 更新累计统计
        self._total_stats["prompt_tokens"] += prompt_tokens
        self._total_stats["completion_tokens"] += completion_tokens
        self._total_stats["total_tokens"] += total_tokens
        self._total_stats["total_requests"] += 1
        self._total_stats["total_cost"] += cost
        
        # 更新用户统计
        if user_id:
            if user_id not in self._user_stats:
                self._user_stats[user_id] = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "requests": 0,
                    "cost": 0.0
                }
            self._user_stats[user_id]["prompt_tokens"] += prompt_tokens
            self._user_stats[user_id]["completion_tokens"] += completion_tokens
            self._user_stats[user_id]["total_tokens"] += total_tokens
            self._user_stats[user_id]["requests"] += 1
            self._user_stats[user_id]["cost"] += cost
        
        # 更新Bot统计
        if bot_id:
            if bot_id not in self._bot_stats:
                self._bot_stats[bot_id] = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "requests": 0,
                    "cost": 0.0
                }
            self._bot_stats[bot_id]["prompt_tokens"] += prompt_tokens
            self._bot_stats[bot_id]["completion_tokens"] += completion_tokens
            self._bot_stats[bot_id]["total_tokens"] += total_tokens
            self._bot_stats[bot_id]["requests"] += 1
            self._bot_stats[bot_id]["cost"] += cost
        
        # 更新模型统计
        if model not in self._model_stats:
            self._model_stats[model] = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "requests": 0,
                "cost": 0.0
            }
        self._model_stats[model]["prompt_tokens"] += prompt_tokens
        self._model_stats[model]["completion_tokens"] += completion_tokens
        self._model_stats[model]["total_tokens"] += total_tokens
        self._model_stats[model]["requests"] += 1
        self._model_stats[model]["cost"] += cost
        
        # 添加到历史记录
        self._history.append(stats)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        
        logger.debug(
            f"Token usage recorded: {total_tokens} tokens, ${cost:.6f} "
            f"(model: {model}, user: {user_id})"
        )
        
        return stats
    
    def get_total_stats(self) -> Dict:
        """获取总体统计"""
        return dict(self._total_stats)
    
    def get_user_stats(self, user_id: str) -> Optional[Dict]:
        """获取用户统计"""
        return self._user_stats.get(user_id)
    
    def get_bot_stats(self, bot_id: str) -> Optional[Dict]:
        """获取Bot统计"""
        return self._bot_stats.get(bot_id)
    
    def get_model_stats(self, model: Optional[str] = None) -> Dict:
        """获取模型统计"""
        if model:
            return self._model_stats.get(model, {})
        return dict(self._model_stats)
    
    def get_recent_history(self, count: int = 100) -> List[Dict]:
        """获取最近的使用记录"""
        return [stat.to_dict() for stat in self._history[-count:]]
    
    def export_stats(self) -> Dict:
        """导出所有统计数据"""
        return {
            "total": self.get_total_stats(),
            "by_user": dict(self._user_stats),
            "by_bot": dict(self._bot_stats),
            "by_model": dict(self._model_stats),
            "recent_history": self.get_recent_history(100)
        }
