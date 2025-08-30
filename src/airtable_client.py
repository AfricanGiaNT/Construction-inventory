"""Airtable client for the Construction Inventory Bot."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from pyairtable import Api, Base, Table
from pyairtable.formulas import match

# Settings will be passed in constructor
from schemas import Item, StockMovement, TelegramUser, UserRole

logger = logging.getLogger(__name__)


class AirtableClient:
    """Client for interacting with Airtable."""
    
    def __init__(self, settings):
        """Initialize the Airtable client."""
        self.api = Api(settings.airtable_api_key)
        self.base = self.api.base(settings.airtable_base_id)
        
        # Table references
        self.items_table = self.base.table("Items")
        self.movements_table = self.base.table("Stock Movements")
        self.users_table = self.base.table("Telegram Users")
        self.units_table = self.base.table("Item Units")
        self.locations_table = self.base.table("Locations")
        self.people_table = self.base.table("People")
        self.bot_meta_table = self.base.table("Bot Meta")
        self.stocktakes_table = self.base.table("Stocktakes")
    
    async def get_item(self, item_name: str) -> Optional[Item]:
        """Get an item by name."""
        try:
            formula = match({"Name": item_name})
            records = self.items_table.all(formula=formula)
            
            if not records:
                return None
            
            record = records[0]
            return Item(
                name=record["fields"].get("Name", ""),
                sku=record["fields"].get("Name", ""),  # Use name as SKU for now
                description=None,  # Aliases field removed
                base_unit=record["fields"].get("Base Unit", ""),
                units=[],  # Simplified - no Item Units table
                on_hand=record["fields"].get("On Hand", 0.0),
                threshold=record["fields"].get("Reorder Level"),  # Using Reorder Level as threshold
                location=record["fields"].get("Preferred Location", [None])[0] if record["fields"].get("Preferred Location") else None,
                category=record["fields"].get("Category", ""),
                large_qty_threshold=record["fields"].get("Large Qty Threshold"),
                is_active=record["fields"].get("Is Active", True),
                last_stocktake_date=record["fields"].get("Last Stocktake Date"),
                last_stocktake_by=record["fields"].get("Last Stocktake By"),
                # New fields for enhanced item structure
                unit_size=record["fields"].get("Unit Size", 1.0),
                unit_type=record["fields"].get("Unit Type", "piece")
            )
        except Exception as e:
            logger.error(f"Error getting item {item_name}: {e}")
            return None
    
    async def search_items(self, query: str) -> List[Item]:
        """Search items by name."""
        try:
            # Simple search by name only
            all_items = self.items_table.all()
            results = []
            
            query_lower = query.lower()
            for record in all_items:
                fields = record["fields"]
                name = fields.get("Name", "").lower()
                
                if query_lower in name:
                    results.append(Item(
                        name=fields.get("Name", ""),
                        sku=fields.get("Name", ""),  # Use name as SKU
                        description=None,  # Aliases field removed
                        base_unit=fields.get("Base Unit", ""),
                        units=[],
                        on_hand=fields.get("On Hand", 0.0),
                        threshold=fields.get("Reorder Level"),
                        location=fields.get("Preferred Location", [None])[0] if fields.get("Preferred Location") else None,
                        category=fields.get("Category", ""),
                        large_qty_threshold=fields.get("Large Qty Threshold"),
                        # New fields for enhanced item structure
                        unit_size=fields.get("Unit Size", 1.0),
                        unit_type=fields.get("Unit Type", "piece")
                    ))
            
            return results[:10]  # Limit results
        except Exception as e:
            logger.error(f"Error searching items: {e}")
            return []
    
    async def get_all_items(self) -> List[Item]:
        """Get all items from the database for fuzzy search."""
        try:
            all_records = self.items_table.all()
            items = []
            
            for record in all_records:
                fields = record["fields"]
                item = Item(
                    name=fields.get("Name", ""),
                    sku=fields.get("Name", ""),  # Use name as SKU
                    description=None,  # Aliases field removed
                    base_unit=fields.get("Base Unit", ""),
                    units=[],
                    on_hand=fields.get("On Hand", 0.0),
                    threshold=fields.get("Reorder Level"),
                    location=fields.get("Preferred Location", [None])[0] if fields.get("Preferred Location") else None,
                    category=fields.get("Category", ""),
                    large_qty_threshold=fields.get("Large Qty Threshold"),
                    # New fields for enhanced item structure
                    unit_size=fields.get("Unit Size", 1.0),
                    unit_type=fields.get("Unit Type", "piece")
                )
                items.append(item)
            
            logger.info(f"Retrieved {len(items)} items from database")
            return items
            
        except Exception as e:
            logger.error(f"Error getting all items: {e}")
            return []
    
    def _extract_unit_info_from_name(self, item_name: str) -> tuple[float, str]:
        """
        Extract unit size and type from item name if specified.
        
        Examples:
        - "Paint 20ltrs" -> (20.0, "ltrs")
        - "Cement 50kg" -> (50.0, "kg")
        - "Steel Beam" -> (1.0, "piece")
        
        Returns:
            Tuple of (unit_size, unit_type)
        """
        try:
            # Pattern to match: ItemName NumberUnit (e.g., "Paint 20ltrs", "Cement 50kg")
            import re
            pattern = r'(.+?)\s+(\d+(?:\.\d+)?)([a-zA-Z]+)$'
            match = re.match(pattern, item_name.strip())
            
            if match:
                base_name = match.group(1).strip()
                unit_size = float(match.group(2))
                unit_type = match.group(3).lower()
                
                # Validate unit_size
                if unit_size <= 0:
                    logger.warning(f"Invalid unit_size {unit_size} extracted from {item_name}, defaulting to 1.0")
                    return 1.0, "piece"
                
                # Map common unit types to standardized values
                unit_type_mapping = {
                    "ltrs": "ltrs",
                    "litres": "ltrs",
                    "ltr": "ltrs",
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
                
                # Special handling for thickness specifications (mm, cm, etc.)
                thickness_patterns = ["mm", "cm", "inch", "inches"]
                if unit_type in thickness_patterns:
                    logger.info(f"'{unit_type}' detected as thickness specification for '{item_name}', using unit 'piece'")
                    return 1.0, "piece"
                
                standardized_unit_type = unit_type_mapping.get(unit_type, unit_type)
                
                logger.info(f"Extracted unit info from '{item_name}': size={unit_size}, type={standardized_unit_type}")
                return unit_size, standardized_unit_type
            
            # No unit info found, return defaults
            return 1.0, "piece"
            
        except Exception as e:
            logger.warning(f"Error extracting unit info from '{item_name}': {e}, using defaults")
            return 1.0, "piece"

    async def test_connection(self) -> bool:
        """Test the connection to Airtable."""
        try:
            # Try to fetch a single record from the items table
            records = self.items_table.all(max_records=1)
            return True
        except Exception as e:
            logger.error(f"Airtable connection test failed: {e}")
            return False
    
    async def create_item_if_not_exists(self, item_name: str, base_unit: str = "piece", category: str = "General", 
                                      unit_size: float = 1.0, unit_type: str = "piece") -> Optional[str]:
        """Create a new item if it doesn't exist."""
        try:
            # Check if item already exists
            existing_item = await self.get_item(item_name)
            if existing_item:
                return existing_item.name  # Return existing item name as ID
            
            # Validate unit_size
            if unit_size <= 0:
                logger.warning(f"Invalid unit_size {unit_size} for {item_name}, defaulting to 1.0")
                unit_size = 1.0
            
            # Validate unit_type
            if not unit_type or unit_type.strip() == "":
                logger.warning(f"Empty unit_type for {item_name}, defaulting to 'piece'")
                unit_type = "piece"
            
            # Handle thickness specifications (mm, cm, etc.) - these should use 'piece' unit
            thickness_patterns = ["mm", "cm", "inch", "inches"]
            if unit_type in thickness_patterns:
                logger.info(f"'{unit_type}' detected as thickness specification for '{item_name}', using unit 'piece'")
                unit_type = "piece"
            
            # Map common units to valid Airtable options (based on existing data)
            unit_mapping = {
                "piece": "piece",
                "pieces": "piece", 
                "bag": "bag",
                "bags": "bag",
                "meter": "meter",
                "meters": "meter",
                "kg": "kg",
                "ton": "ton",
                "litre": "litre",
                "litres": "litre"
            }
            
            # Map common categories to valid Airtable options (based on existing data)
            # Use only categories that are confirmed to exist in Airtable
            # Note: Airtable categories are case-sensitive, so we map to exact values
            category_mapping = {
                "general": "General",  # Default to General category
                "steel": "Steel",
                "electrical": "Electrical", 
                "paint": "Paint",  # Map paint to existing Paint category
                "white": "Paint",  # Map white to Paint category
                "bitumec": "Paint",  # Map bitumec to Paint category
                "litres": "Paint",  # Map litres to Paint category
                "wire": "Electrical",  # Map wire to Electrical category
                "cable": "Electrical",  # Map cable to Electrical category
                "beam": "Steel",  # Map beam to Steel category
                "plate": "Steel",  # Map plate to Steel category
                "angle": "Steel",  # Map angle to Steel category
                "cement": "General",  # Map cement to General (since Cement doesn't exist)
                "concrete": "General",  # Map concrete to General
                "plumbing": "General",  # Map plumbing to General
                "safety": "General",  # Map safety to General
                "tools": "General",  # Map tools to General
                "equipment": "General"  # Map equipment to General
            }
            
            # Use mapped unit or default to existing valid option
            valid_unit = unit_mapping.get(base_unit.lower(), "meter")  # Default to existing option
            
            # Use mapped category or try to auto-detect from item name
            # This ensures we only use categories that exist in Airtable
            valid_category = None
            
            if category:
                # Handle case-insensitive matching for common categories
                category_lower = category.lower()
                valid_category = category_mapping.get(category_lower, None)
            
            # If no category mapping found, try to auto-detect from item name
            if not valid_category:
                item_lower = item_name.lower()
                if any(paint_word in item_lower for paint_word in ['paint', 'white', 'bitumec', 'ltrs', 'litres']):
                    valid_category = "Paint"
                elif any(electrical_word in item_lower for electrical_word in ['wire', 'cable', 'electrical', 'electric']):
                    valid_category = "Electrical"
                elif any(steel_word in item_lower for steel_word in ['steel', 'beam', 'plate', 'angle']):
                    valid_category = "Steel"
                else:
                    valid_category = "General"  # Default to General for everything else
            
            # Log the mapping for debugging
            if category:
                logger.info(f"Category mapping: '{category}' (lowercase: '{category.lower()}') → '{valid_category}'")
            else:
                logger.info(f"Auto-detected category from item name '{item_name}' → '{valid_category}'")
            
            # Create new item with enhanced fields
            record = {
                "Name": item_name,
                "Base Unit": valid_unit,
                "Unit Size": unit_size,
                "Unit Type": unit_type,
                "Category": valid_category,
                "On Hand": 0.0,
                "Reorder Level": 10,  # Default threshold
                "Large Qty Threshold": 100,  # Default approval threshold
                "Is Active": True
            }
            
            logger.info(f"Creating new item: {item_name} with unit: {valid_unit}, unit_size: {unit_size}, unit_type: {unit_type}")
            created = self.items_table.create(record)
            logger.info(f"Created new item: {item_name}")
            return created["id"]
            
        except Exception as e:
            logger.error(f"Error creating item {item_name}: {e}")
            return None
    
    async def update_item_stock(self, item_name: str, quantity_change: float) -> bool:
        """Update item stock quantity."""
        try:
            item = await self.get_item(item_name)
            if not item:
                logger.warning(f"Item {item_name} not found for stock update")
                return False
            
            # Calculate new quantity
            new_quantity = item.on_hand + quantity_change
            
            # Get the actual record ID from Airtable
            item_record_id = await self._get_item_id_by_name(item_name)
            if not item_record_id:
                logger.error(f"Could not find record ID for item: {item_name}")
                return False
            
            # Update using the record ID, not the name
            self.items_table.update(item_record_id, {"On Hand": new_quantity})
            logger.info(f"Updated {item_name} stock: {item.on_hand} → {new_quantity}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating stock for {item_name}: {e}")
            return False
    
    async def create_movement(self, movement: StockMovement) -> Optional[str]:
        """Create a new stock movement."""
        try:
            # Get the person record for the user
            person_id = await self._get_person_id_by_telegram_user(movement.user_id)
            
            record = {
                "Name": movement.item_name,  # singleLineText - Primary field for Stock Movements
                "Type": movement.movement_type.value.title(),  # singleSelect
                "Quantity": movement.quantity,  # number - CORRECT field name
                "Unit": movement.unit,  # singleSelect - CORRECT field name
                "Status": movement.status.value.title(),  # singleSelect
                "Requested By": [person_id] if person_id else [],  # multipleRecordLinks
                "Source": "Telegram",  # singleSelect
                "Created At": movement.timestamp.strftime("%Y-%m-%d"),  # date
                "Reason": "Issue" if movement.movement_type.value == "Out" else "Purchase" if movement.movement_type.value == "In" else "Adjustment",  # singleSelect
                # Note: Item Category and Item Base Unit are lookup fields, not directly settable
                # Note: Is Posted is a formula field, not directly settable
                # Note: Posted Qty exists but may be calculated differently
            }
            
            # Add category field if available
            if hasattr(movement, 'category') and movement.category:
                # Clean up hierarchical categories (e.g., "Steel > Beams" -> "Steel")
                clean_category = movement.category.split(' > ')[0] if ' > ' in movement.category else movement.category
                logger.info(f"Adding category '{clean_category}' to movement record for {movement.item_name} (original: {movement.category})")
                record["Category"] = clean_category
            else:
                logger.warning(f"Category field missing or empty for movement {movement.item_name}: hasattr={hasattr(movement, 'category')}, category={getattr(movement, 'category', 'NOT_SET')}")
            
            # Add driver name if specified
            if movement.driver_name:
                record["Driver Name"] = movement.driver_name
            
            # Note: Location and Project fields are not available in current Airtable schema
            # These fields were removed to match the actual table structure
            
            # Add Telegram Users link (should link to Telegram User record, not Person)
            telegram_user_id = await self._get_telegram_user_record_id(movement.user_id)
            if telegram_user_id:
                record["Telegram Users"] = [telegram_user_id]
            
            # Handle item reference and auto-creation
            item = await self.get_item(movement.item_name)
            if not item:
                # Create new item if it doesn't exist
                logger.info(f"Creating new item: {movement.item_name}")
                # Extract unit size and type from item name if specified
                unit_size, unit_type = self._extract_unit_info_from_name(movement.item_name)
                
                item_id = await self.create_item_if_not_exists(
                    movement.item_name, 
                    movement.unit, 
                    None,  # Let the method auto-detect category from item name
                    unit_size,
                    unit_type
                )
                if item_id:
                    logger.info(f"Item created successfully: {movement.item_name}")
                else:
                    logger.error(f"Failed to create item: {movement.item_name}")
                    return None
            else:
                logger.info(f"Using existing item: {movement.item_name}")
            
            # Create the movement record
            logger.info(f"Creating movement record with data: {record}")
            created = self.movements_table.create(record)
            logger.info(f"Movement record created successfully: {created.get('id', 'NO_ID')}")
            
            # Automatically update item stock
            if created["id"]:
                quantity_change = movement.signed_base_quantity
                await self.update_item_stock(movement.item_name, quantity_change)
            
            return created["id"]
        except Exception as e:
            logger.error(f"Error creating movement: {e}")
            return None
    
    async def update_movement_status(self, movement_id: str, status: str, 
                                   approved_by: Optional[str] = None) -> bool:
        """Update movement status."""
        try:
            update_data = {"Status": status}
            if approved_by:
                # Get person ID for the approver
                person_id = await self._get_person_id_by_name(approved_by)
                if person_id:
                    update_data["Requested By"] = [person_id]
            
            self.movements_table.update(movement_id, update_data)
            return True
        except Exception as e:
            logger.error(f"Error updating movement status: {e}")
            return False
    
    async def get_user_role(self, user_id: int) -> UserRole:
        """Get user role from Airtable."""
        try:
            formula = match({"Telegram User ID": str(user_id)})
            records = self.users_table.all(formula=formula)
            
            if not records:
                return UserRole.VIEWER
            
            # Try to get role from the Person record first
            person_id = records[0]["fields"].get("Person", [None])[0]
            if person_id:
                try:
                    person_record = self.people_table.get(person_id)
                    role_str = person_record["fields"].get("Role", "viewer")
                    return UserRole(role_str.lower())
                except Exception:
                    # If person record access fails, continue to fallback
                    pass
            
            # Fallback: Check if user has a direct Role field (for new users)
            user_record = records[0]["fields"]
            if "Role" in user_record and user_record["Role"]:
                # If Role is a list, take the first one
                role_value = user_record["Role"][0] if isinstance(user_record["Role"], list) else user_record["Role"]
                try:
                    return UserRole(role_value.lower())
                except ValueError:
                    pass
            
            # Default to VIEWER if no role found
            return UserRole.VIEWER
            
        except Exception as e:
            logger.error(f"Error getting user role: {e}")
            return UserRole.VIEWER
    
    async def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Get all pending approval requests."""
        try:
            formula = match({"Status": "Requested"})
            records = self.movements_table.all(formula=formula)
            
            return [
                {
                    "id": record["id"],
                    "item_name": await self._get_item_name_by_id(record["fields"].get("Item", [None])[0]),
                                    "quantity": record["fields"].get("Quantity"),
                "unit": record["fields"].get("Unit"),
                    "user_name": await self._get_person_name_by_id(record["fields"].get("Requested By", [None])[0]),
                    "timestamp": record["fields"].get("Created At")
                }
                for record in records
            ]
        except Exception as e:
            logger.error(f"Error getting pending approvals: {e}")
            return []
    
    async def get_daily_movements(self, date: str) -> Dict[str, Any]:
        """Get movements for a specific date."""
        try:
            formula = match({"Created At": date})
            records = self.movements_table.all(formula=formula)
            
            total_in = 0.0
            total_out = 0.0
            movements_count = 0
            
            for record in records:
                if record["fields"].get("Status") == "Posted":
                    movements_count += 1
                    quantity = record["fields"].get("Quantity", 0.0)
                    
                    if record["fields"].get("Type") == "In":
                        total_in += quantity
                    elif record["fields"].get("Type") == "Out":
                        total_out += quantity
            
            return {
                "total_in": total_in,
                "total_out": total_out,
                "movements_count": movements_count
            }
        except Exception as e:
            logger.error(f"Error getting daily movements: {e}")
            return {"total_in": 0.0, "total_out": 0.0, "movements_count": 0}
    
    async def get_low_stock_items(self) -> List[str]:
        """Get items with stock below threshold."""
        try:
            all_items = self.items_table.all()
            low_stock = []
            
            for record in all_items:
                fields = record["fields"]
                on_hand = fields.get("On Hand", 0.0)
                threshold = fields.get("Reorder Level")
                
                if threshold and on_hand <= threshold:
                    low_stock.append(fields.get("SKU", ""))
            
            return low_stock
        except Exception as e:
            logger.error(f"Error getting low stock items: {e}")
            return []
    
    async def export_onhand_csv(self) -> str:
        """Export current on-hand inventory to CSV format."""
        try:
            all_items = self.items_table.all()
            csv_lines = ["SKU,Name,On Hand,Base Unit,Location,Reorder Level"]
            
            for record in all_items:
                fields = record["fields"]
                location = fields.get("Preferred Location", [None])[0]
                location_name = await self._get_location_name_by_id(location) if location else "N/A"
                
                csv_lines.append(
                    f"{fields.get('Name', '')},"
                    f"{fields.get('On Hand', 0.0)},"
                    f"{fields.get('Base Unit', '')},"
                    f"{location_name},"
                    f"{fields.get('Reorder Level', '')}"
                )
            
            return "\n".join(csv_lines)
        except Exception as e:
            logger.error(f"Error exporting CSV: {e}")
            return "Name,On Hand,Base Unit,Location,Reorder Level"
    
    # Helper methods for ID lookups
    async def _get_person_id_by_telegram_user(self, telegram_user_id: int) -> Optional[str]:
        """Get person ID by Telegram user ID."""
        try:
            formula = match({"Telegram User ID": str(telegram_user_id)})
            records = self.users_table.all(formula=formula)
            if records:
                return records[0]["fields"].get("Person", [None])[0]
            return None
        except Exception as e:
            logger.error(f"Error getting person ID: {e}")
            return None
    
    async def _get_person_id_by_name(self, name: str) -> Optional[str]:
        """Get person ID by name."""
        try:
            formula = match({"Name": name})
            records = self.people_table.all(formula=formula)
            if records:
                return records[0]["id"]
            return None
        except Exception as e:
            logger.error(f"Error getting person ID by name: {e}")
            return None
    
    async def _get_person_name_by_id(self, person_id: str) -> str:
        """Get person name by ID."""
        try:
            if not person_id:
                return "Unknown"
            record = self.people_table.get(person_id)
            return record["fields"].get("Name", "Unknown")
        except Exception as e:
            logger.error(f"Error getting person name: {e}")
            return "Unknown"
    
    async def _get_item_id_by_name(self, item_name: str) -> Optional[str]:
        """Get item ID by name."""
        try:
            formula = match({"Name": item_name})
            records = self.items_table.all(formula=formula)
            if records:
                return records[0]["id"]
            return None
        except Exception as e:
            logger.error(f"Error getting item ID: {e}")
            return None
    
    async def _get_item_name_by_id(self, item_id: str) -> str:
        """Get item name by ID."""
        try:
            if not item_id:
                return "Unknown"
            record = self.items_table.get(item_id)
            return record["fields"].get("Name", "Unknown")
        except Exception as e:
            logger.error(f"Error getting item name: {e}")
            return "Unknown"
    
    async def _get_location_id_by_name(self, location_name: str) -> Optional[str]:
        """Get location ID by name."""
        try:
            formula = match({"Name": location_name})
            records = self.locations_table.all(formula=formula)
            if records:
                return records[0]["id"]
            return None
        except Exception as e:
            logger.error(f"Error getting location ID: {e}")
            return None
    
    async def _get_location_name_by_id(self, location_id: str) -> str:
        """Get location name by ID."""
        try:
            if not location_id:
                return "N/A"
            record = self.locations_table.get(location_id)
            return record["fields"].get("Name", "N/A")
        except Exception as e:
            logger.error(f"Error getting location name: {e}")
            return "N/A"
    
    async def _get_telegram_user_record_id(self, telegram_user_id: int) -> Optional[str]:
        """Get Telegram User record ID by Telegram user ID."""
        try:
            formula = match({"Telegram User ID": str(telegram_user_id)})
            records = self.users_table.all(formula=formula)
            if records:
                return records[0]["id"]
            return None
        except Exception as e:
            logger.error(f"Error getting Telegram User record ID: {e}")
            return None

    async def create_user_if_not_exists(self, telegram_user_id: int, username: str, first_name: str, 
                                      last_name: str = None, chat_id: int = None) -> bool:
        """Create a new user in both People and Telegram Users tables if they don't exist."""
        try:
            logger.info(f"Checking if user {telegram_user_id} exists...")
            # Check if user already exists
            existing_user = await self.get_user_role(telegram_user_id)
            logger.info(f"Existing user role: {existing_user}")
            if existing_user != UserRole.VIEWER:  # If we got a real role, user exists
                logger.info(f"User {telegram_user_id} already exists with role {existing_user}")
                return True
            
            logger.info(f"Creating new user: {telegram_user_id} ({first_name})")
            
            # First, create a Person record
            person_record = {
                "Name": first_name,  # Use the full name that was already combined
                "Role": "Staff",  # Default role for new users (singleSelect)
                "Phone": "",  # Phone field exists (singleLineText)
                "Notes": f"Auto-created user from Telegram (ID: {telegram_user_id})"  # multilineText
                # Note: Is Active field doesn't exist in People table
            }
            
            logger.info(f"Creating Person record with data: {person_record}")
            created_person = self.people_table.create(person_record)
            person_id = created_person["id"]
            logger.info(f"Created Person record: {person_id}")
            
            # Now create the Telegram User record
            user_record = {
                "Telegram User ID": str(telegram_user_id),
                "Handle": f"@{username}" if username else "",
                "Allowed Chats": str(chat_id) if chat_id else "",
                "Is Active": True,
                "Person": [person_id]  # Link to the person record
                # Note: Role field is computed from Person record, so we don't set it here
            }
            
            logger.info(f"Creating Telegram User record with data: {user_record}")
            created_user = self.users_table.create(user_record)
            logger.info(f"Created Telegram User record: {created_user['id']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating user {telegram_user_id}: {e}")
            return False

    async def get_item_movements(self, item_name: str, limit: int = 50) -> List[StockMovement]:
        """
        Get movement history for a specific item.
        
        Args:
            item_name: Name of the item
            limit: Maximum number of movements to return
            
        Returns:
            List of stock movements for the item
        """
        try:
            # Get the item first to ensure it exists
            item = await self.get_item(item_name)
            if not item:
                logger.warning(f"Item '{item_name}' not found for movement history")
                return []
            
            # Get movements from the Stock Movements table
            formula = match({"Item Name": item_name})
            records = self.movements_table.all(formula=formula, max_records=limit)
            
            movements = []
            for record in records:
                fields = record["fields"]
                
                # Parse movement type
                movement_type_str = fields.get("Movement Type", "IN")
                try:
                    movement_type = MovementType(movement_type_str)
                except ValueError:
                    movement_type = MovementType.IN
                
                # Create StockMovement object
                movement = StockMovement(
                    item_name=fields.get("Item Name", item_name),
                    movement_type=movement_type,
                    quantity=fields.get("Quantity", 0.0),
                    unit=fields.get("Unit", item.base_unit),
                    signed_base_quantity=fields.get("Signed Base Quantity", 0.0),
                    user_id=fields.get("User ID", ""),
                    user_name=fields.get("User Name", "Unknown"),
                    location=fields.get("Location", item.location),
                    project=fields.get("Project", ""),
                    note=fields.get("Note", ""),
                    timestamp=datetime.fromisoformat(fields.get("Timestamp", datetime.now().isoformat())),
                    status=fields.get("Status", "Completed")
                )
                movements.append(movement)
            
            # Sort by timestamp (most recent first)
            movements.sort(key=lambda x: x.timestamp, reverse=True)
            
            logger.info(f"Retrieved {len(movements)} movements for item '{item_name}'")
            return movements
            
        except Exception as e:
            logger.error(f"Error getting movements for item '{item_name}': {e}")
            return []
    
    async def get_pending_approvals_for_item(self, item_name: str) -> List[dict]:
        """
        Get pending batch approvals that contain the specified item.
        
        Args:
            item_name: Name of the item to check
            
        Returns:
            List of pending batch approvals containing the item
        """
        try:
            # This method will need to be implemented based on how batch approvals are stored
            # For now, we'll return an empty list as this is a TODO in the plan
            logger.info(f"Getting pending approvals for item '{item_name}' (not yet implemented)")
            return []
            
        except Exception as e:
            logger.error(f"Error getting pending approvals for item '{item_name}': {e}")
            return []
    
    async def get_item_last_updated(self, item_name: str) -> Optional[datetime]:
        """
        Get the last time an item was updated (based on most recent movement).
        
        Args:
            item_name: Name of the item
            
        Returns:
            Last update timestamp or None if no movements found
        """
        try:
            movements = await self.get_item_movements(item_name, limit=1)
            if movements:
                return movements[0].timestamp
            return None
            
        except Exception as e:
            logger.error(f"Error getting last updated time for item '{item_name}': {e}")
            return None

    # Bot Meta table methods for idempotency
    async def store_idempotency_key(self, key: str) -> bool:
        """Store an idempotency key in the Bot Meta table."""
        try:
            record = {
                "Key": key,
                "Created At": datetime.now().isoformat()
            }
            created = self.bot_meta_table.create(record)
            return bool(created.get("id"))
        except Exception as e:
            logger.error(f"Error storing idempotency key: {e}")
            return False

    async def check_idempotency_key(self, key: str) -> bool:
        """Check if an idempotency key exists in the Bot Meta table."""
        try:
            formula = match({"Key": key})
            records = self.bot_meta_table.all(formula=formula, max_records=1)
            return len(records) > 0
        except Exception as e:
            logger.error(f"Error checking idempotency key: {e}")
            return False

    # Stocktakes table methods for audit trail
    async def create_stocktake_record(self, 
                                    batch_id: str,
                                    date: str,
                                    logged_by: str,
                                    item_name: str,
                                    counted_qty: float,
                                    previous_on_hand: float,
                                    new_on_hand: float,
                                    applied_at: datetime,
                                    applied_by: str,
                                    notes: Optional[str] = None,
                                    discrepancy: Optional[float] = None) -> Optional[str]:
        """Create a stocktake record in the Stocktakes table."""
        try:
            # Get the item record ID for linking
            item = await self.get_item(item_name)
            item_record_id = None
            if item:
                # We need to get the actual record ID from Airtable
                formula = match({"Name": item_name})
                records = self.items_table.all(formula=formula, max_records=1)
                if records:
                    item_record_id = records[0]["id"]

            record = {
                "Batch Id": batch_id,
                "Date": date,
                "Logged By": logged_by,
                "Item Name": item_name,
                "Counted Qty": counted_qty,
                "Previous On Hand": previous_on_hand,
                "New On Hand": new_on_hand,
                "Applied At": applied_at.strftime("%Y-%m-%d"),
                "Applied By": applied_by
            }

            # Add optional fields if provided
            if item_record_id:
                record["Item"] = [item_record_id]
            if notes:
                record["Notes"] = notes
            if discrepancy is not None:
                record["Discrepancy"] = discrepancy

            created = self.stocktakes_table.create(record)
            return created.get("id")
        except Exception as e:
            logger.error(f"Error creating stocktake record: {e}")
            return None

    async def get_stocktake_records_by_batch(self, batch_id: str) -> List[dict]:
        """Get all stocktake records for a specific batch."""
        try:
            formula = match({"Batch Id": batch_id})
            records = self.stocktakes_table.all(formula=formula)
            return records
        except Exception as e:
            logger.error(f"Error getting stocktake records for batch {batch_id}: {e}")
            return []

    async def get_stocktake_records_by_item(self, item_name: str, limit: int = 100) -> List[dict]:
        """Get recent stocktake records for a specific item."""
        try:
            formula = match({"Item Name": item_name})
            records = self.stocktakes_table.all(formula=formula, max_records=limit)
            return records
        except Exception as e:
            logger.error(f"Error getting stocktake records for item {item_name}: {e}")
            return []

    async def get_stocktake_records_by_date_range(self, start_date: str, end_date: str, limit: int = 100) -> List[dict]:
        """Get stocktake records within a date range."""
        try:
            # Airtable date filtering - we'll get all records and filter by date
            # This could be optimized with a formula if needed
            all_records = self.stocktakes_table.all(max_records=limit)
            filtered_records = []
            
            for record in all_records:
                record_date = record["fields"].get("Date")
                if record_date and start_date <= record_date <= end_date:
                    filtered_records.append(record)
                    
            return filtered_records
        except Exception as e:
            logger.error(f"Error getting stocktake records for date range {start_date} to {end_date}: {e}")
            return []

    async def update_item_provenance(self, item_name: str, stocktake_date: str, stocktake_by: str) -> bool:
        """Update the Last Stocktake Date and Last Stocktake By fields for an item."""
        try:
            # Find the item record
            formula = match({"Name": item_name})
            records = self.items_table.all(formula=formula, max_records=1)
            
            if not records:
                logger.warning(f"Item '{item_name}' not found for provenance update")
                return False
            
            record_id = records[0]["id"]
            
            # Update the provenance fields
            update_data = {
                "Last Stocktake Date": stocktake_date,
                "Last Stocktake By": stocktake_by
            }
            
            self.items_table.update(record_id, update_data)
            logger.info(f"Updated provenance fields for item '{item_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Error updating provenance fields for item '{item_name}': {e}")
            return False
    
    async def update_item_category(self, item_name: str, new_category: str) -> bool:
        """Update the category field for an item."""
        try:
            # Find the item record
            formula = match({"Name": item_name})
            records = self.items_table.all(formula=formula, max_records=1)
            
            if not records:
                logger.warning(f"Item '{item_name}' not found for category update")
                return False
            
            record_id = records[0]["id"]
            
            # Update the category field
            update_data = {
                "Category": new_category
            }
            
            self.items_table.update(record_id, update_data)
            logger.info(f"Updated category for item '{item_name}' to '{new_category}'")
            return True
            
        except Exception as e:
            logger.error(f"Error updating category for item '{item_name}': {e}")
            return False
    
    async def update_item_base_unit(self, item_name: str, new_base_unit: str) -> bool:
        """Update the base unit field for an item."""
        try:
            # Find the item record
            formula = match({"Name": item_name})
            records = self.items_table.all(formula=formula, max_records=1)
            
            if not records:
                logger.warning(f"Item '{item_name}' not found for base unit update")
                return False
            
            record_id = records[0]["id"]
            
            # Update the base unit field
            update_data = {
                "Base Unit": new_base_unit
            }
            
            self.items_table.update(record_id, update_data)
            logger.info(f"Updated base unit for item '{item_name}' to '{new_base_unit}'")
            return True
            
        except Exception as e:
            logger.error(f"Error updating base unit for item '{item_name}': {e}")
            return False