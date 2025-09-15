"""Default behavior tests for the batch movement parser."""

import pytest
from src.services.batch_movement_parser import BatchMovementParser
from src.schemas import MovementType, BatchFormat


class TestBatchMovementParserDefaults:
    """Test smart defaults and default behavior of the batch movement parser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = BatchMovementParser()
    
    def test_in_command_defaults(self):
        """Test defaults for /in commands."""
        command = """Solar floodlight panel FS-SFL800, 4
Solar floodlight 800W, 4
Cable 2.5sqmm black 100m, 1"""
        
        result = self.parser.parse_batch_command(command, MovementType.IN)
        
        assert result.is_valid
        batch = result.batches[0]
        
        # Should apply defaults for /in commands
        assert batch.project == "not described"
        assert batch.driver == "not described"
        assert batch.from_location == "not described"
        assert batch.to_location is None  # Not applicable for /in
        
        # Items should be parsed correctly
        assert len(batch.items) == 3
        assert batch.items[0].item_name == "Solar floodlight panel FS-SFL800"
        assert batch.items[0].quantity == 4.0
    
    def test_out_command_defaults(self):
        """Test defaults for /out commands."""
        command = """Solar floodlight panel FS-SFL800, 4
Solar floodlight 800W, 4
Cable 2.5sqmm black 100m, 1"""
        
        result = self.parser.parse_batch_command(command, MovementType.OUT)
        
        assert result.is_valid
        batch = result.batches[0]
        
        # Should apply defaults for /out commands
        assert batch.project == "not described"
        assert batch.driver == "not described"
        assert batch.to_location == "external"
        assert batch.from_location is None  # Not applicable for /out
        
        # Items should be parsed correctly
        assert len(batch.items) == 3
    
    def test_partial_parameters_in_command(self):
        """Test /in command with some parameters specified."""
        command = """project: mzuzu
Solar floodlight panel FS-SFL800, 4
Solar floodlight 800W, 4"""
        
        result = self.parser.parse_batch_command(command, MovementType.IN)
        
        assert result.is_valid
        batch = result.batches[0]
        
        # Specified parameter should be used
        assert batch.project == "mzuzu"
        # Others should use defaults
        assert batch.driver == "not described"
        assert batch.from_location == "not described"
    
    def test_partial_parameters_out_command(self):
        """Test /out command with some parameters specified."""
        command = """driver: Dani maliko
Solar floodlight panel FS-SFL800, 4
Solar floodlight 800W, 4"""
        
        result = self.parser.parse_batch_command(command, MovementType.OUT)
        
        assert result.is_valid
        batch = result.batches[0]
        
        # Specified parameter should be used
        assert batch.driver == "Dani maliko"
        # Others should use defaults
        assert batch.project == "not described"
        assert batch.to_location == "external"
    
    def test_apply_smart_defaults_in(self):
        """Test applying smart defaults to /in batch."""
        from src.schemas import BatchInfo, BatchItem
        
        batch = BatchInfo(
            batch_number=1,
            project=None,  # Should be set to default
            driver="",  # Should be set to default
            from_location=None,  # Should be set to default
            items=[BatchItem(item_name="Test item", quantity=10.0)]
        )
        
        updated_batch = self.parser.apply_smart_defaults(batch, MovementType.IN)
        
        assert updated_batch.project == "not described"
        assert updated_batch.driver == "not described"
        assert updated_batch.from_location == "not described"
        assert updated_batch.to_location is None  # Not applicable for /in
    
    def test_apply_smart_defaults_out(self):
        """Test applying smart defaults to /out batch."""
        from src.schemas import BatchInfo, BatchItem
        
        batch = BatchInfo(
            batch_number=1,
            project="",  # Should be set to default
            driver=None,  # Should be set to default
            to_location="",  # Should be set to default
            items=[BatchItem(item_name="Test item", quantity=10.0)]
        )
        
        updated_batch = self.parser.apply_smart_defaults(batch, MovementType.OUT)
        
        assert updated_batch.project == "not described"
        assert updated_batch.driver == "not described"
        assert updated_batch.to_location == "external"
        assert updated_batch.from_location is None  # Not applicable for /out
    
    def test_apply_smart_defaults_preserves_existing_values(self):
        """Test that smart defaults don't override existing values."""
        from src.schemas import BatchInfo, BatchItem
        
        batch = BatchInfo(
            batch_number=1,
            project="Existing Project",
            driver="Existing Driver",
            to_location="Existing Location",
            items=[BatchItem(item_name="Test item", quantity=10.0)]
        )
        
        updated_batch = self.parser.apply_smart_defaults(batch, MovementType.OUT)
        
        # Existing values should be preserved
        assert updated_batch.project == "Existing Project"
        assert updated_batch.driver == "Existing Driver"
        assert updated_batch.to_location == "Existing Location"
    
    def test_apply_smart_defaults_whitespace_values(self):
        """Test that smart defaults handle whitespace-only values."""
        from src.schemas import BatchInfo, BatchItem
        
        batch = BatchInfo(
            batch_number=1,
            project="   ",  # Whitespace only
            driver="\t\n",  # Whitespace only
            to_location="  ",  # Whitespace only
            items=[BatchItem(item_name="Test item", quantity=10.0)]
        )
        
        updated_batch = self.parser.apply_smart_defaults(batch, MovementType.OUT)
        
        # Whitespace-only values should be treated as empty and get defaults
        assert updated_batch.project == "not described"
        assert updated_batch.driver == "not described"
        assert updated_batch.to_location == "external"
    
    def test_mixed_batches_with_different_defaults(self):
        """Test multiple batches with different parameter combinations."""
        command = """-batch 1-
project: mzuzu
Solar floodlight panel FS-SFL800, 4

-batch 2-
driver: John Banda
Cable 2.5sqmm black 100m, 1

-batch 3-
Solar floodlight 800W, 4"""
        
        result = self.parser.parse_batch_command(command, MovementType.IN)
        
        assert result.is_valid
        assert len(result.batches) == 3
        
        # First batch: project specified, others default
        batch1 = result.batches[0]
        assert batch1.project == "mzuzu"
        assert batch1.driver == "not described"
        assert batch1.from_location == "not described"
        
        # Second batch: driver specified, others default
        batch2 = result.batches[1]
        assert batch2.project == "not described"
        assert batch2.driver == "John Banda"
        assert batch2.from_location == "not described"
        
        # Third batch: all defaults
        batch3 = result.batches[2]
        assert batch3.project == "not described"
        assert batch3.driver == "not described"
        assert batch3.from_location == "not described"
    
    def test_out_command_with_to_location_specified(self):
        """Test /out command with to location specified."""
        command = """project: mzuzu, driver: Dani maliko, to: mzuzu houses
Solar floodlight panel FS-SFL800, 4
Solar floodlight 800W, 4"""
        
        result = self.parser.parse_batch_command(command, MovementType.OUT)
        
        assert result.is_valid
        batch = result.batches[0]
        
        # All parameters specified, no defaults needed
        assert batch.project == "mzuzu"
        assert batch.driver == "Dani maliko"
        assert batch.to_location == "mzuzu houses"
    
    def test_in_command_with_from_location_specified(self):
        """Test /in command with from location specified."""
        command = """project: mzuzu, driver: Dani maliko, from: supplier warehouse
Solar floodlight panel FS-SFL800, 4
Solar floodlight 800W, 4"""
        
        result = self.parser.parse_batch_command(command, MovementType.IN)
        
        assert result.is_valid
        batch = result.batches[0]
        
        # All parameters specified, no defaults needed
        assert batch.project == "mzuzu"
        assert batch.driver == "Dani maliko"
        assert batch.from_location == "supplier warehouse"
    
    def test_defaults_with_units(self):
        """Test that defaults work correctly with items that have units."""
        command = """Cement, 50 bags
Steel bars, 100 pieces
Paint, 20 liters"""
        
        result = self.parser.parse_batch_command(command, MovementType.IN)
        
        assert result.is_valid
        batch = result.batches[0]
        
        # Should apply defaults
        assert batch.project == "not described"
        assert batch.driver == "not described"
        assert batch.from_location == "not described"
        
        # Items with units should be parsed correctly
        assert len(batch.items) == 3
        assert batch.items[0].item_name == "Cement"
        assert batch.items[0].quantity == 50.0
        assert batch.items[0].unit == "bags"
    
    def test_defaults_preserved_after_parsing(self):
        """Test that defaults are preserved after parsing."""
        command = """Solar floodlight panel FS-SFL800, 4
Solar floodlight 800W, 4"""
        
        result = self.parser.parse_batch_command(command, MovementType.OUT)
        
        assert result.is_valid
        batch = result.batches[0]
        
        # Apply smart defaults
        updated_batch = self.parser.apply_smart_defaults(batch, MovementType.OUT)
        
        # Defaults should be consistent
        assert updated_batch.project == "not described"
        assert updated_batch.driver == "not described"
        assert updated_batch.to_location == "external"
        
        # Items should remain unchanged
        assert len(updated_batch.items) == 2
        assert updated_batch.items[0].item_name == "Solar floodlight panel FS-SFL800"
        assert updated_batch.items[0].quantity == 4.0
    
    def test_case_insensitive_parameter_detection(self):
        """Test that parameter detection is case insensitive."""
        command = """PROJECT: Test Project, DRIVER: Test Driver, TO: Test Location
Item 1, 10
Item 2, 20"""
        
        result = self.parser.parse_batch_command(command, MovementType.OUT)
        
        assert result.is_valid
        batch = result.batches[0]
        
        # Should detect parameters regardless of case
        assert batch.project == "Test Project"
        assert batch.driver == "Test Driver"
        assert batch.to_location == "Test Location"
    
    def test_parameter_override_behavior(self):
        """Test that explicitly specified parameters override defaults."""
        from src.schemas import BatchInfo, BatchItem
        
        # Create batch with some defaults already applied
        batch = BatchInfo(
            batch_number=1,
            project="not described",  # Default value
            driver="not described",  # Default value
            to_location="external",  # Default value
            items=[BatchItem(item_name="Test item", quantity=10.0)]
        )
        
        # Apply smart defaults again
        updated_batch = self.parser.apply_smart_defaults(batch, MovementType.OUT)
        
        # Should not change existing values
        assert updated_batch.project == "not described"
        assert updated_batch.driver == "not described"
        assert updated_batch.to_location == "external"


if __name__ == "__main__":
    pytest.main([__file__])
