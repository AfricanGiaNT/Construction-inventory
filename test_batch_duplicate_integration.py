"""Integration tests for batch duplicate handling workflow."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.enhanced_batch_processor import EnhancedBatchProcessor
from src.services.batch_duplicate_handler import BatchDuplicateHandler
from src.schemas import (
    BatchInfo, BatchItem, Item, Unit, DuplicateMatchType, 
    MovementType, DuplicateItem, DuplicateAnalysis
)


class TestBatchDuplicateIntegration:
    """Integration tests for batch duplicate handling."""
    
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
        
        # Sample existing items for realistic testing
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
            ),
            Item(
                name="Paint White 5L",
                on_hand=20.0,
                unit_type="cans",
                category="Paint",
                location="Warehouse A",
                units=[Unit(name="cans", conversion_factor=1.0)]
            ),
            Item(
                name="Cable 2.5sqmm",
                on_hand=200.0,
                unit_type="meters",
                category="Electrical",
                location="Warehouse C",
                units=[Unit(name="meters", conversion_factor=1.0)]
            )
        ]
    
    @pytest.mark.asyncio
    async def test_end_to_end_duplicate_workflow(self):
        """Test complete end-to-end duplicate handling workflow."""
        # Mock airtable to return existing items
        self.mock_airtable.get_all_items = AsyncMock(return_value=self.existing_items)
        
        # Mock stock service for both IN and OUT operations
        self.mock_stock_service.stock_in = AsyncMock(return_value=(True, "Success", 0.0, 10.0))
        self.mock_stock_service.stock_out = AsyncMock(return_value=(True, "Success", 100.0, 90.0))
        self.mock_airtable.update_item = AsyncMock()
        
        # Complex command with multiple batches and mixed duplicates
        command = """-batch 1-
project: mzuzu, driver: Dani maliko
Cement 50kg, 10 bags
Steel Bar 12mm, 5 pieces
New Item A, 3 kg

-batch 2-
project: lilongwe, driver: John Banda
Paint White 5L, 2 cans
Cable 2.5sqmm, 50 meters
New Item B, 1 piece"""
        
        result = await self.processor.process_batch_command_with_duplicates(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        # Verify overall success
        assert result.success_rate == 100.0
        assert result.successful_entries == 6  # All items should be processed
        assert result.failed_entries == 0
        
        # Verify duplicate analysis in summary
        assert "Duplicate Analysis" in result.summary_message
        assert "0 new items processed" in result.summary_message  # All items are duplicates
        assert "4 exact matches auto-merged" in result.summary_message
        
        # Verify that stock service was called for similar items (not new items)
        assert self.mock_stock_service.stock_in.call_count == 2  # 2 similar items
        
        # Verify that airtable was updated for merged items
        assert self.mock_airtable.update_item.call_count == 4  # 4 exact matches
    
    @pytest.mark.asyncio
    async def test_duplicate_preview_workflow(self):
        """Test duplicate preview workflow before processing."""
        # Mock airtable to return existing items
        self.mock_airtable.get_all_items = AsyncMock(return_value=self.existing_items)
        
        command = """-batch 1-
project: mzuzu, driver: Dani maliko
Cement 50kg, 10 bags
Steel Bar 12mm, 5 pieces
New Item A, 3 kg

-batch 2-
project: lilongwe, driver: John Banda
Paint White 5L, 2 cans
Cable 2.5sqmm, 50 meters
New Item B, 1 piece"""
        
        # Get preview without processing
        preview = await self.processor.get_duplicate_preview(command, MovementType.IN)
        
        # Verify preview structure
        assert preview["status"] == "success"
        assert preview["total_items"] == 6
        assert preview["duplicate_count"] == 6  # All items are duplicates
        assert preview["non_duplicate_count"] == 0  # All items are duplicates
        assert preview["exact_matches"] == 4
        assert preview["similar_items"] == 2  # 2 similar items
        
        # Verify duplicate details
        assert len(preview["duplicates"]) == 6  # All items are duplicates
        
        # Check specific duplicates
        duplicate_names = [dup["item_name"] for dup in preview["duplicates"]]
        assert "Cement 50kg" in duplicate_names
        assert "Steel Bar 12mm" in duplicate_names
        assert "Paint White 5L" in duplicate_names
        assert "Cable 2.5sqmm" in duplicate_names
    
    @pytest.mark.asyncio
    async def test_mixed_success_failure_workflow(self):
        """Test workflow with mixed success and failure scenarios."""
        # Mock airtable to return existing items
        self.mock_airtable.get_all_items = AsyncMock(return_value=self.existing_items)
        
        # Mock stock service to fail on specific items
        def mock_stock_in(item_name, **kwargs):
            if item_name in ["Failing Item", "Another Failing Item"]:
                return (False, "Item not found", 0.0, 0.0)
            return (True, "Success", 0.0, 10.0)
        
        self.mock_stock_service.stock_in = AsyncMock(side_effect=mock_stock_in)
        self.mock_airtable.update_item = AsyncMock()
        
        command = """-batch 1-
project: mzuzu, driver: Dani maliko
Cement 50kg, 10 bags
Failing Item, 5 pieces

-batch 2-
project: lilongwe, driver: John Banda
Steel Bar 12mm, 3 pieces
Another Failing Item, 2 kg"""
        
        result = await self.processor.process_batch_command_with_duplicates(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        # Verify mixed results
        assert result.success_rate == 50.0  # 2 success, 2 failure
        assert result.successful_entries == 2
        assert result.failed_entries == 2
        
        # Verify error handling
        assert len(result.errors) == 2
        assert any("Failing Item" in error.message for error in result.errors)
        assert any("Another Failing Item" in error.message for error in result.errors)
        
        # Verify duplicate analysis still works
        assert "Duplicate Analysis" in result.summary_message
        assert "2 exact matches auto-merged" in result.summary_message
    
    @pytest.mark.asyncio
    async def test_out_command_duplicate_workflow(self):
        """Test OUT command with duplicate detection."""
        # Mock airtable to return existing items
        self.mock_airtable.get_all_items = AsyncMock(return_value=self.existing_items)
        
        # Mock stock service for OUT operations
        self.mock_stock_service.stock_out = AsyncMock(return_value=(True, "Success", 100.0, 90.0))
        
        command = """-batch 1-
project: mzuzu, driver: Dani maliko, to: mzuzu houses
Cement 50kg, 10 bags
Steel Bar 12mm, 5 pieces
New Item, 3 kg"""
        
        result = await self.processor.process_batch_command_with_duplicates(
            command, MovementType.OUT, user_id=123, user_name="Test User"
        )
        
        # Verify success
        assert result.success_rate == 100.0
        assert result.successful_entries == 3
        assert result.failed_entries == 0
        
        # Verify duplicate analysis
        assert "Duplicate Analysis" in result.summary_message
        assert "1 new items processed" in result.summary_message
        assert "2 exact matches auto-merged" in result.summary_message
        
        # Verify stock service calls - only 1 new item should call stock_out
        assert self.mock_stock_service.stock_out.call_count == 1
    
    @pytest.mark.asyncio
    async def test_large_batch_duplicate_workflow(self):
        """Test workflow with large batch containing many duplicates."""
        # Create a larger set of existing items
        large_existing_items = self.existing_items + [
            Item(id=f"item_{i}", name=f"Item {i}", on_hand=10.0, unit_type="pieces", 
                 category="Test", location="Warehouse", units=[Unit(name="pieces", conversion_factor=1.0)]) for i in range(5, 20)
        ]
        
        # Mock airtable to return large set
        self.mock_airtable.get_all_items = AsyncMock(return_value=large_existing_items)
        
        # Mock stock service
        self.mock_stock_service.stock_in = AsyncMock(return_value=(True, "Success", 0.0, 10.0))
        self.mock_airtable.update_item = AsyncMock()
        
        # Large command with many items
        command = """-batch 1-
project: test, driver: test driver
Cement 50kg, 10 bags
Steel Bar 12mm, 5 pieces
Item 5, 3 pieces
Item 6, 2 pieces
Item 7, 1 piece
New Item A, 5 kg
New Item B, 3 kg
New Item C, 2 kg"""
        
        result = await self.processor.process_batch_command_with_duplicates(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        # Verify success
        assert result.success_rate == 100.0
        assert result.successful_entries == 8
        assert result.failed_entries == 0
        
        # Verify duplicate analysis
        assert "Duplicate Analysis" in result.summary_message
        assert "0 new items processed" in result.summary_message  # All items are duplicates
        assert "5 exact matches auto-merged" in result.summary_message
    
    @pytest.mark.asyncio
    async def test_error_recovery_in_duplicate_workflow(self):
        """Test error recovery during duplicate processing."""
        # Mock airtable to return existing items
        self.mock_airtable.get_all_items = AsyncMock(return_value=self.existing_items)
        
        # Mock stock service to fail on some items but succeed on others
        def mock_stock_in(item_name, **kwargs):
            if item_name in ["Failing Item"]:
                return (False, "Database error", 0.0, 0.0)
            return (True, "Success", 0.0, 10.0)
        
        self.mock_stock_service.stock_in = AsyncMock(side_effect=mock_stock_in)
        self.mock_airtable.update_item = AsyncMock()
        
        command = """-batch 1-
project: test, driver: test driver
Cement 50kg, 10 bags
Steel Bar 12mm, 5 pieces
Failing Item, 3 kg
New Item, 2 pieces"""
        
        result = await self.processor.process_batch_command_with_duplicates(
            command, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        # Verify partial success
        assert result.success_rate == 75.0  # 3 success, 1 failure
        assert result.successful_entries == 3
        assert result.failed_entries == 1
        
        # Verify that duplicates were still processed despite failures
        assert "Duplicate Analysis" in result.summary_message
        assert "1 new items processed" in result.summary_message
        assert "2 exact matches auto-merged" in result.summary_message
        
        # Verify error handling
        assert len(result.errors) == 1
        assert "Failing Item" in result.errors[0].message
    
    @pytest.mark.asyncio
    async def test_duplicate_handler_integration(self):
        """Test direct integration with duplicate handler."""
        # Create duplicate handler directly
        duplicate_handler = BatchDuplicateHandler(
            airtable_client=self.mock_airtable,
            stock_service=self.mock_stock_service
        )
        
        # Mock airtable
        self.mock_airtable.get_all_items = AsyncMock(return_value=self.existing_items)
        self.mock_stock_service.stock_in = AsyncMock(return_value=(True, "Success", 0.0, 10.0))
        self.mock_airtable.update_item = AsyncMock()
        
        # Create test batches
        batches = [
            BatchInfo(
                batch_number=1,
                project="test",
                driver="test driver",
                items=[
                    BatchItem(item_name="Cement 50kg", quantity=10.0, unit="bags"),
                    BatchItem(item_name="New Item", quantity=5.0, unit="pieces")
                ]
            )
        ]
        
        # Test duplicate identification
        analysis = await duplicate_handler.identify_duplicates(batches)
        
        assert analysis.total_items == 2
        assert analysis.duplicate_count == 1
        assert analysis.non_duplicate_count == 1
        assert len(analysis.exact_matches) == 1
        
        # Test processing non-duplicates
        non_duplicate_result = await duplicate_handler.process_non_duplicates(
            analysis.non_duplicates, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert non_duplicate_result.success_count == 1
        assert non_duplicate_result.failure_count == 0
        
        # Test processing duplicates
        duplicate_result = await duplicate_handler.process_duplicates(
            analysis.duplicates, MovementType.IN, user_id=123, user_name="Test User"
        )
        
        assert duplicate_result.success_count == 1
        assert duplicate_result.failure_count == 0
        assert len(duplicate_result.merged_items) == 1


if __name__ == "__main__":
    pytest.main([__file__])
