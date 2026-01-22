#!/usr/bin/env python3
"""
Token管理模块
=============

提供Bot Token的管理功能，包括设置、验证和批量导入。
"""

import sys
import os
from typing import Optional, List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import get_db_session
from src.models.database import Bot


class TokenManager:
    """
    Token管理类
    
    提供Token相关操作:
    - set_token: 设置Bot Token
    - validate: 验证Token有效性
    - batch_import: 批量导入Token
    - list_tokens: 列出所有Token
    """

    @staticmethod
    def set_token(bot_id: int, token: str) -> bool:
        """
        设置Bot Token
        
        Args:
            bot_id: Bot数据库ID
            token: Telegram Bot Token
            
        Returns:
            bool: 设置是否成功
        """
        db = get_db_session()
        try:
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                print(f"❌ Bot不存在: ID={bot_id}")
                return False
            
            bot.bot_token = token
            db.commit()
            print(f"✅ Token已设置: @{bot.bot_username}")
            return True
        except Exception as e:
            db.rollback()
            print(f"❌ 设置Token失败: {e}")
            return False
        finally:
            db.close()

    @staticmethod
    def set_token_interactive() -> bool:
        """交互式设置Token"""
        db = get_db_session()
        try:
            bots = db.query(Bot).all()
            if not bots:
                print("\n❌ 没有任何Bot")
                return False
            
            print("\n🤖 可用的Bot:")
            for b in bots:
                print(f"   [{b.id}] @{b.bot_username} - {b.bot_name}")
            
            bot_id = int(input("\n请输入Bot ID: "))
            token = input("请输入Bot Token (从BotFather获取): ").strip()
            
            if not token:
                print("❌ Token不能为空")
                return False
            
            db.close()
            return TokenManager.set_token(bot_id, token)
        except ValueError as e:
            print(f"❌ 输入错误: {e}")
            return False
        finally:
            db.close()

    @staticmethod
    def list_tokens() -> None:
        """列出所有Bot的Token信息"""
        db = get_db_session()
        try:
            bots = db.query(Bot).all()
            
            print("\n" + "=" * 60)
            print("🔑 Bot Token列表")
            print("=" * 60)
            
            if not bots:
                print("\n   📭 暂无Bot")
                return
            
            for b in bots:
                # 隐藏Token中间部分
                token = b.bot_token
                if token and len(token) > 20:
                    masked = token[:10] + "..." + token[-10:]
                else:
                    masked = token or "(未设置)"
                
                print(f"\n   [{b.id}] @{b.bot_username}")
                print(f"       名称: {b.bot_name}")
                print(f"       Token: {masked}")
                print(f"       状态: {b.status}")
        finally:
            db.close()

    @staticmethod
    def validate_token(bot_id: int = None) -> Dict[int, bool]:
        """
        验证Token有效性
        
        通过Telegram API验证Token是否有效。
        
        Args:
            bot_id: 指定Bot ID，为None则验证所有
            
        Returns:
            Dict[int, bool]: Bot ID到验证结果的映射
        """
        try:
            import requests
        except ImportError:
            print("❌ 需要安装requests库: pip install requests")
            return {}
        
        db = get_db_session()
        results = {}
        
        try:
            if bot_id:
                bots = [db.query(Bot).filter(Bot.id == bot_id).first()]
            else:
                bots = db.query(Bot).all()
            
            print("\n🔍 验证Token有效性...\n")
            
            for bot in bots:
                if not bot:
                    continue
                    
                if not bot.bot_token:
                    print(f"   ⚠️  @{bot.bot_username}: Token未设置")
                    results[bot.id] = False
                    continue
                
                try:
                    url = f"https://api.telegram.org/bot{bot.bot_token}/getMe"
                    response = requests.get(url, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('ok'):
                            api_username = data['result'].get('username', '')
                            print(f"   ✅ @{bot.bot_username}: Token有效 (API: @{api_username})")
                            results[bot.id] = True
                        else:
                            print(f"   ❌ @{bot.bot_username}: Token无效")
                            results[bot.id] = False
                    else:
                        print(f"   ❌ @{bot.bot_username}: Token无效 (HTTP {response.status_code})")
                        results[bot.id] = False
                        
                except Exception as e:
                    print(f"   ⚠️  @{bot.bot_username}: 验证失败 ({e})")
                    results[bot.id] = False
            
            return results
        finally:
            db.close()

    @staticmethod
    def batch_import(token_list: List[tuple]) -> int:
        """
        批量导入Token
        
        Args:
            token_list: [(bot_identifier, token), ...] 列表
                       bot_identifier可以是bot_id(int)或bot_username(str)
                       
        Returns:
            int: 成功导入的数量
        """
        db = get_db_session()
        success_count = 0
        
        try:
            for identifier, token in token_list:
                # 判断是ID还是username
                if isinstance(identifier, int):
                    bot = db.query(Bot).filter(Bot.id == identifier).first()
                else:
                    bot = db.query(Bot).filter(Bot.bot_username == str(identifier)).first()
                
                if not bot:
                    print(f"   ⚠️  Bot不存在: {identifier}")
                    continue
                
                bot.bot_token = token
                success_count += 1
                print(f"   ✅ @{bot.bot_username}: Token已更新")
            
            db.commit()
            return success_count
        except Exception as e:
            db.rollback()
            print(f"❌ 批量导入失败: {e}")
            return success_count
        finally:
            db.close()

    @staticmethod
    def batch_import_interactive() -> int:
        """交互式批量导入Token"""
        print("\n" + "=" * 60)
        print("📥 批量导入Token")
        print("=" * 60)
        print("\n格式说明: 每行一个，格式为: bot_username,token 或 bot_id,token")
        print("示例:")
        print("   my_bot,123456:ABC-DEF")
        print("   1,789012:GHI-JKL")
        print("\n输入Token列表 (输入'END'结束):")
        
        lines = []
        while True:
            line = input("> ").strip()
            if line.upper() == 'END':
                break
            if line:
                lines.append(line)
        
        if not lines:
            print("❌ 没有输入任何Token")
            return 0
        
        token_list = []
        for line in lines:
            parts = line.split(',', 1)
            if len(parts) != 2:
                print(f"   ⚠️  格式错误: {line}")
                continue
            
            identifier = parts[0].strip()
            token = parts[1].strip()
            
            # 尝试解析为int
            try:
                identifier = int(identifier)
            except ValueError:
                pass
            
            token_list.append((identifier, token))
        
        if not token_list:
            print("❌ 没有有效的Token")
            return 0
        
        success = TokenManager.batch_import(token_list)
        print(f"\n✅ 批量导入完成: {success}/{len(token_list)} 成功")
        return success

    @staticmethod
    def manage_interactive() -> None:
        """Token管理交互菜单"""
        print("\n" + "=" * 60)
        print("🔑 Token管理")
        print("=" * 60)
        
        print("\n选择操作:")
        print("   [1] 查看所有Token")
        print("   [2] 设置/更新Token")
        print("   [3] 验证Token有效性")
        print("   [4] 批量导入Token")
        
        choice = input("\n请选择 (1/2/3/4): ").strip()
        
        if choice == "1":
            TokenManager.list_tokens()
        elif choice == "2":
            TokenManager.set_token_interactive()
        elif choice == "3":
            TokenManager.validate_token()
        elif choice == "4":
            TokenManager.batch_import_interactive()
        else:
            print("❌ 无效选择")
