"""Tests for the idempotency service."""

import pytest
import time
from unittest.mock import patch

from src.services.idempotency import IdempotencyService, IdempotencyKey


class TestIdempotencyService:
    """Test the idempotency service functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = IdempotencyService(default_ttl_seconds=1)  # Short TTL for testing

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

    def test_generate_key_case_insensitive(self):
        """Test that key generation is case-insensitive."""
        content1 = "date:25/08/25 logged by: Trevor\nCement, 50"
        content2 = "DATE:25/08/25 LOGGED BY: TREVOR\nCEMENT, 50"
        
        key1 = self.service.generate_key(content1)
        key2 = self.service.generate_key(content2)
        
        assert key1 == key2

    def test_generate_key_whitespace_normalized(self):
        """Test that whitespace is normalized in key generation."""
        content1 = "date:25/08/25 logged by: Trevor\nCement, 50"
        content2 = "  date:25/08/25 logged by: Trevor\nCement, 50  "
        
        key1 = self.service.generate_key(content1)
        key2 = self.service.generate_key(content2)
        
        assert key1 == key2

    def test_is_duplicate_false_initially(self):
        """Test that content is not duplicate initially."""
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        assert not self.service.is_duplicate(content)

    def test_is_duplicate_true_after_store(self):
        """Test that content is duplicate after storing."""
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        # Store the key
        self.service.store_key(content)
        
        # Should be duplicate now
        assert self.service.is_duplicate(content)

    def test_is_duplicate_false_after_ttl_expiry(self):
        """Test that content is not duplicate after TTL expiry."""
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        # Store with short TTL
        self.service.store_key(content, ttl_seconds=0.1)
        
        # Wait for TTL to expire
        time.sleep(0.2)
        
        # Should not be duplicate now
        assert not self.service.is_duplicate(content)

    def test_store_key_returns_key(self):
        """Test that store_key returns the generated key."""
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        key = self.service.store_key(content)
        
        assert key == self.service.generate_key(content)
        assert len(key) == 64

    def test_store_key_custom_ttl(self):
        """Test storing key with custom TTL."""
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        # Store with custom TTL
        self.service.store_key(content, ttl_seconds=2)
        
        # Should be duplicate immediately
        assert self.service.is_duplicate(content)
        
        # Wait for default TTL but before custom TTL
        time.sleep(1.1)
        
        # Should still be duplicate (custom TTL not expired)
        assert self.service.is_duplicate(content)

    def test_remove_key_success(self):
        """Test removing an existing key."""
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        # Store the key
        self.service.store_key(content)
        assert self.service.is_duplicate(content)
        
        # Remove the key
        result = self.service.remove_key(content)
        assert result is True
        
        # Should not be duplicate now
        assert not self.service.is_duplicate(content)

    def test_remove_key_nonexistent(self):
        """Test removing a non-existent key."""
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        result = self.service.remove_key(content)
        assert result is False

    def test_cleanup_expired(self):
        """Test cleanup of expired keys."""
        # Store multiple keys with different TTLs
        content1 = "content1"
        content2 = "content2"
        content3 = "content3"
        
        self.service.store_key(content1, ttl_seconds=0.1)  # Expires quickly
        self.service.store_key(content2, ttl_seconds=0.1)  # Expires quickly
        self.service.store_key(content3, ttl_seconds=2)     # Expires later
        
        # Wait for first two to expire
        time.sleep(0.2)
        
        # Clean up expired keys
        removed_count = self.service.cleanup_expired()
        
        assert removed_count == 2
        assert not self.service.is_duplicate(content1)
        assert not self.service.is_duplicate(content2)
        assert self.service.is_duplicate(content3)  # Still valid

    def test_get_cache_stats(self):
        """Test cache statistics."""
        # Initially empty
        stats = self.service.get_cache_stats()
        assert stats["total_keys"] == 0
        assert stats["cache_size"] == 0
        
        # Add some keys
        content1 = "content1"
        content2 = "content2"
        
        self.service.store_key(content1)
        self.service.store_key(content2)
        
        stats = self.service.get_cache_stats()
        assert stats["total_keys"] == 2
        assert stats["cache_size"] == 2

    def test_concurrent_duplicate_detection(self):
        """Test that concurrent duplicate detection works correctly."""
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        # Simulate concurrent access
        assert not self.service.is_duplicate(content)
        
        # Store the key
        key = self.service.store_key(content)
        
        # Immediately check for duplicate
        assert self.service.is_duplicate(content)
        
        # Check that the key is the same
        assert key == self.service.generate_key(content)

    def test_ttl_edge_cases(self):
        """Test TTL edge cases."""
        # Clear any existing cache first
        self.service._cache.clear()
        
        content = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        # Test with zero TTL - should not store the key
        self.service.store_key(content, ttl_seconds=0)
        assert not self.service.is_duplicate(content)  # Should not be duplicate since not stored
        
        # Test with negative TTL - should not store the key
        self.service.store_key(content, ttl_seconds=-1)
        assert not self.service.is_duplicate(content)  # Should not be duplicate since not stored
        
        # Test with valid TTL - should store and be duplicate
        self.service.store_key(content, ttl_seconds=1)
        assert self.service.is_duplicate(content)  # Should be duplicate

    def test_large_content_handling(self):
        """Test handling of large content."""
        # Create large content
        large_content = "date:25/08/25 logged by: Trevor\n" + "Cement, 50\n" * 1000
        
        # Should still work
        key = self.service.store_key(large_content)
        assert len(key) == 64
        
        # Should be duplicate
        assert self.service.is_duplicate(large_content)

    def test_special_characters_in_content(self):
        """Test handling of special characters in content."""
        special_content = "date:25/08/25 logged by: Trevor\nCement & Steel, 50\nSpecial: chars!@#$%^&*()"
        
        key = self.service.store_key(special_content)
        assert len(key) == 64
        
        # Should be duplicate
        assert self.service.is_duplicate(special_content)

    def test_unicode_content_handling(self):
        """Test handling of unicode content."""
        unicode_content = "date:25/08/25 logged by: Trevor\nCafé, 50\nRésumé, 25"
        
        key = self.service.store_key(unicode_content)
        assert len(key) == 64
        
        # Should be duplicate
        assert self.service.is_duplicate(unicode_content)
