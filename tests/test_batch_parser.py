"""Tests for the enhanced NLP parser with batch support."""

import pytest
from datetime import datetime
from unittest.mock import Mock

# Import the enhanced parser
try:
    from src.nlp_parser import NLPStockParser
    from src.schemas import (
        StockMovement, MovementType, MovementStatus, 
        BatchFormat, BatchParseResult
    )
except ImportError:
    from nlp_parser import NLPStockParser
    from schemas import (
        StockMovement, MovementType, MovementStatus,
        BatchFormat, BatchParseResult
    )


class TestBatchDetection:
    """Test batch format detection functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = NLPStockParser()
    
    def test_single_entry_detection(self):
        """Test detection of single entry format."""
        text = "/in cement, 50 bags, from supplier"
        format_type = self.parser.detect_batch_format(text)
        assert format_type == BatchFormat.SINGLE
    
    def test_newline_batch_detection(self):
        """Test detection of newline-separated batch format."""
        text = "/in cement, 50 bags, from supplier\nsteel bars, 100 pieces, from warehouse"
        format_type = self.parser.detect_batch_format(text)
        assert format_type == BatchFormat.NEWLINE
    
    def test_semicolon_batch_detection(self):
        """Test detection of semicolon-separated batch format."""
        text = "/in cement, 50 bags, from supplier; steel bars, 100 pieces, from warehouse"
        format_type = self.parser.detect_batch_format(text)
        assert format_type == BatchFormat.SEMICOLON
    
    def test_mixed_format_detection(self):
        """Test detection of mixed format (newlines + semicolons)."""
        text = "/in cement, 50 bags, from supplier\nsteel bars, 100 pieces; safety equipment, 20 sets"
        format_type = self.parser.detect_batch_format(text)
        assert format_type == BatchFormat.MIXED
    
    def test_multiple_movement_indicators_detection(self):
        """Test detection when multiple movement type indicators are present."""
        text = "/in cement, 50 bags\n/out steel bars, 100 pieces"
        format_type = self.parser.detect_batch_format(text)
        assert format_type == BatchFormat.MIXED


class TestBatchParsing:
    """Test batch parsing functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = NLPStockParser()
        self.user_id = 12345
        self.user_name = "Test User"
    
    def test_single_entry_parsing(self):
        """Test parsing of single entry (backward compatibility)."""
        text = "/in project: Bridge Construction, cement, 50 bags, from supplier"
        result = self.parser.parse_batch_entries(text, self.user_id, self.user_name)
    
        assert result.format == BatchFormat.SINGLE
        assert result.is_valid is True
        assert result.total_entries == 1
        assert result.valid_entries == 1
        assert len(result.movements) == 1
        
        movement = result.movements[0]
        assert movement.item_name == "cement"
        assert movement.quantity == 50.0
        assert movement.unit == "bag"
        assert movement.movement_type == MovementType.IN
        assert movement.from_location == "supplier"
    
    def test_newline_batch_parsing(self):
        """Test parsing of newline-separated batch."""
        text = """in project: Bridge Construction, cement, 50 bags, from supplier
    steel bars, 100 pieces, from warehouse
    safety equipment, 20 sets, from office"""
    
        result = self.parser.parse_batch_entries(text, self.user_id, self.user_name)
    
        assert result.format == BatchFormat.NEWLINE
        assert result.is_valid is True
        assert result.total_entries == 3
        assert result.valid_entries == 3
        assert len(result.movements) == 3
        
        # Check first movement
        assert result.movements[0].item_name == "cement"
        assert result.movements[0].quantity == 50.0
        
        # Check second movement
        assert result.movements[1].item_name == "steel bars"
        assert result.movements[1].quantity == 100.0
        
        # Check third movement
        assert result.movements[2].item_name == "safety equipment"
        assert result.movements[2].quantity == 20.0
    
    def test_semicolon_batch_parsing(self):
        """Test parsing of semicolon-separated batch."""
        text = "in project: Bridge Construction, cement, 50 bags, from supplier; steel bars, 100 pieces, from warehouse"
    
        result = self.parser.parse_batch_entries(text, self.user_id, self.user_name)
    
        assert result.format == BatchFormat.SEMICOLON
        assert result.is_valid is True
        assert result.total_entries == 2
        assert result.valid_entries == 2
        assert len(result.movements) == 2
    
    def test_mixed_format_parsing(self):
        """Test parsing of mixed format batch."""
        text = """in project: Bridge Construction, cement, 50 bags, from supplier
    steel bars, 100 pieces, from warehouse; safety equipment, 20 sets, from office"""
    
        result = self.parser.parse_batch_entries(text, self.user_id, self.user_name)
    
        assert result.format == BatchFormat.MIXED
        assert result.is_valid is True
        assert result.total_entries == 3
        assert result.valid_entries == 3
        assert len(result.movements) == 3
    
    def test_batch_size_limit(self):
        """Test that batch size limit is enforced."""
        # Create a batch with 41 entries (exceeds limit of 40)
        entries = []
        for i in range(41):
            entries.append(f"item{i}, {i+1} pieces")
        
        text = "in project: Bridge Construction, " + "\n".join(entries)
        result = self.parser.parse_batch_entries(text, self.user_id, self.user_name)
        
        assert result.is_valid is False
        assert "exceeds maximum limit of 40" in result.errors[0]
    
    def test_movement_type_consistency(self):
        """Test that all entries in a batch have the same movement type."""
        text = """in project: Bridge Construction, cement, 50 bags, from supplier
out project: Bridge Construction, steel bars, 100 pieces, to warehouse"""
        
        result = self.parser.parse_batch_entries(text, self.user_id, self.user_name)
        
        assert result.is_valid is False
        assert any("Movement type" in error for error in result.errors)
    
    def test_required_fields_validation(self):
        """Test validation of required fields in batch entries."""
        text = """in project: Bridge Construction, cement, 50 bags, from supplier
steel bars, from warehouse
safety equipment, 20 sets, from office"""
        
        result = self.parser.parse_batch_entries(text, self.user_id, self.user_name)
        
        assert result.is_valid is False
        assert result.valid_entries == 2  # First and third entries are valid
        assert result.total_entries == 3
        assert len(result.errors) > 0


class TestBackwardCompatibility:
    """Test that existing single-entry functionality still works."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = NLPStockParser()
        self.user_id = 12345
        self.user_name = "Test User"
    
    def test_single_in_command(self):
        """Test single /in command still works."""
        text = "/in project: Bridge Construction, cement, 50 bags, from supplier"
        movement = self.parser.parse_stock_command(text, self.user_id, self.user_name)
        
        assert movement is not None
        assert movement.item_name == "cement"
        assert movement.quantity == 50.0
        assert movement.movement_type == MovementType.IN
    
    def test_single_out_command(self):
        """Test single /out command still works."""
        text = "/out project: Bridge Construction, steel bars, 100 pieces, to warehouse"
        movement = self.parser.parse_stock_command(text, self.user_id, self.user_name)
        
        assert movement is not None
        assert movement.item_name == "steel bars"
        assert movement.quantity == 100.0
        assert movement.movement_type == MovementType.OUT
    
    def test_single_adjust_command(self):
        """Test single /adjust command still works."""
        text = "/adjust project: Bridge Construction, safety equipment, -5 sets"
        movement = self.parser.parse_stock_command(text, self.user_id, self.user_name)
        
        assert movement is not None
        assert movement.item_name == "safety equipment"
        assert movement.quantity == -5.0
        assert movement.movement_type == MovementType.ADJUST


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = NLPStockParser()
        self.user_id = 12345
        self.user_name = "Test User"
    
    def test_empty_text(self):
        """Test handling of empty text."""
        text = ""
        result = self.parser.parse_batch_entries(text, self.user_id, self.user_name)
        
        assert result.is_valid is False
        assert "Could not determine movement type" in result.errors[0]
    
    def test_whitespace_only(self):
        """Test handling of whitespace-only text."""
        text = "   \n   \t   "
        result = self.parser.parse_batch_entries(text, self.user_id, self.user_name)
        
        assert result.is_valid is False
    
    def test_malformed_entries(self):
        """Test handling of malformed entries in batch."""
        text = """in project: Bridge Construction, cement, 50 bags, from supplier
invalid entry
steel bars, 100 pieces, from warehouse"""
        
        result = self.parser.parse_batch_entries(text, self.user_id, self.user_name)
        
        assert result.is_valid is False
        assert result.valid_entries == 2
        assert result.total_entries == 3
        assert len(result.errors) > 0
    
    def test_mixed_separators_in_single_line(self):
        """Test handling of mixed separators in a single line."""
        text = "in project: Bridge Construction, cement, 50 bags; steel bars, 100 pieces, from warehouse"
        
        result = self.parser.parse_batch_entries(text, self.user_id, self.user_name)
        
        assert result.format == BatchFormat.SEMICOLON
        assert result.is_valid is True
        assert result.total_entries == 2


class TestPerformance:
    """Test performance with maximum batch sizes."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = NLPStockParser()
        self.user_id = 12345
        self.user_name = "Test User"
    
    def test_maximum_batch_size_performance(self):
        """Test performance with maximum allowed batch size."""
        # Create a batch with exactly 40 entries
        entries = []
        for i in range(40):
            entries.append(f"item{i}, {i+1} pieces, from warehouse")
        
        text = "in project: Bridge Construction, " + "\n".join(entries)
        
        # Measure parsing time
        import time
        start_time = time.time()
        result = self.parser.parse_batch_entries(text, self.user_id, self.user_name)
        end_time = time.time()
        
        parsing_time = end_time - start_time
        
        assert result.is_valid is True
        assert result.total_entries == 40
        assert result.valid_entries == 40
        assert parsing_time < 1.0  # Should complete within 1 second


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
