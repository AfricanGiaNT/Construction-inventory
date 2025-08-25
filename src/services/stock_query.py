"""Stock query service for fuzzy search and stock information retrieval."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any
from difflib import SequenceMatcher

from ..schemas import Item, StockMovement
from ..airtable_client import AirtableClient

logger = logging.getLogger(__name__)


class StockQueryService:
    """Service for fuzzy searching items and retrieving stock information."""
    
    def __init__(self, airtable_client: AirtableClient):
        """Initialize the stock query service."""
        self.airtable = airtable_client
        self._search_cache: Dict[str, Tuple[List[Item], datetime]] = {}
        self._cache_ttl = timedelta(days=7)  # 7 days cache as requested
        
    def _calculate_similarity(self, query: str, item_name: str) -> float:
        """
        Calculate similarity between query and item name using SequenceMatcher.
        
        Args:
            query: User's search query
            item_name: Item name from database
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        query_lower = query.lower().strip()
        item_lower = item_name.lower().strip()
        
        # Exact match gets highest score
        if query_lower == item_lower:
            return 1.0
        
        # Partial match (query is substring of item name)
        if query_lower in item_lower:
            return 0.9
        
        # Use SequenceMatcher for fuzzy matching
        similarity = SequenceMatcher(None, query_lower, item_lower).ratio()
        
        # Boost similarity for items that start with the query
        if item_lower.startswith(query_lower):
            similarity += 0.1
            
        # Boost similarity for items that contain all query words
        query_words = query_lower.split()
        if all(word in item_lower for word in query_words):
            similarity += 0.05
            
        return min(similarity, 1.0)
    
    def _rank_search_results(self, query: str, items: List[Item]) -> List[Tuple[Item, float]]:
        """
        Rank search results by similarity score.
        
        Args:
            query: User's search query
            items: List of items to rank
            
        Returns:
            List of (item, similarity_score) tuples, sorted by score descending
        """
        # Calculate similarity scores for all items
        scored_items = []
        for item in items:
            score = self._calculate_similarity(query, item.name)
            scored_items.append((item, score))
        
        # Sort by score descending (highest first)
        scored_items.sort(key=lambda x: x[1], reverse=True)
        
        return scored_items
    
    async def fuzzy_search_items(self, query: str, limit: int = 5) -> List[Item]:
        """
        Perform fuzzy search for items matching the query.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return (ignored, always returns max 3)
            
        Returns:
            List of matching items, ranked by similarity (max 3)
        """
        try:
            # Check cache first
            cache_key = query.lower().strip()
            if cache_key in self._search_cache:
                cached_items, cache_time = self._search_cache[cache_key]
                if datetime.now() - cache_time < self._cache_ttl:
                    logger.info(f"Using cached results for query: '{query}'")
                    return cached_items[:3]  # Always return max 3
                else:
                    # Cache expired, remove it
                    del self._search_cache[cache_key]
            
            # Get all items from Airtable
            all_items = await self.airtable.get_all_items()
            if not all_items:
                logger.warning("No items found in database")
                return []
            
            # Rank items by similarity
            scored_items = self._rank_search_results(query, all_items)
            
            # Filter out very low similarity scores (below 0.3)
            filtered_items = [(item, score) for item, score in scored_items if score >= 0.3]
            
            # Always take top 3 results (ignore limit parameter)
            top_results = [item for item, score in filtered_items[:3]]
            
            # Cache the results
            self._search_cache[cache_key] = (top_results, datetime.now())
            
            logger.info(f"Fuzzy search for '{query}' returned {len(top_results)} results (showing top 3)")
            return top_results
            
        except Exception as e:
            logger.error(f"Error in fuzzy search for '{query}': {e}")
            return []
    
    async def get_total_matching_items_count(self, query: str) -> int:
        """
        Get the total count of items matching the query (before limiting to top 3).
        
        Args:
            query: Search query string
            
        Returns:
            Total count of matching items
        """
        try:
            # Get all items from Airtable
            all_items = await self.airtable.get_all_items()
            if not all_items:
                return 0
            
            # Rank items by similarity
            scored_items = self._rank_search_results(query, all_items)
            
            # Filter out very low similarity scores (below 0.3)
            filtered_items = [(item, score) for item, score in scored_items if score >= 0.3]
            
            return len(filtered_items)
            
        except Exception as e:
            logger.error(f"Error getting total matching items count for '{query}': {e}")
            return 0
    
    async def get_item_details(self, item_name: str) -> Tuple[bool, str, Optional[Item]]:
        """
        Get detailed information for a specific item.
        
        Args:
            item_name: Exact name of the item
            
        Returns:
            Tuple of (success, message, item)
        """
        try:
            item = await self.airtable.get_item(item_name)
            if not item:
                return False, f"Item '{item_name}' not found.", None
            
            return True, f"Found item '{item_name}'", item
            
        except Exception as e:
            logger.error(f"Error getting item details for '{item_name}': {e}")
            return False, f"Error retrieving item details: {str(e)}", None
    
    async def get_pending_movements(self, item_name: str) -> List[StockMovement]:
        """
        Get pending movements for a specific item.
        
        Args:
            item_name: Name of the item
            
        Returns:
            List of pending stock movements
        """
        try:
            # Get all movements for the item
            all_movements = await self.airtable.get_item_movements(item_name, limit=100)
            
            # Filter for pending movements
            pending_movements = [
                movement for movement in all_movements 
                if movement.status == "Pending Approval"
            ]
            
            logger.info(f"Found {len(pending_movements)} pending movements for '{item_name}'")
            return pending_movements
            
        except Exception as e:
            logger.error(f"Error getting pending movements for '{item_name}': {e}")
            return []
    
    async def is_in_pending_batch(self, item_name: str) -> bool:
        """
        Check if an item is part of a pending batch approval.
        
        Args:
            item_name: Name of the item
            
        Returns:
            True if item is in pending batch, False otherwise
        """
        try:
            # Get pending approvals for the item
            pending_approvals = await self.airtable.get_pending_approvals_for_item(item_name)
            
            # Check if any approvals are pending
            has_pending = len(pending_approvals) > 0
            
            logger.info(f"Item '{item_name}' has pending batch: {has_pending}")
            return has_pending
            
        except Exception as e:
            logger.error(f"Error checking pending batch for '{item_name}': {e}")
            return False
    
    async def get_item_last_updated(self, item_name: str) -> Optional[datetime]:
        """
        Get the last time an item was updated.
        
        Args:
            item_name: Name of the item
            
        Returns:
            Last update timestamp or None if not found
        """
        try:
            last_updated = await self.airtable.get_item_last_updated(item_name)
            return last_updated
            
        except Exception as e:
            logger.error(f"Error getting last updated time for '{item_name}': {e}")
            return None
    
    def clear_cache(self):
        """Clear the search cache."""
        self._search_cache.clear()
        logger.info("Search cache cleared")
    
    def invalidate_cache_for_item(self, item_name: str):
        """
        Invalidate cache entries that might contain the specified item.
        This is called when stock levels change to ensure fresh data.
        
        Args:
            item_name: Name of the item that changed
        """
        # Remove cache entries that might be affected
        keys_to_remove = []
        for key in self._search_cache:
            # If the cache key contains the item name or vice versa, invalidate it
            if (item_name.lower() in key.lower() or 
                key.lower() in item_name.lower()):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._search_cache[key]
        
        if keys_to_remove:
            logger.info(f"Invalidated {len(keys_to_remove)} cache entries for item '{item_name}'")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring.
        
        Returns:
            Dictionary with cache statistics
        """
        now = datetime.now()
        expired_entries = 0
        valid_entries = 0
        
        for _, cache_time in self._search_cache.values():
            if now - cache_time < self._cache_ttl:
                valid_entries += 1
            else:
                expired_entries += 1
        
        return {
            "total_entries": len(self._search_cache),
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "cache_ttl_days": self._cache_ttl.days
        }
