"""Smart category parser for automatically detecting material categories from item names."""

import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CategoryParser:
    """Smart parser for automatically detecting material categories from item names."""
    
    def __init__(self):
        """Initialize the category parser with predefined rules."""
        self.category_rules = {
            # Paint and coatings
            'paint': 'Paint',
            'coating': 'Paint',
            'varnish': 'Paint',
            'primer': 'Paint',
            'enamel': 'Paint',
            'lacquer': 'Paint',
            
            # Electrical components
            'wire': 'Electrical > Cables',
            'cable': 'Electrical > Cables',
            'switch': 'Electrical > Switches',
            'outlet': 'Electrical > Outlets',
            'socket': 'Electrical > Outlets',
            'bulb': 'Lamps and Bulbs',
            'lamp': 'Lamps and Bulbs',
            'light': 'Lamps and Bulbs',
            'led': 'Lamps and Bulbs',
            'fluorescent': 'Lamps and Bulbs',
            'incandescent': 'Lamps and Bulbs',
            'adapter': 'Adapters',
            'connector': 'Electrical > Components',
            'fuse': 'Electrical > Components',
            'breaker': 'Electrical > Components',
            
            # Plumbing materials
            'pipe': 'Plumbing',
            'fitting': 'Plumbing',
            'valve': 'Plumbing',
            'faucet': 'Plumbing',
            'tap': 'Plumbing',
            'toilet': 'Toilet Items',
            'sink': 'Plumbing',
            'drain': 'Plumbing',
            'shower': 'Plumbing',
            'bath': 'Plumbing',
            
            # Tools
            'hammer': 'Tools',
            'screwdriver': 'Tools',
            'wrench': 'Tools',
            'pliers': 'Tools',
            'drill': 'Tools',
            'saw': 'Tools',
            'level': 'Tools',
            'tape': 'Tools',
            'measure': 'Tools',
            'tool': 'Tools',
            
            # Safety equipment
            'helmet': 'Safety Equipment',
            'safety': 'Safety Equipment',
            'glove': 'Safety Equipment',
            'goggle': 'Safety Equipment',
            'vest': 'Safety Equipment',
            'boot': 'Safety Equipment',
            'mask': 'Safety Equipment',
            'harness': 'Safety Equipment',
            
            # Carpentry materials
            'wood': 'Carpentry',
            'plywood': 'Carpentry',
            'mdf': 'Carpentry',
            'timber': 'Carpentry',
            'board': 'Carpentry',
            'lumber': 'Carpentry',
            'nail': 'Carpentry',
            'screw': 'Carpentry',
            'bolt': 'Carpentry',
            
            # Steel and metal
            'steel': 'Steel',
            'metal': 'Steel',
            'iron': 'Steel',
            'aluminum': 'Steel',
            'copper': 'Steel',
            'beam': 'Steel',
            'plate': 'Steel',
            'sheet': 'Steel',
            'bar': 'Steel',
            
            # Construction materials
            'cement': 'Construction Materials',
            'concrete': 'Construction Materials',
            'sand': 'Construction Materials',
            'gravel': 'Construction Materials',
            'brick': 'Construction Materials',
            'block': 'Construction Materials',
            'tile': 'Construction Materials',
            'grout': 'Construction Materials',
            'mortar': 'Construction Materials',
        }
        
        # Priority rules for ambiguous items
        self.priority_rules = {
            # Paint takes priority over electrical when both keywords present
            'paint': ['electrical', 'power', 'voltage'],
            # Tools take priority over electrical for hand tools
            'tool': ['electrical', 'power'],
            # Plumbing takes priority over electrical for water-related items
            'pipe': ['electrical', 'wire'],
            # Safety equipment takes priority over general categories
            'safety': ['electrical', 'plumbing', 'tools'],
        }
        
        # Subcategory mappings for more specific categorization
        self.subcategory_mappings = {
            'Paint': {
                'interior': 'Interior Paint',
                'exterior': 'Exterior Paint',
                'specialty': 'Specialty Paint',
                'primer': 'Primer',
                'varnish': 'Varnish',
                'enamel': 'Enamel',
            },
            'Electrical': {
                'cable': 'Cables',
                'wire': 'Cables',
                'switch': 'Switches',
                'outlet': 'Outlets',
                'socket': 'Outlets',
                'component': 'Components',
            },
            'Plumbing': {
                'pipe': 'Pipes',
                'fitting': 'Fittings',
                'valve': 'Valves',
                'fixture': 'Fixtures',
            },
            'Tools': {
                'hand': 'Hand Tools',
                'power': 'Power Tools',
                'measuring': 'Measuring Tools',
                'safety': 'Safety Tools',
            },
            'Safety Equipment': {
                'head': 'Head Protection',
                'eye': 'Eye Protection',
                'hand': 'Hand Protection',
                'body': 'Body Protection',
            },
            'Lamps and Bulbs': {
                'led': 'LED Bulbs',
                'fluorescent': 'Fluorescent',
                'incandescent': 'Incandescent',
                'specialty': 'Specialty Lighting',
            },
            'Adapters': {
                'power': 'Power Adapters',
                'pipe': 'Pipe Adapters',
                'cable': 'Cable Adapters',
                'mechanical': 'Mechanical Adapters',
            },
            'Toilet Items': {
                'seat': 'Toilet Seats',
                'tank': 'Toilet Tanks',
                'bowl': 'Toilet Bowls',
                'accessory': 'Toilet Accessories',
            },
            'Carpentry': {
                'wood': 'Wood',
                'plywood': 'Plywood',
                'mdf': 'MDF',
                'tool': 'Wood Tools',
            },
            'Steel': {
                'beam': 'Beams',
                'pipe': 'Pipes',
                'sheet': 'Sheets',
                'structural': 'Structural',
            },
        }
    
    def parse_category(self, item_name: str) -> str:
        """
        Parse the item name and return the appropriate category.
        
        Args:
            item_name: The name of the item to categorize
            
        Returns:
            The detected category (can be hierarchical like "Electrical > Cables")
        """
        if not item_name:
            return "Uncategorized"
        
        item_lower = item_name.lower()
        
        # Check for exact matches first
        for keyword, category in self.category_rules.items():
            if keyword in item_lower:
                # Check if we need to apply priority rules
                final_category = self._apply_priority_rules(item_lower, category)
                
                # Try to add subcategory if applicable
                enhanced_category = self._add_subcategory(item_lower, final_category)
                
                logger.info(f"Category detected for '{item_name}': {enhanced_category}")
                return enhanced_category
        
        # If no match found, create a new category based on the item name
        new_category = self._create_new_category(item_name)
        logger.info(f"New category created for '{item_name}': {new_category}")
        return new_category
    
    def _apply_priority_rules(self, item_lower: str, detected_category: str) -> str:
        """
        Apply priority rules to resolve conflicts between multiple possible categories.
        
        Args:
            item_lower: Lowercase item name
            detected_category: Initially detected category
            
        Returns:
            Final category after applying priority rules
        """
        for priority_keyword, conflicting_keywords in self.priority_rules.items():
            if priority_keyword in item_lower:
                # Check if any conflicting keywords are also present
                for conflicting_keyword in conflicting_keywords:
                    if conflicting_keyword in item_lower:
                        # Priority keyword takes precedence
                        priority_category = self.category_rules.get(priority_keyword)
                        if priority_category:
                            logger.debug(f"Priority rule applied: {priority_keyword} over {conflicting_keyword}")
                            return priority_category
        
        return detected_category
    
    def _add_subcategory(self, item_lower: str, main_category: str) -> str:
        """
        Add subcategory to the main category if applicable.
        
        Args:
            item_lower: Lowercase item name
            main_category: Main category to enhance
            
        Returns:
            Enhanced category with subcategory if applicable
        """
        # Extract the base category name (before any existing subcategory)
        base_category = main_category.split(' > ')[0]
        
        if base_category in self.subcategory_mappings:
            for sub_keyword, subcategory in self.subcategory_mappings[base_category].items():
                if sub_keyword in item_lower:
                    # Check if main category already has a subcategory
                    if ' > ' in main_category:
                        # Keep existing subcategory
                        return main_category
                    else:
                        # Add new subcategory
                        return f"{base_category} > {subcategory}"
        
        return main_category
    
    def _create_new_category(self, item_name: str) -> str:
        """
        Create a new category for items that don't match existing rules.
        
        Args:
            item_name: The item name to create a category for
            
        Returns:
            A new category name
        """
        # Try to extract a meaningful category from the item name
        words = item_name.split()
        
        # Look for descriptive words that could become categories
        descriptive_words = []
        for word in words:
            # Skip common words, numbers, and units
            if (len(word) > 2 and 
                not word.isdigit() and 
                word.lower() not in ['the', 'and', 'or', 'for', 'with', 'from', 'ltrs', 'kg', 'm', 'ton', 'piece']):
                descriptive_words.append(word)
        
        if descriptive_words:
            # Use the first descriptive word as the category
            new_category = descriptive_words[0].title()
            logger.info(f"Created new category '{new_category}' for item '{item_name}'")
            return new_category
        
        # Fallback to generic category
        return "Other"
    
    def get_all_categories(self) -> List[str]:
        """
        Get all available categories (main categories and subcategories).
        
        Returns:
            List of all available categories
        """
        categories = set()
        
        # Add main categories
        for category in self.category_rules.values():
            if ' > ' in category:
                # Add both main and subcategory
                main, sub = category.split(' > ', 1)
                categories.add(main)
                categories.add(category)
            else:
                categories.add(category)
        
        # Add subcategories from mappings
        for main_category, subcategories in self.subcategory_mappings.items():
            categories.add(main_category)
            for subcategory in subcategories.values():
                categories.add(f"{main_category} > {subcategory}")
        
        return sorted(list(categories))
    
    def get_main_categories(self) -> List[str]:
        """
        Get only the main categories (without subcategories).
        
        Returns:
            List of main categories
        """
        main_categories = set()
        
        for category in self.category_rules.values():
            if ' > ' in category:
                main_categories.add(category.split(' > ')[0])
            else:
                main_categories.add(category)
        
        return sorted(list(main_categories))
    
    def search_categories(self, query: str) -> List[str]:
        """
        Search for categories that match the query.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching categories
        """
        query_lower = query.lower()
        matches = []
        
        all_categories = self.get_all_categories()
        
        for category in all_categories:
            if query_lower in category.lower():
                matches.append(category)
        
        return matches[:10]  # Limit results
    
    def validate_category(self, category: str) -> bool:
        """
        Validate if a category exists or follows the expected format.
        
        Args:
            category: Category to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not category:
            return False
        
        # Check if it's a known category
        all_categories = self.get_all_categories()
        if category in all_categories:
            return True
        
        # Check if it follows the hierarchical format (Main > Sub)
        if ' > ' in category:
            parts = category.split(' > ')
            if len(parts) == 2 and parts[0] and parts[1]:
                return True
        
        # Allow custom categories (single word, capitalized)
        if category and ' ' not in category and category[0].isupper():
            return True
        
        return False


# Global instance for easy access
category_parser = CategoryParser()
