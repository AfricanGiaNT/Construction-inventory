"""Tests for the error handling utilities."""

import pytest
from unittest.mock import patch, MagicMock

from src.utils.error_handling import ErrorHandler
from src.schemas import BatchError, BatchErrorType


class TestErrorHandler:
    """Test the ErrorHandler utility class."""

    def test_categorize_error(self):
        """Test error categorization based on message content."""
        # Test validation errors
        validation_result = ErrorHandler.categorize_error("Item not found in database")
        assert validation_result["type"] == BatchErrorType.VALIDATION
        assert "check if the item exists" in validation_result["suggestion"].lower()
        
        # Test database errors
        db_result = ErrorHandler.categorize_error("Database error: connection timeout")
        assert db_result["type"] == BatchErrorType.DATABASE
        assert "problem connecting" in db_result["suggestion"].lower()
        
        # Test parsing errors
        parse_result = ErrorHandler.categorize_error("Could not parse the command format")
        assert parse_result["type"] == BatchErrorType.PARSING
        assert "check syntax" in parse_result["suggestion"].lower()
        
        # Test rollback errors
        rollback_result = ErrorHandler.categorize_error("Rollback operation failed")
        assert rollback_result["type"] == BatchErrorType.ROLLBACK
        assert "manual verification" in rollback_result["suggestion"].lower()
        
        # Test default categorization
        default_result = ErrorHandler.categorize_error("Unknown error type")
        assert default_result["type"] == BatchErrorType.VALIDATION
        assert "check your input" in default_result["suggestion"].lower()

    def test_create_batch_error(self):
        """Test creation of BatchError objects."""
        # Test with explicit parameters
        error = ErrorHandler.create_batch_error(
            message="Test error",
            entry_index=1,
            entry_details="Cement: 5 bags",
            error_type=BatchErrorType.VALIDATION,
            suggestion="Fix this",
            severity="ERROR"
        )
        
        assert error.message == "Test error"
        assert error.entry_index == 1
        assert error.entry_details == "Cement: 5 bags"
        assert error.error_type == BatchErrorType.VALIDATION
        assert error.suggestion == "Fix this"
        assert error.severity == "ERROR"
        
        # Test with auto-categorization
        error = ErrorHandler.create_batch_error(
            message="Item not found in database",
            entry_index=2,
            entry_details="Sand: 10 bags"
        )
        
        assert error.message == "Item not found in database"
        assert error.entry_index == 2
        assert error.entry_details == "Sand: 10 bags"
        assert error.error_type == BatchErrorType.VALIDATION
        assert "check if the item exists" in error.suggestion.lower()
        assert error.severity == "ERROR"

    def test_format_error_message(self):
        """Test formatting of error messages."""
        error = BatchError(
            error_type=BatchErrorType.VALIDATION,
            message="Invalid quantity",
            entry_index=1,
            entry_details="Cement: -5 bags",
            suggestion="Quantity must be positive",
            severity="ERROR"
        )
        
        formatted = ErrorHandler.format_error_message(error)
        assert "Error: Invalid quantity" in formatted
        assert "(Entry: Cement: -5 bags)" in formatted
        assert "Suggestion: Quantity must be positive" in formatted

    def test_format_batch_errors_summary(self):
        """Test formatting of batch error summaries."""
        errors = [
            BatchError(
                error_type=BatchErrorType.VALIDATION,
                message="Invalid quantity",
                entry_index=1,
                entry_details="Cement: -5 bags",
                suggestion="Quantity must be positive",
                severity="ERROR"
            ),
            BatchError(
                error_type=BatchErrorType.VALIDATION,
                message="Item not found",
                entry_index=2,
                entry_details="Unknown item: 10 pieces",
                suggestion="Check item name",
                severity="ERROR"
            ),
            BatchError(
                error_type=BatchErrorType.DATABASE,
                message="Connection timeout",
                entry_index=3,
                entry_details="Steel: 20 bars",
                suggestion="Try again later",
                severity="CRITICAL"
            )
        ]
        
        summary = ErrorHandler.format_batch_errors_summary(errors)
        
        # Check that it contains the error count
        assert "Found 3 error(s)" in summary
        
        # Check that it groups by error type
        assert "2 validation error(s)" in summary
        assert "1 database error(s)" in summary
        
        # Check that it includes examples
        assert "Invalid quantity" in summary
        assert "Item not found" in summary
        assert "Connection timeout" in summary
        
        # Check that it includes suggestions
        assert "Quantity must be positive" in summary or "Check item name" in summary

    def test_get_recovery_suggestion(self):
        """Test generation of recovery suggestions."""
        # Test validation errors
        validation_errors = [
            BatchError(
                error_type=BatchErrorType.VALIDATION,
                message="Invalid quantity",
                entry_index=1,
                suggestion="Quantity must be positive",
                severity="ERROR"
            ),
            BatchError(
                error_type=BatchErrorType.VALIDATION,
                message="Item not found",
                entry_index=2,
                suggestion="Check item name",
                severity="ERROR"
            )
        ]
        
        validation_suggestion = ErrorHandler.get_recovery_suggestion(validation_errors)
        assert "incorrect item names" in validation_suggestion.lower()
        assert "invalid quantities" in validation_suggestion.lower()
        
        # Test database errors
        db_errors = [
            BatchError(
                error_type=BatchErrorType.DATABASE,
                message="Connection timeout",
                entry_index=1,
                suggestion="Try again later",
                severity="CRITICAL"
            )
        ]
        
        db_suggestion = ErrorHandler.get_recovery_suggestion(db_errors)
        assert "database issues detected" in db_suggestion.lower()
        assert "smaller batches" in db_suggestion.lower()
        
        # Test parsing errors
        parse_errors = [
            BatchError(
                error_type=BatchErrorType.PARSING,
                message="Invalid format",
                entry_index=1,
                suggestion="Check syntax",
                severity="ERROR"
            )
        ]
        
        parse_suggestion = ErrorHandler.get_recovery_suggestion(parse_errors)
        assert "command format issues" in parse_suggestion.lower()
        assert "/batchhelp" in parse_suggestion
        
        # Test empty errors
        empty_suggestion = ErrorHandler.get_recovery_suggestion([])
        assert empty_suggestion == ""

