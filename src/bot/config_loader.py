"""
Bot Configuration Loader - Bot配置加载器

加载和解析Bot的YAML配置文件
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import yaml
from loguru import logger


@dataclass
class AIConfig:
    """AI模型配置"""
    provider: str = "openai"
    model: str = "gpt-4"
    temperature: float = 0.8
    max_tokens: int = 1000
    context_window: int = 4096


@dataclass
class PromptConfig:
    """提示词配置"""
    template: Optional[str] = None
    custom: Optional[str] = None
    variables: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingConfig:
    """消息路由配置"""
    mode: str = "auto"  # mention, auto, keyword
    private_chat_auto_reply: bool = True
    group_chat_mention_required: bool = True


@dataclass
class LimitConfig:
    """限额配置"""
    messages: int = 10
    images: int = 0


@dataclass
class LimitsConfig:
    """各等级限额配置"""
    free_tier: LimitConfig = field(default_factory=lambda: LimitConfig(10, 0))
    basic_tier: LimitConfig = field(default_factory=lambda: LimitConfig(100, 5))
    premium_tier: LimitConfig = field(default_factory=lambda: LimitConfig(1000, 50))


@dataclass
class AgentConfig:
    """Agent配置"""
    name: str
    priority: int = 50
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentsConfig:
    """Agents总配置"""
    enabled: List[AgentConfig] = field(default_factory=list)
    fallback: Optional[str] = None


@dataclass
class MessagesConfig:
    """消息模板配置"""
    welcome: str = "欢迎使用！"
    help: str = "使用帮助"
    limit_reached: str = "今日额度已用完"


@dataclass
class BotConfig:
    """
    Bot完整配置
    
    从YAML配置文件加载的Bot配置对象
    """
    # 基础信息
    name: str
    description: str = ""
    username: str = ""
    bot_type: str = "assistant"
    language: str = "zh"
    is_public: bool = True
    
    # 各项配置
    ai: AIConfig = field(default_factory=AIConfig)
    prompt: PromptConfig = field(default_factory=PromptConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    limits: LimitsConfig = field(default_factory=LimitsConfig)
    agents: AgentsConfig = field(default_factory=AgentsConfig)
    messages: MessagesConfig = field(default_factory=MessagesConfig)
    
    # 功能开关
    features_enabled: List[str] = field(default_factory=list)
    features_disabled: List[str] = field(default_factory=list)
    
    # 元数据
    version: str = "1.0.0"
    config_path: Optional[Path] = None
    
    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        if self.prompt.custom:
            return self.prompt.custom
        
        # 使用模板
        if self.prompt.template:
            from src.conversation.prompt_template import get_template_manager
            manager = get_template_manager()
            result = manager.render_template(
                self.prompt.template,
                bot_name=self.name,
                **self.prompt.variables
            )
            if result:
                return result
        
        # 默认提示词
        return f"你是一个名叫{self.name}的智能助手。{self.description}"
    
    def is_feature_enabled(self, feature: str) -> bool:
        """检查功能是否启用"""
        if feature in self.features_disabled:
            return False
        if self.features_enabled and feature not in self.features_enabled:
            return False
        return True
    
    def get_limit(self, tier: str, limit_type: str = "messages") -> int:
        """获取指定等级的限额"""
        tier_config = getattr(self.limits, f"{tier}_tier", self.limits.free_tier)
        return getattr(tier_config, limit_type, 0)


class BotConfigLoader:
    """
    Bot配置加载器
    
    从YAML文件加载Bot配置
    """
    
    def __init__(self, bots_dir: str = "bots"):
        """
        初始化加载器
        
        Args:
            bots_dir: Bots目录路径
        """
        self.bots_dir = Path(bots_dir)
        self._configs: Dict[str, BotConfig] = {}
        
        logger.info(f"BotConfigLoader initialized with bots_dir: {self.bots_dir}")
    
    def _parse_ai_config(self, data: Dict) -> AIConfig:
        """解析AI配置"""
        return AIConfig(
            provider=data.get("provider", "openai"),
            model=data.get("model", "gpt-4"),
            temperature=data.get("temperature", 0.8),
            max_tokens=data.get("max_tokens", 1000),
            context_window=data.get("context_window", 4096)
        )
    
    def _parse_prompt_config(self, data: Dict) -> PromptConfig:
        """解析提示词配置"""
        return PromptConfig(
            template=data.get("template"),
            custom=data.get("custom"),
            variables=data.get("variables", {})
        )
    
    def _parse_routing_config(self, data: Dict) -> RoutingConfig:
        """解析路由配置"""
        return RoutingConfig(
            mode=data.get("mode", "auto"),
            private_chat_auto_reply=data.get("private_chat_auto_reply", True),
            group_chat_mention_required=data.get("group_chat_mention_required", True)
        )
    
    def _parse_limits_config(self, data: Dict) -> LimitsConfig:
        """解析限额配置"""
        free = data.get("free_tier", {})
        basic = data.get("basic_tier", {})
        premium = data.get("premium_tier", {})
        
        return LimitsConfig(
            free_tier=LimitConfig(free.get("messages", 10), free.get("images", 0)),
            basic_tier=LimitConfig(basic.get("messages", 100), basic.get("images", 5)),
            premium_tier=LimitConfig(premium.get("messages", 1000), premium.get("images", 50))
        )
    
    def _parse_agents_config(self, data: Dict) -> AgentsConfig:
        """解析Agents配置"""
        enabled = []
        for agent_data in data.get("enabled", []):
            enabled.append(AgentConfig(
                name=agent_data.get("name", ""),
                priority=agent_data.get("priority", 50),
                config=agent_data.get("config", {})
            ))
        
        return AgentsConfig(
            enabled=enabled,
            fallback=data.get("fallback")
        )
    
    def _parse_messages_config(self, data: Dict) -> MessagesConfig:
        """解析消息模板配置"""
        return MessagesConfig(
            welcome=data.get("welcome", "欢迎使用！"),
            help=data.get("help", "使用帮助"),
            limit_reached=data.get("limit_reached", "今日额度已用完")
        )
    
    def load_config(self, bot_id: str) -> Optional[BotConfig]:
        """
        加载指定Bot的配置
        
        Args:
            bot_id: Bot标识（目录名）
            
        Returns:
            BotConfig对象或None
        """
        config_path = self.bots_dir / bot_id / "config.yaml"
        
        if not config_path.exists():
            logger.warning(f"Config file not found: {config_path}")
            return None
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            bot_data = data.get("bot", {})
            
            config = BotConfig(
                name=bot_data.get("name", bot_id),
                description=bot_data.get("description", ""),
                username=bot_data.get("username", ""),
                bot_type=bot_data.get("type", "assistant"),
                language=bot_data.get("language", "zh"),
                is_public=bot_data.get("is_public", True),
                
                ai=self._parse_ai_config(data.get("ai", {})),
                prompt=self._parse_prompt_config(data.get("prompt", {})),
                routing=self._parse_routing_config(data.get("routing", {})),
                limits=self._parse_limits_config(data.get("limits", {})),
                agents=self._parse_agents_config(data.get("agents", {})),
                messages=self._parse_messages_config(data.get("messages", {})),
                
                features_enabled=data.get("features", {}).get("enabled", []),
                features_disabled=data.get("features", {}).get("disabled", []),
                
                version=data.get("metadata", {}).get("version", "1.0.0"),
                config_path=config_path
            )
            
            self._configs[bot_id] = config
            logger.info(f"Loaded config for bot: {bot_id}")
            
            return config
            
        except Exception as e:
            logger.error(f"Error loading config for bot {bot_id}: {e}")
            return None
    
    def load_all_configs(self) -> Dict[str, BotConfig]:
        """
        加载所有Bot的配置
        
        Returns:
            bot_id -> BotConfig 的字典
        """
        if not self.bots_dir.exists():
            logger.warning(f"Bots directory not found: {self.bots_dir}")
            return {}
        
        configs = {}
        
        for bot_dir in self.bots_dir.iterdir():
            if bot_dir.is_dir() and not bot_dir.name.startswith('_'):
                config = self.load_config(bot_dir.name)
                if config:
                    configs[bot_dir.name] = config
        
        logger.info(f"Loaded {len(configs)} bot configurations")
        return configs
    
    def get_config(self, bot_id: str) -> Optional[BotConfig]:
        """获取已加载的配置"""
        if bot_id not in self._configs:
            self.load_config(bot_id)
        return self._configs.get(bot_id)
    
    def reload_config(self, bot_id: str) -> Optional[BotConfig]:
        """重新加载配置"""
        if bot_id in self._configs:
            del self._configs[bot_id]
        return self.load_config(bot_id)
    
    def list_bots(self) -> List[str]:
        """列出所有可用的Bot"""
        if not self.bots_dir.exists():
            return []
        
        bots = []
        for bot_dir in self.bots_dir.iterdir():
            if bot_dir.is_dir() and not bot_dir.name.startswith('_'):
                if (bot_dir / "config.yaml").exists():
                    bots.append(bot_dir.name)
        
        return bots


# 全局配置加载器实例
_config_loader: Optional[BotConfigLoader] = None


def get_config_loader() -> BotConfigLoader:
    """获取全局配置加载器"""
    global _config_loader
    if _config_loader is None:
        _config_loader = BotConfigLoader()
    return _config_loader
