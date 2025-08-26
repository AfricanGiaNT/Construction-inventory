"""Persistent idempotency service for storing keys in Airtable."""

import hashlib
import logging
import time
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PersistentIdempotencyKey:
    """Persistent idempotency key with Airtable integration."""
    key: str
    created_at: datetime
    ttl_seconds: int = 3600  # Default 1 hour TTL


class PersistentIdempotencyService:
    """Service for managing persistent idempotency keys in Airtable."""
    
    def __init__(self, airtable_client, default_ttl_seconds: int = 3600):
        """Initialize the persistent idempotency service."""
        self.airtable = airtable_client
        self.default_ttl = default_ttl_seconds
        self._cache: Dict[str, PersistentIdempotencyKey] = {}
        self._cache_loaded = False
    
    def generate_key(self, content: str) -> str:
        """Generate a hash-based idempotency key from content."""
        # Normalize content to ensure consistent hashing
        normalized = content.strip().lower()
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    
    async def is_duplicate(self, content: str, ttl_seconds: Optional[int] = None) -> bool:
        """Check if content is a duplicate within TTL, checking both cache and Airtable."""
        key = self.generate_key(content)
        
        # First check local cache
        if key in self._cache:
            existing = self._cache[key]
            # Use the stored TTL from the key object, not the parameter
            if time.time() - existing.created_at.timestamp() < existing.ttl_seconds:
                logger.info(f"Duplicate request detected in cache for key: {key[:8]}...")
                return True
            else:
                # TTL expired, remove from cache
                del self._cache[key]
                logger.info(f"Expired idempotency key removed from cache: {key[:8]}...")
        
        # Check Airtable for persistent keys
        try:
            await self._load_cache_if_needed()
            
            # Check if key exists in Airtable and is still valid
            if key in self._cache:
                existing = self._cache[key]
                # Use the stored TTL from the key object, not the parameter
                if time.time() - existing.created_at.timestamp() < existing.ttl_seconds:
                    logger.info(f"Duplicate request detected in Airtable for key: {key[:8]}...")
                    return True
                else:
                    # TTL expired, remove from Airtable and cache
                    await self._remove_key_from_airtable(key)
                    if key in self._cache:
                        del self._cache[key]
                    logger.info(f"Expired idempotency key removed from Airtable: {key[:8]}...")
            
        except Exception as e:
            logger.error(f"Error checking persistent idempotency: {e}")
            # Fall back to cache-only behavior on error
        
        return False
    
    async def store_key(self, content: str, ttl_seconds: Optional[int] = None) -> str:
        """Store an idempotency key in both cache and Airtable."""
        key = self.generate_key(content)
        # Handle TTL logic properly - None means use default, 0 means immediate expiration
        if ttl_seconds is None:
            ttl = self.default_ttl
        else:
            ttl = ttl_seconds
        
        # Handle zero or negative TTL as immediate expiration
        if ttl <= 0:
            logger.info(f"Invalid TTL {ttl} specified for key: {key[:8]}..., not storing")
            return key
        
        # Store in local cache
        now = datetime.now()
        self._cache[key] = PersistentIdempotencyKey(
            key=key,
            created_at=now,
            ttl_seconds=ttl
        )
        
        # Store in Airtable
        try:
            await self._store_key_in_airtable(key, now, ttl)
            logger.info(f"Stored persistent idempotency key: {key[:8]}... with TTL {ttl}s")
        except Exception as e:
            logger.error(f"Failed to store key in Airtable: {e}")
            # Continue with cache-only behavior on error
        
        return key
    
    async def remove_key(self, content: str) -> bool:
        """Remove an idempotency key from both cache and Airtable."""
        key = self.generate_key(content)
        removed = False
        
        # Remove from cache
        if key in self._cache:
            del self._cache[key]
            removed = True
        
        # Remove from Airtable
        try:
            await self._remove_key_from_airtable(key)
            logger.info(f"Removed persistent idempotency key: {key[:8]}...")
        except Exception as e:
            logger.error(f"Failed to remove key from Airtable: {e}")
        
        return removed
    
    async def cleanup_expired(self) -> int:
        """Clean up expired keys from both cache and Airtable."""
        current_time = time.time()
        expired_keys = [
            key for key, key_data in self._cache.items()
            if current_time - key_data.created_at.timestamp() >= key_data.ttl_seconds
        ]
        
        # Remove from cache
        for key in expired_keys:
            del self._cache[key]
        
        # Remove from Airtable
        for key in expired_keys:
            try:
                await self._remove_key_from_airtable(key)
            except Exception as e:
                logger.error(f"Failed to remove expired key from Airtable: {e}")
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired persistent idempotency keys")
        
        return len(expired_keys)
    
    async def _load_cache_if_needed(self):
        """Load idempotency keys from Airtable if not already loaded."""
        if self._cache_loaded:
            return
        
        try:
            # Load existing keys from Airtable
            keys = await self._load_keys_from_airtable()
            
            # Filter out expired keys
            current_time = time.time()
            valid_keys = [
                key_data for key_data in keys
                if current_time - key_data.created_at.timestamp() < key_data.ttl_seconds
            ]
            
            # Update cache
            for key_data in valid_keys:
                self._cache[key_data.key] = key_data
            
            self._cache_loaded = True
            logger.info(f"Loaded {len(valid_keys)} valid idempotency keys from Airtable")
            
        except Exception as e:
            logger.error(f"Failed to load idempotency keys from Airtable: {e}")
            # Continue with cache-only behavior
    
    async def _store_key_in_airtable(self, key: str, created_at: datetime, ttl_seconds: int):
        """Store a key in the Bot Meta Airtable table."""
        try:
            # This would create/update a record in the Bot Meta table
            # For now, we'll log the intention - actual implementation depends on Airtable schema
            logger.info(f"Would store key in Airtable: {key[:8]}..., created_at={created_at}, ttl={ttl_seconds}s")
            
            # TODO: Implement actual Airtable storage when schema is ready
            # await self.airtable.create_or_update_bot_meta_record(key, created_at, ttl_seconds)
            
        except Exception as e:
            logger.error(f"Error storing key in Airtable: {e}")
            raise
    
    async def _remove_key_from_airtable(self, key: str):
        """Remove a key from the Bot Meta Airtable table."""
        try:
            # This would delete a record from the Bot Meta table
            # For now, we'll log the intention - actual implementation depends on Airtable schema
            logger.info(f"Would remove key from Airtable: {key[:8]}...")
            
            # TODO: Implement actual Airtable deletion when schema is ready
            # await self.airtable.delete_bot_meta_record(key)
            
        except Exception as e:
            logger.error(f"Error removing key from Airtable: {e}")
            raise
    
    async def _load_keys_from_airtable(self) -> List[PersistentIdempotencyKey]:
        """Load all idempotency keys from the Bot Meta Airtable table."""
        try:
            # This would load all records from the Bot Meta table
            # For now, we'll return an empty list - actual implementation depends on Airtable schema
            logger.info("Would load idempotency keys from Airtable")
            
            # TODO: Implement actual Airtable loading when schema is ready
            # records = await self.airtable.get_all_bot_meta_records()
            # return [PersistentIdempotencyKey(...) for record in records]
            
            return []
            
        except Exception as e:
            logger.error(f"Error loading keys from Airtable: {e}")
            raise
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "total_keys": len(self._cache),
            "cache_size": len(self._cache),
            "persistent_enabled": True
        }
