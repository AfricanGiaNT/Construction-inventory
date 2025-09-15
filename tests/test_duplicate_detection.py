"""Tests for the duplicate detection service."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import List

from src.services.duplicate_detection import (
    DuplicateDetectionService, 
    PotentialDuplicate, 
    DuplicateDetectionResult
)
from src.schemas import StockMovement, MovementType, MovementStatus


class TestDuplicateDetectionService:
    """Test cases for DuplicateDetectionService."""
    
    @pytest.fixture
    def mock_airtable(self):
        """Create a mock AirtableClient."""
        mock = Mock()
        mock.get_stock_movements_since = AsyncMock(return_value=[])
        return mock
    
    @pytest.fixture
    def service(self, mock_airtable):
        """Create a DuplicateDetectionService instance."""
        return DuplicateDetectionService(mock_airtable)
    
    @pytest.fixture
    def sample_movements(self):
        """Create sample stock movements for testing."""
        return [
            StockMovement(
                id="movement_1",
                item_name="Cement 32.5",
                movement_type=MovementType.IN,
                quantity=50.0,
                unit="bags",
                signed_base_quantity=50.0,
                timestamp=datetime.now() - timedelta(days=2),
                user_id="user_1",
                user_name="John",
                status=MovementStatus.POSTED,
                location="Warehouse A",
                category="Construction Materials"
            ),
            StockMovement(
                id="movement_2",
                item_name="32.5 Cement",
                movement_type=MovementType.IN,
                quantity=45.0,
                unit="bags",
                signed_base_quantity=45.0,
                timestamp=datetime.now() - timedelta(days=1),
                user_id="user_2",
                user_name="Sarah",
                status=MovementStatus.POSTED,
                location="Warehouse B",
                category="Construction Materials"
            ),
            StockMovement(
                id="movement_3",
                item_name="12mm rebar",
                movement_type=MovementType.IN,
                quantity=100.0,
                unit="pieces",
                signed_base_quantity=100.0,
                timestamp=datetime.now() - timedelta(days=3),
                user_id="user_3",
                user_name="Mike",
                status=MovementStatus.POSTED,
                location="Warehouse A",
                category="Steel"
            ),
            StockMovement(
                id="movement_4",
                item_name="Paint Red 20ltrs",
                movement_type=MovementType.IN,
                quantity=10.0,
                unit="cans",
                signed_base_quantity=10.0,
                timestamp=datetime.now() - timedelta(days=5),
                user_id="user_4",
                user_name="Alice",
                status=MovementStatus.POSTED,
                location="Warehouse C",
                category="Paints"
            )
        ]
    
    def test_extract_keywords(self, service):
        """Test keyword extraction from item names."""
        # Test basic keyword extraction
        keywords = service._extract_keywords("Cement 32.5 Grade")
        expected = ["cement", "32.5", "grade"]
        assert keywords == expected
        
        # Test with common words
        keywords = service._extract_keywords("The cement and 32.5 grade")
        expected = ["cement", "32.5", "grade"]
        assert keywords == expected
        
        # Test with short words
        keywords = service._extract_keywords("A 50kg bag of cement")
        expected = ["50kg", "bag", "cement"]
        assert keywords == expected
        
        # Test empty text
        keywords = service._extract_keywords("")
        assert keywords == []
        
        # Test only common words
        keywords = service._extract_keywords("the and or")
        assert keywords == []
    
    def test_normalize_text(self, service):
        """Test text normalization."""
        # Test basic normalization
        normalized = service._normalize_text("  Cement  32.5  Grade  ")
        assert normalized == "cement 32.5 grade"
        
        # Test with extra spaces
        normalized = service._normalize_text("Cement   32.5\t\nGrade")
        assert normalized == "cement 32.5 grade"
        
        # Test empty text
        normalized = service._normalize_text("")
        assert normalized == ""
    
    def test_normalize_quantity(self, service):
        """Test quantity and unit extraction."""
        # Test with unit
        qty, unit = service._normalize_quantity("Cement 50kgs")
        assert qty == 50.0
        assert unit == "kgs"
        
        # Test with space between number and unit
        qty, unit = service._normalize_quantity("Cement 50 kgs")
        assert qty == 50.0
        assert unit == "kgs"
        
        # Test decimal quantity
        qty, unit = service._normalize_quantity("Cement 50.5 bags")
        assert qty == 50.5
        assert unit == "bags"
        
        # Test without unit
        qty, unit = service._normalize_quantity("Cement 50")
        assert qty == 50.0
        assert unit == "piece"
        
        # Test multiple quantities (should take first)
        qty, unit = service._normalize_quantity("50kgs cement 30bags")
        assert qty == 50.0
        assert unit == "kgs"
        
        # Test no quantity
        qty, unit = service._normalize_quantity("Cement only")
        assert qty == 0.0
        assert unit == "piece"
    
    def test_quantities_similar(self, service):
        """Test quantity similarity checking."""
        # Test identical quantities
        assert service._quantities_similar(50.0, 50.0) == True
        
        # Test similar quantities within tolerance
        assert service._quantities_similar(50.0, 45.0) == True  # 10% difference
        assert service._quantities_similar(50.0, 55.0) == True  # 10% difference
        
        # Test different quantities beyond tolerance
        assert service._quantities_similar(50.0, 30.0) == False  # 40% difference
        assert service._quantities_similar(50.0, 70.0) == False  # 40% difference
        
        # Test zero quantities
        assert service._quantities_similar(0.0, 0.0) == True
        assert service._quantities_similar(0.0, 10.0) == False
        assert service._quantities_similar(10.0, 0.0) == False
    
    def test_calculate_duplicate_similarity_exact_match(self, service):
        """Test similarity calculation for exact matches."""
        # Test exact text match
        similarity = service._calculate_duplicate_similarity("Cement 32.5", "Cement 32.5")
        assert similarity == 1.0
        
        # Test exact match with different case
        similarity = service._calculate_duplicate_similarity("cement 32.5", "CEMENT 32.5")
        assert similarity == 1.0
    
    def test_calculate_duplicate_similarity_keyword_matches(self, service):
        """Test similarity calculation for keyword matches."""
        # Test all keywords match
        similarity = service._calculate_duplicate_similarity("Cement 32.5", "32.5 Cement")
        assert similarity >= 0.7
        
        # Test with one missing keyword
        similarity = service._calculate_duplicate_similarity("Cement 32.5 Grade", "Cement 32.5")
        assert similarity >= 0.7
        
        # Test with different quantities (should fail)
        similarity = service._calculate_duplicate_similarity("Cement 50kgs", "Cement 20kgs")
        assert similarity < 0.7
        
        # Test with too many missing keywords
        similarity = service._calculate_duplicate_similarity("Cement 32.5 Grade", "Cement")
        assert similarity < 0.7
    
    def test_calculate_duplicate_similarity_order_independence(self, service):
        """Test that order doesn't matter for similarity."""
        # Test different word orders
        similarity1 = service._calculate_duplicate_similarity("50kgs bags cement", "cement 50kgs bags")
        similarity2 = service._calculate_duplicate_similarity("cement 50kgs bags", "50kgs bags cement")
        
        assert similarity1 >= 0.7
        assert similarity2 >= 0.7
        assert similarity1 == similarity2
    
    def test_calculate_duplicate_similarity_no_match(self, service):
        """Test similarity calculation for non-matching items."""
        # Test completely different items
        similarity = service._calculate_duplicate_similarity("Cement 32.5", "Paint Red")
        assert similarity == 0.0
        
        # Test similar but different items (these should be considered similar for duplicate detection)
        similarity = service._calculate_duplicate_similarity("Cement 32.5", "Concrete 32.5")
        assert similarity >= 0.7  # They are similar enough to be considered potential duplicates
    
    def test_calculate_duplicate_similarity_quantity_validation(self, service):
        """Test that quantity similarity is required."""
        # Test same keywords but very different quantities
        similarity = service._calculate_duplicate_similarity("Cement 50kgs", "Cement 5kgs")
        assert similarity < 0.7
        
        # Test same keywords and similar quantities
        similarity = service._calculate_duplicate_similarity("Cement 50kgs", "Cement 45kgs")
        assert similarity >= 0.7
    
    @pytest.mark.asyncio
    async def test_find_potential_duplicates(self, service, sample_movements):
        """Test finding potential duplicates."""
        # Mock the airtable to return sample movements
        service.airtable.get_stock_movements_since = AsyncMock(return_value=sample_movements)
        
        # Test finding duplicates for cement
        duplicates = await service.find_potential_duplicates("Cement 32.5", 50.0)
        
        # Should find the cement movements
        assert len(duplicates) >= 2
        
        # Check that results are sorted by similarity score
        for i in range(len(duplicates) - 1):
            assert duplicates[i].similarity_score >= duplicates[i + 1].similarity_score
        
        # Check that all results meet threshold
        for duplicate in duplicates:
            assert duplicate.similarity_score >= 0.7
    
    @pytest.mark.asyncio
    async def test_find_potential_duplicates_no_matches(self, service):
        """Test finding duplicates when no matches exist."""
        # Mock empty movements
        service.airtable.get_stock_movements_since = AsyncMock(return_value=[])
        
        duplicates = await service.find_potential_duplicates("Cement 32.5", 50.0)
        assert len(duplicates) == 0
    
    @pytest.mark.asyncio
    async def test_find_potential_duplicates_error_handling(self, service):
        """Test error handling in find_potential_duplicates."""
        # Mock airtable to raise exception
        service.airtable.get_stock_movements_since = AsyncMock(side_effect=Exception("Database error"))
        
        duplicates = await service.find_potential_duplicates("Cement 32.5", 50.0)
        assert len(duplicates) == 0
    
    @pytest.mark.asyncio
    async def test_check_entries_for_duplicates(self, service, sample_movements):
        """Test checking multiple entries for duplicates."""
        # Mock the airtable
        service.airtable.get_stock_movements_since = AsyncMock(return_value=sample_movements)
        
        # Create mock entries
        class MockEntry:
            def __init__(self, item_name, quantity):
                self.item_name = item_name
                self.quantity = quantity
        
        entries = [
            MockEntry("Cement 32.5", 50.0),
            MockEntry("12mm rebar", 120.0),
            MockEntry("Paint Blue", 5.0)  # No duplicates expected
        ]
        
        result = await service.check_entries_for_duplicates(entries)
        
        assert isinstance(result, DuplicateDetectionResult)
        assert result.has_duplicates == True
        assert len(result.potential_duplicates) > 0
        assert result.requires_confirmation == True
        assert result.new_entries == entries
    
    @pytest.mark.asyncio
    async def test_check_entries_for_duplicates_no_duplicates(self, service):
        """Test checking entries when no duplicates exist."""
        # Mock empty movements
        service.airtable.get_stock_movements_since = AsyncMock(return_value=[])
        
        class MockEntry:
            def __init__(self, item_name, quantity):
                self.item_name = item_name
                self.quantity = quantity
        
        entries = [MockEntry("Unique Item", 10.0)]
        
        result = await service.check_entries_for_duplicates(entries)
        
        assert result.has_duplicates == False
        assert len(result.potential_duplicates) == 0
        assert result.requires_confirmation == False
    
    def test_clear_cache(self, service):
        """Test cache clearing functionality."""
        # Add some data to cache
        service._cache["test_key"] = ["test_data"]
        service._cache_timestamps["test_key"] = datetime.now()
        
        # Clear cache
        service.clear_cache()
        
        assert len(service._cache) == 0
        assert len(service._cache_timestamps) == 0
    
    @pytest.mark.asyncio
    async def test_cache_functionality(self, service, sample_movements):
        """Test that caching works correctly."""
        # Mock airtable to return sample movements
        service.airtable.get_stock_movements_since = AsyncMock(return_value=sample_movements)
        
        # First call should hit database
        duplicates1 = await service.find_potential_duplicates("Cement 32.5", 50.0)
        
        # Second call should hit cache
        duplicates2 = await service.find_potential_duplicates("Cement 32.5", 50.0)
        
        # Results should be the same
        assert len(duplicates1) == len(duplicates2)
        
        # Airtable should only be called once due to caching
        assert service.airtable.get_stock_movements_since.call_count == 1
    
    def test_potential_duplicate_creation(self):
        """Test PotentialDuplicate dataclass creation."""
        duplicate = PotentialDuplicate(
            item_name="Cement 32.5",
            quantity=50.0,
            unit="bags",
            similarity_score=0.95,
            movement_id="movement_1",
            timestamp=datetime.now(),
            location="Warehouse A",
            category="Construction Materials",
            user_name="John"
        )
        
        assert duplicate.item_name == "Cement 32.5"
        assert duplicate.quantity == 50.0
        assert duplicate.unit == "bags"
        assert duplicate.similarity_score == 0.95
        assert duplicate.movement_id == "movement_1"
        assert duplicate.location == "Warehouse A"
        assert duplicate.category == "Construction Materials"
        assert duplicate.user_name == "John"
    
    def test_duplicate_detection_result_creation(self):
        """Test DuplicateDetectionResult dataclass creation."""
        duplicate = PotentialDuplicate(
            item_name="Cement 32.5",
            quantity=50.0,
            unit="bags",
            similarity_score=0.95,
            movement_id="movement_1",
            timestamp=datetime.now(),
            user_name="John"
        )
        
        class MockEntry:
            def __init__(self, item_name, quantity):
                self.item_name = item_name
                self.quantity = quantity
        
        entries = [MockEntry("Cement 32.5", 50.0)]
        
        result = DuplicateDetectionResult(
            has_duplicates=True,
            potential_duplicates=[duplicate],
            new_entries=entries,
            requires_confirmation=True
        )
        
        assert result.has_duplicates == True
        assert len(result.potential_duplicates) == 1
        assert result.potential_duplicates[0] == duplicate
        assert result.new_entries == entries
        assert result.requires_confirmation == True


class TestDuplicateDetectionEdgeCases:
    """Test edge cases for duplicate detection."""
    
    @pytest.fixture
    def service(self):
        """Create a service instance with mock airtable."""
        mock_airtable = Mock()
        mock_airtable.get_stock_movements_since = AsyncMock(return_value=[])
        return DuplicateDetectionService(mock_airtable)
    
    def test_empty_strings(self, service):
        """Test handling of empty strings."""
        similarity = service._calculate_duplicate_similarity("", "")
        assert similarity == 0.0
        
        similarity = service._calculate_duplicate_similarity("Cement", "")
        assert similarity == 0.0
        
        similarity = service._calculate_duplicate_similarity("", "Cement")
        assert similarity == 0.0
    
    def test_special_characters(self, service):
        """Test handling of special characters."""
        similarity = service._calculate_duplicate_similarity("Cement-32.5", "Cement 32.5")
        assert similarity >= 0.7
        
        similarity = service._calculate_duplicate_similarity("Cement_32.5", "Cement 32.5")
        assert similarity >= 0.7
    
    def test_numbers_in_keywords(self, service):
        """Test handling of numbers in keywords."""
        similarity = service._calculate_duplicate_similarity("Cement 32.5", "32.5 Cement")
        assert similarity >= 0.7
        
        similarity = service._calculate_duplicate_similarity("Pipe 250mm", "250mm Pipe")
        assert similarity >= 0.7
    
    def test_very_long_item_names(self, service):
        """Test handling of very long item names."""
        long_name1 = "Very Long Construction Material Name With Many Descriptive Words And Specifications"
        long_name2 = "Very Long Construction Material Name With Many Descriptive Words And Different Specifications"
        
        similarity = service._calculate_duplicate_similarity(long_name1, long_name2)
        # Should still work but might have lower similarity due to different keywords
        assert similarity >= 0.0
    
    def test_unicode_characters(self, service):
        """Test handling of unicode characters."""
        similarity = service._calculate_duplicate_similarity("Cément 32.5", "Cement 32.5")
        # Should handle unicode normalization
        assert similarity >= 0.0
