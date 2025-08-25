"""Keyboard management service for inline keyboards with expiry and rate limiting."""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dataclasses import dataclass
import uuid

logger = logging.getLogger(__name__)


@dataclass
class KeyboardState:
    """Represents the state of an inline keyboard."""
    keyboard_id: str
    user_id: int
    query_type: str
    items: List[str]
    created_at: datetime
    expires_at: datetime
    click_count: int = 0
    last_click_time: Optional[datetime] = None


@dataclass
class UserClickCount:
    """Tracks user's click rate limiting."""
    user_id: int
    clicks: List[datetime]  # List of click timestamps
    max_clicks: int = 3
    window_minutes: int = 1


class KeyboardManagementService:
    """Service for managing inline keyboards with expiry and rate limiting."""
    
    def __init__(self, expiry_hours: int = 1, max_clicks_per_minute: int = 3):
        """
        Initialize the keyboard management service.
        
        Args:
            expiry_hours: How long keyboards remain active (default: 1 hour)
            max_clicks_per_minute: Maximum clicks per user per minute (default: 3)
        """
        self.expiry_hours = expiry_hours
        self.max_clicks_per_minute = max_clicks_per_minute
        
        # Active keyboards: keyboard_id -> KeyboardState
        self.active_keyboards: Dict[str, KeyboardState] = {}
        
        # User click tracking: user_id -> UserClickCount
        self.user_click_counts: Dict[int, UserClickCount] = {}
        
        logger.info(f"KeyboardManagementService initialized with {expiry_hours}h expiry and {max_clicks_per_minute} clicks/min limit")
    
    def create_keyboard(self, user_id: int, query_type: str, items: List[str]) -> str:
        """
        Create a new keyboard with expiry tracking.
        
        Args:
            user_id: Telegram user ID
            query_type: Type of query (e.g., 'stock_query', 'batch_approval')
            items: List of items for the keyboard
            
        Returns:
            Unique keyboard ID
        """
        try:
            # Generate unique keyboard ID
            keyboard_id = f"{query_type}_{uuid.uuid4().hex[:8]}"
            
            # Calculate expiry time
            created_at = datetime.now()
            expires_at = created_at + timedelta(hours=self.expiry_hours)
            
            # Create keyboard state
            keyboard_state = KeyboardState(
                keyboard_id=keyboard_id,
                user_id=user_id,
                query_type=query_type,
                items=items,
                created_at=created_at,
                expires_at=expires_at
            )
            
            # Store keyboard state
            self.active_keyboards[keyboard_id] = keyboard_state
            
            logger.info(f"Created keyboard {keyboard_id} for user {user_id}, expires at {expires_at}")
            return keyboard_id
            
        except Exception as e:
            logger.error(f"Error creating keyboard for user {user_id}: {e}")
            raise
    
    def get_keyboard(self, keyboard_id: str) -> Optional[KeyboardState]:
        """
        Get keyboard state by ID.
        
        Args:
            keyboard_id: Unique keyboard identifier
            
        Returns:
            KeyboardState if found and not expired, None otherwise
        """
        try:
            if keyboard_id not in self.active_keyboards:
                return None
            
            keyboard_state = self.active_keyboards[keyboard_id]
            
            # Check if expired
            if self.is_keyboard_expired(keyboard_id):
                logger.info(f"Keyboard {keyboard_id} is expired, removing")
                self._remove_keyboard(keyboard_id)
                return None
            
            return keyboard_state
            
        except Exception as e:
            logger.error(f"Error getting keyboard {keyboard_id}: {e}")
            return None
    
    def is_keyboard_expired(self, keyboard_id: str) -> bool:
        """
        Check if a keyboard has expired.
        
        Args:
            keyboard_id: Unique keyboard identifier
            
        Returns:
            True if expired, False otherwise
        """
        try:
            if keyboard_id not in self.active_keyboards:
                return True
            
            keyboard_state = self.active_keyboards[keyboard_id]
            return datetime.now() > keyboard_state.expires_at
            
        except Exception as e:
            logger.error(f"Error checking expiry for keyboard {keyboard_id}: {e}")
            return True
    
    def can_click_keyboard(self, user_id: int, keyboard_id: str) -> bool:
        """
        Check if user can click a keyboard (rate limiting).
        
        Args:
            user_id: Telegram user ID
            keyboard_id: Unique keyboard identifier
            
        Returns:
            True if user can click, False if rate limited
        """
        try:
            # Check if keyboard exists and is not expired
            keyboard_state = self.get_keyboard(keyboard_id)
            if not keyboard_state:
                return False
            
            # Check rate limiting
            return self._check_rate_limit(user_id)
            
        except Exception as e:
            logger.error(f"Error checking if user {user_id} can click keyboard {keyboard_id}: {e}")
            return False
    
    def record_keyboard_click(self, user_id: int, keyboard_id: str) -> bool:
        """
        Record a keyboard click for rate limiting.
        
        Args:
            user_id: Telegram user ID
            keyboard_id: Unique keyboard identifier
            
        Returns:
            True if click was recorded, False otherwise
        """
        try:
            # Check if user can click
            if not self.can_click_keyboard(user_id, keyboard_id):
                return False
            
            # Record click in keyboard state
            if keyboard_id in self.active_keyboards:
                keyboard_state = self.active_keyboards[keyboard_id]
                keyboard_state.click_count += 1
                keyboard_state.last_click_time = datetime.now()
            
            # Record click for rate limiting
            self._record_user_click(user_id)
            
            logger.debug(f"Recorded click for user {user_id} on keyboard {keyboard_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error recording click for user {user_id} on keyboard {keyboard_id}: {e}")
            return False
    
    def cleanup_expired_keyboards(self) -> int:
        """
        Remove all expired keyboards.
        
        Returns:
            Number of keyboards removed
        """
        try:
            current_time = datetime.now()
            keys_to_remove = []
            
            for keyboard_id, keyboard_state in self.active_keyboards.items():
                if current_time > keyboard_state.expires_at:
                    keys_to_remove.append(keyboard_id)
            
            # Remove expired keyboards
            for keyboard_id in keys_to_remove:
                self._remove_keyboard(keyboard_id)
            
            if keys_to_remove:
                logger.info(f"Cleaned up {len(keys_to_remove)} expired keyboards")
            
            return len(keys_to_remove)
            
        except Exception as e:
            logger.error(f"Error cleaning up expired keyboards: {e}")
            return 0
    
    def get_keyboard_stats(self) -> Dict:
        """
        Get statistics about active keyboards.
        
        Returns:
            Dictionary with keyboard statistics
        """
        try:
            current_time = datetime.now()
            total_keyboards = len(self.active_keyboards)
            expired_keyboards = sum(
                1 for k in self.active_keyboards.values() 
                if current_time > k.expires_at
            )
            active_keyboards = total_keyboards - expired_keyboards
            
            return {
                "total_keyboards": total_keyboards,
                "active_keyboards": active_keyboards,
                "expired_keyboards": expired_keyboards,
                "total_users": len(set(k.user_id for k in self.active_keyboards.values())),
                "expiry_hours": self.expiry_hours,
                "max_clicks_per_minute": self.max_clicks_per_minute
            }
            
        except Exception as e:
            logger.error(f"Error getting keyboard stats: {e}")
            return {}
    
    def _check_rate_limit(self, user_id: int) -> bool:
        """
        Check if user is within rate limit.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if within rate limit, False otherwise
        """
        try:
            if user_id not in self.user_click_counts:
                return True
            
            user_clicks = self.user_click_counts[user_id]
            current_time = datetime.now()
            
            # Remove clicks older than the time window
            recent_clicks = [
                click_time for click_time in user_clicks.clicks
                if current_time - click_time < timedelta(minutes=user_clicks.window_minutes)
            ]
            
            # Update user clicks
            user_clicks.clicks = recent_clicks
            
            # Check if within limit
            return len(recent_clicks) < user_clicks.max_clicks
            
        except Exception as e:
            logger.error(f"Error checking rate limit for user {user_id}: {e}")
            return False
    
    def _record_user_click(self, user_id: int):
        """
        Record a user click for rate limiting.
        
        Args:
            user_id: Telegram user ID
        """
        try:
            if user_id not in self.user_click_counts:
                self.user_click_counts[user_id] = UserClickCount(
                    user_id=user_id,
                    clicks=[],
                    max_clicks=self.max_clicks_per_minute
                )
            
            user_clicks = self.user_click_counts[user_id]
            user_clicks.clicks.append(datetime.now())
            
        except Exception as e:
            logger.error(f"Error recording user click for user {user_id}: {e}")
    
    def _remove_keyboard(self, keyboard_id: str):
        """
        Remove a keyboard from active keyboards.
        
        Args:
            keyboard_id: Unique keyboard identifier
        """
        try:
            if keyboard_id in self.active_keyboards:
                del self.active_keyboards[keyboard_id]
                logger.debug(f"Removed keyboard {keyboard_id}")
                
        except Exception as e:
            logger.error(f"Error removing keyboard {keyboard_id}: {e}")
    
    def clear_all_keyboards(self):
        """Clear all active keyboards (for testing/debugging)."""
        try:
            count = len(self.active_keyboards)
            self.active_keyboards.clear()
            self.user_click_counts.clear()
            logger.info(f"Cleared all {count} keyboards and user click counts")
            
        except Exception as e:
            logger.error(f"Error clearing all keyboards: {e}")
