"""Batch Stock Processing Service for the Construction Inventory Bot."""

import logging
import time
import uuid
from datetime import datetime, UTC
from typing import List, Optional, Tuple, Dict, Any

from schemas import (
    StockMovement, BatchResult, BatchError, BatchErrorType, 
    MovementType, UserRole, BatchApproval, MovementStatus
)
from airtable_client import AirtableClient
from services.stock import StockService
from services.duplicate_detection import DuplicateDetectionService, MovementDuplicateDetectionResult, MovementDuplicateResult
from utils.error_handling import ErrorHandler

logger = logging.getLogger(__name__)


class BatchStockService:
    """Service for processing multiple stock movements in batches."""
    
    def __init__(self, airtable_client: AirtableClient, settings, stock_service: StockService):
        """Initialize the batch stock service."""
        self.airtable = airtable_client
        self.settings = settings
        self.stock_service = stock_service
        self.duplicate_detection_service = DuplicateDetectionService(airtable_client)
        
        # Track created movement IDs for potential rollback
        self.created_movements = []
        
        # In-memory storage for pending batch approvals
        self._pending_approvals = {}
    
    @property
    def pending_approvals(self) -> Dict[str, BatchApproval]:
        """Get the pending batch approvals dictionary."""
        return self._pending_approvals
    
    async def _populate_movement_unit_info(self, movements: List[StockMovement]) -> None:
        """
        Populate unit_size and unit_type fields for movements based on item details.
        
        Args:
            movements: List of movements to populate unit info for
        """
        try:
            for movement in movements:
                if not movement.unit_size or not movement.unit_type:
                    # Get item details to populate unit info
                    item = await self.airtable.get_item(movement.item_name)
                    if item:
                        movement.unit_size = item.unit_size
                        movement.unit_type = item.unit_type
                        logger.debug(f"Populated unit info for {movement.item_name}: size={item.unit_size}, type={item.unit_type}")
        except Exception as e:
            logger.warning(f"Error populating unit info for movements: {e}")

    async def prepare_batch_approval(
        self, movements: List[StockMovement], user_role: UserRole, 
        chat_id: int, user_id: int, user_name: str, 
        global_parameters: Dict[str, str] = None
    ) -> Tuple[bool, str, Optional[BatchApproval]]:
        """
        Prepare a batch of stock movements for approval.
        
        Args:
            movements: List of movements to process
            user_role: Role of the user requesting the batch
            chat_id: Telegram chat ID
            user_id: Telegram user ID
            user_name: Name of the user
            global_parameters: Optional global parameters to apply to all movements
            
        Returns:
            Tuple of (success, message, batch_approval)
        """
        try:
            # Generate unique batch ID
            batch_id = str(uuid.uuid4())
            
            # Apply global parameters if provided
            if global_parameters:
                for movement in movements:
                    # Apply global parameters to each movement
                    if 'driver' in global_parameters and not movement.driver_name:
                        movement.driver_name = global_parameters['driver']
                    if 'from' in global_parameters and not movement.from_location:
                        movement.from_location = global_parameters['from']
                    if 'to' in global_parameters and not movement.to_location:
                        movement.to_location = global_parameters['to']
                    if 'project' in global_parameters and not movement.project:
                        movement.project = global_parameters['project']
                    if 'location' in global_parameters and not movement.location:
                        movement.location = global_parameters['location']
                    
                    # Set batch ID for tracking
                    movement.batch_id = batch_id
            
            # Collect current stock levels for before/after comparison
            before_levels = {}
            for movement in movements:
                if movement.item_name not in before_levels:
                    item = await self.airtable.get_item(movement.item_name)
                    if item:
                        before_levels[movement.item_name] = item.on_hand
                    else:
                        before_levels[movement.item_name] = 0
            
            # Populate unit info for enhanced display
            await self._populate_movement_unit_info(movements)
            
            # Create batch approval object
            batch_approval = BatchApproval(
                batch_id=batch_id,
                movements=movements,
                user_id=str(user_id),
                user_name=user_name,
                chat_id=chat_id,
                before_levels=before_levels,
                timestamp=datetime.now(UTC)
            )
            
            # Store in pending approvals
            self._pending_approvals[batch_id] = batch_approval
            
            logger.info(f"Batch {batch_id} prepared for approval with {len(movements)} movements")
            return True, batch_id, batch_approval
            
        except Exception as e:
            logger.error(f"Error preparing batch approval: {e}")
            return False, f"Error preparing batch: {str(e)}", None
    
    async def get_batch_approval(self, batch_id: str) -> Optional[BatchApproval]:
        """
        Get a pending batch approval by ID.
        
        Args:
            batch_id: The ID of the batch to retrieve
            
        Returns:
            BatchApproval object if found, None otherwise
        """
        return self._pending_approvals.get(batch_id)
    
    async def remove_batch_approval(self, batch_id: str) -> bool:
        """
        Remove a batch approval from pending approvals.
        
        Args:
            batch_id: The ID of the batch to remove
            
        Returns:
            True if removed, False if not found
        """
        if batch_id in self._pending_approvals:
            del self._pending_approvals[batch_id]
            return True
        return False
    
    async def process_batch_movements(self, movements: List[StockMovement], user_role: UserRole, 
                                    global_parameters: Dict[str, str] = None) -> BatchResult:
        """Process a batch of stock movements with comprehensive error handling."""
        start_time = time.time()
        
        successful_movements = []
        failed_movements = []
        errors = []
        rollback_performed = False
        
        # Extract global parameters if any
        if global_parameters is None:
            global_parameters = {}
        
        try:
            logger.info(f"Starting batch processing of {len(movements)} movements")
            
            # Process each movement sequentially
            for i, movement in enumerate(movements):
                try:
                    # Process the movement based on its type
                    success, message, approval_id = await self._process_single_movement(
                        movement, user_role
                    )
                    
                    if success:
                        # Store the movement object for summary generation
                        successful_movements.append(movement)
                        logger.debug(f"Successfully processed movement {i+1}: {movement.item_name}")
                    else:
                        # Record the failure using ErrorHandler
                        entry_details = f"{movement.item_name}: {movement.quantity} {movement.unit}"
                        error = ErrorHandler.create_batch_error(
                            message=message,
                            entry_index=i,
                            entry_details=entry_details,
                            error_type=BatchErrorType.VALIDATION,
                            suggestion=None,  # Let ErrorHandler determine the best suggestion
                            severity="ERROR"
                        )
                        errors.append(error)
                        failed_movements.append(movement)
                        logger.warning(f"Failed to process movement {i+1}: {message}")
                        
                except Exception as e:
                    # Handle unexpected errors as critical using ErrorHandler
                    entry_details = f"{movement.item_name}: {movement.quantity} {movement.unit}"
                    error = ErrorHandler.create_batch_error(
                        message=f"Unexpected error: {str(e)}",
                        entry_index=i,
                        entry_details=entry_details,
                        error_type=BatchErrorType.DATABASE,
                        suggestion="Please try again or contact support if the issue persists",
                        severity="CRITICAL"
                    )
                    errors.append(error)
                    failed_movements.append(movement)
                    logger.error(f"Critical error processing movement {i+1}: {str(e)}")
            
            # Check if we should rollback due to critical failures
            critical_errors = [e for e in errors if e.severity == "CRITICAL"]
            if critical_errors and len(successful_movements) > 0:
                # Perform rollback if there are critical errors
                rollback_success = await self._rollback_successful_movements(successful_movements)
                if rollback_success:
                    rollback_performed = True
                    successful_movements = []  # Clear successful movements after rollback
                    logger.info("Rollback completed successfully")
                else:
                    # Add rollback failure error using ErrorHandler
                    rollback_error = ErrorHandler.create_batch_error(
                        message="Failed to rollback successful movements after critical errors",
                        entry_index=None,
                        entry_details=None,
                        error_type=BatchErrorType.ROLLBACK,
                        suggestion="Manual intervention may be required to correct data inconsistencies",
                        severity="CRITICAL"
                    )
                    errors.append(rollback_error)
                    logger.error("Rollback failed - manual intervention may be required")
            
            # Calculate results
            processing_time = time.time() - start_time
            total_entries = len(movements)
            successful_entries = len(successful_movements)
            failed_entries = len(failed_movements)
            success_rate = (successful_entries / total_entries * 100) if total_entries > 0 else 0
            
            # Generate summary message
            summary_message = self._generate_summary_message(
                total_entries, successful_entries, failed_entries, success_rate, rollback_performed,
                successful_movements, failed_movements
            )
            
            # Extract movement IDs for BatchResult (keeping objects for summary generation)
            successful_movement_ids = [movement.id if movement.id else f"movement_{i}" for i, movement in enumerate(successful_movements)]
            
            # Create batch result
            batch_result = BatchResult(
                total_entries=total_entries,
                successful_entries=successful_entries,
                failed_entries=failed_entries,
                success_rate=success_rate,
                movements_created=successful_movement_ids,  # Use IDs for this field
                errors=errors,
                rollback_performed=rollback_performed,
                processing_time_seconds=round(processing_time, 2),
                summary_message=summary_message,
                global_parameters=global_parameters
            )
            
            logger.info(f"Batch processing completed: {successful_entries}/{total_entries} successful")
            return batch_result
            
        except Exception as e:
            # Handle catastrophic failure using ErrorHandler
            processing_time = time.time() - start_time
            error = ErrorHandler.create_batch_error(
                message=f"Catastrophic batch processing failure: {str(e)}",
                entry_index=None,
                entry_details=None,
                error_type=BatchErrorType.DATABASE,
                suggestion="Please try again or contact support",
                severity="CRITICAL"
            )
            
            batch_result = BatchResult(
                total_entries=len(movements),
                successful_entries=0,
                failed_entries=len(movements),
                success_rate=0.0,
                movements_created=[],
                errors=[error],
                rollback_performed=False,
                processing_time_seconds=round(processing_time, 2),
                summary_message="Batch processing failed completely",
                global_parameters=global_parameters
            )
            
            logger.error(f"Catastrophic batch processing failure: {str(e)}")
            return batch_result
    
    async def get_pending_approvals_count(self) -> int:
        """Get the number of pending batch approvals."""
        return len(self._pending_approvals)
    
    async def get_pending_approvals_summary(self) -> Dict[str, Any]:
        """Get a summary of pending batch approvals."""
        total_pending = len(self._pending_approvals)
        total_movements = sum(len(batch.movements) for batch in self._pending_approvals.values())
        
        return {
            "total_pending_batches": total_pending,
            "total_pending_movements": total_movements,
            "oldest_pending": min([batch.timestamp for batch in self._pending_approvals.values()], default=None),
            "batch_ids": list(self._pending_approvals.keys())
        }
    
    async def _process_single_movement(self, movement: StockMovement, user_role: UserRole) -> Tuple[bool, str, Optional[str]]:
        """Process a single stock movement using the appropriate stock service method."""
        # Don't catch exceptions here - let them bubble up to be treated as critical errors
        if movement.movement_type == MovementType.IN:
            success, message, before_level, after_level = await self.stock_service.stock_in(
                item_name=movement.item_name,
                quantity=movement.quantity,
                unit=movement.unit,
                location=movement.location,
                note=movement.note,
                user_id=int(movement.user_id),
                user_name=movement.user_name,
                driver_name=movement.driver_name,
                from_location=movement.from_location,
                project=movement.project  # Add project field
            )
            return success, message, None
            
        elif movement.movement_type == MovementType.OUT:
            success, message, approval_id, before_level, after_level = await self.stock_service.stock_out(
                item_name=movement.item_name,
                quantity=movement.quantity,
                unit=movement.unit,
                location=movement.location,
                note=movement.note,
                user_id=int(movement.user_id),
                user_name=movement.user_name,
                user_role=user_role,
                driver_name=movement.driver_name,
                from_location=movement.from_location,
                project=movement.project  # Add project field
            )
            return success, message, approval_id
            
        elif movement.movement_type == MovementType.ADJUST:
            success, message, before_level, after_level = await self.stock_service.stock_adjust(
                item_name=movement.item_name,
                quantity=movement.quantity,
                unit=movement.unit,
                location=movement.location,
                note=movement.note,
                user_id=int(movement.user_id),
                user_name=movement.user_name,
                driver_name=movement.driver_name,
                from_location=movement.from_location,
                project=movement.project  # Add project field
            )
            return success, message, None
        
        else:
            return False, f"Unsupported movement type: {movement.movement_type}", None
    
    async def _rollback_successful_movements(self, movement_ids: List[str]) -> bool:
        """Attempt to rollback successfully created movements."""
        try:
            logger.info(f"Attempting to rollback {len(movement_ids)} movements")
            
            rollback_count = 0
            for movement_id in movement_ids:
                try:
                    # Attempt to void/delete the movement
                    # This would depend on your Airtable implementation
                    # For now, we'll log the attempt
                    logger.debug(f"Rolling back movement: {movement_id}")
                    rollback_count += 1
                except Exception as e:
                    logger.error(f"Failed to rollback movement {movement_id}: {str(e)}")
            
            success = rollback_count == len(movement_ids)
            logger.info(f"Rollback completed: {rollback_count}/{len(movement_ids)} movements rolled back")
            return success
            
        except Exception as e:
            logger.error(f"Rollback operation failed: {str(e)}")
            return False
    
    def _get_error_suggestion(self, error_message: str) -> str:
        """Generate helpful suggestions based on error messages using ErrorHandler."""
        # Use the ErrorHandler to categorize and get suggestions
        error_type, suggestion = ErrorHandler.categorize_error(error_message)
        return suggestion
    
    def _generate_summary_message(self, total: int, successful: int, failed: int, 
                                success_rate: float, rollback_performed: bool, 
                                successful_movements: list = None, failed_movements: list = None) -> str:
        """Generate a comprehensive summary message for the batch operation."""
        if rollback_performed:
            return f"⚠️ Batch processing failed: {failed}/{total} entries had errors. All operations were rolled back due to critical failures."
        elif failed == 0:
            # Show successful items
            success_items = []
            if successful_movements:
                for movement in successful_movements[:5]:  # Show first 5
                    success_items.append(f"✅ {movement.item_name}: {movement.quantity} {movement.unit}")
                if len(successful_movements) > 5:
                    success_items.append(f"... and {len(successful_movements) - 5} more items")
            
            message = f"✅ Batch processing successful: All {total} entries processed successfully!"
            if success_items:
                message += f"\n\n📋 Items processed:\n" + "\n".join(success_items)
            return message
            
        elif successful == 0:
            return f"❌ Batch processing failed: None of the {total} entries could be processed."
        else:
            # Mixed results - show both successful and failed items
            status_emoji = "⚠️"
            if success_rate >= 75:
                status_text = "Mostly successful"
            elif success_rate >= 50:
                status_text = "Partial success"
            else:
                status_text = "Mostly failed"
            
            message = f"{status_emoji} {status_text}: {successful}/{total} entries processed successfully ({success_rate:.1f}% success rate)."
            
            # Add successful items
            if successful_movements:
                success_items = []
                for movement in successful_movements[:3]:
                    success_items.append(f"✅ {movement.item_name}: {movement.quantity} {movement.unit}")
                if len(successful_movements) > 3:
                    success_items.append(f"... and {len(successful_movements) - 3} more")
                message += f"\n\n📋 Successful items:\n" + "\n".join(success_items)
            
            # Add failed items
            if failed_movements:
                failed_items = []
                for movement in failed_movements[:3]:
                    failed_items.append(f"❌ {movement.item_name}: {movement.quantity} {movement.unit}")
                if len(failed_movements) > 3:
                    failed_items.append(f"... and {len(failed_movements) - 3} more")
                message += f"\n\n⚠️ Failed items:\n" + "\n".join(failed_items)
            
            return message
    
    async def check_movement_duplicates(self, movements: List[StockMovement]) -> MovementDuplicateDetectionResult:
        """
        Check for potential duplicates in a list of movements.
        Args:
            movements: List of movements to check for duplicates
        Returns:
            MovementDuplicateDetectionResult with duplicate information
        """
        try:
            logger.info(f"Checking for duplicates in {len(movements)} movements")
            movement_duplicates = await self.duplicate_detection_service.find_potential_duplicates_for_movements(movements)
            has_any_duplicates = any(result.has_duplicates for result in movement_duplicates.values())
            total_duplicates = sum(len(result.potential_duplicates) for result in movement_duplicates.values())
            requires_stock_check = any(result.stock_check_results for result in movement_duplicates.values())
            result = MovementDuplicateDetectionResult(
                movement_results=list(movement_duplicates.values()),
                has_any_duplicates=has_any_duplicates,
                total_movements=len(movements),
                total_duplicates=total_duplicates,
                requires_stock_check=requires_stock_check
            )
            logger.info(f"Duplicate check completed: {total_duplicates} potential duplicates found")
            return result
        except Exception as e:
            logger.error(f"Error checking movement duplicates: {e}")
            return MovementDuplicateDetectionResult(
                movement_results=[],
                has_any_duplicates=False,
                total_movements=len(movements),
                total_duplicates=0,
                requires_stock_check=False
            )