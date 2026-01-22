"""
Bots Package - Bot模板系统

本目录包含所有机器人的配置文件和定义。每个机器人都有自己独特的：
- 人设 (Personality): 性格特点、语言风格
- 技能 (Skills): 专业领域、关键词匹配
- AI配置: 模型选择、参数设置

每个Bot目录包含：
- config.yaml: Bot配置文件（人设、技能、AI配置）
- __init__.py: Bot包初始化

目录结构：
bots/
├── soulmate_bot/     # 情感陪伴机器人
│   ├── config.yaml
│   └── __init__.py
├── assistant_bot/    # 通用智能助手
│   ├── config.yaml
│   └── __init__.py
├── teacher_bot/      # 智慧导师 - 教育辅导
│   ├── config.yaml
│   └── __init__.py
├── fitness_bot/      # 健身教练 - 运动指导
│   ├── config.yaml
│   └── __init__.py
└── creative_bot/     # 创意达人 - 写作助手
    ├── config.yaml
    └── __init__.py

开发新机器人步骤：
1. 在 bots/ 下创建新的目录（如 my_bot/）
2. 创建 __init__.py 和 config.yaml
3. 在 config.yaml 中配置人设、技能、AI参数
4. 使用 db_manager.py register 注册到数据库
5. 使用 db_manager.py token-set 设置 Telegram Token

详细配置说明请参考现有机器人的 config.yaml 文件。
"""
