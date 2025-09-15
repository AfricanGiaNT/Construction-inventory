"""Test the preview integration functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.main import ConstructionInventoryBot
from src.schemas import MovementType, Item, Unit


class TestPreviewIntegration:
    """Test preview command integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.bot = ConstructionInventoryBot()
        
        # Mock the enhanced batch processor
        self.bot.enhanced_batch_processor = MagicMock()
        self.bot.enhanced_batch_processor.get_duplicate_preview = AsyncMock()
        
        # Mock telegram service
        self.bot.telegram_service = MagicMock()
        self.bot.telegram_service.send_message = AsyncMock()
        self.bot.telegram_service.send_error_message = AsyncMock()
    
    @pytest.mark.asyncio
    async def test_preview_in_command_success(self):
        """Test successful preview IN command."""
        # Mock preview response
        preview_data = {
            "status": "success",
            "total_items": 2,
            "duplicate_count": 1,
            "non_duplicate_count": 1,
            "exact_matches": 1,
            "similar_items": 0,
            "duplicates": [{
                "item_name": "Cement 50kg",
                "quantity": 10.0,
                "existing_item": "Cement 50kg",
                "existing_quantity": 100.0,
                "similarity_score": 0.98,
                "match_type": "exact"
            }]
        }
        
        self.bot.enhanced_batch_processor.get_duplicate_preview.return_value = preview_data
        
        # Test command
        command = type('Command', (), {
            'command': 'preview_in',
            'args': ['-batch 1- project: test\nCement 50kg, 10 bags\nNew Item, 5 pieces']
        })()
        
        await self.bot.execute_command(command, chat_id=123, user_id=456, user_name="Test User", user_role="user")
        
        # Verify preview was called
        self.bot.enhanced_batch_processor.get_duplicate_preview.assert_called_once()
        
        # Verify message was sent
        self.bot.telegram_service.send_message.assert_called_once()
        call_args = self.bot.telegram_service.send_message.call_args[0]
        assert "Duplicate Preview" in call_args[1]
        assert "Total items: 2" in call_args[1]
        assert "Duplicates: 1" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_preview_out_command_success(self):
        """Test successful preview OUT command."""
        # Mock preview response
        preview_data = {
            "status": "success",
            "total_items": 1,
            "duplicate_count": 0,
            "non_duplicate_count": 1,
            "exact_matches": 0,
            "similar_items": 0,
            "duplicates": []
        }
        
        self.bot.enhanced_batch_processor.get_duplicate_preview.return_value = preview_data
        
        # Test command
        command = type('Command', (), {
            'command': 'preview_out',
            'args': ['-batch 1- project: test, to: site\nNew Item, 5 pieces']
        })()
        
        await self.bot.execute_command(command, chat_id=123, user_id=456, user_name="Test User", user_role="user")
        
        # Verify preview was called
        self.bot.enhanced_batch_processor.get_duplicate_preview.assert_called_once()
        
        # Verify message was sent
        self.bot.telegram_service.send_message.assert_called_once()
        call_args = self.bot.telegram_service.send_message.call_args[0]
        assert "Duplicate Preview" in call_args[1]
        assert "New items: 1" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_preview_command_error(self):
        """Test preview command with error."""
        # Mock error response
        preview_data = {
            "status": "error",
            "message": "Failed to parse command"
        }
        
        self.bot.enhanced_batch_processor.get_duplicate_preview.return_value = preview_data
        
        # Test command
        command = type('Command', (), {
            'command': 'preview_in',
            'args': ['invalid command format']
        })()
        
        await self.bot.execute_command(command, chat_id=123, user_id=456, user_name="Test User", user_role="user")
        
        # Verify error message was sent
        self.bot.telegram_service.send_error_message.assert_called_once()
        call_args = self.bot.telegram_service.send_error_message.call_args[0]
        assert "Failed to parse command" in call_args[1]


if __name__ == "__main__":
    pytest.main([__file__])
