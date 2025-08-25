"""Tests for the validate command."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, UTC

from src.main import ConstructionInventoryBot
from src.schemas import (
    BatchFormat, BatchParseResult, BatchError, BatchErrorType,
    StockMovement, MovementType, MovementStatus
)


class TestValidateCommand:
    """Test the validate command functionality."""

    def setup_method(self):
        """Set up test environment."""
        # Mock settings
        self.settings_patcher = patch('src.main.Settings')
        self.mock_settings_class = self.settings_patcher.start()
        self.mock_settings = self.mock_settings_class.return_value
        self.mock_settings.telegram_bot_token = "test_token"
        self.mock_settings.telegram_allowed_chat_ids = [123456]
        self.mock_settings.airtable_api_key = "test_api_key"
        self.mock_settings.airtable_base_id = "test_base_id"
        self.mock_settings.log_level = "INFO"
        
        # Create bot with constructor bypassed
        with patch.object(ConstructionInventoryBot, '__init__', return_value=None):
            self.bot = ConstructionInventoryBot()
            
        # Set up required attributes manually
        self.bot.settings = self.mock_settings
        
        # Mock telegram service
        self.bot.telegram_service = MagicMock()
        self.bot.telegram_service.send_message = AsyncMock()
        
        # Mock command router and NLP parser
        self.bot.command_router = MagicMock()
        self.bot.command_router.parser = MagicMock()
        self.bot.command_router.parser.nlp_parser = MagicMock()
        
        # Test data
        self.chat_id = 123456
        self.user_id = 789012
        self.user_name = "Test User"

    def teardown_method(self):
        """Clean up after tests."""
        self.settings_patcher.stop()

    @pytest.mark.asyncio
    async def test_validate_command_with_valid_batch(self):
        """Test validate command with a valid batch."""
        # Mock batch parsing result
        mock_result = BatchParseResult(
            format=BatchFormat.NEWLINE,
            movements=[
                StockMovement(
                    item_name="cement",
                    quantity=50.0,
                    unit="bags",
                    movement_type=MovementType.IN,
                    user_id=str(self.user_id),
                    user_name=self.user_name,
                    timestamp=datetime.now(UTC),
                    status=MovementStatus.POSTED,
                    signed_base_quantity=50.0
                ),
                StockMovement(
                    item_name="steel bars",
                    quantity=100.0,
                    unit="pieces",
                    movement_type=MovementType.IN,
                    user_id=str(self.user_id),
                    user_name=self.user_name,
                    timestamp=datetime.now(UTC),
                    status=MovementStatus.POSTED,
                    signed_base_quantity=100.0
                )
            ],
            total_entries=2,
            valid_entries=2,
            errors=[],
            is_valid=True
        )
        
        self.bot.command_router.parser.nlp_parser.parse_batch_entries.return_value = mock_result
        
        # Call the validate command
        await self.bot.handle_validate_command(
            self.chat_id, 
            self.user_id, 
            self.user_name, 
            "in cement, 50 bags\nsteel bars, 100 pieces"
        )
        
        # Check that the parser was called correctly
        self.bot.command_router.parser.nlp_parser.parse_batch_entries.assert_called_once()
        
        # Check that the telegram service was called with validation report
        self.bot.telegram_service.send_message.assert_called_once()
        call_args = self.bot.telegram_service.send_message.call_args[0]
        
        # Check that the message contains the expected content
        assert call_args[0] == self.chat_id
        assert "Batch Validation Report" in call_args[1]
        assert "<b>Movement Type:</b> IN" in call_args[1]
        assert "<b>Format:</b> Newline" in call_args[1]
        assert "<b>Total Entries:</b> 2" in call_args[1]
        assert "<b>Valid Entries:</b> 2" in call_args[1]
        assert "<b>Status:</b> ✅ Valid" in call_args[1]
        assert "cement: 50.0 bags" in call_args[1]
        assert "steel bars: 100.0 pieces" in call_args[1]
        assert "Your batch format is valid!" in call_args[1]

    @pytest.mark.asyncio
    async def test_validate_command_with_invalid_batch(self):
        """Test validate command with an invalid batch."""
        # Mock batch parsing result with errors
        mock_result = BatchParseResult(
            format=BatchFormat.NEWLINE,
            movements=[
                StockMovement(
                    item_name="cement",
                    quantity=50.0,
                    unit="bags",
                    movement_type=MovementType.IN,
                    user_id=str(self.user_id),
                    user_name=self.user_name,
                    timestamp=datetime.now(UTC),
                    status=MovementStatus.POSTED,
                    signed_base_quantity=50.0
                )
            ],
            total_entries=2,
            valid_entries=1,
            errors=["Entry #2: Could not parse 'steel bars'. Check format: item, quantity unit, [location], [note]"],
            is_valid=False
        )
        
        self.bot.command_router.parser.nlp_parser.parse_batch_entries.return_value = mock_result
        
        # Call the validate command
        await self.bot.handle_validate_command(
            self.chat_id, 
            self.user_id, 
            self.user_name, 
            "in cement, 50 bags\nsteel bars"
        )
        
        # Check that the parser was called correctly
        self.bot.command_router.parser.nlp_parser.parse_batch_entries.assert_called_once()
        
        # Check that the telegram service was called with validation report
        self.bot.telegram_service.send_message.assert_called_once()
        call_args = self.bot.telegram_service.send_message.call_args[0]
        
        # Check that the message contains the expected content
        assert call_args[0] == self.chat_id
        assert "Batch Validation Report" in call_args[1]
        assert "<b>Movement Type:</b> IN" in call_args[1]
        assert "<b>Format:</b> Newline" in call_args[1]
        assert "<b>Total Entries:</b> 2" in call_args[1]
        assert "<b>Valid Entries:</b> 1" in call_args[1]
        assert "<b>Status:</b> ❌ Invalid" in call_args[1]
        assert "cement: 50.0 bags" in call_args[1]
        assert "<b>Errors:</b>" in call_args[1]
        assert "Could not parse" in call_args[1]
        assert "Please fix the errors and try again" in call_args[1]

    @pytest.mark.asyncio
    async def test_validate_command_with_no_movement_type(self):
        """Test validate command with no movement type specified."""
        # Call the validate command with no movement type
        await self.bot.handle_validate_command(
            self.chat_id, 
            self.user_id, 
            self.user_name, 
            "cement, 50 bags\nsteel bars, 100 pieces"
        )
        
        # Check that the telegram service was called with error message
        self.bot.telegram_service.send_message.assert_called_once()
        call_args = self.bot.telegram_service.send_message.call_args[0]
        
        # Check that the message contains the expected content
        assert call_args[0] == self.chat_id
        assert "Invalid Format" in call_args[1]
        assert "Could not determine movement type" in call_args[1]

    @pytest.mark.asyncio
    async def test_validate_command_with_suggestions(self):
        """Test validate command with recovery suggestions."""
        # Mock batch parsing result with multiple errors
        mock_result = BatchParseResult(
            format=BatchFormat.MIXED,
            movements=[],
            total_entries=3,
            valid_entries=0,
            errors=[
                "Entry #1: Could not parse 'cement'. Check format: item, quantity unit, [location], [note]",
                "Entry #2: Could not parse 'steel bars'. Check format: item, quantity unit, [location], [note]",
                "Entry #3: Could not parse 'safety equipment'. Check format: item, quantity unit, [location], [note]",
                "Tip: For clearer batch commands, try using either all newlines or all semicolons, not mixed format."
            ],
            is_valid=False
        )
        
        self.bot.command_router.parser.nlp_parser.parse_batch_entries.return_value = mock_result
        
        # Call the validate command
        await self.bot.handle_validate_command(
            self.chat_id, 
            self.user_id, 
            self.user_name, 
            "in cement\nsteel bars; safety equipment"
        )
        
        # Check that the parser was called correctly
        self.bot.command_router.parser.nlp_parser.parse_batch_entries.assert_called_once()
        
        # Check that the telegram service was called with validation report
        self.bot.telegram_service.send_message.assert_called_once()
        call_args = self.bot.telegram_service.send_message.call_args[0]
        
        # Check that the message contains the expected content
        assert call_args[0] == self.chat_id
        assert "Batch Validation Report" in call_args[1]
        assert "<b>Movement Type:</b> IN" in call_args[1]
        assert "<b>Format:</b> Mixed" in call_args[1]
        assert "<b>Total Entries:</b> 3" in call_args[1]
        assert "<b>Valid Entries:</b> 0" in call_args[1]
        assert "<b>Status:</b> ❌ Invalid" in call_args[1]
        assert "<b>Errors:</b>" in call_args[1]
        assert "Could not parse" in call_args[1]
        assert "<b>Suggestions:</b>" in call_args[1]
        assert "Command format issues" in call_args[1] or "Check format" in call_args[1]
        assert "Please fix the errors and try again" in call_args[1]
