"""Tests for the batch stock service with global parameters."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC

from src.services.batch_stock import BatchStockService
from src.schemas import StockMovement, MovementType, BatchResult, UserRole


class TestBatchStockServiceWithGlobalParams:
    """Test the batch stock service with global parameters."""

    @pytest.fixture
    def batch_stock_service(self):
        """Create a batch stock service with mocked dependencies."""
        # Mock dependencies
        mock_airtable = MagicMock()
        mock_settings = MagicMock()
        mock_stock_service = MagicMock()
        
        # Configure stock service methods
        mock_stock_service.stock_in = AsyncMock(return_value=(True, "Success"))
        mock_stock_service.stock_out = AsyncMock(return_value=(True, "Success", None))
        mock_stock_service.stock_adjust = AsyncMock(return_value=(True, "Success"))
        
        # Create service
        service = BatchStockService(mock_airtable, mock_settings, mock_stock_service)
        
        return service

    @pytest.mark.asyncio
    async def test_process_batch_with_project_field(self, batch_stock_service):
        """Test processing a batch with project field."""
        # Create test movements with project field
        movements = [
            StockMovement(
                item_name="cement",
                movement_type=MovementType.IN,
                quantity=50.0,
                unit="bags",
                signed_base_quantity=50.0,
                user_id="123",
                user_name="testuser",
                timestamp=datetime.now(UTC),
                project="Bridge Construction"
            ),
            StockMovement(
                item_name="steel bars",
                movement_type=MovementType.IN,
                quantity=100.0,
                unit="pieces",
                signed_base_quantity=100.0,
                user_id="123",
                user_name="testuser",
                timestamp=datetime.now(UTC),
                project="Bridge Construction"
            )
        ]
        
        # Process the batch
        result = await batch_stock_service.process_batch_movements(movements, UserRole.ADMIN)
        
        # Verify the result
        assert result.total_entries == 2
        assert result.successful_entries == 2
        assert result.failed_entries == 0
        assert result.success_rate == 100.0
        assert not result.rollback_performed
        
        # Verify that stock_in was called with project parameter
        batch_stock_service.stock_service.stock_in.assert_called()
        call_args = batch_stock_service.stock_service.stock_in.call_args_list
        
        # Check first call
        assert call_args[0][1].get('project') == "Bridge Construction"
        
        # Check second call
        assert call_args[1][1].get('project') == "Bridge Construction"

    @pytest.mark.asyncio
    async def test_process_batch_with_driver_and_location(self, batch_stock_service):
        """Test processing a batch with driver and location fields."""
        # Create test movements with driver and location fields
        movements = [
            StockMovement(
                item_name="cement",
                movement_type=MovementType.IN,
                quantity=50.0,
                unit="bags",
                signed_base_quantity=50.0,
                user_id="123",
                user_name="testuser",
                timestamp=datetime.now(UTC),
                driver_name="Mr Longwe",
                from_location="chigumula office",
                project="Bridge Construction"
            ),
            StockMovement(
                item_name="steel bars",
                movement_type=MovementType.IN,
                quantity=100.0,
                unit="pieces",
                signed_base_quantity=100.0,
                user_id="123",
                user_name="testuser",
                timestamp=datetime.now(UTC),
                driver_name="Mr Smith",  # Different driver
                from_location="chigumula office",
                project="Bridge Construction"
            )
        ]
        
        # Process the batch
        result = await batch_stock_service.process_batch_movements(movements, UserRole.ADMIN)
        
        # Verify the result
        assert result.total_entries == 2
        assert result.successful_entries == 2
        assert result.failed_entries == 0
        
        # Verify that stock_in was called with driver and location parameters
        batch_stock_service.stock_service.stock_in.assert_called()
        call_args = batch_stock_service.stock_service.stock_in.call_args_list
        
        # Check first call
        assert call_args[0][1].get('driver_name') == "Mr Longwe"
        assert call_args[0][1].get('from_location') == "chigumula office"
        
        # Check second call
        assert call_args[1][1].get('driver_name') == "Mr Smith"
        assert call_args[1][1].get('from_location') == "chigumula office"

    @pytest.mark.asyncio
    async def test_missing_project_field(self, batch_stock_service):
        """Test that missing project field is handled correctly."""
        # Mock the stock service to simulate validation error for missing project
        batch_stock_service.stock_service.stock_in.reset_mock()
        batch_stock_service.stock_service.stock_in.side_effect = [
            (False, "Missing required project field")
        ]
        
        # Create test movement without project field
        movements = [
            StockMovement(
                item_name="cement",
                movement_type=MovementType.IN,
                quantity=50.0,
                unit="bags",
                signed_base_quantity=50.0,
                user_id="123",
                user_name="testuser",
                timestamp=datetime.now(UTC),
                driver_name="Mr Longwe",
                from_location="chigumula office"
                # No project field
            )
        ]
        
        # Process the batch
        result = await batch_stock_service.process_batch_movements(movements, UserRole.ADMIN)
        
        # Verify the result
        assert result.total_entries == 1
        assert result.successful_entries == 0
        assert result.failed_entries == 1
        assert result.success_rate == 0.0
        
        # Verify that the error message mentions missing project
        assert any("Missing required project field" in error.message for error in result.errors)

    @pytest.mark.asyncio
    async def test_different_projects_in_batch(self, batch_stock_service):
        """Test processing a batch with different projects."""
        # Create test movements with different project fields
        movements = [
            StockMovement(
                item_name="cement",
                movement_type=MovementType.IN,
                quantity=50.0,
                unit="bags",
                signed_base_quantity=50.0,
                user_id="123",
                user_name="testuser",
                timestamp=datetime.now(UTC),
                project="Bridge Construction"
            ),
            StockMovement(
                item_name="steel bars",
                movement_type=MovementType.IN,
                quantity=100.0,
                unit="pieces",
                signed_base_quantity=100.0,
                user_id="123",
                user_name="testuser",
                timestamp=datetime.now(UTC),
                project="Road Construction"  # Different project
            )
        ]
        
        # Process the batch
        result = await batch_stock_service.process_batch_movements(movements, UserRole.ADMIN)
        
        # Verify the result
        assert result.total_entries == 2
        assert result.successful_entries == 2
        assert result.failed_entries == 0
        
        # Verify that stock_in was called with correct project parameters
        batch_stock_service.stock_service.stock_in.assert_called()
        call_args = batch_stock_service.stock_service.stock_in.call_args_list
        
        # Check first call
        assert call_args[0][1].get('project') == "Bridge Construction"
        
        # Check second call
        assert call_args[1][1].get('project') == "Road Construction"
