"""
Prompt Template Manager - 提示词模板管理

提供：
- 预定义的提示词模板
- 模板变量替换
- 多语言支持
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from loguru import logger


@dataclass
class PromptTemplate:
    """
    提示词模板
    
    Attributes:
        name: 模板名称
        content: 模板内容（支持变量占位符 {{variable}}）
        description: 模板描述
        variables: 模板变量列表
        language: 语言代码
        category: 模板分类
        metadata: 额外元数据
    """
    name: str
    content: str
    description: str = ""
    variables: List[str] = field(default_factory=list)
    language: str = "zh"
    category: str = "general"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def __post_init__(self):
        """自动提取模板变量"""
        if not self.variables:
            self.variables = self._extract_variables()
    
    def _extract_variables(self) -> List[str]:
        """从模板内容中提取变量"""
        pattern = r'\{\{(\w+)\}\}'
        return list(set(re.findall(pattern, self.content)))
    
    def render(self, **kwargs) -> str:
        """
        渲染模板
        
        Args:
            **kwargs: 变量值
            
        Returns:
            渲染后的内容
        """
        content = self.content
        for var in self.variables:
            placeholder = f"{{{{{var}}}}}"
            value = kwargs.get(var, "")
            content = content.replace(placeholder, str(value))
        return content
    
    def validate_variables(self, **kwargs) -> List[str]:
        """
        验证是否提供了所有必需的变量
        
        Returns:
            缺失的变量列表
        """
        return [var for var in self.variables if var not in kwargs]
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "name": self.name,
            "content": self.content,
            "description": self.description,
            "variables": self.variables,
            "language": self.language,
            "category": self.category,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


# 预定义的系统提示词模板
DEFAULT_TEMPLATES = {
    # 情感陪伴Bot
    "emotional_companion": PromptTemplate(
        name="emotional_companion",
        content="""你是一个温柔、善解人意的情感陪伴助手。

角色设定：
- 名字：{{bot_name}}
- 性格：温暖、耐心、富有同理心
- 目标：倾听用户的心声，提供情感支持和陪伴

沟通原则：
1. 始终使用温暖、关怀的语气
2. 认真倾听并理解用户的情绪
3. 不评判，只给予支持和鼓励
4. 适时提供实用的情绪调节建议
5. 保持适当的边界感

用户信息：
- 用户名：{{user_name}}
- 历史互动次数：{{interaction_count}}

请用温暖、关怀的语气回复用户，让他们感受到被理解和支持。""",
        description="情感陪伴机器人的系统提示词",
        category="companion",
        language="zh"
    ),
    
    # 技术助手Bot
    "tech_assistant": PromptTemplate(
        name="tech_assistant",
        content="""你是一个专业的技术支持助手。

角色设定：
- 名字：{{bot_name}}
- 专长：{{specialties}}
- 风格：专业、简洁、高效

工作原则：
1. 提供准确、实用的技术解答
2. 使用清晰的代码示例说明
3. 分步骤解释复杂概念
4. 主动推荐最佳实践
5. 必要时询问更多上下文

请专业地回答用户的技术问题。""",
        description="技术助手机器人的系统提示词",
        category="assistant",
        language="zh"
    ),
    
    # 客服Bot
    "customer_service": PromptTemplate(
        name="customer_service",
        content="""你是{{company_name}}的智能客服助手。

角色设定：
- 名字：{{bot_name}}
- 职责：解答用户问题、处理咨询请求

服务原则：
1. 礼貌、专业地对待每位用户
2. 快速理解用户需求
3. 提供准确的产品/服务信息
4. 无法解决时，引导用户联系人工客服
5. 保护用户隐私，不索要敏感信息

常见问题类型：
- 产品咨询
- 订单查询
- 售后服务
- 投诉建议

请专业地为用户提供帮助。""",
        description="客服机器人的系统提示词",
        category="service",
        language="zh"
    ),
    
    # 通用助手
    "general_assistant": PromptTemplate(
        name="general_assistant",
        content="""你是一个智能助手，名叫{{bot_name}}。

你的任务是帮助用户完成各种任务，回答问题，提供信息和建议。

请根据用户的需求，提供专业、有帮助的回复。""",
        description="通用助手的系统提示词",
        category="general",
        language="zh"
    ),
    
    # 英文版情感陪伴
    "emotional_companion_en": PromptTemplate(
        name="emotional_companion_en",
        content="""You are a warm and empathetic emotional support companion.

Character:
- Name: {{bot_name}}
- Personality: Warm, patient, empathetic
- Goal: Listen to users and provide emotional support

Guidelines:
1. Always use a warm, caring tone
2. Listen and understand the user's emotions
3. Be non-judgmental, offer support and encouragement
4. Provide practical emotional regulation tips when appropriate
5. Maintain appropriate boundaries

User Info:
- Username: {{user_name}}
- Interaction count: {{interaction_count}}

Please respond warmly and make the user feel understood and supported.""",
        description="Emotional companion bot system prompt (English)",
        category="companion",
        language="en"
    )
}


class PromptTemplateManager:
    """
    提示词模板管理器
    
    管理和渲染提示词模板
    """
    
    def __init__(self, load_defaults: bool = True):
        """
        初始化模板管理器
        
        Args:
            load_defaults: 是否加载默认模板
        """
        self._templates: Dict[str, PromptTemplate] = {}
        
        if load_defaults:
            self._load_default_templates()
        
        logger.info(f"PromptTemplateManager initialized with {len(self._templates)} templates")
    
    def _load_default_templates(self) -> None:
        """加载默认模板"""
        for name, template in DEFAULT_TEMPLATES.items():
            self._templates[name] = template
    
    def register_template(self, template: PromptTemplate) -> None:
        """
        注册模板
        
        Args:
            template: 模板对象
        """
        self._templates[template.name] = template
        logger.info(f"Registered template: {template.name}")
    
    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """
        获取模板
        
        Args:
            name: 模板名称
            
        Returns:
            模板对象或None
        """
        return self._templates.get(name)
    
    def render_template(self, name: str, **kwargs) -> Optional[str]:
        """
        渲染模板
        
        Args:
            name: 模板名称
            **kwargs: 变量值
            
        Returns:
            渲染后的内容或None
        """
        template = self.get_template(name)
        if not template:
            logger.warning(f"Template not found: {name}")
            return None
        
        missing = template.validate_variables(**kwargs)
        if missing:
            logger.warning(f"Missing variables for template {name}: {missing}")
        
        return template.render(**kwargs)
    
    def list_templates(self, category: Optional[str] = None, language: Optional[str] = None) -> List[PromptTemplate]:
        """
        列出模板
        
        Args:
            category: 按分类过滤
            language: 按语言过滤
            
        Returns:
            模板列表
        """
        templates = list(self._templates.values())
        
        if category:
            templates = [t for t in templates if t.category == category]
        
        if language:
            templates = [t for t in templates if t.language == language]
        
        return templates
    
    def delete_template(self, name: str) -> bool:
        """删除模板"""
        if name in self._templates:
            del self._templates[name]
            logger.info(f"Deleted template: {name}")
            return True
        return False
    
    def create_system_prompt(
        self,
        template_name: str,
        bot_name: str = "助手",
        user_name: str = "用户",
        **extra_vars
    ) -> str:
        """
        创建系统提示词
        
        便捷方法，用于从模板生成系统提示词
        
        Args:
            template_name: 模板名称
            bot_name: Bot名称
            user_name: 用户名称
            **extra_vars: 额外变量
            
        Returns:
            生成的系统提示词
        """
        vars = {
            "bot_name": bot_name,
            "user_name": user_name,
            "interaction_count": 0,
            **extra_vars
        }
        
        result = self.render_template(template_name, **vars)
        
        if result is None:
            # 使用通用模板
            result = self.render_template("general_assistant", **vars)
        
        return result or f"你是一个名叫{bot_name}的智能助手。"


# 全局模板管理器实例
_template_manager: Optional[PromptTemplateManager] = None


def get_template_manager() -> PromptTemplateManager:
    """获取全局模板管理器"""
    global _template_manager
    if _template_manager is None:
        _template_manager = PromptTemplateManager()
    return _template_manager
