"""Integration test for Phase 3: Enhanced Error Handling and User Experience."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.main import ConstructionInventoryBot
from src.services.command_suggestions import CommandSuggestionsService


class TestPhase3Integration:
    """Test that Phase 3 features work together correctly."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot instance with Phase 3 features."""
        bot = MagicMock()
        bot.command_suggestions_service = CommandSuggestionsService()
        bot.telegram_service = MagicMock()
        bot.telegram_service.send_message = AsyncMock(return_value=True)
        bot.telegram_service.send_error_message = AsyncMock(return_value=True)
        return bot
    
    @pytest.fixture
    def command_suggestions_service(self):
        """Create a real command suggestions service for testing."""
        return CommandSuggestionsService()
    
    def test_unknown_command_handling(self, mock_bot):
        """Test that unknown commands trigger command suggestions."""
        # Test with a typo that should have suggestions
        suggestions = mock_bot.command_suggestions_service.get_command_suggestions("stok")
        assert len(suggestions) > 0
        assert "stock" in [s[0] for s in suggestions]
        
        # Test with a completely unknown command
        suggestions = mock_bot.command_suggestions_service.get_command_suggestions("xyz123")
        assert len(suggestions) == 0
    
    def test_command_suggestions_for_typos(self, command_suggestions_service):
        """Test command suggestions for common typos."""
        # Test common typos and their expected corrections
        typo_corrections = [
            ("stok", "stock"),
            ("hel", "help"),
            ("batchelp", "batchhelp"),
            ("statu", "status"),
            ("valida", "validate"),
            ("expor", "export"),
            ("aud", "audit"),
            ("approv", "approve"),
            ("quikhelp", "quickhelp")
        ]
        
        for typo, expected_command in typo_corrections:
            suggestions = command_suggestions_service.get_command_suggestions(typo)
            assert len(suggestions) > 0, f"No suggestions for typo: {typo}"
            
            # Check if the expected command is in the suggestions
            suggested_commands = [s[0] for s in suggestions]
            assert expected_command in suggested_commands, f"Expected {expected_command} for typo {typo}, got {suggested_commands}"
    
    def test_quickhelp_command_integration(self, command_suggestions_service):
        """Test that the quickhelp command works correctly."""
        # Test quick help for existing commands
        help_text = command_suggestions_service.get_quick_help("stock")
        assert help_text is not None
        assert "stock - Quick Help" in help_text
        assert "Description:" in help_text
        assert "Usage:" in help_text
        assert "Examples:" in help_text
        assert "Category:" in help_text
        
        # Test quick help for non-existent command
        help_text = command_suggestions_service.get_quick_help("nonexistent")
        assert help_text is None
    
    def test_enhanced_help_categories(self, command_suggestions_service):
        """Test that help categories are properly organized."""
        categories = command_suggestions_service.get_all_categories()
        expected_categories = [
            "Stock Operations",
            "Queries", 
            "Management",
            "Batch Operations",
            "Help"
        ]
        
        for expected_category in expected_categories:
            assert expected_category in categories, f"Missing category: {expected_category}"
        
        # Test that each category has commands
        for category in categories:
            commands = command_suggestions_service.get_commands_by_category(category)
            assert len(commands) > 0, f"Category {category} has no commands"
    
    def test_similarity_scoring_accuracy(self, command_suggestions_service):
        """Test that similarity scoring provides accurate suggestions."""
        # Test that exact matches get highest scores
        exact_score = command_suggestions_service._calculate_similarity("stock", "stock")
        typo_score = command_suggestions_service._calculate_similarity("stok", "stock")
        unrelated_score = command_suggestions_service._calculate_similarity("xyz", "stock")
        
        assert exact_score > typo_score > unrelated_score
        
        # Test that prefix matches get bonus points
        prefix_score = command_suggestions_service._calculate_similarity("st", "stock")
        substring_score = command_suggestions_service._calculate_similarity("ock", "stock")
        
        assert prefix_score > substring_score
    
    def test_command_suggestions_limit(self, command_suggestions_service):
        """Test that command suggestions respect limits."""
        # Test default limit (3)
        suggestions = command_suggestions_service.get_command_suggestions("st")
        assert len(suggestions) <= 3
        
        # Test custom limits
        suggestions = command_suggestions_service.get_command_suggestions("st", max_suggestions=1)
        assert len(suggestions) <= 1
        
        suggestions = command_suggestions_service.get_command_suggestions("st", max_suggestions=5)
        assert len(suggestions) <= 5
    
    def test_suggestions_message_formatting(self, command_suggestions_service):
        """Test that suggestions messages are properly formatted."""
        # Test with suggestions
        suggestions = command_suggestions_service.get_command_suggestions("stok")
        message = command_suggestions_service.format_suggestions_message("stok", suggestions)
        
        # Check required elements
        assert "Did you mean one of these commands?" in message
        assert "stock" in message.lower()
        assert "Usage:" in message
        assert "Example:" in message
        assert "Tips:" in message
        assert "/help" in message
        
        # Test without suggestions
        message = command_suggestions_service.format_suggestions_message("xyz123", [])
        assert "No similar commands found" in message
        assert "Unknown Command: /xyz123" in message
    
    def test_case_insensitive_command_matching(self, command_suggestions_service):
        """Test that command matching works regardless of case."""
        # Test different case variations
        suggestions_lower = command_suggestions_service.get_command_suggestions("stock")
        suggestions_upper = command_suggestions_service.get_command_suggestions("STOCK")
        suggestions_mixed = command_suggestions_service.get_command_suggestions("StOcK")
        
        # All should return the same suggestions
        assert len(suggestions_lower) == len(suggestions_upper) == len(suggestions_mixed)
        
        # Check that the same commands are suggested
        lower_commands = [s[0] for s in suggestions_lower]
        upper_commands = [s[0] for s in suggestions_upper]
        mixed_commands = [s[0] for s in suggestions_mixed]
        
        assert lower_commands == upper_commands == mixed_commands
    
    def test_empty_and_edge_case_inputs(self, command_suggestions_service):
        """Test handling of empty and edge case inputs."""
        # Test empty string
        suggestions = command_suggestions_service.get_command_suggestions("")
        assert len(suggestions) == 0
        
        # Test whitespace-only
        suggestions = command_suggestions_service.get_command_suggestions("   ")
        assert len(suggestions) == 0
        
        # Test very short input
        suggestions = command_suggestions_service.get_command_suggestions("a")
        assert len(suggestions) <= 3  # Should respect limit
        
        # Test very long input
        long_input = "a" * 100
        suggestions = command_suggestions_service.get_command_suggestions(long_input)
        # Should handle gracefully without error
    
    def test_command_info_completeness(self, command_suggestions_service):
        """Test that all commands have complete information."""
        for cmd_name, cmd_info in command_suggestions_service.available_commands.items():
            # Check required fields
            assert "category" in cmd_info, f"Command {cmd_name} missing category"
            assert "description" in cmd_info, f"Command {cmd_name} missing description"
            assert "usage" in cmd_info, f"Command {cmd_name} missing usage"
            assert "examples" in cmd_info, f"Command {cmd_name} missing examples"
            
            # Check field types
            assert isinstance(cmd_info["category"], str), f"Command {cmd_name} category is not string"
            assert isinstance(cmd_info["description"], str), f"Command {cmd_name} description is not string"
            assert isinstance(cmd_info["usage"], str), f"Command {cmd_name} usage is not string"
            assert isinstance(cmd_info["examples"], list), f"Command {cmd_name} examples is not list"
            
            # Check that examples list is not empty
            assert len(cmd_info["examples"]) > 0, f"Command {cmd_name} has no examples"
    
    def test_phase3_feature_integration(self, command_suggestions_service):
        """Test that all Phase 3 features work together."""
        # Test the complete flow: typo -> suggestions -> formatted message
        typo = "stok"
        
        # Step 1: Get suggestions
        suggestions = command_suggestions_service.get_command_suggestions(typo)
        assert len(suggestions) > 0
        
        # Step 2: Format suggestions message
        message = command_suggestions_service.format_suggestions_message(typo, suggestions)
        assert "Did you mean one of these commands?" in message
        
        # Step 3: Get quick help for the suggested command
        if suggestions:
            suggested_command = suggestions[0][0]
            quick_help = command_suggestions_service.get_quick_help(suggested_command)
            assert quick_help is not None
            assert suggested_command in quick_help
        
        # Step 4: Verify category organization
        categories = command_suggestions_service.get_all_categories()
        assert len(categories) >= 5  # Should have at least 5 categories
        
        # Step 5: Verify commands in each category
        for category in categories:
            commands = command_suggestions_service.get_commands_by_category(category)
            assert len(commands) > 0, f"Category {category} is empty"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
