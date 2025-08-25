"""Tests for the Airtable integration with global parameters."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC

from src.airtable_client import AirtableClient
from src.schemas import StockMovement, MovementType, MovementStatus


class TestAirtableIntegrationWithGlobalParams:
    """Test the Airtable integration with global parameters."""

    @pytest.fixture
    def airtable_client(self):
        """Create an Airtable client with mocked dependencies."""
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.airtable_api_key = "test_key"
        mock_settings.airtable_base_id = "test_base"
        
        # Mock the API and tables
        with patch("src.airtable_client.Api") as mock_api_class:
            mock_api = MagicMock()
            mock_api_class.return_value = mock_api
            
            mock_base = MagicMock()
            mock_api.base.return_value = mock_base
            
            mock_movements_table = MagicMock()
            mock_base.table.return_value = mock_movements_table
            
            # Mock create method
            mock_movements_table.create.return_value = {"id": "rec123"}
            
            # Create client
            client = AirtableClient(mock_settings)
            
            # Add mocks for testing
            client._get_person_id_by_telegram_user = AsyncMock(return_value="rec_person")
            client._get_telegram_user_record_id = AsyncMock(return_value="rec_telegram_user")
            client._get_location_id_by_name = AsyncMock(return_value="rec_location")
            client.get_item = AsyncMock(return_value=None)
            client.create_item_if_not_exists = AsyncMock(return_value="rec_item")
            
            return client

    @pytest.mark.asyncio
    async def test_create_movement_with_project(self, airtable_client):
        """Test creating a movement with project field."""
        # Create a movement with project field
        movement = StockMovement(
            item_name="cement",
            movement_type=MovementType.IN,
            quantity=50.0,
            unit="bags",
            signed_base_quantity=50.0,
            user_id="123",
            user_name="testuser",
            timestamp=datetime.now(UTC),
            status=MovementStatus.POSTED,
            driver_name="Mr Longwe",
            from_location="chigumula office",
            project="Bridge Construction"
        )
        
        # Create the movement
        movement_id = await airtable_client.create_movement(movement)
        
        # Verify the result
        assert movement_id == "rec123"
        
        # Verify that create was called with project field
        airtable_client.movements_table.create.assert_called_once()
        call_args = airtable_client.movements_table.create.call_args[0][0]
        
        # Check that project field was included
        assert call_args["From/To Project"] == "Bridge Construction"

    @pytest.mark.asyncio
    async def test_create_movement_with_all_global_params(self, airtable_client):
        """Test creating a movement with all global parameters."""
        # Create a movement with all global parameters
        movement = StockMovement(
            item_name="cement",
            movement_type=MovementType.IN,
            quantity=50.0,
            unit="bags",
            signed_base_quantity=50.0,
            user_id="123",
            user_name="testuser",
            timestamp=datetime.now(UTC),
            status=MovementStatus.POSTED,
            driver_name="Mr Longwe",
            from_location="chigumula office",
            to_location="site A",
            project="Bridge Construction"
        )
        
        # Create the movement
        movement_id = await airtable_client.create_movement(movement)
        
        # Verify the result
        assert movement_id == "rec123"
        
        # Verify that create was called with all global parameters
        airtable_client.movements_table.create.assert_called_once()
        call_args = airtable_client.movements_table.create.call_args[0][0]
        
        # Check that all global parameters were included
        assert call_args["Driver's Name"] == "Mr Longwe"
        assert call_args["From/To Location"] == "chigumula office"
        assert call_args["From/To Project"] == "Bridge Construction"

    @pytest.mark.asyncio
    async def test_create_movement_without_project(self, airtable_client):
        """Test creating a movement without project field."""
        # Create a movement without project field
        movement = StockMovement(
            item_name="cement",
            movement_type=MovementType.IN,
            quantity=50.0,
            unit="bags",
            signed_base_quantity=50.0,
            user_id="123",
            user_name="testuser",
            timestamp=datetime.now(UTC),
            status=MovementStatus.POSTED,
            driver_name="Mr Longwe",
            from_location="chigumula office"
            # No project field
        )
        
        # Create the movement
        movement_id = await airtable_client.create_movement(movement)
        
        # Verify the result
        assert movement_id == "rec123"
        
        # Verify that create was called without project field
        airtable_client.movements_table.create.assert_called_once()
        call_args = airtable_client.movements_table.create.call_args[0][0]
        
        # Check that project field was not included
        assert "From/To Project" not in call_args
