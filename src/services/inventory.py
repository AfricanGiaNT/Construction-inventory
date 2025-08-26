"""Inventory stocktake service for the Construction Inventory Bot."""

import logging
import re
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from ..schemas import Item

logger = logging.getLogger(__name__)


@dataclass
class InventoryHeader:
    """Parsed inventory header information."""
    date: str  # DD/MM/YY format
    logged_by: List[str]  # List of names
    raw_text: str
    normalized_date: str  # ISO YYYY-MM-DD format


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
        """Parse the header line for date and logged by information."""
        # Pattern: date:DD/MM/YY logged by: NAME1,NAME2 or date:DD/MM/YY logged_by: NAME1,NAME2
        # Allow flexible whitespace and variations
        pattern = r'date:\s*(\d{1,2}/\d{1,2}/\d{2})\s+(?:logged\s+by|logged_by):\s*(.+)'
        match = re.match(pattern, header_line, re.IGNORECASE)

        if not match:
            return None

        date_str = match.group(1)
        logged_by_text = match.group(2).strip()

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

        # Validate and parse quantity
        try:
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
                error_message += "/inventory date:DD/MM/YY logged by: NAME1,NAME2\n"
                error_message += "Item Name, Quantity\n"
                error_message += "Item Name, Quantity\n"
                error_message += "\n💡 <b>Tips:</b>\n"
                error_message += "• Use 'logged by:' or 'logged_by:' (both work)\n"
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
                result = await self._process_inventory_entry(entry, parse_result.header.normalized_date, user_name)
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
            report += f"• {entry.item_name}: {entry.quantity}\n"
        
        report += f"\n💡 <b>Ready to apply!</b> Use the same command without 'validate' to process."
        
        return report

    async def _process_inventory_entry(self, entry: InventoryEntry, normalized_date: str, user_name: str) -> Dict:
        """Process a single inventory entry."""
        try:
            # Check if item exists
            existing_item = await self.airtable.get_item(entry.item_name)

            if existing_item:
                # Store previous quantity for audit trail
                previous_quantity = existing_item.on_hand
                
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
                # Create new item with defaults
                try:
                    new_item_id = await self.airtable.create_item_if_not_exists(
                        item_name=entry.item_name,
                        base_unit="piece",  # Default as specified in plan
                        category="General"  # Default as specified in plan
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
                                "message": f"Created {entry.item_name} with stock level {entry.quantity}"
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
            summary += f"• {created_items} items created with default Base Unit='piece' and Category='General'\n"
            summary += f"• These can be updated later with proper categorization\n"
        
        if batch_id and self.audit_trail_service:
            summary += f"\n📋 <b>Audit Trail:</b> Created for all successful entries (Batch: {batch_id})"

        return summary
