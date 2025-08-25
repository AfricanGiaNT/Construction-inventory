"""Tests for the StockQueryService."""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta

from src.services.stock_query import StockQueryService
from src.schemas import Item


class TestStockQueryService:
    """Test cases for StockQueryService."""
    
    @pytest.fixture
    def mock_airtable_client(self):
        """Create a mock Airtable client."""
        client = Mock()
        client.get_all_items = AsyncMock()
        client.get_item = AsyncMock()
        return client
    
    @pytest.fixture
    def stock_query_service(self, mock_airtable_client):
        """Create a StockQueryService instance with mock dependencies."""
        return StockQueryService(mock_airtable_client)
    
    @pytest.fixture
    def sample_items(self):
        """Create sample items for testing."""
        return [
            Item(
                name="cement",
                sku="cement",
                description=None,
                base_unit="bags",
                units=[],
                on_hand=100.0,
                threshold=10.0,
                location="Warehouse A",
                category="Building Materials",
                large_qty_threshold=1000.0
            ),
            Item(
                name="cement bags",
                sku="cement bags",
                description=None,
                base_unit="bags",
                units=[],
                on_hand=50.0,
                threshold=5.0,
                location="Warehouse B",
                category="Building Materials",
                large_qty_threshold=500.0
            ),
            Item(
                name="cement powder",
                sku="cement powder",
                description=None,
                base_unit="kg",
                units=[],
                on_hand=200.0,
                threshold=20.0,
                location="Warehouse A",
                category="Building Materials",
                large_qty_threshold=2000.0
            ),
            Item(
                name="steel bars",
                sku="steel bars",
                description=None,
                base_unit="pieces",
                units=[],
                on_hand=75.0,
                threshold=10.0,
                location="Warehouse C",
                category="Steel",
                large_qty_threshold=500.0
            )
        ]
    
    def test_calculate_similarity_exact_match(self, stock_query_service):
        """Test exact match similarity calculation."""
        similarity = stock_query_service._calculate_similarity("cement", "cement")
        assert similarity == 1.0
    
    def test_calculate_similarity_partial_match(self, stock_query_service):
        """Test partial match similarity calculation."""
        similarity = stock_query_service._calculate_similarity("cem", "cement")
        assert similarity == 0.9
    
    def test_calculate_similarity_substring_match(self, stock_query_service):
        """Test substring match similarity calculation."""
        similarity = stock_query_service._calculate_similarity("cement", "cement bags")
        assert similarity == 0.9
    
    def test_calculate_similarity_fuzzy_match(self, stock_query_service):
        """Test fuzzy match similarity calculation."""
        similarity = stock_query_service._calculate_similarity("cement", "cement powder")
        assert similarity > 0.8  # Should be high similarity
    
    def test_calculate_similarity_low_similarity(self, stock_query_service):
        """Test low similarity calculation."""
        similarity = stock_query_service._calculate_similarity("cement", "steel bars")
        assert similarity < 0.5  # Should be low similarity
    
    def test_rank_search_results(self, stock_query_service, sample_items):
        """Test search result ranking."""
        query = "cement"
        ranked_results = stock_query_service._rank_search_results(query, sample_items)
        
        # Should have 4 results
        assert len(ranked_results) == 4
        
        # First result should be exact match
        first_item, first_score = ranked_results[0]
        assert first_item.name == "cement"
        assert first_score == 1.0
        
        # Second and third should be partial matches
        second_item, second_score = ranked_results[1]
        third_item, third_score = ranked_results[2]
        assert "cement" in second_item.name
        assert "cement" in third_item.name
        assert second_score >= third_score
    
    @pytest.mark.asyncio
    async def test_fuzzy_search_items_no_results(self, stock_query_service, mock_airtable_client):
        """Test fuzzy search with no results."""
        mock_airtable_client.get_all_items.return_value = []
        
        results = await stock_query_service.fuzzy_search_items("nonexistent", limit=5)
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_fuzzy_search_items_with_results(self, stock_query_service, mock_airtable_client, sample_items):
        """Test fuzzy search with results."""
        mock_airtable_client.get_all_items.return_value = sample_items
        
        results = await stock_query_service.fuzzy_search_items("cement", limit=3)
        
        # Should return 3 results
        assert len(results) == 3
        
        # All results should contain "cement"
        for item in results:
            assert "cement" in item.name.lower()
    
    @pytest.mark.asyncio
    async def test_fuzzy_search_items_limit(self, stock_query_service, mock_airtable_client, sample_items):
        """Test that fuzzy search always returns max 3 results regardless of limit parameter."""
        mock_airtable_client.get_all_items.return_value = sample_items
        
        # Should always return max 3 results, ignoring limit parameter
        results = await stock_query_service.fuzzy_search_items("cement", limit=2)
        assert len(results) == 3  # Always returns max 3
        
        # Test with different limit values
        results = await stock_query_service.fuzzy_search_items("cement", limit=5)
        assert len(results) == 3  # Still returns max 3
        
        results = await stock_query_service.fuzzy_search_items("cement", limit=1)
        assert len(results) == 3  # Still returns max 3
    
    @pytest.mark.asyncio
    async def test_fuzzy_search_items_cache(self, stock_query_service, mock_airtable_client, sample_items):
        """Test that fuzzy search uses and updates cache."""
        mock_airtable_client.get_all_items.return_value = sample_items
        
        # First search should populate cache
        results1 = await stock_query_service.fuzzy_search_items("cement", limit=3)
        assert len(results1) == 3
        
        # Second search should use cache (same results)
        results2 = await stock_query_service.fuzzy_search_items("cement", limit=3)
        assert results1 == results2
        
        # Cache should have been called only once
        assert mock_airtable_client.get_all_items.call_count == 1
    
    def test_cache_management(self, stock_query_service):
        """Test cache management methods."""
        # Test cache stats
        stats = stock_query_service.get_cache_stats()
        assert stats["total_entries"] == 0
        assert stats["cache_ttl_days"] == 7
        
        # Test cache clearing
        stock_query_service.clear_cache()
        stats = stock_query_service.get_cache_stats()
        assert stats["total_entries"] == 0
    
    def test_cache_invalidation(self, stock_query_service):
        """Test cache invalidation for specific items."""
        # Add some test data to cache
        stock_query_service._search_cache["cement"] = ([], datetime.now())
        stock_query_service._search_cache["cement bags"] = ([], datetime.now())
        stock_query_service._search_cache["steel"] = ([], datetime.now())
        
        # Invalidate cache for "cement"
        stock_query_service.invalidate_cache_for_item("cement")
        
        # Should have removed cement-related cache entries
        assert "cement" not in stock_query_service._search_cache
        assert "cement bags" not in stock_query_service._search_cache
        assert "steel" in stock_query_service._search_cache  # Should remain
    
    @pytest.mark.asyncio
    async def test_get_item_details_success(self, stock_query_service, mock_airtable_client, sample_items):
        """Test successful item details retrieval."""
        mock_airtable_client.get_item.return_value = sample_items[0]
        
        success, message, item = await stock_query_service.get_item_details("cement")
        
        assert success is True
        assert "Found item" in message
        assert item.name == "cement"
    
    @pytest.mark.asyncio
    async def test_get_item_details_not_found(self, stock_query_service, mock_airtable_client):
        """Test item details retrieval when item not found."""
        mock_airtable_client.get_item.return_value = None
        
        success, message, item = await stock_query_service.get_item_details("nonexistent")
        
        assert success is False
        assert "not found" in message
        assert item is None
    
    @pytest.mark.asyncio
    async def test_get_pending_movements(self, stock_query_service):
        """Test pending movements retrieval."""
        # This is currently a TODO, so it should return empty list
        movements = await stock_query_service.get_pending_movements("cement")
        assert movements == []
    
    @pytest.mark.asyncio
    async def test_is_in_pending_batch(self, stock_query_service):
        """Test pending batch check."""
        # This is currently a TODO, so it should return False
        result = await stock_query_service.is_in_pending_batch("cement")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_total_matching_items_count(self, stock_query_service, mock_airtable_client, sample_items):
        """Test getting total count of matching items."""
        mock_airtable_client.get_all_items.return_value = sample_items
        
        # Should return total count of all matching items (before limiting to 3)
        total_count = await stock_query_service.get_total_matching_items_count("cement")
        assert total_count == 3  # All 3 items contain "cement"
        
        # Test with different query
        total_count = await stock_query_service.get_total_matching_items_count("steel")
        assert total_count == 1  # Only 1 item contains "steel"
        
        # Test with no matches (use a query that truly has no similarity)
        total_count = await stock_query_service.get_total_matching_items_count("xyz123")
        assert total_count == 0  # No matches
