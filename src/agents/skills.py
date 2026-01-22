"""
Skills System for Token-Efficient Selection

技能系统 - 提供Telegram按钮界面，让用户选择需要的服务，
减少LLM token消耗。

主要功能：
1. 定义可选技能/能力
2. 生成Telegram InlineKeyboard按钮
3. 处理用户选择回调
4. 与Agent系统集成
"""
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class SkillCategory(str, Enum):
    """技能分类"""
    EMOTIONAL = "emotional"  # 情感支持
    TECH = "tech"  # 技术帮助
    TOOLS = "tools"  # 实用工具
    ANALYSIS = "analysis"  # 分析任务
    CREATIVE = "creative"  # 创意任务
    OTHER = "other"  # 其他


@dataclass
class Skill:
    """
    技能定义
    
    Attributes:
        id: 技能唯一标识
        name: 显示名称
        description: 技能描述
        category: 技能分类
        icon: 显示图标（emoji）
        agent_name: 关联的Agent名称
        keywords: 触发关键词
        is_active: 是否激活
    """
    id: str
    name: str
    description: str
    category: SkillCategory = SkillCategory.OTHER
    icon: str = "🔧"
    agent_name: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    is_active: bool = True
    priority: int = 0  # 显示优先级，数字越大越靠前
    
    def to_button_data(self) -> Dict[str, str]:
        """转换为Telegram按钮数据"""
        return {
            "text": f"{self.icon} {self.name}",
            "callback_data": f"skill:{self.id}"
        }


class SkillRegistry:
    """
    技能注册表
    
    管理所有可用技能，提供注册、查询、生成按钮等功能。
    """
    
    def __init__(self):
        """初始化技能注册表"""
        self._skills: Dict[str, Skill] = {}
        self._category_skills: Dict[SkillCategory, List[str]] = {}
        
        # 注册默认技能
        self._register_default_skills()
    
    def _register_default_skills(self):
        """注册默认技能"""
        default_skills = [
            Skill(
                id="emotional_support",
                name="情感支持",
                description="倾听你的心声，提供情感陪伴和支持",
                category=SkillCategory.EMOTIONAL,
                icon="💝",
                agent_name="EmotionalAgent",
                keywords=["难过", "开心", "焦虑", "压力", "心情", "feel", "sad", "happy"],
                priority=10
            ),
            Skill(
                id="tech_help",
                name="技术帮助",
                description="编程问题解答、代码调试、技术指导",
                category=SkillCategory.TECH,
                icon="💻",
                agent_name="TechAgent",
                keywords=["代码", "编程", "bug", "错误", "code", "python", "javascript"],
                priority=9
            ),
            Skill(
                id="tool_query",
                name="实用工具",
                description="天气查询、时间查询、计算等实用功能",
                category=SkillCategory.TOOLS,
                icon="🔧",
                agent_name="ToolAgent",
                keywords=["天气", "时间", "计算", "翻译", "weather", "time"],
                priority=8
            ),
            Skill(
                id="group_monitor",
                name="群组监控",
                description="监控群组讨论，总结话题",
                category=SkillCategory.ANALYSIS,
                icon="📊",
                agent_name="GroupMonitorAgent",
                keywords=["监控", "群组", "总结", "讨论", "monitor", "group", "summary"],
                priority=7
            ),
            Skill(
                id="general_chat",
                name="日常聊天",
                description="日常对话，闲聊陪伴",
                category=SkillCategory.OTHER,
                icon="💬",
                agent_name=None,  # 不关联特定Agent，使用默认LLM
                keywords=[],
                priority=1
            ),
        ]
        
        for skill in default_skills:
            self.register(skill)
    
    def register(self, skill: Skill) -> None:
        """
        注册技能
        
        Args:
            skill: 技能实例
        """
        self._skills[skill.id] = skill
        
        # 更新分类索引
        if skill.category not in self._category_skills:
            self._category_skills[skill.category] = []
        if skill.id not in self._category_skills[skill.category]:
            self._category_skills[skill.category].append(skill.id)
        
        logger.info(f"注册技能: {skill.id} ({skill.name})")
    
    def unregister(self, skill_id: str) -> bool:
        """
        注销技能
        
        Args:
            skill_id: 技能ID
            
        Returns:
            bool: 是否成功注销
        """
        if skill_id in self._skills:
            skill = self._skills[skill_id]
            del self._skills[skill_id]
            
            # 更新分类索引
            if skill.category in self._category_skills:
                if skill_id in self._category_skills[skill.category]:
                    self._category_skills[skill.category].remove(skill_id)
            
            logger.info(f"注销技能: {skill_id}")
            return True
        return False
    
    def get(self, skill_id: str) -> Optional[Skill]:
        """获取技能"""
        return self._skills.get(skill_id)
    
    def get_by_agent(self, agent_name: str) -> Optional[Skill]:
        """根据Agent名称获取技能"""
        for skill in self._skills.values():
            if skill.agent_name == agent_name:
                return skill
        return None
    
    def get_all(self, active_only: bool = True) -> List[Skill]:
        """获取所有技能"""
        skills = list(self._skills.values())
        if active_only:
            skills = [s for s in skills if s.is_active]
        return sorted(skills, key=lambda s: -s.priority)
    
    def get_by_category(self, category: SkillCategory, active_only: bool = True) -> List[Skill]:
        """获取指定分类的技能"""
        skill_ids = self._category_skills.get(category, [])
        skills = [self._skills[sid] for sid in skill_ids if sid in self._skills]
        if active_only:
            skills = [s for s in skills if s.is_active]
        return sorted(skills, key=lambda s: -s.priority)
    
    def match_skills(self, text: str, top_n: int = 3) -> List[Skill]:
        """
        根据文本内容匹配技能
        
        Args:
            text: 用户输入文本
            top_n: 返回前N个匹配的技能
            
        Returns:
            List[Skill]: 匹配的技能列表
        """
        text_lower = text.lower()
        matches = []
        
        for skill in self._skills.values():
            if not skill.is_active:
                continue
            
            score = 0
            for keyword in skill.keywords:
                if keyword.lower() in text_lower:
                    score += 1
            
            if score > 0:
                matches.append((skill, score))
        
        # 按匹配分数排序
        matches.sort(key=lambda x: (-x[1], -x[0].priority))
        
        return [m[0] for m in matches[:top_n]]


class SkillButtonGenerator:
    """
    Telegram按钮生成器
    
    为技能系统生成InlineKeyboard按钮。
    """
    
    def __init__(self, registry: SkillRegistry):
        """
        初始化按钮生成器
        
        Args:
            registry: 技能注册表
        """
        self.registry = registry
    
    def generate_main_menu(self, columns: int = 2) -> List[List[Dict[str, str]]]:
        """
        生成主菜单按钮
        
        Args:
            columns: 每行按钮数量
            
        Returns:
            List[List[Dict]]: 按钮行列表，适配InlineKeyboardMarkup
        """
        skills = self.registry.get_all(active_only=True)
        buttons = []
        row = []
        
        for i, skill in enumerate(skills):
            row.append(skill.to_button_data())
            
            if len(row) >= columns:
                buttons.append(row)
                row = []
        
        if row:
            buttons.append(row)
        
        return buttons
    
    def generate_category_menu(self, category: SkillCategory, columns: int = 2) -> List[List[Dict[str, str]]]:
        """
        生成分类菜单按钮
        
        Args:
            category: 技能分类
            columns: 每行按钮数量
            
        Returns:
            List[List[Dict]]: 按钮行列表
        """
        skills = self.registry.get_by_category(category, active_only=True)
        buttons = []
        row = []
        
        for skill in skills:
            row.append(skill.to_button_data())
            
            if len(row) >= columns:
                buttons.append(row)
                row = []
        
        if row:
            buttons.append(row)
        
        # 添加返回按钮
        buttons.append([{"text": "⬅️ 返回", "callback_data": "skill:back_to_main"}])
        
        return buttons
    
    def generate_matched_skills(
        self,
        text: str,
        include_cancel: bool = True,
        columns: int = 2
    ) -> List[List[Dict[str, str]]]:
        """
        根据用户输入生成匹配的技能按钮
        
        Args:
            text: 用户输入文本
            include_cancel: 是否包含取消按钮
            columns: 每行按钮数量
            
        Returns:
            List[List[Dict]]: 按钮行列表
        """
        matched = self.registry.match_skills(text, top_n=5)
        
        if not matched:
            # 如果没有匹配，返回默认技能
            matched = self.registry.get_all(active_only=True)[:3]
        
        buttons = []
        row = []
        
        for skill in matched:
            row.append(skill.to_button_data())
            
            if len(row) >= columns:
                buttons.append(row)
                row = []
        
        if row:
            buttons.append(row)
        
        if include_cancel:
            buttons.append([{"text": "❌ 取消", "callback_data": "skill:cancel"}])
        
        return buttons


# 全局技能注册表实例
skill_registry = SkillRegistry()

# 全局按钮生成器实例
skill_button_generator = SkillButtonGenerator(skill_registry)


def register_skill(
    id: str,
    name: str,
    description: str,
    category: SkillCategory = SkillCategory.OTHER,
    icon: str = "🔧",
    agent_name: Optional[str] = None,
    keywords: List[str] = None,
    priority: int = 0
) -> Skill:
    """
    便捷函数：注册新技能
    
    Args:
        id: 技能ID
        name: 显示名称
        description: 技能描述
        category: 技能分类
        icon: 显示图标
        agent_name: 关联的Agent名称
        keywords: 触发关键词
        priority: 显示优先级
        
    Returns:
        Skill: 注册的技能实例
    """
    skill = Skill(
        id=id,
        name=name,
        description=description,
        category=category,
        icon=icon,
        agent_name=agent_name,
        keywords=keywords or [],
        priority=priority
    )
    skill_registry.register(skill)
    return skill
