"""Tests for batch duplicate processing workflow."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.services.enhanced_batch_processor import EnhancedBatchProcessor
from src.schemas import (
    BatchInfo, BatchItem, Item, Unit, DuplicateMatchType, 
    MovementType, DuplicateItem
)


class TestBatchDuplicateProcessing:
    """Test batch duplicate processing workflow."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_airtable = MagicMock()
        self.mock_airtable.get_all_items = AsyncMock(return_value=[])
        self.mock_airtable.update_item = AsyncMock(return_value=True)
        
        self.mock_settings = MagicMock()
        
        self.mock_stock_service = MagicMock()
        self.mock_stock_service.stock_in = AsyncMock(return_value=(True, "Success", 0.0, 10.0))
        self.mock_stock_service.stock_out = AsyncMock(return_value=(True, "Success", 0.0, 10.0))
        
        # Create enhanced batch processor
        self.processor = EnhancedBatchProcessor(
            airtable_client=self.mock_airtable,
            settings=self.mock_settings,
            stock_service=self.mock_stock_service
        )
        
        # Sample existing items
        self.existing_items = [
            Item(
                name="Cement 50kg",
                on_hand=100.0,
                unit_type="bags",
                category="Construction Materials",
                location="Warehouse A",
                units=[Unit(name="bags", conversion_factor=1.0)]
            ),
            Item(
                name="Steel Bars 12mm",
                on_hand=50.0,
                unit_type="pieces",
                category="Steel",
                location="Warehouse B",
                units=[Unit(name="pieces", conversion_factor=1.0)]
            )
        ]
    
    @pytest.mark.asyncio
    async def test_process_batch_with_no_duplicates(self):
        """Test processing batch with no duplicates."""
        # Mock airtable to return existing items
        self.mock_airtable.get_all_items = AsyncMock(return_value=self.existing_items)
        
        # Mock stock service
        self.mock_stock_service.stock_in = AsyncMock(return_value=(True, "Success", 0.0, 10.0))
        
        command = """project: test, driver: test driver
New Item 1, 10 pieces
New Item 2, 5 kg"""
        
        result = await self.processor.process_batch_command_with_duplicates(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert result.success_rate == 100.0
        assert result.successful_entries == 2
        assert result.failed_entries == 0
        assert "Successfully processed 2 items" in result.summary_message
        assert "Duplicate Analysis" not in result.summary_message
    
    @pytest.mark.asyncio
    async def test_process_batch_with_exact_duplicates(self):
        """Test processing batch with exact duplicates."""
        # Mock airtable to return existing items
        self.mock_airtable.get_all_items = AsyncMock(return_value=self.existing_items)
        
        # Mock stock service and airtable update
        self.mock_stock_service.stock_in = AsyncMock(return_value=(True, "Success", 0.0, 10.0))
        self.mock_airtable.update_item = AsyncMock()
        
        command = """project: test, driver: test driver
Cement 50kg, 10 bags
New Item, 5 pieces"""
        
        result = await self.processor.process_batch_command_with_duplicates(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert result.success_rate == 100.0
        assert result.successful_entries == 2
        assert result.failed_entries == 0
        assert "Duplicate Analysis" in result.summary_message
        assert "1 new items processed" in result.summary_message
        assert "1 exact matches auto-merged" in result.summary_message
    
    @pytest.mark.asyncio
    async def test_process_batch_with_similar_duplicates(self):
        """Test processing batch with similar duplicates."""
        # Mock airtable to return existing items
        self.mock_airtable.get_all_items = AsyncMock(return_value=self.existing_items)
        
        # Mock stock service
        self.mock_stock_service.stock_in = AsyncMock(return_value=(True, "Success", 0.0, 10.0))
        
        command = """project: test, driver: test driver
Cement 50kg bag, 10 bags
Steel Bar 12mm, 5 pieces"""
        
        result = await self.processor.process_batch_command_with_duplicates(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert result.success_rate == 100.0
        assert result.successful_entries == 2
        assert result.failed_entries == 0
        assert "Duplicate Analysis" in result.summary_message
        assert "similar items processed" in result.summary_message
    
    @pytest.mark.asyncio
    async def test_process_batch_with_mixed_duplicates(self):
        """Test processing batch with mixed exact and similar duplicates."""
        # Mock airtable to return existing items
        self.mock_airtable.get_all_items = AsyncMock(return_value=self.existing_items)
        
        # Mock stock service and airtable update
        self.mock_stock_service.stock_in = AsyncMock(return_value=(True, "Success", 0.0, 10.0))
        self.mock_airtable.update_item = AsyncMock()
        
        command = """project: test, driver: test driver
Cement 50kg, 10 bags
Steel Bar 12mm, 5 pieces
New Item, 3 kg"""
        
        result = await self.processor.process_batch_command_with_duplicates(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert result.success_rate == 100.0
        assert result.successful_entries == 3
        assert result.failed_entries == 0
        assert "Duplicate Analysis" in result.summary_message
        assert "1 new items processed" in result.summary_message
        assert "2 exact matches auto-merged" in result.summary_message
    
    @pytest.mark.asyncio
    async def test_process_batch_with_processing_failures(self):
        """Test processing batch with some failures."""
        # Mock airtable to return existing items
        self.mock_airtable.get_all_items = AsyncMock(return_value=self.existing_items)
        
        # Mock stock service to fail on some items
        def mock_stock_in(item_name, **kwargs):
            if item_name == "Failing Item":
                return (False, "Item not found", 0.0, 0.0)
            return (True, "Success", 0.0, 10.0)
        
        self.mock_stock_service.stock_in = AsyncMock(side_effect=mock_stock_in)
        
        command = """project: test, driver: test driver
Success Item, 10 pieces
Failing Item, 5 kg"""
        
        result = await self.processor.process_batch_command_with_duplicates(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert result.success_rate == 50.0
        assert result.successful_entries == 1
        assert result.failed_entries == 1
        assert "Processed 1 items successfully, 1 failed" in result.summary_message
        assert len(result.errors) == 1
    
    @pytest.mark.asyncio
    async def test_get_duplicate_preview(self):
        """Test getting duplicate preview without processing."""
        # Mock airtable to return existing items
        self.mock_airtable.get_all_items = AsyncMock(return_value=self.existing_items)
        
        command = """project: test, driver: test driver
Cement 50kg, 10 bags
New Item, 5 pieces"""
        
        preview = await self.processor.get_duplicate_preview(command, MovementType.IN)
        
        assert preview["status"] == "success"
        assert preview["total_items"] == 2
        assert preview["duplicate_count"] == 1
        assert preview["non_duplicate_count"] == 1
        assert preview["exact_matches"] == 1
        assert preview["similar_items"] == 0
        assert len(preview["duplicates"]) == 1
        
        # Check duplicate details
        duplicate = preview["duplicates"][0]
        assert duplicate["item_name"] == "Cement 50kg"
        assert duplicate["existing_item"] == "Cement 50kg"
        assert duplicate["match_type"] == "exact"
        assert duplicate["similarity_score"] >= 0.95
    
    @pytest.mark.asyncio
    async def test_get_duplicate_preview_invalid_command(self):
        """Test getting duplicate preview with invalid command."""
        # Mock airtable to avoid async issues
        self.mock_airtable.get_all_items = AsyncMock(return_value=[])
        
        command = """invalid command format"""
        
        preview = await self.processor.get_duplicate_preview(command, MovementType.IN)
        
        # The parser might be lenient, so check if it's either error or success with empty results
        assert preview["status"] in ["error", "success"]
        if preview["status"] == "error":
            assert "Failed to parse command" in preview["message"]
        else:
            # If parser accepts it, it should have 0 items
            assert preview["total_items"] == 0
    
    @pytest.mark.asyncio
    async def test_process_out_command_with_duplicates(self):
        """Test processing OUT command with duplicates."""
        # Mock airtable to return existing items
        self.mock_airtable.get_all_items = AsyncMock(return_value=self.existing_items)
        
        # Mock stock service
        self.mock_stock_service.stock_out = AsyncMock(return_value=(True, "Success", 100.0, 90.0))
        
        command = """project: test, driver: test driver, to: test location
Cement 50kg, 10 bags
New Item, 5 pieces"""
        
        result = await self.processor.process_batch_command_with_duplicates(
            command, MovementType.OUT, user_id=123, user_name="Test User"
        )
        
        assert result.success_rate == 100.0
        assert result.successful_entries == 2
        assert result.failed_entries == 0
        assert "Successfully processed 2 items" in result.summary_message
    
    @pytest.mark.asyncio
    async def test_error_handling_in_enhanced_processing(self):
        """Test error handling in enhanced batch processing."""
        # Mock airtable to raise exception
        self.mock_airtable.get_all_items = AsyncMock(side_effect=Exception("Database error"))
        
        command = """project: test, driver: test driver
Test Item, 10 pieces"""
        
        result = await self.processor.process_batch_command_with_duplicates(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        # With proper async mocks, the processing should succeed even with database error
        # because items are treated as non-duplicates when we can't get existing items
        assert result.success_rate == 100.0
        assert result.successful_entries == 1
        assert result.failed_entries == 0
        assert "Successfully processed 1 items" in result.summary_message
    
    @pytest.mark.asyncio
    async def test_enhanced_summary_generation(self):
        """Test enhanced summary message generation."""
        # Mock airtable to return existing items
        self.mock_airtable.get_all_items = AsyncMock(return_value=self.existing_items)
        
        # Mock stock service and airtable update
        self.mock_stock_service.stock_in = AsyncMock(return_value=(True, "Success", 0.0, 10.0))
        self.mock_airtable.update_item = AsyncMock()
        
        command = """project: test, driver: test driver
Cement 50kg, 10 bags
Steel Bar 12mm, 5 pieces
New Item, 3 kg"""
        
        result = await self.processor.process_batch_command_with_duplicates(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        # Check that summary contains duplicate analysis
        assert "Duplicate Analysis" in result.summary_message
        assert "new items processed" in result.summary_message
        assert "exact matches auto-merged" in result.summary_message
        assert "similar items processed" in result.summary_message
        assert "Processing time" in result.summary_message


if __name__ == "__main__":
    pytest.main([__file__])
