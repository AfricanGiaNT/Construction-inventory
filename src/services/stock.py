"""Stock management service for the Construction Inventory Bot."""

import logging
from datetime import datetime, UTC
from typing import Optional, Tuple

from schemas import Item, StockMovement, MovementType, MovementStatus, UserRole
from airtable_client import AirtableClient
from services.category_parser import category_parser
# Settings will be passed in constructor

logger = logging.getLogger(__name__)


class StockService:
    """Service for managing inventory stock operations."""
    
    def __init__(self, airtable_client: AirtableClient, settings):
        """Initialize the stock service."""
        self.airtable = airtable_client
        self.settings = settings
    
    async def stock_in(self, item_name: str, quantity: float, unit: Optional[str], 
                      location: Optional[str], note: Optional[str], user_id: int, 
                      user_name: str, driver_name: Optional[str] = None, 
                      from_location: Optional[str] = None, project: Optional[str] = None) -> Tuple[bool, str, float, float]:
        """
        Process stock in operation.
        
        Returns:
            Tuple containing (success, message, before_level, after_level)
        """
        try:
            # Get item details (will auto-create if doesn't exist)
            item = await self.airtable.get_item(item_name)
            
            # Validate enhanced item structure if item exists
            if item:
                is_valid, error_msg = await self._validate_enhanced_item_structure(item)
                if not is_valid:
                    logger.warning(f"Enhanced item structure validation failed for {item_name}: {error_msg}")
                    # Continue with operation but log the warning
            
            # Store the stock level before the operation
            before_level = item.on_hand if item else 0
            
            # Determine base unit quantity
            base_quantity = await self._convert_to_base_quantity(item, quantity, unit) if item else quantity
            
            # Get category for the movement
            item_category = None
            if item and item.category:
                item_category = item.category
            else:
                # Auto-detect category if not available from item
                item_category = category_parser.parse_category(item_name)
                logger.info(f"Auto-detected category for '{item_name}': {item_category}")

            # Create movement record
            movement = StockMovement(
                item_name=item_name,
                movement_type=MovementType.IN,
                quantity=quantity,
                unit=unit or (item.unit_type if item else "piece"),
                signed_base_quantity=base_quantity,
                unit_size=item.unit_size if item else None,
                unit_type=item.unit_type if item else None,
                location=location or (item.location if item else None),
                note=note,
                status=MovementStatus.POSTED,
                user_id=str(user_id),
                user_name=user_name,
                timestamp=datetime.now(UTC),
                reason="Purchase",
                driver_name=driver_name,
                from_location=from_location,
                project=project,
                category=item_category  # Add category field
            )
            
            # Save to Airtable
            movement_id = await self.airtable.create_movement(movement)
            if not movement_id:
                return False, "Failed to save stock movement.", before_level, before_level
            
            # Calculate after level
            after_level = before_level + base_quantity
            
            # Enhanced success message with unit context and category
            if item and item.unit_size and item.unit_size > 1.0 and item.unit_type != "piece":
                total_volume = quantity * item.unit_size
                category_info = f" (Category: {item.category})" if item and item.category else ""
                success_message = f"Stock in: {quantity} units × {item.unit_size} {item.unit_type} = {total_volume} {item.unit_type} of {item_name}{category_info} recorded successfully."
            else:
                category_info = f" (Category: {item.category})" if item and item.category else ""
                success_message = f"Stock in: {quantity} {unit or (item.unit_type if item else 'piece')} of {item_name}{category_info} recorded successfully."
            
            return True, success_message, before_level, after_level
            
        except Exception as e:
            logger.error(f"Error in stock_in: {e}")
            return False, f"Error processing stock in: {str(e)}", 0, 0
    
    async def stock_out(self, item_name: str, quantity: float, unit: Optional[str], 
                       location: Optional[str], note: Optional[str], user_id: int, 
                       user_name: str, user_role: UserRole, driver_name: Optional[str] = None,
                       from_location: Optional[str] = None, project: Optional[str] = None) -> Tuple[bool, str, Optional[str], float, float]:
        """
        Process stock out operation.
        
        Returns:
            Tuple containing (success, message, movement_id, before_level, after_level)
        """
        try:
            # Get item details
            item = await self.airtable.get_item(item_name)
            if not item:
                return False, f"Item '{item_name}' not found.", None, 0, 0
            
            # Validate enhanced item structure
            is_valid, error_msg = await self._validate_enhanced_item_structure(item)
            if not is_valid:
                logger.warning(f"Enhanced item structure validation failed for {item_name}: {error_msg}")
                # Continue with operation but log the warning
            
            # Store the stock level before the operation
            before_level = item.on_hand
            
            # Determine base unit quantity
            base_quantity = await self._convert_to_base_quantity(item, quantity, unit)
            
            # Calculate the new stock level
            after_level = before_level - base_quantity
            
            # Check if this would result in negative stock
            if item.on_hand < base_quantity:
                if user_role != UserRole.ADMIN:
                    # Enhanced error message with unit context
                    if item.unit_size and item.unit_size > 1.0 and item.unit_type != "piece":
                        current_volume = item.on_hand * item.unit_size
                        requested_volume = base_quantity * item.unit_size
                        error_message = f"Insufficient stock. Current: {item.on_hand} units × {item.unit_size} {item.unit_type} = {current_volume} {item.unit_type}, Requested: {base_quantity} units × {item.unit_size} {item.unit_type} = {requested_volume} {item.unit_type}. Admin approval required for negative stock."
                    else:
                        error_message = f"Insufficient stock. Current: {item.on_hand} {item.unit_type}, Requested: {base_quantity} {item.unit_type}. Admin approval required for negative stock."
                    
                    return False, error_message, None, before_level, after_level
                else:
                    # Admin can override negative stock
                    pass
            
            # Check if approval is required based on item's Large Qty Threshold
            # First try to get the threshold from the item's Large Qty Threshold field
            item_threshold = await self._get_item_large_qty_threshold(item_name)
            approval_threshold = item_threshold or self.settings.default_approval_threshold
            
            # For our new implementation, all movements require approval
            # Using REQUESTED instead of PENDING_APPROVAL to match Airtable options
            status = MovementStatus.REQUESTED
            
            # Get category for the movement
            item_category = item.category if item.category else category_parser.parse_category(item_name)
            logger.info(f"Category detection for '{item_name}': item.category='{item.category}', parsed='{category_parser.parse_category(item_name)}', final='{item_category}'")
            if not item.category and item_category:
                logger.info(f"Auto-detected category for '{item_name}': {item_category}")

            # Create movement record
            movement = StockMovement(
                item_name=item_name,
                movement_type=MovementType.OUT,
                quantity=quantity,
                unit=unit or item.unit_type,
                signed_base_quantity=-base_quantity,  # Negative for out
                unit_size=item.unit_size,
                unit_type=item.unit_type,
                location=location or item.location,
                note=note,
                status=status,
                user_id=str(user_id),
                user_name=user_name,
                timestamp=datetime.now(UTC),
                reason="Purchase",
                driver_name=driver_name,
                from_location=from_location,
                project=project,
                category=item_category  # Add category field
            )
            
            logger.info(f"Created StockMovement object for '{item_name}' with category='{item_category}'")
            
            # Save to Airtable
            movement_id = await self.airtable.create_movement(movement)
            if not movement_id:
                return False, "Failed to save stock movement.", None, before_level, before_level
            
            # Enhanced success message with unit context and category
            if item.unit_size and item.unit_size > 1.0 and item.unit_type != "piece":
                total_volume = quantity * item.unit_size
                category_info = f" (Category: {item.category})" if item.category else ""
                success_message = f"Stock out request submitted for approval: {quantity} units × {item.unit_size} {item.unit_type} = {total_volume} {item.unit_type} of {item_name}{category_info}. Movement ID: {movement_id}"
            else:
                category_info = f" (Category: {item.category})" if item.category else ""
                success_message = f"Stock out request submitted for approval: {quantity} {unit or item.unit_type} of {item_name}{category_info}. Movement ID: {movement_id}"
            
            return True, success_message, movement_id, before_level, after_level
                
        except Exception as e:
            logger.error(f"Error in stock_out: {e}")
            return False, f"Error processing stock out: {str(e)}", None, 0, 0
    
    async def stock_adjust(self, item_name: str, quantity: float, unit: Optional[str], 
                          location: Optional[str], note: Optional[str], user_id: int, 
                          user_name: str, driver_name: Optional[str] = None,
                          from_location: Optional[str] = None, project: Optional[str] = None) -> Tuple[bool, str, float, float]:
        """
        Process stock adjustment (admin only).
        
        Returns:
            Tuple containing (success, message, before_level, after_level)
        """
        try:
            # Get item details
            item = await self.airtable.get_item(item_name)
            if not item:
                return False, f"Item '{item_name}' not found.", 0, 0
            
            # Validate enhanced item structure
            is_valid, error_msg = await self._validate_enhanced_item_structure(item)
            if not is_valid:
                logger.warning(f"Enhanced item structure validation failed for {item_name}: {error_msg}")
                # Continue with operation but log the warning
            
            # Store the stock level before the operation
            before_level = item.on_hand
            
            # Determine base unit quantity
            base_quantity = await self._convert_to_base_quantity(item, quantity, unit)
            
            # Calculate the new stock level
            after_level = before_level + base_quantity
            
            # Get category for the movement
            item_category = item.category if item.category else category_parser.parse_category(item_name)
            if not item.category and item_category:
                logger.info(f"Auto-detected category for '{item_name}': {item_category}")

            # Create movement record
            movement = StockMovement(
                item_name=item_name,
                movement_type=MovementType.ADJUST,
                quantity=quantity,
                unit=unit or item.unit_type,
                signed_base_quantity=base_quantity,
                unit_size=item.unit_size,
                unit_type=item.unit_type,
                location=location or item.location,
                note=note,
                status=MovementStatus.REQUESTED,  # All adjustments need approval
                user_id=str(user_id),
                user_name=user_name,
                timestamp=datetime.now(UTC),
                reason="Adjustment",
                driver_name=driver_name,
                from_location=from_location,
                project=project,
                category=item_category  # Add category field
            )
            
            # Save to Airtable
            movement_id = await self.airtable.create_movement(movement)
            if not movement_id:
                return False, "Failed to save stock movement.", before_level, before_level
            
            # Enhanced success message with unit context and category
            if item.unit_size and item.unit_size > 1.0 and item.unit_type != "piece":
                total_volume = quantity * item.unit_size
                category_info = f" (Category: {item.category})" if item.category else ""
                success_message = f"Stock adjustment request submitted for approval: {quantity} units × {item.unit_size} {item.unit_type} = {total_volume} {item.unit_type} of {item_name}{category_info}."
            else:
                category_info = f" (Category: {item.category})" if item.category else ""
                success_message = f"Stock adjustment request submitted for approval: {quantity} {unit or item.unit_type} of {item_name}{category_info}."
            
            return True, success_message, before_level, after_level
            
        except Exception as e:
            logger.error(f"Error in stock_adjust: {e}")
            return False, f"Error processing stock adjustment: {str(e)}", 0, 0
    
    async def _validate_enhanced_item_structure(self, item: Item) -> Tuple[bool, str]:
        """
        Validate enhanced item structure for mixed-size materials.
        
        Args:
            item: Item to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Validate unit_size
            if item.unit_size <= 0:
                return False, f"Invalid unit size: {item.unit_size}. Unit size must be greater than 0."
            
            # Validate unit_type
            if not item.unit_type or item.unit_type.strip() == "":
                return False, f"Invalid unit type: '{item.unit_type}'. Unit type cannot be empty."
            
            # Validate total volume calculation
            expected_total = item.unit_size * item.on_hand
            actual_total = item.get_total_volume()
            if abs(expected_total - actual_total) > 0.01:  # Allow small floating point differences
                return False, f"Total volume mismatch: expected {expected_total}, got {actual_total}"
            
            return True, "Enhanced item structure is valid"
            
        except Exception as e:
            return False, f"Error validating enhanced item structure: {str(e)}"

    async def _convert_to_base_quantity(self, item: Item, quantity: float, 
                                      unit: Optional[str]) -> float:
        """Convert quantity to base unit."""
        if not unit or unit == item.unit_type:
            return quantity
        
        # TODO: Implement unit conversion logic using Item Units table
        # For now, return the original quantity
        logger.warning(f"Unit conversion not implemented. Using original quantity for {item.name}")
        return quantity
    
    async def _get_item_large_qty_threshold(self, item_name: str) -> Optional[float]:
        """Get the Large Qty Threshold for an item."""
        try:
            item = await self.airtable.get_item(item_name)
            if item and item.large_qty_threshold:
                return item.large_qty_threshold
            return None
        except Exception as e:
            logger.error(f"Error getting item threshold: {e}")
            return None
    
    async def get_current_stock(self, item_name: str) -> Tuple[bool, str, Optional[Item]]:
        """Get current stock level for an item."""
        try:
            item = await self.airtable.get_item(item_name)
            if not item:
                return False, f"Item '{item_name}' not found.", None
            
            # Enhanced stock display with unit context
            if item.unit_size and item.unit_size > 1.0 and item.unit_type != "piece":
                total_volume = item.get_total_volume()
                stock_message = f"Current stock: {item.on_hand} units × {item.unit_size} {item.unit_type} = {total_volume} {item.unit_type}"
            else:
                stock_message = f"Current stock: {item.on_hand} {item.unit_type}"
            
            return True, stock_message, item
            
        except Exception as e:
            logger.error(f"Error getting current stock: {e}")
            return False, f"Error retrieving stock information: {str(e)}", None
    
    async def search_items(self, query: str) -> Tuple[bool, str, list]:
        """Search for items by SKU, name, or alias."""
        try:
            items = await self.airtable.search_items(query)
            if not items:
                return False, f"No items found matching '{query}'", []
            
            # Enhanced search results with unit context
            enhanced_items = []
            for item in items:
                if item.unit_size and item.unit_size > 1.0 and item.unit_type != "piece":
                    total_volume = item.get_total_volume()
                    enhanced_items.append(f"{item.name}: {item.on_hand} units × {item.unit_size} {item.unit_type} = {total_volume} {item.unit_type}")
                else:
                    enhanced_items.append(f"{item.name}: {item.on_hand} {item.unit_type}")
            
            return True, f"Found {len(items)} items matching '{query}'", items
            
        except Exception as e:
            logger.error(f"Error searching items: {e}")
            return False, f"Error searching items: {str(e)}", []
    
    async def get_low_stock_items(self) -> Tuple[bool, str, list]:
        """Get items with stock below threshold."""
        try:
            low_stock = await self.airtable.get_low_stock_items()
            if not low_stock:
                return True, "No items are currently below threshold.", []
            
            # Enhanced low stock display with unit context
            enhanced_low_stock = []
            for item in low_stock:
                if item.unit_size and item.unit_size > 1.0 and item.unit_type != "piece":
                    total_volume = item.get_total_volume()
                    threshold_volume = item.threshold * item.unit_size if item.threshold else 0
                    enhanced_low_stock.append(f"{item.name}: {item.on_hand} units × {item.unit_size} {item.unit_type} = {total_volume} {item.unit_type} (Threshold: {item.threshold} units = {threshold_volume} {item.unit_type})")
                else:
                    enhanced_low_stock.append(f"{item.name}: {item.on_hand} {item.base_unit} (Threshold: {item.threshold} {item.base_unit})")
            
            return True, f"Found {len(low_stock)} items below threshold", low_stock
            
        except Exception as e:
            logger.error(f"Error getting low stock items: {e}")
            return False, f"Error retrieving low stock items: {str(e)}", []
