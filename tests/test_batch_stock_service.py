"""Unit tests for the BatchStockService with approval flow."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from src.schemas import (
    MovementStatus, MovementType, StockMovement, UserRole, 
    BatchApproval, Item, BatchResult
)
from src.services.batch_stock import BatchStockService


class MockAirtableClient:
    """Mock AirtableClient for testing."""
    
    def __init__(self):
        """Initialize with test data."""
        self.items = {}
        self.movements = {}
    
    def add_item(self, name, on_hand=0, base_unit="piece"):
        """Add a test item."""
        self.items[name] = Item(
            name=name,
            base_unit=base_unit,
            units=[],
            on_hand=on_hand
        )
    
    async def get_item(self, item_name):
        """Get an item by name."""
        return self.items.get(item_name)
    
    async def create_movement(self, movement):
        """Create a mock movement."""
        movement_id = f"mov_{len(self.movements) + 1}"
        self.movements[movement_id] = movement
        return movement_id


class MockStockService:
    """Mock StockService for testing."""
    
    def __init__(self):
        """Initialize with test data."""
        self.processed_in = []
        self.processed_out = []
        self.processed_adjust = []
    
    async def stock_in(self, **kwargs):
        """Mock stock_in method."""
        self.processed_in.append(kwargs)
        return True, "Success", None
    
    async def stock_out(self, **kwargs):
        """Mock stock_out method."""
        self.processed_out.append(kwargs)
        return True, "Success", None
    
    async def stock_adjust(self, **kwargs):
        """Mock stock_adjust method."""
        self.processed_adjust.append(kwargs)
        return True, "Success", None


@pytest.fixture
def mock_services():
    """Create mock services for testing."""
    settings = MagicMock()
    mock_airtable = MockAirtableClient()
    mock_stock = MockStockService()
    
    # Add test items
    mock_airtable.add_item("cement", 100, "bags")
    mock_airtable.add_item("sand", 200, "kg")
    
    return mock_airtable, mock_stock, settings


@pytest.mark.asyncio
async def test_prepare_batch_approval(mock_services):
    """Test preparing a batch for approval."""
    mock_airtable, mock_stock, settings = mock_services
    
    # Create batch service
    batch_service = BatchStockService(mock_airtable, settings, mock_stock)
    
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
            movement_type=MovementType.IN,
            quantity=20.0,
            unit="kg",
            signed_base_quantity=20.0,
            user_id="123",
            user_name="Test User"
        )
    ]
    
    # Test prepare_batch_approval
    success, batch_id, batch_approval = await batch_service.prepare_batch_approval(
        movements, UserRole.STAFF, 12345, 678, "Test User"
    )
    
    # Verify results
    assert success is True
    assert batch_id is not None
    assert batch_id.startswith("batch_")
    assert batch_approval is not None
    assert len(batch_service.pending_approvals) == 1
    assert batch_id in batch_service.pending_approvals
    
    # Verify movements status was updated
    for movement in batch_approval.movements:
        assert movement.status == MovementStatus.PENDING_APPROVAL
        assert movement.batch_id == batch_id
    
    # Verify before levels were collected
    assert batch_approval.before_levels["cement"] == 100
    assert batch_approval.before_levels["sand"] == 200
    
    # Verify batch approval properties
    assert batch_approval.user_id == "678"
    assert batch_approval.user_name == "Test User"
    assert batch_approval.chat_id == 12345
    assert batch_approval.status == "Pending"


@pytest.mark.asyncio
async def test_get_batch_approval(mock_services):
    """Test getting a batch approval by ID."""
    mock_airtable, mock_stock, settings = mock_services
    
    # Create batch service
    batch_service = BatchStockService(mock_airtable, settings, mock_stock)
    
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
        )
    ]
    
    # Create a batch approval
    success, batch_id, _ = await batch_service.prepare_batch_approval(
        movements, UserRole.STAFF, 12345, 678, "Test User"
    )
    
    # Test get_batch_approval
    batch_approval = await batch_service.get_batch_approval(batch_id)
    
    # Verify results
    assert batch_approval is not None
    assert batch_approval.batch_id == batch_id
    
    # Test with invalid ID
    invalid_batch = await batch_service.get_batch_approval("invalid_id")
    assert invalid_batch is None


@pytest.mark.asyncio
async def test_remove_batch_approval(mock_services):
    """Test removing a batch approval."""
    mock_airtable, mock_stock, settings = mock_services
    
    # Create batch service
    batch_service = BatchStockService(mock_airtable, settings, mock_stock)
    
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
        )
    ]
    
    # Create a batch approval
    success, batch_id, _ = await batch_service.prepare_batch_approval(
        movements, UserRole.STAFF, 12345, 678, "Test User"
    )
    
    # Test remove_batch_approval
    removed = await batch_service.remove_batch_approval(batch_id)
    
    # Verify results
    assert removed is True
    assert len(batch_service.pending_approvals) == 0
    
    # Test with invalid ID
    removed = await batch_service.remove_batch_approval("invalid_id")
    assert removed is False


@pytest.mark.asyncio
async def test_get_pending_approvals_count(mock_services):
    """Test getting the count of pending approvals."""
    mock_airtable, mock_stock, settings = mock_services
    
    # Create batch service
    batch_service = BatchStockService(mock_airtable, settings, mock_stock)
    
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
        )
    ]
    
    # Create two batch approvals
    await batch_service.prepare_batch_approval(
        movements, UserRole.STAFF, 12345, 678, "Test User 1"
    )
    
    await batch_service.prepare_batch_approval(
        movements, UserRole.STAFF, 12345, 789, "Test User 2"
    )
    
    # Test get_pending_approvals_count
    count = await batch_service.get_pending_approvals_count()
    
    # Verify results
    assert count == 2


@pytest.mark.asyncio
async def test_get_pending_approvals_summary(mock_services):
    """Test getting a summary of pending approvals."""
    mock_airtable, mock_stock, settings = mock_services
    
    # Create batch service
    batch_service = BatchStockService(mock_airtable, settings, mock_stock)
    
    # Create test movements
    movements1 = [
        StockMovement(
            item_name="cement",
            movement_type=MovementType.IN,
            quantity=10.0,
            unit="bags",
            signed_base_quantity=10.0,
            user_id="123",
            user_name="Test User"
        )
    ]
    
    movements2 = [
        StockMovement(
            item_name="sand",
            movement_type=MovementType.IN,
            quantity=20.0,
            unit="kg",
            signed_base_quantity=20.0,
            user_id="123",
            user_name="Test User"
        ),
        StockMovement(
            item_name="cement",
            movement_type=MovementType.IN,
            quantity=30.0,
            unit="bags",
            signed_base_quantity=30.0,
            user_id="123",
            user_name="Test User"
        )
    ]
    
    # Create two batch approvals
    await batch_service.prepare_batch_approval(
        movements1, UserRole.STAFF, 12345, 678, "Test User 1"
    )
    
    await batch_service.prepare_batch_approval(
        movements2, UserRole.STAFF, 12345, 789, "Test User 2"
    )
    
    # Test get_pending_approvals_summary
    summary = await batch_service.get_pending_approvals_summary()
    
    # Verify results
    assert summary["total_pending_batches"] == 2
    assert summary["total_pending_movements"] == 3  # 1 + 2
    assert isinstance(summary["oldest_pending"], datetime)
    assert len(summary["batch_ids"]) == 2


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])