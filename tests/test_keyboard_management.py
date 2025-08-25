"""Tests for the KeyboardManagementService."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from src.services.keyboard_management import (
    KeyboardManagementService, 
    KeyboardState, 
    UserClickCount
)


class TestKeyboardManagementService:
    """Test cases for KeyboardManagementService."""
    
    @pytest.fixture
    def keyboard_service(self):
        """Create a KeyboardManagementService instance for testing."""
        return KeyboardManagementService(expiry_hours=1, max_clicks_per_minute=3)
    
    @pytest.fixture
    def sample_items(self):
        """Create sample items for testing."""
        return ["item_1", "item_2", "item_3"]
    
    def test_initialization(self, keyboard_service):
        """Test service initialization."""
        assert keyboard_service.expiry_hours == 1
        assert keyboard_service.max_clicks_per_minute == 3
        assert len(keyboard_service.active_keyboards) == 0
        assert len(keyboard_service.user_click_counts) == 0
    
    def test_create_keyboard(self, keyboard_service, sample_items):
        """Test keyboard creation."""
        user_id = 123
        query_type = "stock_query"
        
        keyboard_id = keyboard_service.create_keyboard(user_id, query_type, sample_items)
        
        # Should return a valid keyboard ID
        assert keyboard_id.startswith("stock_query_")
        assert len(keyboard_id) > len("stock_query_")
        
        # Should store keyboard state
        assert keyboard_id in keyboard_service.active_keyboards
        keyboard_state = keyboard_service.active_keyboards[keyboard_id]
        
        assert keyboard_state.user_id == user_id
        assert keyboard_state.query_type == query_type
        assert keyboard_state.items == sample_items
        assert keyboard_state.click_count == 0
        assert keyboard_state.last_click_time is None
        
        # Should have expiry time
        assert keyboard_state.expires_at > datetime.now()
        assert keyboard_state.expires_at <= datetime.now() + timedelta(hours=1, minutes=1)
    
    def test_get_keyboard_valid(self, keyboard_service, sample_items):
        """Test getting a valid keyboard."""
        user_id = 123
        keyboard_id = keyboard_service.create_keyboard(user_id, "stock_query", sample_items)
        
        keyboard_state = keyboard_service.get_keyboard(keyboard_id)
        
        assert keyboard_state is not None
        assert keyboard_state.keyboard_id == keyboard_id
        assert keyboard_state.user_id == user_id
    
    def test_get_keyboard_nonexistent(self, keyboard_service):
        """Test getting a nonexistent keyboard."""
        keyboard_state = keyboard_service.get_keyboard("nonexistent_id")
        assert keyboard_state is None
    
    def test_keyboard_expiry(self, keyboard_service, sample_items):
        """Test that keyboards expire after the specified time."""
        user_id = 123
        keyboard_id = keyboard_service.create_keyboard(user_id, "stock_query", sample_items)
        
        # Mock time passing (1 hour + 1 minute)
        with patch('src.services.keyboard_management.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.now() + timedelta(hours=1, minutes=1)
            
            # Should be expired
            assert keyboard_service.is_keyboard_expired(keyboard_id) is True
            
            # Getting expired keyboard should return None and remove it
            keyboard_state = keyboard_service.get_keyboard(keyboard_id)
            assert keyboard_state is None
            assert keyboard_id not in keyboard_service.active_keyboards
    
    def test_rate_limiting(self, keyboard_service, sample_items):
        """Test rate limiting functionality."""
        user_id = 123
        keyboard_id = keyboard_service.create_keyboard(user_id, "stock_query", sample_items)
        
        # First 3 clicks should work
        assert keyboard_service.can_click_keyboard(user_id, keyboard_id) is True
        keyboard_service.record_keyboard_click(user_id, keyboard_id)
        
        assert keyboard_service.can_click_keyboard(user_id, keyboard_id) is True
        keyboard_service.record_keyboard_click(user_id, keyboard_id)
        
        assert keyboard_service.can_click_keyboard(user_id, keyboard_id) is True
        keyboard_service.record_keyboard_click(user_id, keyboard_id)
        
        # 4th click should be blocked
        assert keyboard_service.can_click_keyboard(user_id, keyboard_id) is False
    
    def test_rate_limiting_reset(self, keyboard_service, sample_items):
        """Test that rate limiting resets after time window."""
        user_id = 123
        keyboard_id = keyboard_service.create_keyboard(user_id, "stock_query", sample_items)
        
        # Record 3 clicks
        for _ in range(3):
            keyboard_service.record_keyboard_click(user_id, keyboard_id)
        
        # Should be rate limited
        assert keyboard_service.can_click_keyboard(user_id, keyboard_id) is False
        
        # Mock time passing (1 minute + 1 second)
        with patch('src.services.keyboard_management.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.now() + timedelta(minutes=1, seconds=1)
            
            # Should be able to click again
            assert keyboard_service.can_click_keyboard(user_id, keyboard_id) is True
    
    def test_cleanup_expired_keyboards(self, keyboard_service, sample_items):
        """Test automatic cleanup of expired keyboards."""
        user_id = 123
        
        # Create a keyboard
        keyboard_id = keyboard_service.create_keyboard(user_id, "stock_query", sample_items)
        assert keyboard_id in keyboard_service.active_keyboards
        
        # Mock time passing to expire the keyboard
        with patch('src.services.keyboard_management.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.now() + timedelta(hours=1, minutes=1)
            
            # Cleanup should remove expired keyboards
            cleaned_count = keyboard_service.cleanup_expired_keyboards()
            assert cleaned_count == 1
            
            # Keyboard should be removed
            assert keyboard_id not in keyboard_service.active_keyboards
    
    def test_cleanup_no_expired_keyboards(self, keyboard_service, sample_items):
        """Test cleanup when no keyboards are expired."""
        user_id = 123
        
        # Create a keyboard
        keyboard_id = keyboard_service.create_keyboard(user_id, "stock_query", sample_items)
        
        # Cleanup should not remove any keyboards
        cleaned_count = keyboard_service.cleanup_expired_keyboards()
        assert cleaned_count == 0
        
        # Keyboard should still exist
        assert keyboard_id in keyboard_service.active_keyboards
    
    def test_keyboard_stats(self, keyboard_service, sample_items):
        """Test keyboard statistics."""
        user_id = 123
        
        # Create a keyboard
        keyboard_id = keyboard_service.create_keyboard(user_id, "stock_query", sample_items)
        
        # Get stats
        stats = keyboard_service.get_keyboard_stats()
        
        assert stats["total_keyboards"] == 1
        assert stats["active_keyboards"] == 1
        assert stats["expired_keyboards"] == 0
        assert stats["total_users"] == 1
        assert stats["expiry_hours"] == 1
        assert stats["max_clicks_per_minute"] == 3
    
    def test_keyboard_stats_with_expired(self, keyboard_service, sample_items):
        """Test keyboard statistics with expired keyboards."""
        user_id = 123
        
        # Create a keyboard
        keyboard_id = keyboard_service.create_keyboard(user_id, "stock_query", sample_items)
        
        # Mock time passing to expire the keyboard
        with patch('src.services.keyboard_management.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.now() + timedelta(hours=1, minutes=1)
            
            # Get stats (should show expired keyboard)
            stats = keyboard_service.get_keyboard_stats()
            
            assert stats["total_keyboards"] == 1
            assert stats["active_keyboards"] == 0
            assert stats["expired_keyboards"] == 1
    
    def test_multiple_users(self, keyboard_service, sample_items):
        """Test keyboard management with multiple users."""
        user1_id = 123
        user2_id = 456
        
        # Create keyboards for different users
        keyboard1_id = keyboard_service.create_keyboard(user1_id, "stock_query", sample_items)
        keyboard2_id = keyboard_service.create_keyboard(user2_id, "batch_approval", sample_items)
        
        # Both keyboards should exist
        assert keyboard1_id in keyboard_service.active_keyboards
        assert keyboard2_id in keyboard_service.active_keyboards
        
        # Stats should show 2 users
        stats = keyboard_service.get_keyboard_stats()
        assert stats["total_users"] == 2
    
    def test_clear_all_keyboards(self, keyboard_service, sample_items):
        """Test clearing all keyboards."""
        user_id = 123
        
        # Create multiple keyboards
        keyboard_service.create_keyboard(user_id, "stock_query", sample_items)
        keyboard_service.create_keyboard(user_id, "batch_approval", sample_items)
        
        # Should have 2 keyboards
        assert len(keyboard_service.active_keyboards) == 2
        
        # Clear all
        keyboard_service.clear_all_keyboards()
        
        # Should be empty
        assert len(keyboard_service.active_keyboards) == 0
        assert len(keyboard_service.user_click_counts) == 0
    
    def test_error_handling(self, keyboard_service):
        """Test error handling in various scenarios."""
        # Test with invalid keyboard ID
        assert keyboard_service.get_keyboard("") is None
        assert keyboard_service.is_keyboard_expired("") is True
        
        # Test rate limiting with invalid user
        assert keyboard_service.can_click_keyboard(0, "invalid_id") is False
        
        # Test recording click with invalid data
        assert keyboard_service.record_keyboard_click(0, "invalid_id") is False
    
    def test_custom_configuration(self):
        """Test service with custom configuration."""
        # Create service with custom settings
        custom_service = KeyboardManagementService(expiry_hours=2, max_clicks_per_minute=5)
        
        assert custom_service.expiry_hours == 2
        assert custom_service.max_clicks_per_minute == 5
        
        # Test that custom settings work
        user_id = 123
        keyboard_id = custom_service.create_keyboard(user_id, "test", ["item1"])
        
        # Should allow 5 clicks
        for _ in range(5):
            assert custom_service.can_click_keyboard(user_id, keyboard_id) is True
            custom_service.record_keyboard_click(user_id, keyboard_id)
        
        # 6th click should be blocked
        assert custom_service.can_click_keyboard(user_id, keyboard_id) is False


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
