"""Main background worker for the Construction Inventory Bot."""

import logging
import asyncio
import signal
import sys
from datetime import datetime, UTC
from typing import Dict, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import Settings
from .airtable_client import AirtableClient
from .auth import AuthService
from .commands import CommandRouter
from .services.stock import StockService
from .services.batch_stock import BatchStockService
from .services.approvals import ApprovalService
from .services.queries import QueryService
from .services.stock_query import StockQueryService
from .services.keyboard_management import KeyboardManagementService
from .services.command_suggestions import CommandSuggestionsService
from .services.inventory import InventoryService
from .services.idempotency import IdempotencyService
from .services.persistent_idempotency import PersistentIdempotencyService
from .services.audit_trail import AuditTrailService
from .telegram_service import TelegramService
from .health import init_health_checker
from .schemas import UserRole

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_event = asyncio.Event()


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating shutdown...")
    shutdown_event.set()


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


class ConstructionInventoryBot:
    """Main bot class for the Construction Inventory Bot."""
    
    def __init__(self):
        """Initialize the bot and all services."""
        # Load settings
        self.settings = Settings()
        
        # Configure logging with settings
        logging.getLogger().setLevel(getattr(logging, self.settings.log_level))
        
        # Initialize services with settings
        self.airtable_client = AirtableClient(self.settings)
        self.auth_service = AuthService(self.settings, self.airtable_client)
        self.command_router = CommandRouter()
        self.stock_service = StockService(self.airtable_client, self.settings)
        self.batch_stock_service = BatchStockService(self.airtable_client, self.settings, self.stock_service)
        # Initialize approval service with batch_stock_service
        self.approval_service = ApprovalService(self.airtable_client, self.batch_stock_service)
        self.query_service = QueryService(self.airtable_client)
        self.stock_query_service = StockQueryService(self.airtable_client)
        self.keyboard_management_service = KeyboardManagementService(expiry_hours=1, max_clicks_per_minute=10)
        self.command_suggestions_service = CommandSuggestionsService()
        self.idempotency_service = IdempotencyService()
        self.persistent_idempotency_service = PersistentIdempotencyService(self.airtable_client)
        self.audit_trail_service = AuditTrailService(self.airtable_client)
        self.inventory_service = InventoryService(
            self.airtable_client, 
            self.settings,
            audit_trail_service=self.audit_trail_service,
            persistent_idempotency_service=self.persistent_idempotency_service
        )
        self.telegram_service = TelegramService(self.settings)
        
        # Initialize scheduler
        self.scheduler = AsyncIOScheduler()
        
        # Bot instance for polling
        self.bot = self.telegram_service.bot
        
        # Track last update ID to avoid processing duplicates
        self.last_update_id = 0
        
        # Initialize health checker
        init_health_checker(self)
        
        # Initialize monitoring and debugging
        self.monitoring_stats = {
            'commands_processed': 0,
            'callback_queries_processed': 0,
            'errors_encountered': 0,
            'start_time': datetime.now(UTC),
            'last_cleanup': datetime.now(UTC)
        }
        
        logger.info("Construction Inventory Bot initialized successfully")
    
    async def start(self):
        """Start the bot and scheduled tasks."""
        try:
            # Start the scheduler
            self.scheduler.start()
            
            # Schedule daily report
            self.scheduler.add_job(
                self.send_daily_report,
                CronTrigger(hour=8, minute=0),  # 8:00 AM daily
                id="daily_report",
                replace_existing=True
            )
            
            # Schedule weekly backup
            self.scheduler.add_job(
                self.send_weekly_backup,
                CronTrigger(day_of_week=0, hour=9, minute=0),  # Monday 9:00 AM
                id="weekly_backup",
                replace_existing=True
            )
            
            # Schedule keyboard cleanup (every 15 minutes)
            self.scheduler.add_job(
                self.cleanup_expired_keyboards,
                CronTrigger(minute="*/15"),  # Every 15 minutes
                id="keyboard_cleanup",
                replace_existing=True
            )
            
            logger.info("Scheduled tasks started successfully")
            
            # Start polling for updates
            await self.poll_updates()
            
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise
    
    async def stop(self):
        """Stop the bot and cleanup."""
        try:
            # Stop the scheduler
            if self.scheduler.running:
                self.scheduler.shutdown()
            
            logger.info("Bot stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")
    
    async def poll_updates(self):
        """Poll Telegram for updates continuously."""
        logger.info("Starting to poll for Telegram updates...")
        
        while not shutdown_event.is_set():
            try:
                # Get updates from Telegram
                updates = await self.bot.get_updates(
                    offset=self.last_update_id + 1,
                    timeout=30,  # 30 second timeout
                    allowed_updates=["message", "callback_query"]  # Allow callback queries for buttons
                )
                
                # Process updates
                for update in updates:
                    if update.update_id > self.last_update_id:
                        await self.process_update(update)
                        self.last_update_id = update.update_id
                
                # Sleep between polling cycles
                await asyncio.sleep(self.settings.worker_sleep_interval)
                
            except Exception as e:
                logger.error(f"Error polling for updates: {e}")
                await asyncio.sleep(30)  # Wait longer on error
                
    async def process_callback_query(self, callback_query):
        """Process a callback query from inline buttons."""
        try:
            # Extract data from callback query
            data = callback_query.data
            chat_id = callback_query.message.chat.id
            user_id = callback_query.from_user.id
            first_name = callback_query.from_user.first_name or ""
            last_name = callback_query.from_user.last_name or ""
            user_name = f"{first_name} {last_name}".strip() or "Unknown"
            message_id = callback_query.message.message_id
            
            logger.info(f"Processing callback query: {data} from user {user_name} ({user_id}) in chat {chat_id}")
            
            # Check user access - use "approve" as the command for permission checking
            access_valid, access_message, user_role = await self.auth_service.validate_user_access(
                user_id, chat_id, "approve"
            )
            
            if not access_valid:
                await self.bot.answer_callback_query(
                    callback_query.id,
                    text=access_message,
                    show_alert=True
                )
                return
            
            # Handle different callback types
            if data.startswith("approve:"):
                # Handle single approval
                movement_id = data.split(":", 1)[1]
                success, message = await self.approval_service.approve_movement(
                    movement_id, user_name, user_role
                )
                
                await self.bot.answer_callback_query(
                    callback_query.id,
                    text="Approved!" if success else "Failed to approve."
                )
                
                if success:
                    # Update the original message
                    await self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"{callback_query.message.text}\n\n✅ Approved by {user_name}",
                        parse_mode='HTML'
                    )
                    await self.telegram_service.send_success_message(chat_id, message)
                else:
                    await self.telegram_service.send_error_message(chat_id, message)
                    
            elif data.startswith("void:"):
                # Handle void/cancel single approval
                movement_id = data.split(":", 1)[1]
                success, message = await self.approval_service.void_movement(
                    movement_id, user_name, user_role
                )
                
                await self.bot.answer_callback_query(
                    callback_query.id,
                    text="Voided!" if success else "Failed to void."
                )
                
                if success:
                    # Update the original message
                    await self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"{callback_query.message.text}\n\n❌ Voided by {user_name}",
                        parse_mode='HTML'
                    )
                    await self.telegram_service.send_success_message(chat_id, message)
                else:
                    await self.telegram_service.send_error_message(chat_id, message)
                
            elif data.startswith("approvebatch:"):
                # Handle batch approval
                batch_id = data.split(":", 1)[1]
                
                # Show processing message
                await self.bot.answer_callback_query(
                    callback_query.id,
                    text="Processing batch approval..."
                )
                
                # Update the original message to show processing
                try:
                    await self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"{callback_query.message.text}\n\n⏳ Processing approval by {user_name}...",
                        parse_mode='HTML',
                        reply_markup=None  # Remove buttons
                    )
                except Exception as e:
                    logger.error(f"Failed to update message: {e}")
                
                # Process the approval
                success, message, batch_result = await self.approval_service.approve_batch(
                    batch_id, user_name, user_role
                )
                
                if success:
                    # Update the original message
                    try:
                        await self.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=f"{callback_query.message.text}\n\n✅ Approved by {user_name}",
                            parse_mode='HTML'
                        )
                    except Exception as e:
                        logger.error(f"Failed to update message after approval: {e}")
                    
                    # Get batch approval details
                    batch_approval = await self.batch_stock_service.get_batch_approval(batch_id)
                    if batch_approval:
                        # Send detailed success summary
                        await self.telegram_service.send_batch_success_summary(
                            chat_id,
                            batch_id,
                            batch_approval.movements,
                            batch_approval.before_levels,
                            batch_approval.after_levels,
                            batch_approval.failed_entries
                        )
                    else:
                        await self.telegram_service.send_success_message(chat_id, message)
                else:
                    await self.telegram_service.send_error_message(chat_id, message)
            
            elif data.startswith("rejectbatch:"):
                # Handle batch rejection
                batch_id = data.split(":", 1)[1]
                
                # Show processing message
                await self.bot.answer_callback_query(
                    callback_query.id,
                    text="Rejecting batch..."
                )
                
                # Process the rejection
                success, message = await self.approval_service.reject_batch(
                    batch_id, user_name, user_role
                )
                
                if success:
                    # Update the original message
                    await self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"{callback_query.message.text}\n\n❌ Rejected by {user_name}",
                        parse_mode='HTML',
                        reply_markup=None  # Remove buttons
                    )
                    await self.telegram_service.send_message(
                        chat_id, 
                        f"⛔ <b>Batch Rejected</b>\n\nBatch ID: {batch_id} was rejected by {user_name}."
                    )
                else:
                    await self.telegram_service.send_error_message(chat_id, message)
            
            elif data.startswith("stock_item_"):
                # Handle stock item selection from inline keyboard
                await self.handle_stock_keyboard_callback(callback_query)
            
            else:
                # Unknown callback type
                await self.bot.answer_callback_query(
                    callback_query.id,
                    text="Unknown action",
                    show_alert=True
                )
                
        except Exception as e:
            logger.error(f"Error processing callback query: {e}")
            # Try to notify the user if possible
            try:
                await self.bot.answer_callback_query(
                    callback_query.id,
                    text=f"Error: {str(e)}",
                    show_alert=True
                )
            except Exception:
                pass
    
    async def process_update(self, update):
        """Process a single Telegram update."""
        try:
            # Handle callback queries from inline buttons
            if hasattr(update, 'callback_query') and update.callback_query:
                self.monitoring_stats['callback_queries_processed'] += 1
                await self.process_callback_query(update.callback_query)
                return
            
            # Extract message data
            if not hasattr(update, 'message') or update.message is None:
                return
            
            message = update.message
            chat_id = message.chat.id
            user_id = message.from_user.id
            first_name = message.from_user.first_name or ""
            last_name = message.from_user.last_name or ""
            user_name = f"{first_name} {last_name}".strip() or "Unknown"
            username = message.from_user.username or ""
            text = message.text or ""
            message_id = message.message_id
            update_id = update.update_id
            
            # Check if this is a command
            if text.startswith("/"):
                self.monitoring_stats['commands_processed'] += 1
                logger.info(f"Processing command: {text} from user {user_name} ({user_id}) in chat {chat_id}")
                
                # Fix escaped newlines in Telegram messages
                if '\\n' in text:
                    text = text.replace('\\n', '\n')
                
                # Create user if they don't exist FIRST (before permission check)
                logger.info(f"Attempting to create user {user_id} ({user_name}) if they don't exist...")
                user_created = await self.airtable_client.create_user_if_not_exists(user_id, username, user_name, chat_id=chat_id)
                logger.info(f"User creation result: {user_created}")
                
                # Now validate user access (after user creation)
                # Use command parser to get the correct command name for permission checking
                temp_command = await self.command_router.route_command(
                    text, chat_id, user_id, user_name, message_id, update_id
                )
                
                if temp_command[1]:  # If there's an error
                    await self.telegram_service.send_error_message(chat_id, temp_command[1])
                    return
                
                if not temp_command[0]:  # If no command returned
                    return
                
                command_name = temp_command[0].command
                access_valid, access_message, user_role = await self.auth_service.validate_user_access(
                    user_id, chat_id, command_name
                )
                
                if not access_valid:
                    await self.telegram_service.send_error_message(chat_id, access_message)
                    return
                
                # Execute command (already parsed during permission check)
                command = temp_command[0]
                await self.execute_command(command, chat_id, user_id, user_name, user_role)
                
            else:
                # Command-only system: ignore all non-command messages
                logger.debug(f"Ignoring non-command message: '{text}' from user {user_name} ({user_id}) in chat {chat_id}")
                return
            
        except Exception as e:
            self.monitoring_stats['errors_encountered'] += 1
            logger.error(f"Error processing update: {e}")
    
    async def execute_command(self, command, chat_id: int, user_id: int, 
                             user_name: str, user_role):
        """Execute a parsed command."""
        try:
            cmd = command.command.lower()
            args = command.args
            
            if cmd == "help":
                # Handle searchable help: /help [topic]
                search_term = args[0] if args else None
                await self.telegram_service.send_help_message(chat_id, user_role.value, search_term)
                
            elif cmd == "quickhelp":
                # Quick help for specific command: /quickhelp [command]
                if not args:
                    await self.telegram_service.send_message(
                        chat_id,
                        "📖 <b>Quick Help</b>\n\n"
                        "Get quick help for a specific command.\n\n"
                        "<b>Usage:</b>\n"
                        "/quickhelp <command_name>\n\n"
                        "<b>Examples:</b>\n"
                        "/quickhelp stock\n"
                        "/quickhelp in\n"
                        "/quickhelp batchhelp\n\n"
                        "💡 Use <code>/help</code> to see all commands."
                    )
                    return
                
                command_name = args[0].lower()
                quick_help = self.command_suggestions_service.get_quick_help(command_name)
                
                if quick_help:
                    await self.telegram_service.send_message(chat_id, quick_help)
                else:
                    # Command not found, suggest similar commands
                    suggestions = self.command_suggestions_service.get_command_suggestions(command_name)
                    if suggestions:
                        suggestions_message = self.command_suggestions_service.format_suggestions_message(command_name, suggestions)
                        await self.telegram_service.send_message(chat_id, suggestions_message)
                    else:
                        await self.telegram_service.send_error_message(
                            chat_id,
                            f"❌ <b>Command not found: /{command_name}</b>\n\n"
                            "Use <code>/help</code> to see all available commands."
                        )
                
            elif cmd == "batchhelp":
                await self.send_batch_help_message(chat_id, user_role.value)
                
            elif cmd == "status":
                await self.send_system_status_message(chat_id, user_role.value)
                
            elif cmd == "monitor":
                # Show monitoring and debugging information
                await self.send_monitoring_info(chat_id, user_role.value)
                
            elif cmd == "validate":
                if not args:
                    await self.telegram_service.send_message(
                        chat_id,
                        "ℹ️ <b>Batch Validation</b>\n\n"
                        "This command validates your batch format without processing any movements.\n\n"
                        "<b>Usage:</b>\n"
                        "/validate [movement_type] [entries...]\n\n"
                        "<b>Examples:</b>\n"
                        "/validate in cement, 5 bags; sand, 10 bags\n"
                        "/validate out cement, 5 bags\nsand, 10 bags\n\n"
                        "Use this to check your batch format before submitting."
                    )
                    return
                
                # Process the validation
                # For multi-line commands, we need to preserve the newlines
                full_text = args[0] if len(args) == 1 else " ".join(args)
                
                # Debug log
                logger.info(f"DEBUG - Processing validate command with text: '{full_text}'")
                
                await self.handle_validate_command(chat_id, user_id, user_name, full_text)
                
            elif cmd == "stock":
                if not args:
                    await self.telegram_service.send_message(
                        chat_id,
                        "🔍 <b>Stock Query</b>\n\n"
                        "This command allows you to search for items and view their stock levels.\n\n"
                        "<b>Usage:</b>\n"
                        "/stock <item_name>\n\n"
                        "<b>Examples:</b>\n"
                        "/stock cement\n"
                        "/stock m24 bolts\n"
                        "/stock safety helmets\n\n"
                        "The search will find items with similar names and show you options to choose from."
                    )
                    return
                
                # Process the stock query
                query = args[0] if len(args) == 1 else " ".join(args)
                logger.info(f"Processing stock query: '{query}' for user {user_name}")
                
                await self.handle_stock_command(chat_id, user_id, user_name, query)
                
            elif cmd == "inventory_validate":
                # Admin-only command
                if user_role != UserRole.ADMIN:
                    await self.telegram_service.send_error_message(
                        chat_id,
                        "❌ <b>Access Denied</b>\n\n"
                        "The /inventory validate command is restricted to administrators only."
                    )
                    return

                if not args:
                    await self.telegram_service.send_message(
                        chat_id,
                        "🔍 <b>Inventory Validation</b>\n\n"
                        "This command allows administrators to validate inventory commands without applying them.\n\n"
                        "<b>Usage:</b>\n"
                        "/inventory validate date:DD/MM/YY logged by: NAME1,NAME2\n"
                        "Item Name, Quantity\n"
                        "Item Name, Quantity\n\n"
                        "<b>Examples:</b>\n"
                        "/inventory validate date:25/08/25 logged by: Trevor,Kayesera\n"
                        "Cement 32.5, 50\n"
                        "12mm rebar, 120.0\n"
                        "Safety helmets, 25\n\n"
                        "<b>Notes:</b>\n"
                        "• Validates format without making changes\n"
                        "• Maximum 50 entries per batch\n"
                        "• Shows normalized dates and parsed entries\n"
                        "• Use to test before applying"
                    )
                    return

                # Process the inventory validation command
                full_text = args[0] if len(args) == 1 else " ".join(args)
                await self.handle_inventory_validate_command(chat_id, user_id, user_name, full_text)

            elif cmd == "inventory":
                # Admin-only command
                if user_role != UserRole.ADMIN:
                    await self.telegram_service.send_error_message(
                        chat_id,
                        "❌ <b>Access Denied</b>\n\n"
                        "The /inventory command is restricted to administrators only."
                    )
                    return

                if not args:
                    await self.telegram_service.send_message(
                        chat_id,
                        "📊 <b>Inventory Stocktake</b>\n\n"
                        "This command allows administrators to perform inventory stocktaking.\n\n"
                        "<b>Usage:</b>\n"
                        "/inventory date:DD/MM/YY logged by: NAME1,NAME2\n"
                        "Item Name, Quantity\n"
                        "Item Name, Quantity\n\n"
                        "<b>Examples:</b>\n"
                        "/inventory date:25/08/25 logged by: Trevor,Kayesera\n"
                        "Cement 32.5, 50\n"
                        "12mm rebar, 120.0\n"
                        "Safety helmets, 25\n\n"
                        "<b>Notes:</b>\n"
                        "• Maximum 50 entries per batch\n"
                        "• Duplicate items use last occurrence\n"
                        "• New items are created with default settings\n"
                        "• Existing items are updated to counted quantity\n"
                        "• Use /inventory validate to test first"
                    )
                    return

                # Process the inventory command
                # For multi-line commands, we need to preserve the newlines
                full_text = args[0] if len(args) == 1 else " ".join(args)

                # Check for idempotency (prevent duplicate applies) - now persistent across restarts
                if await self.persistent_idempotency_service.is_duplicate(full_text):
                    await self.telegram_service.send_error_message(
                        chat_id,
                        "⚠️ <b>Duplicate Request Detected</b>\n\n"
                        "This exact inventory command was already processed recently.\n\n"
                        "If you need to apply the same inventory again, please wait for the idempotency period to expire "
                        "or modify the command slightly (e.g., add a comment or change spacing).\n\n"
                        "💡 <b>Note:</b> This check persists across bot restarts."
                    )
                    return

                logger.info(f"Processing inventory command for user {user_name}")

                await self.handle_inventory_command(chat_id, user_id, user_name, full_text)
                
            elif cmd == "whoami":
                await self.telegram_service.send_message(
                    chat_id, 
                    f"👤 <b>User Information</b>\n\n"
                    f"<b>Name:</b> {user_name}\n"
                    f"<b>Role:</b> {user_role.value.title()}\n"
                    f"<b>User ID:</b> {user_id}"
                )
                
            elif cmd == "find":
                if not args:
                    await self.telegram_service.send_error_message(chat_id, "Please provide a search query.")
                    return
                
                success, message, items = await self.stock_service.search_items(args[0])
                if success:
                    if items:
                        text = f"🔍 <b>Search Results for '{args[0]}'</b>\n\n"
                        for item in items[:5]:  # Limit to 5 results
                            text += f"• <b>{item.name}</b>\n"
                            text += f"  Stock: {item.on_hand} {item.base_unit}\n"
                            text += f"  Location: {item.location or 'N/A'}\n\n"
                        
                        if len(items) > 5:
                            text += f"... and {len(items) - 5} more results"
                    else:
                        text = f"No items found matching '{args[0]}'"
                    
                    await self.telegram_service.send_message(chat_id, text)
                else:
                    await self.telegram_service.send_error_message(chat_id, message)
                    
            elif cmd == "onhand":
                if not args:
                    await self.telegram_service.send_error_message(chat_id, "Please provide an item name.")
                    return
                
                success, message, item = await self.stock_service.get_current_stock(args[0])
                if success:
                    await self.telegram_service.send_message(chat_id, message)
                else:
                    await self.telegram_service.send_error_message(chat_id, message)
                    
            elif cmd == "in":
                if not args:
                    help_text = "📝 <b>Stock IN Command Usage</b>\n\n"
                    help_text += "<b>Single Entry:</b>\n"
                    help_text += "/in <item>, <quantity> <unit>, [driver], [from_location], [note]\n\n"
                    help_text += "<b>Batch Entry:</b>\n"
                    help_text += "/in <item1>, <qty1> <unit1>\n"
                    help_text += "<item2>, <qty2> <unit2>\n"
                    help_text += "<item3>, <qty3> <unit3>\n\n"
                    help_text += "<b>Examples:</b>\n"
                    help_text += "• /in cement, 50 bags, delivered by John, from supplier\n"
                    help_text += "• /in cement, 50 bags\n"
                    help_text += "  steel bars, 100 pieces\n"
                    help_text += "  safety equipment, 20 sets\n\n"
                    help_text += "Use /batchhelp for detailed batch command help."
                    await self.telegram_service.send_error_message(chat_id, help_text)
                    return
                
                try:
                    # Use NLP parser for natural language
                    # For multi-line commands, we need to preserve the newlines
                    full_text = args[0] if len(args) == 1 else " ".join(args)
                    
                    # Debug log
                    logger.info(f"DEBUG - Processing batch command with text: '{full_text}'")
                    
                    # Check if this is a batch command by parsing with batch parser
                    batch_result = self.command_router.parser.nlp_parser.parse_batch_entries(
                        f"in {full_text}", user_id, user_name
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
                            
                            await self.telegram_service.send_message(
                                chat_id,
                                f"📝 <b>Entry submitted for approval</b>\n\n"
                                f"Your request to add {movement.quantity} {movement.unit} of {movement.item_name} has been submitted for admin approval.\n\n"
                                f"<b>Batch ID:</b> {batch_id}"
                            )
                        else:
                            await self.telegram_service.send_error_message(chat_id, f"Error preparing entry: {batch_id}")
                    
                    # If it's a batch, prepare for approval
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
                                f"📝 <b>Batch submitted for approval</b>\n\n"
                                f"Your batch of {batch_size} items has been submitted for admin approval.\n\n"
                                f"<b>Batch ID:</b> {batch_id}"
                            )
                        else:
                            await self.telegram_service.send_error_message(chat_id, f"Error preparing batch: {batch_id}")
                    
                    # If parsing failed
                    else:
                        error_msg = "Could not parse the command. Please use format: /in item, quantity unit, location, driver, from_location, note"
                        if batch_result.errors:
                            error_msg += f"\n\nErrors: {'; '.join(batch_result.errors)}"
                        await self.telegram_service.send_error_message(chat_id, error_msg)
                        
                except Exception as e:
                    await self.telegram_service.send_error_message(chat_id, f"Error processing command: {str(e)}")
                    
            elif cmd == "out":
                if not args:
                    help_text = "📝 <b>Stock OUT Command Usage</b>\n\n"
                    help_text += "<b>Single Entry:</b>\n"
                    help_text += "/out <item>, <quantity> <unit>, [to_location], [driver], [note]\n\n"
                    help_text += "<b>Batch Entry:</b>\n"
                    help_text += "/out <item1>, <qty1> <unit1>\n"
                    help_text += "<item2>, <qty2> <unit2>\n"
                    help_text += "<item3>, <qty3> <unit3>\n\n"
                    help_text += "<b>Examples:</b>\n"
                    help_text += "• /out cement, 25 bags, to site A, by Mr Longwe\n"
                    help_text += "• /out cement, 25 bags\n"
                    help_text += "  steel bars, 10 pieces\n"
                    help_text += "  safety equipment, 5 sets\n\n"
                    help_text += "Use /batchhelp for detailed batch command help."
                    await self.telegram_service.send_error_message(chat_id, help_text)
                    return
                
                try:
                    # Use NLP parser for natural language
                    # For multi-line commands, we need to preserve the newlines
                    full_text = args[0] if len(args) == 1 else " ".join(args)
                    
                    # Debug log
                    logger.info(f"DEBUG - Processing batch command with text: '{full_text}'")
                    
                    # Check if this is a batch command by parsing with batch parser
                    batch_result = self.command_router.parser.nlp_parser.parse_batch_entries(
                        f"out {full_text}", user_id, user_name
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
                            
                            await self.telegram_service.send_message(
                                chat_id,
                                f"📝 <b>Entry submitted for approval</b>\n\n"
                                f"Your request to remove {movement.quantity} {movement.unit} of {movement.item_name} has been submitted for admin approval.\n\n"
                                f"<b>Batch ID:</b> {batch_id}"
                            )
                        else:
                            await self.telegram_service.send_error_message(chat_id, f"Error preparing entry: {batch_id}")
                    
                    # If it's a batch, prepare for approval
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
                                f"📝 <b>Batch submitted for approval</b>\n\n"
                                f"Your batch of {batch_size} items has been submitted for admin approval.\n\n"
                                f"<b>Batch ID:</b> {batch_id}"
                            )
                        else:
                            await self.telegram_service.send_error_message(chat_id, f"Error preparing batch: {batch_id}")
                    
                    # If parsing failed
                    else:
                        error_msg = "Could not parse the command. Please use format: /out item, quantity unit, location, driver, from_location, note"
                        if batch_result.errors:
                            error_msg += f"\n\nErrors: {'; '.join(batch_result.errors)}"
                        await self.telegram_service.send_error_message(chat_id, error_msg)
                        
                except Exception as e:
                    await self.telegram_service.send_error_message(chat_id, f"Error processing command: {str(e)}")
                    
            elif cmd == "adjust":
                if user_role.value != "admin":
                    await self.telegram_service.send_error_message(chat_id, "Only administrators can adjust stock.")
                    return
                
                if not args:
                    help_text = "📝 <b>Stock ADJUST Command Usage (Admin Only)</b>\n\n"
                    help_text += "<b>Single Entry:</b>\n"
                    help_text += "/adjust <item>, <±quantity> <unit>, [location], [driver], [note]\n\n"
                    help_text += "<b>Batch Entry:</b>\n"
                    help_text += "/adjust <item1>, <±qty1> <unit1>\n"
                    help_text += "<item2>, <±qty2> <unit2>\n"
                    help_text += "<item3>, <±qty3> <unit3>\n\n"
                    help_text += "<b>Examples:</b>\n"
                    help_text += "• /adjust cement, -5 bags, warehouse, damaged\n"
                    help_text += "• /adjust cement, -5 bags\n"
                    help_text += "  steel bars, -2 pieces\n"
                    help_text += "  safety equipment, +3 sets\n\n"
                    help_text += "Use /batchhelp for detailed batch command help."
                    await self.telegram_service.send_error_message(chat_id, help_text)
                    return
                
                try:
                    # Use NLP parser for natural language
                    # For multi-line commands, we need to preserve the newlines
                    full_text = args[0] if len(args) == 1 else " ".join(args)
                    
                    # Debug log
                    logger.info(f"DEBUG - Processing batch command with text: '{full_text}'")
                    
                    # Check if this is a batch command by parsing with batch parser
                    batch_result = self.command_router.parser.nlp_parser.parse_batch_entries(
                        f"adjust {full_text}", user_id, user_name
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
                            error_msg += f"\n\nErrors: {'; '.join(batch_result.errors)}"
                        await self.telegram_service.send_error_message(chat_id, error_msg)
                        
                except Exception as e:
                    await self.telegram_service.send_error_message(chat_id, f"Error processing command: {str(e)}")
                    
            elif cmd == "approve":
                if user_role.value != "admin":
                    await self.telegram_service.send_error_message(chat_id, "Only administrators can approve movements.")
                    return
                
                if not args:
                    await self.telegram_service.send_error_message(chat_id, "Please provide a movement ID.")
                    return
                
                success, message = await self.approval_service.approve_movement(
                    args[0], user_name, user_role
                )
                
                if success:
                    await self.telegram_service.send_success_message(chat_id, message)
                else:
                    await self.telegram_service.send_error_message(chat_id, message)
                    
            elif cmd == "audit":
                success, message, low_stock = await self.stock_service.get_low_stock_items()
                if success:
                    if low_stock:
                        text = f"⚠️ <b>Low Stock Items</b>\n\n"
                        for item in low_stock[:10]:  # Limit to 10 items
                            text += f"• {item}\n"
                        
                        if len(low_stock) > 10:
                            text += f"\n... and {len(low_stock) - 10} more items"
                    else:
                        text = "✅ No items are currently below threshold."
                    
                    await self.telegram_service.send_message(chat_id, text)
                else:
                    await self.telegram_service.send_error_message(chat_id, message)
                    
            elif cmd == "export":
                if args and args[0] == "onhand":
                    success, message, csv_data = await self.query_service.export_inventory_csv()
                    if success and csv_data:
                        filename = f"inventory_export_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.csv"
                        await self.telegram_service.send_csv_export(chat_id, csv_data, filename)
                    else:
                        await self.telegram_service.send_error_message(chat_id, message)
                else:
                    await self.telegram_service.send_error_message(chat_id, "Usage: /export onhand")
                    
            else:
                # Use command suggestions service for unknown commands
                suggestions = self.command_suggestions_service.get_command_suggestions(cmd)
                if suggestions:
                    # Send helpful suggestions
                    suggestions_message = self.command_suggestions_service.format_suggestions_message(cmd, suggestions)
                    await self.telegram_service.send_message(chat_id, suggestions_message)
                else:
                    # No suggestions found, send generic help
                    help_text = f"❌ <b>Unknown Command: /{cmd}</b>\n\n"
                    help_text += "💡 <b>Available Commands:</b>\n"
                    help_text += "• <b>/help</b> - Show all commands\n"
                    help_text += "• <b>/help [topic]</b> - Search commands by topic\n"
                    help_text += "• <b>/stock [item]</b> - Search inventory\n"
                    help_text += "• <b>/in [item, qty unit]</b> - Add stock\n"
                    help_text += "• <b>/out [item, qty unit]</b> - Remove stock\n\n"
                    help_text += "Use <code>/help</code> to see all available commands."
                    await self.telegram_service.send_error_message(chat_id, help_text)
                
        except Exception as e:
            logger.error(f"Error executing command {command.command}: {e}")
            await self.telegram_service.send_error_message(chat_id, "An error occurred while processing your command.")
    
    async def send_batch_result_message(self, chat_id: int, batch_result):
        """Send a comprehensive batch processing result message."""
        from .schemas import BatchErrorType
        from .utils.error_handling import ErrorHandler
        
        # Send summary message
        await self.telegram_service.send_message(chat_id, batch_result.summary_message)
        
        # If there are errors, send detailed error information
        if batch_result.errors:
            # Use ErrorHandler to format errors
            error_text = "📋 <b>Detailed Error Report:</b>\n\n"
            error_text += ErrorHandler.format_batch_errors_summary(batch_result.errors)
            
            # Add recovery suggestions if there are multiple errors
            if len(batch_result.errors) > 1:
                error_text += "\n<b>Recovery Suggestions:</b>\n"
                error_text += ErrorHandler.get_recovery_suggestion(batch_result.errors)
            
            await self.telegram_service.send_message(chat_id, error_text)
        
        # Send processing statistics with enhanced information
        stats_text = f"📊 <b>Processing Statistics:</b>\n\n"
        
        # Include global parameters if available
        if hasattr(batch_result, 'global_parameters') and batch_result.global_parameters:
            stats_text += f"<b>Global Parameters:</b>\n"
            for param_name, param_value in batch_result.global_parameters.items():
                stats_text += f"• <b>{param_name.title()}:</b> {param_value}\n"
            stats_text += "\n"
        
        stats_text += f"• Total Entries: {batch_result.total_entries}\n"
        stats_text += f"• Successful: {batch_result.successful_entries}\n"
        stats_text += f"• Failed: {batch_result.failed_entries}\n"
        stats_text += f"• Success Rate: {batch_result.success_rate:.1f}%\n"
        
        if batch_result.processing_time_seconds:
            # Add performance assessment
            time_per_entry = batch_result.processing_time_seconds / batch_result.total_entries if batch_result.total_entries > 0 else 0
            stats_text += f"• Processing Time: {batch_result.processing_time_seconds:.2f}s"
            stats_text += f" ({time_per_entry:.2f}s per entry)\n"
            
            # Add performance assessment
            if time_per_entry < 0.5:
                stats_text += "• Performance: ⚡ Excellent\n"
            elif time_per_entry < 1.0:
                stats_text += "• Performance: ✅ Good\n"
            elif time_per_entry < 2.0:
                stats_text += "• Performance: ⚠️ Fair\n"
            else:
                stats_text += "• Performance: ❌ Slow\n"
        
        if batch_result.rollback_performed:
            stats_text += f"• ⚠️ Rollback Performed: Yes\n"
        
        # Add next steps guidance
        if batch_result.failed_entries > 0:
            stats_text += "\n<b>Next Steps:</b>\n"
            if batch_result.rollback_performed:
                stats_text += "• Try processing smaller batches\n"
                stats_text += "• Fix the critical errors and try again\n"
            elif batch_result.failed_entries < batch_result.total_entries / 2:
                stats_text += "• Review errors and fix the failed entries\n"
                stats_text += "• Try resubmitting just the failed entries\n"
            else:
                stats_text += "• Check your input format and try again\n"
                stats_text += "• Use /batchhelp for guidance on correct formats\n"
        
        await self.telegram_service.send_message(chat_id, stats_text)
    
    async def handle_validate_command(self, chat_id: int, user_id: int, user_name: str, command_text: str):
        """Handle /validate command to check batch format without processing."""
        # Determine movement type from the command text
        movement_type = None
        
        # Extract movement type from the beginning of the command
        if command_text.lower().startswith("in ") or command_text.lower().startswith("/in "):
            movement_type = "IN"
            # Remove the movement type prefix
            if command_text.lower().startswith("/in "):
                command_text = command_text[4:].strip()
            else:
                command_text = command_text[3:].strip()
        elif command_text.lower().startswith("out ") or command_text.lower().startswith("/out "):
            movement_type = "OUT"
            # Remove the movement type prefix
            if command_text.lower().startswith("/out "):
                command_text = command_text[5:].strip()
            else:
                command_text = command_text[4:].strip()
        elif command_text.lower().startswith("adjust ") or command_text.lower().startswith("/adjust "):
            movement_type = "ADJUST"
            # Remove the movement type prefix
            if command_text.lower().startswith("/adjust "):
                command_text = command_text[8:].strip()
            else:
                command_text = command_text[7:].strip()
        
        # If movement type not found, try to infer from the first word
        if not movement_type:
            first_word = command_text.split()[0].lower() if command_text.split() else ""
            if first_word in ["in", "/in"]:
                movement_type = "IN"
                # Remove the movement type from the command text
                command_text = command_text[len(first_word):].strip()
            elif first_word in ["out", "/out"]:
                movement_type = "OUT"
                command_text = command_text[len(first_word):].strip()
            elif first_word in ["adjust", "/adjust"]:
                movement_type = "ADJUST"
                command_text = command_text[len(first_word):].strip()
        
        # If still no movement type, send error
        if not movement_type:
            await self.telegram_service.send_message(
                chat_id,
                "❌ <b>Invalid Format</b>\n\n"
                "Could not determine movement type. Please start with IN, OUT, or ADJUST.\n\n"
                "Example: /validate in cement, 5 bags"
            )
            return
        
        # Prepare the command for parsing
        parse_text = f"{movement_type.lower()} {command_text}"
        
        # Parse the batch
        batch_result = self.command_router.parser.nlp_parser.parse_batch_entries(
            parse_text, user_id, user_name
        )
        
        # Generate validation report with enhanced error handling
        validation_text = f"🔍 <b>Batch Validation Report</b>\n\n"
        validation_text += f"• <b>Movement Type:</b> {movement_type}\n"
        validation_text += f"• <b>Format:</b> {batch_result.format.value.title()}\n"
        validation_text += f"• <b>Total Entries:</b> {batch_result.total_entries}\n"
        validation_text += f"• <b>Valid Entries:</b> {batch_result.valid_entries}\n"
        validation_text += f"• <b>Status:</b> {'✅ Valid' if batch_result.is_valid else '❌ Invalid'}\n"
        
        # Add global parameters if present
        if batch_result.global_parameters:
            validation_text += f"\n<b>Global Parameters:</b>\n"
            for param_name, param_value in batch_result.global_parameters.items():
                validation_text += f"• <b>{param_name.title()}:</b> {param_value}\n"
            validation_text += f"<i>These parameters will be applied to all entries unless overridden.</i>\n"
        else:
            # Remind about project parameter if not present
            validation_text += f"\n<b>⚠️ No Global Parameters:</b>\n"
            validation_text += f"• Remember that project is required for all entries.\n"
            validation_text += f"• Consider using 'project:' as a global parameter.\n"
        validation_text += "\n"
        
        # Add details about entries
        if batch_result.movements:
            validation_text += "<b>Parsed Entries:</b>\n"
            for i, movement in enumerate(batch_result.movements[:5]):
                validation_text += f"{i+1}. {movement.item_name}: {movement.quantity} {movement.unit}"
                if movement.location:
                    validation_text += f" at {movement.location}"
                if movement.driver_name:
                    validation_text += f", by {movement.driver_name}"
                if movement.from_location:
                    validation_text += f", from {movement.from_location}"
                if movement.to_location:
                    validation_text += f", to {movement.to_location}"
                if movement.project:
                    validation_text += f", project: {movement.project}"
                if movement.note:
                    validation_text += f" ({movement.note})"
                validation_text += "\n"
            
            if len(batch_result.movements) > 5:
                validation_text += f"... and {len(batch_result.movements) - 5} more entries\n"
            
            validation_text += "\n"
        
        # Add errors if any
        if batch_result.errors:
            from .utils.error_handling import ErrorHandler
            
            validation_text += "<b>Errors:</b>\n"
            for i, error in enumerate(batch_result.errors[:5]):
                validation_text += f"• {error}\n"
            
            if len(batch_result.errors) > 5:
                validation_text += f"... and {len(batch_result.errors) - 5} more errors\n"
            
            # Add recovery suggestions if there are multiple errors
            if len(batch_result.errors) > 1:
                # Create BatchError objects for the ErrorHandler
                from .schemas import BatchError, BatchErrorType
                batch_errors = [
                    BatchError(
                        error_type=BatchErrorType.PARSING,
                        message=error,
                        suggestion="Check format",
                        severity="ERROR"
                    ) for error in batch_result.errors
                ]
                
                validation_text += "\n<b>Suggestions:</b>\n"
                validation_text += ErrorHandler.get_recovery_suggestion(batch_errors)
                validation_text += "\n"
        
        # Add next steps guidance
        validation_text += "\n<b>Next Steps:</b>\n"
        if batch_result.is_valid:
            validation_text += "✅ Your batch format is valid! You can now use:\n"
            validation_text += f"/{movement_type.lower()} {command_text}\n"
            validation_text += "to process this batch."
        else:
            validation_text += "❌ Please fix the errors and try again.\n"
            validation_text += "Use /batchhelp for guidance on correct formats."
        
        await self.telegram_service.send_message(chat_id, validation_text)

    async def handle_stock_command(self, chat_id: int, user_id: int, user_name: str, query: str):
        """Handle /stock command for querying item stock levels."""
        try:
            logger.info(f"Processing stock query: '{query}' for user {user_name}")
            
            # Perform fuzzy search
            search_results = await self.stock_query_service.fuzzy_search_items(query, limit=5)
            
            if not search_results:
                # No results found
                await self.telegram_service.send_message(
                    chat_id,
                    f"🔍 <b>Stock Query Results</b>\n\n"
                    f"<b>Search:</b> {query}\n\n"
                    f"❌ <b>No items found</b>\n\n"
                    f"<i>Try searching with different keywords or check the spelling.</i>"
                )
                return
            
            # Collect pending information for each item
            pending_info = {}
            for item in search_results:
                pending_movements = await self.stock_query_service.get_pending_movements(item.name)
                in_pending_batch = await self.stock_query_service.is_in_pending_batch(item.name)
                
                pending_info[item.name] = {
                    'pending_movements': len(pending_movements),
                    'in_pending_batch': in_pending_batch
                }
            
            # Get total count of matching items for "Showing top 3 of X" message
            total_count = await self.stock_query_service.get_total_matching_items_count(query)
            
            # Send search results
            await self.telegram_service.send_stock_search_results(
                chat_id, query, search_results, pending_info, total_count
            )
            
            # Store search results for user confirmation
            # We'll store this in a simple in-memory cache for now
            # In production, this could be stored in Redis or database
            if not hasattr(self, '_stock_search_cache'):
                self._stock_search_cache = {}
            
            # Store results with timestamp and user info
            cache_key = f"{chat_id}_{user_id}"
            self._stock_search_cache[cache_key] = {
                'query': query,
                'results': search_results,
                'pending_info': pending_info,
                'timestamp': datetime.now(),
                'user_name': user_name
            }
            
            # Debug logging
            logger.info(f"Stored stock search cache for key: {cache_key}")
            logger.info(f"Cache now contains {len(self._stock_search_cache)} entries")
            logger.info(f"Cache keys: {list(self._stock_search_cache.keys())}")
            
            # Clean up old cache entries (older than 1 hour)
            self._cleanup_stock_search_cache()
            
        except Exception as e:
            logger.error(f"Error handling stock command: {e}")
            error_text = (
                "❌ <b>Stock Query Error</b>\n\n"
                f"An error occurred while processing your stock query: {str(e)}\n\n"
                "Please try again or contact support if the problem persists."
            )
            await self.telegram_service.send_message(chat_id, error_text)

    def _cleanup_stock_search_cache(self):
        """Clean up old stock search cache entries."""
        try:
            if not hasattr(self, '_stock_search_cache'):
                return
            
            current_time = datetime.now()
            keys_to_remove = []
            
            for cache_key, cache_data in self._stock_search_cache.items():
                # Remove entries older than 1 hour
                if (current_time - cache_data['timestamp']).total_seconds() > 3600:
                    keys_to_remove.append(cache_key)
            
            for key in keys_to_remove:
                del self._stock_search_cache[key]
                
            if keys_to_remove:
                logger.info(f"Cleaned up {len(keys_to_remove)} old stock search cache entries")
                
        except Exception as e:
            logger.error(f"Error cleaning up stock search cache: {e}")

    async def handle_stock_confirmation(self, chat_id: int, user_id: int, user_name: str, confirmation: str):
        """Handle user confirmation of stock item selection."""
        try:
            logger.info(f"Processing stock confirmation: '{confirmation}' for user {user_name}")
            
            # Get cached search results
            cache_key = f"{chat_id}_{user_id}"
            if not hasattr(self, '_stock_search_cache') or cache_key not in self._stock_search_cache:
                await self.telegram_service.send_message(
                    chat_id,
                    "❌ <b>No Recent Search</b>\n\n"
                    "Please perform a stock search first using /stock <item_name>"
                )
                return
            
            cache_data = self._stock_search_cache[cache_key]
            search_results = cache_data['results']
            pending_info = cache_data['pending_info']
            
            # Parse confirmation (could be number or exact name)
            selected_item = None
            
            # Try to parse as number first
            try:
                item_number = int(confirmation)
                if 1 <= item_number <= len(search_results):
                    selected_item = search_results[item_number - 1]  # Convert to 0-based index
                    logger.info(f"User selected item {item_number}: {selected_item.name}")
                else:
                    await self.telegram_service.send_message(
                        chat_id,
                        f"❌ <b>Invalid Selection</b>\n\n"
                        f"Please select a number between 1 and {len(search_results)}"
                    )
                    return
            except ValueError:
                # Not a number, try to find by exact name
                confirmation_lower = confirmation.lower().strip()
                for item in search_results:
                    if item.name.lower() == confirmation_lower:
                        selected_item = item
                        logger.info(f"User confirmed item by name: {item.name}")
                        break
                
                if not selected_item:
                    # Try fuzzy matching for close names
                    for item in search_results:
                        if confirmation_lower in item.name.lower() or item.name.lower() in confirmation_lower:
                            selected_item = item
                            logger.info(f"User confirmed item by partial name match: {item.name}")
                            break
                    
                    if not selected_item:
                        await self.telegram_service.send_message(
                            chat_id,
                            f"❌ <b>Item Not Found</b>\n\n"
                            f"Could not find an item matching '{confirmation}' in your recent search results.\n\n"
                            f"<b>Available options:</b>\n" + 
                            "\n".join([f"{i+1}. {item.name}" for i, item in enumerate(search_results)])
                        )
                        return
            
            # Get detailed information for the selected item
            pending_movements = await self.stock_query_service.get_pending_movements(selected_item.name)
            in_pending_batch = await self.stock_query_service.is_in_pending_batch(selected_item.name)
            
            # Send detailed item information
            await self.telegram_service.send_item_details(
                chat_id, selected_item, pending_movements, in_pending_batch
            )
            
            # Clear the cache for this user
            del self._stock_search_cache[cache_key]
            
        except Exception as e:
            logger.error(f"Error handling stock confirmation: {e}")
            error_text = (
                "❌ <b>Stock Confirmation Error</b>\n\n"
                f"An error occurred while processing your confirmation: {str(e)}\n\n"
                "Please try again or contact support if the problem persists."
            )
            await self.telegram_service.send_message(chat_id, error_text)

    async def handle_inventory_validate_command(self, chat_id: int, user_id: int, user_name: str, command_text: str):
        """Handle /inventory validate command for validation only."""
        try:
            logger.info(f"Processing inventory validation: '{command_text}' for user {user_name}")

            # Process the inventory command in validate-only mode
            success, message = await self.inventory_service.process_inventory_stocktake(
                command_text, user_id, user_name, validate_only=True
            )

            if success:
                await self.telegram_service.send_message(chat_id, message)
            else:
                await self.telegram_service.send_error_message(chat_id, message)

        except Exception as e:
            logger.error(f"Error handling inventory validation: {e}")
            error_text = (
                "❌ <b>Inventory Validation Error</b>\n\n"
                f"An error occurred while validating your inventory command: {str(e)}\n\n"
                "Please try again or contact support if the problem persists."
            )
            await self.telegram_service.send_message(chat_id, error_text)

    async def handle_inventory_command(self, chat_id: int, user_id: int, user_name: str, command_text: str):
        """Handle /inventory command for stocktaking."""
        try:
            logger.info(f"Processing inventory command: '{command_text}' for user {user_name}")
            
            # Process the inventory command using the inventory service
            success, message = await self.inventory_service.process_inventory_stocktake(
                command_text, user_id, user_name
            )
            
            if success:
                # Store persistent idempotency key to prevent duplicates across restarts
                await self.persistent_idempotency_service.store_key(command_text)
                await self.telegram_service.send_message(chat_id, message)
            else:
                await self.telegram_service.send_error_message(chat_id, message)
                
        except Exception as e:
            logger.error(f"Error handling inventory command: {e}")
            error_text = (
                "❌ <b>Inventory Command Error</b>\n\n"
                f"An error occurred while processing your inventory command: {str(e)}\n\n"
                "Please try again or contact support if the problem persists."
            )
            await self.telegram_service.send_message(chat_id, error_text)

    async def send_batch_help_message(self, chat_id: int, user_role: str):
        """Send concise help message for batch commands."""
        text = "📦 <b>BATCH COMMAND GUIDE</b>\n\n"
        
        # Quick reference section
        text += "📝 <b>QUICK REFERENCE</b>\n"
        text += "• Required format: <i>/command item, qty unit, [details]</i>\n"
        text += "• Project field is <b>required</b> (use global parameter)\n"
        text += "• Max 15 entries per batch\n"
        text += "• Use /validate to test your format first\n\n"
        
        # Global parameters - most important feature
        text += "🔑 <b>GLOBAL PARAMETERS</b> (recommended)\n"
        text += "Add at the beginning of your command:\n"
        text += "<code>driver: name, from: location, to: location, project: name</code>\n\n"
        text += "<i>Example:</i>\n"
        text += "/in <b>project: Bridge, driver: Mr Longwe</b>\n"
        text += "cement, 50 bags\n"
        text += "steel bars, 100 pieces\n\n"
        
        # Format options - simplified
        text += "📋 <b>FORMAT OPTIONS</b>\n"
        text += "1️⃣ <b>Newline</b> (most readable):\n"
        text += "<code>/in project: Site A\n"
        text += "cement, 50 bags\n"
        text += "steel bars, 10 pieces</code>\n\n"
        
        text += "2️⃣ <b>Semicolon</b> (compact):\n"
        text += "<code>/in project: Site A\n"
        text += "cement, 50 bags; steel bars, 10 pieces</code>\n\n"
        
        # Common examples - the most useful part
        text += "🔍 <b>EXAMPLES</b>\n"
        
        text += "🟢 <b>Stock IN</b>:\n"
        text += "<code>/in driver: Mr Longwe, project: Bridge\n"
        text += "cement, 50 bags\n"
        text += "steel bars, 100 pieces</code>\n\n"
        
        text += "🔴 <b>Stock OUT</b>:\n"
        text += "<code>/out to: Site A, project: Road\n"
        text += "cement, 25 bags\n"
        text += "steel bars, 10 pieces</code>\n\n"
        
        # Tips section - concise and helpful
        text += "💡 <b>TIPS</b>\n"
        text += "• Override globals in specific entries\n"
        text += "  <code>cement, 50 bags, by Mr Smith</code>\n"
        text += "• Use /validate to check format\n"
        text += "• Command prefix only needed on first line\n\n"
        
        text += "Need more details? Use /status for feature overview."
        
        await self.telegram_service.send_message(chat_id, text)
    
    async def send_system_status_message(self, chat_id: int, user_role: str):
        """Send system status and batch processing information."""
        text = "🔍 <b>SYSTEM STATUS</b>\n\n"
        
        # System status - simple traffic light system
        text += "🟢 <b>Bot:</b> Online\n"
        text += "🟢 <b>Database:</b> Connected\n"
        text += "🟢 <b>Batch Processing:</b> Available\n\n"
        
        # Key features - organized by importance
        text += "✨ <b>KEY FEATURES</b>\n"
        text += "• <b>Global Parameters</b> - Set common values once\n"
        text += "• <b>Multiple Formats</b> - Newlines, semicolons, mixed\n"
        text += "• <b>Project Tracking</b> - Required for all movements\n"
        text += "• <b>Validation</b> - Test formats before processing\n\n"
        
        # Movement types - simplified
        text += "📋 <b>MOVEMENT TYPES</b>\n"
        text += "• 🟢 <b>/in</b> - Stock receiving\n"
        text += "• 🔴 <b>/out</b> - Stock issuing\n"
        text += "• 🟡 <b>/adjust</b> - Stock corrections (admin)\n\n"
        
        # Quick command reference
        text += "⚡ <b>QUICK COMMANDS</b>\n"
        text += "• <b>/help</b> - General commands\n"
        text += "• <b>/batchhelp</b> - Batch command guide\n"
        text += "• <b>/validate</b> - Test batch format\n"
        text += "• <b>/whoami</b> - Your user info\n\n"
        
        # Tips section
        text += "💡 <b>PRO TIP</b>\n"
        text += "Always include <b>project:</b> in your commands.\n"
        text += "Example: <code>/in project: Bridge, cement, 50 bags</code>"
        
        await self.telegram_service.send_message(chat_id, text)
    
    async def send_daily_report(self):
        """Send daily inventory report to all allowed chats."""
        try:
            logger.info("Sending daily report")
            
            # Generate daily report
            report = await self.query_service.generate_daily_report()
            report_data = report.dict()
            
            # Send to all allowed chats if specified, otherwise log that no specific chats are configured
            if self.settings.telegram_allowed_chat_ids:
                for chat_id in self.settings.telegram_allowed_chat_ids:
                    await self.telegram_service.send_daily_report(chat_id, report_data)
                logger.info("Daily report sent successfully to configured chats")
            else:
                logger.info("No specific chat IDs configured for daily reports - bot will respond to commands in any chat")
                
        except Exception as e:
            logger.error(f"Error sending daily report: {e}")
    
    async def send_weekly_backup(self):
        """Send weekly backup report to all allowed chats."""
        try:
            logger.info("Sending weekly backup")
            
            # Generate inventory summary
            summary = await self.query_service.get_inventory_summary()
            
            # Send to all allowed chats if specified, otherwise log that no specific chats are configured
            if self.settings.telegram_allowed_chat_ids:
                for chat_id in self.settings.telegram_allowed_chat_ids:
                    await self.telegram_service.send_message(
                        chat_id,
                        f"📊 <b>Weekly Inventory Summary</b>\n\n"
                        f"<b>Low Stock Items:</b> {summary['low_stock_count']}\n"
                        f"<b>Pending Approvals:</b> {summary['pending_approvals']}\n"
                        f"<b>Last Updated:</b> {summary['last_updated']}"
                    )
                logger.info("Weekly backup sent successfully to configured chats")
            else:
                logger.info("No specific chat IDs configured for weekly backups - bot will respond to commands in any chat")
                
        except Exception as e:
            logger.error(f"Error sending weekly backup: {e}")
    
    async def handle_stock_keyboard_callback(self, callback_query):
        """Handle inline keyboard callbacks for stock item selection with smart management."""
        try:
            # Extract callback data
            callback_data = callback_query.data
            user_id = callback_query.from_user.id
            chat_id = callback_query.message.chat.id
            
            logger.info(f"Processing stock keyboard callback: {callback_data} from user {user_id}")
            
            # Parse callback data: "stock_item_{index}_{item_name_slug}"
            if not callback_data.startswith("stock_item_"):
                await self.telegram_service.answer_callback_query(
                    callback_query.id, 
                    "❌ Invalid callback data"
                )
                return
            
            try:
                # Parse callback data: "stock_item_{index}_{item_name_slug}"
                # The item_name_slug may contain underscores, so we need to be careful
                if not callback_data.startswith("stock_item_"):
                    raise ValueError("Invalid callback data format")
                
                # Remove "stock_item_" prefix
                remaining = callback_data[11:]  # len("stock_item_") = 11
                
                # Find the first underscore after the prefix
                underscore_pos = remaining.find("_")
                if underscore_pos == -1:
                    raise ValueError("Invalid callback data format")
                
                # Extract index and item name slug
                item_index = int(remaining[:underscore_pos]) - 1  # Convert to 0-based index
                item_name_slug = remaining[underscore_pos + 1:]
                
                # Debug logging
                logger.info(f"Parsed callback data: index={item_index}, item_name_slug='{item_name_slug}'")
                
                # Validate item_index is a number
                if item_index < 0:
                    raise ValueError("Invalid item index")
                
            except (ValueError, IndexError):
                await self.telegram_service.answer_callback_query(
                    callback_query.id, 
                    "❌ Invalid callback data format"
                )
                return
            
            # Temporarily bypass rate limiting for stock queries to test functionality
            # TODO: Implement proper rate limiting for stock queries
            logger.info(f"Bypassing rate limiting for stock query callback")
            
            # Get cached search results
            cache_key = f"{chat_id}_{user_id}"
            logger.info(f"Looking for cache key: {cache_key}")
            logger.info(f"Cache exists: {hasattr(self, '_stock_search_cache')}")
            if hasattr(self, '_stock_search_cache'):
                logger.info(f"Cache contains {len(self._stock_search_cache)} entries")
                logger.info(f"Cache keys: {list(self._stock_search_cache.keys())}")
            
            if not hasattr(self, '_stock_search_cache') or cache_key not in self._stock_search_cache:
                await self.telegram_service.answer_callback_query(
                    callback_query.id, 
                    "❌ No recent search found. Please search again."
                )
                return
            
            cache_data = self._stock_search_cache[cache_key]
            search_results = cache_data['results']
            pending_info = cache_data['pending_info']
            
            logger.info(f"Cache data retrieved: {len(search_results)} results, pending_info: {pending_info}")
            logger.info(f"Item index requested: {item_index}, available items: {[item.name for item in search_results]}")
            
            # Validate item index
            if item_index < 0 or item_index >= len(search_results):
                await self.telegram_service.answer_callback_query(
                    callback_query.id, 
                    "❌ Invalid item selection"
                )
                return
            
            # Get selected item
            selected_item = search_results[item_index]
            logger.info(f"Selected item: {selected_item.name}")
            
            # Get pending movements and batch status for the selected item
            logger.info(f"Getting pending movements for item: {selected_item.name}")
            pending_movements = await self.stock_query_service.get_pending_movements(selected_item.name)
            logger.info(f"Found {len(pending_movements)} pending movements")
            
            logger.info(f"Checking if item is in pending batch: {selected_item.name}")
            in_pending_batch = await self.stock_query_service.is_in_pending_batch(selected_item.name)
            logger.info(f"Item in pending batch: {in_pending_batch}")
            
            # Send detailed item information
            await self.telegram_service.send_item_details(
                chat_id, selected_item, pending_movements, in_pending_batch
            )
            
            # Answer callback query to remove loading state
            await self.telegram_service.answer_callback_query(
                callback_query.id, 
                f"✅ Showing details for {selected_item.name}"
            )
            
            logger.info(f"Successfully processed keyboard callback for item: {selected_item.name}")
            
        except Exception as e:
            logger.error(f"Error handling stock keyboard callback: {e}")
            try:
                await self.telegram_service.answer_callback_query(
                    callback_query.id, 
                    "❌ Error processing selection. Please try again."
                )
            except:
                pass  # Ignore errors in error handling
    
    async def cleanup_expired_keyboards(self):
        """Clean up expired keyboards (scheduled task)."""
        try:
            cleaned_count = self.keyboard_management_service.cleanup_expired_keyboards()
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired keyboards")
            
            # Log keyboard statistics periodically
            stats = self.keyboard_management_service.get_keyboard_stats()
            if stats:
                logger.debug(f"Keyboard stats: {stats['active_keyboards']} active, {stats['expired_keyboards']} expired")
            
            # Update monitoring stats
            self.monitoring_stats['last_cleanup'] = datetime.now(UTC)
                
        except Exception as e:
            logger.error(f"Error cleaning up expired keyboards: {e}")
    
    async def send_monitoring_info(self, chat_id: int, user_role: str):
        """Send monitoring and debugging information."""
        try:
            if user_role not in ["admin", "staff"]:
                await self.telegram_service.send_error_message(
                    chat_id, 
                    "❌ <b>Access Denied</b>\n\nOnly staff and admin users can access monitoring information."
                )
                return
            
            # Get current time
            current_time = datetime.now(UTC)
            uptime = current_time - self.monitoring_stats['start_time']
            
            # Get keyboard management stats
            keyboard_stats = self.keyboard_management_service.get_keyboard_stats()
            
            # Build monitoring message
            text = "📊 <b>SYSTEM MONITORING</b>\n\n"
            
            # System status
            text += "🖥️ <b>System Status</b>\n"
            text += f"• Uptime: {uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds % 3600) // 60}m\n"
            text += f"• Last cleanup: {self.monitoring_stats['last_cleanup'].strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
            
            # Activity statistics
            text += "📈 <b>Activity Statistics</b>\n"
            text += f"• Commands processed: {self.monitoring_stats['commands_processed']}\n"
            text += f"• Callback queries: {self.monitoring_stats['callback_queries_processed']}\n"
            text += f"• Errors encountered: {self.monitoring_stats['errors_encountered']}\n\n"
            
            # Keyboard management stats
            if keyboard_stats:
                text += "⌨️ <b>Keyboard Management</b>\n"
                text += f"• Active keyboards: {keyboard_stats.get('active_keyboards', 0)}\n"
                text += f"• Expired keyboards: {keyboard_stats.get('expired_keyboards', 0)}\n"
                text += f"• Total keyboards: {keyboard_stats.get('total_keyboards', 0)}\n\n"
            
            # Performance metrics
            text += "⚡ <b>Performance Metrics</b>\n"
            text += f"• Commands per hour: {self.monitoring_stats['commands_processed'] / max(uptime.total_seconds() / 3600, 1):.1f}\n"
            text += f"• Error rate: {(self.monitoring_stats['errors_encountered'] / max(self.monitoring_stats['commands_processed'], 1)) * 100:.2f}%\n\n"
            
            # Health status
            text += "💚 <b>Health Status</b>\n"
            error_rate = (self.monitoring_stats['errors_encountered'] / max(self.monitoring_stats['commands_processed'], 1)) * 100
            if error_rate < 1:
                text += "• System: 🟢 Healthy\n"
            elif error_rate < 5:
                text += "• System: 🟡 Warning\n"
            else:
                text += "• System: 🔴 Critical\n"
            
            text += "💡 <b>Useful Commands:</b>\n"
            text += "• <code>/status</code> - System features\n"
            text += "• <code>/help</code> - Available commands\n"
            text += "• <code>/monitor</code> - This monitoring info"
            
            await self.telegram_service.send_message(chat_id, text)
            
        except Exception as e:
            logger.error(f"Error sending monitoring info: {e}")
            await self.telegram_service.send_error_message(
                chat_id, 
                f"❌ <b>Error</b>\n\nFailed to retrieve monitoring information: {str(e)}"
            )


async def main():
    """Main entry point for the background worker."""
    bot = ConstructionInventoryBot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        await bot.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
