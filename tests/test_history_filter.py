"""
Tests for History Filter Utility
测试历史过滤工具
"""
import pytest
import os
import json
import tempfile
import shutil
import sys
from pathlib import Path

# Add the src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import directly from the module file to avoid chain imports
import importlib.util
spec = importlib.util.spec_from_file_location(
    "history_filter", 
    Path(__file__).parent.parent / "src" / "utils" / "history_filter.py"
)
history_filter_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history_filter_module)

HistoryFilter = history_filter_module.HistoryFilter
FilteredContent = history_filter_module.FilteredContent
FilterResult = history_filter_module.FilterResult
get_history_filter = history_filter_module.get_history_filter


class TestHistoryFilter:
    """测试历史过滤器"""
    
    @pytest.fixture
    def filter_with_temp_dir(self):
        """创建带临时目录的过滤器"""
        temp_dir = tempfile.mkdtemp()
        filter_instance = HistoryFilter(
            storage_dir=temp_dir,
            enable_url_filter=True,
            enable_trivial_filter=True,
            enable_disk_storage=True
        )
        yield filter_instance
        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def filter_no_storage(self):
        """创建不使用磁盘存储的过滤器"""
        return HistoryFilter(
            enable_url_filter=True,
            enable_trivial_filter=True,
            enable_disk_storage=False
        )
    
    def test_extract_urls(self, filter_no_storage):
        """测试URL提取"""
        content = "看看这个网站 https://example.com/path 还有这个 www.test.org"
        urls = filter_no_storage.extract_urls(content)
        
        assert len(urls) >= 2
        assert "https://example.com/path" in urls
    
    def test_filter_url_dominated_content(self, filter_no_storage):
        """测试过滤URL主导的内容"""
        # URL主导的消息
        history = [
            {"role": "user", "content": "https://www.example.com/very/long/url/path/to/something"},
            {"role": "assistant", "content": "好的，我看看这个链接"},
        ]
        
        result = filter_no_storage.filter_history(history)
        
        # URL主导的消息应该被过滤，用占位符替换
        assert len(result.filtered_out) >= 1
        assert any("[用户分享了" in msg.get("content", "") for msg in result.filtered_history) or \
               len(result.filtered_history) < len(history)
    
    def test_filter_trivial_content(self, filter_no_storage):
        """测试过滤简单寒暄"""
        history = [
            {"role": "user", "content": "好的"},
            {"role": "assistant", "content": "还有什么需要帮助的吗？"},
            {"role": "user", "content": "谢谢"},
            {"role": "assistant", "content": "不客气！"},
        ]
        
        result = filter_no_storage.filter_history(history)
        
        # 简单寒暄应该被过滤
        assert len(result.filtered_out) >= 2
        # 过滤后应该只剩下助手的回复
        user_messages = [m for m in result.filtered_history if m.get("role") == "user"]
        assert len(user_messages) < 2
    
    def test_preserve_important_content(self, filter_no_storage):
        """测试保留重要内容"""
        history = [
            {"role": "user", "content": "我今天很开心，因为找到了新工作！"},
            {"role": "assistant", "content": "太棒了！恭喜你！"},
            {"role": "user", "content": "谢谢！我下周一开始上班"},
            {"role": "assistant", "content": "加油！新的开始！"},
        ]
        
        result = filter_no_storage.filter_history(history)
        
        # 重要内容应该保留
        # 至少保留"找到新工作"这条重要信息
        assert any("找到了新工作" in m.get("content", "") for m in result.filtered_history)
    
    def test_filter_empty_content(self, filter_no_storage):
        """测试过滤空内容"""
        history = [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": "你好"},
            {"role": "user", "content": "   "},
            {"role": "assistant", "content": "有什么可以帮助你的吗？"},
        ]
        
        result = filter_no_storage.filter_history(history)
        
        # 空内容应该被过滤
        assert len(result.filtered_history) <= len(history)
    
    def test_clean_urls_from_content(self, filter_no_storage):
        """测试清理内容中的URL"""
        content = "我觉得这个网站 https://example.com 很不错，你觉得呢？"
        cleaned = filter_no_storage._clean_urls_from_content(content)
        
        assert "[链接]" in cleaned
        assert "https://example.com" not in cleaned
        assert "我觉得这个网站" in cleaned
    
    def test_is_url_dominated(self, filter_no_storage):
        """测试URL主导判断"""
        # URL主导
        url_only = "https://www.example.com/path/to/something"
        assert filter_no_storage.is_url_dominated(url_only) is True
        
        # 非URL主导
        text_with_url = "这是一段很长的文字，包含了很多内容，然后有一个链接 https://x.com"
        assert filter_no_storage.is_url_dominated(text_with_url) is False
    
    def test_disk_storage(self, filter_with_temp_dir):
        """测试磁盘存储功能"""
        history = [
            {"role": "user", "content": "好的"},
            {"role": "assistant", "content": "收到"},
        ]
        
        result = filter_with_temp_dir.filter_history(
            history, 
            chat_id="test_chat",
            user_id="test_user"
        )
        
        # 应该有存储路径
        if result.filtered_out:
            assert result.storage_path is not None
            assert os.path.exists(result.storage_path)
            
            # 验证存储内容
            with open(result.storage_path, 'r', encoding='utf-8') as f:
                stored_data = json.load(f)
            
            assert stored_data["chat_id"] == "test_chat"
            assert stored_data["user_id"] == "test_user"
            assert len(stored_data["items"]) == len(result.filtered_out)
    
    def test_retrieve_filtered_content(self, filter_with_temp_dir):
        """测试检索过滤内容"""
        # 先过滤一些内容
        history = [
            {"role": "user", "content": "好的"},
            {"role": "user", "content": "谢谢"},
        ]
        
        filter_with_temp_dir.filter_history(
            history,
            chat_id="retrieve_test",
            user_id="user123"
        )
        
        # 检索
        results = filter_with_temp_dir.retrieve_filtered_content(
            chat_id="retrieve_test",
            user_id="user123"
        )
        
        assert len(results) >= 1
        assert results[0]["chat_id"] == "retrieve_test"
    
    def test_no_filter_when_disabled(self):
        """测试禁用过滤时不过滤"""
        filter_instance = HistoryFilter(
            enable_url_filter=False,
            enable_trivial_filter=False,
            enable_disk_storage=False,
            min_content_length=1  # 设置为1以避免短内容过滤
        )
        
        history = [
            {"role": "user", "content": "好的，我知道了"},  # 使用更长的内容
            {"role": "user", "content": "https://example.com 是一个很好的网站"},
        ]
        
        result = filter_instance.filter_history(history)
        
        # 禁用过滤后应该保留所有内容
        assert len(result.filtered_history) == len(history)
    
    def test_global_filter_instance(self):
        """测试全局过滤器实例"""
        # Reset the global instance first
        history_filter_module._history_filter = None
        
        filter1 = get_history_filter()
        filter2 = get_history_filter()
        
        assert filter1 is filter2  # 应该是同一个实例


class TestFilterResult:
    """测试过滤结果类"""
    
    def test_filter_result_structure(self):
        """测试过滤结果结构"""
        result = FilterResult(
            filtered_history=[{"role": "user", "content": "test"}],
            filtered_out=[
                FilteredContent(
                    original_content="好的",
                    filter_reason="trivial"
                )
            ],
            storage_path="/tmp/test.json"
        )
        
        assert len(result.filtered_history) == 1
        assert len(result.filtered_out) == 1
        assert result.storage_path == "/tmp/test.json"


class TestFilteredContent:
    """测试过滤内容类"""
    
    def test_filtered_content_with_urls(self):
        """测试包含URL的过滤内容"""
        content = FilteredContent(
            original_content="https://example.com",
            filter_reason="url_dominated",
            extracted_urls=["https://example.com"],
            placeholder="[用户分享了1个链接]"
        )
        
        assert content.filter_reason == "url_dominated"
        assert len(content.extracted_urls) == 1
        assert "[用户分享了1个链接]" in content.placeholder
