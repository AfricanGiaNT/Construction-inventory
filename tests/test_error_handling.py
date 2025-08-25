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
        error_type, suggestion = ErrorHandler.categorize_error("Item not found")
        assert error_type == BatchErrorType.VALIDATION
        assert "verify your input" in suggestion.lower()
        
        # Test database errors
        error_type, suggestion = ErrorHandler.categorize_error("Database error: connection timeout")
        assert error_type == BatchErrorType.DATABASE
        assert "try again later" in suggestion.lower()
        
        # Test parsing errors
        error_type, suggestion = ErrorHandler.categorize_error("Could not parse the command format")
        assert error_type == BatchErrorType.PARSING
        assert "check the format" in suggestion.lower()
        
        # Test rollback errors
        error_type, suggestion = ErrorHandler.categorize_error("Rollback operation failed")
        assert error_type == BatchErrorType.ROLLBACK
        assert "check inventory" in suggestion.lower()
        
        # Test default categorization
        error_type, suggestion = ErrorHandler.categorize_error("Unknown error type")
        assert error_type == BatchErrorType.VALIDATION
        assert "verify your input" in suggestion.lower()

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
            message="Item not found",
            entry_index=2,
            entry_details="Sand: 10 bags"
        )
        
        assert error.message == "Item not found"
        assert error.entry_index == 2
        assert error.entry_details == "Sand: 10 bags"
        assert error.error_type == BatchErrorType.VALIDATION
        assert "verify your input" in error.suggestion.lower()
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
        assert "Entry #2: Invalid quantity (Cement: -5 bags) Suggestion: Quantity must be positive" in formatted

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
                entry_details="Database error",
                suggestion="Try again later",
                severity="ERROR"
            )
        ]
        
        summary = ErrorHandler.format_batch_errors_summary(errors)
        assert "Validation errors: 2" in summary
        assert "Database errors: 1" in summary
        
        # The summary only contains error counts, not detailed messages
        # Check that it doesn't contain the actual error messages
        assert "Invalid quantity" not in summary
        assert "Item not found" not in summary
        assert "Connection timeout" not in summary

    def test_get_recovery_suggestion(self):
        """Test recovery suggestion generation."""
        # Test validation errors
        validation_errors = [
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
            )
        ]
        
        validation_suggestion = ErrorHandler.get_recovery_suggestion(validation_errors)
        assert "check your input data" in validation_suggestion.lower()
        
        # Test database errors
        db_errors = [
            BatchError(
                error_type=BatchErrorType.DATABASE,
                message="Connection timeout",
                entry_index=1,
                entry_details="Database error",
                suggestion="Try again later",
                severity="ERROR"
            )
        ]
        
        db_suggestion = ErrorHandler.get_recovery_suggestion(db_errors)
        assert "database connection issues" in db_suggestion.lower()
        
        # Test parsing errors
        parse_errors = [
            BatchError(
                error_type=BatchErrorType.PARSING,
                message="Invalid format",
                entry_index=1,
                entry_details="Command syntax error",
                suggestion="Check syntax",
                severity="ERROR"
            )
        ]
        
        parse_suggestion = ErrorHandler.get_recovery_suggestion(parse_errors)
        assert "format of your command" in parse_suggestion.lower()
        
        # Test empty errors
        empty_suggestion = ErrorHandler.get_recovery_suggestion([])
        assert empty_suggestion == ""

