"""Tests for duplicate detection callback handlers in main bot."""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from telegram import CallbackQuery, User, Message, Chat

from src.main import ConstructionInventoryBot


class TestDuplicateCallbackHandlers:
    """Test cases for duplicate detection callback handlers."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot instance."""
        bot = Mock()
        bot.answer_callback_query = AsyncMock()
        bot.edit_message_text = AsyncMock()
        return bot
    
    @pytest.fixture
    def mock_telegram_service(self):
        """Create a mock TelegramService."""
        service = Mock()
        service.answer_callback_query = AsyncMock()
        service.send_message = AsyncMock()
        service.send_duplicate_confirmation_result = AsyncMock()
        return service
    
    @pytest.fixture
    def mock_duplicate_detection_service(self):
        """Create a mock DuplicateDetectionService."""
        service = Mock()
        return service
    
    @pytest.fixture
    def bot_instance(self, mock_bot, mock_telegram_service, mock_duplicate_detection_service):
        """Create a ConstructionInventoryBot instance with mocked dependencies."""
        bot = ConstructionInventoryBot()
        bot.bot = mock_bot
        bot.telegram_service = mock_telegram_service
        bot.duplicate_detection_service = mock_duplicate_detection_service
        return bot
    
    @pytest.fixture
    def sample_callback_query(self):
        """Create a sample callback query for testing."""
        # Create mock user
        user = Mock(spec=User)
        user.id = 12345
        user.first_name = "John"
        user.last_name = "Doe"
        user.username = "johndoe"
        
        # Create mock chat
        chat = Mock(spec=Chat)
        chat.id = 67890
        
        # Create mock message
        message = Mock(spec=Message)
        message.chat = chat
        message.message_id = 1
        message.text = "Test message"
        
        # Create mock callback query
        callback_query = Mock(spec=CallbackQuery)
        callback_query.id = "callback_123"
        callback_query.from_user = user
        callback_query.message = message
        callback_query.data = "confirm_duplicates"
        
        return callback_query
    
    @pytest.mark.asyncio
    async def test_handle_duplicate_confirmation_callback_confirm(self, bot_instance, sample_callback_query):
        """Test handling confirm duplicates callback."""
        # Set up the callback query
        sample_callback_query.data = "confirm_duplicates"
        
        # Call the handler
        await bot_instance.handle_duplicate_confirmation_callback(sample_callback_query, "confirm_duplicates")
        
        # Verify that answer_callback_query was called
        bot_instance.telegram_service.answer_callback_query.assert_called_once()
        
        # Verify that edit_message_text was called
        bot_instance.bot.edit_message_text.assert_called_once()
        
        # Verify that send_duplicate_confirmation_result was called
        bot_instance.telegram_service.send_duplicate_confirmation_result.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_duplicate_confirmation_callback_cancel(self, bot_instance, sample_callback_query):
        """Test handling cancel duplicates callback."""
        # Set up the callback query
        sample_callback_query.data = "cancel_duplicates"
        
        # Call the handler
        await bot_instance.handle_duplicate_confirmation_callback(sample_callback_query, "cancel_duplicates")
        
        # Verify that answer_callback_query was called
        bot_instance.telegram_service.answer_callback_query.assert_called_once()
        
        # Verify that edit_message_text was called
        bot_instance.bot.edit_message_text.assert_called_once()
        
        # Verify that send_duplicate_confirmation_result was NOT called
        bot_instance.telegram_service.send_duplicate_confirmation_result.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_duplicate_confirmation_callback_show_all(self, bot_instance, sample_callback_query):
        """Test handling show all duplicates callback."""
        # Set up the callback query
        sample_callback_query.data = "show_all_duplicates"
        
        # Call the handler
        await bot_instance.handle_duplicate_confirmation_callback(sample_callback_query, "show_all_duplicates")
        
        # Verify that answer_callback_query was called
        bot_instance.telegram_service.answer_callback_query.assert_called_once()
        
        # Verify that send_message was called
        bot_instance.telegram_service.send_message.assert_called_once()
        
        # Verify that edit_message_text was NOT called
        bot_instance.bot.edit_message_text.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_duplicate_confirmation_callback_unknown_action(self, bot_instance, sample_callback_query):
        """Test handling unknown action callback."""
        # Set up the callback query
        sample_callback_query.data = "unknown_action"
        
        # Call the handler
        await bot_instance.handle_duplicate_confirmation_callback(sample_callback_query, "unknown_action")
        
        # Verify that answer_callback_query was called with error message
        bot_instance.telegram_service.answer_callback_query.assert_called_once()
        call_args = bot_instance.telegram_service.answer_callback_query.call_args
        assert "Unknown duplicate action" in call_args[0][1]
        assert call_args[1]['show_alert'] == True  # show_alert=True
    
    @pytest.mark.asyncio
    async def test_process_duplicate_confirmation(self, bot_instance, sample_callback_query):
        """Test processing duplicate confirmation."""
        # Call the method
        await bot_instance._process_duplicate_confirmation(sample_callback_query, "John Doe")
        
        # Verify that answer_callback_query was called
        bot_instance.telegram_service.answer_callback_query.assert_called_once()
        call_args = bot_instance.telegram_service.answer_callback_query.call_args
        assert "Duplicates confirmed and processed!" in call_args[0][1]
        
        # Verify that edit_message_text was called
        bot_instance.bot.edit_message_text.assert_called_once()
        
        # Verify that send_duplicate_confirmation_result was called
        bot_instance.telegram_service.send_duplicate_confirmation_result.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_duplicate_cancellation(self, bot_instance, sample_callback_query):
        """Test processing duplicate cancellation."""
        # Call the method
        await bot_instance._process_duplicate_cancellation(sample_callback_query, "John Doe")
        
        # Verify that answer_callback_query was called
        bot_instance.telegram_service.answer_callback_query.assert_called_once()
        call_args = bot_instance.telegram_service.answer_callback_query.call_args
        assert "Duplicates cancelled" in call_args[0][1]
        
        # Verify that edit_message_text was called
        bot_instance.bot.edit_message_text.assert_called_once()
        
        # Verify that send_duplicate_confirmation_result was NOT called
        bot_instance.telegram_service.send_duplicate_confirmation_result.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_show_all_duplicate_matches(self, bot_instance, sample_callback_query):
        """Test showing all duplicate matches."""
        # Call the method
        await bot_instance._show_all_duplicate_matches(sample_callback_query, "John Doe")
        
        # Verify that answer_callback_query was called
        bot_instance.telegram_service.answer_callback_query.assert_called_once()
        call_args = bot_instance.telegram_service.answer_callback_query.call_args
        assert "Showing all duplicate matches" in call_args[0][1]
        
        # Verify that send_message was called
        bot_instance.telegram_service.send_message.assert_called_once()
        
        # Verify that edit_message_text was NOT called
        bot_instance.bot.edit_message_text.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_duplicate_confirmation_callback_error_handling(self, bot_instance, sample_callback_query):
        """Test error handling in duplicate confirmation callback."""
        # Mock an exception in the handler
        bot_instance.telegram_service.answer_callback_query.side_effect = Exception("Test error")
        
        # Call the handler
        await bot_instance.handle_duplicate_confirmation_callback(sample_callback_query, "confirm_duplicates")
        
        # Should not raise an exception
        # The error should be caught and handled gracefully
    
    @pytest.mark.asyncio
    async def test_process_duplicate_confirmation_error_handling(self, bot_instance, sample_callback_query):
        """Test error handling in process duplicate confirmation."""
        # Mock an exception
        bot_instance.telegram_service.answer_callback_query.side_effect = Exception("Test error")
        
        # Call the method - should raise an exception since error handling is not implemented yet
        with pytest.raises(Exception, match="Test error"):
            await bot_instance._process_duplicate_confirmation(sample_callback_query, "John Doe")
    
    @pytest.mark.asyncio
    async def test_process_duplicate_cancellation_error_handling(self, bot_instance, sample_callback_query):
        """Test error handling in process duplicate cancellation."""
        # Mock an exception
        bot_instance.telegram_service.answer_callback_query.side_effect = Exception("Test error")
        
        # Call the method - should raise an exception since error handling is not implemented yet
        with pytest.raises(Exception, match="Test error"):
            await bot_instance._process_duplicate_cancellation(sample_callback_query, "John Doe")
    
    @pytest.mark.asyncio
    async def test_show_all_duplicate_matches_error_handling(self, bot_instance, sample_callback_query):
        """Test error handling in show all duplicate matches."""
        # Mock an exception
        bot_instance.telegram_service.answer_callback_query.side_effect = Exception("Test error")
        
        # Call the method - should raise an exception since error handling is not implemented yet
        with pytest.raises(Exception, match="Test error"):
            await bot_instance._show_all_duplicate_matches(sample_callback_query, "John Doe")


class TestDuplicateCallbackIntegration:
    """Integration tests for duplicate detection callbacks."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot instance."""
        bot = Mock()
        bot.answer_callback_query = AsyncMock()
        bot.edit_message_text = AsyncMock()
        return bot
    
    @pytest.fixture
    def mock_telegram_service(self):
        """Create a mock TelegramService."""
        service = Mock()
        service.answer_callback_query = AsyncMock()
        service.send_message = AsyncMock()
        service.send_duplicate_confirmation_result = AsyncMock()
        return service
    
    @pytest.fixture
    def bot_instance(self, mock_bot, mock_telegram_service):
        """Create a ConstructionInventoryBot instance with mocked dependencies."""
        bot = ConstructionInventoryBot()
        bot.bot = mock_bot
        bot.telegram_service = mock_telegram_service
        return bot
    
    @pytest.mark.asyncio
    async def test_callback_query_routing_confirm_duplicates(self, bot_instance):
        """Test that confirm_duplicates callback is routed correctly."""
        # Create a callback query
        callback_query = Mock()
        callback_query.data = "confirm_duplicates"
        callback_query.from_user = Mock()
        callback_query.from_user.id = 12345
        callback_query.from_user.first_name = "John"
        callback_query.from_user.last_name = "Doe"
        callback_query.message = Mock()
        callback_query.message.chat = Mock()
        callback_query.message.chat.id = 67890
        callback_query.message.message_id = 1
        callback_query.message.text = "Test message"
        
        # Mock the auth service
        bot_instance.auth_service = Mock()
        bot_instance.auth_service.validate_user_access = AsyncMock(return_value=(True, "OK", "admin"))
        
        # Mock the duplicate confirmation handler
        bot_instance.handle_duplicate_confirmation_callback = AsyncMock()
        
        # Call the main callback query processor
        await bot_instance.process_callback_query(callback_query)
        
        # Verify that the duplicate confirmation handler was called
        bot_instance.handle_duplicate_confirmation_callback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_callback_query_routing_cancel_duplicates(self, bot_instance):
        """Test that cancel_duplicates callback is routed correctly."""
        # Create a callback query
        callback_query = Mock()
        callback_query.data = "cancel_duplicates"
        callback_query.from_user = Mock()
        callback_query.from_user.id = 12345
        callback_query.from_user.first_name = "John"
        callback_query.from_user.last_name = "Doe"
        callback_query.message = Mock()
        callback_query.message.chat = Mock()
        callback_query.message.chat.id = 67890
        callback_query.message.message_id = 1
        callback_query.message.text = "Test message"
        
        # Mock the auth service
        bot_instance.auth_service = Mock()
        bot_instance.auth_service.validate_user_access = AsyncMock(return_value=(True, "OK", "admin"))
        
        # Mock the duplicate confirmation handler
        bot_instance.handle_duplicate_confirmation_callback = AsyncMock()
        
        # Call the main callback query processor
        await bot_instance.process_callback_query(callback_query)
        
        # Verify that the duplicate confirmation handler was called
        bot_instance.handle_duplicate_confirmation_callback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_callback_query_routing_show_all_duplicates(self, bot_instance):
        """Test that show_all_duplicates callback is routed correctly."""
        # Create a callback query
        callback_query = Mock()
        callback_query.data = "show_all_duplicates"
        callback_query.from_user = Mock()
        callback_query.from_user.id = 12345
        callback_query.from_user.first_name = "John"
        callback_query.from_user.last_name = "Doe"
        callback_query.message = Mock()
        callback_query.message.chat = Mock()
        callback_query.message.chat.id = 67890
        callback_query.message.message_id = 1
        callback_query.message.text = "Test message"
        
        # Mock the auth service
        bot_instance.auth_service = Mock()
        bot_instance.auth_service.validate_user_access = AsyncMock(return_value=(True, "OK", "admin"))
        
        # Mock the duplicate confirmation handler
        bot_instance.handle_duplicate_confirmation_callback = AsyncMock()
        
        # Call the main callback query processor
        await bot_instance.process_callback_query(callback_query)
        
        # Verify that the duplicate confirmation handler was called
        bot_instance.handle_duplicate_confirmation_callback.assert_called_once()
