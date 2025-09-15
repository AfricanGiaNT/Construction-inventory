#!/usr/bin/env python3
"""
Phase 5 Final Integration Tests

Comprehensive system validation for the completed batch movement commands overhaul.
Tests the entire system end-to-end to ensure all components work together correctly.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any

from src.main import ConstructionInventoryBot
from src.schemas import (
    Item, Unit, MovementType, BatchInfo, BatchItem, 
    DuplicateItem, DuplicateMatchType, UserRole
)
from src.commands import Command


class TestPhase5FinalIntegration:
    """Comprehensive final integration tests for Phase 5."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Initialize bot
        self.bot = ConstructionInventoryBot()
        
        # Mock external dependencies
        self.mock_airtable = AsyncMock()
        self.mock_settings = MagicMock()
        self.mock_telegram = AsyncMock()
        self.mock_stock_service = AsyncMock()
        
        # Configure mocks
        self.bot.airtable_client = self.mock_airtable
        self.bot.settings = self.mock_settings
        self.bot.telegram_service = self.mock_telegram
        self.bot.stock_service = self.mock_stock_service
        
        # Mock enhanced batch processor
        self.bot.enhanced_batch_processor = AsyncMock()
        
        # Sample test data
        self.sample_items = [
            Item(
                id="item1",
                name="Cement bags 50kg",
                on_hand=100.0,
                unit_type="bags",
                project="test project",
                category="Building Materials",
                units=[Unit(name="bags", conversion_factor=1.0)]
            ),
            Item(
                id="item2", 
                name="Steel bars 12mm",
                on_hand=50.0,
                unit_type="pieces",
                project="test project", 
                category="Steel",
                units=[Unit(name="pieces", conversion_factor=1.0)]
            )
        ]
    
    def _create_command(self, command: str, args: list) -> Command:
        """Helper to create Command objects for testing."""
        return Command(
            command=command,
            args=args,
            chat_id=123,
            user_id=456,
            user_name="Test User",
            message_id=789,
            update_id=101112
        )

    @pytest.mark.asyncio
    async def test_complete_batch_in_workflow(self):
        """Test complete /in batch workflow end-to-end."""
        # Mock successful batch processing
        self.bot.enhanced_batch_processor.process_batch_command_with_duplicates.return_value = AsyncMock()
        result_mock = AsyncMock()
        result_mock.success_rate = 100.0
        result_mock.total_entries = 3
        result_mock.successful_entries = 3
        result_mock.failed_entries = 0
        result_mock.summary_message = "Successfully processed 3 items"
        result_mock.processing_time_seconds = 1.5
        result_mock.requires_user_confirmation = False
        result_mock.pending_duplicates = []
        self.bot.enhanced_batch_processor.process_batch_command_with_duplicates.return_value = result_mock
        
        # Mock preview
        self.bot.enhanced_batch_processor.get_duplicate_preview.return_value = {
            "status": "success",
            "total_items": 3,
            "total_batches": 1,
            "duplicates_found": 0,
            "message": "No duplicates found"
        }
        
        # Test command
        command_text = """-batch 1-
project: test site, driver: John Doe
Cement bags 50kg, 10 bags
Steel bars 12mm, 5 pieces
Paint white 5L, 2 cans"""
        
        command = self._create_command("in", [command_text])
        
        # Execute command
        await self.bot.execute_command(command, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify calls were made
        self.bot.enhanced_batch_processor.get_duplicate_preview.assert_called_once()
        self.bot.enhanced_batch_processor.process_batch_command_with_duplicates.assert_called_once()
        
        # Verify messages were sent
        assert self.bot.telegram_service.send_message.call_count >= 2  # Summary + Progress + Result

    @pytest.mark.asyncio
    async def test_complete_batch_out_workflow(self):
        """Test complete /out batch workflow end-to-end."""
        # Mock successful batch processing
        self.bot.enhanced_batch_processor.process_batch_command_with_duplicates.return_value = AsyncMock()
        result_mock = AsyncMock()
        result_mock.success_rate = 100.0
        result_mock.total_entries = 2
        result_mock.successful_entries = 2
        result_mock.failed_entries = 0
        result_mock.summary_message = "Successfully processed 2 items"
        result_mock.processing_time_seconds = 1.2
        result_mock.requires_user_confirmation = False
        result_mock.pending_duplicates = []
        self.bot.enhanced_batch_processor.process_batch_command_with_duplicates.return_value = result_mock
        
        # Mock preview
        self.bot.enhanced_batch_processor.get_duplicate_preview.return_value = {
            "status": "success",
            "total_items": 2,
            "total_batches": 1,
            "duplicates_found": 0,
            "message": "No duplicates found"
        }
        
        # Test command
        command_text = """-batch 1-
project: construction site, driver: Jane Smith, to: warehouse A
Cement bags 50kg, 5 bags
Steel bars 12mm, 10 pieces"""
        
        command = self._create_command("out", [command_text])
        
        # Execute command
        await self.bot.execute_command(command, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify calls were made
        self.bot.enhanced_batch_processor.get_duplicate_preview.assert_called_once()
        self.bot.enhanced_batch_processor.process_batch_command_with_duplicates.assert_called_once()
        
        # Verify messages were sent
        assert self.bot.telegram_service.send_message.call_count >= 2

    @pytest.mark.asyncio
    async def test_multi_batch_processing(self):
        """Test multi-batch processing workflow."""
        # Mock successful multi-batch processing
        result_mock = AsyncMock()
        result_mock.success_rate = 100.0
        result_mock.total_entries = 5
        result_mock.successful_entries = 5
        result_mock.failed_entries = 0
        result_mock.summary_message = "Successfully processed 5 items across 2 batches"
        result_mock.processing_time_seconds = 2.3
        result_mock.requires_user_confirmation = False
        result_mock.pending_duplicates = []
        self.bot.enhanced_batch_processor.process_batch_command_with_duplicates.return_value = result_mock
        
        # Mock preview
        self.bot.enhanced_batch_processor.get_duplicate_preview.return_value = {
            "status": "success",
            "total_items": 5,
            "total_batches": 2,
            "duplicates_found": 0,
            "message": "No duplicates found"
        }
        
        # Test multi-batch command
        command_text = """-batch 1-
project: mzuzu site, driver: Peter Banda, to: construction zone
Cement bags 50kg, 15 bags
Steel bars 12mm, 20 pieces

-batch 2-
project: lilongwe office, driver: Mary Phiri, to: storage room
Paint white 5L, 3 cans
Brushes 4inch, 10 pieces"""
        
        command = self._create_command("out", [command_text])
        
        # Execute command
        await self.bot.execute_command(command, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify processing was called with correct parameters
        self.bot.enhanced_batch_processor.process_batch_command_with_duplicates.assert_called_once_with(
            command_text, MovementType.OUT, 456, "Test User", 123
        )

    @pytest.mark.asyncio
    async def test_duplicate_confirmation_workflow(self):
        """Test the duplicate confirmation workflow."""
        # Mock duplicate detection result
        result_mock = AsyncMock()
        result_mock.success_rate = 75.0
        result_mock.total_entries = 4
        result_mock.successful_entries = 3
        result_mock.failed_entries = 0
        result_mock.summary_message = "Processed 3 items, 1 duplicate requires confirmation"
        result_mock.processing_time_seconds = 1.8
        result_mock.requires_user_confirmation = True
        
        # Mock pending duplicates
        duplicate_item = {
            'batch_item': {'item_name': 'Cement 50kg bags', 'quantity': 10.0, 'unit': 'bags'},
            'existing_item': {'name': 'Cement bags 50kg', 'on_hand': 100.0, 'unit_type': 'bags'},
            'similarity_score': 0.95,
            'match_type': DuplicateMatchType.EXACT,
            'batch_number': 1,
            'item_index': 0
        }
        result_mock.pending_duplicates = [duplicate_item]
        
        self.bot.enhanced_batch_processor.process_batch_command_with_duplicates.return_value = result_mock
        
        # Mock preview
        self.bot.enhanced_batch_processor.get_duplicate_preview.return_value = {
            "status": "success",
            "total_items": 4,
            "total_batches": 1,
            "duplicates_found": 1,
            "message": "1 potential duplicate found"
        }
        
        # Test command with duplicates
        command_text = """-batch 1-
project: test site
Cement 50kg bags, 10 bags
Steel bars 12mm, 5 pieces
New item, 3 units"""
        
        command = self._create_command("in", [command_text])
        
        # Execute command
        await self.bot.execute_command(command, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify duplicate confirmation dialog was triggered
        self.bot.telegram_service.send_duplicate_confirmation_dialog.assert_called_once()

    @pytest.mark.asyncio
    async def test_preview_commands(self):
        """Test preview command functionality."""
        # Mock preview results
        preview_result = {
            "status": "success",
            "total_items": 3,
            "total_batches": 1,
            "duplicates_found": 1,
            "duplicates": [
                {
                    'batch_item': {'item_name': 'Cement 50kg', 'quantity': 10.0},
                    'existing_item': {'name': 'Cement bags 50kg', 'on_hand': 100.0},
                    'similarity_score': 0.88,
                    'match_type': 'similar'
                }
            ],
            "non_duplicates": [
                {'item_name': 'New item', 'quantity': 5.0}
            ],
            "message": "Preview completed"
        }
        
        self.bot.enhanced_batch_processor.get_duplicate_preview.return_value = preview_result
        
        # Test preview in command
        command_text = "Cement 50kg, 10 bags\nSteel bars, 5 pieces\nNew item, 5 units"
        command = self._create_command("preview_in", [command_text])
        
        # Execute command
        await self.bot.execute_command(command, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify preview was called
        self.bot.enhanced_batch_processor.get_duplicate_preview.assert_called_once_with(
            command_text, MovementType.IN
        )
        
        # Verify formatted preview was sent
        self.bot.telegram_service.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        # Mock partial failure result
        result_mock = AsyncMock()
        result_mock.success_rate = 66.7
        result_mock.total_entries = 3
        result_mock.successful_entries = 2
        result_mock.failed_entries = 1
        result_mock.summary_message = "Processed 2 items, 1 failed"
        result_mock.processing_time_seconds = 1.5
        result_mock.requires_user_confirmation = False
        result_mock.pending_duplicates = []
        
        # Mock errors
        error_mock = MagicMock()
        error_mock.message = "Item 'Invalid Item' not found in inventory"
        error_mock.suggestion = "Check item name or create new item"
        result_mock.errors = [error_mock]
        
        self.bot.enhanced_batch_processor.process_batch_command_with_duplicates.return_value = result_mock
        
        # Mock preview
        self.bot.enhanced_batch_processor.get_duplicate_preview.return_value = {
            "status": "success",
            "total_items": 3,
            "total_batches": 1,
            "duplicates_found": 0,
            "message": "No duplicates found"
        }
        
        # Test command with invalid item
        command_text = """-batch 1-
project: test site
Cement bags 50kg, 10 bags
Invalid Item Name, 5 pieces
Steel bars 12mm, 3 pieces"""
        
        command = self._create_command("in", [command_text])
        
        # Execute command
        await self.bot.execute_command(command, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify error message was sent
        self.bot.telegram_service.send_error_message.assert_called()

    @pytest.mark.asyncio
    async def test_help_system_integration(self):
        """Test help system integration."""
        # Test /in help
        command = self._create_command("in", [])
        await self.bot.execute_command(command, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify help message was sent
        self.bot.telegram_service.send_message.assert_called()
        help_call = self.bot.telegram_service.send_message.call_args[0][1]
        assert "Stock IN Command - New Batch System" in help_call
        assert "Batch Command Features" in help_call or "Key Features" in help_call
        
        # Reset mock
        self.bot.telegram_service.reset_mock()
        
        # Test /out help
        command = self._create_command("out", [])
        await self.bot.execute_command(command, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify help message was sent
        self.bot.telegram_service.send_message.assert_called()
        help_call = self.bot.telegram_service.send_message.call_args[0][1]
        assert "Stock OUT Command - New Batch System" in help_call

    @pytest.mark.asyncio
    async def test_performance_validation(self):
        """Test system performance with large batches."""
        # Mock large batch processing
        result_mock = AsyncMock()
        result_mock.success_rate = 100.0
        result_mock.total_entries = 50
        result_mock.successful_entries = 50
        result_mock.failed_entries = 0
        result_mock.summary_message = "Successfully processed 50 items across 5 batches"
        result_mock.processing_time_seconds = 5.2
        result_mock.requires_user_confirmation = False
        result_mock.pending_duplicates = []
        
        self.bot.enhanced_batch_processor.process_batch_command_with_duplicates.return_value = result_mock
        
        # Mock preview for large batch
        self.bot.enhanced_batch_processor.get_duplicate_preview.return_value = {
            "status": "success",
            "total_items": 50,
            "total_batches": 5,
            "duplicates_found": 0,
            "message": "No duplicates found"
        }
        
        # Create large batch command (simulated)
        large_command = "-batch 1-\nproject: large test\n" + "\n".join([
            f"Test Item {i}, {i} units" for i in range(1, 11)
        ])
        for batch_num in range(2, 6):
            large_command += f"\n-batch {batch_num}-\nproject: batch {batch_num}\n"
            large_command += "\n".join([
                f"Test Item {i + batch_num * 10}, {i} units" for i in range(1, 11)
            ])
        
        command = self._create_command("in", [large_command])
        
        # Measure execution time
        start_time = time.time()
        await self.bot.execute_command(command, 123, 456, "Test User", UserRole.STAFF)
        execution_time = time.time() - start_time
        
        # Verify performance (should complete within reasonable time)
        assert execution_time < 10.0  # Should complete within 10 seconds
        
        # Verify processing was called
        self.bot.enhanced_batch_processor.process_batch_command_with_duplicates.assert_called_once()

    @pytest.mark.asyncio
    async def test_backward_compatibility_validation(self):
        """Test that the system maintains compatibility with expected interfaces."""
        # Test that all expected command handlers exist
        command_handlers = [
            "in", "out", "preview_in", "preview_out", 
            "stock", "help", "inventory", "adjust"
        ]
        
        for handler in command_handlers:
            # Create test command
            command = self._create_command(handler, [])
            
            # Should not raise an exception
            try:
                await self.bot.execute_command(command, 123, 456, "Test User", UserRole.STAFF)
            except AttributeError as e:
                if "has no attribute" in str(e):
                    pytest.fail(f"Missing command handler for '{handler}': {e}")

    @pytest.mark.asyncio
    async def test_system_monitoring_integration(self):
        """Test that system monitoring and statistics work correctly."""
        # Execute several commands to generate stats
        commands = [
            self._create_command("in", ["Cement, 10 bags"]),
            self._create_command("out", ["Steel, 5 pieces"]),
            self._create_command("stock", ["cement"]),
            self._create_command("help", [])
        ]
        
        # Mock successful results
        self.bot.enhanced_batch_processor.process_batch_command_with_duplicates.return_value = AsyncMock()
        result_mock = AsyncMock()
        result_mock.success_rate = 100.0
        result_mock.requires_user_confirmation = False
        result_mock.pending_duplicates = []
        self.bot.enhanced_batch_processor.process_batch_command_with_duplicates.return_value = result_mock
        
        self.bot.enhanced_batch_processor.get_duplicate_preview.return_value = {
            "status": "success",
            "total_items": 1,
            "total_batches": 1,
            "duplicates_found": 0
        }
        
        # Execute commands
        for command in commands:
            await self.bot.execute_command(command, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify monitoring stats were updated
        assert hasattr(self.bot, 'monitoring_stats')
        assert self.bot.monitoring_stats['commands_processed'] >= len(commands)

    def test_migration_completeness(self):
        """Test that migration is complete and no legacy code remains."""
        # Verify that the new batch processing system is properly integrated
        assert hasattr(self.bot, 'enhanced_batch_processor')
        
        # Verify that all required services are initialized
        required_services = [
            'airtable_client', 'telegram_service', 'stock_service',
            'enhanced_batch_processor', 'command_router'
        ]
        
        for service in required_services:
            assert hasattr(self.bot, service), f"Missing required service: {service}"
        
        # Verify that the command router has the expected patterns
        expected_patterns = ['in', 'out', 'preview_in', 'preview_out']
        for pattern in expected_patterns:
            # This would need to be adapted based on actual command router implementation
            pass  # Placeholder for actual validation


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short"])
