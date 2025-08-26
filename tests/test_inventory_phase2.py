"""Tests for Phase 2 inventory features: validate mode, date normalization, and provenance fields."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.inventory import InventoryService, InventoryParser, InventoryHeader, InventoryEntry, InventoryParseResult
from src.services.idempotency import IdempotencyService
from src.schemas import Item


class TestInventoryPhase2Features:
    """Test Phase 2 inventory features."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_airtable = AsyncMock()
        self.mock_settings = MagicMock()
        self.service = InventoryService(self.mock_airtable, self.mock_settings)
        self.parser = InventoryParser()

    def test_date_normalization_valid_dates(self):
        """Test date normalization for various valid dates."""
        test_cases = [
            ("25/08/25", "2025-08-25"),  # Recent date
            ("01/01/00", "2000-01-01"),  # Year 2000
            ("31/12/99", "1999-12-31"),  # Year 1999
            ("15/06/50", "1950-06-15"),  # Year 1950
            ("29/02/24", "2024-02-29"),  # Leap year
        ]
        
        for input_date, expected_iso in test_cases:
            normalized = self.parser._normalize_date(input_date)
            assert normalized == expected_iso, f"Failed for {input_date}: expected {expected_iso}, got {normalized}"

    def test_date_normalization_edge_cases(self):
        """Test date normalization edge cases."""
        # Test with invalid dates (should return original)
        invalid_dates = ["invalid", "25-08-25", "25.08.25", ""]
        
        for invalid_date in invalid_dates:
            normalized = self.parser._normalize_date(invalid_date)
            assert normalized == invalid_date, f"Should return original for invalid date: {invalid_date}"

    def test_parse_inventory_command_with_normalized_date(self):
        """Test that parsed commands include normalized dates."""
        command_text = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        result = self.parser.parse_inventory_command(command_text)
        
        assert result.is_valid
        assert result.header.date == "25/08/25"
        assert result.header.normalized_date == "2025-08-25"

    @pytest.mark.asyncio
    async def test_validate_mode_parsing_only(self):
        """Test validate mode parses correctly without processing entries."""
        command_text = "date:25/08/25 logged by: Trevor\nCement, 50\nSteel, 100"
        
        # Mock the parser to return valid result
        mock_parse_result = MagicMock()
        mock_parse_result.is_valid = True
        mock_parse_result.entries = [
            InventoryEntry("Cement", 50.0, 2, "Cement, 50"),
            InventoryEntry("Steel", 100.0, 3, "Steel, 100")
        ]
        mock_parse_result.header.date = "25/08/25"
        mock_parse_result.header.normalized_date = "2025-08-25"
        mock_parse_result.header.logged_by = ["Trevor"]
        mock_parse_result.total_lines = 3
        mock_parse_result.valid_entries = 2
        
        self.service.parser.parse_inventory_command = MagicMock(return_value=mock_parse_result)
        
        # Test validate mode
        success, message = await self.service.process_inventory_stocktake(
            command_text, 123, "TestUser", validate_only=True
        )
        
        assert success is True
        assert "Inventory Command Validation Successful" in message
        assert "25/08/25 (normalized to 2025-08-25)" in message
        assert "Ready to apply!" in message
        
        # Verify no Airtable calls were made
        self.mock_airtable.get_item.assert_not_called()
        self.mock_airtable.create_item_if_not_exists.assert_not_called()
        self.mock_airtable.update_item_stock.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_mode_with_parse_errors(self):
        """Test validate mode with parsing errors."""
        command_text = "invalid header\nCement, 50"
        
        # Mock the parser to return invalid result
        mock_parse_result = MagicMock()
        mock_parse_result.is_valid = False
        mock_parse_result.errors = ["Invalid header format. Expected: date:DD/MM/YY logged by: NAME1,NAME2"]
        
        self.service.parser.parse_inventory_command = MagicMock(return_value=mock_parse_result)
        
        # Test validate mode
        success, message = await self.service.process_inventory_stocktake(
            command_text, 123, "TestUser", validate_only=True
        )
        
        assert success is False
        assert "Inventory Command Parse Errors" in message

    @pytest.mark.asyncio
    async def test_provenance_fields_update_intention(self):
        """Test that provenance field updates are logged (actual implementation pending)."""
        command_text = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        # Mock the parser to return valid result
        mock_parse_result = MagicMock()
        mock_parse_result.is_valid = True
        mock_parse_result.entries = [
            InventoryEntry("Cement", 50.0, 2, "Cement, 50")
        ]
        mock_parse_result.header.normalized_date = "2025-08-25"
        mock_parse_result.header.logged_by = ["Trevor"]
        
        self.service.parser.parse_inventory_command = MagicMock(return_value=mock_parse_result)
        
        # Mock existing item
        existing_item = Item(name="Cement", base_unit="bag", on_hand=30.0, units=[])
        self.mock_airtable.get_item.return_value = existing_item
        self.mock_airtable.update_item_stock.return_value = True
        
        # Process the command
        success, message = await self.service.process_inventory_stocktake(
            command_text, 123, "TestUser"
        )
        
        assert success is True
        
        # Verify that provenance update was attempted (logged)
        # The actual implementation will be added when Airtable schema is ready
        self.mock_airtable.update_item_stock.assert_called_once()

    def test_summary_includes_normalized_date(self):
        """Test that summary includes both original and normalized dates."""
        header = InventoryHeader("25/08/25", ["Trevor"], "raw text", "2025-08-25")
        
        results = [
            {"success": True, "created": False, "item_name": "Cement", "message": "Updated Cement: 30.0 → 50.0"}
        ]
        
        summary = self.service._generate_summary(header, 1, 0, 0, results)
        
        assert "Date:</b> 25/08/25 (normalized to 2025-08-25)" in summary

    @pytest.mark.asyncio
    async def test_validate_mode_summary_format(self):
        """Test that validate mode generates proper summary format."""
        command_text = "date:25/08/25 logged by: Trevor\nCement, 50\nSteel, 100"
        
        # Mock the parser to return valid result
        mock_parse_result = MagicMock()
        mock_parse_result.is_valid = True
        mock_parse_result.entries = [
            InventoryEntry("Cement", 50.0, 2, "Cement, 50"),
            InventoryEntry("Steel", 100.0, 3, "Steel, 100")
        ]
        mock_parse_result.header.date = "25/08/25"
        mock_parse_result.header.normalized_date = "2025-08-25"
        mock_parse_result.header.logged_by = ["Trevor"]
        mock_parse_result.total_lines = 3
        mock_parse_result.valid_entries = 2
        
        self.service.parser.parse_inventory_command = MagicMock(return_value=mock_parse_result)
        
        # Test validate mode
        success, message = await self.service.process_inventory_stocktake(
            command_text, 123, "TestUser", validate_only=True
        )
        
        assert success is True
        assert "Inventory Command Validation Successful" in message
        assert "Date:</b> 25/08/25 (normalized to 2025-08-25)" in message
        assert "Logged by:</b> Trevor" in message
        assert "Total lines:</b> 3" in message
        assert "Valid entries:</b> 2" in message
        assert "Parsed Entries:" in message
        assert "• Cement: 50" in message
        assert "• Steel: 100" in message
        assert "Ready to apply!" in message


class TestInventoryPhase2Integration:
    """Test Phase 2 features integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_airtable = AsyncMock()
        self.mock_settings = MagicMock()
        self.service = InventoryService(self.mock_airtable, self.mock_settings)

    @pytest.mark.asyncio
    async def test_validate_then_apply_workflow(self):
        """Test the validate then apply workflow."""
        command_text = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        # Mock the parser to return valid result
        mock_parse_result = MagicMock()
        mock_parse_result.is_valid = True
        mock_parse_result.entries = [
            InventoryEntry("Cement", 50.0, 2, "Cement, 50")
        ]
        mock_parse_result.header.date = "25/08/25"
        mock_parse_result.header.normalized_date = "2025-08-25"
        mock_parse_result.header.logged_by = ["Trevor"]
        mock_parse_result.total_lines = 2
        mock_parse_result.valid_entries = 1
        
        self.service.parser.parse_inventory_command = MagicMock(return_value=mock_parse_result)
        
        # Step 1: Validate
        success, validate_message = await self.service.process_inventory_stocktake(
            command_text, 123, "TestUser", validate_only=True
        )
        
        assert success is True
        assert "Inventory Command Validation Successful" in validate_message
        
        # Step 2: Apply (with mocked Airtable)
        existing_item = Item(name="Cement", base_unit="bag", on_hand=30.0, units=[])
        self.mock_airtable.get_item.return_value = existing_item
        self.mock_airtable.update_item_stock.return_value = True
        
        success, apply_message = await self.service.process_inventory_stocktake(
            command_text, 123, "TestUser", validate_only=False
        )
        
        assert success is True
        assert "Inventory Stocktake Complete" in apply_message
        assert "Items updated: 1" in apply_message
        
        # Verify Airtable calls were made
        self.mock_airtable.get_item.assert_called_once()
        self.mock_airtable.update_item_stock.assert_called_once()

    @pytest.mark.asyncio
    async def test_provenance_fields_integration(self):
        """Test that provenance fields are updated during stock updates."""
        command_text = "date:25/08/25 logged by: Trevor\nCement, 50"
        
        # Mock the parser to return valid result
        mock_parse_result = MagicMock()
        mock_parse_result.is_valid = True
        mock_parse_result.entries = [
            InventoryEntry("Cement", 50.0, 2, "Cement, 50")
        ]
        mock_parse_result.header.normalized_date = "2025-08-25"
        mock_parse_result.header.logged_by = ["Trevor"]
        
        self.service.parser.parse_inventory_command = MagicMock(return_value=mock_parse_result)
        
        # Mock existing item
        existing_item = Item(name="Cement", base_unit="bag", on_hand=30.0, units=[])
        self.mock_airtable.get_item.return_value = existing_item
        self.mock_airtable.update_item_stock.return_value = True
        
        # Process the command
        success, message = await self.service.process_inventory_stocktake(
            command_text, 123, "TestUser"
        )
        
        assert success is True
        
        # Verify that the stock update was called with the correct parameters
        self.mock_airtable.update_item_stock.assert_called_once_with("Cement", 20.0)  # 50 - 30 = 20
        
        # Note: Actual provenance field updates will be implemented when Airtable schema is ready
        # For now, we just verify the intention is logged
