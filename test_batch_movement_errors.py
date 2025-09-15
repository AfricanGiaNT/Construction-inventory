"""Tests for batch movement error handling."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.batch_movement_processor import BatchMovementProcessor
from src.schemas import MovementType, BatchResult, BatchError, BatchErrorType


class TestBatchMovementErrors:
    """Test error handling in batch movement processing."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_airtable = MagicMock()
        self.mock_settings = MagicMock()
        self.mock_stock_service = MagicMock()
        
        self.processor = BatchMovementProcessor(
            airtable_client=self.mock_airtable,
            settings=self.mock_settings,
            stock_service=self.mock_stock_service
        )
    
    @pytest.mark.asyncio
    async def test_database_connection_error(self):
        """Test handling of database connection errors."""
        command = """project: test, driver: test driver
Test item, 10"""
        
        # Mock stock service to raise database connection error
        self.mock_stock_service.stock_in = AsyncMock(
            side_effect=Exception("Database connection failed")
        )
        
        result = await self.processor.process_batch_command(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        assert result.successful_entries == 0
        assert result.failed_entries == 1
        assert result.success_rate == 0.0
        assert len(result.errors) == 1
        assert result.errors[0].error_type == BatchErrorType.DATABASE
        assert "Error processing Test item" in result.errors[0].message
        assert result.errors[0].severity == "ERROR"
    
    @pytest.mark.asyncio
    async def test_item_not_found_error(self):
        """Test handling of item not found errors."""
        command = """project: test, driver: test driver
Non-existent item, 10"""
        
        # Mock stock service to return item not found error
        self.mock_stock_service.stock_in = AsyncMock(
            return_value=(False, "Item not found in database", 0.0, 0.0)
        )
        
        result = await self.processor.process_batch_command(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        assert result.successful_entries == 0
        assert result.failed_entries == 1
        assert result.success_rate == 0.0
        assert len(result.errors) == 1
        assert result.errors[0].error_type == BatchErrorType.DATABASE
        assert "Failed to process Non-existent item" in result.errors[0].message
        assert "Item not found in database" in result.errors[0].message
    
    @pytest.mark.asyncio
    async def test_insufficient_stock_error(self):
        """Test handling of insufficient stock errors for /out commands."""
        command = """project: test, driver: test driver, to: test location
Test item, 100"""
        
        # Mock stock service to return insufficient stock error
        self.mock_stock_service.stock_out = AsyncMock(
            return_value=(False, "Insufficient stock available", 5.0, 5.0)
        )
        
        result = await self.processor.process_batch_command(
            command, MovementType.OUT, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        assert result.successful_entries == 0
        assert result.failed_entries == 1
        assert result.success_rate == 0.0
        assert len(result.errors) == 1
        assert result.errors[0].error_type == BatchErrorType.DATABASE
        assert "Failed to process Test item" in result.errors[0].message
        assert "Insufficient stock available" in result.errors[0].message
    
    @pytest.mark.asyncio
    async def test_validation_error_in_batch(self):
        """Test handling of validation errors in batch."""
        command = """project: test, driver: test driver
, 10
Valid item, 5"""
        
        result = await self.processor.process_batch_command(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        assert result.successful_entries == 0
        assert result.failed_entries == 0
        assert result.success_rate == 0.0
        assert len(result.errors) == 1
        assert result.errors[0].error_type == BatchErrorType.VALIDATION
        assert "Item name is required" in result.errors[0].message
    
    @pytest.mark.asyncio
    async def test_malformed_command_error(self):
        """Test handling of malformed command errors."""
        command = """invalid command without proper format"""
        
        result = await self.processor.process_batch_command(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        assert result.successful_entries == 0
        assert result.failed_entries == 0
        assert result.success_rate == 0.0
        assert len(result.errors) == 1
        assert result.errors[0].error_type == BatchErrorType.PARSING
        assert "Failed to parse command" in result.errors[0].message
        assert result.errors[0].severity == "ERROR"
    
    @pytest.mark.asyncio
    async def test_empty_batch_error(self):
        """Test handling of empty batch errors."""
        command = """project: test, driver: test driver"""
        
        result = await self.processor.process_batch_command(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        assert result.successful_entries == 0
        assert result.failed_entries == 0
        assert result.success_rate == 0.0
        assert len(result.errors) == 1
        assert result.errors[0].error_type == BatchErrorType.VALIDATION
        assert "No items found" in result.errors[0].message
    
    @pytest.mark.asyncio
    async def test_mixed_errors_in_multiple_batches(self):
        """Test handling of mixed errors across multiple batches."""
        command = """-batch 1-
project: test1, driver: driver1
Valid item, 10

-batch 2-
project: test2, driver: driver2
Invalid item, 5
Another valid item, 3

-batch 3-
project: test3, driver: driver3
, 2"""
        
        # Mock stock service responses
        def mock_stock_in(item_name, **kwargs):
            if item_name == "Invalid item":
                return (False, "Item not found", 0.0, 0.0)
            return (True, "Success", 0.0, 10.0)
        
        self.mock_stock_service.stock_in = AsyncMock(side_effect=mock_stock_in)
        
        result = await self.processor.process_batch_command(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        assert result.successful_entries == 2  # Valid item and Another valid item
        assert result.failed_entries == 2  # Invalid item and empty name item
        assert result.success_rate == 50.0  # 2/4 * 100
        assert len(result.errors) == 2  # One for Invalid item, one for validation
        assert any("Failed to process Invalid item" in error.message for error in result.errors)
        assert any("Item name is required" in error.message for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_critical_error_handling(self):
        """Test handling of critical errors."""
        command = """project: test, driver: test driver
Test item, 10"""
        
        # Mock stock service to raise critical error
        self.mock_stock_service.stock_in = AsyncMock(
            side_effect=Exception("Critical system failure")
        )
        
        result = await self.processor.process_batch_command(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        assert result.successful_entries == 0
        assert result.failed_entries == 1
        assert result.success_rate == 0.0
        assert len(result.errors) == 1
        assert result.errors[0].error_type == BatchErrorType.DATABASE
        assert "Error processing Test item" in result.errors[0].message
        assert "Critical system failure" in result.errors[0].message
        assert result.errors[0].severity == "ERROR"
    
    @pytest.mark.asyncio
    async def test_network_timeout_error(self):
        """Test handling of network timeout errors."""
        command = """project: test, driver: test driver
Test item, 10"""
        
        # Mock stock service to raise timeout error
        self.mock_stock_service.stock_in = AsyncMock(
            side_effect=Exception("Network timeout")
        )
        
        result = await self.processor.process_batch_command(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        assert result.successful_entries == 0
        assert result.failed_entries == 1
        assert result.success_rate == 0.0
        assert len(result.errors) == 1
        assert result.errors[0].error_type == BatchErrorType.DATABASE
        assert "Error processing Test item" in result.errors[0].message
        assert "Network timeout" in result.errors[0].message
    
    @pytest.mark.asyncio
    async def test_airtable_api_error(self):
        """Test handling of Airtable API errors."""
        command = """project: test, driver: test driver
Test item, 10"""
        
        # Mock stock service to return Airtable API error
        self.mock_stock_service.stock_in = AsyncMock(
            return_value=(False, "Airtable API rate limit exceeded", 0.0, 0.0)
        )
        
        result = await self.processor.process_batch_command(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        assert result.successful_entries == 0
        assert result.failed_entries == 1
        assert result.success_rate == 0.0
        assert len(result.errors) == 1
        assert result.errors[0].error_type == BatchErrorType.DATABASE
        assert "Failed to process Test item" in result.errors[0].message
        assert "Airtable API rate limit exceeded" in result.errors[0].message
    
    @pytest.mark.asyncio
    async def test_rollback_error_handling(self):
        """Test error handling during rollback."""
        movement_ids = ["id1", "id2", "id3"]
        
        # Mock rollback to fail
        with patch.object(self.processor, 'rollback_batch', return_value=False):
            result = await self.processor.rollback_batch(movement_ids)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_processing_time_tracking(self):
        """Test that processing time is tracked correctly."""
        command = """project: test, driver: test driver
Test item, 10"""
        
        # Mock stock service with delay
        async def delayed_stock_in(*args, **kwargs):
            import asyncio
            await asyncio.sleep(0.1)  # 100ms delay
            return (True, "Success", 0.0, 10.0)
        
        self.mock_stock_service.stock_in = AsyncMock(side_effect=delayed_stock_in)
        
        result = await self.processor.process_batch_command(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        assert result.processing_time_seconds > 0.1
        assert result.processing_time_seconds < 1.0  # Should be reasonable
    
    def test_error_severity_levels(self):
        """Test that errors have appropriate severity levels."""
        # Test validation error
        validation_error = BatchError(
            error_type=BatchErrorType.VALIDATION,
            message="Test validation error",
            severity="ERROR"
        )
        assert validation_error.severity == "ERROR"
        
        # Test database error
        database_error = BatchError(
            error_type=BatchErrorType.DATABASE,
            message="Test database error",
            severity="ERROR"
        )
        assert database_error.severity == "ERROR"
        
        # Test parsing error
        parsing_error = BatchError(
            error_type=BatchErrorType.PARSING,
            message="Test parsing error",
            severity="ERROR"
        )
        assert parsing_error.severity == "ERROR"
    
    @pytest.mark.asyncio
    async def test_error_recovery_continues_processing(self):
        """Test that error recovery allows processing to continue."""
        command = """-batch 1-
project: test1, driver: driver1
Failing item, 10

-batch 2-
project: test2, driver: driver2
Working item, 5"""
        
        # Mock stock service to fail on first item, succeed on second
        def mock_stock_in(item_name, **kwargs):
            if item_name == "Failing item":
                return (False, "Item not found", 0.0, 0.0)
            return (True, "Success", 0.0, 5.0)
        
        self.mock_stock_service.stock_in = AsyncMock(side_effect=mock_stock_in)
        
        result = await self.processor.process_batch_command(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        assert result.successful_entries == 1  # Working item
        assert result.failed_entries == 1  # Failing item
        assert result.success_rate == 50.0
        assert len(result.errors) == 1
        assert "Failed to process Failing item" in result.errors[0].message


if __name__ == "__main__":
    pytest.main([__file__])
