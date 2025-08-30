"""Edge case handler service for the Construction Inventory Bot."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, UTC

from schemas import Item
from airtable_client import AirtableClient
from services.category_parser import category_parser

logger = logging.getLogger(__name__)


class EdgeCaseHandler:
    """Service for handling edge cases and complex scenarios in category management."""
    
    def __init__(self, airtable_client: AirtableClient):
        """Initialize the edge case handler."""
        self.airtable = airtable_client
        self.ambiguous_items_cache: Dict[str, Dict[str, Any]] = {}
        self.new_categories_cache: Dict[str, Dict[str, Any]] = {}
    
    async def handle_ambiguous_item(self, item_name: str, detected_categories: List[str]) -> str:
        """
        Handle items that could fit multiple categories.
        
        Args:
            item_name: Name of the ambiguous item
            detected_categories: List of possible categories
            
        Returns:
            Resolved category based on priority rules and context
        """
        try:
            logger.info(f"Handling ambiguous item '{item_name}' with categories: {detected_categories}")
            
            if not detected_categories:
                # No categories detected, create new one
                return self._create_new_category_from_name(item_name)
            
            if len(detected_categories) == 1:
                # Only one category, use it
                return detected_categories[0]
            
            # Multiple categories detected, apply priority rules
            resolved_category = self._apply_priority_rules(item_name, detected_categories)
            
            # Cache the resolution for future reference
            self.ambiguous_items_cache[item_name] = {
                "detected_categories": detected_categories,
                "resolved_category": resolved_category,
                "resolution_method": "priority_rules",
                "timestamp": datetime.now(UTC)
            }
            
            logger.info(f"Resolved ambiguous item '{item_name}' to category: {resolved_category}")
            return resolved_category
            
        except Exception as e:
            logger.error(f"Error handling ambiguous item '{item_name}': {e}")
            # Fallback to creating a new category
            return self._create_new_category_from_name(item_name)
    
    def _apply_priority_rules(self, item_name: str, categories: List[str]) -> str:
        """
        Apply priority rules to resolve category conflicts.
        
        Args:
            item_name: Name of the item
            categories: List of possible categories
            
        Returns:
            Highest priority category
        """
        item_lower = item_name.lower()
        
        # Define priority hierarchy (higher index = higher priority)
        priority_hierarchy = [
            "Safety Equipment",  # Safety items take highest priority
            "Tools",              # Tools are next
            "Electrical",         # Electrical items
            "Plumbing",           # Plumbing items
            "Paint",              # Paint items
            "Carpentry",          # Carpentry items
            "Steel",              # Steel items
            "Construction Materials"  # General construction materials
        ]
        
        # Find the highest priority category that matches
        for priority_cat in priority_hierarchy:
            if any(priority_cat.lower() in cat.lower() for cat in categories):
                return priority_cat
        
        # If no priority match, use the first category
        return categories[0]
    
    def _create_new_category_from_name(self, item_name: str) -> str:
        """
        Create a new category based on the item name.
        
        Args:
            item_name: Name of the item
            
        Returns:
            New category name
        """
        # Extract descriptive words from item name
        words = item_name.split()
        
        # Filter out common words and numbers
        common_words = {"the", "a", "an", "and", "or", "of", "with", "for", "in", "on", "at", "to", "from"}
        descriptive_words = [word.lower() for word in words if word.lower() not in common_words and not word.isdigit()]
        
        if descriptive_words:
            # Use the most descriptive word as category
            new_category = descriptive_words[0].title()
            
            # Cache the new category
            self.new_categories_cache[new_category] = {
                "created_from": item_name,
                "timestamp": datetime.now(UTC),
                "usage_count": 1
            }
            
            logger.info(f"Created new category '{new_category}' from item '{item_name}'")
            return new_category
        else:
            # Fallback to generic category
            return "General"
    
    async def validate_category_consistency(self) -> Dict[str, Any]:
        """
        Validate consistency across all categories in the system.
        
        Returns:
            Dictionary with validation results
        """
        try:
            # Get all items
            all_items = await self.airtable.get_all_items()
            if not all_items:
                return {"error": "No items found"}
            
            validation_results = {
                "total_items": len(all_items),
                "categories_found": set(),
                "inconsistencies": [],
                "warnings": [],
                "suggestions": [],
                "timestamp": datetime.now(UTC)
            }
            
            # Analyze each item
            for item in all_items:
                if item.category:
                    validation_results["categories_found"].add(item.category)
                    
                    # Check for potential inconsistencies
                    if self._has_potential_inconsistency(item):
                        validation_results["inconsistencies"].append({
                            "item_name": item.name,
                            "current_category": item.category,
                            "issue": "Potential category mismatch",
                            "suggestion": self._suggest_better_category(item.name, item.category)
                        })
            
            # Check for orphaned categories
            all_categories = category_parser.get_all_categories()
            orphaned_categories = [cat for cat in all_categories if cat not in validation_results["categories_found"]]
            
            if orphaned_categories:
                validation_results["warnings"].append(f"Found {len(orphaned_categories)} categories with no items")
                validation_results["suggestions"].append("Consider removing unused categories")
            
            # Generate suggestions for improvement
            validation_results["suggestions"].extend(self._generate_improvement_suggestions(all_items))
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating category consistency: {e}")
            return {"error": str(e)}
    
    def _has_potential_inconsistency(self, item: Item) -> bool:
        """
        Check if an item has potential category inconsistencies.
        
        Args:
            item: Item to check
            
        Returns:
            True if potential inconsistency found
        """
        if not item.category:
            return False
        
        # Check if the detected category would be different
        detected_category = category_parser.parse_category(item.name)
        
        # Allow for minor variations (e.g., "Paint" vs "Paint > Interior")
        if detected_category.lower() in item.category.lower() or item.category.lower() in detected_category.lower():
            return False
        
        # Check for significant mismatches
        significant_mismatches = [
            ("Paint", "Electrical"),
            ("Electrical", "Plumbing"),
            ("Tools", "Safety Equipment"),
            ("Steel", "Carpentry")
        ]
        
        for mismatch in significant_mismatches:
            if (item.category.lower() in [m.lower() for m in mismatch] and 
                detected_category.lower() in [m.lower() for m in mismatch]):
                return True
        
        return False
    
    def _suggest_better_category(self, item_name: str, current_category: str) -> str:
        """
        Suggest a better category for an item.
        
        Args:
            item_name: Name of the item
            current_category: Current category
            
        Returns:
            Suggested better category
        """
        detected_category = category_parser.parse_category(item_name)
        
        if detected_category != current_category:
            return detected_category
        
        return current_category
    
    def _generate_improvement_suggestions(self, items: List[Item]) -> List[str]:
        """
        Generate suggestions for improving category organization.
        
        Args:
            items: List of all items
            
        Returns:
            List of improvement suggestions
        """
        suggestions = []
        
        # Analyze category distribution
        category_counts = {}
        for item in items:
            if item.category:
                category_counts[item.category] = category_counts.get(item.category, 0) + 1
        
        # Suggest consolidating very small categories
        small_categories = [cat for cat, count in category_counts.items() if count <= 2]
        if small_categories:
            suggestions.append(f"Consider consolidating {len(small_categories)} small categories: {', '.join(small_categories[:5])}")
        
        # Suggest splitting very large categories
        large_categories = [cat for cat, count in category_counts.items() if count >= 20]
        if large_categories:
            suggestions.append(f"Consider splitting large categories: {', '.join(large_categories)}")
        
        # Suggest hierarchical organization for flat categories
        flat_categories = [cat for cat in category_counts.keys() if " > " not in cat and category_counts[cat] >= 10]
        if flat_categories:
            suggestions.append(f"Consider adding subcategories to: {', '.join(flat_categories[:3])}")
        
        return suggestions
    
    async def handle_new_category_request(self, item_name: str, requested_category: str) -> Dict[str, Any]:
        """
        Handle requests to create new categories.
        
        Args:
            item_name: Name of the item requesting the category
            requested_category: Requested category name
            
        Returns:
            Dictionary with handling results
        """
        try:
            # Validate the requested category
            if not self._is_valid_category_name(requested_category):
                return {
                    "success": False,
                    "error": f"Invalid category name: '{requested_category}'",
                    "suggestion": "Use alphanumeric characters, spaces, and '>' for hierarchy"
                }
            
            # Check if category already exists
            existing_categories = category_parser.get_all_categories()
            if requested_category in existing_categories:
                return {
                    "success": True,
                    "message": f"Category '{requested_category}' already exists",
                    "category": requested_category
                }
            
            # Check for similar existing categories
            similar_categories = category_parser.search_categories(requested_category)
            if similar_categories:
                return {
                    "success": False,
                    "error": f"Similar categories already exist: {', '.join(similar_categories)}",
                    "suggestion": "Use an existing category or choose a more distinct name"
                }
            
            # Create the new category
            success = await self._create_category_in_system(requested_category, item_name)
            
            if success:
                return {
                    "success": True,
                    "message": f"Category '{requested_category}' created successfully",
                    "category": requested_category,
                    "created_for_item": item_name
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to create category in system"
                }
                
        except Exception as e:
            logger.error(f"Error handling new category request: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _is_valid_category_name(self, category_name: str) -> bool:
        """
        Validate if a category name is valid.
        
        Args:
            category_name: Category name to validate
            
        Returns:
            True if valid
        """
        if not category_name or len(category_name.strip()) == 0:
            return False
        
        # Allow alphanumeric, spaces, hyphens, and '>' for hierarchy
        import re
        valid_pattern = r'^[a-zA-Z0-9\s\->]+$'
        
        return bool(re.match(valid_pattern, category_name))
    
    async def _create_category_in_system(self, category_name: str, created_for_item: str) -> bool:
        """
        Create a new category in the system.
        
        Args:
            category_name: Name of the new category
            created_for_item: Item that triggered the creation
            
        Returns:
            True if successful
        """
        try:
            # For now, we'll just cache it
            # In a full implementation, this would update the category system
            self.new_categories_cache[category_name] = {
                "created_from": created_for_item,
                "timestamp": datetime.now(UTC),
                "usage_count": 1,
                "status": "active"
            }
            
            logger.info(f"Created new category '{category_name}' in system")
            return True
            
        except Exception as e:
            logger.error(f"Error creating category '{category_name}' in system: {e}")
            return False
    
    def get_edge_case_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about edge cases handled.
        
        Returns:
            Dictionary with edge case statistics
        """
        return {
            "ambiguous_items_handled": len(self.ambiguous_items_cache),
            "new_categories_created": len(self.new_categories_cache),
            "cache_timestamp": datetime.now(UTC),
            "ambiguous_items": list(self.ambiguous_items_cache.keys()),
            "new_categories": list(self.new_categories_cache.keys())
        }
    
    def clear_caches(self):
        """Clear all caches."""
        self.ambiguous_items_cache.clear()
        self.new_categories_cache.clear()
        logger.info("Edge case handler caches cleared")
