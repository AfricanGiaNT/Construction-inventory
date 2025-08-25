"""Tests for the global parameters feature in batch commands."""

import pytest
from datetime import datetime, UTC
from typing import Dict, List, Optional, Tuple

from src.nlp_parser import NLPStockParser
from src.schemas import StockMovement, MovementType, BatchFormat, BatchParseResult


class TestGlobalParameters:
    """Test global parameters in batch commands."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance for testing."""
        return NLPStockParser()

    def test_parse_global_parameters_single(self, parser):
        """Test parsing a single global parameter."""
        text = "/in driver: Mr Longwe, cement, 50 bags"
        global_params, remaining_text = parser.parse_global_parameters(text)
        
        assert global_params == {"driver": "Mr Longwe"}
        assert "cement, 50 bags" in remaining_text
        assert remaining_text.startswith("/in ")

    def test_parse_global_parameters_multiple(self, parser):
        """Test parsing multiple global parameters."""
        text = "/in driver: Mr Longwe, from: chigumula office, project: Bridge Construction, cement, 50 bags"
        global_params, remaining_text = parser.parse_global_parameters(text)
        
        assert global_params == {
            "driver": "Mr Longwe",
            "from": "chigumula office",
            "project": "Bridge Construction"
        }
        assert "cement, 50 bags" in remaining_text
        assert remaining_text.startswith("/in ")

    def test_parse_global_parameters_none(self, parser):
        """Test parsing with no global parameters."""
        text = "/in cement, 50 bags"
        global_params, remaining_text = parser.parse_global_parameters(text)
        
        assert global_params == {}
        assert remaining_text == text

    def test_parse_global_parameters_different_order(self, parser):
        """Test parsing global parameters in different order."""
        text = "/in project: Bridge Construction, driver: Mr Longwe, from: chigumula office, cement, 50 bags"
        global_params, remaining_text = parser.parse_global_parameters(text)
        
        assert global_params == {
            "driver": "Mr Longwe",
            "from": "chigumula office",
            "project": "Bridge Construction"
        }
        assert "cement, 50 bags" in remaining_text

    def test_apply_global_parameters(self, parser):
        """Test applying global parameters to movements."""
        global_params = {
            "driver": "Mr Longwe",
            "from": "chigumula office",
            "project": "Bridge Construction"
        }
        
        movements = [
            StockMovement(
                item_name="cement",
                movement_type=MovementType.IN,
                quantity=50,
                unit="bags",
                signed_base_quantity=50,
                user_id="123",
                user_name="testuser",
                timestamp=datetime.now(UTC)
            ),
            StockMovement(
                item_name="steel",
                movement_type=MovementType.IN,
                quantity=100,
                unit="pieces",
                signed_base_quantity=100,
                user_id="123",
                user_name="testuser",
                timestamp=datetime.now(UTC)
            )
        ]
        
        updated_movements = parser.apply_global_parameters(movements, global_params)
        
        for movement in updated_movements:
            assert movement.driver_name == "Mr Longwe"
            assert movement.from_location == "chigumula office"
            assert movement.project == "Bridge Construction"

    def test_apply_global_parameters_with_override(self, parser):
        """Test applying global parameters with entry-specific overrides."""
        global_params = {
            "driver": "Mr Longwe",
            "from": "chigumula office",
            "project": "Bridge Construction"
        }
        
        movements = [
            StockMovement(
                item_name="cement",
                movement_type=MovementType.IN,
                quantity=50,
                unit="bags",
                signed_base_quantity=50,
                user_id="123",
                user_name="testuser",
                timestamp=datetime.now(UTC),
                driver_name="Mr Smith"  # Override driver
            ),
            StockMovement(
                item_name="steel",
                movement_type=MovementType.IN,
                quantity=100,
                unit="pieces",
                signed_base_quantity=100,
                user_id="123",
                user_name="testuser",
                timestamp=datetime.now(UTC)
            )
        ]
        
        updated_movements = parser.apply_global_parameters(movements, global_params)
        
        # First movement should keep its specific driver
        assert updated_movements[0].driver_name == "Mr Smith"
        assert updated_movements[0].from_location == "chigumula office"
        assert updated_movements[0].project == "Bridge Construction"
        
        # Second movement should use all global parameters
        assert updated_movements[1].driver_name == "Mr Longwe"
        assert updated_movements[1].from_location == "chigumula office"
        assert updated_movements[1].project == "Bridge Construction"

    def test_batch_parse_with_global_parameters_newline(self, parser):
        """Test parsing a batch with global parameters using newline format."""
        text = "/in driver: Mr Longwe, from: chigumula office, project: Bridge Construction\ncement, 50 bags\nsteel bars, 100 pieces"
        result = parser.parse_batch_entries(text, 123, "testuser")
        
        assert result.format == BatchFormat.NEWLINE
        assert len(result.movements) == 2
        assert result.global_parameters == {
            "driver": "Mr Longwe",
            "from": "chigumula office",
            "project": "Bridge Construction"
        }
        
        for movement in result.movements:
            assert movement.driver_name == "Mr Longwe"
            assert movement.from_location == "chigumula office"
            assert movement.project == "Bridge Construction"

    def test_batch_parse_with_global_parameters_semicolon(self, parser):
        """Test parsing a batch with global parameters using semicolon format."""
        text = "/in driver: Mr Longwe, project: Bridge Construction, cement, 50 bags; steel bars, 100 pieces"
        result = parser.parse_batch_entries(text, 123, "testuser")
        
        assert result.format == BatchFormat.SEMICOLON
        assert len(result.movements) == 2
        assert result.global_parameters == {
            "driver": "Mr Longwe",
            "project": "Bridge Construction"
        }
        
        for movement in result.movements:
            assert movement.driver_name == "Mr Longwe"
            assert movement.project == "Bridge Construction"

    def test_batch_parse_with_entry_specific_override(self, parser):
        """Test parsing a batch with entry-specific parameters that override globals."""
        text = "/in driver: Mr Longwe, from: chigumula office, project: Bridge Construction\ncement, 50 bags\nsteel bars, 100 pieces, by Mr Smith"
        result = parser.parse_batch_entries(text, 123, "testuser")
        
        assert result.format == BatchFormat.NEWLINE
        assert len(result.movements) == 2
        
        # First movement should use global driver
        assert result.movements[0].driver_name == "Mr Longwe"
        
        # Second movement should use its specific driver
        assert result.movements[1].driver_name == "Mr Smith"
        
        # Both should use global project and from_location
        for movement in result.movements:
            assert movement.from_location == "chigumula office"
            assert movement.project == "Bridge Construction"

    def test_project_required_validation(self, parser):
        """Test that project is required in validation."""
        text = "/in cement, 50 bags\nsteel bars, 100 pieces"
        result = parser.parse_batch_entries(text, 123, "testuser")
        
        assert not result.is_valid
        assert any("Missing project name" in error for error in result.errors)

    def test_global_parameters_in_error_message(self, parser):
        """Test that global parameters are mentioned in error messages when present."""
        text = "/in driver: Mr Longwe, project: Bridge Construction, invalid command"
        result = parser.parse_batch_entries(text, 123, "testuser")
        
        assert not result.is_valid
        assert any("Global parameters were detected" in error for error in result.errors)
        assert any("driver: Mr Longwe" in error for error in result.errors)
        assert any("project: Bridge Construction" in error for error in result.errors)
