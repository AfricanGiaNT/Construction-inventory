"""Command suggestion service for fuzzy command matching and typo correction."""

import logging
from difflib import SequenceMatcher
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class CommandSuggestionsService:
    """Service for suggesting commands based on user input and handling typos."""
    
    def __init__(self):
        """Initialize the command suggestions service."""
        # Define all available commands with their categories and descriptions
        self.available_commands = {
            # Stock Operations
            "in": {
                "category": "Stock Operations",
                "description": "Add stock to inventory",
                "usage": "/in <item>, <qty> <unit>, [details]",
                "examples": ["/in cement, 50 bags", "/in steel bars, 100 pieces"]
            },
            "out": {
                "category": "Stock Operations", 
                "description": "Remove stock from inventory",
                "usage": "/out <item>, <qty> <unit>, [details]",
                "examples": ["/out cement, 25 bags", "/out steel bars, 10 pieces"]
            },
            "adjust": {
                "category": "Stock Operations",
                "description": "Correct stock levels (admin only)",
                "usage": "/adjust <item>, ±<qty> <unit>",
                "examples": ["/adjust cement, +5 bags", "/adjust steel bars, -2 pieces"]
            },
            
            # Queries
            "stock": {
                "category": "Queries",
                "description": "Search inventory with fuzzy matching",
                "usage": "/stock <item_name>",
                "examples": ["/stock cement", "/stock m24 bolts", "/stock safety helmets"]
            },
            "find": {
                "category": "Queries",
                "description": "Search inventory by exact name",
                "usage": "/find <item_name>",
                "examples": ["/find cement bags", "/find steel bars"]
            },
            "onhand": {
                "category": "Queries", 
                "description": "Check current stock level",
                "usage": "/onhand <item_name>",
                "examples": ["/onhand cement", "/onhand steel bars"]
            },
            "whoami": {
                "category": "Queries",
                "description": "Show your user information",
                "usage": "/whoami",
                "examples": ["/whoami"]
            },
            
            # Management
            "approve": {
                "category": "Management",
                "description": "Approve a stock movement",
                "usage": "/approve <movement_id>",
                "examples": ["/approve 12345"]
            },
            "audit": {
                "category": "Management",
                "description": "Show low stock items",
                "usage": "/audit",
                "examples": ["/audit"]
            },
            "export": {
                "category": "Management",
                "description": "Export inventory data",
                "usage": "/export <type>",
                "examples": ["/export onhand"]
            },
            
            # Batch Operations
            "batchhelp": {
                "category": "Batch Operations",
                "description": "Detailed batch command guide",
                "usage": "/batchhelp",
                "examples": ["/batchhelp"]
            },
            "validate": {
                "category": "Batch Operations",
                "description": "Test batch format without processing",
                "usage": "/validate <entries>",
                "examples": ["/validate cement, 5 bags; sand, 10 bags"]
            },
            "status": {
                "category": "Batch Operations",
                "description": "Show system status and features",
                "usage": "/status",
                "examples": ["/status"]
            },
            
            # Help
            "help": {
                "category": "Help",
                "description": "Show available commands",
                "usage": "/help [topic]",
                "examples": ["/help", "/help stock", "/help batch"]
            },
            "quickhelp": {
                "category": "Help",
                "description": "Get quick help for a specific command",
                "usage": "/quickhelp <command_name>",
                "examples": ["/quickhelp stock", "/quickhelp in", "/quickhelp batchhelp"]
            },
            "monitor": {
                "category": "Management",
                "description": "Show system monitoring and debugging information",
                "usage": "/monitor",
                "examples": ["/monitor"]
            }
        }
        
        logger.info(f"CommandSuggestionsService initialized with {len(self.available_commands)} commands")
    
    def get_command_suggestions(self, user_input: str, max_suggestions: int = 3) -> List[Tuple[str, float, dict]]:
        """
        Get command suggestions based on user input.
        
        Args:
            user_input: The user's command input
            max_suggestions: Maximum number of suggestions to return
            
        Returns:
            List of tuples: (command_name, similarity_score, command_info)
        """
        try:
            if not user_input:
                return []
            
            # Remove leading slash if present
            clean_input = user_input.lstrip('/').lower()
            
            # Calculate similarity scores for all commands
            scored_commands = []
            for cmd_name, cmd_info in self.available_commands.items():
                similarity = self._calculate_similarity(clean_input, cmd_name)
                scored_commands.append((cmd_name, similarity, cmd_info))
            
            # Sort by similarity score (highest first)
            scored_commands.sort(key=lambda x: x[1], reverse=True)
            
            # Filter out very low similarity scores and take top suggestions
            suggestions = [
                (cmd, score, info) for cmd, score, info in scored_commands
                if score >= 0.3  # Minimum similarity threshold
            ][:max_suggestions]
            
            logger.debug(f"Command suggestions for '{user_input}': {suggestions}")
            return suggestions
            
        except Exception as e:
            logger.error(f"Error getting command suggestions for '{user_input}': {e}")
            return []
    
    def get_command_info(self, command_name: str) -> Optional[dict]:
        """
        Get information about a specific command.
        
        Args:
            command_name: Name of the command (without leading slash)
            
        Returns:
            Command information dictionary or None if not found
        """
        return self.available_commands.get(command_name.lower())
    
    def get_commands_by_category(self, category: str) -> List[Tuple[str, dict]]:
        """
        Get all commands in a specific category.
        
        Args:
            category: Category name to filter by
            
        Returns:
            List of tuples: (command_name, command_info)
        """
        try:
            category_lower = category.lower()
            commands = [
                (cmd_name, cmd_info) for cmd_name, cmd_info in self.available_commands.items()
                if cmd_info["category"].lower() == category_lower
            ]
            return commands
        except Exception as e:
            logger.error(f"Error getting commands for category '{category}': {e}")
            return []
    
    def get_all_categories(self) -> List[str]:
        """
        Get all available command categories.
        
        Returns:
            List of category names
        """
        try:
            categories = list(set(info["category"] for info in self.available_commands.values()))
            return sorted(categories)
        except Exception as e:
            logger.error(f"Error getting command categories: {e}")
            return []
    
    def _calculate_similarity(self, input_text: str, command_name: str) -> float:
        """
        Calculate similarity between input text and command name.
        
        Args:
            input_text: User input text
            command_name: Command name to compare against
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        try:
            # Use SequenceMatcher for string similarity
            matcher = SequenceMatcher(None, input_text.lower(), command_name.lower())
            similarity = matcher.ratio()
            
            # Bonus for exact prefix match
            if command_name.lower().startswith(input_text.lower()):
                similarity += 0.2
            
            # Bonus for substring match
            if input_text.lower() in command_name.lower():
                similarity += 0.1
            
            # Cap at 1.0
            return min(similarity, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating similarity between '{input_text}' and '{command_name}': {e}")
            return 0.0
    
    def format_suggestions_message(self, user_input: str, suggestions: List[Tuple[str, float, dict]]) -> str:
        """
        Format command suggestions into a user-friendly message.
        
        Args:
            user_input: Original user input
            suggestions: List of command suggestions
            
        Returns:
            Formatted message string
        """
        try:
            if not suggestions:
                return f"❌ <b>Unknown Command: /{user_input}</b>\n\nNo similar commands found."
            
            message = f"❓ <b>Did you mean one of these commands?</b>\n\n"
            
            for i, (cmd_name, similarity, cmd_info) in enumerate(suggestions, 1):
                message += f"{i}. <b>/{cmd_name}</b> - {cmd_info['description']}\n"
                message += f"   <i>Usage:</i> <code>{cmd_info['usage']}</code>\n"
                if cmd_info['examples']:
                    message += f"   <i>Example:</i> <code>{cmd_info['examples'][0]}</code>\n"
                message += "\n"
            
            message += "💡 <b>Tips:</b>\n"
            message += "• Use <code>/help</code> to see all commands\n"
            message += "• Use <code>/help [category]</code> to browse by category\n"
            message += "• Commands are case-insensitive"
            
            return message
            
        except Exception as e:
            logger.error(f"Error formatting suggestions message: {e}")
            return f"❌ <b>Unknown Command: /{user_input}</b>\n\nUse <code>/help</code> to see available commands."
    
    def get_quick_help(self, command_name: str) -> Optional[str]:
        """
        Get quick help for a specific command.
        
        Args:
            command_name: Name of the command
            
        Returns:
            Quick help message or None if command not found
        """
        try:
            cmd_info = self.get_command_info(command_name)
            if not cmd_info:
                return None
            
            help_text = f"📖 <b>/{command_name} - Quick Help</b>\n\n"
            help_text += f"<b>Description:</b> {cmd_info['description']}\n\n"
            help_text += f"<b>Usage:</b>\n<code>{cmd_info['usage']}</code>\n\n"
            
            if cmd_info['examples']:
                help_text += "<b>Examples:</b>\n"
                for example in cmd_info['examples']:
                    help_text += f"• <code>{example}</code>\n"
                help_text += "\n"
            
            help_text += f"<b>Category:</b> {cmd_info['category']}\n\n"
            help_text += "💡 Use <code>/help {command_name}</code> for more details."
            
            return help_text
            
        except Exception as e:
            logger.error(f"Error getting quick help for '{command_name}': {e}")
            return None
