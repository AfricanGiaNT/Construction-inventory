"""Enhanced Batch Processor with Duplicate Detection for the Construction Inventory Bot."""

import logging
import time
from typing import List, Optional, Dict, Any

from src.schemas import (
    BatchInfo, BatchItem, BatchParseResult, StockMovement, 
    MovementType, MovementStatus, BatchResult, BatchError, BatchErrorType,
    DuplicateAnalysis, DuplicateProcessingResult
)
from src.airtable_client import AirtableClient
from src.services.stock import StockService
from src.services.batch_movement_parser import BatchMovementParser
from src.services.batch_duplicate_handler import BatchDuplicateHandler
from src.utils.error_handling import ErrorHandler

logger = logging.getLogger(__name__)


class EnhancedBatchProcessor:
    """Enhanced batch processor with duplicate detection capabilities."""
    
    def __init__(self, airtable_client: AirtableClient, settings, stock_service: StockService):
        """Initialize the enhanced batch processor."""
        self.airtable = airtable_client
        self.settings = settings
        self.stock_service = stock_service
        self.parser = BatchMovementParser()
        self.duplicate_handler = BatchDuplicateHandler(airtable_client, stock_service)
        self.error_handler = ErrorHandler()
        
        # Track created movement IDs for potential rollback
        self.created_movements = []
    
    async def process_batch_command_with_duplicates(self, command_text: str, movement_type: MovementType, 
                                                  user_id: int, user_name: str, chat_id: int | None = None) -> BatchResult:
        """
        Process a batch command with duplicate detection and handling.
        
        Args:
            command_text: The command text to parse and process
            movement_type: Type of movement (IN/OUT)
            user_id: User ID
            user_name: User name
            
        Returns:
            BatchResult with processing results including duplicate handling
        """
        start_time = time.time()
        
        try:
            logger.info(f"Processing enhanced batch command: {command_text[:100]}...")
            
            # Step 1: Parse the command
            parse_result = self.parser.parse_batch_command(command_text, movement_type)
            if not parse_result.is_valid:
                return self._create_error_result(
                    f"Failed to parse command: {'; '.join(parse_result.errors)}",
                    parse_result.errors,
                    time.time() - start_time
                )
            
            # Step 2: Identify duplicates
            logger.info("Identifying duplicates in batch items...")
            duplicate_analysis = await self.duplicate_handler.identify_duplicates(parse_result.batches)
            
            # Step 3: Process non-duplicates first (with error recovery)
            logger.info(f"Processing {duplicate_analysis.non_duplicate_count} non-duplicate items...")
            non_duplicate_result = await self._process_with_error_recovery(
                lambda: self.duplicate_handler.process_non_duplicates(
                    duplicate_analysis.non_duplicates, movement_type, user_id, user_name
                ),
                "non-duplicate items"
            )
            
            # Step 4: Process duplicates (with error recovery)
            duplicate_result = DuplicateProcessingResult()
            if duplicate_analysis.duplicate_count > 0:
                logger.info(f"Processing {duplicate_analysis.duplicate_count} duplicate items...")
                duplicate_result = await self._process_with_error_recovery(
                    lambda: self.duplicate_handler.process_duplicates(
                        duplicate_analysis.duplicates, movement_type, user_id, user_name,
                        auto_merge_exact=False, require_user_confirmation=True
                    ),
                    "duplicate items"
                )
                
                # If user confirmation is required, store the data for callback handling
                if duplicate_result.requires_user_confirmation and duplicate_result.pending_duplicates:
                    # Store pending duplicates for UI confirmation using chat_id if available
                    target_chat_id = chat_id if chat_id is not None else user_id
                    await self._store_duplicate_confirmation_data(
                        target_chat_id, duplicate_result.pending_duplicates, movement_type, user_id, user_name
                    )
            
            # Step 5: Combine results
            total_entries = duplicate_analysis.total_items
            successful_entries = non_duplicate_result.success_count + duplicate_result.success_count
            failed_entries = non_duplicate_result.failure_count + duplicate_result.failure_count
            
            # Calculate success rate
            success_rate = (successful_entries / total_entries * 100) if total_entries > 0 else 0.0
            
            # Combine all errors
            all_errors = non_duplicate_result.processing_errors + duplicate_result.processing_errors
            
            # Generate summary message
            summary_message = self._generate_enhanced_summary_message(
                total_entries, successful_entries, failed_entries, success_rate,
                duplicate_analysis, non_duplicate_result, duplicate_result
            )
            
            processing_time = time.time() - start_time
            
            return BatchResult(
                total_entries=total_entries,
                successful_entries=successful_entries,
                failed_entries=failed_entries,
                success_rate=success_rate,
                movements_created=self.created_movements,
                errors=all_errors,
                rollback_performed=False,
                processing_time_seconds=processing_time,
                summary_message=summary_message,
                global_parameters={}
            )
            
        except Exception as e:
            logger.error(f"Error in enhanced batch processing: {e}")
            return self._create_error_result(
                f"Unexpected error: {str(e)}",
                [BatchError(
                    error_type=BatchErrorType.DATABASE,
                    message=str(e),
                    severity="CRITICAL"
                )],
                time.time() - start_time
            )
    
    async def get_duplicate_preview(self, command_text: str, movement_type: MovementType) -> Dict[str, Any]:
        """
        Get a preview of duplicates without processing the command.
        
        Args:
            command_text: The command text to analyze
            movement_type: Type of movement (IN/OUT)
            
        Returns:
            Dictionary with duplicate analysis preview
        """
        try:
            # Parse the command
            parse_result = self.parser.parse_batch_command(command_text, movement_type)
            if not parse_result.is_valid:
                return {
                    "status": "error",
                    "message": f"Failed to parse command: {'; '.join(parse_result.errors)}",
                    "errors": parse_result.errors
                }
            
            # Identify duplicates
            duplicate_analysis = await self.duplicate_handler.identify_duplicates(parse_result.batches)
            
            # Format preview
            preview = {
                "status": "success",
                "total_items": duplicate_analysis.total_items,
                "duplicate_count": duplicate_analysis.duplicate_count,
                "non_duplicate_count": duplicate_analysis.non_duplicate_count,
                "exact_matches": len(duplicate_analysis.exact_matches),
                "similar_items": len(duplicate_analysis.similar_items),
                "duplicates": []
            }
            
            # Add duplicate details
            for duplicate in duplicate_analysis.duplicates:
                preview["duplicates"].append({
                    "item_name": duplicate.batch_item['item_name'],
                    "quantity": duplicate.batch_item['quantity'],
                    "existing_item": duplicate.existing_item['name'],
                    "existing_quantity": duplicate.existing_item['on_hand'],
                    "similarity_score": duplicate.similarity_score,
                    "match_type": duplicate.match_type.value,
                    "batch_number": duplicate.batch_number
                })
            
            return preview
            
        except Exception as e:
            logger.error(f"Error generating duplicate preview: {e}")
            return {
                "status": "error",
                "message": f"Error generating preview: {str(e)}"
            }
    
    def _create_error_result(self, message: str, errors: List[str], processing_time: float) -> BatchResult:
        """Create an error result."""
        batch_errors = []
        for error in errors:
            if isinstance(error, str):
                batch_errors.append(BatchError(
                    error_type=BatchErrorType.VALIDATION,
                    message=error,
                    severity="ERROR"
                ))
            else:
                batch_errors.append(error)
        
        return BatchResult(
            total_entries=0,
            successful_entries=0,
            failed_entries=0,
            success_rate=0.0,
            movements_created=[],
            errors=batch_errors,
            rollback_performed=False,
            processing_time_seconds=processing_time,
            summary_message=f"❌ {message}",
            global_parameters={}
        )
    
    def _generate_enhanced_summary_message(self, total_entries: int, successful_entries: int, 
                                         failed_entries: int, success_rate: float,
                                         duplicate_analysis: DuplicateAnalysis,
                                         non_duplicate_result: DuplicateProcessingResult,
                                         duplicate_result: DuplicateProcessingResult) -> str:
        """Generate enhanced summary message with duplicate information."""
        
        if success_rate == 100.0:
            message = f"✅ Successfully processed {successful_entries} items"
        elif success_rate == 0.0:
            message = f"❌ Failed to process {failed_entries} items"
        else:
            message = f"⚠️ Processed {successful_entries} items successfully, {failed_entries} failed"
        
        # Add duplicate information
        if duplicate_analysis.duplicate_count > 0:
            message += f"\n\n📋 Duplicate Analysis:"
            message += f"\n• {duplicate_analysis.non_duplicate_count} new items processed"
            message += f"\n• {len(duplicate_analysis.exact_matches)} exact matches auto-merged"
            message += f"\n• {len(duplicate_analysis.similar_items)} similar items processed"
            
            if duplicate_result.merged_items:
                message += f"\n• {len(duplicate_result.merged_items)} items merged with existing inventory"
        
        # Add processing details
        message += f"\n\n⏱️ Processing time: {success_rate:.1f}% success rate"
        
        return message
    
    async def _process_with_error_recovery(self, process_func, item_type: str) -> DuplicateProcessingResult:
        """
        Process items with error recovery - skip failed items and continue with others.
        
        Args:
            process_func: Function to process items
            item_type: Description of item type for logging
            
        Returns:
            DuplicateProcessingResult with processing results
        """
        try:
            return await process_func()
        except Exception as e:
            logger.error(f"Error processing {item_type}: {e}")
            # Return empty result with error information
            return DuplicateProcessingResult(
                processing_errors=[BatchError(
                    error_type=BatchErrorType.DATABASE,
                    message=f"Failed to process {item_type}: {str(e)}",
                    severity="ERROR"
                )],
                success_count=0,
                failure_count=0
            )
    
    async def _store_duplicate_confirmation_data(self, chat_id: int, duplicates: List[Any], 
                                                movement_type: MovementType, user_id: int, user_name: str):
        """
        Store duplicate confirmation data for callback handling.
        
        Args:
            chat_id: Telegram chat ID
            duplicates: List of duplicate items requiring confirmation
            movement_type: Type of movement (IN/OUT)
            user_id: User ID
            user_name: User name
        """
        try:
            # This would typically store data in a database or cache
            # For now, we'll use a simple in-memory storage
            if not hasattr(self, '_duplicate_confirmation_storage'):
                self._duplicate_confirmation_storage = {}
            
            self._duplicate_confirmation_storage[chat_id] = {
                'duplicates': [duplicate.model_dump() if hasattr(duplicate, 'model_dump') else duplicate for duplicate in duplicates],
                'movement_type': movement_type,
                'user_id': user_id,
                'user_name': user_name,
                'created_at': time.time(),
                'confirmed_items': [],
                'cancelled_items': []
            }
            
            logger.info(f"Stored duplicate confirmation data for chat {chat_id} with {len(duplicates)} items")
            
        except Exception as e:
            logger.error(f"Error storing duplicate confirmation data: {e}")
    
    async def get_duplicate_confirmation_data(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """
        Get stored duplicate confirmation data for a chat.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            Stored duplicate confirmation data or None
        """
        try:
            if not hasattr(self, '_duplicate_confirmation_storage'):
                return None
            
            return self._duplicate_confirmation_storage.get(chat_id)
            
        except Exception as e:
            logger.error(f"Error getting duplicate confirmation data: {e}")
            return None
    
    async def process_duplicate_confirmation(self, chat_id: int, action: str, item_index: int = None) -> Dict[str, Any]:
        """
        Process a duplicate confirmation action.
        
        Args:
            chat_id: Telegram chat ID
            action: Action taken (confirm, cancel, confirm_all, cancel_all)
            item_index: Index of specific item (for individual actions)
            
        Returns:
            Dictionary with processing results
        """
        try:
            duplicate_data = await self.get_duplicate_confirmation_data(chat_id)
            if not duplicate_data:
                return {"success": False, "message": "No pending duplicate confirmations found"}
            
            duplicates = duplicate_data['duplicates']
            movement_type = duplicate_data['movement_type']
            user_id = duplicate_data['user_id']
            user_name = duplicate_data['user_name']
            
            if action in ["confirm_all", "cancel_all"]:
                # Process all duplicates
                for i, duplicate in enumerate(duplicates):
                    result = await self.duplicate_handler.process_user_confirmation(
                        duplicate, action.replace("_all", ""), movement_type, user_id, user_name
                    )
                    
                    if action == "confirm_all":
                        duplicate_data['confirmed_items'].append(duplicate)
                    else:
                        duplicate_data['cancelled_items'].append(duplicate)
                
                total = len(duplicates)
                confirmed_count = len(duplicate_data['confirmed_items'])
                cancelled_count = len(duplicate_data['cancelled_items'])
                
                # Clean up storage
                del self._duplicate_confirmation_storage[chat_id]
                
                return {
                    "success": True,
                    "message": f"Processed {total} items",
                    "confirmed_count": confirmed_count,
                    "cancelled_count": cancelled_count,
                    "total": total,
                    "remaining": 0,
                    "all_processed": True
                }
            
            elif action in ["confirm", "cancel"] and item_index is not None:
                # Process individual duplicate
                if item_index >= len(duplicates):
                    return {"success": False, "message": "Invalid item index"}
                
                duplicate = duplicates[item_index]
                result = await self.duplicate_handler.process_user_confirmation(
                    duplicate, action, movement_type, user_id, user_name
                )
                
                if action == "confirm":
                    duplicate_data['confirmed_items'].append(duplicate)
                else:
                    duplicate_data['cancelled_items'].append(duplicate)
                
                # Check if all items processed
                total_processed = len(duplicate_data['confirmed_items']) + len(duplicate_data['cancelled_items'])
                total = len(duplicates)
                remaining = max(total - total_processed, 0)
                if total_processed >= total:
                    # All items processed, clean up
                    del self._duplicate_confirmation_storage[chat_id]
                
                return {
                    "success": True,
                    "message": f"Processed item {item_index + 1}",
                    "all_processed": total_processed >= total,
                    "confirmed_count": len(duplicate_data['confirmed_items']),
                    "cancelled_count": len(duplicate_data['cancelled_items']),
                    "total": total,
                    "remaining": remaining
                }
            
            else:
                return {"success": False, "message": "Invalid action or missing item index"}
                
        except Exception as e:
            logger.error(f"Error processing duplicate confirmation: {e}")
            return {"success": False, "message": f"Error processing confirmation: {str(e)}"}
