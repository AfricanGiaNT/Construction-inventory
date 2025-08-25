"""Tests for the user experience improvements in Phase 3."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC

from src.main import ConstructionInventoryBot
from src.schemas import BatchFormat, BatchParseResult, StockMovement, MovementType, BatchResult, BatchError, BatchErrorType


class TestUserExperienceImprovements:
    """Test the user experience improvements for global parameters."""

    @pytest.fixture
    def bot(self):
        """Create a bot instance with mocked services for testing."""
        with patch("src.main.Settings") as mock_settings:
            # Mock settings
            mock_settings.return_value.log_level = "INFO"
            mock_settings.return_value.telegram_bot_token = "test_token"
            mock_settings.return_value.airtable_api_key = "test_api_key"
            mock_settings.return_value.airtable_base_id = "test_base_id"
            
            # Create bot instance
            bot = ConstructionInventoryBot()
            
            # Mock services
            bot.telegram_service.send_message = AsyncMock(return_value=True)
            
            return bot

    @pytest.mark.asyncio
    async def test_batch_help_message_includes_global_parameters(self, bot):
        """Test that the batch help message includes global parameters examples."""
        # Call the batch help message handler
        await bot.send_batch_help_message(123456789, "admin")
        
        # Check that the message was sent
        bot.telegram_service.send_message.assert_called_once()
        call_args = bot.telegram_service.send_message.call_args[0]
        
        # Verify that the message includes global parameters examples
        message_text = call_args[1]
        
        # Check for global parameters section
        assert "Global Parameters" in message_text
        assert "driver: Mr Longwe" in message_text
        assert "project: Bridge Construction" in message_text
        
        # Check for global parameters rules
        assert "Global parameters must be at the beginning of the command" in message_text
        assert "Global parameters use 'key: value' format" in message_text
        
        # Check for best practices
        assert "Use global parameters for common values" in message_text
        
        # Check for examples with global parameters
        assert "/in driver: Mr Longwe, from: supplier, project: Bridge Construction" in message_text
        assert "/out driver: Mr Smith, to: site A, project: Road Construction" in message_text

    @pytest.mark.asyncio
    async def test_system_status_message_includes_global_parameters(self, bot):
        """Test that the system status message includes global parameters feature."""
        # Call the system status message handler
        await bot.send_system_status_message(123456789, "admin")
        
        # Check that the message was sent
        bot.telegram_service.send_message.assert_called_once()
        call_args = bot.telegram_service.send_message.call_args[0]
        
        # Verify that the message includes global parameters feature
        message_text = call_args[1]
        
        # Check for global parameters in features
        assert "Global parameters for common values" in message_text
        assert "Project field support" in message_text
        assert "Parameter inheritance and override" in message_text
        
        # Check for global parameters in input formats
        assert "Global parameters (driver:, from:, to:, project:)" in message_text
        assert "Parameter inheritance and override" in message_text

    @pytest.mark.asyncio
    async def test_validation_feedback_with_global_parameters(self, bot):
        """Test that the validation feedback includes global parameters."""
        # Create a mock batch parse result with global parameters
        mock_result = BatchParseResult(
            format=BatchFormat.NEWLINE,
            movements=[
                StockMovement(
                    item_name="cement",
                    movement_type=MovementType.IN,
                    quantity=50.0,
                    unit="bags",
                    signed_base_quantity=50.0,
                    user_id="123",
                    user_name="testuser",
                    timestamp=datetime.now(UTC),
                    driver_name="Mr Longwe",
                    from_location="chigumula office",
                    project="Bridge Construction"
                )
            ],
            total_entries=1,
            valid_entries=1,
            errors=[],
            is_valid=True,
            global_parameters={
                "driver": "Mr Longwe",
                "from": "chigumula office",
                "project": "Bridge Construction"
            }
        )
        
        # Mock the parse_batch_entries method
        bot.command_router.parser.nlp_parser.parse_batch_entries = MagicMock(return_value=mock_result)
        
        # Call the validate command handler
        await bot.handle_validate_command(123456789, 123, "testuser", "in driver: Mr Longwe, from: chigumula office, project: Bridge Construction, cement, 50 bags")
        
        # Check that the message was sent
        assert bot.telegram_service.send_message.call_count >= 1
        call_args = bot.telegram_service.send_message.call_args[0]
        
        # Verify that the message includes global parameters
        message_text = call_args[1]
        
        # Check for global parameters section
        assert "<b>Global Parameters:</b>" in message_text
        assert "<b>Driver:</b> Mr Longwe" in message_text
        assert "<b>From:</b> chigumula office" in message_text
        assert "<b>Project:</b> Bridge Construction" in message_text
        
        # Check for inheritance message
        assert "These parameters will be applied to all entries unless overridden" in message_text

    @pytest.mark.asyncio
    async def test_validation_feedback_without_global_parameters(self, bot):
        """Test that the validation feedback includes a reminder about project field when no global parameters are used."""
        # Create a mock batch parse result without global parameters
        mock_result = BatchParseResult(
            format=BatchFormat.NEWLINE,
            movements=[
                StockMovement(
                    item_name="cement",
                    movement_type=MovementType.IN,
                    quantity=50.0,
                    unit="bags",
                    signed_base_quantity=50.0,
                    user_id="123",
                    user_name="testuser",
                    timestamp=datetime.now(UTC),
                    project="Bridge Construction"  # Project directly on the movement
                )
            ],
            total_entries=1,
            valid_entries=1,
            errors=[],
            is_valid=True,
            global_parameters={}  # No global parameters
        )
        
        # Mock the parse_batch_entries method
        bot.command_router.parser.nlp_parser.parse_batch_entries = MagicMock(return_value=mock_result)
        
        # Call the validate command handler
        await bot.handle_validate_command(123456789, 123, "testuser", "in cement, 50 bags, project: Bridge Construction")
        
        # Check that the message was sent
        assert bot.telegram_service.send_message.call_count >= 1
        call_args = bot.telegram_service.send_message.call_args[0]
        
        # Verify that the message includes a reminder about project field
        message_text = call_args[1]
        
        # Check for no global parameters warning
        assert "<b>⚠️ No Global Parameters:</b>" in message_text
        assert "Remember that project is required for all entries" in message_text
        assert "Consider using 'project:' as a global parameter" in message_text

    @pytest.mark.asyncio
    async def test_batch_result_message_with_global_parameters(self, bot):
        """Test that the batch result message includes global parameters."""
        # Create a mock batch result with global parameters
        mock_result = BatchResult(
            total_entries=2,
            successful_entries=2,
            failed_entries=0,
            success_rate=100.0,
            movements_created=["rec123", "rec456"],
            errors=[],
            rollback_performed=False,
            processing_time_seconds=0.5,
            summary_message="All entries processed successfully",
            global_parameters={
                "driver": "Mr Longwe",
                "from": "chigumula office",
                "project": "Bridge Construction"
            }
        )
        
        # Call the batch result message handler
        await bot.send_batch_result_message(123456789, mock_result)
        
        # Check that messages were sent
        assert bot.telegram_service.send_message.call_count >= 2
        
        # Get the second call args (stats message)
        stats_call_args = bot.telegram_service.send_message.call_args_list[1][0]
        
        # Verify that the message includes global parameters
        stats_text = stats_call_args[1]
        
        # Check for global parameters section
        assert "<b>Global Parameters:</b>" in stats_text
        assert "<b>Driver:</b> Mr Longwe" in stats_text
        assert "<b>From:</b> chigumula office" in stats_text
        assert "<b>Project:</b> Bridge Construction" in stats_text
