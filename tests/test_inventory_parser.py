"""Tests for inventory parser functionality."""

import pytest
from src.services.inventory import InventoryParser, InventoryHeader, InventoryEntry, InventoryParseResult


class TestInventoryParser:
    """Test the inventory parser functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = InventoryParser()
    
    def test_parse_valid_header(self):
        """Test parsing a valid header line."""
        header_line = "date:25/08/25 logged by: Trevor,Kayesera"
        result = self.parser._parse_header(header_line)
        
        assert result is not None
        assert result.date == "25/08/25"
        assert result.logged_by == ["Trevor", "Kayesera"]
        assert result.raw_text == header_line
    
    def test_parse_header_with_extra_whitespace(self):
        """Test parsing header with extra whitespace."""
        header_line = "date: 25/08/25  logged  by:  Trevor , Kayesera "
        result = self.parser._parse_header(header_line)
        
        assert result is not None
        assert result.date == "25/08/25"
        assert result.logged_by == ["Trevor", "Kayesera"]
    
    def test_parse_header_case_insensitive(self):
        """Test parsing header with different case."""
        header_line = "DATE:25/08/25 LOGGED BY: Trevor,Kayesera"
        result = self.parser._parse_header(header_line)
        
        assert result is not None
        assert result.date == "25/08/25"
        assert result.logged_by == ["Trevor", "Kayesera"]
    
    def test_parse_header_single_name(self):
        """Test parsing header with single name."""
        header_line = "date:25/08/25 logged by: Trevor"
        result = self.parser._parse_header(header_line)
        
        assert result is not None
        assert result.date == "25/08/25"
        assert result.logged_by == ["Trevor"]
    
    def test_parse_header_invalid_format(self):
        """Test parsing invalid header format."""
        header_line = "invalid format"
        result = self.parser._parse_header(header_line)
        
        assert result is None
    
    def test_parse_header_missing_date(self):
        """Test parsing header missing date."""
        header_line = "logged by: Trevor,Kayesera"
        result = self.parser._parse_header(header_line)
        
        assert result is None
    
    def test_parse_header_missing_logged_by(self):
        """Test parsing header missing logged by."""
        header_line = "date:25/08/25"
        result = self.parser._parse_header(header_line)
        
        assert result is None
    
    def test_parse_header_invalid_date_format(self):
        """Test parsing header with invalid date format."""
        # Invalid day
        header_line = "date:32/08/25 logged by: Trevor"
        result = self.parser._parse_header(header_line)
        assert result is None
        
        # Invalid month
        header_line = "date:25/13/25 logged by: Trevor"
        result = self.parser._parse_header(header_line)
        assert result is None
        
        # Invalid year
        header_line = "date:25/08/100 logged by: Trevor"
        result = self.parser._parse_header(header_line)
        assert result is None
        
        # Wrong separator
        header_line = "date:25-08-25 logged by: Trevor"
        result = self.parser._parse_header(header_line)
        assert result is None
    
    def test_parse_header_february_edge_cases(self):
        """Test parsing header with February edge cases."""
        # February 29 in leap year
        header_line = "date:29/02/24 logged by: Trevor"
        result = self.parser._parse_header(header_line)
        assert result is not None
        
        # February 29 in non-leap year
        header_line = "date:29/02/25 logged by: Trevor"
        result = self.parser._parse_header(header_line)
        assert result is None
        
        # February 30 (invalid)
        header_line = "date:30/02/24 logged by: Trevor"
        result = self.parser._parse_header(header_line)
        assert result is None
    
    def test_parse_header_month_30_days(self):
        """Test parsing header with months that have 30 days."""
        # April 30 (valid)
        header_line = "date:30/04/25 logged by: Trevor"
        result = self.parser._parse_header(header_line)
        assert result is not None
        
        # April 31 (invalid)
        header_line = "date:31/04/25 logged by: Trevor"
        result = self.parser._parse_header(header_line)
        assert result is None
        
        # June 30 (valid)
        header_line = "date:30/06/25 logged by: Trevor"
        result = self.parser._parse_header(header_line)
        assert result is not None
        
        # June 31 (invalid)
        header_line = "date:31/06/25 logged by: Trevor"
        result = self.parser._parse_header(header_line)
        assert result is None
    
    def test_parse_valid_entry_line(self):
        """Test parsing a valid entry line."""
        line = "Cement 32.5, 50"
        result = self.parser._parse_entry_line(line, 2)
        
        assert result is not None
        assert result.item_name == "Cement 32.5"
        assert result.quantity == 50.0
        assert result.line_number == 2
        assert result.raw_text == line
    
    def test_parse_entry_line_with_whitespace(self):
        """Test parsing entry line with extra whitespace."""
        line = "  Cement 32.5 ,  50  "
        result = self.parser._parse_entry_line(line, 2)
        
        assert result is not None
        assert result.item_name == "Cement 32.5"
        assert result.quantity == 50.0
    
    def test_parse_entry_line_decimal_quantity(self):
        """Test parsing entry line with decimal quantity."""
        line = "Steel bars, 120.5"
        result = self.parser._parse_entry_line(line, 2)
        
        assert result is not None
        assert result.item_name == "Steel bars"
        assert result.quantity == 120.5
    
    def test_parse_entry_line_zero_quantity(self):
        """Test parsing entry line with zero quantity."""
        line = "Empty container, 0"
        result = self.parser._parse_entry_line(line, 2)
        
        assert result is not None
        assert result.item_name == "Empty container"
        assert result.quantity == 0.0
    
    def test_parse_entry_line_invalid_format(self):
        """Test parsing invalid entry line format."""
        # Missing comma
        line = "Cement 32.5 50"
        result = self.parser._parse_entry_line(line, 2)
        assert result is None
        
        # Empty item name
        line = ", 50"
        result = self.parser._parse_entry_line(line, 2)
        assert result is None
        
        # Empty quantity
        line = "Cement 32.5,"
        result = self.parser._parse_entry_line(line, 2)
        assert result is None
    
    def test_parse_entry_line_invalid_quantity(self):
        """Test parsing entry line with invalid quantity."""
        # Non-numeric
        line = "Cement 32.5, abc"
        result = self.parser._parse_entry_line(line, 2)
        assert result is None
        
        # Negative number
        line = "Cement 32.5, -5"
        result = self.parser._parse_entry_line(line, 2)
        assert result is None
        
        # NaN (this would be caught by float conversion)
        line = "Cement 32.5, NaN"
        result = self.parser._parse_entry_line(line, 2)
        assert result is None
    
    def test_parse_entries_single_entry(self):
        """Test parsing single entry."""
        entry_lines = ["Cement 32.5, 50"]
        result = self.parser._parse_entries(entry_lines)
        
        assert result["is_valid"] is True
        assert len(result["entries"]) == 1
        assert len(result["errors"]) == 0
        
        entry = result["entries"][0]
        assert entry.item_name == "Cement 32.5"
        assert entry.quantity == 50.0
        assert entry.line_number == 2
    
    def test_parse_entries_multiple_entries(self):
        """Test parsing multiple entries."""
        entry_lines = [
            "Cement 32.5, 50",
            "Steel bars, 120.0",
            "Safety helmets, 25"
        ]
        result = self.parser._parse_entries(entry_lines)
        
        assert result["is_valid"] is True
        assert len(result["entries"]) == 3
        assert len(result["errors"]) == 0
        
        # Check all entries are parsed correctly
        items = [entry.item_name for entry in result["entries"]]
        quantities = [entry.quantity for entry in result["entries"]]
        
        assert "Cement 32.5" in items
        assert "Steel bars" in items
        assert "Safety helmets" in items
        assert 50.0 in quantities
        assert 120.0 in quantities
        assert 25.0 in quantities
    
    def test_parse_entries_with_empty_lines(self):
        """Test parsing entries with empty lines."""
        entry_lines = [
            "Cement 32.5, 50",
            "",
            "Steel bars, 120.0",
            "  ",
            "Safety helmets, 25"
        ]
        result = self.parser._parse_entries(entry_lines)
        
        assert result["is_valid"] is True
        assert len(result["entries"]) == 3
        assert len(result["errors"]) == 0
    
    def test_parse_entries_with_invalid_lines(self):
        """Test parsing entries with invalid lines."""
        entry_lines = [
            "Cement 32.5, 50",
            "Invalid line",
            "Steel bars, 120.0"
        ]
        result = self.parser._parse_entries(entry_lines)
        
        assert result["is_valid"] is False
        assert len(result["entries"]) == 2
        assert len(result["errors"]) == 1
        assert "Line 3: Invalid format" in result["errors"][0]
    
    def test_parse_entries_duplicate_items(self):
        """Test parsing entries with duplicate items (case-insensitive)."""
        entry_lines = [
            "Cement 32.5, 50",
            "cement 32.5, 75",  # Different case, should replace
            "Steel bars, 120.0",
            "STEEL BARS, 150.0"  # Different case, should replace
        ]
        result = self.parser._parse_entries(entry_lines)
        
        assert result["is_valid"] is True
        assert len(result["entries"]) == 2  # Only 2 unique items
        assert len(result["errors"]) == 0
        
        # Check that last occurrence is kept
        cement_entry = next(e for e in result["entries"] if e.item_name.lower() == "cement 32.5")
        steel_entry = next(e for e in result["entries"] if e.item_name.lower() == "steel bars")
        
        assert cement_entry.quantity == 75.0
        assert steel_entry.quantity == 150.0
    
    def test_parse_entries_max_limit(self):
        """Test parsing entries with maximum limit enforcement."""
        # Create 51 entries (exceeding the 50 limit)
        entry_lines = [f"Item {i}, {i}" for i in range(51)]
        result = self.parser._parse_entries(entry_lines)
        
        assert result["is_valid"] is False
        assert len(result["entries"]) == 50
        assert len(result["errors"]) == 1
        assert "Maximum of 50 entries exceeded" in result["errors"][0]
    
    def test_parse_entries_exactly_at_limit(self):
        """Test parsing entries exactly at the limit."""
        # Create exactly 50 entries
        entry_lines = [f"Item {i}, {i}" for i in range(50)]
        result = self.parser._parse_entries(entry_lines)
        
        assert result["is_valid"] is True
        assert len(result["entries"]) == 50
        assert len(result["errors"]) == 0
    
    def test_parse_inventory_command_valid(self):
        """Test parsing a complete valid inventory command."""
        command_text = """date:25/08/25 logged by: Trevor,Kayesera
Cement 32.5, 50
Steel bars, 120.0
Safety helmets, 25"""
        
        result = self.parser.parse_inventory_command(command_text)
        
        assert result.is_valid is True
        assert result.total_lines == 4
        assert result.valid_entries == 3
        assert len(result.errors) == 0
        
        assert result.header.date == "25/08/25"
        assert result.header.logged_by == ["Trevor", "Kayesera"]
        
        assert len(result.entries) == 3
        assert result.entries[0].item_name == "Cement 32.5"
        assert result.entries[0].quantity == 50.0
        assert result.entries[1].item_name == "Steel bars"
        assert result.entries[1].quantity == 120.0
        assert result.entries[2].item_name == "Safety helmets"
        assert result.entries[2].quantity == 25.0
    
    def test_parse_inventory_command_invalid_header(self):
        """Test parsing inventory command with invalid header."""
        command_text = """invalid header
Cement 32.5, 50"""
        
        result = self.parser.parse_inventory_command(command_text)
        
        assert result.is_valid is False
        assert result.total_lines == 2
        assert result.valid_entries == 0
        assert len(result.errors) == 1
        assert "Invalid header format" in result.errors[0]
    
    def test_parse_inventory_command_invalid_entries(self):
        """Test parsing inventory command with invalid entries."""
        command_text = """date:25/08/25 logged by: Trevor
Cement 32.5, 50
Invalid line
Steel bars, 120.0"""
        
        result = self.parser.parse_inventory_command(command_text)
        
        assert result.is_valid is False
        assert result.total_lines == 4
        assert result.valid_entries == 2
        assert len(result.errors) == 1
        assert "Line 3: Invalid format" in result.errors[0]
    
    def test_parse_inventory_command_insufficient_lines(self):
        """Test parsing inventory command with insufficient lines."""
        command_text = "date:25/08/25 logged by: Trevor"
        
        result = self.parser.parse_inventory_command(command_text)
        
        assert result.is_valid is False
        assert result.total_lines == 0
        assert result.valid_entries == 0
        assert len(result.errors) == 1
        assert "Command must have at least a header and one entry line" in result.errors[0]
    
    def test_parse_inventory_command_empty(self):
        """Test parsing empty inventory command."""
        command_text = ""
        
        result = self.parser.parse_inventory_command(command_text)
        
        assert result.is_valid is False
        assert result.total_lines == 0
        assert result.valid_entries == 0
        assert len(result.errors) == 1
        assert "Command must have at least a header and one entry line" in result.errors[0]
    
    def test_parse_inventory_command_whitespace_only(self):
        """Test parsing inventory command with only whitespace."""
        command_text = "   \n  \n  "
        
        result = self.parser.parse_inventory_command(command_text)
        
        assert result.is_valid is False
        assert result.total_lines == 3
        assert result.valid_entries == 0
        assert len(result.errors) == 1
        assert "Invalid header format" in result.errors[0]
    
    def test_parse_inventory_command_mixed_line_endings(self):
        """Test parsing inventory command with mixed line endings."""
        command_text = "date:25/08/25 logged by: Trevor\r\nCement 32.5, 50\rSteel bars, 120.0\nSafety helmets, 25"
        
        result = self.parser.parse_inventory_command(command_text)
        
        assert result.is_valid is True
        assert result.total_lines == 4
        assert result.valid_entries == 3
        assert len(result.errors) == 0

    # Phase 4: UX & Robustness Enhancement Tests
    
    def test_parse_header_logged_by_variants(self):
        """Test parsing header with different logged by variants."""
        # Test logged by: (space)
        header_line = "date:25/08/25 logged by: Trevor,Kayesera"
        result = self.parser._parse_header(header_line)
        assert result is not None
        assert result.logged_by == ["Trevor", "Kayesera"]
        
        # Test logged_by: (underscore)
        header_line = "date:25/08/25 logged_by: Trevor,Kayesera"
        result = self.parser._parse_header(header_line)
        assert result is not None
        assert result.logged_by == ["Trevor", "Kayesera"]
        
        # Test mixed case
        header_line = "date:25/08/25 LOGGED_BY: Trevor,Kayesera"
        result = self.parser._parse_header(header_line)
        assert result is not None
        assert result.logged_by == ["Trevor", "Kayesera"]
        
        # Test extra whitespace
        header_line = "date:25/08/25  logged_by:  Trevor , Kayesera "
        result = self.parser._parse_header(header_line)
        assert result is not None
        assert result.logged_by == ["Trevor", "Kayesera"]

    def test_parse_entries_with_comment_lines(self):
        """Test parsing entries with comment lines."""
        entry_lines = [
            "Cement 32.5, 50",
            "# This is a comment about cement",
            "Steel bars, 120.0",
            "# Another comment",
            "Safety helmets, 25"
        ]
        
        result = self.parser._parse_entries(entry_lines)
        
        assert result["is_valid"] is True
        assert len(result["entries"]) == 3
        assert result["stats"]["comment_lines"] == 2
        assert result["stats"]["blank_lines"] == 0
        assert result["stats"]["skipped_lines"] == 0
        
        # Verify entries are parsed correctly
        assert result["entries"][0].item_name == "Cement 32.5"
        assert result["entries"][1].item_name == "Steel bars"
        assert result["entries"][2].item_name == "Safety helmets"

    def test_parse_entries_with_blank_lines(self):
        """Test parsing entries with blank lines."""
        entry_lines = [
            "Cement 32.5, 50",
            "",
            "Steel bars, 120.0",
            "   ",
            "Safety helmets, 25"
        ]
        
        result = self.parser._parse_entries(entry_lines)
        
        assert result["is_valid"] is True
        assert len(result["entries"]) == 3
        assert result["stats"]["blank_lines"] == 2
        assert result["stats"]["comment_lines"] == 0
        assert result["stats"]["skipped_lines"] == 0

    def test_parse_entries_with_mixed_ignored_lines(self):
        """Test parsing entries with mixed comment and blank lines."""
        entry_lines = [
            "Cement 32.5, 50",
            "# Comment about cement",
            "",
            "Steel bars, 120.0",
            "   ",
            "# Comment about steel",
            "Safety helmets, 25"
        ]
        
        result = self.parser._parse_entries(entry_lines)
        
        assert result["is_valid"] is True
        assert len(result["entries"]) == 3
        assert result["stats"]["blank_lines"] == 2
        assert result["stats"]["comment_lines"] == 2
        assert result["stats"]["skipped_lines"] == 0

    def test_parse_entries_with_invalid_lines(self):
        """Test parsing entries with invalid lines that get skipped."""
        entry_lines = [
            "Cement 32.5, 50",
            "Invalid line without comma",
            "Steel bars, 120.0",
            "Another invalid line",
            "Safety helmets, 25"
        ]
        
        result = self.parser._parse_entries(entry_lines)
        
        assert result["is_valid"] is False
        assert len(result["entries"]) == 3
        assert result["stats"]["blank_lines"] == 0
        assert result["stats"]["comment_lines"] == 0
        assert result["stats"]["skipped_lines"] == 2
        assert len(result["errors"]) == 2

    def test_parse_entries_comment_lines_not_counted_toward_limit(self):
        """Test that comment lines don't count toward the 50-entry limit."""
        # Create 52 lines: 50 valid entries + 2 comment lines
        entry_lines = []
        for i in range(50):
            entry_lines.append(f"Item {i}, {i + 1}")
        entry_lines.append("# Comment line 1")
        entry_lines.append("# Comment line 2")
        
        result = self.parser._parse_entries(entry_lines)
        
        assert result["is_valid"] is True
        assert len(result["entries"]) == 50
        assert result["stats"]["comment_lines"] == 2
        assert result["stats"]["blank_lines"] == 0
        assert result["stats"]["skipped_lines"] == 0

    def test_parse_entries_blank_lines_not_counted_toward_limit(self):
        """Test that blank lines don't count toward the 50-entry limit."""
        # Create 52 lines: 50 valid entries + 2 blank lines
        entry_lines = []
        for i in range(50):
            entry_lines.append(f"Item {i}, {i + 1}")
        entry_lines.append("")
        entry_lines.append("   ")
        
        result = self.parser._parse_entries(entry_lines)
        
        assert result["is_valid"] is True
        assert len(result["entries"]) == 50
        assert result["stats"]["blank_lines"] == 2
        assert result["stats"]["comment_lines"] == 0
        assert result["stats"]["skipped_lines"] == 0

    def test_parse_inventory_command_with_comments_and_blanks(self):
        """Test parsing complete inventory command with comments and blanks."""
        command_text = """date:25/08/25 logged by: Trevor,Kayesera
# Inventory count for January 2025
Cement 32.5, 50

Steel bars, 120.0
# Safety equipment
Safety helmets, 25
# End of inventory"""
        
        result = self.parser.parse_inventory_command(command_text)
        
        assert result.is_valid is True
        assert result.total_lines == 8
        assert result.valid_entries == 3
        assert result.blank_lines == 1
        assert result.comment_lines == 3
        assert result.skipped_lines == 0
        assert len(result.errors) == 0

    def test_parse_inventory_command_with_logged_by_variants(self):
        """Test parsing inventory command with different logged by variants."""
        # Test logged by: (space)
        command_text = """date:25/08/25 logged by: Trevor,Kayesera
Cement 32.5, 50
Steel bars, 120.0"""
        
        result = self.parser.parse_inventory_command(command_text)
        assert result.is_valid is True
        assert result.valid_entries == 2
        
        # Test logged_by: (underscore)
        command_text = """date:25/08/25 logged_by: Trevor,Kayesera
Cement 32.5, 50
Steel bars, 120.0"""
        
        result = self.parser.parse_inventory_command(command_text)
        assert result.is_valid is True
        assert result.valid_entries == 2

    def test_generate_corrected_template(self):
        """Test generating corrected templates for failed parsing."""
        # Test with missing /inventory prefix
        command_text = """date:25/08/25 logged by: Trevor
Cement 32.5, 50"""
        
        template = self.parser._generate_corrected_template(command_text, ["Invalid header"])
        assert template is not None
        assert template.startswith("/inventory date:25/08/25 logged by: Trevor")
        
        # Test with completely invalid header
        command_text = """invalid header
Cement 32.5, 50"""
        
        template = self.parser._generate_corrected_template(command_text, ["Invalid header"])
        assert template is not None
        assert "/inventory date:25/01/25 logged by: YourName" in template
        
        # Test with empty command
        template = self.parser._generate_corrected_template("", ["Empty command"])
        assert template is None

    def test_parse_inventory_command_edge_cases(self):
        """Test parsing inventory command with various edge cases."""
        # Test with only comment lines (should fail - no valid entries)
        command_text = """date:25/08/25 logged by: Trevor
# Only comments
# No valid entries"""
        
        result = self.parser.parse_inventory_command(command_text)
        assert result.is_valid is False
        assert result.valid_entries == 0
        assert result.comment_lines == 2
        assert result.blank_lines == 0
        assert "Command must have at least a header and one entry line" in result.errors[0]
        
        # Test with only blank lines (should fail - no valid entries)
        command_text = """date:25/08/25 logged by: Trevor


"""
        
        result = self.parser.parse_inventory_command(command_text)
        assert result.is_valid is False
        assert result.valid_entries == 0
        assert result.blank_lines == 3
        assert result.comment_lines == 0
        assert "Command must have at least a header and one entry line" in result.errors[0]
        
        # Test with mixed ignored lines and valid entries
        command_text = """date:25/08/25 logged by: Trevor
# Start of inventory
Cement 32.5, 50

# Middle section
Steel bars, 120.0

# End of inventory
Safety helmets, 25"""
        
        result = self.parser.parse_inventory_command(command_text)
        assert result.is_valid is True
        assert result.valid_entries == 3
        assert result.comment_lines == 3
        assert result.blank_lines == 2
