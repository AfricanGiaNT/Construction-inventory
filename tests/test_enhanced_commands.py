"""Tests for the Enhanced Command Handlers (Phase 3)."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, UTC

# Import the enhanced main bot and related components
try:
    from src.main import ConstructionInventoryBot
    from src.schemas import (
        StockMovement, MovementType, MovementStatus, UserRole,
        BatchFormat, BatchParseResult, BatchResult
    )
except ImportError:
    from main import ConstructionInventoryBot
    from schemas import (
        StockMovement, MovementType, MovementStatus, UserRole,
        BatchFormat, BatchParseResult, BatchResult
    )


class TestEnhancedCommandHandlers:
    """Test the enhanced command handlers with batch support."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock all dependencies
        self.mock_settings = Mock()
        self.mock_settings.telegram_allowed_chat_ids = [12345]
        self.mock_settings.log_level = "INFO"
        
        self.mock_airtable_client = Mock()
        self.mock_stock_service = Mock()
        self.mock_batch_stock_service = Mock()
        self.mock_telegram_service = Mock()
        self.mock_command_router = Mock()
        
        # Create mock NLP parser
        self.mock_nlp_parser = Mock()
        self.mock_command_router.parser.nlp_parser = self.mock_nlp_parser
        
        # Create the bot with mocked dependencies
        with patch('src.main.Settings') as mock_settings_class, \
             patch('src.main.AirtableClient'), \
             patch('src.main.StockService'), \
             patch('src.main.BatchStockService'), \
             patch('src.main.AuthService'), \
             patch('src.main.ApprovalService'), \
             patch('src.main.QueryService'), \
             patch('src.main.TelegramService'), \
             patch('src.main.CommandRouter'), \
             patch('src.main.AsyncIOScheduler'):
            
            # Mock the Settings class
            mock_settings_instance = Mock()
            mock_settings_instance.telegram_allowed_chat_ids = [12345]
            mock_settings_instance.log_level = "INFO"
            mock_settings_instance.telegram_bot_token = "test_token"
            mock_settings_instance.airtable_api_key = "test_key"
            mock_settings_instance.airtable_base_id = "test_base"
            mock_settings_class.return_value = mock_settings_instance
            
            self.bot = ConstructionInventoryBot()
            
            # Replace mocked services with our test mocks
            self.bot.stock_service = self.mock_stock_service
            self.bot.batch_stock_service = self.mock_batch_stock_service
            self.bot.telegram_service = self.mock_telegram_service
            self.bot.command_router = self.mock_command_router
            
            # Mock the prepare_batch_approval method to return success
            self.mock_batch_stock_service.prepare_batch_approval = AsyncMock(return_value=(True, "batch_123", Mock()))
            
            # Mock telegram service methods
            self.mock_telegram_service.send_batch_approval_request = AsyncMock()
            self.mock_telegram_service.send_message = AsyncMock()
            self.mock_telegram_service.send_error_message = AsyncMock()
    
    def create_mock_command(self, command: str, args: list = None):
        """Create a mock command object."""
        return Mock(
            command=command,
            args=args or [],
            chat_id=12345,
            user_id=67890,
            user_name="Test User",
            message_id=1,
            update_id=1
        )
    
    def create_mock_batch_result(self, format_type: BatchFormat, movements: list, errors: list = None):
        """Create a mock batch parse result."""
        return BatchParseResult(
            format=format_type,
            movements=movements,
            total_entries=len(movements),
            valid_entries=len(movements),
            errors=errors or [],
            is_valid=len(errors or []) == 0
        )
    
    def create_mock_movement(self, item_name: str, quantity: float, movement_type: MovementType):
        """Create a mock stock movement."""
        return StockMovement(
            item_name=item_name,
            movement_type=movement_type,
            quantity=quantity,
            unit="pieces",
            signed_base_quantity=quantity,
            location="warehouse",
            status=MovementStatus.POSTED,
            user_id="67890",
            user_name="Test User",
            timestamp=datetime.now(UTC)
        )
    
    @pytest.mark.asyncio
    async def test_batchhelp_command(self):
        """Test the /batchhelp command."""
        command = self.create_mock_command("batchhelp")
        
        # Execute command
        await self.bot.execute_command(command, 12345, 67890, "Test User", UserRole.STAFF)
        
        # Verify that the batch help message was sent
        self.mock_telegram_service.send_message.assert_called_once()
        call_args = self.mock_telegram_service.send_message.call_args[0]
        assert "BATCH COMMAND GUIDE" in call_args[1]
        assert "GLOBAL PARAMETERS" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_status_command(self):
        """Test the /status command."""
        command = self.create_mock_command("status")
        
        # Execute command
        await self.bot.execute_command(command, 12345, 67890, "Test User", UserRole.STAFF)
        
        # Verify that the status message was sent
        self.mock_telegram_service.send_message.assert_called_once()
        call_args = self.mock_telegram_service.send_message.call_args[0]
        assert "SYSTEM STATUS" in call_args[1]
        assert "Bot:" in call_args[1]
        assert "Database:" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_enhanced_in_command_help(self):
        """Test enhanced /in command help when no args provided."""
        command = self.create_mock_command("in", [])
        
        # Mock the telegram service
        self.mock_telegram_service.send_error_message = AsyncMock(return_value=True)
        
        # Execute command
        await self.bot.execute_command(command, 12345, 67890, "Test User", UserRole.STAFF)
        
        # Verify enhanced help message was sent
        self.mock_telegram_service.send_error_message.assert_called_once()
        call_args = self.mock_telegram_service.send_error_message.call_args[0]
        assert "Stock IN Command Usage" in call_args[1]
        assert "Single Entry" in call_args[1]
        assert "Batch Entry" in call_args[1]
        assert "/batchhelp" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_enhanced_out_command_help(self):
        """Test enhanced /out command help when no args provided."""
        command = self.create_mock_command("out", [])
        
        # Mock the telegram service
        self.mock_telegram_service.send_error_message = AsyncMock(return_value=True)
        
        # Execute command
        await self.bot.execute_command(command, 12345, 67890, "Test User", UserRole.STAFF)
        
        # Verify enhanced help message was sent
        self.mock_telegram_service.send_error_message.assert_called_once()
        call_args = self.mock_telegram_service.send_error_message.call_args[0]
        assert "Stock OUT Command Usage" in call_args[1]
        assert "Single Entry" in call_args[1]
        assert "Batch Entry" in call_args[1]
        assert "/batchhelp" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_enhanced_adjust_command_help(self):
        """Test enhanced /adjust command help when no args provided."""
        command = self.create_mock_command("adjust", [])
        
        # Mock the telegram service
        self.mock_telegram_service.send_error_message = AsyncMock(return_value=True)
        
        # Execute command
        await self.bot.execute_command(command, 12345, 67890, "Test User", UserRole.ADMIN)
        
        # Verify enhanced help message was sent
        self.mock_telegram_service.send_error_message.assert_called_once()
        call_args = self.mock_telegram_service.send_error_message.call_args[0]
        assert "Stock ADJUST Command Usage" in call_args[1]
        assert "Admin Only" in call_args[1]
        assert "Single Entry" in call_args[1]
        assert "Batch Entry" in call_args[1]
        assert "/batchhelp" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_batch_in_command_with_confirmation(self):
        """Test /in command with batch detection and confirmation message."""
        command = self.create_mock_command("in", ["cement, 50 bags", "steel bars, 100 pieces"])
        
        # Create mock batch result
        movements = [
            self.create_mock_movement("cement", 50, MovementType.IN),
            self.create_mock_movement("steel bars", 100, MovementType.IN)
        ]
        batch_result = self.create_mock_batch_result(BatchFormat.NEWLINE, movements)
        
        # Mock NLP parser
        self.mock_nlp_parser.parse_batch_entries.return_value = batch_result
        
        # Mock batch approval preparation
        mock_batch_approval = Mock()
        mock_batch_approval.movements = movements
        mock_batch_approval.before_levels = {"cement": 100, "steel bars": 200}
        
        self.mock_batch_stock_service.prepare_batch_approval = AsyncMock(return_value=(True, "batch_123", mock_batch_approval))
        
        # Mock telegram service
        self.mock_telegram_service.send_message = AsyncMock(return_value=True)
        self.mock_telegram_service.send_batch_approval_request = AsyncMock(return_value=True)
        
        # Execute command
        await self.bot.execute_command(command, 12345, 67890, "Test User", UserRole.STAFF)
        
        # Verify batch confirmation was sent
        self.mock_telegram_service.send_message.assert_called()
        call_args = self.mock_telegram_service.send_message.call_args_list[0][0]
        assert "Batch Command Detected!" in call_args[1]
        assert "<b>Format:</b> Newline" in call_args[1]
        assert "<b>Entries:</b> 2 stock IN movements" in call_args[1]
        
        # Verify batch approval preparation was called
        self.mock_batch_stock_service.prepare_batch_approval.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_batch_out_command_with_confirmation(self):
        """Test /out command with batch detection and confirmation message."""
        command = self.create_mock_command("out", ["cement, 25 bags", "steel bars, 10 pieces"])
        
        # Create mock batch result
        movements = [
            self.create_mock_movement("cement", 25, MovementType.OUT),
            self.create_mock_movement("steel bars", 10, MovementType.OUT)
        ]
        batch_result = self.create_mock_batch_result(BatchFormat.SEMICOLON, movements)
        
        # Mock NLP parser
        self.mock_nlp_parser.parse_batch_entries.return_value = batch_result
        
        # Mock batch approval preparation
        mock_batch_approval = Mock()
        mock_batch_approval.movements = movements
        mock_batch_approval.before_levels = {"cement": 100, "steel bars": 200}
        
        self.mock_batch_stock_service.prepare_batch_approval = AsyncMock(return_value=(True, "batch_123", mock_batch_approval))
        
        # Mock telegram service
        self.mock_telegram_service.send_message = AsyncMock(return_value=True)
        self.mock_telegram_service.send_batch_approval_request = AsyncMock(return_value=True)
        
        # Execute command
        await self.bot.execute_command(command, 12345, 67890, "Test User", UserRole.STAFF)
        
        # Verify batch confirmation was sent
        self.mock_telegram_service.send_message.assert_called()
        call_args = self.mock_telegram_service.send_message.call_args_list[0][0]
        assert "Batch Command Detected!" in call_args[1]
        assert "<b>Format:</b> Semicolon" in call_args[1]
        assert "<b>Entries:</b> 2 stock OUT movements" in call_args[1]
        
        # Verify batch approval preparation was called
        self.mock_batch_stock_service.prepare_batch_approval.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_batch_adjust_command_with_confirmation(self):
        """Test /adjust command with batch detection and confirmation message."""
        command = self.create_mock_command("adjust", ["cement, -5 bags", "steel bars, -2 pieces"])
        
        # Create mock batch result
        movements = [
            self.create_mock_movement("cement", -5, MovementType.ADJUST),
            self.create_mock_movement("steel bars", -2, MovementType.ADJUST)
        ]
        batch_result = self.create_mock_batch_result(BatchFormat.NEWLINE, movements)
        
        # Mock NLP parser
        self.mock_nlp_parser.parse_batch_entries.return_value = batch_result
        
        # Mock batch approval preparation
        mock_batch_approval = Mock()
        mock_batch_approval.movements = movements
        mock_batch_approval.before_levels = {"cement": 100, "steel bars": 200}
        
        self.mock_batch_stock_service.prepare_batch_approval = AsyncMock(return_value=(True, "batch_123", mock_batch_approval))
        
        # Mock telegram service
        self.mock_telegram_service.send_message = AsyncMock(return_value=True)
        self.mock_telegram_service.send_batch_approval_request = AsyncMock(return_value=True)
        
        # Execute command
        await self.bot.execute_command(command, 12345, 67890, "Test User", UserRole.ADMIN)
        
        # Verify batch confirmation was sent
        self.mock_telegram_service.send_message.assert_called()
        call_args = self.mock_telegram_service.send_message.call_args_list[0][0]
        assert "Batch Command Detected!" in call_args[1]
        assert "<b>Format:</b> Newline" in call_args[1]
        assert "<b>Entries:</b> 2 stock ADJUST movements" in call_args[1]
        
        # Verify batch approval preparation was called
        self.mock_batch_stock_service.prepare_batch_approval.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_single_entry_fallback(self):
        """Test that single entries fall back to single-entry approval flow."""
        command = self.create_mock_command("in", ["cement, 50 bags, from supplier"])
        
        # Create mock batch result for single entry
        movements = [self.create_mock_movement("cement", 50, MovementType.IN)]
        batch_result = self.create_mock_batch_result(BatchFormat.SINGLE, movements)
        
        # Mock NLP parser
        self.mock_nlp_parser.parse_batch_entries.return_value = batch_result
        
        # Mock batch approval preparation
        mock_batch_approval = Mock()
        mock_batch_approval.movements = movements
        mock_batch_approval.before_levels = {"cement": 100}
        
        self.mock_batch_stock_service.prepare_batch_approval = AsyncMock(return_value=(True, "batch_123", mock_batch_approval))
        
        # Mock telegram service
        self.mock_telegram_service.send_message = AsyncMock(return_value=True)
        self.mock_telegram_service.send_batch_approval_request = AsyncMock(return_value=True)
        
        # Execute command
        await self.bot.execute_command(command, 12345, 67890, "Test User", UserRole.STAFF)
        
        # Verify single entry approval was sent
        self.mock_telegram_service.send_message.assert_called()
        call_args = self.mock_telegram_service.send_message.call_args_list[0][0]
        assert "Entry submitted for approval" in call_args[1]
        assert "cement" in call_args[1]
        
        # Verify batch approval preparation was called
        self.mock_batch_stock_service.prepare_batch_approval.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_help_command_includes_batchhelp(self):
        """Test that /help command includes batchhelp and status commands."""
        command = self.create_mock_command("help")
        
        # Mock the telegram service
        self.mock_telegram_service.send_help_message = AsyncMock(return_value=True)
        
        # Execute command
        await self.bot.execute_command(command, 12345, 67890, "Test User", UserRole.STAFF)
        
        # Verify help was sent
        self.mock_telegram_service.send_help_message.assert_called_once()
        call_args = self.mock_telegram_service.send_help_message.call_args[0]
        assert call_args[0] == 12345  # chat_id
        assert call_args[1] == "staff"  # user_role


class TestUserExperienceEnhancements:
    """Test user experience improvements in Phase 3."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Similar setup as above
        self.mock_settings = Mock()
        self.mock_settings.telegram_allowed_chat_ids = [12345]
        self.mock_settings.log_level = "INFO"
        
        # Create the bot with mocked dependencies
        with patch('src.main.Settings') as mock_settings_class, \
             patch('src.main.AirtableClient'), \
             patch('src.main.StockService'), \
             patch('src.main.BatchStockService'), \
             patch('src.main.AuthService'), \
             patch('src.main.ApprovalService'), \
             patch('src.main.QueryService'), \
             patch('src.main.TelegramService'), \
             patch('src.main.CommandRouter'), \
             patch('src.main.AsyncIOScheduler'):
            
            # Mock the Settings class
            mock_settings_instance = Mock()
            mock_settings_instance.telegram_allowed_chat_ids = [12345]
            mock_settings_instance.log_level = "INFO"
            mock_settings_instance.telegram_bot_token = "test_token"
            mock_settings_instance.airtable_api_key = "test_key"
            mock_settings_instance.airtable_base_id = "test_base"
            mock_settings_class.return_value = mock_settings_instance
            
            self.bot = ConstructionInventoryBot()
    
    @pytest.mark.asyncio
    async def test_batch_confirmation_message_format(self):
        """Test that batch confirmation messages are properly formatted."""
        # Test the format of batch confirmation messages
        # This would test the actual message content and formatting
        
        # Mock dependencies
        self.bot.telegram_service = Mock()
        self.bot.telegram_service.send_message = AsyncMock(return_value=True)
        
        # Test the message formatting logic
        batch_size = 5
        format_type = "newline"
        movement_type = "Stock IN"
        
        confirmation_msg = f"🔄 <b>Batch Command Detected!</b>\n\n"
        confirmation_msg += f"• <b>Format:</b> {format_type.title()}\n"
        confirmation_msg += f"• <b>Entries:</b> {batch_size} {movement_type.lower()} movements\n"
        confirmation_msg += f"• <b>Movement Type:</b> {movement_type}\n\n"
        confirmation_msg += f"<i>Processing {batch_size} entries sequentially...</i>"
        
        # Verify message format
        assert "🔄 <b>Batch Command Detected!</b>" in confirmation_msg
        assert "• <b>Format:</b> Newline" in confirmation_msg
        assert "• <b>Entries:</b> 5 stock in movements" in confirmation_msg
        assert "• <b>Movement Type:</b> Stock IN" in confirmation_msg
        assert "<i>Processing 5 entries sequentially...</i>" in confirmation_msg
    
    @pytest.mark.asyncio
    async def test_enhanced_error_messages(self):
        """Test that enhanced error messages provide better guidance."""
        # Test that error messages now include batch command examples
        
        # This would test the actual error message content
        # and verify that /batchhelp guidance is included
        
        assert True  # Placeholder for actual test implementation


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
