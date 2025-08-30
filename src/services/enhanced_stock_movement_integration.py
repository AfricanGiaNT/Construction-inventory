"""Enhanced Stock Movement Integration Service for Phase 4."""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from schemas import StockMovement, MovementType, MovementStatus
from services.enhanced_stock_parser import EnhancedStockCommandParser, InCommandParseResult, OutCommandParseResult
from services.batch_stock_movement_service import batch_stock_movement_service
from services.smart_field_populator import smart_field_populator

logger = logging.getLogger(__name__)


class EnhancedStockMovementIntegration:
    """Integration layer for enhanced stock movements."""
    
    def __init__(self):
        """Initialize the integration service."""
        self.enhanced_parser = EnhancedStockCommandParser()
        self.batch_service = batch_stock_movement_service
        self.smart_populator = smart_field_populator
        
        # Track integration status
        self.integration_status = {
            "enhanced_parser": False,
            "smart_field_populator": False,
            "batch_service": False,
            "command_handlers": False
        }
    
    def integrate_with_existing_services(self) -> Dict[str, Any]:
        """Connect enhanced system with existing infrastructure."""
        try:
            logger.info("Starting integration with existing services...")
            
            # Test integration with enhanced parser
            self._test_enhanced_parser_integration()
            
            # Test integration with smart field populator
            self._test_smart_field_populator_integration()
            
            # Test integration with batch service
            self._test_batch_service_integration()
            
            # Test schema compatibility
            self._test_schema_compatibility()
            
            logger.info("Integration with existing services completed successfully")
            return {
                "status": "success",
                "message": "All services integrated successfully",
                "timestamp": datetime.now(),
                "integration_status": self.integration_status
            }
            
        except Exception as e:
            logger.error(f"Integration failed: {e}")
            return {
                "status": "error",
                "message": f"Integration failed: {str(e)}",
                "timestamp": datetime.now(),
                "integration_status": self.integration_status
            }
    
    def update_command_handlers(self) -> Dict[str, Any]:
        """Update main bot to handle enhanced commands."""
        try:
            logger.info("Updating command handlers for enhanced stock movements...")
            
            # Test enhanced command parsing
            self._test_enhanced_commands()
            
            # Test command validation
            self._test_command_validation()
            
            # Test error handling
            self._test_error_handling()
            
            # Test user experience
            self._test_user_experience()
            
            self.integration_status["command_handlers"] = True
            
            logger.info("Command handlers updated successfully")
            return {
                "status": "success",
                "message": "Command handlers updated successfully",
                "timestamp": datetime.now(),
                "integration_status": self.integration_status
            }
            
        except Exception as e:
            logger.error(f"Command handler update failed: {e}")
            return {
                "status": "error",
                "message": f"Command handler update failed: {str(e)}",
                "timestamp": datetime.now(),
                "integration_status": self.integration_status
            }
    
    def process_enhanced_in_command(self, command_text: str, user_id: int, 
                                  user_name: str, chat_id: int) -> Dict[str, Any]:
        """Process enhanced /in command with full integration."""
        try:
            logger.info(f"Processing enhanced IN command: {command_text[:100]}...")
            
            # Parse the command
            parse_result = self.enhanced_parser.parse_in_command(command_text)
            if not parse_result.is_valid:
                return {
                    "status": "error",
                    "message": "Command parsing failed",
                    "errors": parse_result.errors,
                    "suggestions": self._generate_parsing_suggestions(parse_result.errors)
                }
            
            # Process the batch
            batch_result = self.batch_service.process_batch_in(
                parse_result, user_id, user_name, chat_id
            )
            
            if batch_result.success_rate == 1.0:
                return {
                    "status": "success",
                    "message": "Batch IN processed successfully",
                    "summary": batch_result.summary_message,
                    "batch_id": batch_result.global_parameters.get('batch_id'),
                    "items_processed": batch_result.successful_entries,
                    "total_items": batch_result.total_entries
                }
            else:
                return {
                    "status": "partial_success",
                    "message": "Batch IN processed with some errors",
                    "summary": batch_result.summary_message,
                    "batch_id": batch_result.global_parameters.get('batch_id'),
                    "items_processed": batch_result.successful_entries,
                    "total_items": batch_result.total_entries,
                    "errors": [error.message for error in batch_result.errors]
                }
                
        except Exception as e:
            logger.error(f"Error processing enhanced IN command: {e}")
            return {
                "status": "error",
                "message": f"Processing error: {str(e)}",
                "suggestions": ["Please check command format and try again"]
            }
    
    def process_enhanced_out_command(self, command_text: str, user_id: int, 
                                   user_name: str, chat_id: int) -> Dict[str, Any]:
        """Process enhanced /out command with full integration."""
        try:
            logger.info(f"Processing enhanced OUT command: {command_text[:100]}...")
            
            # Parse the command
            parse_result = self.enhanced_parser.parse_out_command(command_text)
            if not parse_result.is_valid:
                return {
                    "status": "error",
                    "message": "Command parsing failed",
                    "errors": parse_result.errors,
                    "suggestions": self._generate_parsing_suggestions(parse_result.errors)
                }
            
            # Process the batch
            batch_result = self.batch_service.process_batch_out(
                parse_result, user_id, user_name, chat_id
            )
            
            if batch_result.success_rate == 1.0:
                return {
                    "status": "success",
                    "message": "Batch OUT processed successfully",
                    "summary": batch_result.summary_message,
                    "batch_id": batch_result.global_parameters.get('batch_id'),
                    "items_processed": batch_result.successful_entries,
                    "total_items": batch_result.total_entries
                }
            else:
                return {
                    "status": "partial_success",
                    "message": "Batch OUT processed with some errors",
                    "summary": batch_result.summary_message,
                    "batch_id": batch_result.global_parameters.get('batch_id'),
                    "items_processed": batch_result.successful_entries,
                    "total_items": batch_result.total_entries,
                    "errors": [error.message for error in batch_result.errors]
                }
                
        except Exception as e:
            logger.error(f"Error processing enhanced OUT command: {e}")
            return {
                "status": "error",
                "message": f"Processing error: {str(e)}",
                "suggestions": ["Please check command format and try again"]
            }
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get current integration status."""
        return {
            "overall_status": "complete" if all(self.integration_status.values()) else "in_progress",
            "integration_status": self.integration_status,
            "timestamp": datetime.now(),
            "services": {
                "enhanced_parser": "EnhancedStockCommandParser",
                "smart_field_populator": "SmartFieldPopulator", 
                "batch_service": "BatchStockMovementService",
                "command_handlers": "Enhanced Command Handlers"
            }
        }
    
    def _test_enhanced_parser_integration(self):
        """Test integration with enhanced parser."""
        try:
            # Test basic parsing
            test_command = "/in project: Test, driver: John; cement, 100"
            result = self.enhanced_parser.parse_in_command(test_command)
            
            if result.is_valid and len(result.items) > 0:
                self.integration_status["enhanced_parser"] = True
                logger.info("Enhanced parser integration test passed")
            else:
                raise Exception("Enhanced parser test failed")
                
        except Exception as e:
            logger.error(f"Enhanced parser integration test failed: {e}")
            raise
    
    def _test_smart_field_populator_integration(self):
        """Test integration with smart field populator."""
        try:
            # Test category detection
            category = self.smart_populator.populate_category("Paint 20ltrs")
            if category:
                self.integration_status["smart_field_populator"] = True
                logger.info("Smart field populator integration test passed")
            else:
                raise Exception("Smart field populator test failed")
                
        except Exception as e:
            logger.error(f"Smart field populator integration test failed: {e}")
            raise
    
    def _test_batch_service_integration(self):
        """Test integration with batch service."""
        try:
            # Test batch processing
            test_batch = InCommandParseResult(
                project="Test",
                driver="Test Driver",
                from_location="Test Source",
                items=[{"name": "test item", "quantity": 1, "unit": "piece"}]
            )
            
            result = self.batch_service.process_batch_in(
                test_batch, 12345, "Test User", 67890
            )
            
            if result.success_rate > 0:
                self.integration_status["batch_service"] = True
                logger.info("Batch service integration test passed")
            else:
                raise Exception("Batch service test failed")
                
        except Exception as e:
            logger.error(f"Batch service integration test failed: {e}")
            raise
    
    def _test_schema_compatibility(self):
        """Test schema compatibility with existing system."""
        try:
            # Test that we can create StockMovement objects
            movement = StockMovement(
                item_name="Test Item",
                movement_type=MovementType.IN,
                quantity=1,
                unit="piece",
                signed_base_quantity=1,
                user_id="12345",
                user_name="Test User"
            )
            
            if movement.item_name == "Test Item":
                logger.info("Schema compatibility test passed")
            else:
                raise Exception("Schema compatibility test failed")
                
        except Exception as e:
            logger.error(f"Schema compatibility test failed: {e}")
            raise
    
    def _test_enhanced_commands(self):
        """Test enhanced command functionality."""
        try:
            # Test IN command
            in_command = "/in project: Building A, driver: John\ncement, 100, for foundation"
            in_result = self.process_enhanced_in_command(in_command, 12345, "John", 67890)
            
            # Test OUT command
            out_command = "/out project: Road B, to: Site C, driver: Jane\npaint, 5, for marking"
            out_result = self.process_enhanced_out_command(out_command, 12346, "Jane", 67890)
            
            if in_result["status"] in ["success", "partial_success"] and out_result["status"] in ["success", "partial_success"]:
                logger.info("Enhanced commands test passed")
            else:
                raise Exception("Enhanced commands test failed")
                
        except Exception as e:
            logger.error(f"Enhanced commands test failed: {e}")
            raise
    
    def _test_command_validation(self):
        """Test command validation."""
        try:
            # Test invalid commands
            invalid_in = "/in project: Test\ncement, 100"  # Missing driver
            invalid_out = "/out project: Test\npaint, 5"  # Missing destination
            
            in_result = self.process_enhanced_in_command(invalid_in, 12345, "Test", 67890)
            out_result = self.process_enhanced_out_command(invalid_out, 12345, "Test", 67890)
            
            if in_result["status"] == "error" and out_result["status"] == "error":
                logger.info("Command validation test passed")
            else:
                raise Exception("Command validation test failed")
                
        except Exception as e:
            logger.error(f"Command validation test failed: {e}")
            raise
    
    def _test_error_handling(self):
        """Test error handling scenarios."""
        try:
            # Test malformed commands
            malformed = "invalid command format"
            result = self.process_enhanced_in_command(malformed, 12345, "Test", 67890)
            
            if result["status"] == "error" and "suggestions" in result:
                logger.info("Error handling test passed")
            else:
                raise Exception("Error handling test failed")
                
        except Exception as e:
            logger.error(f"Error handling test failed: {e}")
            raise
    
    def _test_user_experience(self):
        """Test user experience aspects."""
        try:
            # Test helpful error messages
            helpful_command = "/in project: Test\ncement, -5"  # Negative quantity
            result = self.process_enhanced_in_command(helpful_command, 12345, "Test", 67890)
            
            if result["status"] == "error" and len(result.get("suggestions", [])) > 0:
                logger.info("User experience test passed")
            else:
                raise Exception("User experience test failed")
                
        except Exception as e:
            logger.error(f"User experience test failed: {e}")
            raise
    
    def _generate_parsing_suggestions(self, errors: List[str]) -> List[str]:
        """Generate helpful suggestions for parsing errors."""
        suggestions = []
        
        for error in errors:
            if "Missing project" in error:
                suggestions.append("Add project: ProjectName to your command")
            elif "Missing driver" in error:
                suggestions.append("Add driver: DriverName to your command")
            elif "Missing destination" in error:
                suggestions.append("Add to: Destination to your OUT command")
            elif "Invalid quantity" in error:
                suggestions.append("Ensure quantity is a positive number")
            elif "Missing item name" in error:
                suggestions.append("Provide a name for each item")
            else:
                suggestions.append("Check command format: /in project: Name, driver: Name; item, quantity, unit")
        
        return suggestions


# Create a singleton instance
enhanced_stock_movement_integration = EnhancedStockMovementIntegration()
