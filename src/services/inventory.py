"""Inventory stocktake service for the Construction Inventory Bot."""

import logging
import re
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from schemas import Item
from services.category_parser import category_parser

logger = logging.getLogger(__name__)


@dataclass
class InventoryHeader:
    """Parsed inventory header information."""
    date: str  # DD/MM/YY format
    logged_by: List[str]  # List of names
    category: Optional[str] = None  # Optional category override
    raw_text: str = ""
    normalized_date: str = ""  # ISO YYYY-MM-DD format


@dataclass
class InventoryEntry:
    """Parsed inventory entry."""
    item_name: str
    quantity: float
    line_number: int
    raw_text: str


@dataclass
class InventoryParseResult:
    """Result of parsing inventory command."""
    header: InventoryHeader
    entries: List[InventoryEntry]
    total_lines: int
    valid_entries: int
    errors: List[str]
    is_valid: bool
    blank_lines: int = 0
    comment_lines: int = 0
    skipped_lines: int = 0


class InventoryParser:
    """Parser for inventory stocktake commands."""

    def __init__(self, max_entries: int = 50):
        """Initialize the inventory parser."""
        self.max_entries = max_entries

    def parse_inventory_command(self, command_text: str) -> InventoryParseResult:
        """
        Parse an inventory command with header and entries.

        Format:
        /inventory date:DD/MM/YY logged by: NAME1,NAME2
        Item Name, Quantity
        Item Name, Quantity
        ...
        """
        # Normalize line endings to \n
        command_text = command_text.replace('\r\n', '\n').replace('\r', '\n')
        lines = command_text.split('\n')
        if len(lines) < 2:
            return InventoryParseResult(
                header=InventoryHeader("", [], "", ""),
                entries=[],
                total_lines=0,
                valid_entries=0,
                errors=["Command must have at least a header and one entry line"],
                is_valid=False
            )

        # Parse header (first line)
        header_result = self._parse_header(lines[0])
        if not header_result:
            return InventoryParseResult(
                header=InventoryHeader("", [], "", ""),
                entries=[],
                total_lines=len(lines),
                valid_entries=0,
                errors=["Invalid header format. Expected: date:DD/MM/YY logged by: NAME1,NAME2"],
                is_valid=False
            )

        # Parse entry lines (remaining lines)
        entries_result = self._parse_entries(lines[1:])

        # Combine results
        total_valid = len(entries_result["entries"])
        # Command is valid only if header is valid AND there's at least one valid entry
        is_valid = header_result and entries_result["is_valid"] and total_valid > 0
        
        # Add error if no valid entries found
        errors = entries_result["errors"].copy()
        if total_valid == 0 and header_result:
            errors.append("Command must have at least a header and one entry line")

        return InventoryParseResult(
            header=header_result,
            entries=entries_result["entries"],
            total_lines=len(lines),
            valid_entries=total_valid,
            errors=errors,
            is_valid=is_valid,
            blank_lines=entries_result.get("stats", {}).get("blank_lines", 0),
            comment_lines=entries_result.get("stats", {}).get("comment_lines", 0),
            skipped_lines=entries_result.get("stats", {}).get("skipped_lines", 0)
        )

    def _parse_header(self, header_line: str) -> Optional[InventoryHeader]:
        """Parse the header line for date, logged by, and optional category information."""
        # Pattern: date:DD/MM/YY logged by: NAME1,NAME2 [category: CATEGORY]
        # Allow flexible whitespace and variations, category can be anywhere
        # First, extract the date
        date_match = re.search(r'date:\s*(\d{1,2}/\d{1,2}/\d{2})', header_line, re.IGNORECASE)
        if not date_match:
            return None
        
        date_str = date_match.group(1)
        
        # Extract logged by
        logged_by_match = re.search(r'(?:logged\s+by|logged_by):\s*(.+?)(?=\s+category:|$)', header_line, re.IGNORECASE)
        if not logged_by_match:
            return None
        
        logged_by_text = logged_by_match.group(1).strip()
        
        # Extract category if present
        category_match = re.search(r'category:\s*([^\s]+)', header_line, re.IGNORECASE)
        category = category_match.group(1).strip() if category_match else None

        # Validate date format
        if not self._is_valid_date(date_str):
            return None

        # Parse logged by names (comma-separated)
        logged_by = [name.strip() for name in logged_by_text.split(',') if name.strip()]

        if not logged_by:
            return None

        # Normalize date to ISO format
        normalized_date = self._normalize_date(date_str)

        return InventoryHeader(
            date=date_str,
            logged_by=logged_by,
            category=category,
            raw_text=header_line,
            normalized_date=normalized_date
        )

    def _normalize_date(self, date_str: str) -> str:
        """Convert DD/MM/YY to ISO YYYY-MM-DD format."""
        try:
            day, month, year = map(int, date_str.split('/'))
            
            # Convert 2-digit year to 4-digit year
            if year < 50:  # Assume 20xx for years 00-49
                year += 2000
            else:  # Assume 19xx for years 50-99
                year += 1900
            
            return f"{year:04d}-{month:02d}-{day:02d}"
        except (ValueError, AttributeError):
            # Return original if normalization fails
            return date_str

    def _parse_entries(self, entry_lines: List[str]) -> Dict:
        """Parse entry lines for item names and quantities."""
        entries = []
        errors = []
        item_count = 0
        blank_lines = 0
        comment_lines = 0
        skipped_lines = 0

        # Track items for deduplication (case-insensitive)
        seen_items = {}

        for line_num, line in enumerate(entry_lines, start=2):  # Start at 2 since header is line 1
            line = line.strip()

            # Skip empty lines
            if not line:
                blank_lines += 1
                continue

            # Skip comment lines
            if line.startswith('#'):
                comment_lines += 1
                continue

            # Check if we've exceeded the maximum entries
            if item_count >= self.max_entries:
                errors.append(f"Line {line_num}: Maximum of {self.max_entries} entries exceeded")
                break

            # Parse entry line
            entry_result = self._parse_entry_line(line, line_num)
            if entry_result:
                item_name = entry_result.item_name.lower()  # Use lowercase for deduplication

                # If we've seen this item before, remove the previous entry
                if item_name in seen_items:
                    entries = [e for e in entries if e.item_name.lower() != item_name]
                    item_count -= 1

                # Add the new entry
                entries.append(entry_result)
                seen_items[item_name] = True
                item_count += 1
            else:
                errors.append(f"Line {line_num}: Invalid format. Expected: Item Name, Quantity")
                skipped_lines += 1

        return {
            "entries": entries,
            "errors": errors,
            "is_valid": len(errors) == 0,
            "stats": {
                "blank_lines": blank_lines,
                "comment_lines": comment_lines,
                "skipped_lines": skipped_lines
            }
        }

    def _parse_entry_line(self, line: str, line_number: int) -> Optional[InventoryEntry]:
        """Parse a single entry line for item name and quantity."""
        # Pattern: Item Name, Quantity
        # Allow flexible whitespace around comma
        parts = line.split(',', 1)
        if len(parts) != 2:
            return None

        item_name = parts[0].strip()
        quantity_str = parts[1].strip()

        # Validate item name
        if not item_name:
            return None

        # Validate and parse quantity (allow units like "5 cans" → 5.0)
        try:
            # Extract numeric part from quantity string (e.g., "5 cans" → "5")
            import re
            quantity_match = re.search(r'(\d+(?:\.\d+)?)', quantity_str)
            if quantity_match:
                quantity = float(quantity_match.group(1))
            else:
                # Try to parse the entire string as a number
                quantity = float(quantity_str)
            
            # Check for special values
            if quantity != quantity:  # NaN check
                return None
            if quantity == float('inf') or quantity == float('-inf'):
                return None
            # Reject negative quantities for inventory stocktake
            if quantity < 0:
                return None
        except ValueError:
            return None

        return InventoryEntry(
            item_name=item_name,
            quantity=quantity,
            line_number=line_number,
            raw_text=line
        )

    def _is_valid_date(self, date_str: str) -> bool:
        """Validate date format DD/MM/YY."""
        try:
            day, month, year = map(int, date_str.split('/'))

            # Basic validation
            if day < 1 or day > 31:
                return False
            if month < 1 or month > 12:
                return False
            if year < 0 or year > 99:
                return False

            # Additional validation for specific months
            if month in [4, 6, 9, 11] and day > 30:
                return False
            if month == 2:
                # Simple leap year check (not perfect but good enough for YY format)
                if year % 4 == 0 and day > 29:
                    return False
                elif year % 4 != 0 and day > 28:
                    return False

            return True
        except (ValueError, AttributeError):
            return False

    def _generate_corrected_template(self, command_text: str, errors: List[str]) -> Optional[str]:
        """Generate a corrected template when parsing fails."""
        try:
            lines = command_text.split('\n')
            if len(lines) < 2:
                return None
            
            # Try to extract a working header
            header_line = lines[0].strip()
            if not header_line.startswith('/inventory'):
                header_line = '/inventory ' + header_line
            
            # Check if header has the right format
            if 'date:' not in header_line.lower() or 'logged' not in header_line.lower():
                # Provide a complete template
                return "/inventory date:25/01/25 logged by: YourName\nItem Name, Quantity\nItem Name, Quantity"
            
            # If header looks good, just show the format for entries
            return f"{header_line}\nItem Name, Quantity\nItem Name, Quantity"
            
        except Exception:
            return None


class InventoryService:
    """Service for processing inventory stocktake operations."""

    def __init__(self, airtable_client, settings, audit_trail_service=None, persistent_idempotency_service=None):
        """Initialize the inventory service."""
        self.airtable = airtable_client
        self.settings = settings
        self.parser = InventoryParser()
        self.audit_trail_service = audit_trail_service
        self.persistent_idempotency_service = persistent_idempotency_service

    def _extract_unit_info_from_name(self, item_name: str) -> Tuple[float, str]:
        """
        Extract unit size and type from item name if specified.
        
        Examples:
        - "20 ltrs white shene" -> (20.0, "ltrs")
        - "5 litres red oxide" -> (5.0, "litres")
        - "Cement 50kg" -> (50.0, "kg")
        - "Steel Beam" -> (1.0, "piece")
        
        Returns:
            Tuple of (unit_size, unit_type)
        """
        try:
            import re
            
            # First, try to match unit info anywhere in the item name (not just at the end)
            # Pattern: Number + Unit (e.g., "20 ltrs", "5 litres", "50kg")
            unit_pattern = r'(\d+(?:\.\d+)?)\s*([a-zA-Z]+)'
            unit_matches = re.findall(unit_pattern, item_name)
            
            if unit_matches:
                # Use the first unit match found
                unit_size_str, unit_type = unit_matches[0]
                unit_size = float(unit_size_str)
                
                # Validate unit_size
                if unit_size <= 0:
                    logger.warning(f"Invalid unit_size {unit_size} extracted from {item_name}, defaulting to 1.0")
                    return 1.0, "piece"
                
                # Map common unit types to standardized values
                unit_type_mapping = {
                    "ltrs": "litre",
                    "litres": "litre",
                    "ltr": "litre",
                    "kg": "kg",
                    "kgs": "kg",
                    "ton": "ton",
                    "tons": "ton",
                    "m": "m",
                    "meter": "m",
                    "meters": "m",
                    "bag": "bag",
                    "bags": "bag",
                    "piece": "piece",
                    "pieces": "piece"
                }
                
                standardized_unit_type = unit_type_mapping.get(unit_type.lower(), unit_type.lower())
                
                logger.info(f"Extracted unit info from '{item_name}': size={unit_size}, type={standardized_unit_type}")
                return unit_size, standardized_unit_type
            
            # No unit info found, return defaults
            return 1.0, "piece"
            
        except Exception as e:
            logger.warning(f"Error extracting unit info from '{item_name}': {e}, using defaults")
            return 1.0, "piece"

    async def process_inventory_stocktake(self, command_text: str, user_id: int, user_name: str, 
                                       validate_only: bool = False) -> Tuple[bool, str]:
        """
        Process an inventory stocktake command.

        Args:
            command_text: The command text to process
            user_id: User ID for logging
            user_name: User name for logging
            validate_only: If True, only parse and validate without writing to database

        Returns:
            Tuple of (success, message)
        """
        try:
            # Parse the command
            parse_result = self.parser.parse_inventory_command(command_text)

            if not parse_result.is_valid:
                error_message = "❌ <b>Inventory Command Parse Errors</b>\n\n"
                for error in parse_result.errors:
                    error_message += f"• {error}\n"
                
                # Add statistics about ignored lines
                if parse_result.blank_lines > 0 or parse_result.comment_lines > 0:
                    error_message += f"\n📊 <b>Lines Processed:</b>\n"
                    if parse_result.blank_lines > 0:
                        error_message += f"• {parse_result.blank_lines} blank lines ignored\n"
                    if parse_result.comment_lines > 0:
                        error_message += f"• {parse_result.comment_lines} comment lines ignored\n"
                
                error_message += "\n<b>Expected Format:</b>\n"
                error_message += "/inventory date:DD/MM/YY logged by: NAME1,NAME2 [category: CATEGORY]\n"
                error_message += "Item Name, Quantity\n"
                error_message += "Item Name, Quantity\n"
                error_message += "\n💡 <b>Tips:</b>\n"
                error_message += "• Use 'logged by:' or 'logged_by:' (both work)\n"
                error_message += "• Use 'category: CATEGORY' to override auto-detection\n"
                error_message += "• Comment lines starting with # are ignored\n"
                error_message += "• Blank lines are ignored\n"
                error_message += "• Maximum 50 entries allowed\n"
                
                # Generate corrected template
                corrected_template = self.parser._generate_corrected_template(command_text, parse_result.errors)
                if corrected_template:
                    error_message += f"\n🔧 <b>Corrected Template:</b>\n{corrected_template}"
                
                return False, error_message

            if validate_only:
                # Return validation report without processing
                return True, self._generate_validation_report(parse_result)

            # Generate batch ID for audit trail
            batch_id = None
            if self.audit_trail_service:
                batch_id = self.audit_trail_service.generate_batch_id()

            # Process each entry
            results = []
            updated_items = 0
            created_items = 0
            failed_items = 0

            for entry in parse_result.entries:
                result = await self._process_inventory_entry(entry, parse_result.header.normalized_date, user_name, parse_result.header.category)
                results.append(result)

                if result["success"]:
                    if result["created"]:
                        created_items += 1
                    else:
                        updated_items += 1
                else:
                    failed_items += 1

            # Create audit trail records for successful entries
            if self.audit_trail_service and batch_id:
                try:
                    audit_records = await self.audit_trail_service.create_audit_records(
                        batch_id=batch_id,
                        date=parse_result.header.normalized_date,
                        logged_by=parse_result.header.logged_by,
                        entries=results,
                        user_name=user_name
                    )
                    logger.info(f"Created {len(audit_records)} audit records for batch {batch_id}")
                except Exception as e:
                    logger.error(f"Failed to create audit trail: {e}")
                    # Continue even if audit trail creation fails

            # Generate summary message
            summary = self._generate_summary(
                parse_result.header,
                updated_items,
                created_items,
                failed_items,
                results,
                batch_id,
                parse_result
            )

            return True, summary

        except Exception as e:
            logger.error(f"Error processing inventory stocktake: {e}")
            return False, f"❌ <b>Error processing inventory stocktake:</b>\n{str(e)}"

    def _generate_validation_report(self, parse_result: InventoryParseResult) -> str:
        """Generate a validation report without processing entries."""
        report = f"✅ <b>Inventory Command Validation Successful</b>\n\n"
        report += f"<b>Date:</b> {parse_result.header.date} (normalized to {parse_result.header.normalized_date})\n"
        report += f"<b>Logged by:</b> {', '.join(parse_result.header.logged_by)}\n"
        if parse_result.header.category:
            report += f"<b>Category Override:</b> {parse_result.header.category}\n"
        report += f"<b>Total lines:</b> {parse_result.total_lines}\n"
        report += f"<b>Valid entries:</b> {parse_result.valid_entries}\n"
        
        # Add statistics about ignored lines
        if parse_result.blank_lines > 0 or parse_result.comment_lines > 0:
            report += f"\n📊 <b>Lines Processed:</b>\n"
            if parse_result.blank_lines > 0:
                report += f"• {parse_result.blank_lines} blank lines ignored\n"
            if parse_result.comment_lines > 0:
                report += f"• {parse_result.comment_lines} comment lines ignored\n"
        
        report += "\n📋 <b>Parsed Entries:</b>\n"
        for entry in parse_result.entries:
            if parse_result.header.category:
                # Use category override
                detected_category = parse_result.header.category
            else:
                # Auto-detect category
                detected_category = category_parser.parse_category(entry.item_name)
            report += f"• {entry.item_name} → {detected_category}: {entry.quantity}\n"
        
        report += f"\n💡 <b>Ready to apply!</b> Use the same command without 'validate' to process."
        if parse_result.header.category:
            report += f"\n\n🔍 <b>Category Override Applied:</b> All items will use category '{parse_result.header.category}'"
        else:
            report += f"\n\n🔍 <b>Smart Category Detection:</b> Categories are automatically detected from item names."
        
        return report

    async def _process_inventory_entry(self, entry: InventoryEntry, normalized_date: str, user_name: str, category_override: Optional[str] = None) -> Dict:
        """Process a single inventory entry."""
        try:
            # Check if item exists
            existing_item = await self.airtable.get_item(entry.item_name)

            if existing_item:
                # Store previous quantity for audit trail
                previous_quantity = existing_item.on_hand
                
                # Update category and base unit if override is specified and different from current
                if category_override and existing_item.category != category_override:
                    try:
                        # Apply the same category mapping logic used in create_item_if_not_exists
                        # Map common categories to valid Airtable options
                        category_mapping = {
                            "general": "Steel",
                            "steel": "Steel",
                            "electrical": "Electrical", 
                            "cement": "Cement",
                            "paint": "Paint",  # Map paint to existing Paint category
                            "plumbing": "Steel",
                            "safety": "Steel",
                            "tools": "Steel",
                            "equipment": "Steel",
                            "construction materials": "Construction Materials",
                            "white": "Paint",
                            "bitumec": "Paint",
                            "litres": "Paint"
                        }
                        
                        # Use mapped category or default to Steel if not mapped
                        mapped_category = category_mapping.get(category_override.lower(), "Steel")
                        
                        await self.airtable.update_item_category(entry.item_name, mapped_category)
                        logger.info(f"Updated {entry.item_name} category from {existing_item.category} to {mapped_category} (mapped from '{category_override}')")
                        
                        # Also update the base unit for paint items to use "litre" instead of "piece"
                        if mapped_category == "Paint":
                            # Extract unit info from item name to determine correct base unit
                            unit_size, unit_type = self._extract_unit_info_from_name(entry.item_name)
                            if unit_type and unit_type != "piece":
                                # Update base unit to the extracted unit type
                                await self.airtable.update_item_base_unit(entry.item_name, unit_type)
                                logger.info(f"Updated {entry.item_name} base unit to {unit_type} (extracted from item name)")
                            else:
                                # Default to "litre" for paint items if no specific unit found
                                await self.airtable.update_item_base_unit(entry.item_name, "litre")
                                logger.info(f"Updated {entry.item_name} base unit to 'litre' (default for paint items)")
                        
                    except Exception as e:
                        logger.warning(f"Failed to update category/base unit for {entry.item_name}: {e}")
                
                # Update existing item
                success = await self._update_item_stock(entry.item_name, entry.quantity, existing_item, normalized_date, user_name)
                if success:
                    return {
                        "success": True,
                        "created": False,
                        "item_name": entry.item_name,
                        "quantity": entry.quantity,
                        "previous_quantity": previous_quantity,
                        "message": f"Updated {entry.item_name} stock to {entry.quantity}"
                    }
                else:
                    return {
                        "success": False,
                        "created": False,
                        "item_name": entry.item_name,
                        "quantity": entry.quantity,
                        "previous_quantity": previous_quantity,
                        "message": f"Failed to update {entry.item_name} stock"
                    }
            else:
                # Create new item with enhanced defaults
                try:
                    # Extract unit size and type from item name if specified (e.g., "Paint 20ltrs")
                    unit_size, unit_type = self._extract_unit_info_from_name(entry.item_name)
                    
                    # Use category override if provided, otherwise auto-detect
                    if category_override:
                        detected_category = category_override
                    else:
                        detected_category = category_parser.parse_category(entry.item_name)
                    
                    # Determine base unit from item name or use detected unit type
                    # For paint items, use the extracted unit type (e.g., "litre" instead of "piece")
                    if unit_type and unit_type != "piece":
                        base_unit = unit_type
                    else:
                        # Fallback to piece for items without specific units
                        base_unit = "piece"
                    
                    logger.info(f"Determined base unit for {entry.item_name}: {base_unit} (from unit_type: {unit_type})")
                    
                    new_item_id = await self.airtable.create_item_if_not_exists(
                        item_name=entry.item_name,
                        base_unit=base_unit,  # Dynamic based on item name
                        category=detected_category,  # Use override or auto-detected category
                        unit_size=unit_size,
                        unit_type=unit_type
                    )
                    
                    if new_item_id:
                        # Set the stock level
                        stock_success = await self._update_item_stock(entry.item_name, entry.quantity, None, normalized_date, user_name)
                        if stock_success:
                                                    return {
                            "success": True,
                            "created": True,
                            "item_name": entry.item_name,
                            "quantity": entry.quantity,
                            "previous_quantity": 0.0,  # New items start with 0
                            "message": f"Created {entry.item_name} (Category: {detected_category}) with stock level {entry.quantity}"
                        }
                        else:
                            return {
                                "success": False,
                                "created": True,
                                "item_name": entry.item_name,
                                "quantity": entry.quantity,
                                "previous_quantity": 0.0,  # New items start with 0
                                "message": f"Created {entry.item_name} but failed to set stock level"
                            }
                    else:
                        return {
                            "success": False,
                            "created": False,
                            "item_name": entry.item_name,
                            "quantity": entry.quantity,
                            "previous_quantity": 0.0,
                            "message": f"Failed to create {entry.item_name}"
                        }
                except Exception as e:
                    logger.error(f"Error creating item {entry.item_name}: {e}")
                    return {
                        "success": False,
                        "created": False,
                        "item_name": entry.item_name,
                        "quantity": entry.quantity,
                        "previous_quantity": 0.0,
                        "message": f"Error creating item: {str(e)}"
                    }

        except Exception as e:
            logger.error(f"Error processing inventory entry {entry.item_name}: {e}")
            return {
                "success": False,
                "created": False,
                "item_name": entry.item_name,
                "quantity": entry.quantity,
                "previous_quantity": 0.0,
                "message": f"Error: {str(e)}"
            }

    async def _update_item_stock(self, item_name: str, new_quantity: float, existing_item: Optional[Item] = None,
                                normalized_date: str = "", user_name: str = "") -> bool:
        """Update item stock to a specific quantity (not increment/decrement)."""
        try:
            # Use existing item if provided, otherwise get it
            if existing_item is None:
                item = await self.airtable.get_item(item_name)
                if not item:
                    return False
            else:
                item = existing_item

            # Calculate the change needed
            quantity_change = new_quantity - item.on_hand

            # Use the existing update method
            success = await self.airtable.update_item_stock(item_name, quantity_change)
            
            if success and normalized_date and user_name:
                # Update provenance fields if available
                try:
                    await self._update_provenance_fields(item_name, normalized_date, user_name)
                except Exception as e:
                    logger.warning(f"Failed to update provenance fields for {item_name}: {e}")
                    # Don't fail the main operation if provenance update fails
            
            return success

        except Exception as e:
            logger.error(f"Error updating item stock for {item_name}: {e}")
            return False

    async def _update_provenance_fields(self, item_name: str, normalized_date: str, user_name: str):
        """Update provenance fields for an item."""
        try:
            # Update the Airtable fields for Last Stocktake Date and Last Stocktake By
            success = await self.airtable.update_item_provenance(item_name, normalized_date, user_name)
            if success:
                logger.info(f"Updated provenance for {item_name}: date={normalized_date}, by={user_name}")
            else:
                logger.warning(f"Failed to update provenance for {item_name}")
            
        except Exception as e:
            logger.error(f"Error updating provenance fields for {item_name}: {e}")
            raise

    def _generate_summary(self, header: InventoryHeader, updated_items: int,
                         created_items: int, failed_items: int, results: List[Dict], 
                         batch_id: Optional[str] = None, parse_result: Optional[InventoryParseResult] = None) -> str:
        """Generate a summary message for the inventory operation."""
        summary = f"📊 <b>Inventory Stocktake Complete</b>\n\n"
        summary += f"<b>Date:</b> {header.date} (normalized to {header.normalized_date})\n"
        summary += f"<b>Logged by:</b> {', '.join(header.logged_by)}\n"
        
        if batch_id:
            summary += f"<b>Batch ID:</b> {batch_id}\n"
        
        summary += f"\n✅ <b>Results:</b>\n"
        summary += f"• Items updated: {updated_items}\n"
        summary += f"• Items created: {created_items}\n"
        summary += f"• Items failed: {failed_items}\n"
        
        # Add statistics about ignored lines if available
        if parse_result and (parse_result.blank_lines > 0 or parse_result.comment_lines > 0):
            summary += f"\n📊 <b>Lines Processed:</b>\n"
            if parse_result.blank_lines > 0:
                summary += f"• {parse_result.blank_lines} blank lines ignored\n"
            if parse_result.comment_lines > 0:
                summary += f"• {parse_result.comment_lines} comment lines ignored\n"
            if parse_result.skipped_lines > 0:
                summary += f"• {parse_result.skipped_lines} invalid lines skipped\n"

        if failed_items > 0:
            summary += f"\n❌ <b>Failed Items:</b>\n"
            for result in results:
                if not result["success"]:
                    summary += f"• {result['item_name']}: {result['message']}\n"
        
        # Add warnings for new items with default values
        if created_items > 0:
            summary += f"\n⚠️ <b>New Items Created:</b>\n"
            summary += f"• {created_items} items created with enhanced structure\n"
            summary += f"• Unit size and type extracted from item names (e.g., 'Paint 20ltrs' → size=20, type=ltrs)\n"
            summary += f"• Categories automatically detected using smart parsing\n"
            summary += f"• These can be updated later with proper categorization and unit specifications\n"
            
            # Show enhanced item examples if any were created with unit size > 1
            enhanced_items = [r for r in results if r.get("success") and r.get("created")]
            if enhanced_items:
                summary += f"\n🔍 <b>Enhanced Items Created:</b>\n"
                for result in enhanced_items[:3]:  # Show first 3 enhanced items
                    item_name = result.get("item_name", "Unknown")
                    quantity = result.get("quantity", 0)
                    # Try to extract unit info from the name for display
                    unit_size, unit_type = self._extract_unit_info_from_name(item_name)
                    # Get detected category for display
                    detected_category = category_parser.parse_category(item_name)
                    
                    if unit_size > 1.0 and unit_type != "piece":
                        total_volume = unit_size * quantity
                        summary += f"• {item_name} (Category: {detected_category}): {quantity} units × {unit_size} {unit_type} = {total_volume} {unit_type}\n"
                    else:
                        summary += f"• {item_name} (Category: {detected_category}): {quantity} {unit_type}\n"
                
                if len(enhanced_items) > 3:
                    summary += f"... and {len(enhanced_items) - 3} more enhanced items\n"
        
        if batch_id and self.audit_trail_service:
            summary += f"\n📋 <b>Audit Trail:</b> Created for all successful entries (Batch: {batch_id})"

        return summary
