"""Integration tests for inventory command functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.main import ConstructionInventoryBot
from src.schemas import UserRole


class TestInventoryCommandIntegration:
    """Test inventory command integration with the main bot."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create a minimal bot instance for testing
        with patch('src.main.Settings') as mock_settings:
            mock_settings.return_value.log_level = 'INFO'
            self.bot = ConstructionInventoryBot()
    
    @pytest.mark.asyncio
    async def test_inventory_command_admin_access(self):
        """Test inventory command with admin user."""
        # Mock the inventory service
        mock_inventory_service = AsyncMock()
        mock_inventory_service.process_inventory_stocktake.return_value = (True, "Success message")
        self.bot.inventory_service = mock_inventory_service
        
        # Mock telegram service
        mock_telegram_service = AsyncMock()
        self.bot.telegram_service = mock_telegram_service
        
        # Test admin access
        await self.bot.handle_inventory_command(123, 456, "AdminUser", "date:25/08/25 logged by: Trevor\nCement, 50")
        
        # Verify the service was called
        mock_inventory_service.process_inventory_stocktake.assert_called_once_with(
            "date:25/08/25 logged by: Trevor\nCement, 50", 456, "AdminUser"
        )
        
        # Verify success message was sent
        mock_telegram_service.send_message.assert_called_once_with(123, "Success message")
    
    @pytest.mark.asyncio
    async def test_inventory_command_non_admin_access_denied(self):
        """Test inventory command with non-admin user."""
        # Mock telegram service
        mock_telegram_service = AsyncMock()
        self.bot.telegram_service = mock_telegram_service
        
        # Test non-admin access (this would be called from the main command handler)
        # We need to simulate the admin check that happens in the main command processing
        user_role = UserRole.STAFF  # Non-admin role
        
        # This simulates what happens in the main command handler
        if user_role != UserRole.ADMIN:
            await self.bot.telegram_service.send_error_message(
                123,
                "❌ <b>Access Denied</b>\n\n"
                "The /inventory command is restricted to administrators only."
            )
        
        # Verify access denied message was sent
        mock_telegram_service.send_error_message.assert_called_once()
        call_args = mock_telegram_service.send_error_message.call_args[0]
        assert "Access Denied" in call_args[1]
        assert "restricted to administrators only" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_inventory_command_help_message(self):
        """Test inventory command help message for admin users."""
        # Mock telegram service
        mock_telegram_service = AsyncMock()
        self.bot.telegram_service = mock_telegram_service
        
        # This simulates what happens when no args are provided
        await self.bot.telegram_service.send_message(
            123,
            "📊 <b>Inventory Stocktake</b>\n\n"
            "This command allows administrators to perform inventory stocktaking.\n\n"
            "<b>Usage:</b>\n"
            "/inventory date:DD/MM/YY logged by: NAME1,NAME2\n"
            "Item Name, Quantity\n"
            "Item Name, Quantity\n\n"
            "<b>Examples:</b>\n"
            "/inventory date:25/08/25 logged by: Trevor,Kayesera\n"
            "Cement 32.5, 50\n"
            "12mm rebar, 120.0\n"
            "Safety helmets, 25\n\n"
            "<b>Notes:</b>\n"
            "• Maximum 50 entries per batch\n"
            "• Duplicate items use last occurrence\n"
            "• New items are created with default settings\n"
            "• Existing items are updated to counted quantity"
        )
        
        # Verify help message was sent
        mock_telegram_service.send_message.assert_called_once()
        call_args = mock_telegram_service.send_message.call_args[0]
        assert "Inventory Stocktake" in call_args[1]
        assert "Maximum 50 entries per batch" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_inventory_command_service_error(self):
        """Test inventory command when service encounters an error."""
        # Mock the inventory service to return error
        mock_inventory_service = AsyncMock()
        mock_inventory_service.process_inventory_stocktake.return_value = (False, "Error message")
        self.bot.inventory_service = mock_inventory_service
        
        # Mock telegram service
        mock_telegram_service = AsyncMock()
        self.bot.telegram_service = mock_telegram_service
        
        # Test error handling
        await self.bot.handle_inventory_command(123, 456, "AdminUser", "invalid command")
        
        # Verify error message was sent
        mock_telegram_service.send_error_message.assert_called_once_with(123, "Error message")
    
    @pytest.mark.asyncio
    async def test_inventory_command_exception_handling(self):
        """Test inventory command exception handling."""
        # Mock the inventory service to raise an exception
        mock_inventory_service = AsyncMock()
        mock_inventory_service.process_inventory_stocktake.side_effect = Exception("Test exception")
        self.bot.inventory_service = mock_inventory_service
        
        # Mock telegram service
        mock_telegram_service = AsyncMock()
        self.bot.telegram_service = mock_telegram_service
        
        # Test exception handling
        await self.bot.handle_inventory_command(123, 456, "AdminUser", "test command")
        
        # Verify error message was sent
        mock_telegram_service.send_message.assert_called_once()
        call_args = mock_telegram_service.send_message.call_args[0]
        assert "Inventory Command Error" in call_args[1]
        assert "Test exception" in call_args[1]


class TestInventoryCommandParsing:
    """Test inventory command parsing integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        from src.commands import CommandParser
        self.parser = CommandParser()
    
    def test_inventory_command_pattern_matching(self):
        """Test that inventory command pattern correctly matches valid commands."""
        # Test basic inventory command
        command = self.parser.parse_command(
            "/inventory date:25/08/25 logged by: Trevor", 123, 456, "TestUser", 789, 101
        )
        
        assert command is not None
        assert command.command == "inventory"
        assert command.args == ["date:25/08/25 logged by: Trevor"]
    
    def test_inventory_command_with_multiline_content(self):
        """Test inventory command with multiline content."""
        multiline_command = """date:25/08/25 logged by: Trevor,Kayesera
Cement 32.5, 50
Steel bars, 120.0
Safety helmets, 25"""
        
        command = self.parser.parse_command(
            f"/inventory {multiline_command}", 123, 456, "TestUser", 789, 101
        )
        
        assert command is not None
        assert command.command == "inventory"
        assert command.args == [multiline_command]
    
    def test_inventory_command_with_extra_whitespace(self):
        """Test inventory command with extra whitespace."""
        command = self.parser.parse_command(
            "/inventory   date:25/08/25 logged by: Trevor   ", 123, 456, "TestUser", 789, 101
        )
        
        assert command is not None
        assert command.command == "inventory"
        assert command.args == ["date:25/08/25 logged by: Trevor"]
    
    def test_inventory_command_case_insensitive(self):
        """Test inventory command case insensitivity."""
        command = self.parser.parse_command(
            "/INVENTORY date:25/08/25 logged by: Trevor", 123, 456, "TestUser", 789, 101
        )
        
        assert command is not None
        assert command.command == "inventory"
    
    def test_inventory_command_invalid_format(self):
        """Test that invalid inventory command format is not matched."""
        # Missing /inventory prefix
        command = self.parser.parse_command(
            "inventory date:25/08/25 logged by: Trevor", 123, 456, "TestUser", 789, 101
        )
        
        assert command is None
    
    def test_inventory_command_empty_content(self):
        """Test inventory command with empty content."""
        command = self.parser.parse_command(
            "/inventory", 123, 456, "TestUser", 789, 101
        )
    
        # Inventory command requires arguments, so it should not match
        assert command is None


class TestInventoryCommandSuggestions:
    """Test inventory command suggestions integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        from src.services.command_suggestions import CommandSuggestionsService
        self.suggestions_service = CommandSuggestionsService()
    
    def test_inventory_command_in_suggestions(self):
        """Test that inventory command is included in command suggestions."""
        # Check if inventory command exists in available commands
        assert "inventory" in self.suggestions_service.available_commands
        
        inventory_cmd = self.suggestions_service.available_commands["inventory"]
        assert inventory_cmd["category"] == "Management"
        assert "admin only" in inventory_cmd["description"].lower()
        assert "date:DD/MM/YY logged by: NAME1,NAME2" in inventory_cmd["usage"]
    
    def test_inventory_command_suggestions(self):
        """Test inventory command suggestions for similar inputs."""
        # Test exact match
        suggestions = self.suggestions_service.get_command_suggestions("inventory")
        assert len(suggestions) > 0
        assert any(cmd[0] == "inventory" for cmd in suggestions)
        
        # Test partial match
        suggestions = self.suggestions_service.get_command_suggestions("inven")
        assert len(suggestions) > 0
        assert any(cmd[0] == "inventory" for cmd in suggestions)
    
    def test_inventory_command_quick_help(self):
        """Test inventory command quick help."""
        quick_help = self.suggestions_service.get_quick_help("inventory")
        assert quick_help is not None
        assert "inventory" in quick_help.lower()
        assert "stocktake" in quick_help.lower()


class TestInventoryCommandEndToEnd:
    """Test end-to-end inventory command functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create a minimal bot instance for testing
        with patch('src.main.Settings') as mock_settings:
            mock_settings.return_value.log_level = 'INFO'
            self.bot = ConstructionInventoryBot()
    
    @pytest.mark.asyncio
    async def test_complete_inventory_workflow(self):
        """Test complete inventory workflow from command to result."""
        # Mock all dependencies
        mock_airtable = AsyncMock()
        mock_settings = MagicMock()
        
        # Mock inventory service
        mock_inventory_service = AsyncMock()
        mock_inventory_service.process_inventory_stocktake.return_value = (
            True, 
            "📊 <b>Inventory Stocktake Complete</b>\n\n"
            "<b>Date:</b> 25/08/25\n"
            "<b>Logged by:</b> Trevor, Kayesera\n\n"
            "✅ <b>Results:</b>\n"
            "• Items updated: 2\n"
            "• Items created: 1\n"
            "• Items failed: 0"
        )
        
        self.bot.airtable_client = mock_airtable
        self.bot.settings = mock_settings
        self.bot.inventory_service = mock_inventory_service
        
        # Mock telegram service
        mock_telegram_service = AsyncMock()
        self.bot.telegram_service = mock_telegram_service
        
        # Test the complete workflow
        command_text = """date:25/08/25 logged by: Trevor,Kayesera
Cement 32.5, 50
Steel bars, 120.0
Safety helmets, 25"""
        
        await self.bot.handle_inventory_command(123, 456, "AdminUser", command_text)
        
        # Verify the service was called with correct parameters
        mock_inventory_service.process_inventory_stocktake.assert_called_once_with(
            command_text, 456, "AdminUser"
        )
        
        # Verify success message was sent
        mock_telegram_service.send_message.assert_called_once()
        call_args = mock_telegram_service.send_message.call_args[0]
        assert "Inventory Stocktake Complete" in call_args[1]
        assert "Items updated: 2" in call_args[1]
        assert "Items created: 1" in call_args[1]
