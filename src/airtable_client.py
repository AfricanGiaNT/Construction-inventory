"""Airtable client for the Construction Inventory Bot."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from pyairtable import Api, Base, Table
from pyairtable.formulas import match

# Settings will be passed in constructor
from .schemas import Item, StockMovement, TelegramUser, UserRole

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
                large_qty_threshold=record["fields"].get("Large Qty Threshold")
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
                        large_qty_threshold=fields.get("Large Qty Threshold")
                    ))
            
            return results[:10]  # Limit results
        except Exception as e:
            logger.error(f"Error searching items: {e}")
            return []
    
    async def test_connection(self) -> bool:
        """Test the connection to Airtable."""
        try:
            # Try to fetch a single record from the items table
            records = self.items_table.all(max_records=1)
            return True
        except Exception as e:
            logger.error(f"Airtable connection test failed: {e}")
            return False
    
    async def create_item_if_not_exists(self, item_name: str, base_unit: str = "piece", category: str = "General") -> Optional[str]:
        """Create a new item if it doesn't exist."""
        try:
            # Check if item already exists
            existing_item = await self.get_item(item_name)
            if existing_item:
                return existing_item.name  # Return existing item name as ID
            
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
            category_mapping = {
                "general": "Steel",  # Default to existing category
                "steel": "Steel",
                "electrical": "Electrical", 
                "cement": "Cement",
                "plumbing": "Steel",  # Default to existing
                "safety": "Steel",  # Default to existing
                "tools": "Steel",  # Default to existing
                "equipment": "Steel"  # Default to existing
            }
            
            # Use mapped unit or default to existing valid option
            valid_unit = unit_mapping.get(base_unit.lower(), "meter")  # Default to existing option
            
            # Use mapped category or default to existing valid option
            valid_category = category_mapping.get(category.lower(), "Steel")  # Default to existing option
            
            # Create new item
            record = {
                "Name": item_name,
                "Base Unit": valid_unit,
                "Category": valid_category,
                "On Hand": 0.0,
                "Reorder Level": 10,  # Default threshold
                "Large Qty Threshold": 100,  # Default approval threshold
                "Is Active": True
            }
            
            logger.info(f"Creating new item: {item_name} with unit: {valid_unit}")
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
                "Qty Entered": movement.quantity,  # number
                "Unit Entered": movement.unit,  # singleSelect
                "Signed Base Qty": movement.signed_base_quantity,  # number
                "Note": movement.note or "",  # multilineText
                "Status": movement.status.value.title(),  # singleSelect
                "Requested By": [person_id] if person_id else [],  # multipleRecordLinks
                "Source": "Telegram",  # singleSelect
                "Created At": movement.timestamp.strftime("%Y-%m-%d"),  # date
                "Reason": "Issue" if movement.movement_type.value == "Out" else "Purchase" if movement.movement_type.value == "In" else "Adjustment",  # singleSelect
                "Item": movement.item_name,  # singleLineText
                # Note: Item Category and Item Base Unit are lookup fields, not directly settable
                # Note: Is Posted is a formula field, not directly settable
                # Note: Posted Qty exists but may be calculated differently
            }
            
            # Add driver name if specified
            if movement.driver_name:
                record["Driver's Name"] = movement.driver_name
            
            # Add from/to location if specified
            if movement.from_location:
                record["From/To Location"] = movement.from_location
            
            # Add location if specified
            if movement.location:
                location_id = await self._get_location_id_by_name(movement.location)
                if location_id:
                    record["Location"] = [location_id]
            
            # Add project if specified - using the correct field name "From/To Project"
            if movement.project:
                record["From/To Project"] = movement.project
            
            # Add Telegram Users link (should link to Telegram User record, not Person)
            telegram_user_id = await self._get_telegram_user_record_id(movement.user_id)
            if telegram_user_id:
                record["Telegram Users"] = [telegram_user_id]
            
            # Handle item reference and auto-creation
            item = await self.get_item(movement.item_name)
            if not item:
                # Create new item if it doesn't exist
                logger.info(f"Creating new item: {movement.item_name}")
                item_id = await self.create_item_if_not_exists(
                    movement.item_name, 
                    movement.unit, 
                    "General"  # Default category
                )
                if item_id:
                    logger.info(f"Item created successfully: {movement.item_name}")
                else:
                    logger.error(f"Failed to create item: {movement.item_name}")
                    return None
            else:
                logger.info(f"Using existing item: {movement.item_name}")
            
            # Create the movement record
            created = self.movements_table.create(record)
            
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
                    "quantity": record["fields"].get("Qty Entered"),
                    "unit": record["fields"].get("Unit Entered"),
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
                    quantity = record["fields"].get("Signed Base Qty", 0.0)
                    
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
