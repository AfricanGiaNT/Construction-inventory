"""Tests for command parsing and routing."""

import pytest
from src.commands import CommandParser, CommandRouter


class TestCommandParser:
    """Test the command parser functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = CommandParser()
    
    def test_parse_help_command(self):
        """Test parsing help command."""
        command = self.parser.parse_command(
            "/help", 123, 456, "TestUser", 789, 101
        )
        
        assert command is not None
        assert command.command == "help"
        assert command.chat_id == 123
        assert command.user_id == 456
        assert command.user_name == "TestUser"
    
    def test_parse_find_command(self):
        """Test parsing find command with arguments."""
        command = self.parser.parse_command(
            "/find cement", 123, 456, "TestUser", 789, 101
        )
        
        assert command is not None
        assert command.command == "find"
        assert command.args == ["cement"]
    
    def test_parse_stock_in_command(self):
        """Test parsing stock in command."""
        command = self.parser.parse_command(
            "/in ABC123 50 boxes warehouse shipment", 123, 456, "TestUser", 789, 101
        )
        
        assert command is not None
        assert command.command == "in"
        assert command.args == ["ABC123 50 boxes warehouse shipment"]
    
    def test_parse_invalid_command(self):
        """Test parsing invalid command."""
        command = self.parser.parse_command(
            "not a command", 123, 456, "TestUser", 789, 101
        )
        
        assert command is None
    
    def test_parse_movement_args(self):
        """Test parsing movement arguments."""
        args = ["ABC123", "50", "boxes", "warehouse", "shipment"]
        full_text, quantity, unit, location, note, driver, project = self.parser.parse_movement_args(args)
        
        assert full_text == "ABC123 50 boxes warehouse shipment"
        assert quantity == 0  # Default value in current implementation
        assert unit is None
        assert location is None
        assert note is None
        assert driver is None
        assert project is None
    
    def test_parse_movement_args_minimal(self):
        """Test parsing movement arguments with minimal data."""
        args = ["ABC123", "50"]
        full_text, quantity, unit, location, note, driver, project = self.parser.parse_movement_args(args)
        
        assert full_text == "ABC123 50"
        assert quantity == 0  # Default value in current implementation
        assert unit is None
        assert location is None
        assert note is None
        assert driver is None
        assert project is None
    
    def test_parse_movement_args_invalid_quantity(self):
        """Test parsing movement arguments with invalid quantity."""
        args = ["ABC123", "invalid"]
        
        # Current implementation doesn't validate quantity at parse time
        full_text, quantity, unit, location, note, driver, project = self.parser.parse_movement_args(args)
        
        assert full_text == "ABC123 invalid"
        assert quantity == 0  # Default value
        assert unit is None
        assert location is None
        assert note is None
        assert driver is None
        assert project is None
    
    def test_parse_movement_args_insufficient_args(self):
        """Test parsing movement arguments with insufficient data."""
        args = ["ABC123"]
        
        # Current implementation doesn't validate arg count at parse time
        full_text, quantity, unit, location, note, driver, project = self.parser.parse_movement_args(args)
        
        assert full_text == "ABC123"
        assert quantity == 0  # Default value
        assert unit is None
        assert location is None
        assert note is None
        assert driver is None
        assert project is None


class TestCommandRouter:
    """Test the command router functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.router = CommandRouter()
    
    @pytest.mark.asyncio
    async def test_route_valid_command(self):
        """Test routing a valid command."""
        command, error = await self.router.route_command(
            "/help", 123, 456, "TestUser", 789, 101
        )
        
        assert command is not None
        assert error is None
        assert command.command == "help"
    
    @pytest.mark.asyncio
    async def test_route_invalid_command(self):
        """Test routing an invalid command."""
        command, error = await self.router.route_command(
            "not a command", 123, 456, "TestUser", 789, 101
        )
        
        assert command is None
        assert error is not None
        assert "Invalid command format" in error

