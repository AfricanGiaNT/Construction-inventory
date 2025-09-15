"""Inventory stocktake service for the Construction Inventory Bot."""

import logging
import re
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from schemas import Item
from services.category_parser import category_parser
from services.smart_unit_converter import smart_unit_converter
from services.duplicate_detection import DuplicateDetectionService, DuplicateDetectionResult

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
                errors=["Invalid header format. Expected: logged by: NAME1,NAME2 [date:DD/MM/YY] [category: CATEGORY]"],
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
        # Pattern: [date:DD/MM/YY] logged by: NAME1,NAME2 [category: CATEGORY]
        # Date is now optional - if not provided, defaults to current date
        # Allow flexible whitespace and variations, category can be anywhere
        
        # Extract the date (optional)
        date_match = re.search(r'date:\s*(\d{1,2}/\d{1,2}/\d{2})', header_line, re.IGNORECASE)
        if date_match:
            date_str = date_match.group(1)
        else:
            # Default to current date in DD/MM/YY format
            from datetime import datetime
            current_date = datetime.now()
            date_str = current_date.strftime("%d/%m/%y")
        
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

                # If we've seen this item before, combine the quantities
                if item_name in seen_items:
                    # Find the existing entry and add the quantities
                    for existing_entry in entries:
                        if existing_entry.item_name.lower() == item_name:
                            existing_entry.quantity += entry_result.quantity
                            logger.info(f"Combined quantities for {entry_result.item_name}: {existing_entry.quantity - entry_result.quantity} + {entry_result.quantity} = {existing_entry.quantity}")
                            break
                else:
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
            
            # Check if header has the right format (logged by is required, date is optional)
            if 'logged' not in header_line.lower():
                # Provide a complete template
                return "/inventory logged by: YourName\nItem Name, Quantity\nItem Name, Quantity"
            
            # If header looks good, just show the format for entries
            return f"{header_line}\nItem Name, Quantity\nItem Name, Quantity"
            
        except Exception:
            return None


class InventoryService:
    """Service for processing inventory stocktake operations."""

    def __init__(self, airtable_client, settings, audit_trail_service=None, persistent_idempotency_service=None, duplicate_detection_service=None):
        """Initialize the inventory service."""
        self.airtable = airtable_client
        self.settings = settings
        self.parser = InventoryParser()
        self.audit_trail_service = audit_trail_service
        self.persistent_idempotency_service = persistent_idempotency_service
        self.duplicate_detection_service = duplicate_detection_service or DuplicateDetectionService(airtable_client)

    def _extract_unit_info_from_name(self, item_name: str) -> Tuple[float, str]:
        """
        Extract unit size and type from item name using smart conversion.
        
        This method now uses the SmartUnitConverter to extract unit specifications
        for tracking purposes (no base unit field needed).
        
        Examples:
        - "20l pva plascon plaster primer" -> (20.0, "l")      # Volume spec
        - "Green cable 1.5sqm 100meters" -> (1.5, "sqm")      # Area spec  
        - "Cement 50kg" -> (50.0, "kg")                        # Weight spec
        - "Steel Beam 6m" -> (6.0, "m")                        # Length spec
        
        Returns:
            Tuple of (unit_size, detected_unit_type)
        """
        try:
            # Use smart converter for intelligent extraction
            conversion_result = smart_unit_converter.convert_item_specification(item_name)
            
            logger.info(f"Smart conversion result: {conversion_result.original_input} → "
                       f"size={conversion_result.detected_unit_size}, "
                       f"type={conversion_result.detected_unit_type}, "
                       f"confidence={conversion_result.confidence:.2f}")
            
            if conversion_result.confidence < 0.5:
                logger.warning(f"Low confidence ({conversion_result.confidence:.2f}) for conversion: {conversion_result.notes}")
            
            return conversion_result.detected_unit_size, conversion_result.detected_unit_type
            
        except Exception as e:
            logger.warning(f"Error in smart unit extraction for '{item_name}': {e}, using defaults")
            return 1.0, "piece"

    async def process_inventory_stocktake(self, command_text: str, user_id: int, user_name: str, 
                                       validate_only: bool = False, telegram_service=None, chat_id: int = None) -> Tuple[bool, str]:
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
                error_message += "/inventory logged by: NAME1,NAME2 [date:DD/MM/YY] [category: CATEGORY]\n"
                error_message += "Item Name, Quantity\n"
                error_message += "Item Name, Quantity\n"
                error_message += "\n💡 <b>Tips:</b>\n"
                error_message += "• Use 'logged by:' or 'logged_by:' (both work)\n"
                error_message += "• Date is optional - defaults to today if not provided\n"
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

            # Check for duplicates if telegram_service and chat_id are provided
            if telegram_service and chat_id is not None:
                duplicate_result = await self._check_for_duplicates(parse_result.entries, user_name)
                if duplicate_result.has_duplicates:
                    # Send duplicate confirmation dialog
                    message_id = await telegram_service.send_duplicate_confirmation(
                        chat_id, duplicate_result.potential_duplicates, parse_result.entries
                    )
                    if message_id > 0:
                        # Store the duplicate data for later processing
                        await self._store_duplicate_data(chat_id, duplicate_result, parse_result, user_id, user_name)
                        return True, "duplicate_detection_sent"  # Special return value to indicate duplicate detection was sent

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
            # Use smart converter for category detection
            conversion_result = smart_unit_converter.convert_item_specification(entry.item_name, parse_result.header.category)
            detected_category = conversion_result.mapped_category
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
                    new_total = previous_quantity + entry.quantity
                    return {
                        "success": True,
                        "created": False,
                        "item_name": entry.item_name,
                        "quantity": entry.quantity,
                        "previous_quantity": previous_quantity,
                        "new_total": new_total,
                        "message": f"Added {entry.quantity} to {entry.item_name} stock (was {previous_quantity}, now {new_total})"
                    }
                else:
                    return {
                        "success": False,
                        "created": False,
                        "item_name": entry.item_name,
                        "quantity": entry.quantity,
                        "previous_quantity": previous_quantity,
                        "message": f"Failed to add {entry.quantity} to {entry.item_name} stock"
                    }
            else:
                # Create new item with enhanced defaults
                try:
                    # Extract unit size and type from item name if specified (e.g., "Paint 20ltrs")
                    unit_size, unit_type = self._extract_unit_info_from_name(entry.item_name)
                    
                    # Use smart converter for both unit and category detection
                    conversion_result = smart_unit_converter.convert_item_specification(entry.item_name, category_override)
                    
                    # Use category override if provided, otherwise use smart detection
                    detected_category = conversion_result.mapped_category
                    
                    logger.info(f"Creating item {entry.item_name} with category: {detected_category}, unit_size: {unit_size}, unit_type: {unit_type}")
                    
                    new_item_id = await self.airtable.create_item_if_not_exists(
                        item_name=entry.item_name,
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

    async def _update_item_stock(self, item_name: str, quantity_to_add: float, existing_item: Optional[Item] = None,
                                normalized_date: str = "", user_name: str = "") -> bool:
        """Add quantity to existing item stock (cumulative updates)."""
        try:
            # Use existing item if provided, otherwise get it
            if existing_item is None:
                item = await self.airtable.get_item(item_name)
                if not item:
                    return False
            else:
                item = existing_item

            # Add the new quantity to existing stock (cumulative behavior)
            quantity_change = quantity_to_add

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
        summary += f"• Items updated (quantities added): {updated_items}\n"
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

        # Show cumulative updates for existing items
        if updated_items > 0:
            updated_results = [r for r in results if r.get("success") and not r.get("created")]
            if updated_results:
                summary += f"\n📈 <b>Stock Updates (Cumulative):</b>\n"
                for result in updated_results[:5]:  # Show first 5 updates
                    item_name = result.get("item_name", "Unknown")
                    quantity_added = result.get("quantity", 0)
                    previous_qty = result.get("previous_quantity", 0)
                    new_total = result.get("new_total", previous_qty + quantity_added)
                    summary += f"• {item_name}: +{quantity_added} (was {previous_qty}, now {new_total})\n"
                
                if len(updated_results) > 5:
                    summary += f"• ... and {len(updated_results) - 5} more items\n"

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
                    # Use smart converter for both unit and category info for display
                    conversion_result = smart_unit_converter.convert_item_specification(item_name)
                    unit_size, unit_type = conversion_result.detected_unit_size, conversion_result.detected_unit_type
                    detected_category = conversion_result.mapped_category
                    
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

    async def _check_for_duplicates(self, entries: List[InventoryEntry], user_name: str) -> DuplicateDetectionResult:
        """
        Check for potential duplicates in the inventory entries.
        
        Args:
            entries: List of inventory entries to check
            user_name: Name of the user performing the inventory
            
        Returns:
            DuplicateDetectionResult with duplicate information
        """
        try:
            all_duplicates = []
            new_entries = []
            
            for entry in entries:
                # Check for duplicates for this entry
                duplicates = await self.duplicate_detection_service.find_potential_duplicates(
                    entry.item_name, entry.quantity
                )
                
                if duplicates:
                    all_duplicates.extend(duplicates)
                    new_entries.append(entry)
            
            # Create result
            result = DuplicateDetectionResult(
                has_duplicates=len(all_duplicates) > 0,
                potential_duplicates=all_duplicates,
                new_entries=new_entries,
                requires_confirmation=len(all_duplicates) > 0
            )
            
            logger.info(f"Duplicate detection found {len(all_duplicates)} potential duplicates for {len(new_entries)} entries")
            return result
            
        except Exception as e:
            logger.error(f"Error checking for duplicates: {e}")
            # Return empty result on error
            return DuplicateDetectionResult(
                has_duplicates=False,
                potential_duplicates=[],
                new_entries=[],
                requires_confirmation=False
            )

    async def _store_duplicate_data(self, chat_id: int, duplicate_result: DuplicateDetectionResult, 
                                  parse_result: InventoryParseResult, user_id: int, user_name: str):
        """
        Store duplicate data for later processing when user confirms.
        
        Args:
            chat_id: Telegram chat ID
            duplicate_result: Result from duplicate detection
            parse_result: Parsed inventory command result
            user_id: User ID
            user_name: User name
        """
        try:
            # In a real implementation, this would store the data in a persistent store
            # For now, we'll use a simple in-memory store
            if not hasattr(self, '_pending_duplicates'):
                self._pending_duplicates = {}
            
            self._pending_duplicates[chat_id] = {
                'duplicate_result': duplicate_result,
                'parse_result': parse_result,
                'user_id': user_id,
                'user_name': user_name,
                'timestamp': datetime.now()
            }
            
            logger.info(f"Stored duplicate data for chat {chat_id} with {len(duplicate_result.potential_duplicates)} duplicates")
            
        except Exception as e:
            logger.error(f"Error storing duplicate data: {e}")

    async def process_duplicate_confirmation(self, chat_id: int, action: str, telegram_service=None) -> Tuple[bool, str]:
        """
        Process duplicate confirmation action.
        
        Args:
            chat_id: Telegram chat ID
            action: Action taken (confirm_duplicates, cancel_duplicates)
            telegram_service: Telegram service for sending messages
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Get stored duplicate data
            if not hasattr(self, '_pending_duplicates') or chat_id not in self._pending_duplicates:
                return False, "No pending duplicate data found for this chat."
            
            duplicate_data = self._pending_duplicates[chat_id]
            duplicate_result = duplicate_data['duplicate_result']
            parse_result = duplicate_data['parse_result']
            user_id = duplicate_data['user_id']
            user_name = duplicate_data['user_name']
            
            if action == "confirm_duplicates":
                # Process duplicates by consolidating quantities
                return await self._process_duplicate_consolidation(
                    duplicate_result, parse_result, user_id, user_name, telegram_service, chat_id
                )
            elif action == "cancel_duplicates":
                # Process normally without duplicate consolidation
                return await self._process_normal_inventory(
                    parse_result, user_id, user_name, telegram_service, chat_id
                )
            else:
                return False, f"Unknown action: {action}"
                
        except Exception as e:
            logger.error(f"Error processing duplicate confirmation: {e}")
            return False, f"Error processing duplicate confirmation: {str(e)}"

    async def _process_duplicate_consolidation(self, duplicate_result: DuplicateDetectionResult, 
                                             parse_result: InventoryParseResult, user_id: int, 
                                             user_name: str, telegram_service=None, chat_id: int = None) -> Tuple[bool, str]:
        """
        Process duplicate consolidation by updating existing items.
        
        Args:
            duplicate_result: Duplicate detection result
            parse_result: Parsed inventory command result
            user_id: User ID
            user_name: User name
            telegram_service: Telegram service for sending messages
            chat_id: Telegram chat ID
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Generate batch ID for audit trail
            batch_id = None
            if self.audit_trail_service:
                batch_id = self.audit_trail_service.generate_batch_id()

            # Process each entry with duplicate consolidation
            results = []
            updated_items = 0
            created_items = 0
            failed_items = 0
            consolidated_items = []

            for entry in parse_result.entries:
                # Check if this entry has duplicates
                entry_duplicates = [d for d in duplicate_result.potential_duplicates 
                                  if self._entries_similar(entry, d)]
                
                if entry_duplicates:
                    # Consolidate with existing items
                    result = await self._consolidate_with_duplicates(
                        entry, entry_duplicates, parse_result.header.normalized_date, 
                        user_name, parse_result.header.category
                    )
                    consolidated_items.append(entry.item_name)
                else:
                    # Process normally
                    result = await self._process_inventory_entry(
                        entry, parse_result.header.normalized_date, user_name, parse_result.header.category
                    )
                
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

            # Generate summary message
            summary = self._generate_duplicate_consolidation_summary(
                parse_result.header, updated_items, created_items, failed_items, 
                results, batch_id, parse_result, consolidated_items
            )

            # Clean up stored duplicate data
            if hasattr(self, '_pending_duplicates') and chat_id in self._pending_duplicates:
                del self._pending_duplicates[chat_id]

            return True, summary

        except Exception as e:
            logger.error(f"Error processing duplicate consolidation: {e}")
            return False, f"Error processing duplicate consolidation: {str(e)}"

    async def _process_normal_inventory(self, parse_result: InventoryParseResult, user_id: int, 
                                      user_name: str, telegram_service=None, chat_id: int = None) -> Tuple[bool, str]:
        """
        Process inventory normally without duplicate consolidation.
        
        Args:
            parse_result: Parsed inventory command result
            user_id: User ID
            user_name: User name
            telegram_service: Telegram service for sending messages
            chat_id: Telegram chat ID
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Generate batch ID for audit trail
            batch_id = None
            if self.audit_trail_service:
                batch_id = self.audit_trail_service.generate_batch_id()

            # Process each entry normally
            results = []
            updated_items = 0
            created_items = 0
            failed_items = 0

            for entry in parse_result.entries:
                result = await self._process_inventory_entry(
                    entry, parse_result.header.normalized_date, user_name, parse_result.header.category
                )
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

            # Generate summary message
            summary = self._generate_summary(
                parse_result.header, updated_items, created_items, failed_items, 
                results, batch_id, parse_result
            )

            # Clean up stored duplicate data
            if hasattr(self, '_pending_duplicates') and chat_id in self._pending_duplicates:
                del self._pending_duplicates[chat_id]

            return True, summary

        except Exception as e:
            logger.error(f"Error processing normal inventory: {e}")
            return False, f"Error processing normal inventory: {str(e)}"

    def _entries_similar(self, entry: InventoryEntry, duplicate) -> bool:
        """
        Check if an inventory entry is similar to a potential duplicate.
        
        Args:
            entry: Inventory entry
            duplicate: Potential duplicate
            
        Returns:
            True if entries are similar
        """
        try:
            # Use the duplicate detection service's similarity check
            similarity = self.duplicate_detection_service._calculate_duplicate_similarity(
                entry.item_name, duplicate.item_name
            )
            return similarity >= self.duplicate_detection_service.similarity_threshold
        except Exception as e:
            logger.error(f"Error checking entry similarity: {e}")
            return False

    async def _consolidate_with_duplicates(self, entry: InventoryEntry, duplicates: List, 
                                         normalized_date: str, user_name: str, 
                                         category_override: Optional[str] = None) -> Dict:
        """
        Consolidate an inventory entry with its duplicates.
        
        Args:
            entry: Inventory entry to consolidate
            duplicates: List of potential duplicates
            normalized_date: Normalized date string
            user_name: User name
            category_override: Optional category override
            
        Returns:
            Dictionary with consolidation result
        """
        try:
            # Find the best matching duplicate (highest similarity score)
            best_duplicate = max(duplicates, key=lambda d: d.similarity_score)
            
            # Get the existing item
            existing_item = await self.airtable.get_item(best_duplicate.item_name)
            if not existing_item:
                # Fall back to normal processing if item not found
                return await self._process_inventory_entry(
                    entry, normalized_date, user_name, category_override
                )
            
            # Store previous quantity for audit trail
            previous_quantity = existing_item.on_hand
            
            # Add the new quantity to existing stock
            success = await self._update_item_stock(
                best_duplicate.item_name, entry.quantity, existing_item, normalized_date, user_name
            )
            
            if success:
                new_total = previous_quantity + entry.quantity
                return {
                    "success": True,
                    "created": False,
                    "item_name": best_duplicate.item_name,
                    "quantity": entry.quantity,
                    "previous_quantity": previous_quantity,
                    "new_total": new_total,
                    "message": f"Consolidated {entry.item_name} with {best_duplicate.item_name}: +{entry.quantity} (was {previous_quantity}, now {new_total})"
                }
            else:
                return {
                    "success": False,
                    "created": False,
                    "item_name": best_duplicate.item_name,
                    "quantity": entry.quantity,
                    "previous_quantity": previous_quantity,
                    "message": f"Failed to consolidate {entry.item_name} with {best_duplicate.item_name}"
                }
                
        except Exception as e:
            logger.error(f"Error consolidating with duplicates: {e}")
            return {
                "success": False,
                "created": False,
                "item_name": entry.item_name,
                "quantity": entry.quantity,
                "previous_quantity": 0.0,
                "message": f"Error consolidating: {str(e)}"
            }

    def _generate_duplicate_consolidation_summary(self, header: InventoryHeader, updated_items: int, 
                                                created_items: int, failed_items: int, results: List[Dict], 
                                                batch_id: Optional[str], parse_result: InventoryParseResult,
                                                consolidated_items: List[str]) -> str:
        """
        Generate summary message for duplicate consolidation processing.
        
        Args:
            header: Inventory header
            updated_items: Number of updated items
            created_items: Number of created items
            failed_items: Number of failed items
            results: List of processing results
            batch_id: Batch ID for audit trail
            parse_result: Parsed inventory command result
            consolidated_items: List of consolidated item names
            
        Returns:
            Formatted summary message
        """
        summary = f"✅ <b>Inventory Processing Complete (Duplicate Consolidation)</b>\n\n"
        summary += f"<b>Date:</b> {header.date} (normalized to {header.normalized_date})\n"
        summary += f"<b>Logged by:</b> {', '.join(header.logged_by)}\n"
        if header.category:
            summary += f"<b>Category Override:</b> {header.category}\n"
        
        summary += f"\n📊 <b>Processing Results:</b>\n"
        summary += f"• Updated Items: {updated_items}\n"
        summary += f"• Created Items: {created_items}\n"
        summary += f"• Failed Items: {failed_items}\n"
        summary += f"• Consolidated Items: {len(consolidated_items)}\n"
        
        if consolidated_items:
            summary += f"\n🔄 <b>Consolidated Items:</b>\n"
            for item in consolidated_items[:5]:  # Show first 5
                summary += f"• {item}\n"
            if len(consolidated_items) > 5:
                summary += f"• ... and {len(consolidated_items) - 5} more\n"
        
        # Add statistics about ignored lines if available
        if parse_result and (parse_result.blank_lines > 0 or parse_result.comment_lines > 0):
            summary += f"\n📊 <b>Lines Processed:</b>\n"
            if parse_result.blank_lines > 0:
                summary += f"• {parse_result.blank_lines} blank lines ignored\n"
            if parse_result.comment_lines > 0:
                summary += f"• {parse_result.comment_lines} comment lines ignored\n"
            if parse_result.skipped_lines > 0:
                summary += f"• {parse_result.skipped_lines} invalid lines skipped\n"

        # Show consolidation updates
        if updated_items > 0:
            updated_results = [r for r in results if r.get("success") and not r.get("created")]
            if updated_results:
                summary += f"\n📈 <b>Consolidation Updates:</b>\n"
                for result in updated_results[:5]:  # Show first 5 updates
                    item_name = result.get("item_name", "Unknown")
                    quantity_added = result.get("quantity", 0)
                    previous_qty = result.get("previous_quantity", 0)
                    new_total = result.get("new_total", previous_qty + quantity_added)
                    summary += f"• {item_name}: +{quantity_added} (was {previous_qty}, now {new_total})\n"
                
                if len(updated_results) > 5:
                    summary += f"• ... and {len(updated_results) - 5} more items\n"

        if failed_items > 0:
            summary += f"\n❌ <b>Failed Items:</b>\n"
            for result in results:
                if not result["success"]:
                    summary += f"• {result['item_name']}: {result['message']}\n"
        
        if batch_id and self.audit_trail_service:
            summary += f"\n📋 <b>Audit Trail:</b> Created for all successful entries (Batch: {batch_id})"

        return summary
