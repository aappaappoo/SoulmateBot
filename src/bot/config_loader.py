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
class AppearanceConfig:
    """外貌特征配置"""
    avatar: Optional[str] = None  # 头像描述或URL
    physical_description: str = ""  # 外貌描述
    style: str = ""  # 穿着风格
    distinctive_features: List[str] = field(default_factory=list)  # 独特特征


@dataclass
class PersonalityConfig:
    """
    Bot人格配置 - 定义Bot的独特个性
    
    包含性格、外貌、口头禅、理想、爱好等个人特征
    """
    # 性格特点
    character: str = ""  # 基础人设描述
    traits: List[str] = field(default_factory=list)  # 性格特点列表
    
    # 外貌特征
    appearance: AppearanceConfig = field(default_factory=AppearanceConfig)

    # 口头禅
    catchphrases: List[str] = field(default_factory=list)
    
    # 理想和人生规划
    ideals: str = ""  # 理想
    life_goals: List[str] = field(default_factory=list)  # 人生规划/目标
    
    # 爱好和讨厌点
    likes: List[str] = field(default_factory=list)  # 喜欢的事物
    dislikes: List[str] = field(default_factory=list)  # 讨厌的事物
    
    # 居住环境
    living_environment: str = ""  # 居住环境描述
    
    # 语言风格
    speaking_style: Dict[str, Any] = field(default_factory=dict)
    
    # 交互偏好
    interaction_style: Dict[str, Any] = field(default_factory=dict)
    
    # 情绪应对策略
    emotional_response: Dict[str, Any] = field(default_factory=dict)
    
    # 安全策略
    safety_policy: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillConfig:
    """Bot技能配置 - 与Agent能力对应"""
    id: str  # 技能ID
    name: str  # 技能显示名称
    description: str = ""  # 技能描述
    agent_name: Optional[str] = None  # 关联的Agent名称
    enabled: bool = True  # 是否启用
    priority: int = 0  # 优先级


@dataclass
class SkillsConfig:
    """Bot技能总配置"""
    enabled: List[SkillConfig] = field(default_factory=list)
    default_skill: Optional[str] = None  # 默认技能ID


@dataclass
class VoiceConfig:
    """
    Bot语音配置 - 定义Bot的语音回复设置
    
    启用后，Bot将使用TTS将文本回复转换为语音发送
    
    可用音色 (voice_id):
    - alloy: 中性，平衡的声音
    - echo: 柔和，有质感的声音  
    - fable: 英式口音，叙事风格
    - onyx: 深沉，有力的声音
    - nova: 年轻，活泼的声音
    - shimmer: 温暖，表达力强的声音
    """
    enabled: bool = False  # 是否启用语音回复
    voice_id: str = "alloy"  # 语音音色ID


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
    
    # Bot人格配置 - 定义Bot的独特个性
    personality: PersonalityConfig = field(default_factory=PersonalityConfig)
    
    # Bot技能配置 - 与Agent能力对应
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    
    # Bot语音配置 - 定义Bot的语音回复设置
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    
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
    
    def _parse_appearance_config(self, data: Dict) -> AppearanceConfig:
        """解析外貌特征配置"""
        return AppearanceConfig(
            avatar=data.get("avatar"),
            physical_description=data.get("physical_description", ""),
            style=data.get("style", ""),
            distinctive_features=data.get("distinctive_features", [])
        )
    
    def _parse_personality_config(self, data: Dict) -> PersonalityConfig:
        """
        解析人格配置
        
        包含性格、外貌、口头禅、理想、爱好等个人特征
        """
        appearance_data = data.get("appearance", {})
        
        return PersonalityConfig(
            # 性格特点
            character=data.get("character", ""),
            traits=data.get("traits", []),
            
            # 外貌特征
            appearance=self._parse_appearance_config(appearance_data),
            
            # 口头禅
            catchphrases=data.get("catchphrases", []),
            
            # 理想和人生规划
            ideals=data.get("ideals", ""),
            life_goals=data.get("life_goals", []),
            
            # 爱好和讨厌点
            likes=data.get("likes", []),
            dislikes=data.get("dislikes", []),
            
            # 居住环境
            living_environment=data.get("living_environment", ""),
            
            # 语言风格
            speaking_style=data.get("speaking_style", {}),
            
            # 交互偏好
            interaction_style=data.get("interaction_style", {}),
            
            # 情绪应对策略
            emotional_response=data.get("emotional_response", {}),
            
            # 安全策略
            safety_policy=data.get("safety_policy", {})
        )
    
    def _parse_skills_config(self, data: Dict) -> SkillsConfig:
        """
        解析技能配置
        
        技能与Agent能力对应，定义Bot可使用的能力
        """
        enabled = []
        for skill_data in data.get("enabled", []):
            enabled.append(SkillConfig(
                id=skill_data.get("id", ""),
                name=skill_data.get("name", ""),
                description=skill_data.get("description", ""),
                agent_name=skill_data.get("agent_name"),
                enabled=skill_data.get("enabled", True),
                priority=skill_data.get("priority", 0)
            ))
        
        return SkillsConfig(
            enabled=enabled,
            default_skill=data.get("default_skill")
        )
    
    def _parse_voice_config(self, data: Dict) -> VoiceConfig:
        """
        解析语音配置
        
        配置Bot的语音回复设置
        """
        return VoiceConfig(
            enabled=data.get("enabled", False),
            voice_id=data.get("voice_id", "alloy")
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
                
                # Bot人格配置 - 包含性格、外貌、口头禅、理想、爱好等
                personality=self._parse_personality_config(data.get("personality", {})),
                
                # Bot技能配置 - 与Agent能力对应
                skills=self._parse_skills_config(data.get("skills", {})),
                
                # Bot语音配置 - 语音回复设置
                voice=self._parse_voice_config(data.get("voice", {})),
                
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
