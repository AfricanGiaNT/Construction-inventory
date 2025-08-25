"""Tests for the command suggestions service (Phase 3)."""

import pytest
from src.services.command_suggestions import CommandSuggestionsService


class TestCommandSuggestionsService:
    """Test the command suggestions service functionality."""
    
    @pytest.fixture
    def service(self):
        """Create a command suggestions service instance."""
        return CommandSuggestionsService()
    
    def test_initialization(self, service):
        """Test that the service initializes with all commands."""
        assert len(service.available_commands) > 0
        assert "stock" in service.available_commands
        assert "help" in service.available_commands
        assert "in" in service.available_commands
    
    def test_get_command_info(self, service):
        """Test getting information about a specific command."""
        # Test existing command
        cmd_info = service.get_command_info("stock")
        assert cmd_info is not None
        assert cmd_info["category"] == "Queries"
        assert "fuzzy matching" in cmd_info["description"].lower()
        
        # Test non-existent command
        cmd_info = service.get_command_info("nonexistent")
        assert cmd_info is None
    
    def test_get_commands_by_category(self, service):
        """Test getting commands by category."""
        # Test stock operations category
        stock_commands = service.get_commands_by_category("Stock Operations")
        assert len(stock_commands) > 0
        command_names = [cmd[0] for cmd in stock_commands]
        assert "in" in command_names
        assert "out" in command_names
        assert "adjust" in command_names
        
        # Test queries category
        query_commands = service.get_commands_by_category("Queries")
        assert len(query_commands) > 0
        command_names = [cmd[0] for cmd in query_commands]
        assert "stock" in command_names
        assert "find" in command_names
        assert "onhand" in command_names
    
    def test_get_all_categories(self, service):
        """Test getting all available categories."""
        categories = service.get_all_categories()
        assert len(categories) > 0
        assert "Stock Operations" in categories
        assert "Queries" in categories
        assert "Management" in categories
        assert "Batch Operations" in categories
        assert "Help" in categories
    
    def test_calculate_similarity(self, service):
        """Test similarity calculation between input and command names."""
        # Test exact match
        similarity = service._calculate_similarity("stock", "stock")
        assert similarity >= 1.0
        
        # Test prefix match
        similarity = service._calculate_similarity("st", "stock")
        assert similarity >= 0.8  # Should be high due to prefix bonus
        
        # Test substring match
        similarity = service._calculate_similarity("tock", "stock")
        assert similarity >= 0.6  # Should be moderate
        
        # Test low similarity
        similarity = service._calculate_similarity("xyz", "stock")
        assert similarity < 0.5  # Should be low
    
    def test_get_command_suggestions(self, service):
        """Test getting command suggestions for user input."""
        # Test exact command
        suggestions = service.get_command_suggestions("stock")
        assert len(suggestions) > 0
        assert suggestions[0][0] == "stock"  # First suggestion should be exact match
        
        # Test typo correction
        suggestions = service.get_command_suggestions("stok")
        assert len(suggestions) > 0
        assert "stock" in [s[0] for s in suggestions]
        
        # Test partial input
        suggestions = service.get_command_suggestions("st")
        assert len(suggestions) > 0
        assert "stock" in [s[0] for s in suggestions]
        
        # Test no matches
        suggestions = service.get_command_suggestions("xyz123")
        assert len(suggestions) == 0
    
    def test_format_suggestions_message(self, service):
        """Test formatting suggestions into user-friendly messages."""
        # Test with suggestions
        suggestions = service.get_command_suggestions("stok")
        message = service.format_suggestions_message("stok", suggestions)
        
        assert "Did you mean one of these commands?" in message
        assert "stock" in message.lower()
        assert "Usage:" in message
        assert "Example:" in message
        assert "Tips:" in message
        
        # Test without suggestions
        message = service.format_suggestions_message("xyz123", [])
        assert "No similar commands found" in message
        assert "Unknown Command: /xyz123" in message
    
    def test_get_quick_help(self, service):
        """Test getting quick help for a specific command."""
        # Test existing command
        help_text = service.get_quick_help("stock")
        assert help_text is not None
        assert "stock - Quick Help" in help_text
        assert "Description:" in help_text
        assert "Usage:" in help_text
        assert "Examples:" in help_text
        assert "Category:" in help_text
        
        # Test non-existent command
        help_text = service.get_quick_help("nonexistent")
        assert help_text is None
    
    def test_command_suggestions_with_typos(self, service):
        """Test command suggestions with common typos."""
        # Test common typos
        test_cases = [
            ("stok", "stock"),
            ("hel", "help"),
            ("batchelp", "batchhelp"),
            ("statu", "status"),
            ("valida", "validate"),
            ("expor", "export"),
            ("aud", "audit"),
            ("approv", "approve")
        ]
        
        for typo, expected_command in test_cases:
            suggestions = service.get_command_suggestions(typo)
            assert len(suggestions) > 0, f"No suggestions for typo: {typo}"
            
            # Check if the expected command is in the suggestions
            suggested_commands = [s[0] for s in suggestions]
            assert expected_command in suggested_commands, f"Expected {expected_command} for typo {typo}, got {suggested_commands}"
    
    def test_similarity_scoring(self, service):
        """Test that similarity scoring works correctly."""
        # Test that exact matches get highest scores
        exact_similarity = service._calculate_similarity("stock", "stock")
        partial_similarity = service._calculate_similarity("st", "stock")
        low_similarity = service._calculate_similarity("xyz", "stock")
        
        assert exact_similarity > partial_similarity
        assert partial_similarity > low_similarity
        
        # Test that prefix matches get bonus points
        prefix_similarity = service._calculate_similarity("st", "stock")
        substring_similarity = service._calculate_similarity("ock", "stock")
        
        assert prefix_similarity > substring_similarity
    
    def test_max_suggestions_limit(self, service):
        """Test that suggestions respect the maximum limit."""
        # Test with default limit (3)
        suggestions = service.get_command_suggestions("st")
        assert len(suggestions) <= 3
        
        # Test with custom limit
        suggestions = service.get_command_suggestions("st", max_suggestions=5)
        assert len(suggestions) <= 5
        
        # Test with very low limit
        suggestions = service.get_command_suggestions("st", max_suggestions=1)
        assert len(suggestions) <= 1
    
    def test_empty_input_handling(self, service):
        """Test handling of empty or invalid input."""
        # Test empty string
        suggestions = service.get_command_suggestions("")
        assert len(suggestions) == 0
        
        # Test None input
        suggestions = service.get_command_suggestions(None)
        assert len(suggestions) == 0
        
        # Test whitespace-only input
        suggestions = service.get_command_suggestions("   ")
        assert len(suggestions) == 0
    
    def test_case_insensitive_matching(self, service):
        """Test that command matching is case insensitive."""
        # Test uppercase input
        suggestions_upper = service.get_command_suggestions("STOCK")
        suggestions_lower = service.get_command_suggestions("stock")
        
        assert len(suggestions_upper) == len(suggestions_lower)
        assert suggestions_upper[0][0] == suggestions_lower[0][0]
        
        # Test mixed case
        suggestions_mixed = service.get_command_suggestions("StOcK")
        assert len(suggestions_mixed) > 0
        assert "stock" in [s[0] for s in suggestions_mixed]


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
