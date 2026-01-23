#!/usr/bin/env python3
"""
SoulmateBot 数据库管理工具
===========================

重构后的数据库管理工具，提供清晰的CRUD操作接口。

新的模块结构:
  db_manager/
  ├── base.py          # 基础数据库管理
  ├── user_crud.py     # 用户增删改查
  ├── bot_crud.py      # Bot增删改查
  ├── channel_crud.py  # Channel增删改查
  ├── mapping_crud.py  # 绑定关系管理
  ├── token_manager.py # Token管理
  └── cli.py           # 命令行接口

使用方法:
  # 推荐使用模块方式运行
  python -m scripts.db_manager <command>

  # 也可以直接运行此脚本(向后兼容)
  python scripts/db_manager.py <command>

命令列表:
  rebuild             重建数据库(删除所有表并重新创建)
  status              查看数据库状态
  fix                 修复数据库结构
  clear               清空所有数据

  user list           列出所有用户
  user create         创建新用户
  user update         更新用户信息
  user delete         删除用户

  bot list            列出所有Bot
  bot create          创建新Bot
  bot update          更新Bot信息
  bot delete          删除Bot

  channel list        列出所有Channel
  channel create      创建新Channel
  channel update      更新Channel信息
  channel delete      删除Channel

  bind                绑定Bot到Channel(交互式)
  bind-quick <chat_id> <bot_id> [mode]   快速绑定
  unbind              解绑Bot(交互式)
  mapping list        列出所有绑定关系

  token               Token管理(交互菜单)
  token-set <bot_id> <token>   快速设置Token
  token-list          列出所有Token
  token-validate      验证Token有效性

  init                初始化测试数据(交互式)
  all                 重建数据库并初始化测试数据

示例:
  python scripts/db_manager.py status
  python scripts/db_manager.py user list
  python scripts/db_manager.py bot create
  python scripts/db_manager.py bind
  python scripts/db_manager.py token-set 1 YOUR_BOT_TOKEN
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入新的模块化CLI
from scripts.db_manager.cli import main

if __name__ == "__main__":
    main()
