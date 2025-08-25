"""Unit tests for the TelegramService with batch approval support."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

from src.telegram_service import TelegramService
from src.schemas import StockMovement, MovementType


class MockTelegramBot:
    """Mock Telegram Bot for testing."""
    
    def __init__(self):
        """Initialize with empty message history."""
        self.sent_messages = []
        self.sent_documents = []
    
    async def send_message(self, chat_id, text, reply_markup=None, parse_mode=None):
        """Mock send_message method."""
        self.sent_messages.append({
            "chat_id": chat_id,
            "text": text,
            "reply_markup": reply_markup,
            "parse_mode": parse_mode
        })
        return MagicMock()  # Return a mock message object
    
    async def send_document(self, chat_id, document, filename=None, caption=None):
        """Mock send_document method."""
        self.sent_documents.append({
            "chat_id": chat_id,
            "document": document,
            "filename": filename,
            "caption": caption
        })
        return MagicMock()  # Return a mock message object


@pytest.fixture
def telegram_service():
    """Create a TelegramService with a mock bot for testing."""
    settings = MagicMock()
    settings.telegram_bot_token = "mock_token"
    
    service = TelegramService(settings)
    service.bot = MockTelegramBot()
    
    return service


@pytest.mark.asyncio
async def test_send_batch_approval_request(telegram_service):
    """Test sending a batch approval request."""
    # Create test movements
    movements = [
        StockMovement(
            item_name="cement",
            movement_type=MovementType.IN,
            quantity=10.0,
            unit="bags",
            signed_base_quantity=10.0,
            user_id="123",
            user_name="Test User"
        ),
        StockMovement(
            item_name="sand",
            movement_type=MovementType.OUT,
            quantity=20.0,
            unit="kg",
            signed_base_quantity=-20.0,
            user_id="123",
            user_name="Test User"
        ),
        StockMovement(
            item_name="steel",
            movement_type=MovementType.ADJUST,
            quantity=5.0,
            unit="pieces",
            signed_base_quantity=-5.0,  # Negative adjustment
            user_id="123",
            user_name="Test User"
        )
    ]
    
    # Mock stock levels
    before_levels = {
        "cement": 100,
        "sand": 200,
        "steel": 50
    }
    
    # Test send_batch_approval_request
    success = await telegram_service.send_batch_approval_request(
        12345, "batch_test_123", movements, before_levels, "Test User"
    )
    
    # Verify success and message was sent
    assert success is True
    assert len(telegram_service.bot.sent_messages) == 1
    
    # Verify message content
    message = telegram_service.bot.sent_messages[0]
    assert message["chat_id"] == 12345
    assert "Batch Approval Required" in message["text"]
    assert "batch_test_123" in message["text"]
    assert "Test User" in message["text"]
    assert "<b>Items to process:</b> 3" in message["text"]
    
    # Verify all items are included
    assert "cement" in message["text"]
    assert "sand" in message["text"]
    assert "steel" in message["text"]
    
    # Verify direction symbols
    assert "➕ <b>cement</b>" in message["text"]
    assert "➖ <b>sand</b>" in message["text"]
    assert "➖ <b>steel</b>" in message["text"]
    
    # Verify buttons
    assert message["reply_markup"] is not None
    reply_markup_str = str(message["reply_markup"])
    assert "approvebatch:batch_test_123" in reply_markup_str
    assert "rejectbatch:batch_test_123" in reply_markup_str


@pytest.mark.asyncio
async def test_send_batch_approval_request_many_items(telegram_service):
    """Test sending a batch approval request with many items (all items displayed)."""
    # Create 15 test movements
    movements = []
    for i in range(15):
        movements.append(
            StockMovement(
                item_name=f"item_{i}",
                movement_type=MovementType.IN,
                quantity=10.0,
                unit="pieces",
                signed_base_quantity=10.0,
                user_id="123",
                user_name="Test User"
            )
        )
    
    # Mock stock levels
    before_levels = {f"item_{i}": 100 for i in range(15)}
    
    # Test send_batch_approval_request
    success = await telegram_service.send_batch_approval_request(
        12345, "batch_test_123", movements, before_levels, "Test User"
    )
    
    # Verify success and message was sent
    assert success is True
    assert len(telegram_service.bot.sent_messages) == 1
    
    # Verify message content
    message = telegram_service.bot.sent_messages[0]
    assert "<b>Items to process:</b> 15" in message["text"]
    
    # Verify all items are listed (no more pagination limit)
    assert "item_0" in message["text"]
    assert "item_9" in message["text"]
    assert "item_10" in message["text"]
    assert "item_14" in message["text"]  # Last item (15th item, 0-indexed)
    
    # Verify no "more items" message since all items are shown
    assert "... and" not in message["text"]


@pytest.mark.asyncio
async def test_send_batch_approval_request_max_items(telegram_service):
    """Test sending a batch approval request with maximum batch size (40 items)."""
    # Create 40 test movements (maximum batch size)
    movements = []
    for i in range(40):
        movements.append(
            StockMovement(
                item_name=f"max_item_{i}",
                movement_type=MovementType.IN,
                quantity=10.0,
                unit="pieces",
                signed_base_quantity=10.0,
                user_id="123",
                user_name="Test User"
            )
        )
    
    # Mock stock levels
    before_levels = {f"max_item_{i}": 100 for i in range(40)}
    
    # Test send_batch_approval_request
    success = await telegram_service.send_batch_approval_request(
        12345, "batch_max_test", movements, before_levels, "Test User"
    )
    
    # Verify success and message was sent
    assert success is True
    assert len(telegram_service.bot.sent_messages) == 1
    
    # Verify message content
    message = telegram_service.bot.sent_messages[0]
    assert "<b>Items to process:</b> 40" in message["text"]
    
    # Verify all items are listed (no truncation)
    assert "max_item_0" in message["text"]
    assert "max_item_19" in message["text"]  # Middle item
    assert "max_item_39" in message["text"]  # Last item (40th item, 0-indexed)
    
    # Verify no "more items" message since all items are shown
    assert "... and" not in message["text"]
    
    # Verify the message length is reasonable (should be well under Telegram's 4096 limit)
    assert len(message["text"]) < 4000  # Leave some buffer


@pytest.mark.asyncio
async def test_send_batch_success_summary(telegram_service):
    """Test sending a batch success summary."""
    # Create test movements
    movements = [
        StockMovement(
            item_name="cement",
            movement_type=MovementType.IN,
            quantity=10.0,
            unit="bags",
            signed_base_quantity=10.0,
            user_id="123",
            user_name="Test User"
        ),
        StockMovement(
            item_name="sand",
            movement_type=MovementType.OUT,
            quantity=20.0,
            unit="kg",
            signed_base_quantity=-20.0,
            user_id="123",
            user_name="Test User"
        )
    ]
    
    # Mock stock levels
    before_levels = {
        "cement": 100,
        "sand": 200
    }
    
    after_levels = {
        "cement": 110,  # 100 + 10
        "sand": 180     # 200 - 20
    }
    
    # Test send_batch_success_summary
    success = await telegram_service.send_batch_success_summary(
        12345, "batch_test_123", movements, before_levels, after_levels
    )
    
    # Verify success and message was sent
    assert success is True
    assert len(telegram_service.bot.sent_messages) == 1
    
    # Verify message content
    message = telegram_service.bot.sent_messages[0]
    assert message["chat_id"] == 12345
    assert "Batch Processed Successfully" in message["text"]
    assert "batch_test_123" in message["text"]
    assert "<b>Items processed:</b> 2/2" in message["text"]
    
    # Verify inventory changes
    assert "Stock: 100 → 110 (+10.00)" in message["text"]
    assert "Stock: 200 → 180 (-20.00)" in message["text"]


@pytest.mark.asyncio
async def test_send_batch_success_summary_with_failures(telegram_service):
    """Test sending a batch success summary with some failed entries."""
    # Create test movements
    movements = [
        StockMovement(
            item_name="cement",
            movement_type=MovementType.IN,
            quantity=10.0,
            unit="bags",
            signed_base_quantity=10.0,
            user_id="123",
            user_name="Test User"
        ),
        StockMovement(
            item_name="sand",
            movement_type=MovementType.OUT,
            quantity=20.0,
            unit="kg",
            signed_base_quantity=-20.0,
            user_id="123",
            user_name="Test User"
        ),
        StockMovement(
            item_name="invalid_item",
            movement_type=MovementType.IN,
            quantity=5.0,
            unit="pieces",
            signed_base_quantity=5.0,
            user_id="123",
            user_name="Test User"
        )
    ]
    
    # Mock stock levels
    before_levels = {
        "cement": 100,
        "sand": 200
    }
    
    after_levels = {
        "cement": 110,  # 100 + 10
        "sand": 180     # 200 - 20
    }
    
    # Mock failed entries
    failed_entries = [
        {
            "item_name": "invalid_item",
            "error": "Item not found in inventory"
        }
    ]
    
    # Test send_batch_success_summary
    success = await telegram_service.send_batch_success_summary(
        12345, "batch_test_123", movements, before_levels, after_levels, failed_entries
    )
    
    # Verify success and message was sent
    assert success is True
    assert len(telegram_service.bot.sent_messages) == 1
    
    # Verify message content
    message = telegram_service.bot.sent_messages[0]
    assert "<b>Items processed:</b> 2/3" in message["text"]
    
    # Verify failed entries section
    assert "Failed Entries:" in message["text"]
    assert "invalid_item" in message["text"]
    assert "Item not found in inventory" in message["text"]


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
