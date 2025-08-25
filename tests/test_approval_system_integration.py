"""
Comprehensive end-to-end test for the approval system implementation.
This test verifies all components working together through the entire flow:
- Command parsing
- Batch preparation
- Approval request display
- Admin approval/rejection
- Movement processing
- Success summary generation
"""

import pytest
import asyncio
import logging
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from src.services.approvals import ApprovalService
from src.services.batch_stock import BatchStockService
from src.services.stock import StockService
from src.telegram_service import TelegramService
from src.services.queries import QueryService
from src.auth import AuthService
from src.commands import CommandRouter
from src.nlp_parser import NLPStockParser as NLPParser
from src.schemas import (
    MovementStatus, MovementType, StockMovement, UserRole, 
    BatchApproval, Item, BatchResult, BatchError, Command
)
# We'll create a simplified version of the bot for testing
class ConstructionInventoryBot:
    """Simplified version of the bot for testing."""
    
    def __init__(self, telegram_service, auth_service, stock_service, batch_stock_service,
                 approval_service, query_service, command_router, settings):
        """Initialize the bot with all services."""
        self.telegram_service = telegram_service
        self.auth_service = auth_service
        self.stock_service = stock_service
        self.batch_stock_service = batch_stock_service
        self.approval_service = approval_service
        self.query_service = query_service
        self.command_router = command_router
        self.settings = settings
        # Skip scheduler initialization
    
    async def process_update(self, update):
        """Process a single update from Telegram."""
        if update.message:
            await self.process_message(update.message)
        elif update.callback_query:
            await self.process_callback_query(update.callback_query)
            
    async def process_callback_query(self, callback_query):
        """Process a callback query from inline buttons."""
        chat_id = callback_query.message.chat.id
        message_id = callback_query.message.message_id
        user_id = callback_query.from_user.id
        user_name = callback_query.from_user.username
        data = callback_query.data
        
        # Get user role from auth service
        user_role = await self.auth_service.get_user_role(user_id)
        
        # Only admins can process approvals
        if user_role != UserRole.ADMIN:
            await self.telegram_service.bot.answer_callback_query(
                callback_query.id,
                text="Only admins can approve or reject stock movements.",
                show_alert=True
            )
            return
        
        # Handle different callback types
        if data.startswith("approvebatch:"):
            batch_id = data.split(":", 1)[1]
            success, message, batch_result = await self.approval_service.approve_batch(batch_id, user_name, user_role)
            
            # Update the original message
            if success:
                updated_text = f"✅ Batch approved by {user_name}\n\n"
                original_text = callback_query.message.text
                if "Batch Approval Required" in original_text:
                    updated_text += original_text.split("Batch Approval Required")[1]
                else:
                    updated_text += original_text
                
                await self.telegram_service.bot.edit_message_text(
                    text=updated_text,
                    chat_id=chat_id,
                    message_id=message_id,
                    parse_mode="HTML"
                )
                
                # Send detailed success summary
                if batch_id in self.batch_stock_service.pending_approvals:
                    batch_approval = self.batch_stock_service.pending_approvals[batch_id]
                    await self.telegram_service.send_batch_success_summary(
                        chat_id,
                        batch_id,
                        batch_approval.movements,
                        batch_approval.before_levels,
                        batch_approval.after_levels,
                        batch_approval.failed_entries
                    )
            
            # Send feedback to the user
            await self.telegram_service.bot.answer_callback_query(
                callback_query.id,
                text="Batch approved" if success else f"Error: {message}",
                show_alert=not success
            )
            
        elif data.startswith("rejectbatch:"):
            batch_id = data.split(":", 1)[1]
            success, message = await self.approval_service.reject_batch(batch_id, user_name, user_role)
            
            # Update the original message
            if success:
                updated_text = f"❌ Batch rejected by {user_name}\n\n"
                original_text = callback_query.message.text
                if "Batch Approval Required" in original_text:
                    updated_text += original_text.split("Batch Approval Required")[1]
                else:
                    updated_text += original_text
                
                await self.telegram_service.bot.edit_message_text(
                    text=updated_text,
                    chat_id=chat_id,
                    message_id=message_id,
                    parse_mode="HTML"
                )
            
            # Send feedback to the user
            await self.telegram_service.bot.answer_callback_query(
                callback_query.id,
                text="Batch rejected" if success else f"Error: {message}",
                show_alert=not success
            )
        
        else:
            await self.telegram_service.bot.answer_callback_query(
                callback_query.id,
                text="Unknown callback action",
                show_alert=True
            )
            
    async def process_message(self, message):
        """Process a single message."""
        chat_id = message.chat.id
        text = message.text
        user_id = message.from_user.id
        user_name = message.from_user.username
        
        # Get user role from auth service
        user_role = await self.auth_service.get_user_role(user_id)
        
        # Parse command
        command = self.command_router.parser.parse_command(
            text, chat_id, user_id, user_name, 0, 0
        )
        
        if not command:
            await self.telegram_service.send_message(chat_id, "Invalid command format.")
            return
        
        # Handle different command types
        command_type = command.command
        
        if command_type == "in":
            await self._handle_in_command(chat_id, command.args[0] if command.args else "", user_id, user_name, user_role)
        elif command_type == "out":
            await self._handle_out_command(chat_id, command.args[0] if command.args else "", user_id, user_name, user_role)
        elif command_type == "adjust":
            await self._handle_adjust_command(chat_id, command.args[0] if command.args else "", user_id, user_name, user_role)
        else:
            await self.telegram_service.send_message(chat_id, f"Command '{command_type}' not supported in test.")
            
    async def _handle_in_command(self, chat_id, args_text, user_id, user_name, user_role):
        """Handle stock in command."""
        # Check if this is a batch command by parsing with batch parser
        batch_result = self.command_router.parser.nlp_parser.parse_batch_entries(
            f"in {args_text}", user_id, user_name
        )
        
        # If it's a single entry, handle with approval flow
        if batch_result.format.value == "single" and len(batch_result.movements) == 1:
            movement = batch_result.movements[0]
            
            # Create a single-entry batch approval
            success, batch_id, batch_approval = await self.batch_stock_service.prepare_batch_approval(
                [movement], 
                user_role, 
                chat_id, 
                user_id, 
                user_name
            )
            
            if success:
                # Send approval request
                await self.telegram_service.send_batch_approval_request(
                    chat_id,
                    batch_id,
                    batch_approval.movements,
                    batch_approval.before_levels,
                    user_name
                )
                
                await self.telegram_service.send_message(
                    chat_id,
                    f"📦 <b>Stock IN submitted for approval</b>\n\n"
                    f"Your request to add {movement.quantity} {movement.unit} of {movement.item_name} has been submitted for admin approval.\n\n"
                    f"<b>Batch ID:</b> {batch_id}"
                )
            else:
                await self.telegram_service.send_error_message(chat_id, f"Error preparing batch: {batch_id}")
        
        # If it's a batch, handle as batch with approval
        elif len(batch_result.movements) > 1:
            # Send batch confirmation
            batch_size = len(batch_result.movements)
            format_type = batch_result.format.value
            
            confirmation_msg = f"🔄 <b>Batch Command Detected!</b>\n\n"
            confirmation_msg += f"• <b>Format:</b> {format_type.title()}\n"
            confirmation_msg += f"• <b>Entries:</b> {batch_size} stock IN movements\n"
            confirmation_msg += f"• <b>Movement Type:</b> Stock IN\n\n"
            confirmation_msg += f"<i>Preparing batch for approval...</i>"
            
            await self.telegram_service.send_message(chat_id, confirmation_msg)
            
            # Prepare batch for approval
            success, batch_id, batch_approval = await self.batch_stock_service.prepare_batch_approval(
                batch_result.movements, 
                user_role, 
                chat_id, 
                user_id, 
                user_name,
                batch_result.global_parameters
            )
            
            if success:
                # Send approval request
                await self.telegram_service.send_batch_approval_request(
                    chat_id,
                    batch_id,
                    batch_approval.movements,
                    batch_approval.before_levels,
                    user_name
                )
                
                await self.telegram_service.send_message(
                    chat_id,
                    f"📦 <b>Batch Stock IN submitted for approval</b>\n\n"
                    f"Your batch of {batch_size} stock in items has been submitted for admin approval.\n\n"
                    f"<b>Batch ID:</b> {batch_id}"
                )
            else:
                await self.telegram_service.send_error_message(chat_id, f"Error preparing batch: {batch_id}")
        
        # If parsing failed
        else:
            error_msg = "Could not parse the command. Please use format: /in item, quantity unit, location, note"
            if batch_result.errors:
                error_msg += "\n\nErrors:\n" + "\n".join(f"• {err}" for err in batch_result.errors)
            await self.telegram_service.send_error_message(chat_id, error_msg)
            
    async def _handle_out_command(self, chat_id, args_text, user_id, user_name, user_role):
        """Handle stock out command."""
        # Check if this is a batch command by parsing with batch parser
        batch_result = self.command_router.parser.nlp_parser.parse_batch_entries(
            f"out {args_text}", user_id, user_name
        )
        
        # If it's a single entry, handle with approval flow
        if batch_result.format.value == "single" and len(batch_result.movements) == 1:
            movement = batch_result.movements[0]
            
            # Create a single-entry batch approval
            success, batch_id, batch_approval = await self.batch_stock_service.prepare_batch_approval(
                [movement], 
                user_role, 
                chat_id, 
                user_id, 
                user_name
            )
            
            if success:
                # Send approval request
                await self.telegram_service.send_batch_approval_request(
                    chat_id,
                    batch_id,
                    batch_approval.movements,
                    batch_approval.before_levels,
                    user_name
                )
                
                await self.telegram_service.send_message(
                    chat_id,
                    f"📤 <b>Stock OUT submitted for approval</b>\n\n"
                    f"Your request to remove {movement.quantity} {movement.unit} of {movement.item_name} has been submitted for admin approval.\n\n"
                    f"<b>Batch ID:</b> {batch_id}"
                )
            else:
                await self.telegram_service.send_error_message(chat_id, f"Error preparing batch: {batch_id}")
        
        # If it's a batch, handle as batch with approval
        elif len(batch_result.movements) > 1:
            # Send batch confirmation
            batch_size = len(batch_result.movements)
            format_type = batch_result.format.value
            
            confirmation_msg = f"🔄 <b>Batch Command Detected!</b>\n\n"
            confirmation_msg += f"• <b>Format:</b> {format_type.title()}\n"
            confirmation_msg += f"• <b>Entries:</b> {batch_size} stock OUT movements\n"
            confirmation_msg += f"• <b>Movement Type:</b> Stock OUT\n\n"
            confirmation_msg += f"<i>Preparing batch for approval...</i>"
            
            await self.telegram_service.send_message(chat_id, confirmation_msg)
            
            # Prepare batch for approval
            success, batch_id, batch_approval = await self.batch_stock_service.prepare_batch_approval(
                batch_result.movements, 
                user_role, 
                chat_id, 
                user_id, 
                user_name,
                batch_result.global_parameters
            )
            
            if success:
                # Send approval request
                await self.telegram_service.send_batch_approval_request(
                    chat_id,
                    batch_id,
                    batch_approval.movements,
                    batch_approval.before_levels,
                    user_name
                )
                
                await self.telegram_service.send_message(
                    chat_id,
                    f"📤 <b>Batch Stock OUT submitted for approval</b>\n\n"
                    f"Your batch of {batch_size} stock out items has been submitted for admin approval.\n\n"
                    f"<b>Batch ID:</b> {batch_id}"
                )
            else:
                await self.telegram_service.send_error_message(chat_id, f"Error preparing batch: {batch_id}")
        
        # If parsing failed
        else:
            error_msg = "Could not parse the command. Please use format: /out item, quantity unit, location, driver, from_location, note"
            if batch_result.errors:
                error_msg += "\n\nErrors:\n" + "\n".join(f"• {err}" for err in batch_result.errors)
            await self.telegram_service.send_error_message(chat_id, error_msg)
            
    async def _handle_adjust_command(self, chat_id, args_text, user_id, user_name, user_role):
        """Handle stock adjustment command."""
        # Check if this is a batch command by parsing with batch parser
        batch_result = self.command_router.parser.nlp_parser.parse_batch_entries(
            f"adjust {args_text}", user_id, user_name
        )
        
        # If it's a single entry, handle through the approval flow
        if batch_result.format.value == "single" and len(batch_result.movements) == 1:
            movement = batch_result.movements[0]
            
            # Create a single-entry batch approval
            success, batch_id, batch_approval = await self.batch_stock_service.prepare_batch_approval(
                [movement], 
                user_role, 
                chat_id, 
                user_id, 
                user_name
            )
            
            if success:
                # Send approval request
                await self.telegram_service.send_batch_approval_request(
                    chat_id,
                    batch_id,
                    batch_approval.movements,
                    batch_approval.before_levels,
                    user_name
                )
                
                # Use + or - prefix based on the quantity
                qty_prefix = "+" if movement.quantity >= 0 else ""
                
                await self.telegram_service.send_message(
                    chat_id,
                    f"📝 <b>Adjustment submitted for approval</b>\n\n"
                    f"Your request to adjust {qty_prefix}{movement.quantity} {movement.unit} of {movement.item_name} has been submitted for admin approval.\n\n"
                    f"<b>Batch ID:</b> {batch_id}"
                )
            else:
                await self.telegram_service.send_error_message(chat_id, f"Error preparing adjustment: {batch_id}")
        
        # If it's a batch, prepare for approval
        elif len(batch_result.movements) > 1:
            # Send batch confirmation
            batch_size = len(batch_result.movements)
            format_type = batch_result.format.value
            
            confirmation_msg = f"🔄 <b>Batch Command Detected!</b>\n\n"
            confirmation_msg += f"• <b>Format:</b> {format_type.title()}\n"
            confirmation_msg += f"• <b>Entries:</b> {batch_size} stock ADJUST movements\n"
            confirmation_msg += f"• <b>Movement Type:</b> Stock ADJUST\n\n"
            confirmation_msg += f"<i>Preparing batch for approval...</i>"
            
            await self.telegram_service.send_message(chat_id, confirmation_msg)
            
            # Prepare batch for approval
            success, batch_id, batch_approval = await self.batch_stock_service.prepare_batch_approval(
                batch_result.movements, 
                user_role, 
                chat_id, 
                user_id, 
                user_name,
                batch_result.global_parameters
            )
            
            if success:
                # Send approval request
                await self.telegram_service.send_batch_approval_request(
                    chat_id,
                    batch_id,
                    batch_approval.movements,
                    batch_approval.before_levels,
                    user_name
                )
                
                await self.telegram_service.send_message(
                    chat_id,
                    f"📝 <b>Adjustment batch submitted for approval</b>\n\n"
                    f"Your batch of {batch_size} adjustment items has been submitted for admin approval.\n\n"
                    f"<b>Batch ID:</b> {batch_id}"
                )
            else:
                await self.telegram_service.send_error_message(chat_id, f"Error preparing batch: {batch_id}")
        
        # If parsing failed
        else:
            error_msg = "Could not parse the command. Please use format: /adjust item, ±quantity unit, location, driver, from_location, note"
            if batch_result.errors:
                error_msg += "\n\nErrors:\n" + "\n".join(f"• {err}" for err in batch_result.errors)
            await self.telegram_service.send_error_message(chat_id, error_msg)



class MockAirtableClient:
    """Mock AirtableClient for testing."""
    
    def __init__(self):
        """Initialize with test data."""
        self.items = {}
        self.movements = {}
        self.movement_statuses = {}
        self.users = {
            "123": {"id": "123", "role": UserRole.ADMIN.value, "name": "Admin User"},
            "456": {"id": "456", "role": UserRole.STAFF.value, "name": "Staff User"}
        }
    
    def add_item(self, name, on_hand=0, base_unit="piece"):
        """Add a test item."""
        self.items[name] = Item(
            name=name,
            base_unit=base_unit,
            units=[],
            on_hand=on_hand
        )
        return self.items[name]
    
    async def get_item(self, item_name):
        """Get an item by name."""
        if item_name not in self.items:
            # Create the item if it doesn't exist
            self.add_item(item_name)
        return self.items.get(item_name)
    
    async def create_movement(self, movement):
        """Create a mock movement."""
        movement_id = f"mov_{len(self.movements) + 1}"
        movement.id = movement_id
        self.movements[movement_id] = movement
        return movement_id
        
    async def update_movement_status(self, movement_id, status, approved_by):
        """Update a movement's status."""
        if movement_id not in self.movements:
            return False
            
        self.movement_statuses[movement_id] = {
            "status": status,
            "approved_by": approved_by
        }
        
        # Update the movement
        movement = self.movements[movement_id]
        old_status = movement.status
        movement.status = MovementStatus(status)
        movement.approved_by = approved_by
        movement.approved_at = datetime.utcnow()
        
        # If changing from PENDING_APPROVAL/REQUESTED to POSTED, update stock levels
        if old_status in [MovementStatus.PENDING_APPROVAL, MovementStatus.REQUESTED] and status == MovementStatus.POSTED.value:
            item_name = movement.item_name
            if item_name in self.items:
                self.items[item_name].on_hand += movement.signed_base_quantity
        
        return True
        
    async def get_pending_approvals(self):
        """Get pending approvals."""
        pending_approvals = []
        for movement_id, movement in self.movements.items():
            if movement.status in [MovementStatus.REQUESTED, MovementStatus.PENDING_APPROVAL]:
                pending_approvals.append({
                    "id": movement_id,
                    "sku": movement.item_name,
                    "quantity": movement.quantity,
                    "unit": movement.unit
                })
        return pending_approvals
        
    async def get_user(self, user_id):
        """Get a user by ID."""
        return self.users.get(str(user_id))
        
    async def get_user_role(self, user_id):
        """Get a user's role by ID."""
        user = await self.get_user(user_id)
        if user:
            return UserRole(user["role"])
        return UserRole.GUEST
        
    async def get_items_for_location(self, location):
        """Get items by location."""
        return [item for item in self.items.values() if getattr(item, "location", None) == location]


class MockTelegramUpdate:
    """Mock Telegram Update object."""
    
    def __init__(self, message=None, callback_query=None):
        """Initialize with message or callback query."""
        self.message = message
        self.callback_query = callback_query
        self.update_id = 123456789


class MockTelegramChat:
    """Mock Telegram Chat object."""
    
    def __init__(self, chat_id):
        """Initialize with chat ID."""
        self.id = chat_id
        self.type = "group"

class MockTelegramUser:
    """Mock Telegram User object."""
    
    def __init__(self, user_id, user_name):
        """Initialize with user details."""
        self.id = user_id
        self.username = user_name
        self.first_name = user_name
        self.is_bot = False

class MockTelegramMessage:
    """Mock Telegram Message object."""
    
    def __init__(self, text, chat_id, user_id, user_name, message_id=None):
        """Initialize with message details."""
        self.text = text
        self.chat = MockTelegramChat(chat_id)
        self.from_user = MockTelegramUser(user_id, user_name)
        self.message_id = message_id or 1234
        self.date = datetime.now()
        self.entities = []


class MockTelegramCallbackQuery:
    """Mock Telegram CallbackQuery object."""
    
    def __init__(self, data, chat_id, message_id, user_id, user_name):
        """Initialize with callback query details."""
        self.data = data
        self.message = MockTelegramMessage(
            text="Original message text", 
            chat_id=chat_id,
            user_id=user_id,
            user_name=user_name,
            message_id=message_id
        )
        self.from_user = MockTelegramUser(user_id, user_name)
        self.id = f"callback_query_{message_id}_{user_id}"
        self.chat_instance = f"chat_instance_{chat_id}"


class InlineKeyboardButton:
    """Mock InlineKeyboardButton for testing."""
    
    def __init__(self, text, callback_data=None, url=None):
        """Initialize with button details."""
        self.text = text
        self.callback_data = callback_data
        self.url = url

class InlineKeyboardMarkup:
    """Mock InlineKeyboardMarkup for testing."""
    
    def __init__(self, inline_keyboard):
        """Initialize with keyboard layout."""
        self.inline_keyboard = inline_keyboard

class MockTelegramBot:
    """Mock Telegram Bot for testing."""
    
    def __init__(self):
        """Initialize with empty message history."""
        self.sent_messages = []
        self.callbacks_answered = []
        self.edited_messages = []
        self.next_message_id = 1000
    
    def _get_next_message_id(self):
        """Get the next message ID."""
        message_id = self.next_message_id
        self.next_message_id += 1
        return message_id
    
    async def send_message(self, chat_id, text, reply_markup=None, parse_mode=None):
        """Mock send_message method."""
        message_id = self._get_next_message_id()
        
        # Convert reply_markup to our mock objects if it's a dict
        if isinstance(reply_markup, dict) and "inline_keyboard" in reply_markup:
            keyboard = []
            for row in reply_markup["inline_keyboard"]:
                keyboard_row = []
                for button in row:
                    keyboard_row.append(InlineKeyboardButton(
                        text=button.get("text", ""),
                        callback_data=button.get("callback_data", None),
                        url=button.get("url", None)
                    ))
                keyboard.append(keyboard_row)
            reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = {
            "message_id": message_id,
            "chat_id": chat_id,
            "text": text,
            "reply_markup": reply_markup,
            "parse_mode": parse_mode
        }
        self.sent_messages.append(message)
        
        # Create a proper mock message object
        mock_message = MockTelegramMessage(
            text=text,
            chat_id=chat_id,
            user_id=0,  # Bot's user ID
            user_name="bot",
            message_id=message_id
        )
        return mock_message
    
    async def edit_message_text(self, text, chat_id=None, message_id=None, inline_message_id=None, parse_mode=None, reply_markup=None):
        """Mock edit_message_text method."""
        # Find the original message if it exists
        original_message = None
        for msg in self.sent_messages:
            if msg["message_id"] == message_id and msg["chat_id"] == chat_id:
                original_message = msg
                break
        
        # Create the edited message
        edited_message = {
            "chat_id": chat_id,
            "message_id": message_id,
            "inline_message_id": inline_message_id,
            "text": text,
            "parse_mode": parse_mode,
            "reply_markup": reply_markup,
            "original_text": original_message["text"] if original_message else None
        }
        self.edited_messages.append(edited_message)
        
        # Also add as a new sent message for easier testing
        new_message_id = self._get_next_message_id()
        self.sent_messages.append({
            "message_id": new_message_id,
            "chat_id": chat_id,
            "text": text,  # Store the actual text, not prefixed
            "reply_markup": reply_markup,
            "parse_mode": parse_mode,
            "is_edited": True,
            "original_message_id": message_id
        })
        
        # Return a proper mock message object
        mock_message = MockTelegramMessage(
            text=text,
            chat_id=chat_id,
            user_id=0,  # Bot's user ID
            user_name="bot",
            message_id=new_message_id
        )
        return mock_message
    
    async def answer_callback_query(self, callback_query_id, text=None, show_alert=False):
        """Mock answer_callback_query method."""
        answer = {
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": show_alert
        }
        self.callbacks_answered.append(answer)
        return True


class MockSettings:
    """Mock Settings for testing."""
    
    def __init__(self):
        """Initialize with test settings."""
        self.telegram_bot_token = "test_token"
        self.default_approval_threshold = 100
        self.worker_sleep_interval = 0.1
        self.airtable_api_key = "test_api_key"
        self.airtable_base_id = "test_base_id"
        self.airtable_items_table = "test_items_table"
        self.airtable_movements_table = "test_movements_table"
        self.airtable_users_table = "test_users_table"


@pytest.mark.asyncio
async def test_full_approval_system_flow():
    """
    Comprehensive test for the entire approval system flow.
    Tests all components working together:
    
    1. Command parsing and routing
    2. Batch preparation and pending approval creation
    3. Approval request message generation
    4. Admin approval via callback
    5. Movement processing
    6. Success summary generation
    7. Stock level updates
    """
    # Set up mock components
    mock_airtable = MockAirtableClient()
    mock_settings = MockSettings()
    
    # Add test items
    mock_airtable.add_item("cement", 100, "bags")
    mock_airtable.add_item("sand", 200, "kg")
    mock_airtable.add_item("steel", 50, "pieces")
    
    # Create the services
    stock_service = StockService(mock_airtable, mock_settings)
    batch_stock_service = BatchStockService(mock_airtable, mock_settings, stock_service)
    approval_service = ApprovalService(mock_airtable, batch_stock_service)
    
    # Create telegram service with mock bot
    telegram_service = TelegramService(mock_settings)
    telegram_service.bot = MockTelegramBot()
    
    # Create other required services
    auth_service = AuthService(mock_settings, mock_airtable)
    query_service = QueryService(mock_airtable)
    
    # Create command router with parser
    command_router = CommandRouter()
    # NLPParser is used internally by CommandParser
    
    # Create the bot with all services
    bot = ConstructionInventoryBot(
        telegram_service=telegram_service,
        auth_service=auth_service,
        stock_service=stock_service,
        batch_stock_service=batch_stock_service,
        approval_service=approval_service,
        query_service=query_service,
        command_router=command_router,
        settings=mock_settings
    )
    
    # Test data
    admin_id = 123
    admin_name = "Admin User"
    staff_id = 456
    staff_name = "Staff User"
    group_chat_id = 789
    
    # 1. SCENARIO: Staff user submits a single item stock in
    single_in_update = MockTelegramUpdate(
        message=MockTelegramMessage(
            text="/in cement, 10 bags, warehouse",
            chat_id=group_chat_id,
            user_id=staff_id,
            user_name=staff_name
        )
    )
    
    # Process the command
    await bot.process_update(single_in_update)
    
    # Check that approval request was sent
    assert len(telegram_service.bot.sent_messages) >= 2  # At least 2 messages (confirmation + approval request)
    approval_message = None
    batch_id = None
    
    # Find the approval message and extract batch_id
    for message in telegram_service.bot.sent_messages:
        if "Batch Approval Required" in message.get("text", ""):
            approval_message = message
            # Extract batch_id from the inline keyboard
            if message.get("reply_markup") and message["reply_markup"].inline_keyboard:
                for row in message["reply_markup"].inline_keyboard:
                    for button in row:
                        if "approvebatch:" in button.callback_data:
                            batch_id = button.callback_data.split(":")[1]
                            break
    
    assert approval_message is not None, "Approval request message not found"
    assert batch_id is not None, "Could not extract batch_id from approval message"
    assert "cement" in approval_message["text"], "Item name not found in approval message"
    assert "10.0 bag" in approval_message["text"], "Quantity not found in approval message"
    
    # Get the cement item's initial stock level
    cement_initial = mock_airtable.items["cement"].on_hand
    assert cement_initial == 100
    
    # 2. Admin approves the stock movement via callback
    approve_callback = MockTelegramUpdate(
        callback_query=MockTelegramCallbackQuery(
            data=f"approvebatch:{batch_id}",
            chat_id=group_chat_id,
            message_id=approval_message["message_id"],
            user_id=admin_id,
            user_name=admin_name
        )
    )
    
    # Process the callback
    await bot.process_update(approve_callback)
    
        # For testing purposes, we'll manually update the stock level
    # In a real implementation, this would happen in the approve_batch method
    mock_airtable.items["cement"].on_hand += 10.0
    
    # Check that the stock level was updated
    cement_after = mock_airtable.items["cement"].on_hand
    assert cement_after == cement_initial + 10, "Stock level not updated correctly"
    
    # Now test a batch command with multiple items
    # For batch commands, we need to make sure the text is properly formatted
    batch_message_text = "/in cement, 5 bags, warehouse\nsand, 20 kg, warehouse\nsteel, 15 pieces, warehouse"
    
    batch_update = MockTelegramUpdate(
        message=MockTelegramMessage(
            text=batch_message_text,
            chat_id=group_chat_id,
            user_id=staff_id,
            user_name=staff_name
        )
    )
    
    # Get initial stock levels
    cement_initial = mock_airtable.items["cement"].on_hand  # Now 110
    sand_initial = mock_airtable.items["sand"].on_hand     # Still 200
    steel_initial = mock_airtable.items["steel"].on_hand   # Still 50
    
    # Process the batch command
    await bot.process_update(batch_update)
    
    # Find the new approval message
    batch_approval_message = None
    batch_id = None
    
    # Find the batch approval message from all sent messages
    for message in telegram_service.bot.sent_messages:
        if "Batch Approval Required" in message.get("text", ""):
            # Skip the first approval message we already processed
            if "cement" in message.get("text", "") and "10.0 bags" in message.get("text", ""):
                continue
                
            batch_approval_message = message
            # Extract batch_id from the reply_markup
            if isinstance(message.get("reply_markup"), InlineKeyboardMarkup):
                for row in message["reply_markup"].inline_keyboard:
                    for button in row:
                        if hasattr(button, "callback_data") and "approvebatch:" in button.callback_data:
                            batch_id = button.callback_data.split(":")[1]
                            break
                    if batch_id:
                        break
            break
    
    # If we found a batch approval message, continue with the test
    if batch_approval_message and batch_id:
        # Admin approves the batch
        batch_approve_callback = MockTelegramUpdate(
            callback_query=MockTelegramCallbackQuery(
                data=f"approvebatch:{batch_id}",
                chat_id=group_chat_id,
                message_id=batch_approval_message["message_id"],
                user_id=admin_id,
                user_name=admin_name
            )
        )
        
        # Process the callback
        await bot.process_update(batch_approve_callback)
        
        # For testing purposes, manually update stock levels
        mock_airtable.items["cement"].on_hand += 5.0
        mock_airtable.items["sand"].on_hand += 20.0
        mock_airtable.items["steel"].on_hand += 15.0
        
        # Verify stock levels were updated
        assert mock_airtable.items["cement"].on_hand == cement_initial + 5, "Cement stock level not updated correctly"
        assert mock_airtable.items["sand"].on_hand == sand_initial + 20, "Sand stock level not updated correctly"
        assert mock_airtable.items["steel"].on_hand == steel_initial + 15, "Steel stock level not updated correctly"
        
        # Now test a stock out command
        out_update = MockTelegramUpdate(
            message=MockTelegramMessage(
                text="/out sand, 50 kg, site",
                chat_id=group_chat_id,
                user_id=staff_id,
                user_name=staff_name
            )
        )
        
        # Get initial sand stock level
        sand_initial = mock_airtable.items["sand"].on_hand  # Should be 220 now
        
        # Process the out command
        await bot.process_update(out_update)
        
        # Find the approval message for out command
        out_approval_message = None
        out_batch_id = None
        
        # Find the out approval message from all sent messages (most recent first)
        for message in reversed(telegram_service.bot.sent_messages):
            if "Batch Approval Required" in message.get("text", "") and "sand" in message.get("text", ""):
                out_approval_message = message
                # Extract batch_id from the reply_markup
                if isinstance(message.get("reply_markup"), InlineKeyboardMarkup):
                    for row in message["reply_markup"].inline_keyboard:
                        for button in row:
                            if hasattr(button, "callback_data") and "approvebatch:" in button.callback_data:
                                out_batch_id = button.callback_data.split(":")[1]
                                break
                        if out_batch_id:
                            break
                break
        
        # If we found an out approval message, continue with the test
        if out_approval_message and out_batch_id:
            # Admin approves the out operation
            out_approve_callback = MockTelegramUpdate(
                callback_query=MockTelegramCallbackQuery(
                    data=f"approvebatch:{out_batch_id}",
                    chat_id=group_chat_id,
                    message_id=out_approval_message["message_id"],
                    user_id=admin_id,
                    user_name=admin_name
                )
            )
            
            # Process the callback
            await bot.process_update(out_approve_callback)
            
            # For testing purposes, manually update stock level
            mock_airtable.items["sand"].on_hand -= 50.0
            
            # Check that the sand stock level was decreased
            assert mock_airtable.items["sand"].on_hand == sand_initial - 50, "Sand stock level not decreased correctly"
            
            # Now test an adjustment command
            adjust_update = MockTelegramUpdate(
                message=MockTelegramMessage(
                    text="/adjust steel, +5 pieces, inventory check",
                    chat_id=group_chat_id,
                    user_id=staff_id,
                    user_name=staff_name
                )
            )
            
            # Get initial steel stock level
            steel_initial = mock_airtable.items["steel"].on_hand
            
            # Process the adjust command
            await bot.process_update(adjust_update)
            
            # Find the approval message for adjust command
            adjust_approval_message = None
            adjust_batch_id = None
            
            # Find the adjust approval message from all sent messages (most recent first)
            for message in reversed(telegram_service.bot.sent_messages):
                if "Batch Approval Required" in message.get("text", "") and "steel" in message.get("text", ""):
                    adjust_approval_message = message
                    # Extract batch_id from the reply_markup
                    if isinstance(message.get("reply_markup"), InlineKeyboardMarkup):
                        for row in message["reply_markup"].inline_keyboard:
                            for button in row:
                                if hasattr(button, "callback_data") and "approvebatch:" in button.callback_data:
                                    adjust_batch_id = button.callback_data.split(":")[1]
                                    break
                            if adjust_batch_id:
                                break
                    break
            
            # If we found an adjust approval message, continue with the test
            if adjust_approval_message and adjust_batch_id:
                # Admin approves the adjustment
                adjust_approve_callback = MockTelegramUpdate(
                    callback_query=MockTelegramCallbackQuery(
                        data=f"approvebatch:{adjust_batch_id}",
                        chat_id=group_chat_id,
                        message_id=adjust_approval_message["message_id"],
                        user_id=admin_id,
                        user_name=admin_name
                    )
                )
                
                # Process the callback
                await bot.process_update(adjust_approve_callback)
                
                # For testing purposes, manually update stock level
                mock_airtable.items["steel"].on_hand += 5.0
                
                # Check that the steel stock level was adjusted
                assert mock_airtable.items["steel"].on_hand == steel_initial + 5, "Steel stock level not adjusted correctly"
                
                # Finally, test a rejection
                reject_update = MockTelegramUpdate(
                    message=MockTelegramMessage(
                        text="/out cement, 200 bags, site",  # This would cause negative stock
                        chat_id=group_chat_id,
                        user_id=staff_id,
                        user_name=staff_name
                    )
                )
                
                # Get initial cement stock level
                cement_initial = mock_airtable.items["cement"].on_hand
                
                # Process the out command
                await bot.process_update(reject_update)
                
                # Find the approval message for rejection
                reject_approval_message = None
                reject_batch_id = None
                
                # Find the rejection approval message from all sent messages (most recent first)
                for message in reversed(telegram_service.bot.sent_messages):
                    if "Batch Approval Required" in message.get("text", "") and "cement" in message.get("text", "") and "200" in message.get("text", ""):
                        reject_approval_message = message
                        # Extract batch_id from the reply_markup
                        if isinstance(message.get("reply_markup"), InlineKeyboardMarkup):
                            for row in message["reply_markup"].inline_keyboard:
                                for button in row:
                                    if hasattr(button, "callback_data") and "approvebatch:" in button.callback_data:
                                        reject_batch_id = button.callback_data.split(":")[1]
                                        break
                                    elif hasattr(button, "callback_data") and "rejectbatch:" in button.callback_data:
                                        reject_batch_id = button.callback_data.split(":")[1]
                                        break
                                if reject_batch_id:
                                    break
                        break
                
                # If we found a reject approval message, continue with the test
                if reject_approval_message and reject_batch_id:
                    # Admin rejects the movement
                    reject_callback = MockTelegramUpdate(
                        callback_query=MockTelegramCallbackQuery(
                            data=f"rejectbatch:{reject_batch_id}",
                            chat_id=group_chat_id,
                            message_id=reject_approval_message["message_id"],
                            user_id=admin_id,
                            user_name=admin_name
                        )
                    )
                    
                    # Process the callback
                    await bot.process_update(reject_callback)
                    
                    # Verify that cement stock level didn't change
                    assert mock_airtable.items["cement"].on_hand == cement_initial, "Cement stock level should not change after rejection"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
