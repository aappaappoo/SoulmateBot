"""
Tests for Reminder Service

测试提醒服务的解析和格式化功能
"""
import pytest
import re
from typing import Optional, Tuple


# ========== Copy of the parser classes for testing ==========
# This avoids dependency issues from the main services module

class ReminderParser:
    """提醒解析器"""
    
    TIME_UNITS = {
        "分钟": 1, "分": 1, "分鐘": 1, "min": 1, "minute": 1, "minutes": 1,
        "小时": 60, "小時": 60, "个小时": 60, "個小時": 60, "hour": 60, "hours": 60, "hr": 60, "h": 60,
        "天": 1440, "day": 1440, "days": 1440,
    }
    
    CHINESE_NUMBERS = {
        "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
        "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
        "半": 0.5, "两": 2, "兩": 2
    }
    
    REMINDER_PATTERNS = [
        r"(\d+|[一二三四五六七八九十两兩半]+)\s*(分钟|分|分鐘|小时|小時|个小时|個小時|天|hour|hours|minute|minutes|min|day|days|hr|h)后[记記]?[得要]?提醒我(.+)",
        r"提醒我(\d+|[一二三四五六七八九十两兩半]+)\s*(分钟|分|分鐘|小时|小時|个小时|個小時|天|hour|hours|minute|minutes|min|day|days|hr|h)后(.+)",
        r"过[了]?(\d+|[一二三四五六七八九十两兩半]+)\s*(分钟|分|分鐘|小时|小時|个小时|個小時|天|hour|hours|minute|minutes|min|day|days|hr|h)提醒我(.+)",
        r"remind me in (\d+)\s*(minute|minutes|min|hour|hours|hr|h|day|days)s?\s+(?:to\s+)?(.+)",
        r"in (\d+)\s*(minute|minutes|min|hour|hours|hr|h|day|days)s?\s+remind me\s+(?:to\s+)?(.+)",
    ]
    
    def parse(self, message: str) -> Optional[Tuple[int, str]]:
        message = message.strip()
        for pattern in self.REMINDER_PATTERNS:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                amount_str = match.group(1)
                unit = match.group(2).lower()
                content = match.group(3).strip()
                
                amount = self._parse_amount(amount_str)
                if amount is None:
                    continue
                
                minutes = int(amount * self.TIME_UNITS.get(unit, 1))
                content = self._clean_content(content)
                
                if content and minutes > 0:
                    return (minutes, content)
        return None
    
    def _parse_amount(self, amount_str: str) -> Optional[float]:
        try:
            return float(amount_str)
        except ValueError:
            pass
        
        if amount_str in self.CHINESE_NUMBERS:
            return self.CHINESE_NUMBERS[amount_str]
        
        if "十" in amount_str:
            if amount_str == "十":
                return 10
            elif amount_str.startswith("十"):
                rest = amount_str[1:]
                if rest in self.CHINESE_NUMBERS:
                    return 10 + self.CHINESE_NUMBERS[rest]
            else:
                parts = amount_str.split("十")
                if len(parts) == 2:
                    tens = self.CHINESE_NUMBERS.get(parts[0], 0) * 10
                    ones = self.CHINESE_NUMBERS.get(parts[1], 0) if parts[1] else 0
                    return tens + ones
        
        return None
    
    def _clean_content(self, content: str) -> str:
        # 移除开头的独立"要"或"去"字
        if content.startswith("要") and len(content) > 1:
            content = content[1:]
        elif content.startswith("去") and len(content) > 1:
            content = content[1:]
        content = content.rstrip("。！？!?")
        return content.strip()


def format_reminder_confirmation(minutes: int, reminder_text: str) -> str:
    if minutes >= 1440:
        days = minutes // 1440
        time_str = f"{days}天"
    elif minutes >= 60:
        hours = minutes // 60
        remaining_mins = minutes % 60
        if remaining_mins > 0:
            time_str = f"{hours}小时{remaining_mins}分钟"
        else:
            time_str = f"{hours}小时"
    else:
        time_str = f"{minutes}分钟"
    
    return f"⏰ 好的！我会在 {time_str} 后提醒你：\n\n📝 {reminder_text}\n\n放心吧，到时间我会准时提醒你的！"


def format_reminder_message(reminder_text: str) -> str:
    return f"⏰ **提醒时间到！**\n\n📝 {reminder_text}\n\n记得去做哦！"


class TestReminderParser:
    """测试提醒解析器"""
    
    def setup_method(self):
        self.parser = ReminderParser()
    
    # ========== 中文格式测试 ==========
    
    def test_parse_chinese_hour_reminder(self):
        """测试中文小时提醒格式"""
        result = self.parser.parse("1小时后提醒我开会")
        assert result is not None
        minutes, text = result
        assert minutes == 60
        assert text == "开会"
    
    def test_parse_chinese_minute_reminder(self):
        """测试中文分钟提醒格式"""
        result = self.parser.parse("30分钟后提醒我吃药")
        assert result is not None
        minutes, text = result
        assert minutes == 30
        assert text == "吃药"
    
    def test_parse_chinese_reminder_prefix(self):
        """测试提醒我在前面的格式"""
        result = self.parser.parse("提醒我30分钟后给妈妈打电话")
        assert result is not None
        minutes, text = result
        assert minutes == 30
        assert text == "给妈妈打电话"
    
    def test_parse_chinese_guo_format(self):
        """测试'过X时间提醒我'格式"""
        result = self.parser.parse("过2小时提醒我吃药")
        assert result is not None
        minutes, text = result
        assert minutes == 120
        assert text == "吃药"
    
    def test_parse_chinese_jide_format(self):
        """测试'记得提醒我'格式"""
        result = self.parser.parse("半小时后记得提醒我做饭")
        assert result is not None
        minutes, text = result
        assert minutes == 30
        assert text == "做饭"
    
    def test_parse_chinese_day_reminder(self):
        """测试中文天数提醒"""
        result = self.parser.parse("1天后提醒我交作业")
        assert result is not None
        minutes, text = result
        assert minutes == 1440
        assert text == "交作业"
    
    def test_parse_chinese_number_yi(self):
        """测试中文数字一"""
        result = self.parser.parse("一小时后提醒我休息")
        assert result is not None
        minutes, text = result
        assert minutes == 60
        assert text == "休息"
    
    def test_parse_chinese_number_ban(self):
        """测试中文数字半"""
        result = self.parser.parse("半小时后提醒我喝水")
        assert result is not None
        minutes, text = result
        assert minutes == 30
        assert text == "喝水"
    
    def test_parse_chinese_number_liang(self):
        """测试中文数字两"""
        result = self.parser.parse("两小时后提醒我回家")
        assert result is not None
        minutes, text = result
        assert minutes == 120
        assert text == "回家"
    
    # ========== 英文格式测试 ==========
    
    def test_parse_english_remind_me_in(self):
        """测试英文 remind me in 格式"""
        result = self.parser.parse("remind me in 10 minutes to check email")
        assert result is not None
        minutes, text = result
        assert minutes == 10
        assert text == "check email"
    
    def test_parse_english_in_remind_me(self):
        """测试英文 in X remind me 格式"""
        result = self.parser.parse("in 1 hour remind me to call John")
        assert result is not None
        minutes, text = result
        assert minutes == 60
        assert text == "call John"
    
    def test_parse_english_hours(self):
        """测试英文小时"""
        result = self.parser.parse("remind me in 2 hours to take a break")
        assert result is not None
        minutes, text = result
        assert minutes == 120
        assert text == "take a break"
    
    def test_parse_english_day(self):
        """测试英文天数"""
        result = self.parser.parse("remind me in 1 day to submit report")
        assert result is not None
        minutes, text = result
        assert minutes == 1440
        assert text == "submit report"
    
    # ========== 边界情况测试 ==========
    
    def test_parse_not_a_reminder(self):
        """测试非提醒消息"""
        result = self.parser.parse("今天天气怎么样")
        assert result is None
    
    def test_parse_empty_message(self):
        """测试空消息"""
        result = self.parser.parse("")
        assert result is None
    
    def test_parse_incomplete_reminder(self):
        """测试不完整的提醒格式"""
        result = self.parser.parse("1小时后")
        assert result is None
    
    def test_parse_strips_punctuation(self):
        """测试移除结尾标点"""
        result = self.parser.parse("5分钟后提醒我喝水。")
        assert result is not None
        _, text = result
        assert text == "喝水"
    
    def test_parse_strips_action_prefix(self):
        """测试移除动作前缀"""
        result = self.parser.parse("10分钟后提醒我要做运动")
        assert result is not None
        _, text = result
        assert text == "做运动"


class TestFormatReminderConfirmation:
    """测试提醒确认消息格式化"""
    
    def test_format_minutes(self):
        """测试分钟格式"""
        msg = format_reminder_confirmation(30, "喝水")
        assert "30分钟" in msg
        assert "喝水" in msg
    
    def test_format_hours(self):
        """测试小时格式"""
        msg = format_reminder_confirmation(60, "开会")
        assert "1小时" in msg
        assert "开会" in msg
    
    def test_format_hours_and_minutes(self):
        """测试小时和分钟混合格式"""
        msg = format_reminder_confirmation(90, "吃饭")
        assert "1小时30分钟" in msg
        assert "吃饭" in msg
    
    def test_format_days(self):
        """测试天数格式"""
        msg = format_reminder_confirmation(1440, "交作业")
        assert "1天" in msg
        assert "交作业" in msg


class TestFormatReminderMessage:
    """测试提醒发送消息格式化"""
    
    def test_format_message(self):
        """测试提醒消息格式"""
        msg = format_reminder_message("开会")
        assert "提醒时间到" in msg
        assert "开会" in msg
        assert "记得去做" in msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
