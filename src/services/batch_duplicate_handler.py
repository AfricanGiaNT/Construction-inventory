"""Batch Duplicate Handler Service for the Construction Inventory Bot."""

import logging
import time
from typing import List, Dict, Tuple, Optional, Any
from difflib import SequenceMatcher

from src.schemas import (
    BatchInfo, BatchItem, Item, DuplicateAnalysis, DuplicateItem, 
    DuplicateMatchType, DuplicateProcessingResult, BatchError, BatchErrorType,
    MovementType, UserRole
)
from src.airtable_client import AirtableClient
from src.services.stock import StockService
from src.services.duplicate_detection import DuplicateDetectionService

logger = logging.getLogger(__name__)


class BatchDuplicateHandler:
    """Service for handling duplicate detection in batch processing."""
    
    def __init__(self, airtable_client: AirtableClient, stock_service: StockService):
        """Initialize the batch duplicate handler."""
        self.airtable = airtable_client
        self.stock_service = stock_service
        self.duplicate_detection_service = DuplicateDetectionService(airtable_client)
        
        # Similarity thresholds (aligned with DuplicateDetectionService)
        self.exact_match_threshold = 0.95
        self.similar_match_threshold = 0.7  # Same as DuplicateDetectionService
        self.fuzzy_match_threshold = 0.5
        
        # Simple caching for existing items
        self._items_cache = None
        self._cache_timestamp = 0
        self._cache_ttl = 300  # 5 minutes cache TTL
    
    async def identify_duplicates(self, batches: List[BatchInfo]) -> DuplicateAnalysis:
        """
        Identify duplicates in batch items by comparing with existing inventory.
        
        Args:
            batches: List of batch information containing items to check
            
        Returns:
            DuplicateAnalysis with categorized duplicates and non-duplicates
        """
        try:
            logger.info(f"Identifying duplicates in {len(batches)} batches")
            
            # Collect all items from all batches
            all_items = []
            for batch_idx, batch in enumerate(batches):
                for item_idx, item in enumerate(batch.items):
                    all_items.append((item, batch_idx, item_idx))
            
            logger.info(f"Checking {len(all_items)} items for duplicates")
            
            # Get all existing items from inventory
            existing_items = await self._get_all_existing_items()
            logger.info(f"Found {len(existing_items)} existing items in inventory")
            
            # Analyze each item for duplicates
            analysis = DuplicateAnalysis()
            
            for batch_item, batch_number, item_index in all_items:
                best_match = await self._find_best_match(batch_item, existing_items)
                
                if best_match:
                    duplicate_item = DuplicateItem(
                        batch_item=batch_item.model_dump(),
                        existing_item=best_match['item'].model_dump(),
                        similarity_score=best_match['score'],
                        match_type=best_match['type'],
                        batch_number=batch_number,
                        item_index=item_index
                    )
                    
                    analysis.duplicates.append(duplicate_item)
                    
                    # Categorize by match type
                    if best_match['type'] == DuplicateMatchType.EXACT:
                        analysis.exact_matches.append(duplicate_item)
                    elif best_match['type'] == DuplicateMatchType.SIMILAR:
                        analysis.similar_items.append(duplicate_item)
                    else:
                        analysis.similar_items.append(duplicate_item)
                else:
                    analysis.non_duplicates.append(batch_item)
            
            # Update counts
            analysis.total_items = len(all_items)
            analysis.duplicate_count = len(analysis.duplicates)
            analysis.non_duplicate_count = len(analysis.non_duplicates)
            
            logger.info(f"Duplicate analysis complete: {analysis.duplicate_count} duplicates, {analysis.non_duplicate_count} non-duplicates")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error identifying duplicates: {e}")
            # Return empty analysis on error
            return DuplicateAnalysis(
                total_items=0,
                duplicate_count=0,
                non_duplicate_count=0
            )
    
    async def process_non_duplicates(self, non_duplicates: List[BatchItem], 
                                   movement_type: MovementType, user_id: int, user_name: str) -> DuplicateProcessingResult:
        """
        Process non-duplicate items first.
        
        Args:
            non_duplicates: List of non-duplicate batch items
            movement_type: Type of movement (IN/OUT)
            user_id: User ID
            user_name: User name
            
        Returns:
            DuplicateProcessingResult with processing results
        """
        try:
            logger.info(f"Processing {len(non_duplicates)} non-duplicate items")
            
            result = DuplicateProcessingResult()
            
            for item in non_duplicates:
                try:
                    # Create stock movement for non-duplicate item
                    success, message, movement_id = await self._create_stock_movement(
                        item, movement_type, user_id, user_name
                    )
                    
                    if success:
                        result.success_count += 1
                        logger.info(f"Successfully processed non-duplicate item: {item.item_name}")
                    else:
                        result.failure_count += 1
                        error = BatchError(
                            error_type=BatchErrorType.DATABASE,
                            message=f"Failed to process {item.item_name}: {message}",
                            severity="ERROR"
                        )
                        result.processing_errors.append(error)
                        logger.error(f"Failed to process non-duplicate item {item.item_name}: {message}")
                        
                except Exception as e:
                    result.failure_count += 1
                    error = BatchError(
                        error_type=BatchErrorType.DATABASE,
                        message=f"Error processing {item.item_name}: {str(e)}",
                        severity="ERROR"
                    )
                    result.processing_errors.append(error)
                    logger.error(f"Error processing non-duplicate item {item.item_name}: {e}")
            
            logger.info(f"Non-duplicate processing complete: {result.success_count} success, {result.failure_count} failures")
            return result
            
        except Exception as e:
            logger.error(f"Error processing non-duplicates: {e}")
            return DuplicateProcessingResult()
    
    async def process_duplicates(self, duplicates: List[DuplicateItem], 
                               movement_type: MovementType, user_id: int, user_name: str,
                               auto_merge_exact: bool = True, 
                               require_user_confirmation: bool = True) -> DuplicateProcessingResult:
        """
        Process duplicate items with user confirmation workflow.
        
        Args:
            duplicates: List of duplicate items to process
            movement_type: Type of movement (IN/OUT)
            user_id: User ID
            user_name: User name
            auto_merge_exact: Whether to automatically merge exact matches
            
        Returns:
            DuplicateProcessingResult with processing results
        """
        try:
            logger.info(f"Processing {len(duplicates)} duplicate items")
            
            result = DuplicateProcessingResult()
            exact_matches = [d for d in duplicates if d.match_type == DuplicateMatchType.EXACT]
            similar_matches = [d for d in duplicates if d.match_type in [DuplicateMatchType.SIMILAR, DuplicateMatchType.FUZZY]]
            
            # Process exact matches automatically if auto_merge_exact is True
            for duplicate in exact_matches:
                try:
                    if auto_merge_exact:
                        # Auto-merge exact matches
                        merged_item = await self.merge_quantities(
                            duplicate.existing_item, duplicate.batch_item
                        )
                        result.merged_items.append(merged_item)
                        result.processed_duplicates.append(duplicate)
                        result.success_count += 1
                        
                        logger.info(f"Auto-merged exact duplicate: {duplicate.batch_item['item_name']}")
                    else:
                        # Add to pending for user confirmation
                        result.pending_duplicates.append(duplicate)
                        result.requires_user_confirmation = True
                        
                except Exception as e:
                    logger.error(f"Error processing exact duplicate {duplicate.batch_item['item_name']}: {e}")
                    result.failure_count += 1
                    error = BatchError(
                        error_type=BatchErrorType.DATABASE,
                        message=f"Failed to process exact duplicate {duplicate.batch_item['item_name']}: {str(e)}",
                        severity="ERROR"
                    )
                    result.processing_errors.append(error)
            
            # Handle similar matches
            if similar_matches:
                if require_user_confirmation:
                    # Add similar matches to pending for user confirmation
                    result.pending_duplicates.extend(similar_matches)
                    result.requires_user_confirmation = True
                    logger.info(f"Added {len(similar_matches)} similar items to pending confirmation")
                else:
                    # Process similar matches as new items (fallback behavior)
                    for duplicate in similar_matches:
                        try:
                            batch_item_obj = BatchItem(**duplicate.batch_item)
                            success, message, movement_id = await self._create_stock_movement(
                                batch_item_obj, movement_type, user_id, user_name
                            )
                            
                            if success:
                                result.new_items_created.append(duplicate.existing_item)
                                result.processed_duplicates.append(duplicate)
                                result.success_count += 1
                                logger.info(f"Created new item for similar duplicate: {duplicate.batch_item['item_name']}")
                            else:
                                result.failure_count += 1
                                error = BatchError(
                                    error_type=BatchErrorType.DATABASE,
                                    message=f"Failed to process similar duplicate {duplicate.batch_item['item_name']}: {message}",
                                    severity="ERROR"
                                )
                                result.processing_errors.append(error)
                            
                        except Exception as e:
                            result.failure_count += 1
                            error = BatchError(
                                error_type=BatchErrorType.DATABASE,
                                message=f"Error processing duplicate {duplicate.batch_item['item_name']}: {str(e)}",
                                severity="ERROR"
                            )
                            result.processing_errors.append(error)
                            logger.error(f"Error processing duplicate {duplicate.batch_item['item_name']}: {e}")
            
            logger.info(f"Duplicate processing complete: {result.success_count} success, {result.failure_count} failures")
            return result
            
        except Exception as e:
            logger.error(f"Error processing duplicates: {e}")
            return DuplicateProcessingResult()
    
    async def process_user_confirmation(self, duplicate: DuplicateItem, action: str, 
                                      movement_type: MovementType, user_id: int, user_name: str) -> DuplicateProcessingResult:
        """
        Process a user's confirmation decision for a specific duplicate item.
        
        Args:
            duplicate: The duplicate item to process
            action: The action taken (confirm, cancel, merge, create_new)
            movement_type: Type of movement (IN/OUT)
            user_id: User ID
            user_name: User name
            
        Returns:
            DuplicateProcessingResult with processing results
        """
        try:
            result = DuplicateProcessingResult()
            
            if action == "confirm" or action == "merge_quantities":
                # Merge quantities with existing item
                merged_item = await self.merge_quantities(
                    duplicate.existing_item, duplicate.batch_item
                )
                result.merged_items.append(merged_item)
                result.processed_duplicates.append(duplicate)
                result.success_count += 1
                
                logger.info(f"User confirmed merge for duplicate: {duplicate.batch_item['item_name']}")
                
            elif action == "create_new":
                # Create as new item
                batch_item_obj = BatchItem(**duplicate.batch_item)
                success, message, movement_id = await self._create_stock_movement(
                    batch_item_obj, movement_type, user_id, user_name
                )
                
                if success:
                    result.new_items_created.append(duplicate.existing_item)
                    result.processed_duplicates.append(duplicate)
                    result.success_count += 1
                    logger.info(f"User created new item for duplicate: {duplicate.batch_item['item_name']}")
                else:
                    result.failure_count += 1
                    error = BatchError(
                        error_type=BatchErrorType.DATABASE,
                        message=f"Failed to create new item for duplicate {duplicate.batch_item['item_name']}: {message}",
                        severity="ERROR"
                    )
                    result.processing_errors.append(error)
                    
            elif action == "cancel":
                # Reject the duplicate
                result.rejected_duplicates.append(duplicate)
                result.failure_count += 1
                logger.info(f"User cancelled duplicate: {duplicate.batch_item['item_name']}")
                
            else:
                logger.warning(f"Unknown confirmation action: {action}")
                result.failure_count += 1
                
            return result
            
        except Exception as e:
            logger.error(f"Error processing user confirmation: {e}")
            result = DuplicateProcessingResult()
            result.failure_count += 1
            result.processing_errors.append(BatchError(
                error_type=BatchErrorType.DATABASE,
                message=f"Error processing confirmation: {str(e)}",
                severity="ERROR"
            ))
            return result
    
    async def validate_stock_levels(self, duplicates: List[DuplicateItem], movement_type: MovementType) -> Dict[str, Any]:
        """
        Validate stock levels for OUT movements with duplicates.
        
        Args:
            duplicates: List of duplicate items
            movement_type: Type of movement (IN/OUT)
            
        Returns:
            Dictionary with validation results
        """
        try:
            if movement_type != MovementType.OUT:
                return {"valid": True, "warnings": []}
            
            validation_results = {
                "valid": True,
                "warnings": [],
                "insufficient_stock": []
            }
            
            for duplicate in duplicates:
                existing_item = duplicate.existing_item
                batch_item = duplicate.batch_item
                
                current_stock = existing_item.get('on_hand', 0)
                requested_quantity = batch_item.get('quantity', 0)
                
                if current_stock < requested_quantity:
                    validation_results["valid"] = False
                    validation_results["insufficient_stock"].append({
                        "item_name": batch_item['item_name'],
                        "current_stock": current_stock,
                        "requested_quantity": requested_quantity,
                        "shortfall": requested_quantity - current_stock
                    })
                    
                    validation_results["warnings"].append(
                        f"⚠️ Insufficient stock for {batch_item['item_name']}: "
                        f"Need {requested_quantity}, have {current_stock}"
                    )
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating stock levels: {e}")
            return {"valid": False, "warnings": [f"Error validating stock levels: {str(e)}"]}
    
    async def handle_project_conflicts(self, duplicate: DuplicateItem, new_project: str) -> Dict[str, Any]:
        """
        Handle project conflicts by appending new project to existing item.
        
        Args:
            duplicate: The duplicate item with project conflict
            new_project: The new project name to append
            
        Returns:
            Dictionary with conflict resolution results
        """
        try:
            existing_item = duplicate.existing_item
            current_projects = existing_item.get('project', '')
            
            # Append new project if not already present
            if new_project not in current_projects:
                updated_projects = f"{current_projects}, {new_project}".strip(", ")
                
                # Update the item in Airtable
                updated_item = existing_item.copy()
                updated_item['project'] = updated_projects
                
                success = await self.airtable.update_item(updated_item)
                
                if success:
                    logger.info(f"Updated project field for {duplicate.batch_item['item_name']}: {updated_projects}")
                    return {
                        "success": True,
                        "updated_projects": updated_projects,
                        "message": f"Project field updated: {updated_projects}"
                    }
                else:
                    return {
                        "success": False,
                        "message": "Failed to update project field in database"
                    }
            else:
                return {
                    "success": True,
                    "message": f"Project '{new_project}' already exists in item"
                }
                
        except Exception as e:
            logger.error(f"Error handling project conflict: {e}")
            return {
                "success": False,
                "message": f"Error handling project conflict: {str(e)}"
            }
    
    async def merge_quantities(self, existing_item: Dict[str, Any], new_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge quantities for exact duplicate matches.
        
        Args:
            existing_item: Existing item in inventory
            new_item: New item from batch
            
        Returns:
            Updated item with merged quantities
        """
        try:
            # Calculate new quantity
            existing_quantity = float(existing_item['on_hand'])
            new_quantity = float(new_item['quantity'])
            merged_quantity = existing_quantity + new_quantity
            
            # Update the existing item
            updated_item = existing_item.copy()
            updated_item['on_hand'] = merged_quantity
            
            # Update in database using update_item_stock
            quantity_change = float(new_item['quantity'])
            success = await self.airtable.update_item_stock(existing_item['name'], quantity_change)
            
            if not success:
                raise Exception("Failed to update item stock in database")
            
            # Also create the movement record
            try:
                # Create a BatchItem object for the movement creation
                batch_item = BatchItem(
                    item_name=existing_item['name'],
                    quantity=new_quantity,
                    unit=new_item.get('unit', 'pieces')
                )
                
                # Create the stock movement record
                movement_success, movement_message, movement_id = await self._create_stock_movement(
                    batch_item, MovementType.IN, 0, "System"  # Use system as user for merged items
                )
                
                if not movement_success:
                    logger.warning(f"Failed to create movement record for {existing_item['name']}: {movement_message}")
                else:
                    logger.info(f"Created movement record for {existing_item['name']}: {movement_id}")
                    
            except Exception as e:
                logger.warning(f"Error creating movement record for {existing_item['name']}: {e}")
            
            logger.info(f"Merged quantities for {existing_item['name']}: {existing_quantity} + {new_quantity} = {merged_quantity}")
            
            return updated_item
            
        except Exception as e:
            logger.error(f"Error merging quantities for {existing_item['name']}: {e}")
            raise
    
    async def _get_all_existing_items(self) -> List[Item]:
        """Get all existing items from inventory with caching."""
        try:
            current_time = time.time()
            
            # Check if cache is valid
            if (self._items_cache is not None and 
                current_time - self._cache_timestamp < self._cache_ttl):
                logger.debug("Using cached items for duplicate detection")
                return self._items_cache
            
            # Fetch fresh items from database
            logger.debug("Fetching fresh items from database for duplicate detection")
            items = await self.airtable.get_all_items()
            
            # Update cache
            self._items_cache = items
            self._cache_timestamp = current_time
            
            logger.info(f"Cached {len(items)} items for duplicate detection")
            return items
            
        except Exception as e:
            logger.error(f"Error getting existing items: {e}")
            # Return cached items if available, even if expired
            if self._items_cache is not None:
                logger.warning("Using expired cache due to database error")
                return self._items_cache
            return []
    
    async def _find_best_match(self, batch_item: BatchItem, existing_items: List[Item]) -> Optional[Dict]:
        """
        Find the best match for a batch item among existing items.
        
        Args:
            batch_item: Item from batch to match
            existing_items: List of existing items to search
            
        Returns:
            Dictionary with match details or None if no good match
        """
        best_match = None
        best_score = 0.0
        
        for existing_item in existing_items:
            # Calculate similarity score
            score = self._calculate_similarity(batch_item.item_name, existing_item.name)
            
            if score > best_score:
                best_score = score
                best_match = {
                    'item': existing_item,
                    'score': score,
                    'type': self._determine_match_type(score)
                }
        
        # Only return matches above the fuzzy threshold
        if best_score >= self.fuzzy_match_threshold:
            return best_match
        
        return None
    
    def _calculate_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity score between two item names using the existing duplicate detection service."""
        try:
            # Use the existing duplicate detection service's enhanced algorithm
            return self.duplicate_detection_service._calculate_duplicate_similarity(name1, name2)
        except Exception as e:
            logger.error(f"Error calculating similarity using duplicate detection service: {e}")
            # Fallback to basic similarity if the service fails
            norm1 = name1.lower().strip()
            norm2 = name2.lower().strip()
            return SequenceMatcher(None, norm1, norm2).ratio()
    
    def _determine_match_type(self, score: float) -> DuplicateMatchType:
        """Determine match type based on similarity score."""
        if score >= self.exact_match_threshold:
            return DuplicateMatchType.EXACT
        elif score >= self.similar_match_threshold:
            return DuplicateMatchType.SIMILAR
        else:
            return DuplicateMatchType.FUZZY
    
    async def _create_stock_movement(self, batch_item: BatchItem, movement_type, 
                                   user_id: int, user_name: str) -> Tuple[bool, str, Optional[str]]:
        """Create a stock movement for a batch item."""
        try:
            # This would integrate with the existing stock service
            # For now, we'll simulate the creation
            movement_type_str = movement_type.value if hasattr(movement_type, 'value') else str(movement_type)
            if movement_type_str == "In":
                success, message, old_qty, new_qty = await self.stock_service.stock_in(
                    item_name=batch_item.item_name,
                    quantity=batch_item.quantity,
                    unit=batch_item.unit,
                    location="not described",  # Add required location parameter
                    note="Batch processing",   # Add required note parameter
                    user_id=user_id,
                    user_name=user_name
                )
                # stock_in doesn't return movement_id, generate one
                movement_id = f"movement_{batch_item.item_name}_{user_id}" if success else None
            else:  # OUT
                success, message, movement_id, old_qty, new_qty = await self.stock_service.stock_out(
                    item_name=batch_item.item_name,
                    quantity=batch_item.quantity,
                    unit=batch_item.unit,
                    location="external",       # Add required location parameter
                    note="Batch processing",   # Add required note parameter
                    user_id=user_id,
                    user_name=user_name,
                    user_role=UserRole.STAFF   # Add required user_role parameter
                )
                # stock_out returns movement_id, use it or generate one if None
                if success and not movement_id:
                    movement_id = f"movement_{batch_item.item_name}_{user_id}"
            
            return success, message, movement_id
            
        except Exception as e:
            logger.error(f"Error creating stock movement: {e}")
            return False, str(e), None
