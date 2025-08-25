"""Error handling utilities for batch processing."""

from typing import List, Optional, Dict, Any

try:
    from ..schemas import BatchError, BatchErrorType
except ImportError:
    from schemas import BatchError, BatchErrorType


class ErrorHandler:
    """Utility class for handling batch processing errors."""
    
    @staticmethod
    def categorize_error(error_message: str) -> tuple[BatchErrorType, Optional[str]]:
        """Categorize an error message and provide a generic suggestion."""
        error_message = error_message.lower()
        
        # Database errors
        if any(keyword in error_message for keyword in 
              ['database', 'airtable', 'connection', 'timeout', 'rate limit']):
            return BatchErrorType.DATABASE, "Please try again later or with fewer items."
        
        # Rollback errors
        elif any(keyword in error_message for keyword in 
                ['rollback', 'revert', 'undo']):
            return BatchErrorType.ROLLBACK, "Some operations could not be undone. Please check inventory."
        
        # Parsing errors
        elif any(keyword in error_message for keyword in 
                ['parse', 'format', 'syntax', 'invalid input']):
            return BatchErrorType.PARSING, "Check the format of your command."
        
        # Default to validation error
        else:
            return BatchErrorType.VALIDATION, "Please verify your input and try again."
    
    @staticmethod
    def create_batch_error(
        message: str,
        error_type: Optional[BatchErrorType] = None,
        entry_index: Optional[int] = None,
        entry_details: Optional[str] = None,
        suggestion: Optional[str] = None,
        severity: str = "ERROR"
    ) -> BatchError:
        """Create a BatchError with automatic categorization if type not provided."""
        if error_type is None:
            error_type, auto_suggestion = ErrorHandler.categorize_error(message)
            if suggestion is None:
                suggestion = auto_suggestion
        
        return BatchError(
            error_type=error_type,
            message=message,
            entry_index=entry_index,
            entry_details=entry_details,
            suggestion=suggestion,
            severity=severity
        )
    
    @staticmethod
    def format_error_message(error: BatchError) -> str:
        """Format a single BatchError into a user-friendly string."""
        parts = []
        
        # Add entry index if available
        if error.entry_index is not None:
            parts.append(f"Entry #{error.entry_index + 1}:")
        
        # Add error message
        parts.append(error.message)
        
        # Add entry details if available
        if error.entry_details:
            parts.append(f"({error.entry_details})")
        
        # Add suggestion if available
        if error.suggestion:
            parts.append(f"Suggestion: {error.suggestion}")
        
        return " ".join(parts)
    
    @staticmethod
    def format_batch_errors_summary(errors: List[BatchError]) -> str:
        """Format a list of BatchError objects into a concise summary."""
        if not errors:
            return "No errors."
        
        # Group errors by type
        errors_by_type: Dict[BatchErrorType, List[BatchError]] = {}
        for error in errors:
            if error.error_type not in errors_by_type:
                errors_by_type[error.error_type] = []
            errors_by_type[error.error_type].append(error)
        
        summary_parts = []
        for error_type, type_errors in errors_by_type.items():
            summary_parts.append(f"{error_type.value.title()} errors: {len(type_errors)}")
        
        return ", ".join(summary_parts)
    
    @staticmethod
    def get_recovery_suggestion(errors: List[BatchError]) -> str:
        """Provide overall recovery advice based on error types."""
        if not errors:
            return ""
        
        # Count error types
        error_types = {}
        for error in errors:
            if error.error_type not in error_types:
                error_types[error.error_type] = 0
            error_types[error.error_type] += 1
        
        # Provide appropriate suggestion based on predominant error type
        if BatchErrorType.DATABASE in error_types and error_types[BatchErrorType.DATABASE] > 0:
            return "There were database connection issues. Try again later or with fewer items."
        
        elif BatchErrorType.ROLLBACK in error_types and error_types[BatchErrorType.ROLLBACK] > 0:
            return "Some operations could not be undone. Please verify your inventory for consistency."
        
        elif BatchErrorType.PARSING in error_types and error_types[BatchErrorType.PARSING] > 0:
            return "There were issues with the format of your command. Check syntax and try again."
        
        elif BatchErrorType.VALIDATION in error_types and error_types[BatchErrorType.VALIDATION] > 0:
            return "Please check your input data and ensure all required fields are provided correctly."
        
        return "Please review the errors and try again."
