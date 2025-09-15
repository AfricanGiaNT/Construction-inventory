"""Tests for the complete duplicate detection workflow integration."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import List

from src.main import ConstructionInventoryBot
from src.services.duplicate_detection import PotentialDuplicate, DuplicateDetectionResult
from src.services.inventory import InventoryEntry, InventoryHeader, InventoryParseResult


class TestCompleteDuplicateWorkflow:
    """Test cases for the complete duplicate detection workflow."""
    
    @pytest.fixture
    def mock_airtable(self):
        """Create mock Airtable client."""
        mock = Mock()
        mock.get_item = AsyncMock()
        mock.create_item_if_not_exists = AsyncMock()
        mock.update_item_stock = AsyncMock()
        mock.get_stock_movements = AsyncMock()
        return mock
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        mock = Mock()
        mock.telegram_bot_token = "test_token"
        return mock
    
    @pytest.fixture
    def mock_telegram_service(self):
        """Create mock Telegram service."""
        mock = Mock()
        mock.send_duplicate_confirmation = AsyncMock(return_value=1)
        mock.send_message = AsyncMock(return_value=True)
        mock.send_error_message = AsyncMock(return_value=True)
        mock.answer_callback_query = AsyncMock(return_value=True)
        mock.bot = Mock()
        mock.bot.edit_message_text = AsyncMock()
        return mock
    
    @pytest.fixture
    def bot_instance(self, mock_airtable, mock_settings, mock_telegram_service):
        """Create ConstructionInventoryBot instance with mocked dependencies."""
        bot = ConstructionInventoryBot()
        bot.airtable_client = mock_airtable
        bot.settings = mock_settings
        bot.telegram_service = mock_telegram_service
        
        # Mock other services
        bot.auth_service = Mock()
        bot.auth_service.validate_user_access = AsyncMock(return_value=(True, "OK", "admin"))
        bot.persistent_idempotency_service = Mock()
        bot.persistent_idempotency_service.store_key = AsyncMock()
        bot.persistent_idempotency_service.check_key = AsyncMock(return_value=False)
        
        # Mock the bot's bot attribute to prevent real API calls
        bot.bot = Mock()
        bot.bot.edit_message_text = AsyncMock()
        
        return bot
    
    @pytest.fixture
    def sample_inventory_command(self):
        """Create sample inventory command text."""
        return """logged by: Trevor,Kayesera
Cement 32.5, 50
12mm rebar, 120"""
    
    @pytest.fixture
    def sample_duplicates(self):
        """Create sample potential duplicates for testing."""
        return [
            PotentialDuplicate(
                item_name="32.5 Cement",
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
                item_name="Cement 32.5",
                quantity=50.0,
                unit="bags",
                similarity_score=0.98,
                movement_id="movement_2",
                timestamp=datetime.now() - timedelta(days=1),
                location="Warehouse B",
                category="Construction Materials",
                user_name="Sarah"
            )
        ]
    
    @pytest.mark.asyncio
    async def test_inventory_command_with_duplicates(self, bot_instance, sample_inventory_command, sample_duplicates):
        """Test complete inventory command workflow with duplicates detected."""
        # Mock duplicate detection service
        bot_instance.duplicate_detection_service.find_potential_duplicates = AsyncMock(return_value=sample_duplicates)
        
        # Mock inventory service methods
        bot_instance.inventory_service._check_for_duplicates = AsyncMock(return_value=DuplicateDetectionResult(
            has_duplicates=True,
            potential_duplicates=sample_duplicates,
            new_entries=[],  # This would be populated by the real method
            requires_confirmation=True
        ))
        bot_instance.inventory_service._store_duplicate_data = AsyncMock()
        
        # Process inventory command
        await bot_instance.handle_inventory_command(
            chat_id=12345,
            user_id=67890,
            user_name="Test User",
            command_text=sample_inventory_command
        )
        
        # Verify duplicate detection was triggered
        assert bot_instance.inventory_service._check_for_duplicates.called
        assert bot_instance.inventory_service._store_duplicate_data.called
        assert bot_instance.telegram_service.send_duplicate_confirmation.called
    
    @pytest.mark.asyncio
    async def test_inventory_command_without_duplicates(self, bot_instance, sample_inventory_command):
        """Test complete inventory command workflow without duplicates."""
        # Mock duplicate detection service to return no duplicates
        bot_instance.duplicate_detection_service.find_potential_duplicates = AsyncMock(return_value=[])
        
        # Mock inventory service methods
        bot_instance.inventory_service._check_for_duplicates = AsyncMock(return_value=DuplicateDetectionResult(
            has_duplicates=False,
            potential_duplicates=[],
            new_entries=[],
            requires_confirmation=False
        ))
        
        # Mock normal processing
        bot_instance.inventory_service._process_inventory_entry = AsyncMock(return_value={
            "success": True,
            "created": False,
            "item_name": "Test Item",
            "quantity": 10.0,
            "previous_quantity": 5.0,
            "new_total": 15.0,
            "message": "Test message"
        })
        
        # Process inventory command
        await bot_instance.handle_inventory_command(
            chat_id=12345,
            user_id=67890,
            user_name="Test User",
            command_text=sample_inventory_command
        )
        
        # Verify normal processing was used
        assert bot_instance.inventory_service._check_for_duplicates.called
        assert not bot_instance.telegram_service.send_duplicate_confirmation.called
    
    @pytest.mark.asyncio
    async def test_duplicate_confirmation_workflow(self, bot_instance, sample_duplicates):
        """Test complete duplicate confirmation workflow."""
        # Mock callback query
        callback_query = Mock()
        callback_query.id = "callback_123"
        callback_query.from_user = Mock()
        callback_query.from_user.id = 67890
        callback_query.from_user.first_name = "Test"
        callback_query.from_user.last_name = "User"
        callback_query.message = Mock()
        callback_query.message.chat = Mock()
        callback_query.message.chat.id = 12345
        callback_query.message.message_id = 1
        callback_query.message.text = "Test message"
        
        # Mock inventory service duplicate confirmation
        bot_instance.inventory_service.process_duplicate_confirmation = AsyncMock(return_value=(True, "Processing complete"))
        
        # Process duplicate confirmation
        await bot_instance._process_duplicate_confirmation(callback_query, "Test User")
        
        # Verify processing
        assert bot_instance.inventory_service.process_duplicate_confirmation.called
        assert bot_instance.telegram_service.answer_callback_query.called
        assert bot_instance.telegram_service.send_message.called
    
    @pytest.mark.asyncio
    async def test_duplicate_cancellation_workflow(self, bot_instance, sample_duplicates):
        """Test complete duplicate cancellation workflow."""
        # Mock callback query
        callback_query = Mock()
        callback_query.id = "callback_123"
        callback_query.from_user = Mock()
        callback_query.from_user.id = 67890
        callback_query.from_user.first_name = "Test"
        callback_query.from_user.last_name = "User"
        callback_query.message = Mock()
        callback_query.message.chat = Mock()
        callback_query.message.chat.id = 12345
        callback_query.message.message_id = 1
        callback_query.message.text = "Test message"
        
        # Mock inventory service duplicate confirmation
        bot_instance.inventory_service.process_duplicate_confirmation = AsyncMock(return_value=(True, "Normal processing complete"))
        
        # Process duplicate cancellation
        await bot_instance._process_duplicate_cancellation(callback_query, "Test User")
        
        # Verify processing
        assert bot_instance.inventory_service.process_duplicate_confirmation.called
        assert bot_instance.telegram_service.answer_callback_query.called
        assert bot_instance.telegram_service.send_message.called
    
    @pytest.mark.asyncio
    async def test_duplicate_confirmation_error_handling(self, bot_instance):
        """Test error handling in duplicate confirmation workflow."""
        # Mock callback query
        callback_query = Mock()
        callback_query.id = "callback_123"
        callback_query.from_user = Mock()
        callback_query.from_user.id = 67890
        callback_query.from_user.first_name = "Test"
        callback_query.from_user.last_name = "User"
        callback_query.message = Mock()
        callback_query.message.chat = Mock()
        callback_query.message.chat.id = 12345
        callback_query.message.message_id = 1
        callback_query.message.text = "Test message"
        
        # Mock inventory service to raise an exception
        bot_instance.inventory_service.process_duplicate_confirmation = AsyncMock(side_effect=Exception("Test error"))
        
        # Process duplicate confirmation
        await bot_instance._process_duplicate_confirmation(callback_query, "Test User")
        
        # Verify error handling
        assert bot_instance.telegram_service.answer_callback_query.called
        # Should not raise an exception
    
    @pytest.mark.asyncio
    async def test_duplicate_cancellation_error_handling(self, bot_instance):
        """Test error handling in duplicate cancellation workflow."""
        # Mock callback query
        callback_query = Mock()
        callback_query.id = "callback_123"
        callback_query.from_user = Mock()
        callback_query.from_user.id = 67890
        callback_query.from_user.first_name = "Test"
        callback_query.from_user.last_name = "User"
        callback_query.message = Mock()
        callback_query.message.chat = Mock()
        callback_query.message.chat.id = 12345
        callback_query.message.message_id = 1
        callback_query.message.text = "Test message"
        
        # Mock inventory service to raise an exception
        bot_instance.inventory_service.process_duplicate_confirmation = AsyncMock(side_effect=Exception("Test error"))
        
        # Process duplicate cancellation
        await bot_instance._process_duplicate_cancellation(callback_query, "Test User")
        
        # Verify error handling
        assert bot_instance.telegram_service.answer_callback_query.called
        # Should not raise an exception
    
    @pytest.mark.asyncio
    async def test_show_all_duplicate_matches(self, bot_instance):
        """Test showing all duplicate matches."""
        # Mock callback query
        callback_query = Mock()
        callback_query.id = "callback_123"
        callback_query.from_user = Mock()
        callback_query.from_user.id = 67890
        callback_query.from_user.first_name = "Test"
        callback_query.from_user.last_name = "User"
        callback_query.message = Mock()
        callback_query.message.chat = Mock()
        callback_query.message.chat.id = 12345
        callback_query.message.message_id = 1
        callback_query.message.text = "Test message"
        
        # Process show all matches
        await bot_instance._show_all_duplicate_matches(callback_query, "Test User")
        
        # Verify processing
        assert bot_instance.telegram_service.answer_callback_query.called
        assert bot_instance.telegram_service.send_message.called
    
    @pytest.mark.asyncio
    async def test_show_all_duplicate_matches_error_handling(self, bot_instance):
        """Test error handling in show all duplicate matches."""
        # Mock callback query
        callback_query = Mock()
        callback_query.id = "callback_123"
        callback_query.from_user = Mock()
        callback_query.from_user.id = 67890
        callback_query.from_user.first_name = "Test"
        callback_query.from_user.last_name = "User"
        callback_query.message = Mock()
        callback_query.message.chat = Mock()
        callback_query.message.chat.id = 12345
        callback_query.message.message_id = 1
        callback_query.message.text = "Test message"
        
        # Mock telegram service to raise an exception
        bot_instance.telegram_service.answer_callback_query.side_effect = Exception("Test error")
        
        # Process show all matches
        await bot_instance._show_all_duplicate_matches(callback_query, "Test User")
        
        # Verify error handling
        # Should not raise an exception


class TestDuplicateWorkflowEdgeCases:
    """Test cases for edge cases in the duplicate detection workflow."""
    
    @pytest.fixture
    def mock_airtable(self):
        """Create mock Airtable client."""
        mock = Mock()
        mock.get_item = AsyncMock()
        mock.create_item_if_not_exists = AsyncMock()
        mock.update_item_stock = AsyncMock()
        mock.get_stock_movements = AsyncMock()
        return mock
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        mock = Mock()
        mock.telegram_bot_token = "test_token"
        return mock
    
    @pytest.fixture
    def bot_instance(self, mock_airtable, mock_settings):
        """Create ConstructionInventoryBot instance with mocked dependencies."""
        bot = ConstructionInventoryBot()
        bot.airtable_client = mock_airtable
        bot.settings = mock_settings
        
        # Mock other services
        bot.auth_service = Mock()
        bot.auth_service.validate_user_access = AsyncMock(return_value=(True, "OK", "admin"))
        bot.persistent_idempotency_service = Mock()
        bot.persistent_idempotency_service.store_key = AsyncMock()
        bot.persistent_idempotency_service.check_key = AsyncMock(return_value=False)
        
        # Mock the bot's bot attribute to prevent real API calls
        bot.bot = Mock()
        bot.bot.edit_message_text = AsyncMock()
        
        return bot
    
    @pytest.mark.asyncio
    async def test_inventory_command_parse_error(self, bot_instance):
        """Test inventory command with parse errors."""
        # Mock inventory service to return parse error
        bot_instance.inventory_service.process_inventory_stocktake = AsyncMock(return_value=(False, "Parse error"))
        
        # Process inventory command
        await bot_instance.handle_inventory_command(
            chat_id=12345,
            user_id=67890,
            user_name="Test User",
            command_text="invalid command"
        )
        
        # Verify error handling
        assert bot_instance.telegram_service.send_error_message.called
    
    @pytest.mark.asyncio
    async def test_inventory_command_exception(self, bot_instance):
        """Test inventory command with exception."""
        # Mock inventory service to raise an exception
        bot_instance.inventory_service.process_inventory_stocktake = AsyncMock(side_effect=Exception("Test error"))
        
        # Process inventory command
        await bot_instance.handle_inventory_command(
            chat_id=12345,
            user_id=67890,
            user_name="Test User",
            command_text="test command"
        )
        
        # Verify error handling
        assert bot_instance.telegram_service.send_message.called
    
    @pytest.mark.asyncio
    async def test_duplicate_confirmation_no_telegram_service(self, bot_instance):
        """Test duplicate confirmation without telegram service."""
        # Mock callback query
        callback_query = Mock()
        callback_query.id = "callback_123"
        callback_query.from_user = Mock()
        callback_query.from_user.id = 67890
        callback_query.from_user.first_name = "Test"
        callback_query.from_user.last_name = "User"
        callback_query.message = Mock()
        callback_query.message.chat = Mock()
        callback_query.message.chat.id = 12345
        callback_query.message.message_id = 1
        callback_query.message.text = "Test message"
        
        # Mock inventory service to return error
        bot_instance.inventory_service.process_duplicate_confirmation = AsyncMock(return_value=(False, "No telegram service"))
        
        # Process duplicate confirmation
        await bot_instance._process_duplicate_confirmation(callback_query, "Test User")
        
        # Verify error handling
        assert bot_instance.telegram_service.answer_callback_query.called
    
    @pytest.mark.asyncio
    async def test_duplicate_cancellation_no_telegram_service(self, bot_instance):
        """Test duplicate cancellation without telegram service."""
        # Mock callback query
        callback_query = Mock()
        callback_query.id = "callback_123"
        callback_query.from_user = Mock()
        callback_query.from_user.id = 67890
        callback_query.from_user.first_name = "Test"
        callback_query.from_user.last_name = "User"
        callback_query.message = Mock()
        callback_query.message.chat = Mock()
        callback_query.message.chat.id = 12345
        callback_query.message.message_id = 1
        callback_query.message.text = "Test message"
        
        # Mock inventory service to return error
        bot_instance.inventory_service.process_duplicate_confirmation = AsyncMock(return_value=(False, "No telegram service"))
        
        # Process duplicate cancellation
        await bot_instance._process_duplicate_cancellation(callback_query, "Test User")
        
        # Verify error handling
        assert bot_instance.telegram_service.answer_callback_query.called
