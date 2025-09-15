"""Telegram integration for the Construction Inventory Bot."""

import logging
from typing import List, Optional, Dict, Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.error import TelegramError

from schemas import StockMovement, MovementType, Item, PaginatedSearchResults
from services.duplicate_detection import PotentialDuplicate, DuplicateDetectionResult, MovementDuplicateResult, MovementDuplicateDetectionResult

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

    async def send_paginated_stock_results(self, chat_id: int, paginated_results: PaginatedSearchResults, 
                                         pending_info: dict) -> bool:
        """
        Send paginated stock search results with navigation buttons.
        
        Args:
            chat_id: Telegram chat ID to send the message to
            paginated_results: PaginatedSearchResults object with pagination metadata
            pending_info: Dictionary with pending movements info
            
        Returns:
            Boolean indicating success or failure
        """
        try:
            # Get items for current page
            start_idx = (paginated_results.current_page - 1) * paginated_results.results_per_page
            end_idx = start_idx + paginated_results.results_per_page
            page_items = paginated_results.all_results[start_idx:end_idx]
            
            # Create search results text
            text = f"🔍 <b>Stock Query Results for \"{paginated_results.query}\"</b>\n\n"
            
            # Add result count message
            text += f"<i>Showing {len(page_items)} of {paginated_results.total_count} results</i>\n\n"
            
            # Add numbered results - only show item names initially
            for i, item in enumerate(page_items, 1):
                text += f"{i}. <b>{item.name}</b>\n"
            
            text += "\n"
            
            # Add instructions
            text += "<b>How to select an item:</b>\n"
            text += "• Click the button below the item name\n"
            text += "• Or type the <b>exact name</b> (e.g., 'cement bags')\n"
            text += "• Or type the <b>number</b> (e.g., '1' for the first item)"
            
            # Create inline keyboard with item buttons and pagination controls
            keyboard = self._create_paginated_keyboard(paginated_results, page_items)
            
            # Send the message with inline keyboard
            message_sent = await self.send_message(
                chat_id, 
                text, 
                reply_markup={"inline_keyboard": keyboard}
            )
            return message_sent
            
        except Exception as e:
            logger.error(f"Error sending paginated stock search results: {e}")
            return False

    def _create_paginated_keyboard(self, paginated_results: PaginatedSearchResults, page_items: List[Item]) -> List[List[Dict[str, str]]]:
        """
        Create inline keyboard for paginated stock results.
        
        Args:
            paginated_results: PaginatedSearchResults object
            page_items: Items for current page
            
        Returns:
            List of keyboard rows
        """
        keyboard = []
        
        # Add item buttons (5 per page)
        for i, item in enumerate(page_items, 1):
            # Create a safe callback data (limit to 64 characters)
            item_name_slug = item.name.replace(" ", "_").replace("-", "_")[:30]
            callback_data = f"stock_item_{i}_{item_name_slug}"
            
            keyboard.append([{
                "text": f"{i}. {item.name}",
                "callback_data": callback_data
            }])
        
        # Add pagination controls
        pagination_row = []
        
        # Previous button
        if self._should_show_previous_button(paginated_results.current_page):
            prev_callback = f"stock_page_prev_{paginated_results.query_hash}_{paginated_results.current_page}"
            pagination_row.append({
                "text": "◀ Previous",
                "callback_data": prev_callback
            })
        
        # Page indicator
        page_text = f"Page {paginated_results.current_page} of {paginated_results.total_pages}"
        pagination_row.append({
            "text": page_text,
            "callback_data": "noop"  # Non-functional button for display
        })
        
        # Next button
        if self._should_show_next_button(paginated_results.current_page, paginated_results.total_pages):
            next_callback = f"stock_page_next_{paginated_results.query_hash}_{paginated_results.current_page}"
            pagination_row.append({
                "text": "Next ▶",
                "callback_data": next_callback
            })
        
        # Show more button (same as Next, but different text)
        if self._should_show_next_button(paginated_results.current_page, paginated_results.total_pages):
            show_more_callback = f"stock_show_more_{paginated_results.query_hash}_{paginated_results.current_page}"
            pagination_row.append({
                "text": "Show more...",
                "callback_data": show_more_callback
            })
        
        # Add pagination row if it has any buttons
        if pagination_row:
            keyboard.append(pagination_row)
        
        return keyboard

    def _should_show_previous_button(self, current_page: int) -> bool:
        """Check if Previous button should be shown."""
        return current_page > 1

    def _should_show_next_button(self, current_page: int, total_pages: int) -> bool:
        """Check if Next/Show more button should be shown."""
        return current_page < total_pages

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
            text += "📦 <b>Stock Operations (New Batch System)</b>\n"
            text += "• <b>/in</b> - Add stock with batch processing\n"
            text += "• <b>/out</b> - Remove stock with batch processing\n"
            text += "• <b>/preview in</b> - Preview duplicates before adding\n"
            text += "• <b>/preview out</b> - Preview duplicates before removing\n"
            text += "• <b>/adjust</b> <i>item, ±qty unit</i> - Correct stock (admin)\n\n"
            
            text += "🔧 <b>Batch Command Features</b>\n"
            text += "• Multiple batches in one command\n"
            text += "• Smart duplicate detection & auto-merge\n"
            text += "• Only item name & quantity required\n"
            text += "• Smart defaults for missing parameters\n"
            text += "• Batch summary before processing\n"
            text += "• Progress indicators during processing\n"
            text += "• Comprehensive error messages with suggestions\n\n"
            
            text += "📝 <b>Quick Examples</b>\n"
            text += "• <code>/in Cement 50kg, 10 bags</code> (minimal)\n"
            text += "• <code>/in -batch 1- project: site A\nCement 50kg, 10 bags</code>\n"
            text += "• <code>/out -batch 1- project: mzuzu, driver: John, to: site\nSteel 12mm, 5 pieces</code>\n\n"
            
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
            
            # Troubleshooting
            text += "🔧 <b>TROUBLESHOOTING</b>\n"
            text += "• <b>Command not working?</b> Check format with <code>/preview in</code>\n"
            text += "• <b>Duplicates found?</b> Bot will ask for confirmation\n"
            text += "• <b>Batch failed?</b> Check error messages for suggestions\n"
            text += "• <b>Need help?</b> Use <code>/help /in</code> for detailed guide\n\n"
            
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
    
    async def send_duplicate_confirmation(self, chat_id: int, 
                                        duplicates: List[PotentialDuplicate], 
                                        new_entries: List[Any]) -> int:
        """
        Send duplicate confirmation dialog with inline keyboard.
        
        Args:
            chat_id: Telegram chat ID to send the message to
            duplicates: List of potential duplicates found
            new_entries: List of new inventory entries
            
        Returns:
            Message ID of the sent message, or -1 if failed
        """
        try:
            message = self._format_duplicate_message(duplicates, new_entries)
            keyboard = self._create_duplicate_confirmation_keyboard()
            
            success = await self.send_message(chat_id, message, keyboard)
            if success:
                # Return a placeholder message ID (in real implementation, this would be the actual message ID)
                return 1  # Placeholder for now
            return -1
            
        except Exception as e:
            logger.error(f"Error sending duplicate confirmation: {e}")
            return -1
    
    def _format_duplicate_message(self, duplicates: List[PotentialDuplicate], 
                                new_entries: List[Any]) -> str:
        """
        Format duplicate detection message with preview.
        
        Args:
            duplicates: List of potential duplicates
            new_entries: List of new inventory entries
            
        Returns:
            Formatted message text
        """
        try:
            # Group duplicates by new entry
            duplicates_by_entry = {}
            for duplicate in duplicates:
                # Find the matching new entry (simplified for now)
                entry_key = f"entry_{len(duplicates_by_entry)}"
                if entry_key not in duplicates_by_entry:
                    duplicates_by_entry[entry_key] = []
                duplicates_by_entry[entry_key].append(duplicate)
            
            text = "🔍 <b>Potential Duplicates Detected</b>\n\n"
            text += "Found similar entries that might be duplicates:\n\n"
            
            # Show each new entry with its potential duplicates
            for i, entry in enumerate(new_entries):
                text += f"<b>New Entry:</b> {entry.item_name}, {entry.quantity}\n"
                
                # Find duplicates for this entry (simplified matching)
                entry_duplicates = [d for d in duplicates if self._entries_similar(entry, d)]
                
                if entry_duplicates:
                    text += "<b>Similar to:</b>\n"
                    for duplicate in entry_duplicates[:3]:  # Show max 3 duplicates
                        similarity_percent = int(duplicate.similarity_score * 100)
                        text += f"• {duplicate.item_name}, {duplicate.quantity} ({similarity_percent}% match)"
                        if duplicate.user_name:
                            text += f" - Added by {duplicate.user_name}"
                        text += "\n"
                    
                    if len(entry_duplicates) > 3:
                        text += f"• ... and {len(entry_duplicates) - 3} more matches\n"
                else:
                    text += "<i>No similar entries found</i>\n"
                
                text += "\n"
            
            text += "<b>Action Required:</b>\n"
            text += "Choose how to proceed with these entries.\n\n"
            text += "<i>Note: Confirming will add quantities together for similar items.</i>"
            
            return text
            
        except Exception as e:
            logger.error(f"Error formatting duplicate message: {e}")
            return "Error formatting duplicate detection message."
    
    def _create_duplicate_confirmation_keyboard(self, duplicates: List[Any] = None) -> InlineKeyboardMarkup:
        """
        Create inline keyboard for duplicate confirmation actions.
        
        Args:
            duplicates: List of duplicate items for individual confirmation
            
        Returns:
            InlineKeyboardMarkup with confirmation buttons
        """
        try:
            if duplicates and len(duplicates) <= 5:
                # Create individual buttons for each duplicate (max 5 for UI limits)
                keyboard = []
                for i, duplicate in enumerate(duplicates[:5]):
                    # Handle both dict and DuplicateItem objects
                    item_name = None
                    try:
                        if isinstance(duplicate, dict):
                            item_name = duplicate.get('batch_item', {}).get('item_name')
                        elif hasattr(duplicate, 'batch_item'):
                            # duplicate.batch_item can be dict or pydantic model dump
                            item_name = duplicate.batch_item.get('item_name') if isinstance(duplicate.batch_item, dict) else getattr(duplicate.batch_item, 'item_name', None)
                    except Exception:
                        item_name = None
                    if not item_name:
                        item_name = f'Item {i+1}'
                    item_name = str(item_name)[:20]
                    keyboard.append([
                        InlineKeyboardButton(f"✅ {item_name}", callback_data=f"confirm_individual_{i}"),
                        InlineKeyboardButton(f"❌ {item_name}", callback_data=f"cancel_individual_{i}")
                    ])
                
                # Add bulk action buttons
                keyboard.append([
                    InlineKeyboardButton("✅ Confirm All", callback_data="confirm_all_duplicates"),
                    InlineKeyboardButton("❌ Cancel All", callback_data="cancel_all_duplicates")
                ])
                keyboard.append([
                    InlineKeyboardButton("🔍 Show All Matches", callback_data="show_all_duplicates")
                ])
            else:
                # Default bulk action keyboard
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Confirm & Update", callback_data="confirm_duplicates"),
                        InlineKeyboardButton("❌ Cancel & Check Stock", callback_data="cancel_duplicates")
                    ],
                    [
                        InlineKeyboardButton("🔍 Show All Matches", callback_data="show_all_duplicates")
                    ]
                ]
            
            return InlineKeyboardMarkup(keyboard)
            
        except Exception as e:
            logger.error(f"Error creating duplicate confirmation keyboard: {e}")
            return InlineKeyboardMarkup([])
    
    async def send_duplicate_confirmation_dialog(self, chat_id: int, duplicates: List[Any], 
                                               movement_type: str, batch_info: Dict[str, Any] = None) -> int:
        """
        Send duplicate confirmation dialog with individual item options.
        
        Args:
            chat_id: Telegram chat ID
            duplicates: List of duplicate items
            movement_type: Type of movement (IN/OUT)
            batch_info: Additional batch information
            
        Returns:
            Message ID of sent message
        """
        try:
            message = self._format_duplicate_confirmation_message(duplicates, movement_type, batch_info)
            keyboard = self._create_duplicate_confirmation_keyboard(duplicates)
            
            return await self.send_message(chat_id, message, reply_markup=keyboard)
            
        except Exception as e:
            logger.error(f"Error sending duplicate confirmation dialog: {e}")
            return await self.send_error_message(chat_id, f"Error creating confirmation dialog: {str(e)}")
    
    def _format_duplicate_confirmation_message(self, duplicates: List[Any], movement_type: str, 
                                             batch_info: Dict[str, Any] = None) -> str:
        """
        Format duplicate confirmation message with detailed information.
        
        Args:
            duplicates: List of duplicate items
            movement_type: Type of movement (IN/OUT)
            batch_info: Additional batch information
            
        Returns:
            Formatted message string
        """
        try:
            message = f"⚠️ <b>Potential Duplicates Detected!</b>\n\n"
            
            if batch_info:
                message += f"📋 <b>Batch {batch_info.get('batch_number', 1)} of {batch_info.get('total_batches', 1)}</b>\n"
                message += f"🔄 <b>Movement Type:</b> {movement_type.upper()}\n\n"
            
            message += f"Found {len(duplicates)} similar items in your batch:\n\n"
            
            for i, duplicate in enumerate(duplicates[:5], 1):  # Show max 5 for readability
                # Handle both dict and DuplicateItem objects
                if hasattr(duplicate, 'batch_item'):
                    batch_item = duplicate.batch_item
                    existing_item = duplicate.existing_item
                    similarity = duplicate.similarity_score
                    match_type = duplicate.match_type
                else:
                    batch_item = duplicate.get('batch_item', {})
                    existing_item = duplicate.get('existing_item', {})
                    similarity = duplicate.get('similarity_score', 0)
                    match_type = duplicate.get('match_type', 'unknown')
                
                item_name = batch_item.get('item_name', f'Item {i}')
                quantity = batch_item.get('quantity', 0)
                existing_quantity = existing_item.get('on_hand', 0)
                existing_name = existing_item.get('name', 'Unknown')
                
                message += f"<b>{i}. {item_name}</b> ({quantity})\n"
                message += f"   → Matches: {existing_name} ({existing_quantity})\n"
                message += f"   → Similarity: {similarity:.1%} ({match_type})\n"
                
                # Add stock level warning for OUT movements
                if movement_type.upper() == "OUT" and existing_quantity < quantity:
                    message += f"   ⚠️ <b>Insufficient stock!</b> (Need: {quantity}, Have: {existing_quantity})\n"
                
                message += "\n"
            
            if len(duplicates) > 5:
                message += f"... and {len(duplicates) - 5} more duplicates\n\n"
            
            message += "<b>Action Required:</b> Choose how to proceed with each item.\n"
            message += "• <b>✅ Confirm:</b> Merge quantities with existing item\n"
            message += "• <b>❌ Cancel:</b> Skip this item\n"
            message += "• <b>🔍 Show All:</b> View detailed match information\n"
            
            return message
            
        except Exception as e:
            logger.error(f"Error formatting duplicate confirmation message: {e}")
            return "Error formatting duplicate confirmation message."
    
    def _entries_similar(self, entry: Any, duplicate: PotentialDuplicate) -> bool:
        """
        Check if a new entry is similar to a potential duplicate.
        
        Args:
            entry: New inventory entry
            duplicate: Potential duplicate
            
        Returns:
            True if entries are similar
        """
        try:
            # Simple similarity check based on item names
            # In a real implementation, this would use the duplicate detection service
            entry_name_lower = entry.item_name.lower()
            duplicate_name_lower = duplicate.item_name.lower()
            
            # Check if they share significant keywords
            entry_words = set(entry_name_lower.split())
            duplicate_words = set(duplicate_name_lower.split())
            
            # If they share at least 50% of words, consider them similar
            if entry_words and duplicate_words:
                common_words = entry_words & duplicate_words
                similarity_ratio = len(common_words) / min(len(entry_words), len(duplicate_words))
                return similarity_ratio >= 0.5
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking entry similarity: {e}")
            return False
    
    async def send_duplicate_confirmation_result(self, chat_id: int, 
                                               updated_items: List[str], 
                                               failed_items: List[str]) -> bool:
        """
        Send confirmation result after processing duplicates.
        
        Args:
            chat_id: Telegram chat ID to send the message to
            updated_items: List of successfully updated items
            failed_items: List of items that failed to update
            
        Returns:
            Boolean indicating success or failure
        """
        try:
            text = "✅ <b>Duplicate Processing Complete</b>\n\n"
            
            if updated_items:
                text += f"<b>Updated Items ({len(updated_items)}):</b>\n"
                for item in updated_items:
                    text += f"• {item}\n"
                text += "\n"
            
            if failed_items:
                text += f"<b>Failed Items ({len(failed_items)}):</b>\n"
                for item in failed_items:
                    text += f"• {item}\n"
                text += "\n"
            
            if not updated_items and not failed_items:
                text += "No items were processed.\n"
            
            return await self.send_message(chat_id, text)
            
        except Exception as e:
            logger.error(f"Error sending duplicate confirmation result: {e}")
            return False
    
    async def send_movement_duplicate_confirmation(self, chat_id: int, movement_duplicates: Dict[str, Any], movements: List[Any]) -> bool:
        """Send movement duplicate confirmation message with inline keyboard."""
        try:
            # Format the duplicate message
            message = self._format_movement_duplicate_message(movement_duplicates, movements)
            
            # Create inline keyboard
            keyboard = self._create_movement_duplicate_keyboard(movement_duplicates, movements)
            
            # Send message with keyboard
            await self.send_message(chat_id, message, reply_markup=keyboard)
            return True
            
        except Exception as e:
            logger.error(f"Error sending movement duplicate confirmation: {e}")
            return False
    
    def _format_movement_duplicate_message(self, movement_duplicates: Dict[str, Any], movements: List[Any]) -> str:
        """Format movement duplicate confirmation message."""
        try:
            message = "🔍 <b>Potential Duplicates Detected!</b>\n\n"
            message += f"Found similar items in {len(movement_duplicates)} of {len(movements)} movements:\n\n"
            
            for movement_id, result in movement_duplicates.items():
                if isinstance(result, MovementDuplicateResult) and result.has_duplicates:
                    # Find the movement details
                    movement = next((m for m in movements if m.id == movement_id), None)
                    if movement:
                        message += f"<b>Stock {movement.movement_type.value}:</b> {movement.item_name}, {movement.quantity} {movement.unit}\n"
                        
                        for duplicate in result.potential_duplicates:
                            message += f"• {duplicate.item_name}, {duplicate.quantity} {duplicate.unit} ({duplicate.similarity_score:.0%} match)\n"
                        message += "\n"
            
            message += "<b>Action Required:</b> Choose how to proceed with each movement.\n"
            message += "<i>Note: Confirming will add quantities together for similar items.</i>"
            
            return message
            
        except Exception as e:
            logger.error(f"Error formatting movement duplicate message: {e}")
            return "🔍 <b>Potential Duplicates Detected!</b>\n\nPlease review the similar items and choose how to proceed."
    
    def _create_movement_duplicate_keyboard(self, movement_duplicates: Dict[str, Any], movements: List[Any] = None) -> InlineKeyboardMarkup:
        """Create inline keyboard for movement duplicate confirmation."""
        try:
            keyboard = []
            
            for movement_id, result in movement_duplicates.items():
                if isinstance(result, MovementDuplicateResult) and result.has_duplicates:
                    # Find the movement details
                    movement = next((m for m in movements if m.id == movement_id), None)
                    if movement:
                        # Create buttons for this movement
                        movement_short = movement.item_name[:20] + "..." if len(movement.item_name) > 20 else movement.item_name
                        
                        confirm_btn = InlineKeyboardButton(
                            f"✔ Confirm {movement.movement_type.value}: {movement_short}",
                            callback_data=f"confirm_movement_duplicate_{movement_id}"
                        )
                        cancel_btn = InlineKeyboardButton(
                            f"❌ Cancel {movement.movement_type.value}: {movement_short}",
                            callback_data=f"cancel_movement_duplicate_{movement_id}"
                        )
                        
                        keyboard.append([confirm_btn, cancel_btn])
            
            # Add batch action buttons
            if len(movement_duplicates) > 1:
                keyboard.append([
                    InlineKeyboardButton("✔ Confirm All", callback_data="confirm_all_movement_duplicates"),
                    InlineKeyboardButton("❌ Cancel All", callback_data="cancel_all_movement_duplicates")
                ])
                keyboard.append([
                    InlineKeyboardButton("• Show All Matches", callback_data="show_all_movement_duplicate_matches")
                ])
            
            return InlineKeyboardMarkup(keyboard)
            
        except Exception as e:
            logger.error(f"Error creating movement duplicate keyboard: {e}")
            return InlineKeyboardMarkup([])
    
    async def send_movement_duplicate_result(self, chat_id: int, result: Any) -> bool:
        """Send movement duplicate detection result."""
        try:
            message = "🔍 <b>Movement Duplicate Detection Result</b>\n\n"
            message += f"• Total movements checked: {result.total_movements}\n"
            message += f"• Duplicates found: {result.total_duplicates}\n"
            message += f"• Requires stock check: {'Yes' if result.requires_stock_check else 'No'}\n\n"
            
            if result.has_any_duplicates:
                message += "⚠️ <b>Action Required:</b> Please review the duplicate confirmation messages above."
            else:
                message += "✅ <b>No duplicates found.</b> Proceeding with normal approval."
            
            await self.send_message(chat_id, message)
            return True
            
        except Exception as e:
            logger.error(f"Error sending movement duplicate result: {e}")
            return False
    
    async def edit_message_text(self, chat_id: int, message_id: int, text: str, reply_markup: InlineKeyboardMarkup = None) -> bool:
        """Edit an existing message text."""
        try:
            await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            return True
        except Exception as e:
            logger.error(f"Error editing message text: {e}")
            return False