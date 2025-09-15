"""Command parsing and routing for the Construction Inventory Bot."""

import re
from typing import List, Optional, Tuple

from schemas import Command, MovementType
from nlp_parser import NLPStockParser


class CommandParser:
    """Parser for Telegram commands."""
    
    def __init__(self):
        """Initialize the command parser."""
        # Command patterns - order matters! More specific patterns must come first
        self.command_patterns = {
            "help": r"^/help\s*(.+)?$",  # Optional help topic
            "status": r"^/status\s*(.+)?$",  # Optional status topic
            "whoami": r"^/whoami$",
            "in": r"^/in\s+([\s\S]+)$",  # Captures everything after /in including newlines
            "out": r"^/out\s+([\s\S]+)$",  # Captures everything after /out including newlines
            "stock": r"^/stock\s+(.+)$",  # Captures everything after /stock for fuzzy search
            "search_category": r"^/search\s+category:([^\s]+)\s*(.+)?$",  # Category-based search
            "category_overview": r"^/category\s+overview$",  # Category overview
            "low_stock_category": r"^/stock\s+low\s+category:([^\s]+)$",  # Low stock by category
            "migration_preview": r"^/migration\s+preview$",  # Migration preview
            "migration_validate": r"^/migration\s+validate$",  # Migration validation
            "migration_dry_run": r"^/migration\s+dry_run$",  # Migration dry run
            "migration_execute": r"^/migration\s+execute$",  # Execute migration
            "report_category": r"^/report\s+category:([^\s]+)$",  # Category-based report
            "report_statistics": r"^/report\s+statistics$",  # Category statistics report
            "edge_case_test": r"^/edge\s+test$",  # Test edge case handling
            "performance_test": r"^/performance\s+test$",  # Run performance tests
            "system_health": r"^/system\s+health$",  # System health check
            "inventory_validate": r"^/inventory\s+validate\s+([\s\S]+)$",  # Must come before inventory
            "inventory": r"^/inventory\s+([\s\S]+)$",  # Captures everything after /inventory including newlines
            "preview_in": r"^/preview\s+in\s+([\s\S]+)$",  # Preview IN command duplicates
            "preview_out": r"^/preview\s+out\s+([\s\S]+)$"  # Preview OUT command duplicates
        }
        
        # Initialize NLP parser
        self.nlp_parser = NLPStockParser()
    
    def parse_command(self, text: str, chat_id: int, user_id: int, 
                     user_name: str, message_id: int, update_id: int) -> Optional[Command]:
        """Parse a Telegram message into a Command object."""
        import logging
        logger = logging.getLogger(__name__)
        
        text = text.strip()
        logger.info(f"DEBUG - Parsing command: '{text}'")
        
        for command, pattern in self.command_patterns.items():
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                args = list(match.groups())
                # Remove None values from args
                args = [arg for arg in args if arg is not None]
                
                return Command(
                    command=command,
                    args=args,
                    chat_id=chat_id,
                    user_id=user_id,
                    user_name=user_name,
                    message_id=message_id,
                    update_id=update_id
                )
        
        logger.info(f"DEBUG - No command pattern matched for: '{text}'")
        return None
    
    def parse_movement_args(self, args: List[str]) -> Tuple[str, float, str, Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Parse movement command arguments using NLP parser."""
        if not args:
            raise ValueError("No arguments provided for movement command")
        
        # Join all arguments into a single text for NLP parsing
        full_text = " ".join(args)
        
        # Use NLP parser to extract information
        # This will be called from the main bot with proper user context
        return full_text, 0, None, None, None, None, None
    
    def validate_movement(self, movement_type: MovementType, quantity: float, 
                         unit: Optional[str] = None) -> bool:
        """Validate movement parameters."""
        if quantity <= 0:
            return False
        
        if movement_type == MovementType.ADJUST:
            # Adjust can be negative (quantity can be negative)
            pass
        elif movement_type == MovementType.OUT:
            # Out quantity should be positive
            if quantity < 0:
                return False
        
        # TODO: Validate unit against allowed units for the item
        
        return True


class CommandRouter:
    """Routes parsed commands to appropriate handlers."""
    
    def __init__(self):
        """Initialize the command router."""
        self.parser = CommandParser()
    
    async def route_command(self, text: str, chat_id: int, user_id: int, 
                           user_name: str, message_id: int, update_id: int):
        """Route a command to its appropriate handler."""
        command = self.parser.parse_command(
            text, chat_id, user_id, user_name, message_id, update_id
        )
        
        if not command:
            return None, "Invalid command format. Use /help for available commands."
        
        return command, None
