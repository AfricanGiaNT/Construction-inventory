"""Telegram integration for the Construction Inventory Bot."""

import logging
from typing import List, Optional, Dict, Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.error import TelegramError

from schemas import StockMovement, MovementType, Item

# Settings will be passed in constructor

logger = logging.getLogger(__name__)


class TelegramService:
    """Service for Telegram bot operations."""
    
    def __init__(self, settings):
        """Initialize the Telegram service."""
        self.bot = Bot(token=settings.telegram_bot_token)
    
    async def send_message(self, chat_id: int, text: str, 
                          reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool:
        """Send a message to a Telegram chat."""
        try:
            # Try with HTML parse mode first
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                return True
            except TelegramError as html_error:
                # If HTML parsing fails, try without parse mode
                if "Can't parse entities" in str(html_error):
                    logger.warning(f"HTML parsing failed, sending without parse mode: {html_error}")
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        reply_markup=reply_markup,
                        parse_mode=None
                    )
                    return True
                else:
                    raise html_error
        except TelegramError as e:
            logger.error(f"Error sending message to {chat_id}: {e}")
            return False
    
    async def send_approval_request(self, chat_id: int, movement_id: str, 
                                  sku: str, quantity: float, unit: str, 
                                  user_name: str) -> bool:
        """Send an approval request with inline keyboard."""
        try:
            text = (
                f"🔔 <b>Approval Required</b>\n\n"
                f"<b>Item:</b> {sku}\n"
                f"<b>Quantity:</b> {quantity} {unit}\n"
                f"<b>Requested by:</b> {user_name}\n"
                f"<b>Movement ID:</b> {movement_id}\n\n"
                f"Please approve or void this request."
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve:{movement_id}"),
                    InlineKeyboardButton("❌ Void", callback_data=f"void:{movement_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            return await self.send_message(chat_id, text, reply_markup)
            
        except Exception as e:
            logger.error(f"Error sending approval request: {e}")
            return False
    
    async def send_batch_approval_request(self, chat_id: int, batch_id: str, 
                                        movements: List[StockMovement],
                                        before_levels: Dict[str, float],
                                        user_name: str) -> bool:
        """
        Send a batch approval request with inline keyboard.
        
        Args:
            chat_id: Telegram chat ID to send the message to
            batch_id: Unique identifier for the batch
            movements: List of movements in the batch
            before_levels: Dictionary of current stock levels
            user_name: Name of the user who requested the batch
            
        Returns:
            Boolean indicating success or failure
        """
        try:
            # Create summary text
            text = (
                f"🔔 <b>Batch Approval Required</b>\n\n"
                f"<b>Requested by:</b> {user_name}\n"
                f"<b>Batch ID:</b> {batch_id}\n"
                f"<b>Items to process:</b> {len(movements)}\n\n"
                f"<b>Items:</b>\n"
            )
            
            # Add item summary, limited to 10 items for readability
            for i, movement in enumerate(movements[:10], 1):
                direction = "➕" if movement.movement_type == MovementType.IN else "➖"
                if movement.movement_type == MovementType.ADJUST:
                    # For adjustments, show + or - based on the signed quantity
                    direction = "➕" if movement.signed_base_quantity >= 0 else "➖"
                    
                text += f"{i}. {direction} <b>{movement.item_name}</b>: {abs(movement.quantity)} {movement.unit}\n"
            
            # If there are more than 10 items, show a count of remaining
            if len(movements) > 10:
                text += f"\n... and {len(movements) - 10} more items\n"
            
            text += f"\nPlease approve or reject this batch request."
            
            # Create approval buttons
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve Batch", callback_data=f"approvebatch:{batch_id}"),
                    InlineKeyboardButton("❌ Reject Batch", callback_data=f"rejectbatch:{batch_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send the message
            message_sent = await self.send_message(chat_id, text, reply_markup)
            return message_sent
            
        except Exception as e:
            logger.error(f"Error sending batch approval request: {e}")
            return False
    
    async def send_stock_search_results(self, chat_id: int, query: str, 
                                      results: List[Item], pending_info: dict, 
                                      total_count: int = None) -> bool:
        """
        Send stock search results with inline keyboard for easy selection.
        
        Args:
            chat_id: Telegram chat ID to send the message to
            query: Original search query
            results: List of search results (should be max 3)
            pending_info: Dictionary with pending movements info
            total_count: Total count of matching items (for "Showing top 3 of X" message)
            
        Returns:
            Boolean indicating success or failure
        """
        try:
            # Create search results text
            text = (
                f"🔍 <b>Stock Query Results for \"{query}\"</b>\n\n"
            )
            
            # Add result count message if total_count is provided
            if total_count and total_count > 3:
                text += f"<i>Showing top 3 of {total_count} results</i>\n\n"
            
            # Add numbered results - only show item names initially
            for i, item in enumerate(results, 1):
                text += f"{i}. <b>{item.name}</b>\n"
            
            text += "\n"
            
            # Add instructions
            text += "<b>How to select an item:</b>\n"
            text += "• Click the button below the item name\n"
            text += "• Or type the <b>exact name</b> (e.g., 'cement bags')\n"
            text += "• Or type the <b>number</b> (e.g., '1' for the first item)"
            
            # Create inline keyboard with 3 buttons
            keyboard = []
            for i, item in enumerate(results, 1):
                # Create a safe callback data (limit to 64 characters)
                item_name_slug = item.name.replace(" ", "_").replace("-", "_")[:30]
                callback_data = f"stock_item_{i}_{item_name_slug}"
                
                keyboard.append([{
                    "text": f"{i}. {item.name}",
                    "callback_data": callback_data
                }])
            
            # Send the message with inline keyboard
            message_sent = await self.send_message(
                chat_id, 
                text, 
                reply_markup={"inline_keyboard": keyboard}
            )
            return message_sent
            
        except Exception as e:
            logger.error(f"Error sending stock search results: {e}")
            return False

    async def send_item_details(self, chat_id: int, item: Item, 
                              pending_movements: List[StockMovement], 
                              in_pending_batch: bool) -> bool:
        """
        Send detailed information for a specific item.
        
        Args:
            chat_id: Telegram chat ID to send the message to
            item: The item to display details for
            pending_movements: List of pending movements for the item
            in_pending_batch: Whether the item is in a pending batch
            
        Returns:
            Boolean indicating success or failure
        """
        try:
            # Create detailed item information text
            text = f"📦 <b>Item Details: {item.name}</b>\n\n"
            
            # Enhanced stock information with unit structure
            if item.unit_size > 1.0 and item.unit_type != "piece":
                # Show both unit count and total volume for enhanced items
                total_volume = item.get_total_volume()
                text += f"<b>Stock Level:</b> {item.on_hand} units × {item.unit_size} {item.unit_type} = {total_volume} {item.unit_type}\n"
                text += f"<b>Unit Size:</b> {item.unit_size} {item.unit_type}\n"
                text += f"<b>Unit Type:</b> {item.unit_type}\n"
                text += f"<b>Base Unit:</b> {item.unit_type}\n"
            else:
                # Standard display for regular items
                text += f"<b>Stock Level:</b> {item.on_hand} {item.unit_type}\n"
                text += f"<b>Unit Size:</b> 1 {item.unit_type}\n"
            
            if item.threshold:
                if item.unit_size > 1.0 and item.unit_type != "piece":
                    threshold_volume = item.threshold * item.unit_size
                    text += f"<b>Reorder Threshold:</b> {item.threshold} units ({threshold_volume} {item.unit_type})\n"
                else:
                    text += f"<b>Reorder Threshold:</b> {item.threshold} {item.unit_type}\n"
            
            if item.location:
                text += f"<b>Preferred Location:</b> {item.location}\n"
            
            if item.category:
                text += f"<b>Category:</b> {item.category}\n"
            
            if item.large_qty_threshold:
                if item.unit_size > 1.0 and item.unit_type != "piece":
                    large_qty_volume = item.large_qty_threshold * item.unit_size
                    text += f"<b>Large Qty Threshold:</b> {item.large_qty_threshold} units ({large_qty_volume} {item.unit_type})\n"
                else:
                    text += f"<b>Large Qty Threshold:</b> {item.large_qty_threshold} {item.unit_type}\n"
            
            # Pending information
            if pending_movements:
                text += f"\n<b>Pending Movements:</b> {len(pending_movements)}\n"
                for i, movement in enumerate(pending_movements[:3], 1):  # Show first 3
                    direction = "➕" if movement.movement_type.value == "IN" else "➖"
                    text += f"{i}. {direction} {movement.quantity} {movement.unit}"
                    if movement.project:
                        text += f" (Project: {movement.project})"
                    text += "\n"
                
                if len(pending_movements) > 3:
                    text += f"... and {len(pending_movements) - 3} more pending movements\n"
            
            if in_pending_batch:
                text += f"\n🔄 <b>This item is part of a pending batch approval</b>\n"
            
            # Send the message
            message_sent = await self.send_message(chat_id, text)
            return message_sent
            
        except Exception as e:
            logger.error(f"Error sending item details: {e}")
            return False

    async def send_batch_success_summary(self, chat_id: int, batch_id: str,
                                       movements: List[StockMovement],
                                       before_levels: Dict[str, float],
                                       after_levels: Dict[str, float],
                                       failed_entries: List[Dict[str, Any]] = None) -> bool:
        """
        Send a detailed success summary after batch approval.
        
        Args:
            chat_id: Telegram chat ID to send the message to
            batch_id: Unique identifier for the batch
            movements: List of movements in the batch
            before_levels: Dictionary of stock levels before processing
            after_levels: Dictionary of stock levels after processing
            failed_entries: List of entries that failed processing
            
        Returns:
            Boolean indicating success or failure
        """
        try:
            if failed_entries is None:
                failed_entries = []
                
            # Create summary text
            text = (
                f"✅ <b>Batch Processed Successfully</b>\n\n"
                f"<b>Batch ID:</b> {batch_id}\n"
                f"<b>Items processed:</b> {len(movements) - len(failed_entries)}/{len(movements)}\n\n"
                f"<b>Inventory Changes:</b>\n"
            )
            
            # Add item details with before/after levels
            # Sort by item name for consistent output
            sorted_movements = sorted(movements, key=lambda m: m.item_name)
            
            for movement in sorted_movements:
                item_name = movement.item_name
                
                # Skip failed entries
                if any(entry.get("item_name") == item_name for entry in failed_entries):
                    continue
                    
                # Determine direction symbol based on movement type
                direction = "➕" if movement.movement_type == MovementType.IN else "➖"
                if movement.movement_type == MovementType.ADJUST:
                    direction = "➕" if movement.signed_base_quantity >= 0 else "➖"
                
                # Get before/after levels
                before = before_levels.get(item_name, 0)
                after = after_levels.get(item_name, before)
                change = after - before
                
                # Format the change with sign
                change_str = f"{change:+.2f}" if change else "0.00"
                
                # Enhanced movement display with unit context
                if hasattr(movement, 'unit_size') and movement.unit_size and movement.unit_size > 1.0:
                    # Show both units and total volume for enhanced items
                    total_volume = abs(movement.quantity) * movement.unit_size
                    text += f"• {direction} <b>{item_name}</b>: {abs(movement.quantity)} units × {movement.unit_size} {movement.unit} = {total_volume} {movement.unit}\n"
                else:
                    # Standard display for regular items
                    text += f"• {direction} <b>{item_name}</b>: {abs(movement.quantity)} {movement.unit}\n"
                
                text += f"  Stock: {before} → {after} ({change_str})\n"
            
            # Add failed entries if any
            if failed_entries and len(failed_entries) > 0:
                text += f"\n<b>Failed Entries:</b>\n"
                for i, entry in enumerate(failed_entries[:5], 1):
                    text += f"{i}. <b>{entry['item_name']}</b>: {entry['error']}\n"
                
                # If there are more than 5 failed entries, show count of remaining
                if len(failed_entries) > 5:
                    text += f"\n... and {len(failed_entries) - 5} more failed entries\n"
            
            # Send the message
            return await self.send_message(chat_id, text)
            
        except Exception as e:
            logger.error(f"Error sending batch success summary: {e}")
            return False
    
    async def send_daily_report(self, chat_id: int, report_data: Dict[str, Any]) -> bool:
        """Send daily inventory report."""
        try:
            text = (
                f"📊 <b>Daily Inventory Report - {report_data['date']}</b>\n\n"
                f"📥 <b>Total In:</b> {report_data['total_in']:.2f}\n"
                f"📤 <b>Total Out:</b> {report_data['total_out']:.2f}\n"
                f"🔄 <b>Movements:</b> {report_data['movements_count']}\n"
                f"⏳ <b>Pending Approvals:</b> {report_data['pending_approvals']}\n\n"
            )
            
            if report_data['low_stock_items']:
                text += f"⚠️ <b>Low Stock Items:</b>\n"
                for item in report_data['low_stock_items'][:5]:  # Limit to 5 items
                    text += f"• {item}\n"
                if len(report_data['low_stock_items']) > 5:
                    text += f"... and {len(report_data['low_stock_items']) - 5} more\n"
            
            return await self.send_message(chat_id, text)
            
        except Exception as e:
            logger.error(f"Error sending daily report: {e}")
            return False
    
    async def send_low_stock_alert(self, chat_id: int, low_stock_items: List[str]) -> bool:
        """Send low stock alert."""
        try:
            if not low_stock_items:
                return True
            
            text = (
                f"⚠️ <b>Low Stock Alert</b>\n\n"
                f"The following items are below their threshold:\n\n"
            )
            
            for item in low_stock_items[:10]:  # Limit to 10 items
                text += f"• {item}\n"
            
            if len(low_stock_items) > 10:
                text += f"\n... and {len(low_stock_items) - 10} more items"
            
            return await self.send_message(chat_id, text)
            
        except Exception as e:
            logger.error(f"Error sending low stock alert: {e}")
            return False
    
    async def send_csv_export(self, chat_id: int, csv_data: str, filename: str) -> bool:
        """Send CSV export as a document."""
        try:
            # Convert CSV string to bytes
            csv_bytes = csv_data.encode('utf-8')
            
            await self.bot.send_document(
                chat_id=chat_id,
                document=csv_bytes,
                filename=filename,
                caption="📊 Inventory Export"
            )
            return True
        except TelegramError as e:
            logger.error(f"Error sending CSV export: {e}")
            return False
    
    async def send_help_message(self, chat_id: int, user_role: str, search_term: str = None) -> bool:
        """Send help message with available commands, optionally filtered by search term."""
        try:
            text = f"🤖 <b>CONSTRUCTION INVENTORY BOT</b>\n\n"
            
            # User role and quick intro
            text += f"<b>Role:</b> {user_role.title()}\n\n"
            
            # If search term provided, show filtered results
            if search_term:
                text += f"🔍 <b>Search Results for \"{search_term}\"</b>\n\n"
                return await self._send_filtered_help(chat_id, text, user_role, search_term.lower())
            
            # Show full help message
            text += "📋 <b>AVAILABLE COMMANDS</b>\n\n"
            
            # Stock Operations
            text += "📦 <b>Stock Operations</b>\n"
            text += "• <b>/in</b> <i>item, qty unit, [details]</i> - Add stock\n"
            text += "• <b>/out</b> <i>item, qty unit, [details]</i> - Remove stock\n"
            text += "• <b>/adjust</b> <i>item, ±qty unit</i> - Correct stock (admin)\n\n"
            
            # Queries
            text += "🔍 <b>Queries</b>\n"
            text += "• <b>/stock</b> <i>item</i> - Fuzzy search with detailed info\n"
            text += "• <b>/find</b> <i>item</i> - Search inventory\n"
            text += "• <b>/onhand</b> <i>item</i> - Check stock level\n"
            text += "• <b>/whoami</b> - Show your role\n\n"
            
            # Management
            if user_role in ["admin", "staff"]:
                text += "⚙️ <b>Management</b>\n"
                text += "• <b>/approve</b> <i>movement_id</i> - Approve movement\n"
                text += "• <b>/approvebatch</b> <i>batch_id</i> - Approve batch\n"
                text += "• <b>/rejectbatch</b> <i>batch_id</i> - Reject batch\n"
                text += "• <b>/setthreshold</b> <i>qty</i> - Set reorder level\n"
                text += "• <b>/audit</b> - Low stock items\n"
                text += "• <b>/export onhand</b> - CSV export\n\n"
            
            # Batch Operations
            if user_role in ["admin", "staff"]:
                text += "📋 <b>Batch Operations</b>\n"
                text += "• <b>/batchhelp</b> - Detailed batch guide\n"
                text += "• <b>/validate</b> <i>entries</i> - Test format\n"
                text += "• <b>/status</b> - System features\n\n"
            
            # Examples
            text += "💡 <b>QUICK EXAMPLES</b>\n"
            text += "• <code>/in project: Bridge, cement, 50 bags</code>\n"
            text += "• <code>/stock cement</code>\n"
            text += "• <code>/help /in</code> - Detailed help for /in command\n\n"
            
            # Pro tip
            text += "💡 <b>PRO TIPS</b>\n"
            text += "• <b>/help [topic]</b> - Search by topic (e.g., <code>/help batch</code>)\n"
            text += "• <b>/help /[command]</b> - Detailed help for specific command\n"
            text += "• Examples: <code>/help /stock</code>, <code>/help /validate</code>"
            
            return await self.send_message(chat_id, text)
            
        except Exception as e:
            logger.error(f"Error sending help message: {e}")
            return False
    
    async def _send_filtered_help(self, chat_id: int, header_text: str, user_role: str, search_term: str) -> bool:
        """Send filtered help message based on search term."""
        try:
            # Import the command suggestions service to get dynamic command data
            from services.command_suggestions import CommandSuggestionsService
            cmd_service = CommandSuggestionsService()
            
            # Check if user is asking for help with a specific command (e.g., "/help /in" or "/help in")
            if search_term.startswith('/'):
                command_name = search_term[1:]  # Remove the leading slash
            else:
                command_name = search_term
            
            # Try to get specific command info
            command_info = cmd_service.get_command_info(command_name)
            if command_info:
                return await self._send_command_specific_help(chat_id, command_name, command_info, user_role)
            
            # Get commands by category
            categories = {}
            for category in cmd_service.get_all_categories():
                commands = cmd_service.get_commands_by_category(category)
                if commands:
                    categories[category.lower()] = {
                        "title": f"📦 {category}" if category == "Stock Operations" else
                                f"🔍 {category}" if category == "Queries" else
                                f"⚙️ {category}" if category == "Management" else
                                f"📋 {category}" if category == "Batch Operations" else
                                f"❓ {category}",
                        "commands": [(f"/{cmd_name}", cmd_info["description"]) for cmd_name, cmd_info in commands]
                    }
            
            # Find matching categories
            matching_categories = []
            for category_key, category_data in categories.items():
                if (search_term in category_key or 
                    any(search_term in cmd[0].lower() or search_term in cmd[1].lower() 
                        for cmd in category_data["commands"])):
                    matching_categories.append((category_key, category_data))
            
            if not matching_categories:
                # No matches found
                text = header_text + f"❌ No commands found matching \"{search_term}\"\n\n"
                text += "💡 <b>Try these options:</b>\n"
                text += "• <code>/help stock</code> - Stock operations\n"
                text += "• <code>/help query</code> - Search commands\n"
                text += "• <code>/help batch</code> - Batch operations\n"
                text += "• <code>/help management</code> - Admin tools\n\n"
                text += "📝 <b>For specific commands:</b>\n"
                text += "• <code>/help /in</code> - Detailed help for /in\n"
                text += "• <code>/help /stock</code> - Detailed help for /stock\n"
                text += "• <code>/help /validate</code> - Detailed help for /validate\n\n"
                text += "Or use <code>/help</code> to see all commands."
                return await self.send_message(chat_id, text)
            
            # Build filtered help message
            text = header_text
            
            for category_key, category_data in matching_categories:
                text += f"{category_data['title']}\n"
                for cmd, description in category_data["commands"]:
                    text += f"• <b>{cmd}</b> - {description}\n"
                text += "\n"
            
            # Add footer
            text += "💡 <b>Need more help?</b>\n"
            text += "Use <code>/help</code> to see all available commands."
            
            return await self.send_message(chat_id, text)
            
        except Exception as e:
            logger.error(f"Error sending filtered help message: {e}")
            return False
    
    async def _send_command_specific_help(self, chat_id: int, command_name: str, command_info: dict, user_role: str) -> bool:
        """Send detailed help for a specific command."""
        try:
            # Build command-specific help message
            text = f"🤖 <b>COMMAND HELP: /{command_name.upper()}</b>\n\n"
            
            # Add category and description
            category_icon = "📦" if command_info["category"] == "Stock Operations" else \
                           "🔍" if command_info["category"] == "Queries" else \
                           "⚙️" if command_info["category"] == "Management" else \
                           "📋" if command_info["category"] == "Batch Operations" else "❓"
            
            text += f"<b>Category:</b> {category_icon} {command_info['category']}\n"
            text += f"<b>Description:</b> {command_info['description']}\n\n"
            
            # Add usage
            text += f"📝 <b>USAGE</b>\n"
            text += f"<code>{command_info['usage']}</code>\n\n"
            
            # Add examples
            if 'examples' in command_info and command_info['examples']:
                text += f"💡 <b>EXAMPLES</b>\n"
                for example in command_info['examples']:
                    text += f"• <code>{example}</code>\n"
                text += "\n"
            
            # Add role-specific notes
            if command_info["category"] == "Management" and user_role not in ["admin", "staff"]:
                text += f"⚠️ <b>NOTE:</b> This command requires Admin or Staff role\n"
                text += f"Your current role: {user_role.title()}\n\n"
            elif command_name in ["adjust", "inventory", "inventory_validate"] and user_role != "admin":
                text += f"⚠️ <b>NOTE:</b> This command requires Admin role\n"
                text += f"Your current role: {user_role.title()}\n\n"
            
            # Add tips for specific commands
            if command_name in ["in", "out", "adjust"]:
                text += f"💡 <b>TIPS</b>\n"
                text += f"• Always include <b>project:</b> in your commands\n"
                text += f"• Use commas to separate item, quantity, and details\n"
                text += f"• Batch operations: separate entries with semicolons or newlines\n\n"
            elif command_name == "stock":
                text += f"💡 <b>TIPS</b>\n"
                text += f"• Uses fuzzy search - partial matches work\n"
                text += f"• Shows detailed item information and stock levels\n"
                text += f"• Try variations if exact name doesn't work\n\n"
            elif command_name == "validate":
                text += f"💡 <b>TIPS</b>\n"
                text += f"• Test your batch format before processing\n"
                text += f"• Use semicolons or newlines to separate entries\n"
                text += f"• Include global parameters like project: at the start\n\n"
            
            # Add footer
            text += f"❓ <b>Need more help?</b>\n"
            text += f"• <code>/help</code> - See all commands\n"
            text += f"• <code>/batchhelp</code> - Detailed batch guide\n"
            text += f"• <code>/help [topic]</code> - Search by topic"
            
            return await self.send_message(chat_id, text)
            
        except Exception as e:
            logger.error(f"Error sending command-specific help for '{command_name}': {e}")
            return False
    
    async def send_error_message(self, chat_id: int, error_message: str) -> bool:
        """Send an error message to the user."""
        try:
            text = f"❌ <b>Error</b>\n\n{error_message}"
            return await self.send_message(chat_id, text)
        except Exception as e:
            logger.error(f"Error sending error message: {e}")
            return False
    
    async def send_success_message(self, chat_id: int, success_message: str) -> bool:
        """Send a success message to the user."""
        try:
            text = f"✅ <b>Success</b>\n\n{success_message}"
            return await self.send_message(chat_id, text)
        except Exception as e:
            logger.error(f"Error sending success message: {e}")
            return False
    
    async def answer_callback_query(self, callback_query_id: str, text: str = None, show_alert: bool = False) -> bool:
        """Answer a callback query to remove the loading state."""
        try:
            await self.bot.answer_callback_query(
                callback_query_id=callback_query_id,
                text=text,
                show_alert=show_alert
            )
            return True
        except Exception as e:
            logger.error(f"Error answering callback query: {e}")
            return False