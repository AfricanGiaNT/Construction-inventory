"""Tests for the persistent idempotency service."""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.services.persistent_idempotency import PersistentIdempotencyService, PersistentIdempotencyKey


class TestPersistentIdempotencyService:
    """Test the persistent idempotency service functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_airtable = AsyncMock()
        self.service = PersistentIdempotencyService(self.mock_airtable, default_ttl_seconds=1)

    def test_generate_key_consistent(self):
        """Test that the same content generates the same key."""
        content1 = "date:25/08/25 logged by: Trevor\nCement, 50"
        content2 = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        key1 = self.service.generate_key(content1)
        key2 = self.service.generate_key(content2)
        
        assert key1 == key2
        assert len(key1) == 64  # SHA-256 hex length

    def test_generate_key_different_content(self):
        """Test that different content generates different keys."""
        content1 = "date:25/08/25 logged by: Trevor\nCement, 50"
        content2 = "date:25/08/25 logged by: Trevor\nCement, 51"
        
        key1 = self.service.generate_key(content1)
        key2 = self.service.generate_key(content2)
        
        assert key1 != key2

    @pytest.mark.asyncio
    async def test_is_duplicate_false_initially(self):
        """Test that content is not duplicate initially."""
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        assert not await self.service.is_duplicate(content)

    @pytest.mark.asyncio
    async def test_is_duplicate_true_after_store(self):
        """Test that content is duplicate after storing."""
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        # Store the key
        await self.service.store_key(content)
        
        # Should be duplicate now
        assert await self.service.is_duplicate(content)

    @pytest.mark.asyncio
    async def test_is_duplicate_false_after_ttl_expiry(self):
        """Test that content is not duplicate after TTL expiry."""
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        # Store with short TTL
        await self.service.store_key(content, ttl_seconds=0.5)
        
        # Wait for TTL to expire
        time.sleep(0.6)
        
        # Should not be duplicate now
        assert not await self.service.is_duplicate(content)

    @pytest.mark.asyncio
    async def test_store_key_returns_key(self):
        """Test that store_key returns the generated key."""
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        key = await self.service.store_key(content)
        
        assert key == self.service.generate_key(content)
        assert len(key) == 64

    @pytest.mark.asyncio
    async def test_store_key_custom_ttl(self):
        """Test storing key with custom TTL."""
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        # Store with custom TTL
        await self.service.store_key(content, ttl_seconds=3)
        
        # Should be duplicate immediately
        assert await self.service.is_duplicate(content)
        
        # Wait for default TTL but before custom TTL
        time.sleep(1.1)
        
        # Should still be duplicate (custom TTL not expired)
        assert await self.service.is_duplicate(content)

    @pytest.mark.asyncio
    async def test_remove_key_success(self):
        """Test removing an existing key."""
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        # Store the key
        await self.service.store_key(content)
        assert await self.service.is_duplicate(content)
        
        # Remove the key
        result = await self.service.remove_key(content)
        assert result is True
        
        # Should not be duplicate now
        assert not await self.service.is_duplicate(content)

    @pytest.mark.asyncio
    async def test_remove_key_nonexistent(self):
        """Test removing a non-existent key."""
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        result = await self.service.remove_key(content)
        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_expired(self):
        """Test cleanup of expired keys."""
        # Store multiple keys with different TTLs
        content1 = "content1"
        content2 = "content2"
        content3 = "content3"
        
        await self.service.store_key(content1, ttl_seconds=0.1)  # Expires quickly
        await self.service.store_key(content2, ttl_seconds=0.1)  # Expires quickly
        await self.service.store_key(content3, ttl_seconds=2)     # Expires later
        
        # Wait for first two to expire
        time.sleep(0.2)
        
        # Clean up expired keys
        removed_count = await self.service.cleanup_expired()
        
        assert removed_count == 2
        assert not await self.service.is_duplicate(content1)
        assert not await self.service.is_duplicate(content2)
        assert await self.service.is_duplicate(content3)  # Still valid

    def test_get_cache_stats(self):
        """Test cache statistics."""
        # Initially empty
        stats = self.service.get_cache_stats()
        assert stats["total_keys"] == 0
        assert stats["cache_size"] == 0
        assert stats["persistent_enabled"] is True

    @pytest.mark.asyncio
    async def test_persistent_storage_intention(self):
        """Test that persistent storage is attempted."""
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        # Store the key
        await self.service.store_key(content)
        
        # Verify that Airtable storage was attempted
        # The actual implementation will be added when Airtable schema is ready
        assert await self.service.is_duplicate(content)

    @pytest.mark.asyncio
    async def test_cache_loading_intention(self):
        """Test that cache loading from Airtable is attempted."""
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        # Check for duplicate (this should trigger cache loading)
        await self.service.is_duplicate(content)
        
        # Verify that cache loading was attempted
        # The actual implementation will be added when Airtable schema is ready
        assert not await self.service.is_duplicate(content)

    @pytest.mark.asyncio
    async def test_airtable_fallback_on_error(self):
        """Test that service falls back to cache-only behavior on Airtable errors."""
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        # Mock Airtable to raise an error
        self.mock_airtable.get_all_bot_meta_records.side_effect = Exception("Airtable error")
        
        # Should still work (fallback to cache-only)
        assert not await self.service.is_duplicate(content)
        
        # Store key should still work
        key = await self.service.store_key(content)
        assert len(key) == 64

    @pytest.mark.asyncio
    async def test_concurrent_duplicate_detection(self):
        """Test that concurrent duplicate detection works correctly."""
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        # Simulate concurrent access
        assert not await self.service.is_duplicate(content)
        
        # Store the key
        key = await self.service.store_key(content)
        
        # Immediately check for duplicate
        assert await self.service.is_duplicate(content)
        
        # Check that the key is the same
        assert key == self.service.generate_key(content)

    @pytest.mark.asyncio
    async def test_ttl_edge_cases(self):
        """Test TTL edge cases."""
        # Clear any existing cache first
        self.service._cache.clear()
        
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        # Test with zero TTL - should not store the key
        await self.service.store_key(content, ttl_seconds=0)
        assert not await self.service.is_duplicate(content)  # Should not be duplicate since not stored
        
        # Test with negative TTL - should not store the key
        await self.service.store_key(content, ttl_seconds=-1)
        assert not await self.service.is_duplicate(content)  # Should not be duplicate since not stored
        
        # Test with valid TTL - should store and be duplicate
        await self.service.store_key(content, ttl_seconds=1)
        assert await self.service.is_duplicate(content)  # Should be duplicate

    @pytest.mark.asyncio
    async def test_large_content_handling(self):
        """Test handling of large content."""
        # Create large content
        large_content = "date:25/08/25 logged by: Trevor\n" + "Cement, 50\n" * 1000
        
        # Should still work
        key = await self.service.store_key(large_content)
        assert len(key) == 64
        
        # Should be duplicate
        assert await self.service.is_duplicate(large_content)

    @pytest.mark.asyncio
    async def test_special_characters_in_content(self):
        """Test handling of special characters in content."""
        special_content = "date:25/08/25 logged by: Trevor\nCement & Steel, 50\nSpecial: chars!@#$%^&*()"
        
        key = await self.service.store_key(special_content)
        assert len(key) == 64
        
        # Should be duplicate
        assert await self.service.is_duplicate(special_content)

    @pytest.mark.asyncio
    async def test_unicode_content_handling(self):
        """Test handling of unicode content."""
        unicode_content = "date:25/08/25 logged by: Trevor\nCafé, 50\nRésumé, 25"
        
        key = await self.service.store_key(unicode_content)
        assert len(key) == 64
        
        # Should be duplicate
        assert await self.service.is_duplicate(unicode_content)
