#!/usr/bin/env python3
"""
基础数据库管理类和通用工具
=========================

提供数据库连接、表管理和基础操作功能。
"""

import sys
import time
from typing import List, Optional, Dict, Any

from sqlalchemy import inspect, text
from loguru import logger

# 添加项目根目录到路径
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import engine, get_db_session
from src.models.database import Base, User, Bot, Channel, ChannelBotMapping, Conversation, UsageRecord, Payment


class DatabaseManager:
    """
    数据库基础管理器
    
    提供数据库结构管理和状态查询功能:
    - rebuild: 重建数据库
    - status: 查看数据库状态
    - fix_schema: 修复数据库结构
    - clear_data: 清空所有数据
    """

    def __init__(self):
        """初始化数据库管理器"""
        self.engine = engine

    def add_table_comments(self) -> bool:
        """
        为所有表和列添加注释
        
        Returns:
            bool: 是否成功添加注释
        """
        try:
            # 获取所有模型类
            table_comments = {}
            column_comments = {}
            
            # 遍历所有模型
            for mapper in Base.registry.mappers:
                model_class = mapper.class_
                table_name = mapper.mapped_table.name
                
                # 获取表级注释（从文档字符串）
                if model_class.__doc__:
                    # 提取第一行作为简短描述
                    doc_lines = model_class.__doc__.strip().split('\n')
                    table_comment = doc_lines[0].strip()
                    table_comments[table_name] = table_comment
                
                # 获取列级注释
                column_comments[table_name] = {}
                for column in mapper.mapped_table.columns:
                    if column.comment:
                        column_comments[table_name][column.name] = column.comment
            
            # 生成并执行 SQL 注释语句
            with self.engine.connect() as conn:
                # 添加表级注释
                for table_name, comment in table_comments.items():
                    sql = text(f"COMMENT ON TABLE {table_name} IS :comment")
                    conn.execute(sql, {"comment": comment})
                    print(f"   ✅ 已添加表注释: {table_name}")
                
                # 添加列级注释
                for table_name, columns in column_comments.items():
                    for column_name, comment in columns.items():
                        sql = text(f"COMMENT ON COLUMN {table_name}.{column_name} IS :comment")
                        conn.execute(sql, {"comment": comment})
                
                conn.commit()
            
            print(f"\n✅ 已为 {len(table_comments)} 个表添加注释")
            return True
            
        except Exception as e:
            print(f"❌ 添加注释失败: {e}")
            return False

    def rebuild(self, confirm: bool = False) -> bool:
        """
        重建数据库：删除所有表并重新创建
        
        Args:
            confirm: 是否跳过确认提示
            
        Returns:
            bool: 重建是否成功
        """
        print("\n" + "=" * 60)
        print("🗑️  数据库重建工具")
        print("=" * 60)
        print("\n⚠️  警告：这将删除所有数据！\n")
        sys.stdout.flush()

        if not confirm:
            user_input = input("输入 'yes' 继续: ")
            if user_input.lower() != 'yes':
                print("❌ 已取消")
                return False

        try:
            def show_progress(message: str, done: bool = False):
                if done:
                    print(f"\r{message} ✅")
                else:
                    print(f"\r{message}", end="")
                sys.stdout.flush()
            
            # 删除表
            show_progress("🗑️  正在删除所有表...")
            start_time = time.time()
            Base.metadata.drop_all(bind=self.engine)
            elapsed = time.time() - start_time
            show_progress(f"🗑️  所有表已删除 ({elapsed:.2f}s)", done=True)

            # 创建表
            show_progress("🔨 正在创建所有表...")
            start_time = time.time()
            Base.metadata.create_all(bind=self.engine)
            elapsed = time.time() - start_time
            show_progress(f"🔨 所有表已创建 ({elapsed:.2f}s)", done=True)
            
            # 添加注释
            show_progress("📝 正在添加表和列注释...")
            start_time = time.time()
            self.add_table_comments()
            elapsed = time.time() - start_time
            show_progress(f"📝 注释已添加 ({elapsed:.2f}s)", done=True)
            
            print()
            self.show_tables()
            
            print("\n✅ 数据库重建完成！")
            sys.stdout.flush()
            return True

        except Exception as e:
            print(f"\n❌ 重建失败: {e}")
            sys.stdout.flush()
            return False

    def status(self) -> None:
        """显示数据库状态和统计信息"""
        print("\n" + "=" * 60)
        print("📊 数据库状态")
        print("=" * 60)
        sys.stdout.flush()

        self.show_tables()

        db = get_db_session()
        try:
            print("\n📈 数据统计:")
            sys.stdout.flush()
            print(f"   👤 用户数: {db.query(User).count()}")
            print(f"   🤖 Bot 数: {db.query(Bot).count()}")
            print(f"   💬 Channel 数: {db.query(Channel).count()}")
            print(f"   🔗 绑定数: {db.query(ChannelBotMapping).count()}")
            print(f"   💭 对话数: {db.query(Conversation).count()}")
            sys.stdout.flush()

            print("\n" + "-" * 60)
            print("📋 详细数据:")
            sys.stdout.flush()

            # 用户列表
            users = db.query(User).all()
            if users:
                print("\n   👤 用户列表:")
                for u in users:
                    print(f"      [{u.id}] @{u.username} | {u.first_name} | tier:{u.subscription_tier}")
                sys.stdout.flush()

            # Bot列表
            bots = db.query(Bot).all()
            if bots:
                print("\n   🤖 Bot 列表:")
                for b in bots:
                    print(f"      [{b.id}] @{b.bot_username} | {b.bot_name} | {b.ai_provider}/{b.ai_model}")
                sys.stdout.flush()

            # Channel列表
            channels = db.query(Channel).all()
            if channels:
                print("\n   💬 Channel 列表:")
                for c in channels:
                    print(f"      [{c.id}] {c.chat_type}: {c.title or '(无标题)'} | chat_id:{c.telegram_chat_id}")
                sys.stdout.flush()

            # 绑定列表
            mappings = db.query(ChannelBotMapping).all()
            if mappings:
                print("\n   🔗 绑定列表:")
                for m in mappings:
                    bot = db.query(Bot).filter(Bot.id == m.bot_id).first()
                    channel = db.query(Channel).filter(Channel.id == m.channel_id).first()
                    bot_name = f"@{bot.bot_username}" if bot else f"Bot#{m.bot_id}"
                    channel_name = channel.title or str(channel.telegram_chat_id) if channel else f"Channel#{m.channel_id}"
                    status = "✅" if m.is_active else "❌"
                    print(f"      {status} {channel_name} <-> {bot_name} | mode:{m.routing_mode}")
                sys.stdout.flush()

        finally:
            db.close()

    def fix_schema(self) -> bool:
        """
        修复数据库结构
        
        检查并添加缺失的列。
        
        Returns:
            bool: 修复是否成功
        """
        print("\n" + "=" * 60)
        print("🔧 修复数据库结构")
        print("=" * 60)

        inspector = inspect(self.engine)

        schema_fixes = {
            'users': [('uuid', 'VARCHAR(36)'), ('version', 'INTEGER DEFAULT 1')],
            'bots': [('uuid', 'VARCHAR(36)'), ('version', 'INTEGER DEFAULT 1')],
            'channels': [('version', 'INTEGER DEFAULT 1')],
            'channel_bot_mappings': [('version', 'INTEGER DEFAULT 1')],
        }

        try:
            with self.engine.connect() as conn:
                for table_name, columns in schema_fixes.items():
                    if table_name not in inspector.get_table_names():
                        continue

                    existing_cols = [col['name'] for col in inspector.get_columns(table_name)]

                    for col_name, col_type in columns:
                        if col_name not in existing_cols:
                            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))
                            print(f"   ✅ {table_name}.{col_name} 已添加")

                conn.commit()

            print("\n✅ 数据库结构修复完成!")
            return True

        except Exception as e:
            print(f"❌ 修复失败: {e}")
            return False

    def clear_data(self, confirm: bool = False) -> bool:
        """
        清空所有数据
        
        Args:
            confirm: 是否跳过确认提示
            
        Returns:
            bool: 清空是否成功
        """
        print("\n" + "=" * 60)
        print("🧹 清空数据")
        print("=" * 60)

        if not confirm:
            if input("\n输入 'yes' 继续: ").lower() != 'yes':
                print("❌ 已取消")
                return False

        db = get_db_session()
        try:
            db.query(ChannelBotMapping).delete()
            db.query(Conversation).delete()
            db.query(UsageRecord).delete()
            db.query(Payment).delete()
            db.query(Channel).delete()
            db.query(Bot).delete()
            db.query(User).delete()
            db.commit()
            print("✅ 所有数据已清空!")
            return True
        except Exception as e:
            db.rollback()
            print(f"❌ 清空失败: {e}")
            return False
        finally:
            db.close()

    def show_tables(self) -> None:
        """显示所有数据库表"""
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        print(f"\n📋 数据库中的表 ({len(tables)} 个):")
        for table in tables:
            cols = [col['name'] for col in inspector.get_columns(table)]
            print(f"   • {table}: {len(cols)} 列")

    def get_table_info(self) -> Dict[str, List[str]]:
        """
        获取所有表的列信息
        
        Returns:
            Dict[str, List[str]]: 表名到列名列表的映射
        """
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        result = {}
        for table in tables:
            cols = [col['name'] for col in inspector.get_columns(table)]
            result[table] = cols
        return result
