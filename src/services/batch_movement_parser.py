"""Batch Movement Parser Service for the Construction Inventory Bot."""

import re
import logging
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime

from schemas import BatchInfo, BatchItem, BatchParseResult, MovementType, BatchFormat

logger = logging.getLogger(__name__)


class BatchMovementParser:
    """Service for parsing batch movement commands."""
    
    def __init__(self):
        """Initialize the batch movement parser."""
        self.batch_separator_pattern = r'-batch\s+(\d+)-'
        self.parameter_pattern = r'(project|driver|to|from):\s*([^,\n]+)'
        
    def parse_batch_command(self, command_text: str, movement_type: MovementType) -> BatchParseResult:
        """
        Parse a batch command into structured data.
        
        Args:
            command_text: The raw command text
            movement_type: Type of movement (IN or OUT)
            
        Returns:
            BatchParseResult with parsed batches and metadata
        """
        try:
            # Clean up the command text
            command_text = command_text.strip()
            
            # Split by batch separators
            batch_sections = re.split(self.batch_separator_pattern, command_text)
            
            if len(batch_sections) < 3:
                # No batch separators found, treat as single batch
                return self._parse_single_batch_command(command_text, movement_type)
            
            batches = []
            errors = []
            total_items = 0
            
            # Process each batch (skip first empty element)
            for i in range(1, len(batch_sections), 2):
                try:
                    # Try to parse batch number, handle non-numeric gracefully
                    try:
                        batch_num = int(batch_sections[i])
                    except ValueError:
                        batch_num = len(batches) + 1  # Use sequential numbering
                        errors.append(f"Invalid batch number '{batch_sections[i]}', using {batch_num}")
                    
                    batch_content = batch_sections[i + 1].strip()
                    
                    if not batch_content:
                        # Create empty batch for tracking
                        empty_batch = BatchInfo(
                            batch_number=batch_num,
                            project="not described",
                            driver="not described",
                            to_location="external" if movement_type == MovementType.OUT else None,
                            from_location="not described" if movement_type == MovementType.IN else None,
                            items=[]
                        )
                        batches.append(empty_batch)
                        errors.append(f"Batch {batch_num}: Empty batch content")
                        continue
                    
                    batch = self._parse_single_batch(batch_content, batch_num, movement_type)
                    batches.append(batch)
                    total_items += len(batch.items)
                    
                except Exception as e:
                    error_msg = f"Batch {batch_num if 'batch_num' in locals() else 'unknown'}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"Error parsing batch: {e}")
            
            return BatchParseResult(
                format=BatchFormat.MIXED,
                movements=[],  # Will be populated later during processing
                total_entries=len(batches),
                valid_entries=len([b for b in batches if b.items]),
                errors=errors,
                is_valid=len(errors) == 0,
                batches=batches,
                total_items=total_items
            )
            
        except Exception as e:
            logger.error(f"Error parsing batch command: {e}")
            return BatchParseResult(
                format=BatchFormat.MIXED,
                movements=[],
                total_entries=0,
                valid_entries=0,
                errors=[f"Failed to parse command: {str(e)}"],
                is_valid=False,
                batches=[],
                total_items=0
            )
    
    def _parse_single_batch_command(self, command_text: str, movement_type: MovementType) -> BatchParseResult:
        """Parse a command without batch separators as a single batch."""
        try:
            batch = self._parse_single_batch(command_text, 1, movement_type)
            return BatchParseResult(
                format=BatchFormat.SINGLE,
                movements=[],
                total_entries=1,
                valid_entries=1 if batch.items else 0,
                errors=[],
                is_valid=True,
                batches=[batch],
                total_items=len(batch.items)
            )
        except Exception as e:
            return BatchParseResult(
                format=BatchFormat.SINGLE,
                movements=[],
                total_entries=0,
                valid_entries=0,
                errors=[f"Failed to parse single batch: {str(e)}"],
                is_valid=False,
                batches=[],
                total_items=0
            )
    
    def _parse_single_batch(self, batch_content: str, batch_number: int, movement_type: MovementType) -> BatchInfo:
        """
        Parse a single batch section.
        
        Args:
            batch_content: Content of the batch
            batch_number: Number of the batch
            movement_type: Type of movement (IN or OUT)
            
        Returns:
            BatchInfo with parsed data
        """
        # Split into header and items
        lines = [line.strip() for line in batch_content.split('\n') if line.strip()]
        
        if not lines:
            raise ValueError("Empty batch content")
        
        # First line(s) contain metadata
        metadata_lines = []
        item_lines = []
        
        # Find where metadata ends and items begin
        for i, line in enumerate(lines):
            if self._is_item_line(line):
                item_lines = lines[i:]
                break
            else:
                metadata_lines.append(line)
        
        # Parse metadata
        metadata = self._parse_batch_metadata('\n'.join(metadata_lines), movement_type)
        
        # Parse items
        items = self._parse_batch_items('\n'.join(item_lines))
        
        return BatchInfo(
            batch_number=batch_number,
            project=metadata.get('project', 'not described'),
            driver=metadata.get('driver', 'not described'),
            to_location=metadata.get('to', 'external' if movement_type == MovementType.OUT else None),
            from_location=metadata.get('from', 'not described' if movement_type == MovementType.IN else None),
            items=items
        )
    
    def _parse_batch_metadata(self, metadata_text: str, movement_type: MovementType) -> Dict[str, str]:
        """
        Parse batch metadata (project, driver, to/from locations).
        
        Args:
            metadata_text: Text containing metadata
            movement_type: Type of movement (IN or OUT)
            
        Returns:
            Dictionary of parsed metadata
        """
        metadata = {}
        
        # Use a more sophisticated approach to handle commas in values
        # Look for each parameter with a more flexible pattern that trims trailing commas
        param_patterns = [
            (r'project:\s*(.+?)(?=\s*(?:driver|to|from):|$)', 'project'),
            (r'driver:\s*(.+?)(?=\s*(?:project|to|from):|$)', 'driver'),
            (r'to:\s*(.+?)(?=\s*(?:project|driver|from):|$)', 'to'),
            (r'from:\s*(.+?)(?=\s*(?:project|driver|to):|$)', 'from')
        ]
        
        # Try each pattern
        for pattern, param_name in param_patterns:
            match = re.search(pattern, metadata_text, re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                # Remove trailing commas and whitespace
                value = value.rstrip(',').strip()
                
                # Skip empty values
                if not value:
                    continue
                    
                if param_name == 'project':
                    metadata['project'] = value
                elif param_name == 'driver':
                    metadata['driver'] = value
                elif param_name == 'to' and movement_type == MovementType.OUT:
                    metadata['to'] = value
                elif param_name == 'from' and movement_type == MovementType.IN:
                    metadata['from'] = value
        
        # If the above approach doesn't work, try a simpler comma-splitting approach
        if not metadata:
            # Split by commas and process each part
            parts = [part.strip() for part in metadata_text.split(',')]
            for part in parts:
                if ':' in part:
                    key_value = part.split(':', 1)
                    if len(key_value) == 2:
                        key = key_value[0].strip().lower()
                        value = key_value[1].strip()
                        if key == 'project':
                            metadata['project'] = value
                        elif key == 'driver':
                            metadata['driver'] = value
                        elif key == 'to' and movement_type == MovementType.OUT:
                            metadata['to'] = value
                        elif key == 'from' and movement_type == MovementType.IN:
                            metadata['from'] = value
        
        return metadata
    
    def _parse_batch_items(self, items_text: str) -> List[BatchItem]:
        """
        Parse items from batch content.
        
        Args:
            items_text: Text containing item lines
            
        Returns:
            List of parsed BatchItem objects
        """
        items = []
        lines = [line.strip() for line in items_text.split('\n') if line.strip()]
        
        for line in lines:
            if not self._is_item_line(line):
                continue
                
            try:
                item = self._parse_item_line(line)
                if item:
                    items.append(item)
            except Exception as e:
                logger.warning(f"Failed to parse item line '{line}': {e}")
                continue
        
        return items
    
    def _parse_item_line(self, line: str) -> Optional[BatchItem]:
        """
        Parse a single item line.
        
        Args:
            line: Item line to parse
            
        Returns:
            Parsed BatchItem or None if parsing fails
        """
        # Pattern to match: item_name, quantity [unit]
        # Examples: "Solar floodlight panel FS-SFL800, 4", "Cable 2.5sqmm black 100m, 1"
        pattern = r'^(.+?),\s*(\d+(?:\.\d+)?)\s*(.*)$'
        match = re.match(pattern, line.strip())
        
        if not match:
            return None
        
        item_name = match.group(1).strip()
        quantity = float(match.group(2))
        unit = match.group(3).strip() if match.group(3) else None
        
        return BatchItem(
            item_name=item_name,
            quantity=quantity,
            unit=unit
        )
    
    def _is_item_line(self, line: str) -> bool:
        """
        Check if a line contains item information.
        
        Args:
            line: Line to check
            
        Returns:
            True if line appears to contain item information
        """
        # Item lines typically contain a comma followed by a number
        return ',' in line and re.search(r'\d+(?:\.\d+)?', line)
    
    def apply_smart_defaults(self, batch: BatchInfo, movement_type: MovementType) -> BatchInfo:
        """
        Apply smart defaults to batch metadata.
        
        Args:
            batch: Batch to apply defaults to
            movement_type: Type of movement (IN or OUT)
            
        Returns:
            Batch with defaults applied
        """
        # Apply defaults if not specified or empty/whitespace
        if not batch.project or not batch.project.strip() or batch.project.strip() == "not described":
            batch.project = "not described"
        
        if not batch.driver or not batch.driver.strip() or batch.driver.strip() == "not described":
            batch.driver = "not described"
        
        if movement_type == MovementType.OUT:
            if not batch.to_location or not batch.to_location.strip() or batch.to_location.strip() == "external":
                batch.to_location = "external"
            # Clear from_location for OUT movements
            batch.from_location = None
        else:
            # MovementType.IN
            if not batch.from_location or not batch.from_location.strip() or batch.from_location.strip() == "not described":
                batch.from_location = "not described"
            # Clear to_location for IN movements
            batch.to_location = None
        
        return batch
    
    def validate_batch(self, batch: BatchInfo) -> List[str]:
        """
        Validate a batch for required fields and data integrity.
        
        Args:
            batch: Batch to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check if batch has items
        if not batch.items:
            errors.append(f"Batch {batch.batch_number}: No items found")
        
        # Validate each item
        for i, item in enumerate(batch.items):
            if not item.item_name or not item.item_name.strip():
                errors.append(f"Batch {batch.batch_number}, Item {i+1}: Item name is required")
            
            if item.quantity <= 0:
                errors.append(f"Batch {batch.batch_number}, Item {i+1}: Quantity must be greater than 0")
        
        return errors
    
    def generate_batch_summary(self, batches: List[BatchInfo]) -> str:
        """
        Generate a summary of batches for user confirmation.
        
        Args:
            batches: List of batches to summarize
            
        Returns:
            Formatted summary string
        """
        if not batches:
            return "No batches found"
        
        summary_lines = [f"Found {len(batches)} batch(es):"]
        
        for batch in batches:
            project = batch.project or "not described"
            driver = batch.driver or "not described"
            to_location = batch.to_location or "external"
            from_location = batch.from_location or "not described"
            
            if batch.to_location:
                summary_lines.append(f"  Batch {batch.batch_number}: {len(batch.items)} items to {to_location} (Project: {project}, Driver: {driver})")
            else:
                summary_lines.append(f"  Batch {batch.batch_number}: {len(batch.items)} items from {from_location} (Project: {project}, Driver: {driver})")
        
        total_items = sum(len(batch.items) for batch in batches)
        summary_lines.append(f"\nTotal items: {total_items}")
        
        return "\n".join(summary_lines)
