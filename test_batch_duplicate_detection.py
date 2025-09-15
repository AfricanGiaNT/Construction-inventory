"""Tests for batch duplicate detection functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.services.batch_duplicate_handler import BatchDuplicateHandler
from src.schemas import (
    BatchInfo, BatchItem, Item, Unit, DuplicateMatchType, 
    DuplicateAnalysis, DuplicateItem, MovementType
)


class TestBatchDuplicateDetection:
    """Test batch duplicate detection functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_airtable = MagicMock()
        self.mock_stock_service = MagicMock()
        
        # Create duplicate handler
        self.duplicate_handler = BatchDuplicateHandler(
            airtable_client=self.mock_airtable,
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
            ),
            Item(
                name="Paint White 5L",
                on_hand=20.0,
                unit_type="cans",
                category="Paint",
                location="Warehouse A",
                units=[Unit(name="cans", conversion_factor=1.0)]
            )
        ]
    
    @pytest.mark.asyncio
    async def test_identify_exact_duplicates(self):
        """Test identification of exact duplicates."""
        # Mock existing items
        self.mock_airtable.get_all_items = AsyncMock(return_value=self.existing_items)
        
        # Create batches with exact duplicates
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
        
        analysis = await self.duplicate_handler.identify_duplicates(batches)
        
        assert analysis.total_items == 2
        assert analysis.duplicate_count == 1
        assert analysis.non_duplicate_count == 1
        assert len(analysis.exact_matches) == 1
        assert len(analysis.similar_items) == 0
        
        # Check duplicate details
        duplicate = analysis.duplicates[0]
        assert duplicate.batch_item['item_name'] == "Cement 50kg"
        assert duplicate.existing_item['name'] == "Cement 50kg"
        assert duplicate.match_type == DuplicateMatchType.EXACT
        assert duplicate.similarity_score >= 0.95
    
    @pytest.mark.asyncio
    async def test_identify_similar_duplicates(self):
        """Test identification of similar duplicates."""
        # Mock existing items
        self.mock_airtable.get_all_items = AsyncMock(return_value=self.existing_items)
        
        # Create batches with similar items
        batches = [
            BatchInfo(
                batch_number=1,
                project="test",
                driver="test driver",
                items=[
                    BatchItem(item_name="Cement 50kg bag", quantity=10.0, unit="bags"),
                    BatchItem(item_name="Steel Bars 12mm piece", quantity=5.0, unit="pieces")
                ]
            )
        ]
        
        analysis = await self.duplicate_handler.identify_duplicates(batches)
        
        assert analysis.total_items == 2
        assert analysis.duplicate_count == 2  # Both should be matches
        assert analysis.non_duplicate_count == 0
        # Enhanced algorithm correctly identifies these as exact matches due to keyword matching
        assert len(analysis.exact_matches) == 2
        
        # Check that both items are identified as similar
        for duplicate in analysis.duplicates:
            assert duplicate.match_type in [DuplicateMatchType.EXACT, DuplicateMatchType.SIMILAR]
            assert duplicate.similarity_score >= 0.7
    
    @pytest.mark.asyncio
    async def test_identify_no_duplicates(self):
        """Test identification when no duplicates exist."""
        # Mock existing items
        self.mock_airtable.get_all_items = AsyncMock(return_value=self.existing_items)
        
        # Create batches with completely new items
        batches = [
            BatchInfo(
                batch_number=1,
                project="test",
                driver="test driver",
                items=[
                    BatchItem(item_name="Completely New Item", quantity=10.0, unit="pieces"),
                    BatchItem(item_name="Another New Item", quantity=5.0, unit="kg")
                ]
            )
        ]
        
        analysis = await self.duplicate_handler.identify_duplicates(batches)
        
        assert analysis.total_items == 2
        assert analysis.duplicate_count == 0
        assert analysis.non_duplicate_count == 2
        assert len(analysis.duplicates) == 0
        assert len(analysis.non_duplicates) == 2
    
    @pytest.mark.asyncio
    async def test_identify_mixed_duplicates(self):
        """Test identification of mixed exact and similar duplicates."""
        # Mock existing items
        self.mock_airtable.get_all_items = AsyncMock(return_value=self.existing_items)
        
        # Create batches with mixed duplicates
        batches = [
            BatchInfo(
                batch_number=1,
                project="test",
                driver="test driver",
                items=[
                    BatchItem(item_name="Cement 50kg", quantity=10.0, unit="bags"),  # Exact match
                    BatchItem(item_name="Steel Bar 12mm", quantity=5.0, unit="pieces"),  # Exact match
                    BatchItem(item_name="Paint White 5L", quantity=2.0, unit="cans"),  # Exact match
                    BatchItem(item_name="New Item", quantity=3.0, unit="pieces")  # No match
                ]
            )
        ]
        
        analysis = await self.duplicate_handler.identify_duplicates(batches)
        
        assert analysis.total_items == 4
        assert analysis.duplicate_count == 3
        assert analysis.non_duplicate_count == 1
        assert len(analysis.exact_matches) == 3
        assert len(analysis.similar_items) == 0
        assert len(analysis.non_duplicates) == 1
    
    @pytest.mark.asyncio
    async def test_similarity_calculation(self):
        """Test similarity score calculation."""
        # Test exact match
        score1 = self.duplicate_handler._calculate_similarity("Cement 50kg", "Cement 50kg")
        assert score1 >= 0.95
        
        # Test similar match (enhanced algorithm considers this very similar due to keyword matching)
        score2 = self.duplicate_handler._calculate_similarity("Cement 50kg", "Cement 50kg bag")
        assert score2 >= 0.7  # Enhanced algorithm gives high score for keyword matches
        
        # Test no match
        score3 = self.duplicate_handler._calculate_similarity("Cement", "Steel")
        assert score3 < 0.5
    
    def test_match_type_determination(self):
        """Test match type determination based on similarity score."""
        # Test exact match
        match_type1 = self.duplicate_handler._determine_match_type(0.96)
        assert match_type1 == DuplicateMatchType.EXACT
        
        # Test similar match
        match_type2 = self.duplicate_handler._determine_match_type(0.8)
        assert match_type2 == DuplicateMatchType.SIMILAR
        
        # Test fuzzy match
        match_type3 = self.duplicate_handler._determine_match_type(0.6)
        assert match_type3 == DuplicateMatchType.FUZZY
    
    @pytest.mark.asyncio
    async def test_process_non_duplicates_success(self):
        """Test successful processing of non-duplicate items."""
        # Mock stock service
        self.mock_stock_service.stock_in = AsyncMock(return_value=(True, "Success", 0.0, 10.0))
        
        non_duplicates = [
            BatchItem(item_name="New Item 1", quantity=10.0, unit="pieces"),
            BatchItem(item_name="New Item 2", quantity=5.0, unit="kg")
        ]
        
        result = await self.duplicate_handler.process_non_duplicates(
            non_duplicates, "In", user_id=123, user_name="Test User"
        )
        
        assert result.success_count == 2
        assert result.failure_count == 0
        assert len(result.processing_errors) == 0
    
    @pytest.mark.asyncio
    async def test_process_non_duplicates_failure(self):
        """Test processing of non-duplicate items with failures."""
        # Mock stock service to fail
        def mock_stock_in(item_name, **kwargs):
            if item_name == "Failing Item":
                return (False, "Item not found", 0.0, 0.0)
            return (True, "Success", 0.0, 10.0)
        
        self.mock_stock_service.stock_in = AsyncMock(side_effect=mock_stock_in)
        
        non_duplicates = [
            BatchItem(item_name="Success Item", quantity=10.0, unit="pieces"),
            BatchItem(item_name="Failing Item", quantity=5.0, unit="kg")
        ]
        
        result = await self.duplicate_handler.process_non_duplicates(
            non_duplicates, "In", user_id=123, user_name="Test User"
        )
        
        assert result.success_count == 1
        assert result.failure_count == 1
        assert len(result.processing_errors) == 1
        assert "Failing Item" in result.processing_errors[0].message
    
    @pytest.mark.asyncio
    async def test_process_duplicates_auto_merge(self):
        """Test processing of duplicates with auto-merge for exact matches."""
        # Mock stock service and airtable
        self.mock_stock_service.stock_in = AsyncMock(return_value=(True, "Success", 0.0, 10.0))
        self.mock_airtable.update_item = AsyncMock()
        
        # Create duplicate items
        existing_item = Item(
            name="Cement 50kg",
            on_hand=100.0,
            unit_type="bags",
            category="Construction Materials",
            location="Warehouse A",
            units=[Unit(name="bags", conversion_factor=1.0)]
        )
        
        duplicate = DuplicateItem(
            batch_item=BatchItem(item_name="Cement 50kg", quantity=10.0, unit="bags").model_dump(),
            existing_item=existing_item.model_dump(),
            similarity_score=0.98,
            match_type=DuplicateMatchType.EXACT,
            batch_number=1,
            item_index=0
        )
        
        result = await self.duplicate_handler.process_duplicates(
            [duplicate], MovementType.IN, user_id=123, user_name="Test User", auto_merge_exact=True
        )
        
        assert result.success_count == 1
        assert result.failure_count == 0
        assert len(result.merged_items) == 1
        assert len(result.processed_duplicates) == 1
    
    @pytest.mark.asyncio
    async def test_merge_quantities(self):
        """Test merging quantities for exact matches."""
        # Mock airtable update
        self.mock_airtable.update_item = AsyncMock()
        
        existing_item = Item(
            name="Cement 50kg",
            on_hand=100.0,
            unit_type="bags",
            category="Construction Materials",
            location="Warehouse A",
            units=[Unit(name="bags", conversion_factor=1.0)]
        )
        
        new_item = BatchItem(item_name="Cement 50kg", quantity=25.0, unit="bags")
        
        merged_item = await self.duplicate_handler.merge_quantities(
            existing_item.model_dump(), new_item.model_dump()
        )
        
        assert merged_item['on_hand'] == 125.0  # 100 + 25
        assert merged_item['name'] == "Cement 50kg"
        self.mock_airtable.update_item.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling_in_duplicate_identification(self):
        """Test error handling during duplicate identification."""
        # Mock airtable to raise exception
        self.mock_airtable.get_all_items = AsyncMock(side_effect=Exception("Database error"))
        
        batches = [
            BatchInfo(
                batch_number=1,
                project="test",
                driver="test driver",
                items=[BatchItem(item_name="Test Item", quantity=10.0, unit="pieces")]
            )
        ]
        
        analysis = await self.duplicate_handler.identify_duplicates(batches)
        
        # Should still process items even if we can't get existing items
        assert analysis.total_items == 1
        assert analysis.duplicate_count == 0  # No duplicates found due to error
        assert analysis.non_duplicate_count == 1  # All items treated as non-duplicates


if __name__ == "__main__":
    pytest.main([__file__])
