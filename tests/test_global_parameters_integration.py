"""Integration tests for the global parameters feature."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC

from src.main import ConstructionInventoryBot
from src.schemas import StockMovement, MovementType, BatchFormat, BatchParseResult


class TestGlobalParametersIntegration:
    """Integration tests for global parameters in batch commands."""

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
            bot.batch_stock_service.process_batch_movements = AsyncMock()
            
            # Mock command router
            bot.command_router.route_command = MagicMock()
            
            return bot

    @pytest.mark.asyncio
    async def test_validate_command_with_global_parameters(self, bot):
        """Test the /validate command with global parameters."""
        # Define test data
        chat_id = 123456789
        user_id = 987654321
        user_name = "testuser"
        command_text = "in driver: Mr Longwe, from: chigumula office, project: Bridge Construction\ncement, 50 bags\nsteel bars, 100 pieces"
        
        # Mock the parse_batch_entries method to return a predefined result
        mock_result = BatchParseResult(
            format=BatchFormat.NEWLINE,
            movements=[
                StockMovement(
                    item_name="cement",
                    movement_type=MovementType.IN,
                    quantity=50.0,
                    unit="bags",
                    signed_base_quantity=50.0,
                    user_id=str(user_id),
                    user_name=user_name,
                    timestamp=datetime.now(UTC),
                    driver_name="Mr Longwe",
                    from_location="chigumula office",
                    project="Bridge Construction"
                ),
                StockMovement(
                    item_name="steel bars",
                    movement_type=MovementType.IN,
                    quantity=100.0,
                    unit="pieces",
                    signed_base_quantity=100.0,
                    user_id=str(user_id),
                    user_name=user_name,
                    timestamp=datetime.now(UTC),
                    driver_name="Mr Longwe",
                    from_location="chigumula office",
                    project="Bridge Construction"
                )
            ],
            total_entries=2,
            valid_entries=2,
            errors=[],
            is_valid=True,
            global_parameters={
                "driver": "Mr Longwe",
                "from": "chigumula office",
                "project": "Bridge Construction"
            }
        )
        bot.command_router.parser.nlp_parser.parse_batch_entries = MagicMock(return_value=mock_result)
        
        # Call the validate command handler
        await bot.handle_validate_command(chat_id, user_id, user_name, command_text)
        
        # Check that send_message was called with the expected content
        bot.telegram_service.send_message.assert_called_once()
        call_args = bot.telegram_service.send_message.call_args[0]
        
        # Verify that the validation report contains global parameters
        assert chat_id == call_args[0]
        assert "<b>Global Parameters:</b>" in call_args[1]
        assert "<b>Driver:</b> Mr Longwe" in call_args[1]
        assert "<b>From:</b> chigumula office" in call_args[1]
        assert "<b>Project:</b> Bridge Construction" in call_args[1]
        
        # Verify that the parsed entries contain the applied global parameters
        assert "cement: 50.0 bags" in call_args[1]
        assert "by Mr Longwe" in call_args[1]
        assert "from chigumula office" in call_args[1]
        assert "project: Bridge Construction" in call_args[1]

    @pytest.mark.asyncio
    async def test_batch_validate_with_global_parameters(self, bot):
        """Test the batch validation with global parameters."""
        # Define test data
        chat_id = 123456789
        user_id = 987654321
        user_name = "testuser"
        command_text = "in driver: Mr Longwe, from: chigumula office, project: Bridge Construction\ncement, 50 bags\nsteel bars, 100 pieces"
        
        # Mock the parse_batch_entries method to return a predefined result
        mock_result = BatchParseResult(
            format=BatchFormat.NEWLINE,
            movements=[
                StockMovement(
                    item_name="cement",
                    movement_type=MovementType.IN,
                    quantity=50.0,
                    unit="bags",
                    signed_base_quantity=50.0,
                    user_id=str(user_id),
                    user_name=user_name,
                    timestamp=datetime.now(UTC),
                    driver_name="Mr Longwe",
                    from_location="chigumula office",
                    project="Bridge Construction"
                ),
                StockMovement(
                    item_name="steel bars",
                    movement_type=MovementType.IN,
                    quantity=100.0,
                    unit="pieces",
                    signed_base_quantity=100.0,
                    user_id=str(user_id),
                    user_name=user_name,
                    timestamp=datetime.now(UTC),
                    driver_name="Mr Longwe",
                    from_location="chigumula office",
                    project="Bridge Construction"
                )
            ],
            total_entries=2,
            valid_entries=2,
            errors=[],
            is_valid=True,
            global_parameters={
                "driver": "Mr Longwe",
                "from": "chigumula office",
                "project": "Bridge Construction"
            }
        )
        bot.command_router.parser.nlp_parser.parse_batch_entries = MagicMock(return_value=mock_result)
        
        # Call the validate command handler with a different command text to verify global parameters are shown
        await bot.handle_validate_command(chat_id, user_id, user_name, "in driver: Mr Longwe, from: warehouse, project: Road Construction\ncement, 30 bags")
        
        # Check that send_message was called with the expected content
        assert bot.telegram_service.send_message.call_count >= 1
        
        # Get the call args
        call_args = bot.telegram_service.send_message.call_args[0]
        assert chat_id == call_args[0]
        assert "<b>Global Parameters:</b>" in call_args[1]

    @pytest.mark.asyncio
    async def test_validate_command_with_entry_specific_override(self, bot):
        """Test validate command with entry-specific parameter override."""
        # Define test data
        chat_id = 123456789
        user_id = 987654321
        user_name = "testuser"
        command_text = "in driver: Mr Longwe, from: chigumula office, project: Bridge Construction\ncement, 50 bags\nsteel bars, 100 pieces, by Mr Smith"
        
        # Mock the parse_batch_entries method to return a predefined result
        mock_result = BatchParseResult(
            format=BatchFormat.NEWLINE,
            movements=[
                StockMovement(
                    item_name="cement",
                    movement_type=MovementType.IN,
                    quantity=50.0,
                    unit="bags",
                    signed_base_quantity=50.0,
                    user_id=str(user_id),
                    user_name=user_name,
                    timestamp=datetime.now(UTC),
                    driver_name="Mr Longwe",
                    from_location="chigumula office",
                    project="Bridge Construction"
                ),
                StockMovement(
                    item_name="steel bars",
                    movement_type=MovementType.IN,
                    quantity=100.0,
                    unit="pieces",
                    signed_base_quantity=100.0,
                    user_id=str(user_id),
                    user_name=user_name,
                    timestamp=datetime.now(UTC),
                    driver_name="Mr Smith",  # Entry-specific override
                    from_location="chigumula office",
                    project="Bridge Construction"
                )
            ],
            total_entries=2,
            valid_entries=2,
            errors=[],
            is_valid=True,
            global_parameters={
                "driver": "Mr Longwe",
                "from": "chigumula office",
                "project": "Bridge Construction"
            }
        )
        bot.command_router.parser.nlp_parser.parse_batch_entries = MagicMock(return_value=mock_result)
        
        # Call the validate command handler
        await bot.handle_validate_command(chat_id, user_id, user_name, command_text)
        
        # Check that send_message was called with the expected content
        assert bot.telegram_service.send_message.call_count >= 1
        
        # Get the call args
        call_args = bot.telegram_service.send_message.call_args[0]
        
        # Verify that both the global driver and entry-specific override are shown
        assert "by Mr Longwe" in call_args[1]
        assert "by Mr Smith" in call_args[1]
        
        # Both should use global project
        assert "project: Bridge Construction" in call_args[1]
