#!/usr/bin/env python3
"""
Bot Template Generator - 机器人模板生成器
==========================================

用于快速创建新的机器人配置目录和文件。

使用方法:
  python scripts/bot_template.py                    # 交互式创建
  python scripts/bot_template.py new <bot_name>     # 快速创建
  python scripts/bot_template.py list               # 列出所有模板
  python scripts/bot_template.py preview <template> # 预览模板

示例:
  python scripts/bot_template.py new research_bot --type expert --desc "研究助手"
  python scripts/bot_template.py new comic_bot --type expert --desc "漫画生成助手"
"""

import sys
import os
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Bot类型模板
BOT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "companion": {
        "description": "情感陪伴类机器人",
        "traits": ["温柔耐心", "高度共情", "稳定可靠", "真诚自然"],
        "features": ["emotional_support", "daily_companion", "mood_tracking", "conversation_memory"],
        "temperature": 0.8,
        "agent": "EmotionalAgent",
    },
    "assistant": {
        "description": "通用助手类机器人",
        "traits": ["高效专业", "逻辑清晰", "知识渊博", "有耐心"],
        "features": ["general_qa", "task_assistance", "information_lookup", "conversation_memory"],
        "temperature": 0.7,
        "agent": "TechAgent",
    },
    "expert": {
        "description": "领域专家类机器人",
        "traits": ["专业严谨", "深度分析", "细致入微", "权威可信"],
        "features": ["domain_expertise", "detailed_analysis", "professional_advice", "conversation_memory"],
        "temperature": 0.6,
        "agent": "TechAgent",
    },
    "creative": {
        "description": "创意类机器人",
        "traits": ["想象力丰富", "幽默风趣", "感性细腻", "灵感充沛"],
        "features": ["creative_writing", "brainstorming", "content_creation", "conversation_memory"],
        "temperature": 0.9,
        "agent": "EmotionalAgent",
    },
    "research": {
        "description": "研究助手类机器人",
        "traits": ["严谨求实", "善于分析", "知识渊博", "逻辑清晰"],
        "features": ["paper_analysis", "research_summary", "web_search", "conversation_memory"],
        "temperature": 0.5,
        "agent": "TechAgent",
    },
}


def generate_config_yaml(
    bot_name: str,
    bot_username: str,
    description: str,
    bot_type: str,
    traits: list,
    features: list,
    temperature: float,
    agent: str,
    custom_prompt: Optional[str] = None,
) -> str:
    """生成config.yaml内容"""
    
    traits_yaml = "\n".join([f'    - "{t}"' for t in traits])
    features_yaml = "\n".join([f'    - "{f}"' for f in features])
    
    # 默认提示词
    if not custom_prompt:
        custom_prompt = f"""你是 {bot_name}，{description}。

## 你的角色特点：
{chr(10).join([f'- {t}' for t in traits])}

## 交互原则：
1. 始终保持专业和友善
2. 根据用户需求调整回复风格
3. 提供准确和有价值的信息
4. 尊重用户隐私和边界

## 回复风格：
- 语言自然流畅
- 适度使用 emoji 增加亲和力
- 根据场景调整正式程度
"""
    
    return f'''# {bot_name} 配置文件
# {description}

bot:
  # 基础信息
  name: "{bot_name}"
  description: "{description}"
  username: "{bot_username}"  # Telegram @username
  
  # Bot类型：companion（陪伴）, assistant（助手）, expert（专家）, creative（创意）, research（研究）
  type: "{bot_type}"
  
  # 语言设置
  language: "zh"
  
  # 是否公开（可被其他用户添加到频道）
  is_public: true


# ======================================
# 🎭 人设配置 - 机器人的核心性格和行为特征
# ======================================
personality:
  # 基础人设描述
  character: |
    {description}
    你致力于为用户提供最好的服务和体验。

  # 性格特点
  traits:
{traits_yaml}
  
  # 语言风格
  speaking_style:
    tone: "专业友善"
    formality: "适度正式"
    use_emoji: true
    emoji_frequency: "moderate"
    
  # 交互偏好
  interaction_style:
    ask_clarifying_questions: true
    provide_examples: true
    use_analogies: true
    summarize_key_points: true
    encourage_user: true


# AI模型配置
ai:
  # 默认Provider: openai, anthropic, vllm
  provider: "openai"
  
  # 模型名称
  model: "gpt-4o"
  
  # 生成参数
  temperature: {temperature}
  max_tokens: 2000
  
  # 上下文窗口大小
  context_window: 8192


# 系统提示词配置
prompt:
  # 自定义系统提示词
  custom: |
    {custom_prompt.replace(chr(10), chr(10) + "    ")}
  
  # 模板变量
  variables:
    bot_name: "{bot_name}"


# 功能配置
features:
  # 启用的功能模块
  enabled:
{features_yaml}
  
  # 禁用的功能
  disabled:
    - "code_execution"


# Agents配置
agents:
  # 启用的Agents
  enabled:
    - name: "{agent}"
      priority: 80
      config: {{}}
  
  # 默认Agent（兜底）
  fallback: "{agent}"


# 消息路由配置
routing:
  # 路由模式: mention（需@）, auto（自动回复）, keyword（关键词触发）
  mode: "auto"
  
  # 私聊是否自动回复
  private_chat_auto_reply: true
  
  # 群聊是否需要@
  group_chat_mention_required: true


# 限额配置（每日）
limits:
  free_tier:
    messages: 15
    images: 0
  
  basic_tier:
    messages: 150
    images: 10
  
  premium_tier:
    messages: 1500
    images: 100


# 回复消息模板
messages:
  welcome: |
    👋 你好！我是{bot_name}。
    
    {description}
    
    有什么我可以帮助你的吗？
  
  help: |
    🌟 我可以帮你：
    
    请直接告诉我你的需求，我会尽力帮助你！
  
  limit_reached: |
    ⚠️ 今天的对话次数已用完。
    
    明天再来和我聊天吧！
    或者升级订阅获取更多额度。


# 元数据
metadata:
  version: "1.0.0"
  author: "SoulmateBot Team"
  created_at: "2024-01-01"
  updated_at: "2024-01-01"
  category: "{bot_type}"
  tags:
    - "{bot_type}"
'''


def generate_init_py(bot_name: str) -> str:
    """生成__init__.py内容"""
    return f'''"""
{bot_name} Bot Package
"""

__all__ = []
'''


def create_bot_directory(
    bot_name: str,
    description: str = "",
    bot_type: str = "assistant",
    custom_traits: Optional[list] = None,
    custom_features: Optional[list] = None,
    dry_run: bool = False,
) -> bool:
    """
    创建新的机器人目录和配置文件
    
    Args:
        bot_name: 机器人名称（如 research_bot）
        description: 机器人描述
        bot_type: 机器人类型
        custom_traits: 自定义性格特点
        custom_features: 自定义功能列表
        dry_run: 仅预览，不实际创建
        
    Returns:
        bool: 创建成功返回True
    """
    import sys
    
    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    bots_dir = project_root / "bots"
    
    # 机器人目录名（使用下划线格式）
    bot_dir_name = bot_name.lower().replace("-", "_").replace(" ", "_")
    if not bot_dir_name.endswith("_bot"):
        bot_dir_name = f"{bot_dir_name}_bot"
    
    bot_dir = bots_dir / bot_dir_name
    
    # 检查是否已存在
    if bot_dir.exists():
        print(f"❌ 机器人目录已存在: {bot_dir}")
        return False
    
    # 获取模板配置
    template = BOT_TEMPLATES.get(bot_type, BOT_TEMPLATES["assistant"])
    
    # 使用自定义或模板默认值
    traits = custom_traits or template["traits"]
    features = custom_features or template["features"]
    temperature = template["temperature"]
    agent = template["agent"]
    
    # 生成显示名称
    display_name = bot_name.replace("_", " ").replace("-", " ").title().replace(" Bot", "Bot")
    if not display_name.endswith("Bot"):
        display_name = f"{display_name}Bot"
    
    # 生成用户名
    username = bot_dir_name.replace("_bot", "_ai_bot")
    
    # 默认描述
    if not description:
        description = template["description"]
    
    # 生成配置内容
    config_content = generate_config_yaml(
        bot_name=display_name,
        bot_username=username,
        description=description,
        bot_type=bot_type,
        traits=traits,
        features=features,
        temperature=temperature,
        agent=agent,
    )
    
    init_content = generate_init_py(display_name)
    
    if dry_run:
        print("\n" + "=" * 60)
        print(f"📁 预览: {bot_dir}")
        print("=" * 60)
        print("\n--- config.yaml ---")
        print(config_content[:1000] + "...\n")
        print("--- __init__.py ---")
        print(init_content)
        return True
    
    try:
        # 创建目录
        bot_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建config.yaml
        config_file = bot_dir / "config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            f.write(config_content)
        
        # 创建__init__.py
        init_file = bot_dir / "__init__.py"
        with open(init_file, "w", encoding="utf-8") as f:
            f.write(init_content)
        
        print("\n" + "=" * 60)
        print("✅ 机器人创建成功！")
        print("=" * 60)
        print(f"""
📁 目录: {bot_dir}
📄 文件:
   - config.yaml (配置文件)
   - __init__.py

💡 下一步:
   1. 编辑 {config_file} 自定义机器人人设
   2. 在 BotFather 中创建 Telegram Bot
   3. 运行以下命令注册机器人:
      python scripts/db_manager.py register
   4. 设置 Bot Token:
      python scripts/db_manager.py token-set <bot_id> <token>
""")
        sys.stdout.flush()
        return True
        
    except Exception as e:
        print(f"❌ 创建失败: {e}")
        return False


def list_templates():
    """列出所有可用模板"""
    print("\n" + "=" * 60)
    print("📋 可用的机器人模板")
    print("=" * 60)
    
    for name, template in BOT_TEMPLATES.items():
        print(f"\n  📌 {name}")
        print(f"     描述: {template['description']}")
        print(f"     特点: {', '.join(template['traits'][:3])}...")
        print(f"     Agent: {template['agent']}")
        print(f"     Temperature: {template['temperature']}")


def list_existing_bots():
    """列出已有的机器人"""
    project_root = Path(__file__).parent.parent
    bots_dir = project_root / "bots"
    
    print("\n" + "=" * 60)
    print("🤖 已有的机器人")
    print("=" * 60)
    
    if not bots_dir.exists():
        print("   (无)")
        return
    
    for bot_dir in sorted(bots_dir.iterdir()):
        if bot_dir.is_dir() and not bot_dir.name.startswith("_"):
            config_file = bot_dir / "config.yaml"
            if config_file.exists():
                print(f"   • {bot_dir.name}")


def interactive_create():
    """交互式创建机器人"""
    print("\n" + "=" * 60)
    print("🤖 创建新机器人")
    print("=" * 60)
    
    list_existing_bots()
    list_templates()
    
    print("\n请输入机器人信息:")
    
    # 获取名称
    bot_name = input("   机器人名称 (如 research): ").strip()
    if not bot_name:
        print("❌ 名称不能为空")
        return False
    
    # 获取类型
    print("\n   选择机器人类型:")
    for i, t in enumerate(BOT_TEMPLATES.keys(), 1):
        print(f"      [{i}] {t}")
    type_choice = input("   请选择 (1-5, 默认2): ").strip() or "2"
    try:
        type_idx = int(type_choice) - 1
        bot_type = list(BOT_TEMPLATES.keys())[type_idx]
    except (ValueError, IndexError):
        bot_type = "assistant"
    
    # 获取描述
    description = input(f"\n   机器人描述 (默认: {BOT_TEMPLATES[bot_type]['description']}): ").strip()
    
    # 确认
    print(f"\n   将创建: {bot_name}_bot (类型: {bot_type})")
    if input("   确认创建? (yes/no): ").lower() != "yes":
        print("❌ 已取消")
        return False
    
    return create_bot_directory(
        bot_name=bot_name,
        description=description,
        bot_type=bot_type,
    )


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="机器人模板生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # new 命令
    new_parser = subparsers.add_parser("new", help="创建新机器人")
    new_parser.add_argument("name", help="机器人名称")
    new_parser.add_argument("--type", "-t", default="assistant", 
                           choices=list(BOT_TEMPLATES.keys()),
                           help="机器人类型")
    new_parser.add_argument("--desc", "-d", default="", help="机器人描述")
    new_parser.add_argument("--dry-run", action="store_true", help="仅预览，不创建")
    
    # list 命令
    subparsers.add_parser("list", help="列出所有模板")
    
    # preview 命令
    preview_parser = subparsers.add_parser("preview", help="预览模板")
    preview_parser.add_argument("template", choices=list(BOT_TEMPLATES.keys()),
                               help="模板名称")
    
    args = parser.parse_args()
    
    if args.command == "new":
        create_bot_directory(
            bot_name=args.name,
            description=args.desc,
            bot_type=args.type,
            dry_run=args.dry_run,
        )
    elif args.command == "list":
        list_templates()
        list_existing_bots()
    elif args.command == "preview":
        create_bot_directory(
            bot_name=f"example_{args.template}",
            bot_type=args.template,
            dry_run=True,
        )
    else:
        # 没有命令，进入交互模式
        interactive_create()


if __name__ == "__main__":
    main()
