"""Enhanced Stock Command Parser for intelligent field population and batch operations."""

import re
import logging
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime

from schemas import (
    StockMovement, MovementType, MovementStatus, 
    BatchFormat, BatchParseResult, BatchError, BatchErrorType
)
from services.category_parser import category_parser

logger = logging.getLogger(__name__)


class InCommandParseResult:
    """Result of parsing an /in command with parameters and multiple items."""
    
    def __init__(self, project: Optional[str] = None, driver: Optional[str] = None,
                 from_location: Optional[str] = None, items: List[Dict[str, Any]] = None,
                 date: Optional[str] = None, logged_by: Optional[str] = None, 
                 category: Optional[str] = None):
        self.project = project
        self.driver = driver
        self.from_location = from_location
        self.items = items or []
        self.date = date
        self.logged_by = logged_by
        self.category = category
        self.is_valid = True
        self.errors = []
    
    def add_error(self, error: str):
        """Add an error message and mark as invalid."""
        self.errors.append(error)
        self.is_valid = False
    
    @property
    def global_parameters(self) -> Dict[str, str]:
        """Get global parameters as a dictionary."""
        params = {}
        if self.project:
            params['project'] = self.project
        if self.driver:
            params['driver'] = self.driver
        if self.from_location:
            params['from'] = self.from_location
        if self.date:
            params['date'] = self.date
        if self.logged_by:
            params['logged_by'] = self.logged_by
        if self.category:
            params['category'] = self.category
        return params


class OutCommandParseResult:
    """Result of parsing an /out command with parameters and multiple items."""
    
    def __init__(self, project: Optional[str] = None, to_location: Optional[str] = None,
                 driver: Optional[str] = None, items: List[Dict[str, Any]] = None,
                 date: Optional[str] = None, logged_by: Optional[str] = None,
                 category: Optional[str] = None):
        self.project = project
        self.to_location = to_location
        self.driver = driver
        self.items = items or []
        self.date = date
        self.logged_by = logged_by
        self.category = category
        self.is_valid = True
        self.errors = []
    
    def add_error(self, error: str):
        """Add an error message and mark as invalid."""
        self.errors.append(error)
        self.is_valid = False
    
    @property
    def global_parameters(self) -> Dict[str, str]:
        """Get global parameters as a dictionary."""
        params = {}
        if self.project:
            params['project'] = self.project
        if self.to_location:
            params['to'] = self.to_location
        if self.driver:
            params['driver'] = self.driver
        if self.date:
            params['date'] = self.date
        if self.logged_by:
            params['logged_by'] = self.logged_by
        if self.category:
            params['category'] = self.category
        return params


class EnhancedStockCommandParser:
    """Enhanced parser for /in and /out commands with smart field detection."""
    
    def __init__(self):
        """Initialize the enhanced command parser."""
        # Parameter patterns for extraction
        self.parameter_patterns = {
            'project': r'project:\s*([^,\n;]+)',
            'driver': r'driver:\s*([^,\n;]+)',
            'from': r'from:\s*([^,\n;]+)',
            'to': r'to:\s*([^,\n;]+)',
            'date': r'date:\s*([^,\n;]+)',
            'logged_by': r'logged\s+by:\s*([^,\n;]+)',
            'category': r'category:\s*([^,\n;]+)'
        }
        
        # Item parsing patterns - more flexible to handle various formats
        # Pattern: item_name, quantity unit, [note]
        # The issue is that item names can contain spaces and numbers, so we need to be more careful
        # We need to match from the end backwards to avoid conflicts with numbers in item names
        self.item_pattern = r'^(.+?),\s*(\d+(?:\.\d+)?)\s*([^\s,]+?)(?:\s*,\s*(.+))?$'
        
        # Maximum items per batch
        self.max_items = 20
    
    def parse_in_command(self, command_text: str) -> InCommandParseResult:
        """Parse /in command with parameters and multiple items."""
        try:
            # Clean and normalize text
            command_text = command_text.strip()
            
            # Extract global parameters
            params = self._extract_parameters(command_text)
            
            # Remove command prefix and parameters from text
            clean_text = self._remove_command_and_params(command_text, params)
            
            # Parse item list
            items = self._parse_item_list(clean_text)
            
            # Validate required fields
            result = InCommandParseResult(
                project=params.get('project'),
                driver=params.get('driver'),
                from_location=params.get('from'),
                items=items,
                date=params.get('date'),
                logged_by=params.get('logged_by'),
                category=params.get('category')
            )
            
            # Validation
            if not items:
                result.add_error("No items found in command")
            
            if len(items) > self.max_items:
                result.add_error(f"Too many items ({len(items)}). Maximum allowed: {self.max_items}")
            
            # Check for duplicate items
            item_names = [item['name'] for item in items]
            if len(item_names) != len(set(item_names)):
                result.add_error("Duplicate items found in command")
            
            # Check required fields - either project/driver OR date/logged_by format
            if not params.get('project') and not params.get('date'):
                result.add_error("Missing project or date")
            
            if not params.get('driver') and not params.get('logged_by'):
                result.add_error("Missing driver or logged by")
            
            # If using date/logged_by format, these are the primary parameters
            # If using project/driver format, those are the primary parameters
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing IN command: {e}")
            result = InCommandParseResult()
            result.add_error(f"Parsing error: {str(e)}")
            return result
    
    def parse_out_command(self, command_text: str) -> OutCommandParseResult:
        """Parse /out command with parameters and multiple items."""
        try:
            # Clean and normalize text
            command_text = command_text.strip()
            
            # Extract global parameters
            params = self._extract_parameters(command_text)
            
            # Remove command prefix and parameters from text
            clean_text = self._remove_command_and_params(command_text, params)
            
            # Parse item list
            items = self._parse_item_list(clean_text)
            
            # Validate required fields
            result = OutCommandParseResult(
                project=params.get('project'),
                to_location=params.get('to'),
                driver=params.get('driver'),
                items=items,
                date=params.get('date'),
                logged_by=params.get('logged_by'),
                category=params.get('category')
            )
            
            # Validation
            if not items:
                result.add_error("No items found in command")
            
            if len(items) > self.max_items:
                result.add_error(f"Too many items ({len(items)}). Maximum allowed: {self.max_items}")
            
            # Check for duplicate items
            item_names = [item['name'] for item in items]
            if len(item_names) != len(set(item_names)):
                result.add_error("Duplicate items found in command")
            
            # Check required fields - either project/driver OR date/logged_by format
            if not params.get('project') and not params.get('date'):
                result.add_error("Missing project or date")
            
            if not params.get('driver') and not params.get('logged_by'):
                result.add_error("Missing driver or logged by")
            
            # For OUT commands, to_location is required
            if not params.get('to'):
                result.add_error("Destination location (to:) is required for OUT commands")
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing OUT command: {e}")
            result = OutCommandParseResult()
            result.add_error(f"Parsing error: {str(e)}")
            return result
    
    def parse_adjust_command(self, command_text: str) -> OutCommandParseResult:
        """Parse /adjust command with parameters and multiple items."""
        try:
            # Clean and normalize text
            command_text = command_text.strip()
            
            # Extract global parameters
            params = self._extract_parameters(command_text)
            
            # Remove command prefix and parameters from text
            clean_text = self._remove_command_and_params(command_text, params)
            
            # Parse item list
            items = self._parse_item_list(clean_text)
            
            # Validate required fields
            result = OutCommandParseResult(
                project=params.get('project'),
                to_location=params.get('to'),
                driver=params.get('driver'),
                items=items,
                date=params.get('date'),
                logged_by=params.get('logged_by'),
                category=params.get('category')
            )
            
            # Validation
            if not items:
                result.add_error("No items found in command")
            
            if len(items) > self.max_items:
                result.add_error(f"Too many items ({len(items)}). Maximum allowed: {self.max_items}")
            
            # Check for duplicate items
            item_names = [item['name'] for item in items]
            if len(item_names) != len(set(item_names)):
                result.add_error("Duplicate items found in command")
            
            # Check required fields - either project/driver OR date/logged_by format
            if not params.get('project') and not params.get('date'):
                result.add_error("Missing project or date")
            
            if not params.get('driver') and not params.get('logged_by'):
                result.add_error("Missing driver or logged by")
            
            # For ADJUST commands, to_location is optional
            # Adjustments can be made without specifying destination
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing ADJUST command: {e}")
            result = OutCommandParseResult()
            result.add_error(f"Parsing error: {str(e)}")
            return result
    
    def _extract_parameters(self, text: str) -> Dict[str, str]:
        """Extract global parameters from command text."""
        params = {}
        
        for param_name, pattern in self.parameter_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                params[param_name] = value
        
        return params
    
    def _remove_command_and_params(self, text: str, params: Dict[str, str]) -> str:
        """Remove command prefix and parameters from text, leaving only items."""
        # Remove command prefix
        text = re.sub(r'^(/in|/out|/adjust|in|out|adjust)\s+', '', text, flags=re.IGNORECASE)
        
        # Instead of trying to remove parameters by regex, let's extract the item lines
        # by looking for lines that contain the item pattern
        lines = text.split('\n')
        item_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                # Check if this line looks like an item (contains a comma followed by a number)
                if re.search(r',\s*\d+', line):
                    item_lines.append(line)
        
        # Join the item lines
        return '\n'.join(item_lines)
    
    def _parse_item_list(self, text: str) -> List[Dict[str, Any]]:
        """Parse the item list from cleaned text."""
        items = []
        
        # Debug logging
        logger.debug(f"Parsing item list from text: '{text}'")
        
        # Split by newlines first
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        logger.debug(f"Split into {len(lines)} lines: {lines}")
        
        for i, line in enumerate(lines):
            logger.debug(f"Processing line {i+1}: '{line}'")
            
            # Also check for semicolon-separated items on the same line
            if ';' in line:
                sub_items = [item.strip() for item in line.split(';') if item.strip()]
                logger.debug(f"Line contains semicolons, split into: {sub_items}")
                for sub_item in sub_items:
                    parsed_item = self._parse_single_item(sub_item)
                    if parsed_item:
                        items.append(parsed_item)
                        logger.debug(f"Added semicolon item: {parsed_item}")
            else:
                parsed_item = self._parse_single_item(line)
                if parsed_item:
                    items.append(parsed_item)
                    logger.debug(f"Added line item: {parsed_item}")
                else:
                    logger.debug(f"Failed to parse line: '{line}'")
        
        logger.debug(f"Total items parsed: {len(items)}")
        return items
    
    def _parse_single_item(self, item_text: str) -> Optional[Dict[str, Any]]:
        """Parse a single item entry."""
        try:
            logger.debug(f"Parsing single item: '{item_text}'")
            
            # The format is: item_name, quantity [unit], [note]
            # For items like "Steel Beam 6m, 10", we want:
            # - quantity: 10 (pieces)
            # - unit: pieces (or the specified unit if given)
            # - unit_size: 6.0 (from the item name)
            # - unit_type: m (from the item name)
            
            # Find the last occurrence of a number (quantity) after a comma
            # Look for pattern: ", 10" or ", 10 pieces" or ", 10 ltrs"
            quantity_unit_match = re.search(r',\s*(\d+(?:\.\d+)?)\s*([^\s,]*?)(?:\s*,\s*(.+))?$', item_text)
            if not quantity_unit_match:
                logger.warning(f"Could not find quantity and unit pattern in: {item_text}")
                return None
            
            quantity = float(quantity_unit_match.group(1))
            specified_unit = quantity_unit_match.group(2).strip()
            note = quantity_unit_match.group(3).strip() if quantity_unit_match.group(3) else None
            
            # Extract item name - everything before the comma that precedes the quantity
            comma_pos = item_text.rfind(',')
            if comma_pos == -1:
                logger.warning(f"Could not find comma separator in: {item_text}")
                return None
            
            item_name = item_text[:comma_pos].strip()
            
            # Smart unit detection and inference
            # For items like "Steel Beam 6m, 10", we want:
            # - unit: "pieces" (the quantity unit)
            # - unit_size: 6.0 (from item name)
            # - unit_type: "m" (from item name)
            
            # Extract unit size and type from item name FIRST
            unit_size, unit_type = self._extract_unit_info(item_name)
            
            # Determine the quantity unit (what the quantity represents)
            if specified_unit and specified_unit.lower() not in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']:
                # User specified a unit like "pieces", "cans", "bags"
                unit = specified_unit
            elif unit_size and unit_type:
                # Item has embedded units (like "6m"), so quantity is pieces
                unit = "piece"  # Use singular form for Airtable compatibility
            else:
                # Use smart unit inference based on item context
                unit = self._infer_unit_from_context(item_name, quantity)
            
            logger.debug(f"Parsed: name='{item_name}', qty={quantity}, unit='{unit}', note='{note}'")
            
            # Auto-detect category
            category = self._detect_category(item_name)
            
            # Extract base category (before ">") for Airtable compatibility
            base_category = None
            if category and '>' in category:
                base_category = category.split('>')[0].strip()
            else:
                base_category = category
            
            result = {
                'name': item_name,
                'quantity': quantity,
                'unit': unit,
                'note': note,
                'unit_size': unit_size,
                'unit_type': unit_type,
                'category': base_category  # Use base category for Airtable
            }
            
            logger.debug(f"Successfully parsed item: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing single item '{item_text}': {e}")
            return None
    
    def _extract_unit_info(self, item_name: str) -> Tuple[Optional[float], Optional[str]]:
        """Extract unit size and type from item name."""
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
                
                # Normalize unit types to singular forms for Airtable compatibility
                if unit_type in ['ltrs', 'liters']:
                    unit_type = 'ltr'
                elif unit_type in ['m', 'meters']:
                    unit_type = 'm'
                elif unit_type in ['kg', 'kilos']:
                    unit_type = 'kg'
                elif unit_type in ['tons']:
                    unit_type = 'ton'
                elif unit_type in ['pieces', 'pcs']:
                    unit_type = 'piece'
                elif unit_type in ['bags']:
                    unit_type = 'bag'
                elif unit_type in ['boxes']:
                    unit_type = 'box'
                elif unit_type in ['sets']:
                    unit_type = 'set'
                
                return size, unit_type
        
        # Default values if no pattern matches
        return None, None
    
    def _infer_unit_from_context(self, item_name: str, quantity: float) -> str:
        """Intelligently infer the most appropriate unit based on item context."""
        item_lower = item_name.lower()
        
        # Construction materials - typically measured by weight or volume
        if any(word in item_lower for word in ['cement', 'concrete', 'sand', 'gravel', 'stone', 'aggregate']):
            if quantity >= 1000:
                return 'ton'
            elif quantity >= 100:
                return 'kg'
            else:
                return 'bag'
        
        # Paint and coatings - typically measured by volume
        if any(word in item_lower for word in ['paint', 'varnish', 'primer', 'coating', 'enamel']):
            if quantity >= 20:
                return 'ltr'
            else:
                return 'can'
        
        # Electrical materials - typically measured by length
        if any(word in item_lower for word in ['wire', 'cable', 'conduit', 'flex']):
            if quantity >= 100:
                return 'm'
            else:
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
                return 'piece'
            elif 'sheet' in item_lower or 'plate' in item_lower:
                return 'sheet'
            else:
                return 'kg'
        
        # Wood and timber - typically measured by length or pieces
        if any(word in item_lower for word in ['wood', 'timber', 'plywood', 'mdf', 'board']):
            if quantity >= 10:
                return 'm'
            else:
                return 'piece'
        
        # Safety equipment - typically measured by pieces
        if any(word in item_lower for word in ['helmet', 'glove', 'goggle', 'vest', 'boot', 'mask']):
            return 'piece'
        
        # Tools - typically measured by pieces
        if any(word in item_lower for word in ['hammer', 'drill', 'saw', 'wrench', 'pliers', 'tool']):
            return 'piece'
        
        # Fasteners - typically measured by count
        if any(word in item_lower for word in ['nail', 'screw', 'bolt', 'nut', 'washer']):
            if quantity >= 100:
                return 'packet'
            else:
                return 'piece'
        
        # Default logic based on quantity ranges
        if quantity >= 1000:
            return 'ton'
        elif quantity >= 100:
            return 'kg'
        elif quantity >= 20:
            return 'piece'
        else:
            return 'piece'
    
    def _detect_category(self, item_name: str) -> Optional[str]:
        """Detect category using existing CategoryParser."""
        try:
            return category_parser.parse_category(item_name)
        except Exception as e:
            logger.warning(f"Error detecting category for '{item_name}': {e}")
            return None
    
    def validate_parse_result(self, result) -> bool:
        """Validate the parse result and add any missing validation errors."""
        if not result.is_valid:
            return False
        
        # Additional validation logic can be added here
        return True


# Create a singleton instance
enhanced_stock_parser = EnhancedStockCommandParser()
