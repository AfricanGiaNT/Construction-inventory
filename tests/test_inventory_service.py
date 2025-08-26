"""Tests for inventory service functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.services.inventory import InventoryService, InventoryEntry
from src.schemas import Item


class TestInventoryService:
    """Test the inventory service functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_airtable = AsyncMock()
        self.mock_settings = MagicMock()
        self.service = InventoryService(self.mock_airtable, self.mock_settings)
    
    @pytest.mark.asyncio
    async def test_process_inventory_stocktake_success(self):
        """Test successful inventory stocktake processing."""
        # Mock the parser to return valid result
        mock_parse_result = MagicMock()
        mock_parse_result.is_valid = True
        mock_parse_result.entries = [
            InventoryEntry("Cement 32.5", 50.0, 2, "Cement 32.5, 50"),
            InventoryEntry("Steel bars", 120.0, 3, "Steel bars, 120.0")
        ]
        mock_parse_result.header.date = "25/08/25"
        mock_parse_result.header.logged_by = ["Trevor", "Kayesera"]
        
        # Mock the parser
        self.service.parser.parse_inventory_command = MagicMock(return_value=mock_parse_result)
        
        # Mock airtable responses
        self.mock_airtable.get_item.side_effect = [
            Item(name="Cement 32.5", base_unit="bag", on_hand=30.0, units=[]),  # Existing item
            None,  # New item (first call)
            Item(name="Steel bars", base_unit="piece", on_hand=0.0, units=[])   # New item (second call after creation)
        ]
        self.mock_airtable.update_item_stock.return_value = True
        self.mock_airtable.create_item_if_not_exists.return_value = "new_item_id"
        
        # Process the command
        command_text = "date:25/08/25 logged by: Trevor,Kayesera\nCement 32.5, 50\nSteel bars, 120.0"
        success, message = await self.service.process_inventory_stocktake(command_text, 123, "TestUser")
        
        assert success is True
        assert "Inventory Stocktake Complete" in message
        assert "Items updated: 1" in message
        assert "Items created: 1" in message
        assert "Items failed: 0" in message
        
        # Verify airtable calls
        assert self.mock_airtable.get_item.call_count == 3  # 2 initial checks + 1 for new item during stock update
        assert self.mock_airtable.update_item_stock.call_count == 2
        assert self.mock_airtable.create_item_if_not_exists.call_count == 1
    
    @pytest.mark.asyncio
    async def test_process_inventory_stocktake_parse_failure(self):
        """Test inventory stocktake with parse failure."""
        # Mock the parser to return invalid result
        mock_parse_result = MagicMock()
        mock_parse_result.is_valid = False
        mock_parse_result.errors = ["Invalid header format"]
        
        self.service.parser.parse_inventory_command = MagicMock(return_value=mock_parse_result)
        
        # Process the command
        command_text = "invalid command"
        success, message = await self.service.process_inventory_stocktake(command_text, 123, "TestUser")
        
        assert success is False
        assert "Inventory Command Parse Errors" in message
        assert "Invalid header format" in message
    
    @pytest.mark.asyncio
    async def test_process_inventory_entry_existing_item(self):
        """Test processing existing inventory entry."""
        # Mock existing item
        existing_item = Item(name="Cement 32.5", base_unit="bag", on_hand=30.0, units=[])
        self.mock_airtable.get_item.return_value = existing_item
        self.mock_airtable.update_item_stock.return_value = True
        
        entry = InventoryEntry("Cement 32.5", 50.0, 2, "Cement 32.5, 50")
        result = await self.service._process_inventory_entry(entry)
        
        assert result["success"] is True
        assert result["created"] is False
        assert result["item_name"] == "Cement 32.5"
        assert result["quantity"] == 50.0
        assert result["previous_quantity"] == 30.0
        assert "Updated Cement 32.5: 30.0 → 50.0" in result["message"]
        
        # Verify airtable calls
        self.mock_airtable.get_item.assert_called_once_with("Cement 32.5")
        self.mock_airtable.update_item_stock.assert_called_once_with("Cement 32.5", 20.0)  # quantity_change = 50 - 30 = 20
    
    @pytest.mark.asyncio
    async def test_process_inventory_entry_new_item(self):
        """Test processing new inventory entry."""
        # Mock new item (doesn't exist)
        self.mock_airtable.get_item.side_effect = [
            None,  # First call: check if item exists
            Item(name="New Item", base_unit="piece", on_hand=0.0, units=[])  # Second call: during stock update
        ]
        self.mock_airtable.create_item_if_not_exists.return_value = "new_item_id"
        self.mock_airtable.update_item_stock.return_value = True
        
        entry = InventoryEntry("New Item", 25.0, 2, "New Item, 25")
        result = await self.service._process_inventory_entry(entry)
        
        assert result["success"] is True
        assert result["created"] is True
        assert result["item_name"] == "New Item"
        assert result["quantity"] == 25.0
        assert result["previous_quantity"] == 0
        assert "Created New Item with 25.0 pieces" in result["message"]
        
        # Verify airtable calls
        assert self.mock_airtable.get_item.call_count == 2
        self.mock_airtable.create_item_if_not_exists.assert_called_once_with(
            "New Item", base_unit="piece", category="General"
        )
        assert self.mock_airtable.update_item_stock.call_count == 1
    
    @pytest.mark.asyncio
    async def test_process_inventory_entry_update_failure(self):
        """Test processing inventory entry with update failure."""
        # Mock existing item
        existing_item = Item(name="Cement 32.5", base_unit="bag", on_hand=30.0, units=[])
        self.mock_airtable.get_item.return_value = existing_item
        self.mock_airtable.update_item_stock.return_value = False
        
        entry = InventoryEntry("Cement 32.5", 50.0, 2, "Cement 32.5, 50")
        result = await self.service._process_inventory_entry(entry)
        
        assert result["success"] is False
        assert result["created"] is False
        assert result["item_name"] == "Cement 32.5"
        assert result["quantity"] == 50.0
        assert "Failed to update Cement 32.5" in result["message"]
    
    @pytest.mark.asyncio
    async def test_process_inventory_entry_creation_failure(self):
        """Test processing inventory entry with creation failure."""
        # Mock new item (doesn't exist)
        self.mock_airtable.get_item.return_value = None
        self.mock_airtable.create_item_if_not_exists.return_value = None
        
        entry = InventoryEntry("New Item", 25.0, 2, "New Item, 25")
        result = await self.service._process_inventory_entry(entry)
        
        assert result["success"] is False
        assert result["created"] is False
        assert result["item_name"] == "New Item"
        assert result["quantity"] == 25.0
        assert "Failed to create New Item" in result["message"]
    
    @pytest.mark.asyncio
    async def test_process_inventory_entry_creation_success_update_failure(self):
        """Test processing inventory entry with successful creation but update failure."""
        # Mock new item (doesn't exist)
        self.mock_airtable.get_item.return_value = None
        self.mock_airtable.create_item_if_not_exists.return_value = "new_item_id"
        self.mock_airtable.update_item_stock.return_value = False
        
        entry = InventoryEntry("New Item", 25.0, 2, "New Item, 25")
        result = await self.service._process_inventory_entry(entry)
        
        assert result["success"] is False
        assert result["created"] is True
        assert result["item_name"] == "New Item"
        assert result["quantity"] == 25.0
        assert "Created New Item but failed to set stock level" in result["message"]
    
    @pytest.mark.asyncio
    async def test_update_item_stock_success(self):
        """Test successful item stock update."""
        # Mock existing item
        existing_item = Item(name="Cement 32.5", base_unit="bag", on_hand=30.0, units=[])
        self.mock_airtable.get_item.return_value = existing_item
        self.mock_airtable.update_item_stock.return_value = True
        
        success = await self.service._update_item_stock("Cement 32.5", 50.0)
        
        assert success is True
        
        # Verify the calculation: new_quantity - current_quantity = 50 - 30 = 20
        self.mock_airtable.update_item_stock.assert_called_once_with("Cement 32.5", 20.0)
    
    @pytest.mark.asyncio
    async def test_update_item_stock_item_not_found(self):
        """Test item stock update when item doesn't exist."""
        self.mock_airtable.get_item.return_value = None
        
        success = await self.service._update_item_stock("Non-existent Item", 50.0)
        
        assert success is False
        self.mock_airtable.update_item_stock.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_update_item_stock_update_failure(self):
        """Test item stock update when airtable update fails."""
        # Mock existing item
        existing_item = Item(name="Cement 32.5", base_unit="bag", on_hand=30.0, units=[])
        self.mock_airtable.get_item.return_value = existing_item
        self.mock_airtable.update_item_stock.return_value = False
        
        success = await self.service._update_item_stock("Cement 32.5", 50.0)
        
        assert success is False
    
    @pytest.mark.asyncio
    async def test_update_item_stock_to_zero(self):
        """Test updating item stock to zero."""
        # Mock existing item
        existing_item = Item(name="Cement 32.5", base_unit="bag", on_hand=30.0, units=[])
        self.mock_airtable.get_item.return_value = existing_item
        self.mock_airtable.update_item_stock.return_value = True
        
        success = await self.service._update_item_stock("Cement 32.5", 0.0)
        
        assert success is True
        
        # Verify the calculation: new_quantity - current_quantity = 0 - 30 = -30
        self.mock_airtable.update_item_stock.assert_called_once_with("Cement 32.5", -30.0)
    
    def test_generate_summary_success(self):
        """Test summary generation for successful inventory operation."""
        from src.services.inventory import InventoryHeader
        
        header = InventoryHeader("25/08/25", ["Trevor", "Kayesera"], "date:25/08/25 logged by: Trevor,Kayesera")
        results = [
            {"success": True, "created": False, "item_name": "Cement 32.5", "message": "Updated Cement 32.5: 30 → 50"},
            {"success": True, "created": True, "item_name": "New Item", "message": "Created New Item with 25 pieces"},
            {"success": False, "created": False, "item_name": "Failed Item", "message": "Failed to update Failed Item"}
        ]
        
        summary = self.service._generate_summary(header, 1, 1, 1, results)
        
        assert "Inventory Stocktake Complete" in summary
        assert "Date:</b> 25/08/25" in summary
        assert "Logged by:</b> Trevor, Kayesera" in summary
        assert "Items updated: 1" in summary
        assert "Items created: 1" in summary
        assert "Items failed: 1" in summary
        assert "Failed Items:" in summary
        assert "Failed Item: Failed to update Failed Item" in summary
    
    def test_generate_summary_no_failures(self):
        """Test summary generation with no failures."""
        from src.services.inventory import InventoryHeader
        
        header = InventoryHeader("25/08/25", ["Trevor"], "date:25/08/25 logged by: Trevor")
        results = [
            {"success": True, "created": False, "item_name": "Cement 32.5", "message": "Updated Cement 32.5: 30 → 50"},
            {"success": True, "created": True, "item_name": "New Item", "message": "Created New Item with 25 pieces"}
        ]
        
        summary = self.service._generate_summary(header, 1, 1, 0, results)
        
        assert "Items failed: 0" in summary
        assert "Failed Items:" not in summary  # Should not show failed items section
    
    def test_generate_summary_empty_results(self):
        """Test summary generation with empty results."""
        from src.services.inventory import InventoryHeader
        
        header = InventoryHeader("25/08/25", ["Trevor"], "date:25/08/25 logged by: Trevor")
        results = []
        
        summary = self.service._generate_summary(header, 0, 0, 0, results)
        
        assert "Items updated: 0" in summary
        assert "Items created: 0" in summary
        assert "Items failed: 0" in summary
        assert "Failed Items:" not in summary


class TestInventoryServiceIntegration:
    """Test inventory service integration scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_airtable = AsyncMock()
        self.mock_settings = MagicMock()
        self.service = InventoryService(self.mock_airtable, self.mock_settings)
    
    @pytest.mark.asyncio
    async def test_mixed_success_failure_scenario(self):
        """Test scenario with mixed success and failure results."""
        # Mock the parser to return valid result
        mock_parse_result = MagicMock()
        mock_parse_result.is_valid = True
        mock_parse_result.entries = [
            InventoryEntry("Cement 32.5", 50.0, 2, "Cement 32.5, 50"),      # Existing item, update success
            InventoryEntry("Steel bars", 120.0, 3, "Steel bars, 120.0"),    # New item, creation success
            InventoryEntry("Failed item", 25.0, 4, "Failed item, 25")       # New item, creation failure
        ]
        mock_parse_result.header.date = "25/08/25"
        mock_parse_result.header.logged_by = ["Trevor"]
        
        self.service.parser.parse_inventory_command = MagicMock(return_value=mock_parse_result)
        
        # Mock airtable responses for different scenarios
        self.mock_airtable.get_item.side_effect = [
            Item(name="Cement 32.5", base_unit="bag", on_hand=30.0, units=[]),  # Existing item
            None,  # New item (first call)
            Item(name="Steel bars", base_unit="piece", on_hand=0.0, units=[]),  # New item (second call after creation)
            None,  # Failed item (first call)
            Item(name="Failed item", base_unit="piece", on_hand=0.0, units=[])   # Failed item (second call after creation)
        ]
        self.mock_airtable.update_item_stock.side_effect = [True, True, False]  # Last update fails
        self.mock_airtable.create_item_if_not_exists.side_effect = ["new_item_id", None]  # Second creation fails
        
        # Process the command
        command_text = "date:25/08/25 logged by: Trevor\nCement 32.5, 50\nSteel bars, 120.0\nFailed item, 25"
        success, message = await self.service.process_inventory_stocktake(command_text, 123, "TestUser")
        
        assert success is True  # Overall success even with some failures
        assert "Items updated: 1" in message
        assert "Items created: 1" in message
        assert "Items failed: 1" in message
        assert "Failed item: Failed to create Failed item" in message
    
    @pytest.mark.asyncio
    async def test_large_batch_processing(self):
        """Test processing a large batch of items."""
        # Create 50 entries (at the limit)
        entries = [InventoryEntry(f"Item {i}", float(i), i+2, f"Item {i}, {i}") for i in range(50)]
        
        mock_parse_result = MagicMock()
        mock_parse_result.is_valid = True
        mock_parse_result.entries = entries
        mock_parse_result.header.date = "25/08/25"
        mock_parse_result.header.logged_by = ["Trevor"]
        
        self.service.parser.parse_inventory_command = MagicMock(return_value=mock_parse_result)
        
        # Mock all items as existing
        self.mock_airtable.get_item.return_value = Item(name="Test", base_unit="piece", on_hand=0.0, units=[])
        self.mock_airtable.update_item_stock.return_value = True
        
        # Process the command
        command_text = "date:25/08/25 logged by: Trevor\n" + "\n".join([f"Item {i}, {i}" for i in range(50)])
        success, message = await self.service.process_inventory_stocktake(command_text, 123, "TestUser")
        
        assert success is True
        assert "Items updated: 50" in message
        assert "Items created: 0" in message
        assert "Items failed: 0" in message
        
        # Verify all items were processed
        assert self.mock_airtable.get_item.call_count == 50
        assert self.mock_airtable.update_item_stock.call_count == 50
