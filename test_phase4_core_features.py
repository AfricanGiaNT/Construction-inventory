"""Core Phase 4 Features Test - Minimal verification."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.main import ConstructionInventoryBot
from src.schemas import MovementType, UserRole


class TestPhase4CoreFeatures:
    """Test core Phase 4 features are implemented."""
    
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
        # Create bot instance
        self.bot = ConstructionInventoryBot()
        
        # Mock services
        self.bot.telegram_service = AsyncMock()
        self.bot.enhanced_batch_processor = AsyncMock()
    
    @pytest.mark.asyncio
    async def test_in_command_has_progress_indicators(self):
        """Test that /in command shows progress indicators."""
        # Mock command
        command = self._create_command("in", ["-batch 1- project: test site\nCement 50kg, 10 bags"])
        
        # Mock enhanced batch processor response
        self.bot.enhanced_batch_processor.get_duplicate_preview = AsyncMock(return_value={
            "status": "success",
            "total_items": 1,
            "duplicate_count": 0,
            "non_duplicate_count": 1,
            "exact_matches": 0,
            "similar_items": 0
        })
        
        # Mock get_duplicate_confirmation_data to return None (no pending duplicates)
        self.bot.enhanced_batch_processor.get_duplicate_confirmation_data = AsyncMock(return_value=None)
        
        # Mock batch result
        batch_result = MagicMock()
        batch_result.success_rate = 100.0
        batch_result.total_entries = 1
        batch_result.successful_entries = 1
        batch_result.failed_entries = 0
        batch_result.processing_time_seconds = 1.5
        batch_result.summary_message = "Successfully processed 1 items"
        batch_result.errors = []
        
        self.bot.enhanced_batch_processor.process_batch_command_with_duplicates = AsyncMock(
            return_value=batch_result
        )
        
        # Execute command
        await self.bot.execute_command(command, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify progress indicator was shown
        progress_calls = [call for call in self.bot.telegram_service.send_message.call_args_list 
                         if "Processing batches..." in str(call)]
        assert len(progress_calls) >= 1, "Progress indicator should be shown"
        
        # Verify success message was sent (updated format)
        success_calls = [call for call in self.bot.telegram_service.send_message.call_args_list 
                        if "Batch Processing Complete!" in str(call) or "Successfully processed" in str(call)]
        assert len(success_calls) >= 1, "Success message should be shown"
    
    @pytest.mark.asyncio
    async def test_out_command_has_progress_indicators(self):
        """Test that /out command shows progress indicators."""
        # Mock command
        command = self._create_command("out", ["-batch 1- project: test site, to: warehouse\nCement 50kg, 5 bags"])
        
        # Mock enhanced batch processor response
        self.bot.enhanced_batch_processor.get_duplicate_preview = AsyncMock(return_value={
            "status": "success",
            "total_items": 1,
            "duplicate_count": 0,
            "non_duplicate_count": 1,
            "exact_matches": 0,
            "similar_items": 0
        })
        
        # Mock get_duplicate_confirmation_data to return None (no pending duplicates)
        self.bot.enhanced_batch_processor.get_duplicate_confirmation_data = AsyncMock(return_value=None)
        
        # Mock batch result
        batch_result = MagicMock()
        batch_result.success_rate = 100.0
        batch_result.total_entries = 1
        batch_result.successful_entries = 1
        batch_result.failed_entries = 0
        batch_result.processing_time_seconds = 1.5
        batch_result.summary_message = "Successfully processed 1 items"
        batch_result.errors = []
        
        self.bot.enhanced_batch_processor.process_batch_command_with_duplicates = AsyncMock(
            return_value=batch_result
        )
        
        # Execute command
        await self.bot.execute_command(command, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify progress indicator was shown
        progress_calls = [call for call in self.bot.telegram_service.send_message.call_args_list 
                         if "Processing batches..." in str(call)]
        assert len(progress_calls) >= 1, "Progress indicator should be shown"
    
    @pytest.mark.asyncio
    async def test_help_command_shows_batch_features(self):
        """Test that help command shows batch features."""
        # Mock command
        command = self._create_command("help", [])
        
        # Execute command
        await self.bot.execute_command(command, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify help message was sent
        assert self.bot.telegram_service.send_help_message.called, "Help message should be sent"
    
    @pytest.mark.asyncio
    async def test_in_command_help_shows_batch_format(self):
        """Test that /in command help shows batch format."""
        # Mock command
        command = self._create_command("in", [])
        
        # Execute command
        await self.bot.execute_command(command, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify help message was sent
        assert self.bot.telegram_service.send_message.called, "Help message should be sent"
        
        # Verify help contains batch format
        help_call = self.bot.telegram_service.send_message.call_args
        help_text = help_call[0][1]  # Get the text argument
        assert "Stock IN Command - New Batch System" in help_text, "Should show batch system title"
        assert "-batch 1-" in help_text, "Should show batch format"
    
    @pytest.mark.asyncio
    async def test_out_command_help_shows_batch_format(self):
        """Test that /out command help shows batch format."""
        # Mock command
        command = self._create_command("out", [])
        
        # Execute command
        await self.bot.execute_command(command, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify help message was sent
        assert self.bot.telegram_service.send_message.called, "Help message should be sent"
        
        # Verify help contains batch format
        help_call = self.bot.telegram_service.send_message.call_args
        help_text = help_call[0][1]  # Get the text argument
        assert "Stock OUT Command - New Batch System" in help_text, "Should show batch system title"
        assert "-batch 1-" in help_text, "Should show batch format"
    
    @pytest.mark.asyncio
    async def test_preview_in_command_works(self):
        """Test that /preview_in command works."""
        # Mock command
        command = self._create_command("preview_in", ["-batch 1- project: test site\nCement 50kg, 10 bags"])
        
        # Mock enhanced batch processor response
        self.bot.enhanced_batch_processor.get_duplicate_preview = AsyncMock(return_value={
            "status": "success",
            "total_items": 1,
            "duplicate_count": 1,
            "non_duplicate_count": 0,
            "exact_matches": 1,
            "similar_items": 0,
            "duplicates": [{
                "item_name": "Cement 50kg", 
                "quantity": 10.0,
                "similarity_score": 0.95,
                "existing_item": "Cement 50kg bags",
                "existing_quantity": 25.0,
                "match_type": "exact"
            }]
        })
        
        # Execute command
        await self.bot.execute_command(command, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify preview was called
        assert self.bot.enhanced_batch_processor.get_duplicate_preview.called, "Preview should be called"
        
        # Verify preview message was sent (it calls _format_duplicate_preview first)
        assert self.bot.telegram_service.send_message.called, "Preview message should be sent"
        
        # Check that the preview was formatted and sent
        message_calls = self.bot.telegram_service.send_message.call_args_list
        assert len(message_calls) >= 1, "At least one message should be sent"
    
    @pytest.mark.asyncio
    async def test_batchhelp_command_works(self):
        """Test that /batchhelp command works."""
        # Mock command
        command = self._create_command("batchhelp", [])
        
        # Execute command
        await self.bot.execute_command(command, 123, 456, "Test User", UserRole.STAFF)
        
        # Verify help message was sent
        assert self.bot.telegram_service.send_message.called, "Batch help message should be sent"
