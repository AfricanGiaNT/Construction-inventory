"""Duplicate detection service for the Construction Inventory Bot."""

import logging
import re
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
from collections import defaultdict

from airtable_client import AirtableClient
from schemas import StockMovement, Item

logger = logging.getLogger(__name__)


@dataclass
class PotentialDuplicate:
    """Represents a potential duplicate entry."""
    item_name: str
    quantity: float
    unit: str
    similarity_score: float
    movement_id: str
    timestamp: datetime
    location: Optional[str] = None
    category: Optional[str] = None
    user_name: str = ""


@dataclass
class DuplicateDetectionResult:
    """Result of duplicate detection analysis."""
    has_duplicates: bool
    potential_duplicates: List[PotentialDuplicate]
    new_entries: List[Any]  # Will be InventoryEntry when integrated
    requires_confirmation: bool


@dataclass
class MovementDuplicateResult:
    """Result of duplicate detection for a single movement."""
    movement_id: str
    has_duplicates: bool
    potential_duplicates: List[PotentialDuplicate]
    stock_check_results: Optional[Dict[str, Any]] = None


@dataclass
class MovementDuplicateDetectionResult:
    """Result of duplicate detection for multiple movements."""
    movement_results: List[MovementDuplicateResult]
    has_any_duplicates: bool
    total_movements: int
    total_duplicates: int
    requires_stock_check: bool


class DuplicateDetectionService:
    """Service for detecting potential duplicate inventory entries."""
    
    def __init__(self, airtable_client: AirtableClient):
        """Initialize the duplicate detection service."""
        self.airtable = airtable_client
        self.similarity_threshold = 0.7  # Higher than search (0.5) for duplicates
        self.cache_ttl = timedelta(minutes=30)
        self._cache = {}
        self._cache_timestamps = {}
        
        # Common words to ignore in keyword extraction
        self.common_words = {
            'the', 'and', 'or', 'of', 'in', 'on', 'at', 'to', 'for', 'with', 'by',
            'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'
        }
    
    async def find_potential_duplicates(self, item_name: str, quantity: float) -> List[PotentialDuplicate]:
        """
        Find potential duplicates for a given item.
        
        Args:
            item_name: Name of the item to check for duplicates
            quantity: Quantity of the item
            
        Returns:
            List of potential duplicates with similarity scores >= threshold
        """
        try:
            # Get all items from the Items table
            items = await self._get_all_items()
            
            potential_duplicates = []
            
            for item in items:
                # Skip if it's the same item name (exact match)
                if item.name.lower() == item_name.lower():
                    continue
                
                # Calculate similarity score
                similarity = self._calculate_duplicate_similarity(item_name, item.name)
                
                if similarity >= self.similarity_threshold:
                    duplicate = PotentialDuplicate(
                        item_name=item.name,
                        quantity=item.on_hand,
                        unit=item.unit_type or "piece",
                        similarity_score=similarity,
                        movement_id=item.name,  # Use item name as identifier
                        timestamp=datetime.now(),  # Items don't have timestamps, use current time
                        location=item.location,
                        category=item.category,
                        user_name="System"  # Items don't have user names
                    )
                    potential_duplicates.append(duplicate)
            
            # Sort by similarity score (highest first)
            potential_duplicates.sort(key=lambda x: x.similarity_score, reverse=True)
            
            return potential_duplicates
            
        except Exception as e:
            logger.error(f"Error finding potential duplicates for '{item_name}': {e}")
            return []
    
    def _calculate_duplicate_similarity(self, new_item: str, existing_item: str) -> float:
        """
        Calculate similarity for duplicate detection.
        
        Enhanced algorithm for duplicate detection:
        - Higher threshold (0.7) than search (0.5)
        - Exact keyword matching with up to 1 missing keyword
        - Order independence: "50kgs bags cement" matches "cement 50kgs bags"
        - No partial word matches, only exact word matches
        - Quantity similarity validation
        
        Args:
            new_item: New item name to check
            existing_item: Existing item name to compare against
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        try:
            # Normalize text
            new_normalized = self._normalize_text(new_item)
            existing_normalized = self._normalize_text(existing_item)
            
            # Extract keywords (ignore common words and quantities)
            new_keywords = self._extract_keywords_without_quantities(new_item)
            existing_keywords = self._extract_keywords_without_quantities(existing_item)
            
            if not new_keywords or not existing_keywords:
                return 0.0
            
            # Extract quantities separately
            new_qty, new_unit = self._normalize_quantity(new_item)
            existing_qty, existing_unit = self._normalize_quantity(existing_item)
            
            # Check exact keyword matches
            new_keywords_set = set(new_keywords)
            existing_keywords_set = set(existing_keywords)
            exact_matches = len(new_keywords_set & existing_keywords_set)
            total_keywords = len(new_keywords)
            
            # Allow up to 1 missing keyword, but require at least 1 keyword to match
            if exact_matches >= total_keywords - 1 and exact_matches >= 1:
                # Check quantity similarity (must be same or very close)
                if self._quantities_similar(new_qty, existing_qty):
                    # Base score from keyword matches
                    base_score = 0.7 + (exact_matches / total_keywords) * 0.3
                    
                    # Boost for exact text match
                    if new_normalized == existing_normalized:
                        base_score = 1.0
                    
                    # Boost for items that start with the same keywords
                    if new_keywords[0] == existing_keywords[0]:
                        base_score += 0.1
                    
                    return min(base_score, 1.0)
                else:
                    # If quantities are very different, still allow but with lower score
                    if exact_matches >= total_keywords:  # All keywords match
                        return 0.6  # Lower score for quantity mismatch
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating similarity between '{new_item}' and '{existing_item}': {e}")
            return 0.0
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract meaningful keywords from item names.
        
        Args:
            text: Text to extract keywords from
            
        Returns:
            List of keywords (lowercase, no common words)
        """
        # Normalize text first to handle special characters
        normalized = self._normalize_text(text)
        
        # Split into words and clean, preserving decimal numbers
        words = re.findall(r'\b\w+(?:\.\w+)?\b', normalized)
        
        # Filter out common words and short words
        keywords = [
            word for word in words 
            if word not in self.common_words and len(word) > 1
        ]
        
        return keywords
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        # Convert to lowercase and strip whitespace
        normalized = text.lower().strip()
        
        # Replace special characters with spaces
        normalized = re.sub(r'[-_]', ' ', normalized)
        
        # Remove extra spaces
        normalized = re.sub(r'\s+', ' ', normalized)
        
        return normalized
    
    def _normalize_quantity(self, text: str) -> Tuple[float, str]:
        """
        Extract and normalize quantity and unit from text.
        
        Args:
            text: Text containing quantity and unit
            
        Returns:
            Tuple of (quantity, unit)
        """
        try:
            # Look for quantity patterns like "50", "50.5", "50kgs", "50 kgs", "50kg"
            quantity_pattern = r'(\d+(?:\.\d+)?)\s*([a-zA-Z]*)'
            matches = re.findall(quantity_pattern, text)
            
            if matches:
                # Take the first (usually most significant) quantity found
                qty_str, unit = matches[0]
                quantity = float(qty_str)
                
                # Normalize unit
                unit = unit.lower().strip()
                if not unit:
                    unit = "piece"  # Default unit
                
                return quantity, unit
            
            # If no quantity found, try to extract just numbers
            number_pattern = r'(\d+(?:\.\d+)?)'
            number_matches = re.findall(number_pattern, text)
            
            if number_matches:
                quantity = float(number_matches[0])
                return quantity, "piece"
            
            return 0.0, "piece"
            
        except (ValueError, IndexError) as e:
            logger.warning(f"Error extracting quantity from '{text}': {e}")
            return 0.0, "piece"
    
    def _extract_keywords_without_quantities(self, text: str) -> List[str]:
        """
        Extract keywords excluding quantity information.
        
        Args:
            text: Text to extract keywords from
            
        Returns:
            List of keywords without quantity information
        """
        # Normalize text first
        normalized = self._normalize_text(text)
        
        # Remove quantity patterns to get clean keywords
        # Remove patterns like "50kgs", "50 kgs", but keep standalone numbers that might be specifications
        unit_words = {'kgs', 'kg', 'lbs', 'lb', 'tons', 'ton', 'pieces', 'piece', 'units', 'unit', 
                     'bags', 'bag', 'cans', 'can', 'bottles', 'bottle', 'meters', 'meter', 'm', 
                     'liters', 'liter', 'ltrs', 'ltr', 'gallons', 'gallon', 'feet', 'foot', 'ft'}
        
        # First, remove quantity+unit patterns like "50kgs", "50 kgs"
        cleaned = normalized
        for unit in unit_words:
            # Remove patterns like "50kgs", "50 kgs"
            cleaned = re.sub(rf'\b\d+(?:\.\d+)?\s*{unit}\b', '', cleaned)
        
        # Split into words
        words = re.findall(r'\b\w+(?:\.\w+)?\b', cleaned)
        
        # Filter out common words and short words
        keywords = [
            word for word in words 
            if word not in self.common_words and len(word) > 1
        ]
        
        return keywords
    
    def _quantities_similar(self, qty1: float, qty2: float, tolerance: float = 0.1) -> bool:
        """
        Check if two quantities are similar within tolerance.
        
        Args:
            qty1: First quantity
            qty2: Second quantity
            tolerance: Tolerance as percentage (0.1 = 10%)
            
        Returns:
            True if quantities are similar
        """
        if qty1 == 0 and qty2 == 0:
            return True
        
        if qty1 == 0 or qty2 == 0:
            return False
        
        # Calculate percentage difference
        diff = abs(qty1 - qty2) / max(qty1, qty2)
        return diff <= tolerance
    
    async def _get_all_items(self) -> List[Item]:
        """
        Get all items from the Items table for duplicate detection.
        
        Returns:
            List of all items
        """
        cache_key = "all_items"
        now = datetime.now()
        
        # Check cache first
        if cache_key in self._cache:
            cache_time = self._cache_timestamps.get(cache_key)
            if cache_time and (now - cache_time) < self.cache_ttl:
                return self._cache[cache_key]
        
        try:
            # Get all items from the Items table
            items = await self.airtable.get_all_items()
            
            # Update cache
            self._cache[cache_key] = items
            self._cache_timestamps[cache_key] = now
            
            return items
            
        except Exception as e:
            logger.error(f"Error getting all items: {e}")
            return []
    
    async def check_entries_for_duplicates(self, entries: List[Any]) -> DuplicateDetectionResult:
        """
        Check a list of inventory entries for potential duplicates.
        
        Args:
            entries: List of inventory entries to check
            
        Returns:
            DuplicateDetectionResult with analysis
        """
        all_duplicates = []
        has_duplicates = False
        
        for entry in entries:
            # Find duplicates for this entry
            duplicates = await self.find_potential_duplicates(entry.item_name, entry.quantity)
            
            if duplicates:
                all_duplicates.extend(duplicates)
                has_duplicates = True
        
        return DuplicateDetectionResult(
            has_duplicates=has_duplicates,
            potential_duplicates=all_duplicates,
            new_entries=entries,
            requires_confirmation=has_duplicates
        )
    
    async def find_potential_duplicates_for_movements(self, movements: List[StockMovement]) -> Dict[str, MovementDuplicateResult]:
        """
        Find potential duplicates for a list of movements.
        
        Args:
            movements: List of StockMovement objects to check for duplicates
            
        Returns:
            Dictionary mapping movement_id to MovementDuplicateResult
        """
        try:
            results = {}
            
            for movement in movements:
                # Find duplicates for this movement
                duplicates = await self.find_potential_duplicates(movement.item_name, movement.quantity)
                
                # If duplicates found, update the movement name to match the best duplicate
                if duplicates:
                    # Find the best duplicate (highest similarity score)
                    best_duplicate = max(duplicates, key=lambda d: d.similarity_score)
                    
                    # Update the movement name to match the existing item name
                    original_name = movement.item_name
                    movement.item_name = best_duplicate.item_name
                    
                    logger.info(f"Updated movement name from '{original_name}' to '{best_duplicate.item_name}' (similarity: {best_duplicate.similarity_score:.2f})")
                
                # Create MovementDuplicateResult
                result = MovementDuplicateResult(
                    movement_id=movement.id,
                    has_duplicates=len(duplicates) > 0,
                    potential_duplicates=duplicates,
                    stock_check_results=None  # TODO: Implement stock check for OUT movements
                )
                
                results[movement.id] = result
                
            return results
            
        except Exception as e:
            logger.error(f"Error finding potential duplicates for movements: {e}")
            return {}
    
    def clear_cache(self):
        """Clear the internal cache."""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("Duplicate detection cache cleared")
