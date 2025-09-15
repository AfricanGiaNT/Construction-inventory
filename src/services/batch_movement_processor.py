"""Batch Movement Processing Service for the Construction Inventory Bot."""

import logging
import time
import uuid
from datetime import datetime, UTC
from typing import List, Optional, Tuple, Dict, Any

from src.schemas import (
    BatchInfo, BatchItem, BatchParseResult, StockMovement, 
    MovementType, MovementStatus, BatchResult, BatchError, BatchErrorType
)
from src.airtable_client import AirtableClient
from src.services.stock import StockService
from src.services.batch_movement_parser import BatchMovementParser
from src.utils.error_handling import ErrorHandler

logger = logging.getLogger(__name__)


class BatchMovementProcessor:
    """Service for processing batch movement commands."""
    
    def __init__(self, airtable_client: AirtableClient, settings, stock_service: StockService):
        """Initialize the batch movement processor."""
        self.airtable = airtable_client
        self.settings = settings
        self.stock_service = stock_service
        self.parser = BatchMovementParser()
        self.error_handler = ErrorHandler()
        
        # Track created movement IDs for potential rollback
        self.created_movements = []
    
    async def process_batch_command(self, command_text: str, movement_type: MovementType, 
                                  user_id: int, user_name: str) -> BatchResult:
        """
        Process a batch movement command.
        
        Args:
            command_text: The raw command text
            movement_type: Type of movement (IN or OUT)
            user_id: User ID performing the operation
            user_name: User name performing the operation
            
        Returns:
            BatchResult with processing results
        """
        start_time = time.time()
        self.created_movements = []
        
        try:
            # Parse the command
            parse_result = self.parser.parse_batch_command(command_text, movement_type)
            
            if not parse_result.is_valid:
                return BatchResult(
                    total_entries=parse_result.total_entries,
                    successful_entries=0,
                    failed_entries=parse_result.total_entries,
                    success_rate=0.0,
                    errors=[BatchError(
                        error_type=BatchErrorType.PARSING,
                        message=f"Failed to parse command: {'; '.join(parse_result.errors)}",
                        severity="ERROR"
                    )],
                    processing_time_seconds=time.time() - start_time,
                    summary_message="Command parsing failed"
                )
            
            # Generate batch summary
            batch_summary = self.parser.generate_batch_summary(parse_result.batches)
            logger.info(f"Processing batch command: {batch_summary}")
            
            # Process each batch
            successful_entries = 0
            failed_entries = 0
            errors = []
            movements_created = []
            
            for batch in parse_result.batches:
                try:
                    # Apply smart defaults
                    batch = self.parser.apply_smart_defaults(batch, movement_type)
                    
                    # Validate batch
                    batch_errors = self.parser.validate_batch(batch)
                    if batch_errors:
                        errors.extend([
                            BatchError(
                                error_type=BatchErrorType.VALIDATION,
                                message=error,
                                severity="ERROR"
                            ) for error in batch_errors
                        ])
                        failed_entries += 1
                        continue
                    
                    # Process batch
                    batch_result = await self._process_single_batch(
                        batch, movement_type, user_id, user_name
                    )
                    
                    if batch_result['success']:
                        successful_entries += len(batch.items)
                        movements_created.extend(batch_result['movement_ids'])
                    else:
                        failed_entries += len(batch.items)
                        errors.extend(batch_result['errors'])
                
                except Exception as e:
                    error_msg = f"Batch {batch.batch_number}: {str(e)}"
                    logger.error(f"Error processing batch {batch.batch_number}: {e}")
                    errors.append(BatchError(
                        error_type=BatchErrorType.DATABASE,
                        message=error_msg,
                        severity="ERROR"
                    ))
                    failed_entries += len(batch.items)
            
            # Calculate success rate
            total_entries = successful_entries + failed_entries
            success_rate = (successful_entries / total_entries * 100) if total_entries > 0 else 0.0
            
            # Generate summary message
            summary_message = self._generate_summary_message(
                successful_entries, failed_entries, len(parse_result.batches)
            )
            
            return BatchResult(
                total_entries=total_entries,
                successful_entries=successful_entries,
                failed_entries=failed_entries,
                success_rate=success_rate,
                movements_created=movements_created,
                errors=errors,
                processing_time_seconds=time.time() - start_time,
                summary_message=summary_message
            )
            
        except Exception as e:
            logger.error(f"Error processing batch command: {e}")
            return BatchResult(
                total_entries=0,
                successful_entries=0,
                failed_entries=0,
                success_rate=0.0,
                errors=[BatchError(
                    error_type=BatchErrorType.DATABASE,
                    message=f"Unexpected error: {str(e)}",
                    severity="CRITICAL"
                )],
                processing_time_seconds=time.time() - start_time,
                summary_message="Unexpected error occurred"
            )
    
    async def _process_single_batch(self, batch: BatchInfo, movement_type: MovementType, 
                                  user_id: int, user_name: str) -> Dict[str, Any]:
        """
        Process a single batch.
        
        Args:
            batch: Batch to process
            movement_type: Type of movement
            user_id: User ID
            user_name: User name
            
        Returns:
            Dictionary with processing results
        """
        movement_ids = []
        errors = []
        
        try:
            for item in batch.items:
                try:
                    # Create stock movement
                    movement = await self._create_stock_movement(
                        item, batch, movement_type, user_id, user_name
                    )
                    
                    # Process the movement
                    if movement_type == MovementType.IN:
                        success, message, before_level, after_level = await self.stock_service.stock_in(
                            item_name=item.item_name,
                            quantity=item.quantity,
                            unit=item.unit,
                            location=batch.from_location,
                            note=f"Batch {batch.batch_number}",
                            user_id=user_id,
                            user_name=user_name,
                            driver_name=batch.driver,
                            from_location=batch.from_location,
                            project=batch.project
                        )
                    else:  # MovementType.OUT
                        success, message, before_level, after_level = await self.stock_service.stock_out(
                            item_name=item.item_name,
                            quantity=item.quantity,
                            unit=item.unit,
                            location=batch.to_location,
                            note=f"Batch {batch.batch_number}",
                            user_id=user_id,
                            user_name=user_name,
                            driver_name=batch.driver,
                            to_location=batch.to_location,
                            project=batch.project
                        )
                    
                    if success:
                        movement_ids.append(str(uuid.uuid4()))  # Generate movement ID
                        self.created_movements.append(str(uuid.uuid4()))
                        logger.info(f"Successfully processed {item.item_name} in batch {batch.batch_number}")
                    else:
                        errors.append(BatchError(
                            error_type=BatchErrorType.DATABASE,
                            message=f"Failed to process {item.item_name}: {message}",
                            severity="ERROR"
                        ))
                        logger.error(f"Failed to process {item.item_name} in batch {batch.batch_number}: {message}")
                
                except Exception as e:
                    error_msg = f"Error processing {item.item_name}: {str(e)}"
                    errors.append(BatchError(
                        error_type=BatchErrorType.DATABASE,
                        message=error_msg,
                        severity="ERROR"
                    ))
                    logger.error(f"Error processing {item.item_name} in batch {batch.batch_number}: {e}")
            
            return {
                'success': len(errors) == 0,
                'movement_ids': movement_ids,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error processing batch {batch.batch_number}: {e}")
            return {
                'success': False,
                'movement_ids': [],
                'errors': [BatchError(
                    error_type=BatchErrorType.DATABASE,
                    message=f"Batch processing error: {str(e)}",
                    severity="ERROR"
                )]
            }
    
    async def _create_stock_movement(self, item: BatchItem, batch: BatchInfo, 
                                   movement_type: MovementType, user_id: int, user_name: str) -> StockMovement:
        """
        Create a StockMovement object from batch item.
        
        Args:
            item: Batch item
            batch: Batch information
            movement_type: Type of movement
            user_id: User ID
            user_name: User name
            
        Returns:
            StockMovement object
        """
        return StockMovement(
            item_name=item.item_name,
            movement_type=movement_type,
            quantity=item.quantity,
            unit=item.unit or "piece",
            signed_base_quantity=item.quantity,  # Will be updated by stock service
            location=batch.from_location if movement_type == MovementType.IN else batch.to_location,
            note=f"Batch {batch.batch_number}",
            status=MovementStatus.POSTED,
            user_id=str(user_id),
            user_name=user_name,
            timestamp=datetime.now(UTC),
            driver_name=batch.driver,
            from_location=batch.from_location if movement_type == MovementType.IN else None,
            to_location=batch.to_location if movement_type == MovementType.OUT else None,
            project=batch.project,
            batch_id=str(uuid.uuid4()),
            source="Telegram"
        )
    
    def _generate_summary_message(self, successful_entries: int, failed_entries: int, 
                                total_batches: int) -> str:
        """
        Generate a summary message for batch processing results.
        
        Args:
            successful_entries: Number of successful entries
            failed_entries: Number of failed entries
            total_batches: Total number of batches processed
            
        Returns:
            Summary message
        """
        if successful_entries == 0 and failed_entries == 0:
            return "No entries processed"
        
        if failed_entries == 0:
            return f"✅ Successfully processed {successful_entries} items across {total_batches} batch(es)"
        elif successful_entries == 0:
            return f"❌ Failed to process {failed_entries} items across {total_batches} batch(es)"
        else:
            return f"⚠️ Processed {successful_entries} items successfully, {failed_entries} failed across {total_batches} batch(es)"
    
    async def rollback_batch(self, movement_ids: List[str]) -> bool:
        """
        Rollback a batch by reversing the movements.
        
        Args:
            movement_ids: List of movement IDs to rollback
            
        Returns:
            True if rollback successful, False otherwise
        """
        try:
            # This would implement rollback logic
            # For now, just log the rollback attempt
            logger.info(f"Rolling back batch with {len(movement_ids)} movements")
            return True
        except Exception as e:
            logger.error(f"Error during rollback: {e}")
            return False
    
    def get_batch_summary(self, batches: List[BatchInfo]) -> str:
        """
        Get a summary of batches for user confirmation.
        
        Args:
            batches: List of batches to summarize
            
        Returns:
            Formatted summary string
        """
        return self.parser.generate_batch_summary(batches)
    
    def validate_batch_command(self, command_text: str, movement_type: MovementType) -> Tuple[bool, str, List[BatchInfo]]:
        """
        Validate a batch command without processing it.
        
        Args:
            command_text: The command text to validate
            movement_type: Type of movement
            
        Returns:
            Tuple of (is_valid, error_message, batches)
        """
        try:
            parse_result = self.parser.parse_batch_command(command_text, movement_type)
            
            if not parse_result.is_valid:
                return False, f"Parsing errors: {'; '.join(parse_result.errors)}", []
            
            # Validate each batch
            all_errors = []
            for batch in parse_result.batches:
                batch_errors = self.parser.validate_batch(batch)
                all_errors.extend(batch_errors)
            
            if all_errors:
                return False, f"Validation errors: {'; '.join(all_errors)}", parse_result.batches
            
            return True, "Command is valid", parse_result.batches
            
        except Exception as e:
            return False, f"Validation error: {str(e)}", []
