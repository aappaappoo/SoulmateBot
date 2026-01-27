"""
Test for database manager comment functionality
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from sqlalchemy import text


class TestDatabaseManagerComments:
    """Test suite for add_table_comments functionality"""
    
    def test_add_table_comments_extracts_model_info(self):
        """Test that add_table_comments correctly extracts table and column comments"""
        # Import here to avoid issues with module loading
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        from scripts.db_manager.base import DatabaseManager
        from src.models.database import Base
        
        # Create a mock engine and connection
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = Mock(return_value=False)
        
        # Create DatabaseManager instance with mocked engine
        db_manager = DatabaseManager()
        db_manager.engine = mock_engine
        
        # Execute the method
        result = db_manager.add_table_comments()
        
        # Verify it succeeded
        assert result is True
        
        # Verify that SQL statements were executed
        assert mock_conn.execute.called
        assert mock_conn.commit.called
        
        # Get all execute calls
        execute_calls = mock_conn.execute.call_args_list
        
        # Verify that table comments were added
        table_comment_calls = [
            call for call in execute_calls 
            if 'COMMENT ON TABLE' in str(call)
        ]
        assert len(table_comment_calls) > 0, "Should have table comment statements"
        
        # Verify that column comments were added
        column_comment_calls = [
            call for call in execute_calls 
            if 'COMMENT ON COLUMN' in str(call)
        ]
        assert len(column_comment_calls) > 0, "Should have column comment statements"
    
    def test_add_table_comments_handles_exceptions(self):
        """Test that add_table_comments handles exceptions gracefully"""
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        from scripts.db_manager.base import DatabaseManager
        
        # Create a mock engine that raises an exception
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("Database connection failed")
        
        # Create DatabaseManager instance with mocked engine
        db_manager = DatabaseManager()
        db_manager.engine = mock_engine
        
        # Execute the method
        result = db_manager.add_table_comments()
        
        # Verify it returns False on exception
        assert result is False
    
    def test_comment_extraction_from_models(self):
        """Test that comments are correctly extracted from model definitions"""
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        from src.models.database import Base, User, Payment, Bot
        
        # Verify that models have docstrings
        assert User.__doc__ is not None, "User model should have docstring"
        assert Payment.__doc__ is not None, "Payment model should have docstring"
        assert Bot.__doc__ is not None, "Bot model should have docstring"
        
        # Verify that models have comments on columns
        for mapper in Base.registry.mappers:
            table = mapper.mapped_table
            columns_with_comments = [col for col in table.columns if col.comment]
            assert len(columns_with_comments) > 0, f"Table {table.name} should have columns with comments"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
