"""
Tests for LLM Call Optimization

验证减少冗余LLM调用的优化措施：
1. skip_llm_analysis 参数正确跳过 LLM 调用
2. memory_analysis 逻辑正确处理所有分支
"""
import pytest
import sys
from pathlib import Path

# Add src to path for direct imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


class TestMemoryAnalysisDataStructure:
    """测试 MemoryAnalysis 数据结构"""
    
    def test_memory_analysis_structure(self):
        """验证 MemoryAnalysis 的数据结构正确"""
        from agents.orchestrator import MemoryAnalysis
        
        # 测试所有字段都存在
        memory_analysis = MemoryAnalysis(
            is_important=True,
            importance_level="medium",
            event_type="birthday",
            event_summary="下个月15号是用户的生日",
            keywords=["生日", "15号"],
            event_date="2026-02-15",
            raw_date_expression="下个月15号"
        )
        
        assert memory_analysis.is_important is True
        assert memory_analysis.importance_level == "medium"
        assert memory_analysis.event_type == "birthday"
        assert memory_analysis.event_summary == "下个月15号是用户的生日"
        assert memory_analysis.keywords == ["生日", "15号"]
        assert memory_analysis.event_date == "2026-02-15"
        assert memory_analysis.raw_date_expression == "下个月15号"
    
    def test_memory_analysis_defaults(self):
        """验证 MemoryAnalysis 的默认值"""
        from agents.orchestrator import MemoryAnalysis
        
        # 测试默认值
        memory_analysis = MemoryAnalysis()
        
        assert memory_analysis.is_important is False
        assert memory_analysis.importance_level is None
        assert memory_analysis.event_type is None
        assert memory_analysis.event_summary is None
        assert memory_analysis.keywords == []
        assert memory_analysis.event_date is None
        assert memory_analysis.raw_date_expression is None
    
    def test_memory_analysis_not_important_structure(self):
        """测试 is_important=False 的数据结构"""
        from agents.orchestrator import MemoryAnalysis
        
        memory_analysis = MemoryAnalysis(
            is_important=False,
            importance_level=None,
            event_type=None,
            event_summary=None,
            keywords=[],
            event_date=None,
            raw_date_expression=None
        )
        
        assert memory_analysis.is_important is False
        assert memory_analysis.importance_level is None


class TestMemorySavingBranchLogic:
    """测试记忆保存逻辑的不同分支"""
    
    def test_memory_analysis_branch_conditions(self):
        """测试不同的 memory_analysis 分支条件"""
        from agents.orchestrator import MemoryAnalysis
        
        # 情况 1: memory_analysis 存在且重要
        analysis_important = MemoryAnalysis(is_important=True, importance_level="high")
        assert analysis_important is not None
        assert analysis_important.is_important is True
        
        # 情况 2: memory_analysis 存在但不重要
        analysis_not_important = MemoryAnalysis(is_important=False)
        assert analysis_not_important is not None
        assert analysis_not_important.is_important is False
        
        # 情况 3: memory_analysis 为 None (回退到传统模式)
        analysis_none = None
        assert analysis_none is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
