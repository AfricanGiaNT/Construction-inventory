"""Telegram Integration Tests for Batch Commands - Phase 4."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, Message, Chat, User, CallbackQuery

from src.main import ConstructionInventoryBot
from src.schemas import MovementType, UserRole
from src.services.enhanced_batch_processor import EnhancedBatchProcessor


class TestTelegramBatchCommands:
    """Test Telegram integration for batch commands."""
    
    def _create_command(self, command: str, args: list) -> 'Command':
        """Helper to create Command objects for testing."""
        from src.commands import Command
        return Command(
            command=command,
            args=args,
            chat_id=123,
            user_id=456,
            user_name="Test User",
            message_id=789,
            update_id=101112
        )
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock settings
        self.mock_settings = MagicMock()
        self.mock_settings.telegram_bot_token = "test_token"
        
        # Mock airtable client
        self.mock_airtable = AsyncMock()
        
        # Mock stock service
        self.mock_stock_service = AsyncMock()
        
        # Mock enhanced batch processor
        self.mock_enhanced_processor = AsyncMock()
        
        # Create bot instance
        self.bot = ConstructionInventoryBot()
        
        # Replace services with mocks
        self.bot.airtable_client = self.mock_airtable
        self.bot.settings = self.mock_settings
        self.bot.stock_service = self.mock_stock_service
        
        # Replace enhanced batch processor with mock
        self.bot.enhanced_batch_processor = self.mock_enhanced_processor
        
        # Mock telegram service
        self.bot.telegram_service = AsyncMock()
        
        # Sample batch result
        self.sample_batch_result = MagicMock()
        self.sample_batch_result.success_rate = 100.0
        self.sample_batch_result.total_entries = 5
        self.sample_batch_result.successful_entries = 5
        self.sample_batch_result.failed_entries = 0
        self.sample_batch_result.processing_time_seconds = 1.5
        self.sample_batch_result.summary_message = "Successfully processed 5 items"
        self.sample_batch_result.errors = []
    
    @pytest.mark.asyncio
    async def test_in_command_success_flow(self):
        """Test successful /in command flow with progress indicators."""
        # Mock command object
        command = self._create_command("in", ["-batch 1- project: test site\nCement 50kg, 10 bags"])
        
        # Mock enhanced batch processor response
        self.mock_enhanced_processor.get_duplicate_preview = AsyncMock(return_value={
            "status": "success",
            "total_items": 1,
            "duplicate_count": 0,
            "non_duplicate_count": 1,
            "exact_matches": 0,
            "similar_items": 0
        })
        self.mock_enhanced_processor.process_batch_command_with_duplicates = AsyncMock(
            return_value=self.sample_batch_result
        )
        
        # Mock telegram service
        self.bot.telegram_service.send_message = AsyncMock(return_value=True)
        
        # Execute command
        await self.bot.execute_command(command, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify calls
        assert self.mock_enhanced_processor.get_duplicate_preview.called
        assert self.mock_enhanced_processor.process_batch_command_with_duplicates.called
        
        # Verify progress indicator was sent
        progress_calls = [call for call in self.bot.telegram_service.send_message.call_args_list 
                         if "Processing batches..." in str(call)]
        assert len(progress_calls) >= 1
        
        # Verify success message was sent
        success_calls = [call for call in self.bot.telegram_service.send_message.call_args_list 
                        if "Batch Processing Complete!" in str(call)]
        assert len(success_calls) >= 1
    
    @pytest.mark.asyncio
    async def test_out_command_success_flow(self):
        """Test successful /out command flow with progress indicators."""
        # Mock command
        command = "out"
        args = ["-batch 1- project: test site, to: warehouse\nCement 50kg, 5 bags"]
        
        # Mock enhanced batch processor response
        self.mock_enhanced_processor.get_duplicate_preview = AsyncMock(return_value={
            "status": "success",
            "total_items": 1,
            "duplicate_count": 0,
            "non_duplicate_count": 1,
            "exact_matches": 0,
            "similar_items": 0
        })
        self.mock_enhanced_processor.process_batch_command_with_duplicates = AsyncMock(
            return_value=self.sample_batch_result
        )
        
        # Mock telegram service
        self.bot.telegram_service.send_message = AsyncMock(return_value=True)
        
        # Execute command
        await self.bot.execute_command(command, args, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify calls
        assert self.mock_enhanced_processor.get_duplicate_preview.called
        assert self.mock_enhanced_processor.process_batch_command_with_duplicates.called
        
        # Verify progress indicator was sent
        progress_calls = [call for call in self.bot.telegram_service.send_message.call_args_list 
                         if "Processing batches..." in str(call)]
        assert len(progress_calls) >= 1
    
    @pytest.mark.asyncio
    async def test_in_command_with_errors(self):
        """Test /in command with processing errors and enhanced error messages."""
        # Mock command
        command = "in"
        args = ["-batch 1- project: test site\nInvalid item, 10 bags"]
        
        # Mock enhanced batch processor response with errors
        self.mock_enhanced_processor.get_duplicate_preview = AsyncMock(return_value={
            "status": "success",
            "total_items": 1,
            "duplicate_count": 0,
            "non_duplicate_count": 1,
            "exact_matches": 0,
            "similar_items": 0
        })
        
        # Mock batch result with errors
        error_result = MagicMock()
        error_result.success_rate = 0.0
        error_result.total_entries = 1
        error_result.successful_entries = 0
        error_result.failed_entries = 1
        error_result.processing_time_seconds = 1.0
        error_result.summary_message = "Failed to process 1 items"
        error_result.errors = [MagicMock(message="Item not found", suggestion="Check item name")]
        
        self.mock_enhanced_processor.process_batch_command_with_duplicates = AsyncMock(
            return_value=error_result
        )
        
        # Mock telegram service
        self.bot.telegram_service.send_message = AsyncMock(return_value=True)
        self.bot.telegram_service.send_error_message = AsyncMock(return_value=True)
        
        # Execute command
        await self.bot.execute_command(command, args, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify error message was sent with details
        error_calls = [call for call in self.bot.telegram_service.send_error_message.call_args_list 
                      if "Batch Processing Completed with Issues" in str(call)]
        assert len(error_calls) >= 1
    
    @pytest.mark.asyncio
    async def test_preview_in_command(self):
        """Test /preview in command functionality."""
        # Mock command
        command = "preview_in"
        args = ["-batch 1- project: test site\nCement 50kg, 10 bags"]
        
        # Mock enhanced batch processor response
        self.mock_enhanced_processor.get_duplicate_preview = AsyncMock(return_value={
            "status": "success",
            "total_items": 1,
            "duplicate_count": 1,
            "non_duplicate_count": 0,
            "exact_matches": 1,
            "similar_items": 0,
            "duplicates": [{"item_name": "Cement 50kg", "similarity_score": 0.95}]
        })
        
        # Mock telegram service
        self.bot.telegram_service.send_message = AsyncMock(return_value=True)
        
        # Execute command
        await self.bot.execute_command(command, args, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify preview was called
        assert self.mock_enhanced_processor.get_duplicate_preview.called
        
        # Verify preview message was sent
        preview_calls = [call for call in self.bot.telegram_service.send_message.call_args_list 
                        if "duplicate" in str(call).lower()]
        assert len(preview_calls) >= 1
    
    @pytest.mark.asyncio
    async def test_help_command_shows_batch_features(self):
        """Test that /help command shows batch features."""
        # Mock command
        command = "help"
        args = []
        
        # Mock telegram service
        self.bot.telegram_service.send_help_message = AsyncMock(return_value=True)
        
        # Execute command
        await self.bot.execute_command(command, args, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify help message was sent
        assert self.bot.telegram_service.send_help_message.called
    
    @pytest.mark.asyncio
    async def test_batch_help_command(self):
        """Test /batchhelp command shows detailed batch guide."""
        # Mock command
        command = "batchhelp"
        args = []
        
        # Mock telegram service
        self.bot.telegram_service.send_message = AsyncMock(return_value=True)
        
        # Execute command
        await self.bot.execute_command(command, args, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify batch help message was sent
        help_calls = [call for call in self.bot.telegram_service.send_message.call_args_list 
                     if "batch" in str(call).lower()]
        assert len(help_calls) >= 1
    
    @pytest.mark.asyncio
    async def test_command_with_exception_handling(self):
        """Test command execution with exception handling."""
        # Mock command that will raise an exception
        command = "in"
        args = ["invalid command"]
        
        # Mock enhanced batch processor to raise exception
        self.mock_enhanced_processor.get_duplicate_preview = AsyncMock(side_effect=Exception("Test error"))
        
        # Mock telegram service
        self.bot.telegram_service.send_error_message = AsyncMock(return_value=True)
        
        # Execute command
        await self.bot.execute_command(command, args, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify error message was sent
        error_calls = [call for call in self.bot.telegram_service.send_error_message.call_args_list 
                      if "Error processing command" in str(call)]
        assert len(error_calls) >= 1
    
    @pytest.mark.asyncio
    async def test_duplicate_confirmation_workflow(self):
        """Test duplicate confirmation workflow integration."""
        # Mock duplicate confirmation data
        duplicate_data = {
            'duplicates': [{"item_name": "Cement 50kg", "similarity_score": 0.95}],
            'movement_type': MovementType.IN,
            'user_id': 456,
            'user_name': "Test User"
        }
        
        # Mock enhanced batch processor
        self.mock_enhanced_processor.get_duplicate_confirmation_data = AsyncMock(return_value=duplicate_data)
        self.mock_enhanced_processor.process_duplicate_confirmation = AsyncMock(return_value={
            "success": True,
            "message": "Processed 1 duplicate"
        })
        
        # Mock telegram service
        self.bot.telegram_service.send_duplicate_confirmation_dialog = AsyncMock(return_value=True)
        
        # Test duplicate confirmation workflow
        result = await self.bot._process_individual_duplicate_confirmation(
            MagicMock(), "confirm", 0, 123, "Test User"
        )
        
        # Verify duplicate confirmation was processed
        assert self.mock_enhanced_processor.process_duplicate_confirmation.called
