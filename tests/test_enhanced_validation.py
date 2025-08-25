"""Tests for enhanced batch validation and error handling."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, UTC

from src.nlp_parser import NLPStockParser
from src.schemas import (
    BatchFormat, BatchParseResult, BatchError, BatchErrorType,
    StockMovement, MovementType, MovementStatus
)


class TestEnhancedValidation:
    """Test enhanced validation for batch operations."""

    def setup_method(self):
        """Set up test environment."""
        self.parser = NLPStockParser()
        self.user_id = 123456
        self.user_name = "Test User"

    def test_batch_size_limit_validation(self):
        """Test validation of batch size limits with enhanced error messages."""
        # Create a batch with more than the maximum allowed entries
        max_size = self.parser.max_batch_size
        entries = [f"item{i}, 1 piece" for i in range(max_size + 5)]
        batch_text = "/in project: Bridge Construction, " + "\n".join(entries)
        
        result = self.parser.parse_batch_entries(batch_text, self.user_id, self.user_name)
        
        assert not result.is_valid
        assert result.total_entries == max_size + 5
        assert result.valid_entries == 0
        assert len(result.errors) >= 1
        assert any("exceeds maximum limit" in error for error in result.errors)
        assert any("split into smaller batches" in error for error in result.errors)

    def test_movement_type_consistency_validation(self):
        """Test validation of movement type consistency with enhanced error messages."""
        batch_text = "/in project: Bridge Construction, cement, 5 bags\nout project: Bridge Construction, sand, 10 bags"
        
        result = self.parser.parse_batch_entries(batch_text, self.user_id, self.user_name)
        
        assert not result.is_valid
        assert len(result.errors) >= 1
        assert any("differs from first entry type" in error for error in result.errors)
        assert any("All entries must" in error for error in result.errors)

    def test_missing_required_fields_validation(self):
        """Test validation of required fields with enhanced error messages."""
        # Missing quantity
        batch_text = "/in project: Bridge Construction, cement\nsand"
        
        result = self.parser.parse_batch_entries(batch_text, self.user_id, self.user_name)
        
        assert not result.is_valid
        assert len(result.errors) >= 1
        assert any("Could not parse" in error for error in result.errors)
        assert any("Check format" in error for error in result.errors)

    def test_negative_quantity_validation(self):
        """Test validation of negative quantities with enhanced error messages."""
        # Negative quantity for IN movement (should fail)
        batch_text = "/in project: Bridge Construction, cement, -5 bags"
        
        result = self.parser.parse_batch_entries(batch_text, self.user_id, self.user_name)
        
        # The parser should create a movement, but validation should fail
        assert not result.is_valid
        assert len(result.errors) >= 1
        assert any("Quantity must be positive" in error for error in result.errors)
        
        # Negative quantity for ADJUST movement (should pass)
        batch_text = "/adjust project: Bridge Construction, cement, -5 bags"
        
        result = self.parser.parse_batch_entries(batch_text, self.user_id, self.user_name)
        
        # ADJUST can have negative quantities
        assert result.is_valid
        assert len(result.movements) == 1
        assert result.movements[0].quantity == -5

    def test_large_quantity_warning(self):
        """Test warning for unusually large quantities."""
        batch_text = "/in project: Bridge Construction, cement, 50000 bags"
        
        result = self.parser.parse_batch_entries(batch_text, self.user_id, self.user_name)
        
        # The parser should create a movement, but validation should warn
        assert not result.is_valid
        assert len(result.errors) >= 1
        assert any("Very large quantity detected" in error for error in result.errors)
        assert any("verify this is correct" in error for error in result.errors)

    def test_duplicate_items_warning(self):
        """Test warning for duplicate items in a batch."""
        batch_text = "/in project: Bridge Construction, cement, 5 bags\ncement, 10 bags\nsand, 20 bags"
        
        result = self.parser.parse_batch_entries(batch_text, self.user_id, self.user_name)
        
        # The parser should create movements, but validation should warn
        assert not result.is_valid
        assert len(result.movements) == 3
        assert len(result.errors) >= 1
        assert any("Item 'cement' appears 2 times" in error for error in result.errors)
        assert any("combining these entries" in error for error in result.errors)

    def test_format_specific_guidance(self):
        """Test that format-specific guidance is provided in error messages."""
        # Test newline format guidance
        batch_text = "/in project: Bridge Construction, cement, bags\nsand, bags"
        
        result = self.parser.parse_batch_entries(batch_text, self.user_id, self.user_name)
        
        assert not result.is_valid
        assert any("For newline format" in error for error in result.errors)
        
        # Test semicolon format guidance
        batch_text = "/in project: Bridge Construction, cement, bags; sand, bags"
        
        result = self.parser.parse_batch_entries(batch_text, self.user_id, self.user_name)
        
        assert not result.is_valid
        assert any("For semicolon format" in error for error in result.errors)
        
        # Test mixed format guidance
        batch_text = "/in project: Bridge Construction, cement, bags; sand, bags\nbricks, 10 pieces"
        
        result = self.parser.parse_batch_entries(batch_text, self.user_id, self.user_name)
        
        assert not result.is_valid
        assert any("For clearer batch commands" in error for error in result.errors)
        assert any("not mixed format" in error for error in result.errors)

    def test_helpful_error_messages(self):
        """Test that error messages are helpful and actionable."""
        # Test missing movement type
        batch_text = "cement, 5 bags\nsand, 10 bags"
        
        result = self.parser.parse_batch_entries(batch_text, self.user_id, self.user_name)
        
        assert not result.is_valid
        assert any("Could not determine movement type" in error for error in result.errors)
        assert any("Please start with /in, /out, or /adjust" in error for error in result.errors)
        
        # Test no valid entries
        batch_text = "/in project: Bridge Construction, ,,,,"
        
        result = self.parser.parse_batch_entries(batch_text, self.user_id, self.user_name)
        
        assert not result.is_valid
        assert any("No valid entries found" in error for error in result.errors)
        assert any("check the format" in error for error in result.errors)

    def test_catastrophic_error_handling(self):
        """Test handling of catastrophic errors with helpful messages."""
        with patch.object(self.parser, '_split_batch_entries', side_effect=Exception("Simulated catastrophic error")):
            batch_text = "/in project: Bridge Construction, cement, 5 bags"
            
            result = self.parser.parse_batch_entries(batch_text, self.user_id, self.user_name)
            
            assert not result.is_valid
            assert len(result.errors) >= 2
            assert any("Error parsing batch: Simulated catastrophic error" in error for error in result.errors)
            assert any("check your command format" in error.lower() for error in result.errors)
            assert any("/batchhelp" in error for error in result.errors)

