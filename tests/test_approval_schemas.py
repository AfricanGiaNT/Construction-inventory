"""Unit tests for the approval system schema models."""

import pytest
from datetime import datetime
from typing import Dict, List

from src.schemas import (
    MovementStatus, StockMovement, MovementType, 
    BatchApproval, BatchError, BatchErrorType
)


def test_movement_status_enum():
    """Test that the new movement statuses are properly defined."""
    # Verify new statuses are available
    assert MovementStatus.PENDING_APPROVAL.value == "Pending Approval"
    assert MovementStatus.REJECTED.value == "Rejected"
    
    # Verify existing statuses still work
    assert MovementStatus.POSTED.value == "Posted"
    assert MovementStatus.REQUESTED.value == "Requested"
    assert MovementStatus.VOIDED.value == "Voided"
    assert MovementStatus.APPROVED.value == "Approved"


def test_stock_movement_with_new_statuses():
    """Test creating stock movements with the new statuses."""
    # Create a movement with PENDING_APPROVAL status
    pending_movement = StockMovement(
        item_name="cement",
        movement_type=MovementType.IN,
        quantity=10.0,
        unit="bags",
        signed_base_quantity=10.0,
        status=MovementStatus.PENDING_APPROVAL,
        user_id="123",
        user_name="Test User"
    )
    assert pending_movement.status == MovementStatus.PENDING_APPROVAL
    
    # Create a movement with REJECTED status
    rejected_movement = StockMovement(
        item_name="cement",
        movement_type=MovementType.IN,
        quantity=10.0,
        unit="bags",
        signed_base_quantity=10.0,
        status=MovementStatus.REJECTED,
        user_id="123",
        user_name="Test User"
    )
    assert rejected_movement.status == MovementStatus.REJECTED


def test_stock_movement_with_batch_id():
    """Test that stock movements can be created with a batch_id."""
    movement = StockMovement(
        item_name="cement",
        movement_type=MovementType.IN,
        quantity=10.0,
        unit="bags",
        signed_base_quantity=10.0,
        status=MovementStatus.PENDING_APPROVAL,
        user_id="123",
        user_name="Test User",
        batch_id="batch_123456"
    )
    
    assert movement.batch_id == "batch_123456"


def test_batch_approval_model():
    """Test the new BatchApproval model."""
    # Create a simple stock movement for testing
    movement = StockMovement(
        item_name="cement",
        movement_type=MovementType.IN,
        quantity=10.0,
        unit="bags",
        signed_base_quantity=10.0,
        status=MovementStatus.PENDING_APPROVAL,
        user_id="123",
        user_name="Test User"
    )
    
    # Create a batch approval with minimal fields
    batch_approval = BatchApproval(
        batch_id="test_batch_001",
        movements=[movement],
        user_id="123",
        user_name="Test User",
        chat_id=456
    )
    
    # Test that all fields are correctly set
    assert batch_approval.batch_id == "test_batch_001"
    assert len(batch_approval.movements) == 1
    assert batch_approval.movements[0].item_name == "cement"
    assert batch_approval.user_id == "123"
    assert batch_approval.user_name == "Test User"
    assert batch_approval.chat_id == 456
    assert batch_approval.status == "Pending"  # Default value
    assert isinstance(batch_approval.timestamp, datetime)
    assert batch_approval.before_levels == {}  # Empty dict by default
    assert batch_approval.after_levels == {}  # Empty dict by default
    assert batch_approval.failed_entries == []  # Empty list by default
    assert batch_approval.message_id is None  # None by default


def test_batch_approval_with_all_fields():
    """Test BatchApproval with all fields populated."""
    # Create a simple stock movement for testing
    movement = StockMovement(
        item_name="cement",
        movement_type=MovementType.IN,
        quantity=10.0,
        unit="bags",
        signed_base_quantity=10.0,
        status=MovementStatus.PENDING_APPROVAL,
        user_id="123",
        user_name="Test User"
    )
    
    # Create before/after levels
    before_levels = {"cement": 100.0, "sand": 50.0}
    after_levels = {"cement": 110.0, "sand": 50.0}
    
    # Create failed entries
    failed_entries = [
        {"item_name": "invalid_item", "error": "Item not found"}
    ]
    
    # Set a specific timestamp for testing
    timestamp = datetime.now()
    
    # Create a batch approval with all fields
    batch_approval = BatchApproval(
        batch_id="test_batch_001",
        movements=[movement],
        user_id="123",
        user_name="Test User",
        chat_id=456,
        status="Approved",  # Override default
        before_levels=before_levels,
        after_levels=after_levels,
        failed_entries=failed_entries,
        timestamp=timestamp,
        message_id=789
    )
    
    # Test that all fields are correctly set
    assert batch_approval.batch_id == "test_batch_001"
    assert len(batch_approval.movements) == 1
    assert batch_approval.status == "Approved"
    assert batch_approval.timestamp == timestamp
    assert batch_approval.before_levels == before_levels
    assert batch_approval.after_levels == after_levels
    assert batch_approval.failed_entries == failed_entries
    assert batch_approval.message_id == 789


def test_batch_approval_add_movement():
    """Test adding a movement to an existing BatchApproval."""
    # Create an empty batch approval
    batch_approval = BatchApproval(
        batch_id="test_batch_001",
        movements=[],
        user_id="123",
        user_name="Test User",
        chat_id=456
    )
    
    # Create a movement
    movement = StockMovement(
        item_name="cement",
        movement_type=MovementType.IN,
        quantity=10.0,
        unit="bags",
        signed_base_quantity=10.0,
        status=MovementStatus.PENDING_APPROVAL,
        user_id="123",
        user_name="Test User"
    )
    
    # Add the movement
    batch_approval.movements.append(movement)
    
    # Verify it was added
    assert len(batch_approval.movements) == 1
    assert batch_approval.movements[0].item_name == "cement"


def test_batch_approval_update_fields():
    """Test updating fields in a BatchApproval."""
    # Create a batch approval
    batch_approval = BatchApproval(
        batch_id="test_batch_001",
        movements=[],
        user_id="123",
        user_name="Test User",
        chat_id=456
    )
    
    # Update status
    batch_approval.status = "Approved"
    assert batch_approval.status == "Approved"
    
    # Update before/after levels
    batch_approval.before_levels = {"cement": 100.0}
    batch_approval.after_levels = {"cement": 110.0}
    
    assert batch_approval.before_levels["cement"] == 100.0
    assert batch_approval.after_levels["cement"] == 110.0
    
    # Add a failed entry
    batch_approval.failed_entries.append({
        "item_name": "invalid_item", 
        "error": "Item not found"
    })
    
    assert len(batch_approval.failed_entries) == 1
    assert batch_approval.failed_entries[0]["item_name"] == "invalid_item"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
