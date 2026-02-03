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
class SkillConfig:
    """Bot技能配置 - 与Agent能力对应"""
    id: str  # 技能ID
    name: str  # 技能显示名称
    description: str = ""  # 技能描述
    agent_name: Optional[str] = None  # 关联的Agent名称
    enabled: bool = True  # 是否启用
    priority: int = 0  # 优先级


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
    # 名字性别语言
    name: str = ""
    gender: str = ""
    language: str = ""
    # 性格特点
    character: str = ""
    traits: List[str] = field(default_factory=list)

    # 外貌特征
    appearance: AppearanceConfig = field(default_factory=AppearanceConfig)

    # 口头禅
    catchphrases: List[str] = field(default_factory=list)

    # 人生规划
    life_goals: List[str] = field(default_factory=list)  # 人生规划

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
class ValueDimensionsConfig:
    """价值观维度配置 - 1-10分的人格维度"""
    rationality: int = 5  # 理性 vs 感性（1=极感性, 10=极理性）
    openness: int = 5  # 保守 vs 开放（1=保守, 10=开放）
    assertiveness: int = 5  # 顺从 vs 坚持（1=顺从, 10=坚持）← 关键参数！
    optimism: int = 5  # 悲观 vs 乐观
    depth_preference: int = 5  # 浅聊 vs 深度


@dataclass
class StanceConfig:
    """预设立场配置"""
    topic: str  # 话题
    position: str  # Bot的观点
    confidence: float = 0.5  # 坚持程度 0-1


@dataclass
class ResponsePreferencesConfig:
    """回应风格偏好"""
    agree_first: bool = True  # 倾向先认同再表达不同
    use_examples: bool = True  # 喜欢用例子说明
    ask_back: bool = True  # 倾向反问用户
    use_humor: bool = False  # 用幽默化解


@dataclass
class ValuesConfig:
    """Bot价值观系统配置"""
    dimensions: ValueDimensionsConfig = field(default_factory=ValueDimensionsConfig)
    stances: List[StanceConfig] = field(default_factory=list)
    response_preferences: ResponsePreferencesConfig = field(default_factory=ResponsePreferencesConfig)
    default_behavior: str = "curious"  # 遇到没有预设立场的话题: curious/neutral/avoid


@dataclass
class VoiceConfig:
    """
    Bot语音配置 - 定义Bot的语音回复设置
    """
    enabled: bool = False  # 是否启用语音回复
    voice_id: str = "xiaoyan"  # 语音音色ID（默认使用Qwen）


@dataclass
class BotConfig:
    """
    从YAML配置文件加载的Bot配置对象
    """

    # 各项配置
    ai: AIConfig = field(default_factory=AIConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    limits: LimitsConfig = field(default_factory=LimitsConfig)
    agents: AgentsConfig = field(default_factory=AgentsConfig)
    messages: MessagesConfig = field(default_factory=MessagesConfig)

    # Bot人格配置 - 定义Bot的独特个性
    personality: PersonalityConfig = field(default_factory=PersonalityConfig)

    # Bot语音配置 - 定义Bot的语音回复设置
    voice: VoiceConfig = field(default_factory=VoiceConfig)

    # Bot价值观系统配置 - 定义Bot的价值观和立场
    values: ValuesConfig = field(default_factory=ValuesConfig)

    # 功能开关
    features_enabled: List[str] = field(default_factory=list)

    # 元数据
    version: str = "1.0.0"
    config_path: Optional[Path] = None


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
            # 基础信息
            name=data.get("name", ""),
            gender=data.get("gender", []),
            language=data.get("language", []),
            # 性格特点
            character=data.get("character", ""),
            traits=data.get("traits", []),
            # 外貌特征
            appearance=self._parse_appearance_config(appearance_data),

            # 口头禅
            catchphrases=data.get("catchphrases", []),

            # 理想
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

    def _parse_voice_config(self, data: Dict) -> VoiceConfig:
        """
        解析语音配置
        
        配置Bot的语音回复设置
        """
        return VoiceConfig(
            enabled=data.get("enabled", False),
            voice_id=data.get("voice_id", "alloy")
        )

    def _parse_values_config(self, data: Dict) -> ValuesConfig:
        """
        解析价值观系统配置
        
        配置Bot的价值观维度、预设立场和回应偏好
        """
        # 解析价值观维度
        dimensions_data = data.get("dimensions", {})
        dimensions = ValueDimensionsConfig(
            rationality=dimensions_data.get("rationality", 5),
            openness=dimensions_data.get("openness", 5),
            assertiveness=dimensions_data.get("assertiveness", 5),
            optimism=dimensions_data.get("optimism", 5),
            depth_preference=dimensions_data.get("depth_preference", 5)
        )

        # 解析预设立场
        stances = []
        for stance_data in data.get("stances", []):
            stances.append(StanceConfig(
                topic=stance_data.get("topic", ""),
                position=stance_data.get("position", ""),
                confidence=stance_data.get("confidence", 0.5)
            ))

        # 解析回应偏好
        preferences_data = data.get("response_preferences", {})
        response_preferences = ResponsePreferencesConfig(
            agree_first=preferences_data.get("agree_first", True),
            use_examples=preferences_data.get("use_examples", True),
            ask_back=preferences_data.get("ask_back", True),
            use_humor=preferences_data.get("use_humor", False)
        )

        return ValuesConfig(
            dimensions=dimensions,
            stances=stances,
            response_preferences=response_preferences,
            default_behavior=data.get("default_behavior", "curious")
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

            config = BotConfig(
                # Bot人格配置 - 包含性格、外貌、口头禅、理想、爱好等
                personality=self._parse_personality_config(data.get("personality", {})),
                # AI模型配置
                ai=self._parse_ai_config(data.get("ai", {})),
                # Bot语音配置 - 语音回复设置
                voice=self._parse_voice_config(data.get("voice", {})),
                # 功能配置
                features_enabled=data.get("features", {}).get("enabled", []),
                # 路由配置
                routing=self._parse_routing_config(data.get("routing", {})),
                # 限制配置
                limits=self._parse_limits_config(data.get("limits", {})),
                # 元数据
                version=data.get("metadata", {}).get("version", "1.0.0"),
                # Bot价值观系统配置 - 价值观和立场
                values=self._parse_values_config(data.get("values", {})),

                config_path=config_path,
                messages=self._parse_messages_config(data.get("messages", {})),
                agents=self._parse_agents_config(data.get("agents", {}))
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
