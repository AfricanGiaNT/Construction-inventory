"""Stock query service for fuzzy search and stock information retrieval."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any
from difflib import SequenceMatcher

from schemas import Item, StockMovement, PaginatedSearchResults
from airtable_client import AirtableClient
from services.category_parser import category_parser

logger = logging.getLogger(__name__)


class StockQueryService:
    """Service for fuzzy searching items and retrieving stock information."""
    
    def __init__(self, airtable_client: AirtableClient):
        """Initialize the stock query service."""
        self.airtable = airtable_client
        self._search_cache: Dict[str, Tuple[List[Item], datetime]] = {}
        self._cache_ttl = timedelta(days=7)  # 7 days cache as requested
        self._pagination_cache: Dict[str, PaginatedSearchResults] = {}
        self._pagination_ttl = timedelta(minutes=10)  # 10 minutes for pagination state
        
    def _calculate_similarity(self, query: str, item_name: str) -> float:
        """
        Calculate similarity between query and item name using word-level matching.
        
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
        
        # Split into words for word-level matching
        query_words = [word.strip() for word in query_lower.split() if word.strip()]
        item_words = [word.strip() for word in item_lower.split() if word.strip()]
        
        if not query_words or not item_words:
            return 0.0
        
        # Check for exact word matches first
        exact_word_matches = 0
        partial_word_matches = 0
        
        for query_word in query_words:
            # Check for exact word match
            if query_word in item_words:
                exact_word_matches += 1
            else:
                # Check for partial word match (query word is substring of any item word)
                for item_word in item_words:
                    if query_word in item_word or item_word in query_word:
                        partial_word_matches += 1
                        break
        
        # Calculate base score based on word matches
        total_query_words = len(query_words)
        exact_match_ratio = exact_word_matches / total_query_words
        partial_match_ratio = partial_word_matches / total_query_words
        
        # Base score: exact matches are worth more than partial matches
        base_score = (exact_match_ratio * 0.8) + (partial_match_ratio * 0.4)
        
        # Require at least one meaningful match
        if exact_word_matches == 0 and partial_word_matches == 0:
            return 0.0
        
        # Boost for items that start with the query
        if item_lower.startswith(query_lower):
            base_score += 0.2
        
        # Boost for items that contain the full query as substring
        if query_lower in item_lower:
            base_score += 0.1
        
        # Boost for items where all query words are found
        if exact_word_matches == total_query_words:
            base_score += 0.1
        
        # Cap at 1.0
        return min(base_score, 1.0)
    
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
            limit: Maximum number of results to return (now respects the limit parameter)
            
        Returns:
            List of matching items, ranked by similarity
        """
        try:
            # Check cache first
            cache_key = query.lower().strip()
            if cache_key in self._search_cache:
                cached_items, cache_time = self._search_cache[cache_key]
                if datetime.now() - cache_time < self._cache_ttl:
                    logger.info(f"Using cached results for query: '{query}'")
                    return cached_items[:limit]  # Return up to the requested limit
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
            
            # Filter out very low similarity scores (below 0.5 for better precision)
            filtered_items = [(item, score) for item, score in scored_items if score >= 0.5]
            
            # Take results up to the requested limit
            top_results = [item for item, score in filtered_items[:limit]]
            
            # Cache the results
            self._search_cache[cache_key] = (top_results, datetime.now())
            
            logger.info(f"Fuzzy search for '{query}' returned {len(top_results)} results (limit: {limit})")
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
            
            # Filter out very low similarity scores (below 0.5 for better precision)
            filtered_items = [(item, score) for item, score in scored_items if score >= 0.5]
            
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
    
    async def get_paginated_search_results(self, query: str, page: int = 1, results_per_page: int = 5) -> PaginatedSearchResults:
        """
        Get paginated search results for a query.
        
        Args:
            query: Search query string
            page: Page number (1-based)
            results_per_page: Number of results per page
            
        Returns:
            PaginatedSearchResults object with pagination metadata
        """
        try:
            # Generate cache key for pagination state
            query_hash = self._generate_query_hash(query)
            cache_key = f"pagination_{query_hash}"
            
            # Check if we have cached pagination state
            if cache_key in self._pagination_cache:
                cached_results = self._pagination_cache[cache_key]
                if datetime.now() - cached_results.cache_timestamp < self._pagination_ttl:
                    # Update current page and return
                    cached_results.current_page = page
                    logger.info(f"Using cached pagination state for query: '{query}', page: {page}")
                    return cached_results
                else:
                    # Cache expired, remove it
                    del self._pagination_cache[cache_key]
            
            # Get all matching results
            all_results = await self._get_all_matching_results(query)
            total_count = len(all_results)
            total_pages = (total_count + results_per_page - 1) // results_per_page  # Ceiling division
            
            # Validate page number
            if page < 1:
                page = 1
            elif page > total_pages and total_pages > 0:
                page = total_pages
            
            # Create paginated results object
            paginated_results = PaginatedSearchResults(
                query=query,
                all_results=all_results,
                current_page=page,
                results_per_page=results_per_page,
                total_pages=total_pages,
                total_count=total_count,
                cache_timestamp=datetime.now(),
                cache_key=cache_key,
                query_hash=query_hash
            )
            
            # Cache the pagination state
            self._pagination_cache[cache_key] = paginated_results
            
            logger.info(f"Created pagination state for query: '{query}', page: {page}/{total_pages}, total: {total_count}")
            return paginated_results
            
        except Exception as e:
            logger.error(f"Error getting paginated search results for '{query}': {e}")
            # Return empty results on error
            return PaginatedSearchResults(
                query=query,
                all_results=[],
                current_page=1,
                results_per_page=results_per_page,
                total_pages=0,
                total_count=0,
                cache_timestamp=datetime.now(),
                cache_key="",
                query_hash=""
            )
    
    async def get_search_results_page(self, query: str, page: int) -> List[Item]:
        """
        Get a specific page of search results.
        
        Args:
            query: Search query string
            page: Page number (1-based)
            
        Returns:
            List of items for the requested page
        """
        try:
            paginated_results = await self.get_paginated_search_results(query, page)
            
            # Calculate start and end indices for the page
            start_idx = (page - 1) * paginated_results.results_per_page
            end_idx = start_idx + paginated_results.results_per_page
            
            # Return the items for this page
            page_items = paginated_results.all_results[start_idx:end_idx]
            
            logger.info(f"Retrieved page {page} for query '{query}': {len(page_items)} items")
            return page_items
            
        except Exception as e:
            logger.error(f"Error getting search results page for '{query}', page {page}: {e}")
            return []
    
    async def _get_all_matching_results(self, query: str) -> List[Item]:
        """
        Get all matching results for a query (internal method).
        
        Args:
            query: Search query string
            
        Returns:
            List of all matching items
        """
        try:
            # Get all items from Airtable
            all_items = await self.airtable.get_all_items()
            if not all_items:
                logger.warning("No items found in database")
                return []
            
            # Rank items by similarity
            scored_items = self._rank_search_results(query, all_items)
            
            # Filter out very low similarity scores (below 0.5 for better precision)
            filtered_items = [(item, score) for item, score in scored_items if score >= 0.5]
            
            # Return all matching items
            matching_items = [item for item, score in filtered_items]
            
            logger.info(f"Found {len(matching_items)} matching items for query: '{query}'")
            return matching_items
            
        except Exception as e:
            logger.error(f"Error getting all matching results for '{query}': {e}")
            return []
    
    def _generate_query_hash(self, query: str) -> str:
        """
        Generate a hash for the query to use as cache key.
        
        Args:
            query: Search query string
            
        Returns:
            Hash string for the query
        """
        import hashlib
        return hashlib.md5(query.lower().strip().encode()).hexdigest()[:8]
    
    def clear_cache(self):
        """Clear the search cache."""
        self._search_cache.clear()
        logger.info("Search cache cleared")
    
    def clear_pagination_cache(self):
        """Clear the pagination cache."""
        self._pagination_cache.clear()
        logger.info("Pagination cache cleared")
    
    def clear_all_caches(self):
        """Clear both search and pagination caches."""
        self.clear_cache()
        self.clear_pagination_cache()
        logger.info("All caches cleared")
    
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
        search_expired_entries = 0
        search_valid_entries = 0
        
        for _, cache_time in self._search_cache.values():
            if now - cache_time < self._cache_ttl:
                search_valid_entries += 1
            else:
                search_expired_entries += 1
        
        # Pagination cache stats
        pagination_expired_entries = 0
        pagination_valid_entries = 0
        
        for paginated_results in self._pagination_cache.values():
            if now - paginated_results.cache_timestamp < self._pagination_ttl:
                pagination_valid_entries += 1
            else:
                pagination_expired_entries += 1
        
        return {
            "search_cache": {
                "total_entries": len(self._search_cache),
                "valid_entries": search_valid_entries,
                "expired_entries": search_expired_entries,
                "cache_ttl_days": self._cache_ttl.days
            },
            "pagination_cache": {
                "total_entries": len(self._pagination_cache),
                "valid_entries": pagination_valid_entries,
                "expired_entries": pagination_expired_entries,
                "cache_ttl_minutes": self._pagination_ttl.total_seconds() / 60
            }
        }
    
    async def search_by_category(self, category_query: str, limit: int = 10) -> List[Item]:
        """
        Search for items by category.
        
        Args:
            category_query: Category to search for (can be partial)
            limit: Maximum number of results to return
            
        Returns:
            List of items in the specified category
        """
        try:
            # First, search for matching categories
            matching_categories = category_parser.search_categories(category_query)
            
            if not matching_categories:
                logger.info(f"No categories found matching '{category_query}'")
                return []
            
            # Get all items from Airtable
            all_items = await self.airtable.get_all_items()
            if not all_items:
                return []
            
            # Filter items by matching categories
            category_items = []
            for item in all_items:
                if item.category and any(cat.lower() in item.category.lower() for cat in matching_categories):
                    category_items.append(item)
            
            # Sort by name for consistent results
            category_items.sort(key=lambda x: x.name.lower())
            
            # Limit results
            return category_items[:limit]
            
        except Exception as e:
            logger.error(f"Error searching by category '{category_query}': {e}")
            return []
    
    async def get_items_by_category(self, category: str) -> List[Item]:
        """
        Get all items in a specific category.
        
        Args:
            category: Exact category name
            
        Returns:
            List of items in the category
        """
        try:
            # Validate the category
            if not category_parser.validate_category(category):
                logger.warning(f"Invalid category: {category}")
                return []
            
            # Get all items from Airtable
            all_items = await self.airtable.get_all_items()
            if not all_items:
                return []
            
            # Filter items by exact category match
            category_items = [
                item for item in all_items 
                if item.category and item.category.lower() == category.lower()
            ]
            
            # Sort by name for consistent results
            category_items.sort(key=lambda x: x.name.lower())
            
            return category_items
            
        except Exception as e:
            logger.error(f"Error getting items by category '{category}': {e}")
            return []
    
    async def get_low_stock_by_category(self, category: str = None) -> List[Item]:
        """
        Get low stock items, optionally filtered by category.
        
        Args:
            category: Optional category to filter by
            
        Returns:
            List of low stock items
        """
        try:
            # Get low stock items
            low_stock_items = await self.airtable.get_low_stock_items()
            
            if not category:
                return low_stock_items
            
            # Filter by category if specified
            category_low_stock = [
                item for item in low_stock_items
                if item.category and item.category.lower() == category.lower()
            ]
            
            return category_low_stock
            
        except Exception as e:
            logger.error(f"Error getting low stock by category '{category}': {e}")
            return []
    
    async def get_category_overview(self) -> Dict[str, Dict[str, Any]]:
        """
        Get an overview of all categories with item counts and stock levels.
        
        Returns:
            Dictionary with category information
        """
        try:
            # Get all items
            all_items = await self.airtable.get_all_items()
            if not all_items:
                return {}
            
            # Group items by category
            category_stats = {}
            for item in all_items:
                category = item.category or "Uncategorized"
                
                if category not in category_stats:
                    category_stats[category] = {
                        "item_count": 0,
                        "total_stock": 0.0,
                        "low_stock_count": 0,
                        "items": []
                    }
                
                category_stats[category]["item_count"] += 1
                category_stats[category]["total_stock"] += item.on_hand
                category_stats[category]["items"].append(item.name)
                
                # Check if item is low stock
                if item.threshold and item.on_hand <= item.threshold:
                    category_stats[category]["low_stock_count"] += 1
            
            return category_stats
            
        except Exception as e:
            logger.error(f"Error getting category overview: {e}")
            return {}
