"""Approval workflow service for the Construction Inventory Bot."""

import logging
from datetime import datetime, UTC
from typing import List, Optional, Tuple, Dict, Any

from ..schemas import MovementStatus, UserRole, BatchResult
from ..airtable_client import AirtableClient
from .batch_stock import BatchStockService

logger = logging.getLogger(__name__)


class ApprovalService:
    """Service for managing approval workflows."""
    
    def __init__(self, airtable_client: AirtableClient, batch_stock_service: Optional[BatchStockService] = None):
        """
        Initialize the approval service.
        
        Args:
            airtable_client: Client for Airtable database access
            batch_stock_service: BatchStockService for batch approval operations
        """
        self.airtable = airtable_client
        self.batch_stock_service = batch_stock_service
    
    async def approve_movement(self, movement_id: str, approved_by: str, 
                             user_role: UserRole) -> Tuple[bool, str]:
        """
        Approve a pending movement request.
        
        Args:
            movement_id: The ID of the movement to approve
            approved_by: Name of the user approving the movement
            user_role: Role of the approving user
            
        Returns:
            Tuple containing success flag and message
        """
        try:
            # Check if user has admin role
            if user_role != UserRole.ADMIN:
                return False, "Only administrators can approve movements."
            
            # Update movement status
            success = await self.airtable.update_movement_status(
                movement_id, 
                MovementStatus.POSTED.value, 
                approved_by
            )
            
            if not success:
                return False, "Failed to update movement status."
            
            return True, f"Movement {movement_id} approved successfully by {approved_by}."
            
        except Exception as e:
            logger.error(f"Error approving movement: {e}")
            return False, f"Error processing approval: {str(e)}"
    
    async def approve_batch(self, batch_id: str, approved_by: str, 
                          user_role: UserRole) -> Tuple[bool, str, Optional[BatchResult]]:
        """
        Approve a pending batch and process all its movements.
        
        Args:
            batch_id: The ID of the batch to approve
            approved_by: Name of the user approving the batch
            user_role: Role of the approving user
            
        Returns:
            Tuple containing success flag, message, and BatchResult
        """
        try:
            # Check if batch stock service is available
            if not self.batch_stock_service:
                return False, "Batch approval service not available.", None
            
            # Check if user has admin role
            if user_role != UserRole.ADMIN:
                return False, "Only administrators can approve batches.", None
            
            # Get the batch from storage
            batch_approval = await self.batch_stock_service.get_batch_approval(batch_id)
            if not batch_approval:
                return False, f"Batch {batch_id} not found.", None
            
            logger.info(f"Processing approval for batch {batch_id} with {len(batch_approval.movements)} movements")
            
            # Update batch status
            batch_approval.status = "Approved"
            
            # Process the batch now that it's approved
            batch_result = await self.batch_stock_service.process_batch_movements(
                batch_approval.movements, 
                user_role,
                {}  # Global parameters already in movements
            )
            
            # Get updated stock levels for after comparison
            after_levels = {}
            for movement in batch_approval.movements:
                if movement.item_name not in after_levels:
                    item = await self.airtable.get_item(movement.item_name)
                    if item:
                        after_levels[movement.item_name] = item.on_hand
                    else:
                        after_levels[movement.item_name] = 0
            
            # Update batch with results
            batch_approval.after_levels = after_levels
            batch_approval.failed_entries = [
                {"item_name": error.entry_details, "error": error.message}
                for error in batch_result.errors
            ]
            
            # Only remove from pending approvals if successful
            if batch_result.failed_entries == 0 or batch_result.successful_entries > 0:
                await self.batch_stock_service.remove_batch_approval(batch_id)
            
            return True, f"Batch {batch_id} processed successfully by {approved_by}.", batch_result
            
        except Exception as e:
            logger.error(f"Error approving batch: {e}")
            return False, f"Error processing batch approval: {str(e)}", None
    
    async def reject_batch(self, batch_id: str, rejected_by: str, 
                         user_role: UserRole) -> Tuple[bool, str]:
        """
        Reject a pending batch without processing it.
        
        Args:
            batch_id: The ID of the batch to reject
            rejected_by: Name of the user rejecting the batch
            user_role: Role of the rejecting user
            
        Returns:
            Tuple containing success flag and message
        """
        try:
            # Check if batch stock service is available
            if not self.batch_stock_service:
                return False, "Batch approval service not available."
            
            # Check if user has admin role
            if user_role != UserRole.ADMIN:
                return False, "Only administrators can reject batches."
            
            # Get the batch from storage
            batch_approval = await self.batch_stock_service.get_batch_approval(batch_id)
            if not batch_approval:
                return False, f"Batch {batch_id} not found."
            
            # Update batch approval status
            batch_approval.status = "Rejected"
            
            # Remove from pending approvals
            await self.batch_stock_service.remove_batch_approval(batch_id)
            
            return True, f"Batch {batch_id} rejected by {rejected_by}."
            
        except Exception as e:
            logger.error(f"Error rejecting batch: {e}")
            return False, f"Error processing batch rejection: {str(e)}"
    
    async def void_movement(self, movement_id: str, voided_by: str, 
                           user_role: UserRole) -> Tuple[bool, str]:
        """
        Void a pending movement request.
        
        Args:
            movement_id: The ID of the movement to void
            voided_by: Name of the user voiding the movement
            user_role: Role of the voiding user
            
        Returns:
            Tuple containing success flag and message
        """
        try:
            # Check if user has admin role
            if user_role != UserRole.ADMIN:
                return False, "Only administrators can void movements."
            
            # Update movement status
            success = await self.airtable.update_movement_status(
                movement_id, 
                MovementStatus.VOIDED.value, 
                voided_by
            )
            
            if not success:
                return False, "Failed to update movement status."
            
            return True, f"Movement {movement_id} voided successfully by {voided_by}."
            
        except Exception as e:
            logger.error(f"Error voiding movement: {e}")
            return False, f"Error processing void: {str(e)}"
    
    async def get_pending_approvals(self) -> Tuple[bool, str, List[dict]]:
        """
        Get all pending approval requests from Airtable.
        
        Returns:
            Tuple containing success flag, message, and list of pending approvals
        """
        try:
            pending = await self.airtable.get_pending_approvals()
            if not pending:
                return True, "No pending approvals.", []
            
            return True, f"Found {len(pending)} pending approvals", pending
            
        except Exception as e:
            logger.error(f"Error getting pending approvals: {e}")
            return False, f"Error retrieving pending approvals: {str(e)}", []
    
    async def get_approval_summary(self) -> dict:
        """
        Get a summary of approval statistics.
        
        Returns:
            Dictionary containing approval statistics
        """
        try:
            pending = await self.airtable.get_pending_approvals()
            
            # Also include batch approvals if batch service is available
            batch_pending_count = 0
            batch_pending_movements = 0
            
            if self.batch_stock_service:
                batch_summary = await self.batch_stock_service.get_pending_approvals_summary()
                batch_pending_count = batch_summary["total_pending_batches"]
                batch_pending_movements = batch_summary["total_pending_movements"]
            
            return {
                "pending_count": len(pending),
                "pending_items": [item["sku"] for item in pending],
                "pending_batches": batch_pending_count,
                "pending_batch_movements": batch_pending_movements,
                "last_updated": datetime.now(UTC).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting approval summary: {e}")
            return {
                "pending_count": 0,
                "pending_items": [],
                "pending_batches": 0,
                "pending_batch_movements": 0,
                "last_updated": datetime.now(UTC).isoformat(),
                "error": str(e)
            }
    
    async def get_batch_approval_details(self, batch_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Get detailed information about a pending batch approval.
        
        Args:
            batch_id: The ID of the batch to get details for
            
        Returns:
            Tuple containing success flag, message, and batch details
        """
        try:
            # Check if batch stock service is available
            if not self.batch_stock_service:
                return False, "Batch approval service not available.", None
            
            # Get the batch from storage
            batch_approval = await self.batch_stock_service.get_batch_approval(batch_id)
            if not batch_approval:
                return False, f"Batch {batch_id} not found.", None
            
            # Create a summary dictionary
            details = {
                "batch_id": batch_approval.batch_id,
                "status": batch_approval.status,
                "user_name": batch_approval.user_name,
                "timestamp": batch_approval.timestamp.isoformat(),
                "total_movements": len(batch_approval.movements),
                "items": [
                    {
                        "name": movement.item_name,
                        "quantity": movement.quantity,
                        "unit": movement.unit,
                        "type": movement.movement_type.value,
                        "location": movement.location or "N/A"
                    }
                    for movement in batch_approval.movements
                ],
                "before_levels": batch_approval.before_levels
            }
            
            return True, f"Found batch {batch_id} details.", details
            
        except Exception as e:
            logger.error(f"Error getting batch approval details: {e}")
            return False, f"Error retrieving batch details: {str(e)}", None
    
    async def is_movement_approved(self, movement_id: str) -> bool:
        """
        Check if a movement has been approved.
        
        Args:
            movement_id: The ID of the movement to check
            
        Returns:
            True if approved, False otherwise
        """
        try:
            # This would require a method to get movement by ID
            # For now, we'll assume it's not approved if we can't check
            return False
        except Exception as e:
            logger.error(f"Error checking movement approval status: {e}")
            return False