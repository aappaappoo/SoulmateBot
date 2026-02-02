"""
Configuration settings for SoulmateBot
"""
from pydantic_settings import BaseSettings
from typing import List, Optional
from enum import Enum


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    # Telegram Configuration
    telegram_bot_token: Optional[str] = None
    telegram_webhook_url: Optional[str] = None

    # AI Provider Configuration
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4"
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-sonnet-20240229"
    vllm_api_url: Optional[str] = None
    vllm_api_token: Optional[str] = None
    vllm_model: str = "default"

    # Database Configuration
    database_url: str = "sqlite:///./soulmatebot.db"
    redis_url: Optional[str] = None

    # Application Configuration
    app_env: Environment = Environment.DEVELOPMENT
    debug: bool = True
    log_level: str = "INFO"
    sql_echo: bool = False  # Enable to show SQLAlchemy SQL statements in logs

    # Subscription Configuration
    stripe_api_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None

    # WeChat Pay Configuration
    wechat_pay_app_id: Optional[str] = None
    wechat_pay_mch_id: Optional[str] = None
    wechat_pay_api_key: Optional[str] = None
    wechat_pay_api_v3_key: Optional[str] = None
    wechat_pay_cert_serial_no: Optional[str] = None
    wechat_pay_private_key_path: Optional[str] = None
    wechat_pay_notify_url: Optional[str] = None

    # Subscription Limits
    free_plan_daily_limit: int = 100
    basic_plan_daily_limit: int = 100
    premium_plan_daily_limit: int = 1000

    # Security
    secret_key: str = "change-me-in-production"
    admin_user_ids: List[int] = []

    # Rate Limiting
    rate_limit_messages_per_minute: int = 10
    rate_limit_images_per_hour: int = 5

    # Voice/TTS Configuration
    openai_tts_model: str = "tts-1"  # OpenAI TTS模型：tts-1 或 tts-1-hd
    default_voice_id: str = "alloy"  # 默认语音音色：alloy, echo, fable, onyx, nova, shimmer

    # iFlytek (科大讯飞) TTS Configuration
    iflytek_app_id: Optional[str] = None  # 讯飞应用ID
    iflytek_api_key: Optional[str] = None  # 讯飞API Key
    iflytek_api_secret: Optional[str] = None  # 讯飞API Secret
    default_iflytek_voice_id: str = "xiaoyan"  # 默认讯飞语音音色

    # Qwen (通义千问) TTS Configuration - 阿里云 DashScope
    dashscope_api_key: Optional[str] = None  # DashScope API Key
    dashscope_api_url: str = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"  # DashScope WebSocket URL
    qwen_tts_model: str = "qwen3-tts-flash-realtime"  # Qwen TTS 模型
    default_qwen_voice_id: str = "Cherry"  # 默认 Qwen 语音音色: Cherry, Serena, Ethan, etc.
    tts_provider: str = "qwen"  # TTS服务提供商：openai, iflytek 或 qwen

    # Embedding Configuration (向量嵌入配置)
    embedding_provider: str = "dashscope"  # 嵌入服务提供商：dashscope 或 openai
    embedding_model: str = "text-embedding-v3"  # 嵌入模型名称
    memory_similarity_threshold: float = 0.5  # 记忆检索的最低相似度阈值

    # Search Agent / SERP API Configuration (搜索代理配置)
    serp_api_keys: str = ""  # 多个 SERP API keys，逗号分隔
    serp_cache_ttl: int = 3600  # 搜索缓存过期时间（秒），默认1小时
    serp_top_k: int = 5  # 返回搜索结果数量
    serp_api_provider: str = "serpapi"  # 搜索API提供商：serpapi, google, bing

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
