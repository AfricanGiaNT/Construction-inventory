"""Tests for batch command integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.services.batch_command_integration import BatchCommandIntegration
from src.services.batch_movement_processor import BatchMovementProcessor


class TestBatchCommandIntegration:
    """Test batch command integration functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_airtable = MagicMock()
        self.mock_settings = MagicMock()
        self.mock_stock_service = MagicMock()
        
        # Create batch processor
        self.batch_processor = BatchMovementProcessor(
            airtable_client=self.mock_airtable,
            settings=self.mock_settings,
            stock_service=self.mock_stock_service
        )
        
        # Create integration service
        self.integration = BatchCommandIntegration(self.batch_processor)
    
    @pytest.mark.asyncio
    async def test_process_in_command_success(self):
        """Test successful /in command processing."""
        command = """project: test, driver: test driver
Test item, 10
Another item, 5"""
        
        # Mock stock service responses
        self.mock_stock_service.stock_in = AsyncMock(return_value=(True, "Success", 0.0, 10.0))
        
        result = await self.integration.process_in_command(
            command, user_id=123, user_name="Test User"
        )
        
        assert result["status"] == "success"
        assert "Successfully processed" in result["message"]
        assert result["details"]["total_items"] == 2
        assert result["details"]["successful_items"] == 2
    
    @pytest.mark.asyncio
    async def test_process_out_command_success(self):
        """Test successful /out command processing."""
        command = """project: test, driver: test driver, to: test location
Test item, 10"""
        
        # Mock stock service responses
        self.mock_stock_service.stock_out = AsyncMock(return_value=(True, "Success", 10.0, 0.0))
        
        result = await self.integration.process_out_command(
            command, user_id=123, user_name="Test User"
        )
        
        assert result["status"] == "success"
        assert "Successfully processed" in result["message"]
        assert result["details"]["total_items"] == 1
        assert result["details"]["successful_items"] == 1
    
    @pytest.mark.asyncio
    async def test_process_in_command_partial_failure(self):
        """Test /in command with partial failures."""
        command = """project: test, driver: test driver
Valid item, 10
Invalid item, 5"""
        
        # Mock stock service to fail on "Invalid item"
        def mock_stock_in(item_name, **kwargs):
            if item_name == "Invalid item":
                return (False, "Item not found", 0.0, 0.0)
            return (True, "Success", 0.0, 10.0)
        
        self.mock_stock_service.stock_in = AsyncMock(side_effect=mock_stock_in)
        
        result = await self.integration.process_in_command(
            command, user_id=123, user_name="Test User"
        )
        
        assert result["status"] == "error"  # Batch fails completely on first error
        assert "Failed to process" in result["message"]
        assert result["details"]["total_items"] == 2
        assert result["details"]["successful_items"] == 0  # No items processed due to batch failure
        assert result["details"]["failed_items"] == 2
        assert len(result["errors"]) > 0
    
    @pytest.mark.asyncio
    async def test_process_out_command_error(self):
        """Test /out command with errors."""
        command = """invalid command format"""
        
        result = await self.integration.process_out_command(
            command, user_id=123, user_name="Test User"
        )
        
        assert result["status"] == "error"
        assert "Failed to process" in result["message"]
        assert result["details"]["total_items"] == 1
        assert result["details"]["failed_items"] == 1
        assert len(result["errors"]) > 0
    
    def test_get_help_text(self):
        """Test help text generation."""
        help_text = self.integration.get_help_text()
        
        assert "New Batch Movement Commands" in help_text
        assert "Format:" in help_text
        assert "Key Features:" in help_text
        assert "Parameters:" in help_text
        assert "Examples:" in help_text
        assert "-batch 1-" in help_text
        assert "project:" in help_text
        assert "driver:" in help_text


if __name__ == "__main__":
    pytest.main([__file__])
