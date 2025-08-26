"""Idempotency service for preventing duplicate inventory operations."""

import hashlib
import logging
import time
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class IdempotencyKey:
    """Idempotency key with TTL information."""
    key: str
    created_at: float
    ttl_seconds: int = 3600  # Default 1 hour TTL


class IdempotencyService:
    """Service for managing idempotency keys to prevent duplicate operations."""
    
    def __init__(self, default_ttl_seconds: int = 3600):
        """Initialize the idempotency service."""
        self.default_ttl = default_ttl_seconds
        self._cache: Dict[str, IdempotencyKey] = {}
    
    def generate_key(self, content: str) -> str:
        """Generate a hash-based idempotency key from content."""
        # Normalize content to ensure consistent hashing
        normalized = content.strip().lower()
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    
    def is_duplicate(self, content: str, ttl_seconds: Optional[int] = None) -> bool:
        """Check if content is a duplicate within TTL."""
        key = self.generate_key(content)
        
        if key in self._cache:
            existing = self._cache[key]
            # Use the stored TTL from the key object, not the parameter
            if time.time() - existing.created_at < existing.ttl_seconds:
                logger.info(f"Duplicate request detected for key: {key[:8]}...")
                return True
            else:
                # TTL expired, remove from cache
                del self._cache[key]
                logger.info(f"Expired idempotency key removed: {key[:8]}...")
        
        return False
    
    def store_key(self, content: str, ttl_seconds: Optional[int] = None) -> str:
        """Store an idempotency key and return the key."""
        key = self.generate_key(content)
        
        # Handle TTL logic properly - None means use default, 0 means immediate expiration
        if ttl_seconds is None:
            ttl = self.default_ttl
        else:
            ttl = ttl_seconds
        
        # Handle zero or negative TTL as immediate expiration
        if ttl <= 0:
            # Don't store the key at all, just return the generated key
            logger.info(f"Invalid TTL {ttl} specified for key: {key[:8]}..., not storing")
            return key
        
        self._cache[key] = IdempotencyKey(
            key=key,
            created_at=time.time(),
            ttl_seconds=ttl
        )
        
        logger.info(f"Stored idempotency key: {key[:8]}... with TTL {ttl}s")
        return key
    
    def remove_key(self, content: str) -> bool:
        """Remove an idempotency key if it exists."""
        key = self.generate_key(content)
        if key in self._cache:
            del self._cache[key]
            logger.info(f"Removed idempotency key: {key[:8]}...")
            return True
        return False
    
    def cleanup_expired(self) -> int:
        """Clean up expired keys and return count of removed keys."""
        current_time = time.time()
        expired_keys = [
            key for key, key_data in self._cache.items()
            if current_time - key_data.created_at >= key_data.ttl_seconds
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired idempotency keys")
        
        return len(expired_keys)
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "total_keys": len(self._cache),
            "cache_size": len(self._cache)
        }
