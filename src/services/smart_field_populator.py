"""Smart Field Populator Service for automatic field population in stock movements."""

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import re

from schemas import StockMovement, MovementType, Item
from services.category_parser import category_parser

logger = logging.getLogger(__name__)


class SmartFieldPopulator:
    """Service for automatically populating stock movement fields."""
    
    def __init__(self):
        """Initialize the smart field populator."""
        # Default location mappings
        self.default_locations = {
            "warehouse": "Warehouse",
            "main warehouse": "Main Warehouse",
            "site": "Site",
            "office": "Office",
            "yard": "Yard"
        }
        
        # Movement type defaults
        self.movement_defaults = {
            MovementType.IN: {
                "reason": "Restocking",
                "source": "Telegram",
                "status": "Requested"
            },
            MovementType.OUT: {
                "reason": "Required",
                "source": "Telegram", 
                "status": "Requested"
            },
            MovementType.ADJUST: {
                "reason": "Adjustment",
                "source": "Telegram",
                "status": "Posted"
            }
        }
    
    def populate_category(self, item_name: str) -> Optional[str]:
        """Auto-detect category using existing CategoryParser."""
        try:
            category = category_parser.parse_category(item_name)
            logger.info(f"Category detected for '{item_name}': {category}")
            return category
        except Exception as e:
            logger.warning(f"Error detecting category for '{item_name}': {e}")
            return None
    
    def extract_units(self, item_name: str) -> Tuple[Optional[float], Optional[str]]:
        """Extract unit size and type from item name."""
        try:
            # Common patterns for unit extraction
            patterns = [
                # Paint 20ltrs -> (20.0, "ltrs")
                r'(\d+(?:\.\d+)?)\s*(ltrs?|liters?|kg|kilos?|tons?|m|meters?|mm|cm|pieces?|bags?|boxes?|sets?)',
                # HDPE Pipe 250mm 3/4 -> (250.0, "mm")
                r'(\d+(?:\.\d+)?)\s*(mm|cm|m|meters?)',
                # Wire 100m -> (100.0, "m")
                r'(\d+(?:\.\d+)?)\s*(m|meters?)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, item_name, re.IGNORECASE)
                if match:
                    size = float(match.group(1))
                    unit_type = match.group(2).lower()
                    
                    # Normalize unit types
                    if unit_type in ['ltrs', 'liters']:
                        unit_type = 'ltrs'
                    elif unit_type in ['m', 'meters']:
                        unit_type = 'm'
                    elif unit_type in ['kg', 'kilos']:
                        unit_type = 'kg'
                    elif unit_type in ['tons']:
                        unit_type = 'tons'
                    elif unit_type in ['pieces', 'pcs']:
                        unit_type = 'pieces'
                    elif unit_type in ['bags']:
                        unit_type = 'bags'
                    elif unit_type in ['boxes']:
                        unit_type = 'boxes'
                    elif unit_type in ['sets']:
                        unit_type = 'sets'
                    
                    return size, unit_type
            
            return None, None
            
        except Exception as e:
            logger.error(f"Error extracting units from '{item_name}': {e}")
            return None, None
    
    def determine_locations(self, movement_type: MovementType, item: Optional[Item], 
                          user_specified: Optional[str]) -> Tuple[str, str]:
        """Determine From/To locations based on movement type."""
        try:
            if movement_type == MovementType.IN:
                # IN: From user-specified location to Warehouse
                from_location = user_specified or "Unknown Source"
                to_location = item.location if item else "Warehouse"
                
            elif movement_type == MovementType.OUT:
                # OUT: From Warehouse (or item's preferred location) to user-specified location
                from_location = item.location if item else "Warehouse"
                to_location = user_specified or "Unknown Destination"
                
            elif movement_type == MovementType.ADJUST:
                # ADJUST: Usually within the same location
                location = user_specified or (item.location if item else "Warehouse")
                from_location = location
                to_location = location
                
            else:
                # Default fallback
                from_location = "Unknown"
                to_location = "Unknown"
            
            # Normalize location names
            from_location = self._normalize_location(from_location)
            to_location = self._normalize_location(to_location)
            
            logger.debug(f"Determined locations for {movement_type.value}: {from_location} -> {to_location}")
            return from_location, to_location
            
        except Exception as e:
            logger.error(f"Error determining locations for {movement_type.value}: {e}")
            return "Unknown", "Unknown"
    
    def populate_user_context(self, user_id: int, user_name: str, 
                            chat_id: int) -> Dict[str, Any]:
        """Populate user context and metadata."""
        try:
            context = {
                "user_id": str(user_id),
                "user_name": user_name,
                "chat_id": chat_id,
                "timestamp": datetime.now(),
                "source": "Telegram"
            }
            
            logger.debug(f"Populated user context: {context}")
            return context
            
        except Exception as e:
            logger.error(f"Error populating user context: {e}")
            return {}
    
    def populate_movement_metadata(self, movement_type: MovementType, 
                                 parse_result: Any) -> Dict[str, Any]:
        """Populate movement-specific metadata."""
        try:
            metadata = {}
            
            # Get defaults for this movement type
            defaults = self.movement_defaults.get(movement_type, {})
            
            # Apply defaults
            for key, value in defaults.items():
                metadata[key] = value
            
            # Add movement-specific metadata
            if movement_type == MovementType.IN:
                metadata.update({
                    "reason": "Restocking",
                    "from_location": getattr(parse_result, 'from_location', None),
                    "project": getattr(parse_result, 'project', None),
                    "driver_name": getattr(parse_result, 'driver', None)
                })
                
            elif movement_type == MovementType.OUT:
                metadata.update({
                    "reason": "Required",
                    "to_location": getattr(parse_result, 'to_location', None),
                    "project": getattr(parse_result, 'project', None),
                    "driver_name": getattr(parse_result, 'driver', None)
                })
                
            elif movement_type == MovementType.ADJUST:
                metadata.update({
                    "reason": "Adjustment",
                    "location": getattr(parse_result, 'from_location', None) or getattr(parse_result, 'to_location', None)
                })
            
            logger.debug(f"Populated metadata for {movement_type.value}: {metadata}")
            return metadata
            
        except Exception as e:
            logger.error(f"Error populating metadata for {movement_type.value}: {e}")
            return {}
    
    def populate_item_fields(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Populate item-specific fields using smart detection."""
        try:
            populated_fields = item_data.copy()
            
            # Extract unit information if not already present
            if populated_fields.get('unit_size') is None or populated_fields.get('unit_type') is None:
                unit_size, unit_type = self.extract_units(item_data['name'])
                populated_fields['unit_size'] = unit_size
                populated_fields['unit_type'] = unit_type
            
            # Ensure category is populated
            if populated_fields.get('category') is None:
                populated_fields['category'] = self.populate_category(item_data['name'])
            
            # Smart unit inference if unit is missing or generic
            if not populated_fields.get('unit') or populated_fields['unit'] in ['pieces', 'pcs']:
                smart_unit = self._infer_smart_unit(item_data['name'], item_data['quantity'])
                if smart_unit:
                    populated_fields['unit'] = smart_unit
            
            logger.debug(f"Populated item fields: {populated_fields}")
            return populated_fields
            
        except Exception as e:
            logger.error(f"Error populating item fields: {e}")
            return item_data
    
    def _normalize_location(self, location: str) -> str:
        """Normalize location names to standard format."""
        if not location:
            return "Unknown"
        
        location_lower = location.lower().strip()
        
        # Check for default location mappings
        for key, value in self.default_locations.items():
            if key in location_lower:
                return value
        
        # Handle "site" locations specially
        if location_lower.startswith('site '):
            # Extract the site identifier and capitalize properly
            site_part = location_lower[5:].strip()  # Remove "site " prefix
            if site_part:
                return f"Site {site_part.upper()}"
            else:
                return "Site"
        
        # Capitalize first letter of each word for consistency
        return location.strip().title()
    
    def _infer_smart_unit(self, item_name: str, quantity: float) -> Optional[str]:
        """Infer the most appropriate unit based on item context."""
        item_lower = item_name.lower()
        
        # Construction materials - typically measured by weight or volume
        if any(word in item_lower for word in ['cement', 'concrete', 'sand', 'gravel', 'stone', 'aggregate']):
            if quantity >= 1000:
                return 'tons'
            elif quantity >= 100:
                return 'kg'
            else:
                return 'bags'
        
        # Paint and coatings - typically measured by volume
        if any(word in item_lower for word in ['paint', 'varnish', 'primer', 'coating', 'enamel']):
            if quantity >= 20:
                return 'ltrs'
            else:
                return 'cans'
        
        # Electrical materials - typically measured by length
        if any(word in item_lower for word in ['wire', 'cable', 'conduit', 'flex']):
            return 'm'
        
        # Plumbing materials - typically measured by length or pieces
        if any(word in item_lower for word in ['pipe', 'tube', 'fitting', 'valve']):
            if quantity >= 10:
                return 'm'
            else:
                return 'pieces'
        
        # Steel and metal - typically measured by weight or length
        if any(word in item_lower for word in ['steel', 'iron', 'aluminum', 'copper', 'metal']):
            if 'bar' in item_lower or 'beam' in item_lower:
                return 'pieces'
            elif 'sheet' in item_lower or 'plate' in item_lower:
                return 'sheets'
            else:
                return 'kg'
        
        # Wood and timber - typically measured by length or pieces
        if any(word in item_lower for word in ['wood', 'timber', 'plywood', 'mdf', 'board']):
            if quantity >= 10:
                return 'm'
            else:
                return 'pieces'
        
        # Safety equipment - typically measured by pieces
        if any(word in item_lower for word in ['helmet', 'glove', 'goggle', 'vest', 'boot', 'mask']):
            return 'pieces'
        
        # Tools - typically measured by pieces
        if any(word in item_lower for word in ['hammer', 'drill', 'saw', 'wrench', 'pliers', 'tool']):
            return 'pieces'
        
        # Fasteners - typically measured by count
        if any(word in item_lower for word in ['nail', 'screw', 'bolt', 'nut', 'washer']):
            if quantity >= 100:
                return 'packets'
            else:
                return 'pieces'
        
        # Default logic based on quantity ranges
        if quantity >= 1000:
            return 'tons'
        elif quantity >= 100:
            return 'kg'
        elif quantity >= 20:
            return 'pieces'
        else:
            return 'pieces'


# Create a singleton instance
smart_field_populator = SmartFieldPopulator()
