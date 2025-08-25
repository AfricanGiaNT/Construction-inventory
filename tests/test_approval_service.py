"""Unit tests for the ApprovalService with batch approval support."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from src.schemas import (
    MovementStatus, MovementType, StockMovement, UserRole, 
    BatchApproval, Item, BatchResult, BatchError
)
from src.services.approvals import ApprovalService
from src.services.batch_stock import BatchStockService


class MockAirtableClient:
    """Mock AirtableClient for testing."""
    
    def __init__(self):
        """Initialize with test data."""
        self.items = {}
        self.movements = {}
        self.movement_statuses = {}
    
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
        
    async def update_movement_status(self, movement_id, status, approved_by):
        """Update a movement's status."""
        # For test_approve_movement, we want this to succeed
        self.movement_statuses[movement_id] = {
            "status": status,
            "approved_by": approved_by
        }
        return True
        
    async def get_pending_approvals(self):
        """Get pending approvals."""
        return [
            {"id": "mov_1", "sku": "cement"},
            {"id": "mov_2", "sku": "sand"}
        ]


class MockBatchStockService:
    """Mock BatchStockService for testing."""
    
    def __init__(self):
        """Initialize with test data."""
        self._pending_approvals = {}
        self.processed_batches = []
    
    async def prepare_batch_approval(self, movements, user_role, chat_id, user_id, user_name):
        """Mock prepare_batch_approval method."""
        batch_id = f"batch_test_{len(self._pending_approvals) + 1}"
        
        batch_approval = BatchApproval(
            batch_id=batch_id,
            movements=movements,
            user_id=str(user_id),
            user_name=user_name,
            chat_id=chat_id,
            before_levels={"cement": 100}
        )
        
        self._pending_approvals[batch_id] = batch_approval
        return True, batch_id, batch_approval
    
    async def get_batch_approval(self, batch_id):
        """Mock get_batch_approval method."""
        return self._pending_approvals.get(batch_id)
    
    async def remove_batch_approval(self, batch_id):
        """Mock remove_batch_approval method."""
        if batch_id in self._pending_approvals:
            del self._pending_approvals[batch_id]
            return True
        return False
    
    async def process_batch_movements(self, movements, user_role, global_parameters=None):
        """Mock process_batch_movements method."""
        self.processed_batches.append({
            "movements": movements,
            "user_role": user_role,
            "global_parameters": global_parameters
        })
        
        # Create a mock BatchResult
        return BatchResult(
            total_entries=len(movements),
            successful_entries=len(movements),
            failed_entries=0,
            success_rate=100.0,
            movements_created=["mov_test_1", "mov_test_2"],
            errors=[],
            summary_message="All processed successfully"
        )
    
    async def get_pending_approvals_count(self):
        """Mock get_pending_approvals_count method."""
        return len(self._pending_approvals)
    
    async def get_pending_approvals_summary(self):
        """Mock get_pending_approvals_summary method."""
        total_movements = sum(len(batch.movements) for batch in self._pending_approvals.values())
        return {
            "total_pending_batches": len(self._pending_approvals),
            "total_pending_movements": total_movements,
            "oldest_pending": datetime.now(),
            "batch_ids": list(self._pending_approvals.keys())
        }


@pytest.fixture
def mock_services():
    """Create mock services for testing."""
    mock_airtable = MockAirtableClient()
    mock_batch_service = MockBatchStockService()
    
    # Add test items
    mock_airtable.add_item("cement", 100, "bags")
    mock_airtable.add_item("sand", 200, "kg")
    
    # Pre-populate a movement for the test_approve_movement test
    mock_airtable.movements["mov_1"] = StockMovement(
        id="mov_1",
        item_name="cement",
        movement_type=MovementType.IN,
        quantity=10.0,
        unit="bags",
        signed_base_quantity=10.0,
        user_id="123",
        user_name="Test User"
    )
    
    return mock_airtable, mock_batch_service


@pytest.mark.asyncio
async def test_approve_movement(mock_services):
    """Test approving a single movement."""
    mock_airtable, mock_batch_service = mock_services
    
    # Create approval service
    approval_service = ApprovalService(mock_airtable, mock_batch_service)
    
    # Test with non-admin role
    success, message = await approval_service.approve_movement(
        "mov_1", "Non-Admin", UserRole.STAFF
    )
    
    assert not success
    assert "administrators" in message.lower()
    
    # Test with admin role
    success, message = await approval_service.approve_movement(
        "mov_1", "Admin User", UserRole.ADMIN
    )
    
    assert success
    assert "mov_1" in message
    assert "successfully" in message.lower()
    assert mock_airtable.movement_statuses["mov_1"]["status"] == MovementStatus.POSTED.value
    assert mock_airtable.movement_statuses["mov_1"]["approved_by"] == "Admin User"


@pytest.mark.asyncio
async def test_approve_batch(mock_services):
    """Test approving a batch."""
    mock_airtable, mock_batch_service = mock_services
    
    # Create approval service
    approval_service = ApprovalService(mock_airtable, mock_batch_service)
    
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
    
    # Create a batch approval
    success, batch_id, _ = await mock_batch_service.prepare_batch_approval(
        movements, UserRole.STAFF, 12345, 678, "Test User"
    )
    
    # Test with non-admin role
    success, message, batch_result = await approval_service.approve_batch(
        batch_id, "Non-Admin", UserRole.STAFF
    )
    
    assert not success
    assert "administrators" in message.lower()
    assert batch_result is None
    
    # Test with admin role
    success, message, batch_result = await approval_service.approve_batch(
        batch_id, "Admin User", UserRole.ADMIN
    )
    
    assert success
    assert batch_id in message
    assert batch_result is not None
    assert batch_result.total_entries == 2
    assert batch_result.successful_entries == 2
    
    # Verify batch was processed
    assert len(mock_batch_service.processed_batches) == 1
    processed = mock_batch_service.processed_batches[0]
    assert len(processed["movements"]) == 2
    assert processed["user_role"] == UserRole.ADMIN
    
    # Verify batch was removed from pending
    assert batch_id not in mock_batch_service._pending_approvals


@pytest.mark.asyncio
async def test_reject_batch(mock_services):
    """Test rejecting a batch."""
    mock_airtable, mock_batch_service = mock_services
    
    # Create approval service
    approval_service = ApprovalService(mock_airtable, mock_batch_service)
    
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
    success, batch_id, _ = await mock_batch_service.prepare_batch_approval(
        movements, UserRole.STAFF, 12345, 678, "Test User"
    )
    
    # Test with non-admin role
    success, message = await approval_service.reject_batch(
        batch_id, "Non-Admin", UserRole.STAFF
    )
    
    assert not success
    assert "administrators" in message.lower()
    assert batch_id in mock_batch_service._pending_approvals  # Still in pending
    
    # Test with admin role
    success, message = await approval_service.reject_batch(
        batch_id, "Admin User", UserRole.ADMIN
    )
    
    assert success
    assert batch_id in message
    assert "rejected" in message.lower()
    
    # Verify batch was removed from pending but not processed
    assert batch_id not in mock_batch_service._pending_approvals
    assert len(mock_batch_service.processed_batches) == 0  # Should not process the batch when rejecting


@pytest.mark.asyncio
async def test_get_approval_summary(mock_services):
    """Test getting approval summary with batch information."""
    mock_airtable, mock_batch_service = mock_services
    
    # Create approval service
    approval_service = ApprovalService(mock_airtable, mock_batch_service)
    
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
    
    # Create two batch approvals
    await mock_batch_service.prepare_batch_approval(
        movements, UserRole.STAFF, 12345, 678, "Test User 1"
    )
    
    await mock_batch_service.prepare_batch_approval(
        movements[:1], UserRole.STAFF, 12345, 789, "Test User 2"
    )
    
    # Test get_approval_summary
    summary = await approval_service.get_approval_summary()
    
    # Verify results
    assert summary["pending_count"] == 2  # From mock Airtable client
    assert summary["pending_batches"] == 2  # From mock batch service
    assert summary["pending_batch_movements"] == 3  # 2 + 1
    assert "cement" in summary["pending_items"]
    assert "sand" in summary["pending_items"]
    assert "last_updated" in summary


@pytest.mark.asyncio
async def test_get_batch_approval_details(mock_services):
    """Test getting batch approval details."""
    mock_airtable, mock_batch_service = mock_services
    
    # Create approval service
    approval_service = ApprovalService(mock_airtable, mock_batch_service)
    
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
    
    # Create a batch approval
    success, batch_id, _ = await mock_batch_service.prepare_batch_approval(
        movements, UserRole.STAFF, 12345, 678, "Test User"
    )
    
    # Test get_batch_approval_details
    success, message, details = await approval_service.get_batch_approval_details(batch_id)
    
    # Verify results
    assert success is True
    assert batch_id in message
    assert details is not None
    assert details["batch_id"] == batch_id
    assert details["status"] == "Pending"
    assert details["user_name"] == "Test User"
    assert len(details["items"]) == 2
    assert details["items"][0]["name"] == "cement"
    assert details["items"][1]["name"] == "sand"
    assert "before_levels" in details
    assert details["before_levels"]["cement"] == 100
    
    # Test with invalid batch ID
    success, message, details = await approval_service.get_batch_approval_details("invalid_id")
    assert not success
    assert "not found" in message.lower()
    assert details is None


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])