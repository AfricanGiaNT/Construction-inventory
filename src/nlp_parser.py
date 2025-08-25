"""Natural Language Parser for Stock Movement Commands."""

import re
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime
try:
    from datetime import UTC
except ImportError:
    # UTC constant was introduced in Python 3.11
    # For older versions, use timezone.utc
    from datetime import timezone
    UTC = timezone.utc

# Use absolute imports for testing
try:
    from .schemas import (
        StockMovement, MovementType, MovementStatus, 
        BatchFormat, BatchParseResult, BatchError, BatchErrorType
    )
    from .utils.error_handling import ErrorHandler
except ImportError:
    from schemas import (
        StockMovement, MovementType, MovementStatus,
        BatchFormat, BatchParseResult, BatchError, BatchErrorType
    )
    from utils.error_handling import ErrorHandler


class NLPStockParser:
    """Natural language parser for stock movement commands."""
    
    def __init__(self):
        """Initialize the NLP parser."""
        # Common unit patterns
        self.units = [
            'piece', 'pieces', 'bag', 'bags', 'box', 'boxes', 'meter', 'meters', 
            'liter', 'liters', 'kg', 'kilos', 'ton', 'tons', 'roll', 'rolls',
            'bundle', 'bundles', 'carton', 'cartons', 'set', 'sets'
        ]
        
        # Common location patterns
        self.location_keywords = ['to', 'at', 'in', 'warehouse', 'site', 'office', 'yard']
        
        # Driver patterns
        self.driver_keywords = ['by', 'delivered by', 'collected by', 'driver', 'person']
        
        # From location patterns
        self.from_keywords = ['from', 'source', 'origin', 'supplier']
        
        # Maximum batch size
        self.max_batch_size = 40
    
    def parse_stock_command(self, text: str, user_id: int, user_name: str) -> Optional[StockMovement]:
        """Parse natural language stock command into StockMovement object.
        
        This method maintains backward compatibility for single entries while
        also supporting batch detection and parsing.
        """
        try:
            # Clean and normalize text
            text = text.strip()
            
            # Check if this is a batch command
            batch_result = self.parse_batch_entries(text, user_id, user_name)
            
            # If it's a single entry, return the first movement
            if batch_result.format == BatchFormat.SINGLE and len(batch_result.movements) == 1:
                return batch_result.movements[0]
            
            # If it's a batch with multiple entries, return None to indicate batch processing
            if len(batch_result.movements) > 1:
                return None
            
            # If it's a single entry but parsing failed, return None
            if len(batch_result.movements) == 0:
                return None
            
            # Fallback: return the first movement if available
            return batch_result.movements[0] if batch_result.movements else None
            
        except Exception as e:
            print(f"Error parsing command: {e}")
            return None
    
    def detect_batch_format(self, text: str) -> BatchFormat:
        """Detect the format of the input text (single, newline, semicolon, or mixed)."""
        # Check for newlines
        has_newlines = '\n' in text
        
        # Check for semicolons
        has_semicolons = ';' in text
        
        # Check for multiple movement type indicators (but only if they're on separate lines)
        lines = text.split('\n')
        movement_indicators = ['/in', '/out', '/adjust', 'in ', 'out ', 'adjust ']
        
        # Count movement indicators that appear at the start of lines
        movement_count = 0
        for line in lines:
            line_lower = line.strip().lower()
            for indicator in movement_indicators:
                if line_lower.startswith(indicator):
                    movement_count += 1
                    break
        
        # If we have multiple lines with movement indicators, it's mixed
        if movement_count > 1:
            return BatchFormat.MIXED
        elif has_newlines and has_semicolons:
            return BatchFormat.MIXED
        elif has_newlines:
            return BatchFormat.NEWLINE
        elif has_semicolons:
            return BatchFormat.SEMICOLON
        else:
            return BatchFormat.SINGLE
    
    def parse_global_parameters(self, text: str) -> Tuple[Dict[str, str], str]:
        """Extract global parameters from the beginning of a command."""
        global_params = {}
        remaining_text = text.strip()
        
        # Check if there are newlines in the text
        first_line = remaining_text.split('\n')[0] if '\n' in remaining_text else remaining_text
        
        # Define global parameter patterns
        global_patterns = {
            'driver': r'driver:\s*([^,\n]+)(?:,\s*|$|\n)',
            'from': r'from:\s*([^,\n]+)(?:,\s*|$|\n)',
            'to': r'to:\s*([^,\n]+)(?:,\s*|$|\n)',
            'project': r'project:\s*([^,\n]+)(?:,\s*|$|\n)'
        }
        
        # Extract command prefix if present
        command_prefix = ""
        command_match = re.match(r'^(/in|/out|/adjust|in|out|adjust)\s+', first_line)
        if command_match:
            command_prefix = command_match.group(0)
            first_line = first_line[len(command_prefix):].strip()
        
        # Look for global parameters at the beginning of the first line
        original_first_line = first_line
        for param_name, pattern in global_patterns.items():
            match = re.search(pattern, first_line, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                global_params[param_name] = value
                
                # Remove the matched parameter from the text
                start, end = match.span()
                first_line = first_line[:start] + first_line[end:]
                
                # Clean up any leftover commas or whitespace
                first_line = re.sub(r'^,\s*', '', first_line)
                first_line = first_line.strip()
        
        # If we didn't extract any global parameters, restore the original text
        if not global_params:
            first_line = original_first_line
            remaining_text = text.strip()
        else:
            # Reconstruct the remaining text with the modified first line
            if '\n' in remaining_text:
                remaining_lines = remaining_text.split('\n')[1:]
                if first_line:  # If there's still content in the first line
                    remaining_text = command_prefix + first_line + '\n' + '\n'.join(remaining_lines)
                else:  # If first line is now empty (all content was parameters)
                    remaining_text = command_prefix + '\n'.join(remaining_lines)
            else:
                remaining_text = command_prefix + first_line
        
        return global_params, remaining_text
    
    def apply_global_parameters(self, movements: List[StockMovement], global_params: Dict[str, str]) -> List[StockMovement]:
        """Apply global parameters to a list of movements."""
        if not global_params:
            return movements
        
        for movement in movements:
            # Apply driver if not already set
            if 'driver' in global_params and not movement.driver_name:
                movement.driver_name = global_params['driver']
            
            # Apply from_location if not already set
            if 'from' in global_params and not movement.from_location:
                movement.from_location = global_params['from']
            
            # Apply to_location if not already set
            if 'to' in global_params and not movement.to_location:
                movement.to_location = global_params['to']
            
            # Apply project if not already set
            if 'project' in global_params and not movement.project:
                movement.project = global_params['project']
        
        return movements
    
    def parse_batch_entries(self, text: str, user_id: int, user_name: str) -> BatchParseResult:
        """Parse multiple stock movement entries from a single text input."""
        try:
            # Clean and normalize text
            text = text.strip()
            
            # Extract global parameters
            global_params, remaining_text = self.parse_global_parameters(text)
            
            # Detect batch format
            batch_format = self.detect_batch_format(remaining_text)
            
            # Extract movement type from the first command
            first_movement_type = self._extract_movement_type(remaining_text)
            if not first_movement_type:
                return BatchParseResult(
                    format=batch_format,
                    movements=[],
                    total_entries=1,
                    valid_entries=0,
                    errors=["Could not determine movement type. Please start with /in, /out, or /adjust."],
                    is_valid=False,
                    global_parameters=global_params
                )
            
            # Split text into individual entries
            entries = self._split_batch_entries(remaining_text, batch_format)
            
            # Validate batch size
            if len(entries) > self.max_batch_size:
                return BatchParseResult(
                    format=batch_format,
                    movements=[],
                    total_entries=len(entries),
                    valid_entries=0,
                    errors=[
                        f"Batch size {len(entries)} exceeds maximum limit of {self.max_batch_size}.",
                        f"Please split into smaller batches or process fewer items at once."
                    ],
                    is_valid=False,
                    global_parameters=global_params
                )
            
            # Parse each entry and check for movement type consistency
            movements = []
            errors = []
            movement_types = set()
            
            for i, entry in enumerate(entries):
                try:
                    # Check if this entry has a different movement type
                    entry_movement_type = self._extract_movement_type(entry)
                    if entry_movement_type and entry_movement_type != first_movement_type:
                        errors.append(
                            f"Entry #{i+1}: Movement type {entry_movement_type.value} differs from first entry type "
                            f"{first_movement_type.value}. All entries must use the same movement type."
                        )
                        continue
                    
                    # Use the first movement type for all entries
                    movement = self._parse_single_entry(entry, first_movement_type, user_id, user_name)
                    if movement:
                        movements.append(movement)
                        movement_types.add(movement.movement_type)
                    else:
                        errors.append(
                            f"Entry #{i+1}: Could not parse '{entry.strip()}'. "
                            f"Check format: item, quantity unit, [location], [note]"
                        )
                except Exception as e:
                    errors.append(f"Entry #{i+1}: {str(e)}")
            
            # Apply global parameters to all movements
            if movements and global_params:
                movements = self.apply_global_parameters(movements, global_params)
            
            # Validate batch consistency
            consistency_valid, consistency_errors = self._validate_batch_consistency(movements)
            if not consistency_valid:
                errors.extend(consistency_errors)
            
            # Add helpful guidance for specific error patterns
            if len(errors) > 0:
                if len(movements) == 0:
                    errors.append("No valid entries found. Please check the format and try again.")
                
                # Add format guidance based on detected format
                if batch_format == BatchFormat.MIXED:
                    errors.append(
                        "Tip: For clearer batch commands, try using either all newlines or all semicolons, "
                        "not mixed format."
                    )
                elif batch_format == BatchFormat.NEWLINE and len(entries) > 1:
                    errors.append(
                        "Tip: For newline format, make sure each entry is on a separate line and follows "
                        "the pattern: item, quantity unit, [location], [note]"
                    )
                elif batch_format == BatchFormat.SEMICOLON and len(entries) > 1:
                    errors.append(
                        "Tip: For semicolon format, separate entries with semicolons and follow the pattern: "
                        "item, quantity unit, [location], [note]; item2, quantity2 unit2, [location2], [note2]"
                    )
                
                # Add guidance for global parameters if they were used
                if global_params:
                    params_list = ", ".join([f"{k}: {v}" for k, v in global_params.items()])
                    errors.append(
                        f"Note: Global parameters were detected ({params_list}) and will be applied to all entries "
                        f"unless overridden in specific entries."
                    )
                else:
                    # If no global parameters were detected, remind about required project parameter
                    if not any(movement.project for movement in movements):
                        errors.append(
                            f"Tip: You must specify a project using 'project:' parameter at the beginning of your command. "
                            f"Example: /in project: Bridge Construction, cement, 50 bags"
                        )
            
            is_valid = len(errors) == 0 and len(movements) > 0
            
            return BatchParseResult(
                format=batch_format,
                movements=movements,
                total_entries=len(entries),
                valid_entries=len(movements),
                errors=errors,
                is_valid=is_valid,
                global_parameters=global_params
            )
            
        except Exception as e:
            return BatchParseResult(
                format=BatchFormat.SINGLE,
                movements=[],
                total_entries=1,
                valid_entries=0,
                errors=[
                    f"Error parsing batch: {str(e)}",
                    "Please check your command format and try again.",
                    "Use /batchhelp for guidance on correct formats."
                ],
                is_valid=False,
                global_parameters={}
            )
    
    def _split_batch_entries(self, text: str, batch_format: BatchFormat) -> List[str]:
        """Split text into individual entries based on the detected format."""
        if batch_format == BatchFormat.SINGLE:
            return [text]
        
        # Remove the command prefix from the first line only
        # We need to preserve the original text structure for proper parsing
        original_text = text
        
        if batch_format == BatchFormat.NEWLINE:
            # Split by newlines and filter out empty lines
            lines = text.split('\n')
            entries = []
            for line in lines:
                if line.strip():
                    # For the first line, remove the command prefix
                    if line == lines[0]:
                        entry = re.sub(r'^(/in|/out|/adjust|in|out|adjust)\s+', '', line.strip(), count=1)
                    else:
                        entry = line.strip()
                    if entry:
                        entries.append(entry)
        elif batch_format == BatchFormat.SEMICOLON:
            # Split by semicolons and filter out empty entries
            # Remove command prefix from the first part
            text = re.sub(r'^(/in|/out|/adjust|in|out|adjust)\s+', '', text, count=1)
            entries = [entry.strip() for entry in text.split(';') if entry.strip()]
        elif batch_format == BatchFormat.MIXED:
            # Handle mixed format: split by both newlines and semicolons
            # First split by newlines, then by semicolons
            entries = []
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if line.strip():
                    # For the first line, remove the command prefix
                    if i == 0:
                        line = re.sub(r'^(/in|/out|/adjust|in|out|adjust)\s+', '', line.strip(), count=1)
                    else:
                        line = line.strip()
                    
                    if line:
                        # Split line by semicolons
                        line_entries = [entry.strip() for entry in line.split(';') if entry.strip()]
                        entries.extend(line_entries)
        else:
            entries = [text]
        
        return entries
    
    def _parse_single_entry(self, entry: str, movement_type: MovementType, user_id: int, user_name: str) -> Optional[StockMovement]:
        """Parse a single entry into a StockMovement object."""
        try:
            # Remove any remaining command prefixes from the entry
            entry = re.sub(r'^(/in|/out|/adjust|in|out|adjust)\s+', '', entry.strip(), count=1)
            
            # First, try to find the quantity and unit to determine where the item name ends
            # Look for patterns like "X pieces", "X kgs", "X bags", etc.
            # We need to be more careful about not matching dimensions like "100x20mm" or "110mm"
            # Look for the pattern: number + space + unit (but not dimensions)
            # Also handle negative numbers properly
            qty_unit_match = re.search(r'(-?\d+(?:\.\d+)?)\s+(pieces?|kgs?|bags?|sets?|units?|liters?|meters?|tons?|boxes?|rolls?|sheets?|bundles?|pairs?|dozens?|hundreds?|thousands?)(?:\s|$|,|;)', entry, re.IGNORECASE)
            
            if qty_unit_match:
                # Found quantity and unit - everything before this is the item name
                qty_start = qty_unit_match.start()
                item_name = entry[:qty_start].strip().rstrip(',')
                quantity = float(qty_unit_match.group(1))
                unit = qty_unit_match.group(2).lower()
                
                # Normalize unit
                if unit.endswith('s'):
                    unit = unit[:-1]  # Remove plural
                
                # Validate unit
                if unit not in self.units:
                    # Try to find a similar unit
                    for valid_unit in self.units:
                        if valid_unit in unit or unit in valid_unit:
                            unit = valid_unit
                            break
                    else:
                        unit = 'piece'  # Default fallback
                
                # Extract remaining parts for location, notes, etc.
                remaining = entry[qty_unit_match.end():].strip()
                parts = [part.strip() for part in remaining.split(',') if part.strip()]
                
                # Extract components
                location = self._extract_location(parts)
                driver_name = self._extract_driver(parts)
                
                # Extract location based on movement type
                if movement_type == MovementType.IN:
                    # For stock IN: extract "from location" (source)
                    from_location = self._extract_from_location(parts)
                    to_location = None
                else:
                    # For stock OUT/ADJUST: extract "to location" (destination)
                    from_location = None
                    to_location = self._extract_to_location(parts)
                
                note = self._extract_note(parts)
                
                if not item_name:
                    return None
                
                # Create movement
                movement = StockMovement(
                    item_name=item_name,
                    movement_type=movement_type,
                    quantity=quantity,
                    unit=unit,
                    signed_base_quantity=quantity,  # Will be converted later
                    location=location,
                    note=note,
                    status=MovementStatus.POSTED,
                    user_id=str(user_id),
                    user_name=user_name,
                    timestamp=datetime.now(UTC),
                    driver_name=driver_name,  # Keep entry-specific driver if found
                    from_location=from_location,
                    to_location=to_location,
                    project=None  # Set to None initially, will be filled by apply_global_parameters
                )
                
                return movement
            else:
                # Fallback to old method if no clear quantity pattern found
                parts = self._smart_split(entry)
                
                # Extract components
                item_name = self._extract_item_name(parts)
                quantity, unit = self._extract_quantity_unit(parts)
                location = self._extract_location(parts)
                driver_name = self._extract_driver(parts)
                
                # Extract location based on movement type
                if movement_type == MovementType.IN:
                    # For stock IN: extract "from location" (source)
                    from_location = self._extract_from_location(parts)
                    to_location = None
                else:
                    # For stock OUT/ADJUST: extract "to location" (destination)
                    from_location = None
                    to_location = self._extract_to_location(parts)
                
                note = self._extract_note(parts)
                
                if not item_name or not quantity:
                    return None
                
                # Create movement
                movement = StockMovement(
                    item_name=item_name,
                    movement_type=movement_type,
                    quantity=quantity,
                    unit=unit,
                    signed_base_quantity=quantity,  # Will be converted later
                    location=location,
                    note=note,
                    status=MovementStatus.POSTED,
                    user_id=str(user_id),
                    user_name=user_name,
                    timestamp=datetime.now(UTC),
                    driver_name=driver_name,  # Keep entry-specific driver if found
                    from_location=from_location,
                    to_location=to_location,
                    project=None  # Set to None initially, will be filled by apply_global_parameters
                )
                
                return movement
            
        except Exception as e:
            print(f"Error parsing single entry: {e}")
            return None
    
    def _validate_batch_consistency(self, movements: List[StockMovement]) -> Tuple[bool, List[str]]:
        """Validate that all movements in a batch are consistent."""
        if not movements:
            return False, ["No valid movements to process. Please check your input format."]
        
        errors = []
        
        # Check that all movements have the same type
        first_type = movements[0].movement_type
        for i, movement in enumerate(movements):
            if movement.movement_type != first_type:
                errors.append(
                    f"Entry #{i+1}: Movement type {movement.movement_type.value} differs from first entry type "
                    f"{first_type.value}. All entries in a batch must be the same type."
                )
        
        # Check that all movements have required fields
        for i, movement in enumerate(movements):
            if not movement.item_name:
                errors.append(f"Entry #{i+1}: Missing item name. Each entry must include an item name.")
            
            if movement.quantity is None:
                errors.append(f"Entry #{i+1}: Missing quantity. Each entry must include a quantity.")
            elif movement.quantity <= 0 and movement.movement_type != MovementType.ADJUST:
                errors.append(
                    f"Entry #{i+1}: Quantity must be positive for {movement.movement_type.value} movements. "
                    f"Only ADJUST movements can have negative quantities."
                )
            
            # Check for project field (required)
            if not movement.project:
                errors.append(
                    f"Entry #{i+1}: Missing project name. Please specify a project using 'project:' parameter "
                    f"at the beginning of your command."
                )
            
            # Check for reasonable quantities (warn about potential typos)
            if movement.quantity is not None:
                if movement.quantity > 10000:
                    errors.append(
                        f"Entry #{i+1}: Very large quantity detected ({movement.quantity}). "
                        f"Please verify this is correct."
                    )
        
        # Check for duplicate items
        item_counts = {}
        for i, movement in enumerate(movements):
            if movement.item_name:
                item_name = movement.item_name.lower()
                if item_name in item_counts:
                    item_counts[item_name] += 1
                else:
                    item_counts[item_name] = 1
        
        # Warn about potential duplicates
        for item_name, count in item_counts.items():
            if count > 1:
                errors.append(
                    f"Warning: Item '{item_name}' appears {count} times in your batch. "
                    f"Consider combining these entries if they are duplicates."
                )
        
        return len(errors) == 0, errors
    
    def _extract_movement_type(self, text: str) -> Optional[MovementType]:
        """Extract movement type from command."""
        if text.startswith('/in ') or text.startswith('in '):
            return MovementType.IN
        elif text.startswith('/out ') or text.startswith('out '):
            return MovementType.OUT
        elif text.startswith('/adjust ') or text.startswith('adjust '):
            return MovementType.ADJUST
        return None
    
    def _smart_split(self, text: str) -> list:
        """Smart split by multiple separators while preserving context."""
        # Split by comma or "and" (but NOT by hyphen to preserve negative numbers)
        parts = re.split(r'[,]|\sand\s', text)
        
        # Clean and filter parts
        cleaned_parts = []
        for part in parts:
            part = part.strip()
            if part and len(part) > 1:  # Skip empty or single character parts
                cleaned_parts.append(part)
        
        return cleaned_parts
    
    def _extract_item_name(self, parts: list) -> Optional[str]:
        """Extract item name from parts."""
        # Use the first part as the item name
        if parts:
            first_part = parts[0].strip()
            if len(first_part) > 1:  # Accept any reasonable item name
                return first_part
        
        return None
    
    def _extract_quantity_unit(self, parts: list) -> Tuple[Optional[float], Optional[str]]:
        """Extract quantity and unit from parts."""
        for part in parts:
            # Look for quantity + unit pattern (including negative numbers)
            # Use a more explicit pattern for negative numbers
            qty_unit_match = re.search(r'(-?\d+(?:\.\d+)?)\s*(\w+)', part)
            if qty_unit_match:
                quantity = float(qty_unit_match.group(1))
                unit = qty_unit_match.group(2)
                
                # Validate unit
                if unit in self.units:
                    return quantity, unit
                elif unit + 's' in self.units:
                    return quantity, unit + 's'
                elif unit[:-1] in self.units:  # Handle singular forms
                    return quantity, unit[:-1]
        
        # Look for just quantity (including negative numbers)
        for part in parts:
            # Use a more explicit pattern for negative numbers
            qty_match = re.search(r'(-?\d+(?:\.\d+)?)', part)
            if qty_match:
                quantity = float(qty_match.group(1))
                # Try to find unit in nearby parts
                unit = self._find_unit_in_context(parts, part)
                return quantity, unit
        
        return None, None
    
    def _find_unit_in_context(self, parts: list, current_part: str) -> Optional[str]:
        """Find unit in context of quantity."""
        current_index = parts.index(current_part)
        
        # Check current part for unit
        for unit in self.units:
            if unit in current_part:
                return unit
        
        # Check adjacent parts
        for offset in [-1, 1]:
            check_index = current_index + offset
            if 0 <= check_index < len(parts):
                check_part = parts[check_index]
                for unit in self.units:
                    if unit in check_part:
                        return unit
        
        # Default to 'piece' if no unit found
        return 'piece'
    
    def _extract_location(self, parts: list) -> Optional[str]:
        """Extract destination location."""
        for i, part in enumerate(parts):
            # Skip the first part (item name) and parts with "from" or "by"
            if i == 0 or 'from' in part or 'by' in part:
                continue
                
            # Look for location keywords
            for keyword in self.location_keywords:
                if keyword in part:
                    # Extract location after keyword
                    location = part.replace(keyword, '').strip()
                    if location and len(location) > 2:
                        return location
                    
                    # Check next part if current part is just the keyword
                    if part.strip() == keyword and i + 1 < len(parts):
                        return parts[i + 1].strip()
        
        # Look for common location words (but not in the first part which is the item)
        for i, part in enumerate(parts):
            if i > 0:  # Skip the first part (item name)
                if any(loc in part.lower() for loc in ['warehouse', 'site', 'office', 'yard']) and 'by' not in part and 'from' not in part:
                    return part
        
        return None
    
    def _extract_driver(self, parts: list) -> Optional[str]:
        """Extract driver name."""
        # Look for "by" keyword specifically
        for i, part in enumerate(parts):
            if "by" in part.lower():
                # Extract the driver name after "by"
                driver = part.lower().replace("by", "", 1).strip()
                if driver and len(driver) > 2:
                    # Return the original case from the part
                    start_idx = part.lower().find(driver)
                    if start_idx >= 0:
                        return part[start_idx:start_idx+len(driver)]
                    return driver
                    
                # Check if it's just "by" and the next part is the driver name
                if part.strip().lower() == "by":
                    # Look for next part as driver name
                    current_index = parts.index(part)
                    if current_index + 1 < len(parts):
                        return parts[current_index + 1].strip()
        
        # Look for other driver keywords
        for i, part in enumerate(parts):
            for keyword in self.driver_keywords:
                if keyword != "by" and keyword.lower() in part.lower():
                    driver = part.lower().replace(keyword.lower(), "", 1).strip()
                    if driver and len(driver) > 2:
                        start_idx = part.lower().find(driver)
                        if start_idx >= 0:
                            return part[start_idx:start_idx+len(driver)]
                        return driver
        
        # Look for "Mr" or "Ms" patterns
        for part in parts:
            if any(title in part.lower() for title in ['mr ', 'ms ', 'mrs ', 'mr.', 'ms.', 'mrs.']):
                return part
        
        # Don't try to guess driver names anymore - rely on global parameters
        return None
    
    def _extract_from_location(self, parts: list) -> Optional[str]:
        """Extract source location for stock IN movements."""
        for i, part in enumerate(parts):
            for keyword in self.from_keywords:
                if keyword in part:
                    from_loc = part.replace(keyword, '').strip()
                    if from_loc:
                        return from_loc
                    
                    # Check if it's just the keyword
                    if part.strip() == keyword:
                        # Look for next part as location
                        current_index = parts.index(part)
                        if current_index + 1 < len(parts):
                            return parts[current_index + 1].strip()
        
        return None
    
    def _extract_to_location(self, parts: list) -> Optional[str]:
        """Extract destination location for stock OUT/ADJUST movements."""
        for i, part in enumerate(parts):
            # Look for "to" keyword
            if 'to ' in part:
                to_loc = part.replace('to ', '').strip()
                if to_loc and len(to_loc) > 2:
                    return to_loc
                
                # Check if it's just "to"
                if part.strip() == 'to':
                    # Look for next part as location
                    current_index = parts.index(part)
                    if current_index + 1 < len(parts):
                        return parts[current_index + 1].strip()
            
            # Look for location keywords (but not "from" keywords)
            for keyword in self.location_keywords:
                if keyword in part and 'from' not in part:
                    location = part.replace(keyword, '').strip()
                    if location and len(location) > 2:
                        return location
        
        # For OUT commands, if no explicit "to" found, use the location field
        # This handles cases like "/out item, qty, unit, location, driver"
        return None
    
    def _extract_note(self, parts: list) -> Optional[str]:
        """Extract note from remaining parts."""
        notes = []
        for part in parts:
            # Skip parts that are clearly not notes
            if not any(keyword in part for keyword in 
                      self.units + self.location_keywords + self.driver_keywords + self.from_keywords):
                # Check if it's not a quantity
                if not re.search(r'\d', part):
                    # Skip if it's the first part (likely the item name)
                    if part != parts[0]:
                        notes.append(part)
        
        if notes:
            return ' - '.join(notes)
        return None
