"""Edge case tests for the batch movement parser."""

import pytest
from src.services.batch_movement_parser import BatchMovementParser
from src.schemas import MovementType, BatchFormat


class TestBatchMovementParserEdgeCases:
    """Test edge cases and error handling of the batch movement parser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = BatchMovementParser()
    
    def test_parse_empty_command(self):
        """Test parsing an empty command."""
        result = self.parser.parse_batch_command("", MovementType.IN)
        
        assert not result.is_valid
        assert len(result.batches) == 0
        assert "Failed to parse single batch" in result.errors[0]
    
    def test_parse_whitespace_only_command(self):
        """Test parsing a command with only whitespace."""
        result = self.parser.parse_batch_command("   \n  \t  \n  ", MovementType.IN)
        
        assert not result.is_valid
        assert len(result.batches) == 0
        assert "Failed to parse single batch" in result.errors[0]
    
    def test_parse_malformed_batch_separators(self):
        """Test parsing with malformed batch separators."""
        command = """-batch1-
project: test, driver: test driver
Item 1, 10

-batch 2
project: test2, driver: test driver2
Item 2, 20

-batch
project: test3, driver: test driver3
Item 3, 30"""
        
        result = self.parser.parse_batch_command(command, MovementType.IN)
        
        # Should handle malformed separators gracefully
        assert result.is_valid or len(result.errors) > 0
    
    def test_parse_extra_whitespace_and_newlines(self):
        """Test parsing with excessive whitespace and newlines."""
        command = """   \n\n   -batch 1-   \n\n   \n   
   project:   mzuzu   ,   driver:   Dani maliko   \n\n   
   Solar floodlight panel FS-SFL800   ,   4   \n\n   
   Solar floodlight 800W   ,   4   \n\n   
   
   -batch 2-   \n\n   
   project:   lilongwe   ,   driver:   John Banda   \n\n   
   Cable 2.5sqmm black 100m   ,   1   \n\n   """
        
        result = self.parser.parse_batch_command(command, MovementType.OUT)
        
        assert result.is_valid
        assert len(result.batches) == 2
        assert result.total_items == 3
        
        # Check that whitespace is properly trimmed
        batch1 = result.batches[0]
        assert batch1.project == "mzuzu"
        assert batch1.driver == "Dani maliko"
        assert len(batch1.items) == 2
        assert batch1.items[0].item_name == "Solar floodlight panel FS-SFL800"
        assert batch1.items[0].quantity == 4.0
    
    def test_parse_special_characters_in_item_names(self):
        """Test parsing items with special characters in names."""
        command = """project: test, driver: test driver
Item with spaces & symbols, 10
Item-with-dashes, 5
Item_with_underscores, 3
Item.with.dots, 2
Item/with/slashes, 1
Item(with)parentheses, 4
Item[with]brackets, 6
Item{with}braces, 7
Item@with#symbols, 8"""
        
        result = self.parser.parse_batch_command(command, MovementType.IN)
        
        assert result.is_valid
        batch = result.batches[0]
        assert len(batch.items) == 9
        
        expected_names = [
            "Item with spaces & symbols",
            "Item-with-dashes",
            "Item_with_underscores",
            "Item.with.dots",
            "Item/with/slashes",
            "Item(with)parentheses",
            "Item[with]brackets",
            "Item{with}braces",
            "Item@with#symbols"
        ]
        
        for i, expected_name in enumerate(expected_names):
            assert batch.items[i].item_name == expected_name
    
    def test_parse_very_long_item_names(self):
        """Test parsing items with very long names."""
        long_name = "A" * 1000  # 1000 character item name
        command = f"""project: test, driver: test driver
{long_name}, 10
Short item, 5"""
        
        result = self.parser.parse_batch_command(command, MovementType.IN)
        
        assert result.is_valid
        batch = result.batches[0]
        assert len(batch.items) == 2
        assert batch.items[0].item_name == long_name
        assert batch.items[0].quantity == 10.0
        assert batch.items[1].item_name == "Short item"
    
    def test_parse_very_large_quantities(self):
        """Test parsing items with very large quantities."""
        command = """project: test, driver: test driver
Item 1, 999999999
Item 2, 0.000001
Item 3, 123456789.987654321"""
        
        result = self.parser.parse_batch_command(command, MovementType.IN)
        
        assert result.is_valid
        batch = result.batches[0]
        assert len(batch.items) == 3
        assert batch.items[0].quantity == 999999999.0
        assert batch.items[1].quantity == 0.000001
        assert batch.items[2].quantity == 123456789.987654321
    
    def test_parse_mixed_valid_invalid_batches(self):
        """Test parsing with some valid and some invalid batches."""
        command = """-batch 1-
project: valid, driver: valid driver
Valid item, 10

-batch 2-
project: invalid, driver: invalid driver
Invalid item, 0

-batch 3-
project: another valid, driver: another valid driver
Another valid item, 5"""
        
        result = self.parser.parse_batch_command(command, MovementType.IN)
        
        # Should parse successfully but validation will catch issues
        assert len(result.batches) == 3
        assert result.total_items == 3
        
        # Check that all batches are parsed
        assert result.batches[0].batch_number == 1
        assert result.batches[1].batch_number == 2
        assert result.batches[2].batch_number == 3
    
    def test_parse_duplicate_batch_numbers(self):
        """Test parsing with duplicate batch numbers."""
        command = """-batch 1-
project: first, driver: first driver
Item 1, 10

-batch 1-
project: second, driver: second driver
Item 2, 20"""
        
        result = self.parser.parse_batch_command(command, MovementType.IN)
        
        # Should handle duplicate numbers (they're just labels)
        assert result.is_valid
        assert len(result.batches) == 2
        assert result.batches[0].batch_number == 1
        assert result.batches[1].batch_number == 1  # Duplicate is allowed
    
    def test_parse_non_numeric_batch_numbers(self):
        """Test parsing with non-numeric batch numbers."""
        command = """-batch one-
project: test, driver: test driver
Item 1, 10

-batch two-
project: test2, driver: test driver2
Item 2, 20"""
        
        result = self.parser.parse_batch_command(command, MovementType.IN)
        
        # Should handle non-numeric batch numbers gracefully
        # When batch separators are malformed, it treats as single batch
        assert result.is_valid
        assert len(result.batches) == 1
        # Should parse all items in the single batch
        assert result.total_items == 2
    
    def test_parse_malformed_item_lines(self):
        """Test parsing with malformed item lines."""
        command = """project: test, driver: test driver
Valid item, 10
Invalid item without comma 5
Another valid item, 15
Invalid item with comma but no number, abc
Valid item with unit, 20 pieces
Invalid item with comma at end, 
Another valid item, 25"""
        
        result = self.parser.parse_batch_command(command, MovementType.IN)
        
        assert result.is_valid
        batch = result.batches[0]
        
        # Should parse only valid items
        assert len(batch.items) == 4  # Only valid items should be parsed
        assert batch.items[0].item_name == "Valid item"
        assert batch.items[1].item_name == "Another valid item"
        assert batch.items[2].item_name == "Valid item with unit"
        assert batch.items[3].item_name == "Another valid item"
    
    def test_parse_parameters_without_values(self):
        """Test parsing parameters without values."""
        command = """project:, driver: test driver, to: test location
Item 1, 10
Item 2, 20"""
        
        result = self.parser.parse_batch_command(command, MovementType.OUT)
        
        assert result.is_valid
        batch = result.batches[0]
        assert batch.project == "not described"  # Should use default
        assert batch.driver == "test driver"
        assert batch.to_location == "test location"
    
    def test_parse_parameters_with_commas_in_values(self):
        """Test parsing parameters with commas in values."""
        command = """project: Test Project, Inc., driver: John Doe, Jr., to: Test Location, LLC
Item 1, 10
Item 2, 20"""
        
        result = self.parser.parse_batch_command(command, MovementType.OUT)
        
        assert result.is_valid
        batch = result.batches[0]
        assert batch.project == "Test Project, Inc."
        assert batch.driver == "John Doe, Jr."
        assert batch.to_location == "Test Location, LLC"
    
    def test_parse_very_long_command(self):
        """Test parsing a very long command with many batches."""
        command_parts = []
        for i in range(100):  # 100 batches
            command_parts.append(f"""-batch {i+1}-
project: project{i+1}, driver: driver{i+1}, to: location{i+1}
Item {i+1}a, 10
Item {i+1}b, 20
Item {i+1}c, 30""")
        
        command = "\n\n".join(command_parts)
        result = self.parser.parse_batch_command(command, MovementType.OUT)
        
        assert result.is_valid
        assert len(result.batches) == 100
        assert result.total_items == 300  # 3 items per batch
    
    def test_parse_unicode_characters(self):
        """Test parsing with unicode characters."""
        command = """project: 测试项目, driver: 测试司机, to: 测试地点
太阳能灯板 FS-SFL800, 4
电缆 2.5平方毫米 黑色 100米, 1
油漆 5升, 2"""
        
        result = self.parser.parse_batch_command(command, MovementType.OUT)
        
        assert result.is_valid
        batch = result.batches[0]
        assert batch.project == "测试项目"
        assert batch.driver == "测试司机"
        assert batch.to_location == "测试地点"
        assert len(batch.items) == 3
        assert batch.items[0].item_name == "太阳能灯板 FS-SFL800"
        assert batch.items[1].item_name == "电缆 2.5平方毫米 黑色 100米"
        assert batch.items[2].item_name == "油漆 5升"
    
    def test_parse_empty_batches(self):
        """Test parsing with empty batches."""
        command = """-batch 1-
project: test, driver: test driver
Item 1, 10

-batch 2-

-batch 3-
project: test3, driver: test driver3
Item 3, 30"""
        
        result = self.parser.parse_batch_command(command, MovementType.IN)
        
        # Should handle empty batch gracefully
        assert len(result.batches) == 3
        assert result.batches[0].batch_number == 1
        assert result.batches[1].batch_number == 2
        assert result.batches[2].batch_number == 3
        
        # Empty batch should have no items
        assert len(result.batches[1].items) == 0
    
    def test_parse_parameters_with_newlines(self):
        """Test parsing parameters that span multiple lines."""
        command = """project: Test Project
driver: John Doe
to: Test Location
Item 1, 10
Item 2, 20"""
        
        result = self.parser.parse_batch_command(command, MovementType.OUT)
        
        assert result.is_valid
        batch = result.batches[0]
        assert batch.project == "Test Project"
        assert batch.driver == "John Doe"
        assert batch.to_location == "Test Location"
        assert len(batch.items) == 2


if __name__ == "__main__":
    pytest.main([__file__])
