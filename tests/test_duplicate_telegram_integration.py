"""Tests for duplicate detection Telegram integration."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import List

from src.telegram_service import TelegramService
from src.services.duplicate_detection import PotentialDuplicate, DuplicateDetectionResult


class TestDuplicateTelegramIntegration:
    """Test cases for duplicate detection Telegram integration."""
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        mock = Mock()
        mock.telegram_bot_token = "test_token"
        return mock
    
    @pytest.fixture
    def telegram_service(self, mock_settings):
        """Create a TelegramService instance."""
        return TelegramService(mock_settings)
    
    @pytest.fixture
    def sample_duplicates(self):
        """Create sample potential duplicates for testing."""
        return [
            PotentialDuplicate(
                item_name="Cement 32.5",
                quantity=45.0,
                unit="bags",
                similarity_score=0.95,
                movement_id="movement_1",
                timestamp=datetime.now() - timedelta(days=2),
                location="Warehouse A",
                category="Construction Materials",
                user_name="John"
            ),
            PotentialDuplicate(
                item_name="32.5 Cement",
                quantity=50.0,
                unit="bags",
                similarity_score=0.98,
                movement_id="movement_2",
                timestamp=datetime.now() - timedelta(days=1),
                location="Warehouse B",
                category="Construction Materials",
                user_name="Sarah"
            ),
            PotentialDuplicate(
                item_name="12mm rebar",
                quantity=100.0,
                unit="pieces",
                similarity_score=0.92,
                movement_id="movement_3",
                timestamp=datetime.now() - timedelta(days=3),
                location="Warehouse A",
                category="Steel",
                user_name="Mike"
            )
        ]
    
    @pytest.fixture
    def sample_entries(self):
        """Create sample inventory entries for testing."""
        class MockEntry:
            def __init__(self, item_name, quantity):
                self.item_name = item_name
                self.quantity = quantity
        
        return [
            MockEntry("Cement 32.5", 50.0),
            MockEntry("12mm rebar", 120.0)
        ]
    
    def test_format_duplicate_message(self, telegram_service, sample_duplicates, sample_entries):
        """Test formatting of duplicate detection message."""
        message = telegram_service._format_duplicate_message(sample_duplicates, sample_entries)
        
        # Check that the message contains expected elements
        assert "Potential Duplicates Detected" in message
        assert "Found similar entries" in message
        assert "New Entry:" in message
        assert "Similar to:" in message
        assert "Action Required:" in message
        assert "Confirming will add quantities together" in message
        
        # Check that specific items are mentioned
        assert "Cement 32.5" in message
        assert "12mm rebar" in message
        
        # Check that similarity scores are shown
        assert "95% match" in message or "98% match" in message or "92% match" in message
    
    def test_create_duplicate_confirmation_keyboard(self, telegram_service):
        """Test creation of duplicate confirmation keyboard."""
        keyboard = telegram_service._create_duplicate_confirmation_keyboard()
        
        # Check that keyboard is created
        assert keyboard is not None
        assert hasattr(keyboard, 'inline_keyboard')
        
        # Check that it has the expected buttons
        buttons = keyboard.inline_keyboard
        assert len(buttons) == 2  # Two rows
        
        # First row should have Confirm and Cancel buttons
        first_row = buttons[0]
        assert len(first_row) == 2
        assert "Confirm & Update" in first_row[0].text
        assert "Cancel & Check Stock" in first_row[1].text
        assert first_row[0].callback_data == "confirm_duplicates"
        assert first_row[1].callback_data == "cancel_duplicates"
        
        # Second row should have Show All Matches button
        second_row = buttons[1]
        assert len(second_row) == 1
        assert "Show All Matches" in second_row[0].text
        assert second_row[0].callback_data == "show_all_duplicates"
    
    def test_entries_similar(self, telegram_service, sample_entries, sample_duplicates):
        """Test entry similarity checking."""
        entry = sample_entries[0]  # Cement 32.5
        duplicate = sample_duplicates[0]  # Cement 32.5
        
        # These should be similar
        assert telegram_service._entries_similar(entry, duplicate) == True
        
        # Test with different items
        different_duplicate = sample_duplicates[2]  # 12mm rebar
        assert telegram_service._entries_similar(entry, different_duplicate) == False
    
    @pytest.mark.asyncio
    async def test_send_duplicate_confirmation(self, telegram_service, sample_duplicates, sample_entries):
        """Test sending duplicate confirmation dialog."""
        # Mock the send_message method
        telegram_service.send_message = AsyncMock(return_value=True)
        
        chat_id = 12345
        message_id = await telegram_service.send_duplicate_confirmation(
            chat_id, sample_duplicates, sample_entries
        )
        
        # Check that send_message was called
        assert telegram_service.send_message.called
        
        # Check that the correct arguments were passed
        call_args = telegram_service.send_message.call_args
        assert call_args[0][0] == chat_id  # chat_id
        assert call_args[0][1] is not None  # message text
        assert call_args[0][2] is not None  # keyboard
        
        # Check return value
        assert message_id == 1  # Placeholder return value
    
    @pytest.mark.asyncio
    async def test_send_duplicate_confirmation_failure(self, telegram_service, sample_duplicates, sample_entries):
        """Test duplicate confirmation when sending fails."""
        # Mock the send_message method to return False
        telegram_service.send_message = AsyncMock(return_value=False)
        
        chat_id = 12345
        message_id = await telegram_service.send_duplicate_confirmation(
            chat_id, sample_duplicates, sample_entries
        )
        
        # Should return -1 on failure
        assert message_id == -1
    
    @pytest.mark.asyncio
    async def test_send_duplicate_confirmation_result(self, telegram_service):
        """Test sending duplicate confirmation result."""
        # Mock the send_message method
        telegram_service.send_message = AsyncMock(return_value=True)
        
        chat_id = 12345
        updated_items = ["Cement 32.5", "12mm rebar"]
        failed_items = ["Paint Red"]
        
        success = await telegram_service.send_duplicate_confirmation_result(
            chat_id, updated_items, failed_items
        )
        
        # Check that send_message was called
        assert telegram_service.send_message.called
        
        # Check the message content
        call_args = telegram_service.send_message.call_args
        message_text = call_args[0][1]
        
        assert "Duplicate Processing Complete" in message_text
        assert "Updated Items (2):" in message_text
        assert "Failed Items (1):" in message_text
        assert "Cement 32.5" in message_text
        assert "12mm rebar" in message_text
        assert "Paint Red" in message_text
        
        assert success == True
    
    @pytest.mark.asyncio
    async def test_send_duplicate_confirmation_result_no_items(self, telegram_service):
        """Test sending duplicate confirmation result with no items."""
        # Mock the send_message method
        telegram_service.send_message = AsyncMock(return_value=True)
        
        chat_id = 12345
        success = await telegram_service.send_duplicate_confirmation_result(
            chat_id, [], []
        )
        
        # Check the message content
        call_args = telegram_service.send_message.call_args
        message_text = call_args[0][1]
        
        assert "No items were processed" in message_text
        assert success == True
    
    def test_format_duplicate_message_empty_duplicates(self, telegram_service, sample_entries):
        """Test formatting message with no duplicates."""
        message = telegram_service._format_duplicate_message([], sample_entries)
        
        # Should still contain the basic structure
        assert "Potential Duplicates Detected" in message
        assert "New Entry:" in message
        assert "No similar entries found" in message
    
    def test_format_duplicate_message_empty_entries(self, telegram_service, sample_duplicates):
        """Test formatting message with no entries."""
        message = telegram_service._format_duplicate_message(sample_duplicates, [])
        
        # Should still contain the basic structure
        assert "Potential Duplicates Detected" in message
        assert "Action Required:" in message
    
    def test_format_duplicate_message_error_handling(self, telegram_service):
        """Test error handling in message formatting."""
        # Test with invalid data that might cause errors
        message = telegram_service._format_duplicate_message(None, None)
        
        # Should return error message
        assert "Error formatting duplicate detection message" in message
    
    def test_create_duplicate_confirmation_keyboard_error_handling(self, telegram_service):
        """Test error handling in keyboard creation."""
        # This should not raise an exception
        keyboard = telegram_service._create_duplicate_confirmation_keyboard()
        
        # Should return a valid keyboard even if there are errors
        assert keyboard is not None
        assert hasattr(keyboard, 'inline_keyboard')
    
    def test_entries_similar_error_handling(self, telegram_service):
        """Test error handling in entry similarity checking."""
        # Test with None values
        result = telegram_service._entries_similar(None, None)
        assert result == False
        
        # Test with invalid entry objects
        class InvalidEntry:
            pass
        
        invalid_entry = InvalidEntry()
        duplicate = PotentialDuplicate(
            item_name="Test",
            quantity=1.0,
            unit="piece",
            similarity_score=0.5,
            movement_id="test",
            timestamp=datetime.now(),
            user_name="test"
        )
        
        result = telegram_service._entries_similar(invalid_entry, duplicate)
        assert result == False


class TestDuplicateMessageFormatting:
    """Test cases for duplicate message formatting edge cases."""
    
    @pytest.fixture
    def telegram_service(self):
        """Create a TelegramService instance."""
        mock_settings = Mock()
        mock_settings.telegram_bot_token = "test_token"
        return TelegramService(mock_settings)
    
    def test_format_message_with_many_duplicates(self, telegram_service):
        """Test formatting with many duplicates (should limit display)."""
        # Create many duplicates
        duplicates = []
        for i in range(10):
            duplicate = PotentialDuplicate(
                item_name=f"Item {i}",
                quantity=float(i),
                unit="pieces",
                similarity_score=0.9,
                movement_id=f"movement_{i}",
                timestamp=datetime.now(),
                user_name=f"User {i}"
            )
            duplicates.append(duplicate)
        
        class MockEntry:
            def __init__(self, item_name, quantity):
                self.item_name = item_name
                self.quantity = quantity
        
        entries = [MockEntry("Test Item", 5.0)]
        
        message = telegram_service._format_duplicate_message(duplicates, entries)
        
        # Should contain the message
        assert "Potential Duplicates Detected" in message
        # Should limit to 3 duplicates per entry
        assert "... and" in message or "more matches" in message
    
    def test_format_message_with_special_characters(self, telegram_service):
        """Test formatting with special characters in item names."""
        duplicate = PotentialDuplicate(
            item_name="Cement-32.5 (Grade A)",
            quantity=50.0,
            unit="bags",
            similarity_score=0.95,
            movement_id="movement_1",
            timestamp=datetime.now(),
            user_name="John Doe"
        )
        
        class MockEntry:
            def __init__(self, item_name, quantity):
                self.item_name = item_name
                self.quantity = quantity
        
        # Use the same item name to ensure similarity
        entry = MockEntry("Cement-32.5 (Grade A)", 50.0)
        
        message = telegram_service._format_duplicate_message([duplicate], [entry])
        
        # Should handle special characters properly
        assert "Cement-32.5 (Grade A)" in message
        assert "John Doe" in message
    
    def test_format_message_with_long_names(self, telegram_service):
        """Test formatting with very long item names."""
        long_name = "Very Long Construction Material Name With Many Descriptive Words And Specifications That Might Cause Formatting Issues"
        
        duplicate = PotentialDuplicate(
            item_name=long_name,
            quantity=1.0,
            unit="piece",
            similarity_score=0.8,
            movement_id="movement_1",
            timestamp=datetime.now(),
            user_name="Test User"
        )
        
        class MockEntry:
            def __init__(self, item_name, quantity):
                self.item_name = item_name
                self.quantity = quantity
        
        entry = MockEntry(long_name, 1.0)
        
        message = telegram_service._format_duplicate_message([duplicate], [entry])
        
        # Should handle long names without errors
        assert "Potential Duplicates Detected" in message
        assert len(message) > 0  # Should not be empty
