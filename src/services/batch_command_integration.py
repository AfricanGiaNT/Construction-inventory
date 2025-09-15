"""Integration service for batch movement commands."""

import logging
from typing import Dict, Any

from src.services.batch_movement_processor import BatchMovementProcessor
from src.schemas import MovementType

logger = logging.getLogger(__name__)


class BatchCommandIntegration:
    """Integration service for batch movement commands with Telegram."""
    
    def __init__(self, batch_processor: BatchMovementProcessor):
        """Initialize the batch command integration."""
        self.batch_processor = batch_processor
    
    async def process_in_command(self, command_text: str, user_id: int, user_name: str) -> Dict[str, Any]:
        """
        Process a /in command using the new batch processor.
        
        Args:
            command_text: The command text after /in
            user_id: User ID
            user_name: User name
            
        Returns:
            Dictionary with processing results
        """
        try:
            logger.info(f"Processing /in command: {command_text[:100]}...")
            
            # Process the command using the batch processor
            result = await self.batch_processor.process_batch_command(
                command_text, MovementType.IN, user_id, user_name
            )
            
            # Format the response
            if result.success_rate == 100.0:
                return {
                    "status": "success",
                    "message": result.summary_message,
                    "details": {
                        "total_items": result.total_entries,
                        "successful_items": result.successful_entries,
                        "processing_time": result.processing_time_seconds
                    }
                }
            elif result.success_rate == 0.0:
                return {
                    "status": "error",
                    "message": result.summary_message,
                    "errors": [error.message for error in result.errors],
                    "details": {
                        "total_items": result.total_entries,
                        "successful_items": result.successful_entries,
                        "failed_items": result.failed_entries,
                        "processing_time": result.processing_time_seconds
                    }
                }
            else:
                return {
                    "status": "partial_success",
                    "message": result.summary_message,
                    "errors": [error.message for error in result.errors],
                    "details": {
                        "total_items": result.total_entries,
                        "successful_items": result.successful_entries,
                        "failed_items": result.failed_entries,
                        "success_rate": result.success_rate,
                        "processing_time": result.processing_time_seconds
                    }
                }
                
        except Exception as e:
            logger.error(f"Error processing /in command: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
                "errors": [str(e)]
            }
    
    async def process_out_command(self, command_text: str, user_id: int, user_name: str) -> Dict[str, Any]:
        """
        Process a /out command using the new batch processor.
        
        Args:
            command_text: The command text after /out
            user_id: User ID
            user_name: User name
            
        Returns:
            Dictionary with processing results
        """
        try:
            logger.info(f"Processing /out command: {command_text[:100]}...")
            
            # Process the command using the batch processor
            result = await self.batch_processor.process_batch_command(
                command_text, MovementType.OUT, user_id, user_name
            )
            
            # Format the response
            if result.success_rate == 100.0:
                return {
                    "status": "success",
                    "message": result.summary_message,
                    "details": {
                        "total_items": result.total_entries,
                        "successful_items": result.successful_entries,
                        "processing_time": result.processing_time_seconds
                    }
                }
            elif result.success_rate == 0.0:
                return {
                    "status": "error",
                    "message": result.summary_message,
                    "errors": [error.message for error in result.errors],
                    "details": {
                        "total_items": result.total_entries,
                        "successful_items": result.successful_entries,
                        "failed_items": result.failed_entries,
                        "processing_time": result.processing_time_seconds
                    }
                }
            else:
                return {
                    "status": "partial_success",
                    "message": result.summary_message,
                    "errors": [error.message for error in result.errors],
                    "details": {
                        "total_items": result.total_entries,
                        "successful_items": result.successful_entries,
                        "failed_items": result.failed_entries,
                        "success_rate": result.success_rate,
                        "processing_time": result.processing_time_seconds
                    }
                }
                
        except Exception as e:
            logger.error(f"Error processing /out command: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
                "errors": [str(e)]
            }
    
    def get_help_text(self) -> str:
        """Get help text for the new batch commands."""
        return """📝 <b>New Batch Movement Commands</b>

<b>Format:</b>
/in
-batch 1-
project: mzuzu, driver: Dani maliko
Solar floodlight panel FS-SFL800, 4
Solar floodlight 800W, 4

-batch 2-
project: lilongwe, driver: John Banda
Cable 2.5sqmm black 100m, 1

<b>Key Features:</b>
• Multiple batches in one command
• Simple parameter format
• Smart defaults for missing info
• Essential parameters only: item name, quantity

<b>Parameters:</b>
• project: Project name (defaults to "not described")
• driver: Driver name (defaults to "not described")
• to: Destination (for /out, defaults to "external")
• from: Source (for /in, defaults to "not described")

<b>Examples:</b>
• Single batch: /in project: test, driver: John
  Item 1, 10
  Item 2, 5

• Multiple batches: /out
  -batch 1-
  project: site1, driver: Driver1, to: location1
  Item A, 10
  
  -batch 2-
  project: site2, driver: Driver2, to: location2
  Item B, 5"""
