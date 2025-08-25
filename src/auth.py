"""Authentication and authorization for the Construction Inventory Bot."""

import logging
from typing import Optional

from .schemas import UserRole
from .airtable_client import AirtableClient
# Settings will be passed in constructor

logger = logging.getLogger(__name__)


class AuthService:
    """Service for handling authentication and authorization."""
    
    def __init__(self, settings, airtable_client: AirtableClient):
        """Initialize the auth service."""
        self.settings = settings
        self.airtable = airtable_client
    
    async def get_user_role(self, user_id: int) -> UserRole:
        """Get the role of a user from Airtable."""
        try:
            return await self.airtable.get_user_role(user_id)
        except Exception as e:
            logger.error(f"Error getting user role for {user_id}: {e}")
            return UserRole.VIEWER
    
    def is_chat_allowed(self, chat_id: int) -> bool:
        """Check if a chat ID is in the allowed list."""
        return chat_id in self.settings.telegram_allowed_chat_ids
    
    def can_execute_command(self, command: str, user_role: UserRole) -> bool:
        """Check if a user can execute a specific command."""
        # Command permissions by role
        permissions = {
            "help": [UserRole.ADMIN, UserRole.STAFF, UserRole.VIEWER],
            "whoami": [UserRole.ADMIN, UserRole.STAFF, UserRole.VIEWER],
            "find": [UserRole.ADMIN, UserRole.STAFF, UserRole.VIEWER],
            "onhand": [UserRole.ADMIN, UserRole.STAFF, UserRole.VIEWER],
            "in": [UserRole.ADMIN, UserRole.STAFF],  # Staff can add stock
            "out": [UserRole.ADMIN, UserRole.STAFF],  # Staff can remove stock
            "adjust": [UserRole.ADMIN],  # Only admins can adjust
            "approve": [UserRole.ADMIN],  # Only admins can approve
            "audit": [UserRole.ADMIN, UserRole.STAFF],
            "setthreshold": [UserRole.ADMIN],
            "export": [UserRole.ADMIN, UserRole.STAFF]
        }
        
        allowed_roles = permissions.get(command, [])
        return user_role in allowed_roles
    
    def is_admin(self, user_role: UserRole) -> bool:
        """Check if a user has admin privileges."""
        return user_role == UserRole.ADMIN
    
    def is_staff(self, user_role: UserRole) -> bool:
        """Check if a user has staff privileges."""
        return user_role in [UserRole.ADMIN, UserRole.STAFF]
    
    async def validate_user_access(self, user_id: int, chat_id: int, 
                                 command: str) -> tuple[bool, str, Optional[UserRole]]:
        """Validate user access for a specific command."""
        try:
            # Check if chat is allowed
            if not self.is_chat_allowed(chat_id):
                return False, "This chat is not authorized to use the bot.", None
            
            # Get user role
            user_role = await self.get_user_role(user_id)
            
            # Check if user can execute the command
            if not self.can_execute_command(command, user_role):
                return False, f"You don't have permission to use /{command}.", None
            
            return True, "Access granted.", user_role
            
        except Exception as e:
            logger.error(f"Error validating user access: {e}")
            return False, "Error validating access. Please try again.", None
    
    async def create_user_if_not_exists(self, user_id: int, username: str, 
                                      first_name: str, last_name: Optional[str] = None) -> bool:
        """Create a new user in Airtable if they don't exist."""
        try:
            # Check if user already exists
            existing_role = await self.get_user_role(user_id)
            if existing_role != UserRole.VIEWER:  # If we got a real role, user exists
                return True
            
            # Create new user with default VIEWER role
            # This would require implementing a method to create users in Airtable
            # For now, return True (assume creation is handled elsewhere)
            logger.info(f"New user {user_id} ({username}) would be created with VIEWER role")
            return True
            
        except Exception as e:
            logger.error(f"Error creating user {user_id}: {e}")
            return False
