"""Tests for batch movement processing."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.batch_movement_processor import BatchMovementProcessor
from src.schemas import MovementType, BatchResult, BatchError, BatchErrorType


class TestBatchMovementProcessing:
    """Test batch movement processing functionality."""
    
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
    async def test_process_single_batch_in_command(self):
        """Test processing a single batch /in command."""
        command = """project: mzuzu, driver: Dani maliko
Solar floodlight panel FS-SFL800, 4
Solar floodlight 800W, 4"""
        
        # Mock stock service responses
        self.mock_stock_service.stock_in = AsyncMock(return_value=(True, "Success", 0.0, 4.0))
        
        result = await self.processor.process_batch_command(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        assert result.successful_entries == 2
        assert result.failed_entries == 0
        assert result.success_rate == 100.0
        assert len(result.movements_created) == 2
        assert result.errors == []
        assert "Successfully processed 2 items" in result.summary_message
    
    @pytest.mark.asyncio
    async def test_process_single_batch_out_command(self):
        """Test processing a single batch /out command."""
        command = """project: mzuzu, driver: Dani maliko, to: mzuzu houses
Solar floodlight panel FS-SFL800, 4
Solar floodlight 800W, 4"""
        
        # Mock stock service responses
        self.mock_stock_service.stock_out = AsyncMock(return_value=(True, "Success", 4.0, 0.0))
        
        result = await self.processor.process_batch_command(
            command, MovementType.OUT, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        assert result.successful_entries == 2
        assert result.failed_entries == 0
        assert result.success_rate == 100.0
        assert len(result.movements_created) == 2
        assert result.errors == []
    
    @pytest.mark.asyncio
    async def test_process_multiple_batches(self):
        """Test processing multiple batches in one command."""
        command = """-batch 1-
project: mzuzu, driver: Dani maliko, to: mzuzu houses
Solar floodlight panel FS-SFL800, 4

-batch 2-
project: lilongwe, driver: John Banda, to: lilongwe site
Cable 2.5sqmm black 100m, 1
Cable 2.5sqmm green 100m, 1"""
        
        # Mock stock service responses
        self.mock_stock_service.stock_out = AsyncMock(return_value=(True, "Success", 0.0, 0.0))
        
        result = await self.processor.process_batch_command(
            command, MovementType.OUT, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        assert result.successful_entries == 3
        assert result.failed_entries == 0
        assert result.success_rate == 100.0
        assert len(result.movements_created) == 3
        assert "Successfully processed 3 items" in result.summary_message
    
    @pytest.mark.asyncio
    async def test_process_with_stock_service_failures(self):
        """Test processing with some stock service failures."""
        command = """project: test, driver: test driver
Valid item, 10
Invalid item, 5
Another valid item, 3"""
        
        # Mock stock service to fail on "Invalid item"
        def mock_stock_in(item_name, **kwargs):
            if item_name == "Invalid item":
                return (False, "Item not found", 0.0, 0.0)
            return (True, "Success", 0.0, 10.0)
        
        self.mock_stock_service.stock_in = AsyncMock(side_effect=mock_stock_in)
        
        result = await self.processor.process_batch_command(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        # The processor stops processing the batch after the first failure
        assert result.successful_entries == 0  # No items processed due to batch failure
        assert result.failed_entries == 3  # All items failed due to batch failure
        assert result.success_rate == 0.0
        assert len(result.movements_created) == 0
        assert len(result.errors) == 1
        assert "Failed to process Invalid item" in result.errors[0].message
    
    @pytest.mark.asyncio
    async def test_process_invalid_command(self):
        """Test processing an invalid command."""
        command = """invalid command format"""
        
        result = await self.processor.process_batch_command(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        assert result.successful_entries == 0
        assert result.failed_entries == 1  # Empty batch is treated as failed entry
        assert result.success_rate == 0.0
        assert len(result.movements_created) == 0
        assert len(result.errors) == 1
        assert result.errors[0].error_type == BatchErrorType.VALIDATION
        assert "No items found" in result.errors[0].message
    
    @pytest.mark.asyncio
    async def test_process_empty_batch(self):
        """Test processing a command with empty batch."""
        command = """project: test, driver: test driver"""
        
        result = await self.processor.process_batch_command(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        assert result.successful_entries == 0
        assert result.failed_entries == 1  # Empty batch is treated as failed entry
        assert result.success_rate == 0.0
        assert len(result.movements_created) == 0
        assert len(result.errors) == 1
        assert "No items found" in result.errors[0].message
    
    @pytest.mark.asyncio
    async def test_process_with_exception(self):
        """Test processing with unexpected exception."""
        command = """project: test, driver: test driver
Test item, 10"""
        
        # Mock stock service to raise exception
        self.mock_stock_service.stock_in = AsyncMock(side_effect=Exception("Database error"))
        
        result = await self.processor.process_batch_command(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        assert result.successful_entries == 0
        assert result.failed_entries == 1
        assert result.success_rate == 0.0
        assert len(result.movements_created) == 0
        assert len(result.errors) == 1
        assert "Error processing Test item" in result.errors[0].message
    
    @pytest.mark.asyncio
    async def test_process_mixed_success_failure(self):
        """Test processing with mixed success and failure."""
        command = """-batch 1-
project: test1, driver: driver1
Success item, 10

-batch 2-
project: test2, driver: driver2
Failure item, 5
Another success item, 3"""
        
        # Mock stock service responses
        def mock_stock_in(item_name, **kwargs):
            if item_name == "Failure item":
                return (False, "Item not found", 0.0, 0.0)
            return (True, "Success", 0.0, 10.0)
        
        self.mock_stock_service.stock_in = AsyncMock(side_effect=mock_stock_in)
        
        result = await self.processor.process_batch_command(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert isinstance(result, BatchResult)
        assert result.successful_entries == 1  # Only Success item from batch 1
        assert result.failed_entries == 2  # Failure item and Another success item from batch 2
        assert abs(result.success_rate - 33.33) < 0.01  # 1/3 * 100 (floating point precision)
        assert len(result.movements_created) == 1
        assert len(result.errors) == 1
        assert "Processed 1 items successfully, 2 failed" in result.summary_message
    
    def test_validate_batch_command_valid(self):
        """Test validating a valid batch command."""
        command = """project: test, driver: test driver
Test item, 10
Another item, 5"""
        
        is_valid, message, batches = self.processor.validate_batch_command(
            command, MovementType.IN
        )
        
        assert is_valid
        assert message == "Command is valid"
        assert len(batches) == 1
        assert len(batches[0].items) == 2
    
    def test_validate_batch_command_invalid(self):
        """Test validating an invalid batch command."""
        command = """invalid command format"""
        
        is_valid, message, batches = self.processor.validate_batch_command(
            command, MovementType.IN
        )
        
        assert not is_valid
        assert "Validation errors" in message
        assert len(batches) == 1  # Empty batch is created
    
    def test_validate_batch_command_empty_batch(self):
        """Test validating a command with empty batch."""
        command = """project: test, driver: test driver"""
        
        is_valid, message, batches = self.processor.validate_batch_command(
            command, MovementType.IN
        )
        
        assert not is_valid
        assert "Validation errors" in message
        assert len(batches) == 1
    
    def test_get_batch_summary(self):
        """Test getting batch summary."""
        from src.schemas import BatchInfo, BatchItem
        
        batches = [
            BatchInfo(
                batch_number=1,
                project="mzuzu",
                driver="Dani maliko",
                to_location="mzuzu houses",
                items=[
                    BatchItem(item_name="Item 1", quantity=10.0),
                    BatchItem(item_name="Item 2", quantity=5.0)
                ]
            ),
            BatchInfo(
                batch_number=2,
                project="lilongwe",
                driver="John Banda",
                to_location="lilongwe site",
                items=[
                    BatchItem(item_name="Item 3", quantity=3.0)
                ]
            )
        ]
        
        summary = self.processor.get_batch_summary(batches)
        
        assert "Found 2 batch(es):" in summary
        assert "Batch 1: 2 items to mzuzu houses" in summary
        assert "Batch 2: 1 items to lilongwe site" in summary
        assert "Total items: 3" in summary
    
    def test_generate_summary_message_all_success(self):
        """Test generating summary message for all successful entries."""
        message = self.processor._generate_summary_message(5, 0, 2)
        
        assert "Successfully processed 5 items across 2 batch(es)" in message
        assert "✅" in message
    
    def test_generate_summary_message_all_failure(self):
        """Test generating summary message for all failed entries."""
        message = self.processor._generate_summary_message(0, 3, 1)
        
        assert "Failed to process 3 items across 1 batch(es)" in message
        assert "❌" in message
    
    def test_generate_summary_message_mixed(self):
        """Test generating summary message for mixed success/failure."""
        message = self.processor._generate_summary_message(3, 2, 2)
        
        assert "Processed 3 items successfully, 2 failed across 2 batch(es)" in message
        assert "⚠️" in message
    
    def test_generate_summary_message_no_entries(self):
        """Test generating summary message for no entries."""
        message = self.processor._generate_summary_message(0, 0, 0)
        
        assert message == "No entries processed"
    
    @pytest.mark.asyncio
    async def test_rollback_batch(self):
        """Test rollback functionality."""
        movement_ids = ["id1", "id2", "id3"]
        
        result = await self.processor.rollback_batch(movement_ids)
        
        assert result is True  # Currently always returns True


if __name__ == "__main__":
    pytest.main([__file__])
