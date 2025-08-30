"""Batch Stock Movement Service for handling batch operations and validation."""

import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from schemas import (
    StockMovement, MovementType, MovementStatus, 
    BatchResult, BatchError, BatchErrorType, Item
)
from services.smart_field_populator import smart_field_populator
from services.enhanced_stock_parser import InCommandParseResult, OutCommandParseResult

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of batch validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    items_to_create: List[Dict[str, Any]]  # For IN movements
    existing_items: List[Item]  # For OUT movements


class BatchStockMovementService:
    """Service for handling batch stock movements with validation."""
    
    def __init__(self):
        """Initialize the batch stock movement service."""
        self.max_batch_size = 20
        self.max_quantity_per_item = 10000  # Reasonable upper limit
    
    def process_batch_in(self, parse_result: InCommandParseResult, 
                        user_id: int, user_name: str, chat_id: int) -> BatchResult:
        """Process batch of items coming in."""
        try:
            logger.info(f"Processing batch IN with {len(parse_result.items)} items")
            
            # Generate batch ID
            batch_id = self._generate_batch_id()
            
            # Validate batch
            validation_result = self._validate_batch_in(parse_result)
            if not validation_result.is_valid:
                return self._create_batch_result_with_errors(
                    parse_result.items, validation_result.errors, batch_id
                )
            
            # Create stock movements
            movements = self._create_stock_movements_in(
                parse_result, validation_result, user_id, user_name, batch_id
            )
            
            # Prepare batch result
            batch_result = BatchResult(
                total_entries=len(parse_result.items),
                successful_entries=len(movements),
                failed_entries=0,
                success_rate=1.0,
                movements_created=[mov.id for mov in movements if mov.id],
                errors=[],
                rollback_performed=False,
                processing_time_seconds=None,
                summary_message=self._generate_in_summary(parse_result, movements),
                global_parameters={
                    'project': parse_result.project or "Default Project",
                    'driver': parse_result.driver or "Default Driver",
                    'from_location': parse_result.from_location or "Default Source",
                    'batch_id': batch_id
                }
            )
            
            logger.info(f"Batch IN processed successfully: {batch_id}")
            return batch_result
            
        except Exception as e:
            logger.error(f"Error processing batch IN: {e}")
            return self._create_batch_result_with_errors(
                parse_result.items, [f"Processing error: {str(e)}"], 
                self._generate_batch_id()
            )
    
    def process_batch_out(self, parse_result: OutCommandParseResult, 
                         user_id: int, user_name: str, chat_id: int) -> BatchResult:
        """Process batch of items going out."""
        try:
            logger.info(f"Processing batch OUT with {len(parse_result.items)} items")
            
            # Generate batch ID
            batch_id = self._generate_batch_id()
            
            # Validate batch
            validation_result = self._validate_batch_out(parse_result)
            if not validation_result.is_valid:
                return self._create_batch_result_with_errors(
                    parse_result.items, validation_result.errors, batch_id
                )
            
            # Create stock movements
            movements = self._create_stock_movements_out(
                parse_result, validation_result, user_id, user_name, batch_id
            )
            
            # Prepare batch result
            batch_result = BatchResult(
                total_entries=len(parse_result.items),
                successful_entries=len(movements),
                failed_entries=0,
                success_rate=1.0,
                movements_created=[mov.id for mov in movements if mov.id],
                errors=[],
                rollback_performed=False,
                processing_time_seconds=None,
                summary_message=self._generate_out_summary(parse_result, movements),
                global_parameters={
                    'project': parse_result.project or "Default Project",
                    'driver': parse_result.driver or "Default Driver",
                    'to_location': parse_result.to_location or "Default Destination",
                    'batch_id': batch_id
                }
            )
            
            logger.info(f"Batch OUT processed successfully: {batch_id}")
            return batch_result
            
        except Exception as e:
            logger.error(f"Error processing batch OUT: {e}")
            return self._create_batch_result_with_errors(
                parse_result.items, [f"Processing error: {str(e)}"], 
                self._generate_batch_id()
            )
    
    def validate_batch(self, items: List[Dict[str, Any]], 
                      movement_type: MovementType) -> ValidationResult:
        """Validate batch before processing."""
        errors = []
        warnings = []
        items_to_create = []
        existing_items = []
        
        # Check batch size
        if len(items) > self.max_batch_size:
            errors.append(f"Batch size {len(items)} exceeds maximum limit of {self.max_batch_size}")
            return ValidationResult(False, errors, warnings, [], [])
        
        # Validate each item
        for i, item in enumerate(items):
            item_errors, item_warnings = self._validate_single_item(item, i + 1)
            errors.extend(item_errors)
            warnings.extend(item_warnings)
            
            # For IN movements, track items that need to be created
            if movement_type == MovementType.IN:
                items_to_create.append(item)
            # For OUT movements, we'd need to check if items exist
            # (This would require database integration)
        
        # Check for critical errors
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            items_to_create=items_to_create,
            existing_items=existing_items
        )
    
    def _validate_batch_in(self, parse_result: InCommandParseResult) -> ValidationResult:
        """Validate batch IN specific requirements."""
        errors = []
        warnings = []
        items_to_create = []
        
        # Check required fields
        if not parse_result.project:
            warnings.append("Project not specified - using default")
        
        if not parse_result.driver:
            warnings.append("Driver not specified - using default")
        
        # Validate items
        for i, item in enumerate(parse_result.items):
            item_errors, item_warnings = self._validate_single_item(item, i + 1)
            errors.extend(item_errors)
            warnings.extend(item_warnings)
            items_to_create.append(item)
        
        # Check for critical errors
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            items_to_create=items_to_create,
            existing_items=[]
        )
    
    def _validate_batch_out(self, parse_result: OutCommandParseResult) -> ValidationResult:
        """Validate batch OUT specific requirements."""
        errors = []
        warnings = []
        items_to_create = []
        
        # Check required fields
        if not parse_result.to_location:
            errors.append("Destination location (to:) is required for OUT commands")
        
        if not parse_result.project:
            warnings.append("Project not specified - using default")
        
        if not parse_result.driver:
            warnings.append("Driver not specified - using default")
        
        # Validate items
        for i, item in enumerate(parse_result.items):
            item_errors, item_warnings = self._validate_single_item(item, i + 1)
            errors.extend(item_errors)
            warnings.extend(item_warnings)
            # For OUT, items should already exist (would need DB check)
        
        # Check for critical errors
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            items_to_create=[],
            existing_items=[]
        )
    
    def _validate_single_item(self, item: Dict[str, Any], item_index: int) -> Tuple[List[str], List[str]]:
        """Validate a single item in the batch."""
        errors = []
        warnings = []
        
        # Check required fields
        if not item.get('name'):
            errors.append(f"Item {item_index}: Missing item name")
        
        if item.get('quantity') is None:
            errors.append(f"Item {item_index}: Missing quantity")
        elif not isinstance(item['quantity'], (int, float)) or item['quantity'] <= 0:
            errors.append(f"Item {item_index}: Invalid quantity '{item['quantity']}'")
        elif item['quantity'] > self.max_quantity_per_item:
            errors.append(f"Item {item_index}: Quantity {item['quantity']} exceeds maximum limit of {self.max_quantity_per_item}")
        
        # Check unit
        if not item.get('unit'):
            warnings.append(f"Item {item_index}: No unit specified - will use smart inference")
        
        # Check for reasonable item names
        if item.get('name') and len(item['name']) > 200:
            warnings.append(f"Item {item_index}: Item name is very long ({len(item['name'])} characters)")
        
        return errors, warnings
    
    def _create_stock_movements_in(self, parse_result: InCommandParseResult, 
                                 validation_result: ValidationResult, 
                                 user_id: int, user_name: str, 
                                 batch_id: str) -> List[StockMovement]:
        """Create stock movements for IN batch."""
        movements = []
        
        for item in validation_result.items_to_create:
            # Populate item fields using smart field populator
            populated_item = smart_field_populator.populate_item_fields(item)
            
            # Determine locations
            from_location, to_location = smart_field_populator.determine_locations(
                MovementType.IN, None, parse_result.from_location
            )
            
            # Create stock movement
            movement = StockMovement(
                item_name=populated_item['name'],
                movement_type=MovementType.IN,
                quantity=populated_item['quantity'],
                unit=populated_item['unit'],
                signed_base_quantity=populated_item['quantity'],  # Simplified for now
                unit_size=populated_item.get('unit_size'),
                unit_type=populated_item.get('unit_type'),
                location=to_location,
                note=populated_item.get('note'),
                status=MovementStatus.REQUESTED,
                user_id=str(user_id),
                user_name=user_name,
                timestamp=datetime.now(),
                reason="Restocking",
                source="Telegram",
                driver_name=parse_result.driver,
                from_location=from_location,
                project=parse_result.project,
                batch_id=batch_id
            )
            
            movements.append(movement)
        
        return movements
    
    def _create_stock_movements_out(self, parse_result: OutCommandParseResult, 
                                  validation_result: ValidationResult, 
                                  user_id: int, user_name: str, 
                                  batch_id: str) -> List[StockMovement]:
        """Create stock movements for OUT batch."""
        movements = []
        
        for item in parse_result.items:
            # Populate item fields using smart field populator
            populated_item = smart_field_populator.populate_item_fields(item)
            
            # Determine locations
            from_location, to_location = smart_field_populator.determine_locations(
                MovementType.OUT, None, parse_result.to_location
            )
            
            # Create stock movement
            movement = StockMovement(
                item_name=populated_item['name'],
                movement_type=MovementType.OUT,
                quantity=populated_item['quantity'],
                unit=populated_item['unit'],
                signed_base_quantity=-populated_item['quantity'],  # Negative for OUT
                unit_size=populated_item.get('unit_size'),
                unit_type=populated_item.get('unit_type'),
                location=from_location,
                note=populated_item.get('note'),
                status=MovementStatus.REQUESTED,
                user_id=str(user_id),
                user_name=user_name,
                timestamp=datetime.now(),
                reason="Required",
                source="Telegram",
                driver_name=parse_result.driver,
                from_location=from_location,
                to_location=to_location,
                project=parse_result.project,
                batch_id=batch_id
            )
            
            movements.append(movement)
        
        return movements
    
    def _generate_batch_id(self) -> str:
        """Generate a unique batch ID."""
        return f"BATCH_{uuid.uuid4().hex[:8].upper()}_{int(datetime.now().timestamp())}"
    
    def _create_batch_result_with_errors(self, items: List[Dict[str, Any]], 
                                       errors: List[str], batch_id: str) -> BatchResult:
        """Create a batch result with errors."""
        return BatchResult(
            total_entries=len(items),
            successful_entries=0,
            failed_entries=len(items),
            success_rate=0.0,
            movements_created=[],
            errors=[BatchError(
                error_type=BatchErrorType.VALIDATION,
                message=error,
                severity="ERROR"
            ) for error in errors],
            rollback_performed=False,
            processing_time_seconds=None,
            summary_message=f"Batch processing failed: {'; '.join(errors)}",
            global_parameters={}
        )
    
    def _generate_in_summary(self, parse_result: InCommandParseResult, 
                           movements: List[StockMovement]) -> str:
        """Generate summary message for IN batch."""
        total_items = len(movements)
        project = parse_result.project or "Default Project"
        driver = parse_result.driver or "Default Driver"
        from_location = parse_result.from_location or "Unknown Source"
        
        summary = f"✅ Batch IN processed successfully!\n\n"
        summary += f"📦 **Items Added:** {total_items}\n"
        summary += f"📋 **Project:** {project}\n"
        summary += f"🚗 **Driver:** {driver}\n"
        summary += f"📍 **From:** {from_location}\n"
        summary += f"🏢 **To:** Warehouse\n\n"
        summary += f"All items have been submitted for approval."
        
        return summary
    
    def _generate_out_summary(self, parse_result: OutCommandParseResult, 
                            movements: List[StockMovement]) -> str:
        """Generate summary message for OUT batch."""
        total_items = len(movements)
        project = parse_result.project or "Default Project"
        driver = parse_result.driver or "Default Driver"
        to_location = parse_result.to_location or "Unknown Destination"
        
        summary = f"✅ Batch OUT processed successfully!\n\n"
        summary += f"📦 **Items Issued:** {total_items}\n"
        summary += f"📋 **Project:** {project}\n"
        summary += f"🚗 **Driver:** {driver}\n"
        summary += f"🏢 **From:** Warehouse\n"
        summary += f"📍 **To:** {to_location}\n\n"
        summary += f"All items have been submitted for approval."
        
        return summary


# Create a singleton instance
batch_stock_movement_service = BatchStockMovementService()
