"""Command parsing and routing for the Construction Inventory Bot."""

import re
from typing import List, Optional, Tuple

from .schemas import Command, MovementType
from .nlp_parser import NLPStockParser


class CommandParser:
    """Parser for Telegram commands."""
    
    def __init__(self):
        """Initialize the command parser."""
        # Command patterns
        self.patterns = {
            "help": r"^/help$",
            "whoami": r"^/whoami$",
            "find": r"^/find\s+(.+)$",
            "onhand": r"^/onhand\s+(\S+)$",
            "in": r"^/in\s+([\s\S]+)$",  # Captures everything after /in including newlines
            "out": r"^/out\s+([\s\S]+)$",  # Captures everything after /out including newlines
            "adjust": r"^/adjust\s+([\s\S]+)$",  # Captures everything after /adjust including newlines
            "approve": r"^/approve\s+(\S+)$",
            "audit": r"^/audit$",
            "setthreshold": r"^/setthreshold\s+([\d.]+)$",
            "export": r"^/export\s+(onhand)$",
            "batchhelp": r"^/batchhelp$",
            "status": r"^/status$",
            "validate": r"^/validate\s+([\s\S]+)$",  # Captures everything after /validate including newlines
            "stock": r"^/stock\s+(.+)$"  # Captures everything after /stock for fuzzy search
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
        
        for command, pattern in self.patterns.items():
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                args = list(match.groups())
                # Remove None values from args
                args = [arg for arg in args if arg is not None]
                
                logger.info(f"DEBUG - Command matched: '{command}' with args: {args}")
                
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
