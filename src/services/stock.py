"""Stock management service for the Construction Inventory Bot."""

import logging
from datetime import datetime
from typing import Optional, Tuple

from ..schemas import Item, StockMovement, MovementType, MovementStatus, UserRole
from ..airtable_client import AirtableClient
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
            
            # Store the stock level before the operation
            before_level = item.on_hand if item else 0
            
            # Determine base unit quantity
            base_quantity = await self._convert_to_base_quantity(item, quantity, unit) if item else quantity
            
            # Create movement record
            movement = StockMovement(
                item_name=item_name,
                movement_type=MovementType.IN,
                quantity=quantity,
                unit=unit or (item.base_unit if item else "piece"),
                signed_base_quantity=base_quantity,
                location=location or (item.location if item else None),
                note=note,
                status=MovementStatus.POSTED,
                user_id=str(user_id),
                user_name=user_name,
                timestamp=datetime.utcnow(),
                reason="Purchase",
                driver_name=driver_name,
                from_location=from_location,
                project=project
            )
            
            # Save to Airtable
            movement_id = await self.airtable.create_movement(movement)
            if not movement_id:
                return False, "Failed to save stock movement.", before_level, before_level
            
            # Calculate after level
            after_level = before_level + base_quantity
            
            return True, f"Stock in: {quantity} {unit or (item.base_unit if item else 'piece')} of {item_name} recorded successfully.", before_level, after_level
            
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
            
            # Store the stock level before the operation
            before_level = item.on_hand
            
            # Determine base unit quantity
            base_quantity = await self._convert_to_base_quantity(item, quantity, unit)
            
            # Calculate the new stock level
            after_level = before_level - base_quantity
            
            # Check if this would result in negative stock
            if item.on_hand < base_quantity:
                if user_role != UserRole.ADMIN:
                    return False, f"Insufficient stock. Current: {item.on_hand} {item.base_unit}, Requested: {base_quantity} {item.base_unit}. Admin approval required for negative stock.", None, before_level, after_level
                else:
                    # Admin can override negative stock
                    pass
            
            # Check if approval is required based on item's Large Qty Threshold
            # First try to get the threshold from the item's Large Qty Threshold field
            item_threshold = await self._get_item_large_qty_threshold(item_name)
            approval_threshold = item_threshold or self.settings.default_approval_threshold
            
            # For our new implementation, all movements require approval
            status = MovementStatus.PENDING_APPROVAL
            
            # Create movement record
            movement = StockMovement(
                item_name=item_name,
                movement_type=MovementType.OUT,
                quantity=quantity,
                unit=unit or item.base_unit,
                signed_base_quantity=-base_quantity,  # Negative for out
                location=location or item.location,
                note=note,
                status=status,
                user_id=str(user_id),
                user_name=user_name,
                timestamp=datetime.utcnow(),
                reason="Issue",
                driver_name=driver_name,
                from_location=from_location,
                project=project
            )
            
            # Save to Airtable
            movement_id = await self.airtable.create_movement(movement)
            if not movement_id:
                return False, "Failed to save stock movement.", None, before_level, before_level
            
            return True, f"Stock out request submitted for approval. Movement ID: {movement_id}", movement_id, before_level, after_level
                
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
            
            # Store the stock level before the operation
            before_level = item.on_hand
            
            # Determine base unit quantity
            base_quantity = await self._convert_to_base_quantity(item, quantity, unit)
            
            # Calculate the new stock level
            after_level = before_level + base_quantity
            
            # Create movement record
            movement = StockMovement(
                item_name=item_name,
                movement_type=MovementType.ADJUST,
                quantity=quantity,
                unit=unit or item.base_unit,
                signed_base_quantity=base_quantity,
                location=location or item.location,
                note=note,
                status=MovementStatus.PENDING_APPROVAL,  # All adjustments need approval
                user_id=str(user_id),
                user_name=user_name,
                timestamp=datetime.utcnow(),
                reason="Adjustment",
                driver_name=driver_name,
                from_location=from_location,
                project=project
            )
            
            # Save to Airtable
            movement_id = await self.airtable.create_movement(movement)
            if not movement_id:
                return False, "Failed to save stock movement.", before_level, before_level
            
            return True, f"Stock adjustment request submitted for approval: {quantity} {unit or item.base_unit} of {item_name}.", before_level, after_level
            
        except Exception as e:
            logger.error(f"Error in stock_adjust: {e}")
            return False, f"Error processing stock adjustment: {str(e)}", 0, 0
    
    async def _convert_to_base_quantity(self, item: Item, quantity: float, 
                                      unit: Optional[str]) -> float:
        """Convert quantity to base unit."""
        if not unit or unit == item.base_unit:
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
            
            return True, f"Current stock: {item.on_hand} {item.base_unit}", item
            
        except Exception as e:
            logger.error(f"Error getting current stock: {e}")
            return False, f"Error retrieving stock information: {str(e)}", None
    
    async def search_items(self, query: str) -> Tuple[bool, str, list]:
        """Search for items by SKU, name, or alias."""
        try:
            items = await self.airtable.search_items(query)
            if not items:
                return False, f"No items found matching '{query}'", []
            
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
            
            return True, f"Found {len(low_stock)} items below threshold", low_stock
            
        except Exception as e:
            logger.error(f"Error getting low stock items: {e}")
            return False, f"Error retrieving low stock items: {str(e)}", []
