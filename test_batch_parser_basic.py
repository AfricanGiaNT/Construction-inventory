"""Basic tests for the batch movement parser."""

import pytest
from src.services.batch_movement_parser import BatchMovementParser
from src.schemas import MovementType, BatchFormat


class TestBatchMovementParserBasic:
    """Test basic functionality of the batch movement parser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = BatchMovementParser()
    
    def test_parse_single_batch_in_command(self):
        """Test parsing a single batch /in command."""
        command = """project: mzuzu, driver: Dani maliko
Solar floodlight panel FS-SFL800, 4
Solar floodlight 800W, 4
Cable 2.5sqmm black 100m, 1"""
        
        result = self.parser.parse_batch_command(command, MovementType.IN)
        
        assert result.is_valid
        assert result.format == BatchFormat.SINGLE
        assert len(result.batches) == 1
        assert result.total_items == 3
        
        batch = result.batches[0]
        assert batch.batch_number == 1
        assert batch.project == "mzuzu"
        assert batch.driver == "Dani maliko"
        assert batch.from_location == "not described"
        assert len(batch.items) == 3
        
        # Check items
        assert batch.items[0].item_name == "Solar floodlight panel FS-SFL800"
        assert batch.items[0].quantity == 4.0
        assert batch.items[0].unit is None
        
        assert batch.items[1].item_name == "Solar floodlight 800W"
        assert batch.items[1].quantity == 4.0
        
        assert batch.items[2].item_name == "Cable 2.5sqmm black 100m"
        assert batch.items[2].quantity == 1.0
    
    def test_parse_single_batch_out_command(self):
        """Test parsing a single batch /out command."""
        command = """project: mzuzu, driver: Dani maliko, to: mzuzu houses
Solar floodlight panel FS-SFL800, 4
Solar floodlight 800W, 4"""
        
        result = self.parser.parse_batch_command(command, MovementType.OUT)
        
        assert result.is_valid
        assert result.format == BatchFormat.SINGLE
        assert len(result.batches) == 1
        assert result.total_items == 2
        
        batch = result.batches[0]
        assert batch.batch_number == 1
        assert batch.project == "mzuzu"
        assert batch.driver == "Dani maliko"
        assert batch.to_location == "mzuzu houses"
        assert len(batch.items) == 2
    
    def test_parse_multiple_batches(self):
        """Test parsing multiple batches in one command."""
        command = """-batch 1-
project: mzuzu, driver: Dani maliko, to: mzuzu houses
Solar floodlight panel FS-SFL800, 4
Solar floodlight 800W, 4

-batch 2-
project: lilongwe, driver: John Banda, to: lilongwe site
Cable 2.5sqmm black 100m, 1
Cable 2.5sqmm green 100m, 1"""
        
        result = self.parser.parse_batch_command(command, MovementType.OUT)
        
        assert result.is_valid
        assert result.format == BatchFormat.MIXED
        assert len(result.batches) == 2
        assert result.total_items == 4
        
        # Check first batch
        batch1 = result.batches[0]
        assert batch1.batch_number == 1
        assert batch1.project == "mzuzu"
        assert batch1.driver == "Dani maliko"
        assert batch1.to_location == "mzuzu houses"
        assert len(batch1.items) == 2
        
        # Check second batch
        batch2 = result.batches[1]
        assert batch2.batch_number == 2
        assert batch2.project == "lilongwe"
        assert batch2.driver == "John Banda"
        assert batch2.to_location == "lilongwe site"
        assert len(batch2.items) == 2
    
    def test_parse_items_with_units(self):
        """Test parsing items with units specified."""
        command = """project: test, driver: test driver
Cement, 50 bags
Steel bars, 100 pieces
Paint, 20 liters"""
        
        result = self.parser.parse_batch_command(command, MovementType.IN)
        
        assert result.is_valid
        batch = result.batches[0]
        assert len(batch.items) == 3
        
        assert batch.items[0].item_name == "Cement"
        assert batch.items[0].quantity == 50.0
        assert batch.items[0].unit == "bags"
        
        assert batch.items[1].item_name == "Steel bars"
        assert batch.items[1].quantity == 100.0
        assert batch.items[1].unit == "pieces"
        
        assert batch.items[2].item_name == "Paint"
        assert batch.items[2].quantity == 20.0
        assert batch.items[2].unit == "liters"
    
    def test_parse_decimal_quantities(self):
        """Test parsing items with decimal quantities."""
        command = """project: test, driver: test driver
Cable, 2.5 meters
Paint, 1.5 liters
Steel, 0.5 tons"""
        
        result = self.parser.parse_batch_command(command, MovementType.IN)
        
        assert result.is_valid
        batch = result.batches[0]
        assert len(batch.items) == 3
        
        assert batch.items[0].quantity == 2.5
        assert batch.items[1].quantity == 1.5
        assert batch.items[2].quantity == 0.5
    
    def test_parse_mixed_parameter_order(self):
        """Test parsing with parameters in different orders."""
        command = """driver: John Doe, project: Test Project, to: Test Location
Item 1, 10
Item 2, 20 pieces"""
        
        result = self.parser.parse_batch_command(command, MovementType.OUT)
        
        assert result.is_valid
        batch = result.batches[0]
        assert batch.driver == "John Doe"
        assert batch.project == "Test Project"
        assert batch.to_location == "Test Location"
    
    def test_parse_case_insensitive_parameters(self):
        """Test parsing with case insensitive parameters."""
        command = """PROJECT: Test Project, DRIVER: Test Driver, TO: Test Location
Item 1, 10
Item 2, 20"""
        
        result = self.parser.parse_batch_command(command, MovementType.OUT)
        
        assert result.is_valid
        batch = result.batches[0]
        assert batch.project == "Test Project"
        assert batch.driver == "Test Driver"
        assert batch.to_location == "Test Location"
    
    def test_parse_whitespace_handling(self):
        """Test parsing with various whitespace scenarios."""
        command = """  project:  mzuzu  ,  driver:  Dani maliko  ,  to:  mzuzu houses  
  Solar floodlight panel FS-SFL800  ,  4  
  Solar floodlight 800W  ,  4  """
        
        result = self.parser.parse_batch_command(command, MovementType.OUT)
        
        assert result.is_valid
        batch = result.batches[0]
        assert batch.project == "mzuzu"
        assert batch.driver == "Dani maliko"
        assert batch.to_location == "mzuzu houses"
        assert len(batch.items) == 2
        assert batch.items[0].item_name == "Solar floodlight panel FS-SFL800"
        assert batch.items[0].quantity == 4.0
    
    def test_generate_batch_summary(self):
        """Test batch summary generation."""
        command = """-batch 1-
project: mzuzu, driver: Dani maliko, to: mzuzu houses
Solar floodlight panel FS-SFL800, 4
Solar floodlight 800W, 4

-batch 2-
project: lilongwe, driver: John Banda, to: lilongwe site
Cable 2.5sqmm black 100m, 1"""
        
        result = self.parser.parse_batch_command(command, MovementType.OUT)
        summary = self.parser.generate_batch_summary(result.batches)
        
        assert "Found 2 batch(es):" in summary
        assert "Batch 1: 2 items to mzuzu houses" in summary
        assert "Batch 2: 1 items to lilongwe site" in summary
        assert "Total items: 3" in summary
    
    def test_validate_batch(self):
        """Test batch validation."""
        command = """project: test, driver: test driver
Valid item, 10
Another valid item, 5"""
        
        result = self.parser.parse_batch_command(command, MovementType.IN)
        batch = result.batches[0]
        
        errors = self.parser.validate_batch(batch)
        assert len(errors) == 0
    
    def test_validate_empty_batch(self):
        """Test validation of empty batch."""
        command = """project: test, driver: test driver"""
        
        result = self.parser.parse_batch_command(command, MovementType.IN)
        batch = result.batches[0]
        
        errors = self.parser.validate_batch(batch)
        assert len(errors) == 1
        assert "No items found" in errors[0]
    
    def test_validate_invalid_quantities(self):
        """Test validation with invalid quantities."""
        # This test would require the parser to handle invalid quantities
        # For now, we'll test the validation logic directly
        from src.schemas import BatchInfo, BatchItem
        
        batch = BatchInfo(
            batch_number=1,
            project="test",
            driver="test driver",
            items=[
                BatchItem(item_name="Valid item", quantity=10.0),
                BatchItem(item_name="Invalid item", quantity=0.0),  # Invalid quantity
                BatchItem(item_name="Another invalid", quantity=-5.0)  # Invalid quantity
            ]
        )
        
        errors = self.parser.validate_batch(batch)
        assert len(errors) == 2
        assert any("Quantity must be greater than 0" in error for error in errors)
    
    def test_validate_missing_item_names(self):
        """Test validation with missing item names."""
        from src.schemas import BatchInfo, BatchItem
        
        batch = BatchInfo(
            batch_number=1,
            project="test",
            driver="test driver",
            items=[
                BatchItem(item_name="Valid item", quantity=10.0),
                BatchItem(item_name="", quantity=5.0),  # Empty name
                BatchItem(item_name="   ", quantity=3.0)  # Whitespace only
            ]
        )
        
        errors = self.parser.validate_batch(batch)
        assert len(errors) == 2
        assert all("Item name is required" in error for error in errors)


if __name__ == "__main__":
    pytest.main([__file__])
