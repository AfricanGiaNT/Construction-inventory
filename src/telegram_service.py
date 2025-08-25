"""Telegram integration for the Construction Inventory Bot."""

import logging
from typing import List, Optional, Dict, Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.error import TelegramError

from .schemas import StockMovement, MovementType

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
    
    async def send_help_message(self, chat_id: int, user_role: str) -> bool:
        """Send help message with available commands."""
        try:
            text = f"🤖 <b>CONSTRUCTION INVENTORY BOT</b>\n\n"
            
            # User role and quick intro
            text += f"<b>Role:</b> {user_role.title()}\n\n"
            
            # Core commands - everyone can use these
            text += "📋 <b>CORE COMMANDS</b>\n"
            text += "• <b>/help</b> - This help message\n"
            text += "• <b>/find</b> <i>item</i> - Search inventory\n"
            text += "• <b>/onhand</b> <i>item</i> - Check stock level\n"
            text += "• <b>/whoami</b> - Show your role\n\n"
            
            # Batch commands - staff and admin only
            if user_role in ["admin", "staff"]:
                text += "📦 <b>BATCH COMMANDS</b>\n"
                text += "• <b>/batchhelp</b> - Detailed batch guide\n"
                text += "• <b>/validate</b> <i>entries</i> - Test format\n"
                text += "• <b>/status</b> - System features\n\n"
                
                # Movement commands
                text += "🔄 <b>STOCK MOVEMENTS</b>\n"
                text += "• <b>/in</b> <i>item, qty unit, [details]</i>\n"
                text += "• <b>/out</b> <i>item, qty unit, [details]</i>\n"
                
                # Simple example
                text += "\n<b>Quick Example:</b>\n"
                text += "<code>/in project: Bridge, cement, 50 bags</code>\n\n"
                
                # Batch example - most important feature
                text += "<b>Batch Example:</b>\n"
                text += "<code>/in project: Bridge\n"
                text += "cement, 50 bags\n"
                text += "steel bars, 10 pieces</code>\n\n"
                
                # Admin tools
                if user_role == "admin":
                    text += "⚙️ <b>ADMIN TOOLS</b>\n"
                    text += "• <b>/adjust</b> <i>item, ±qty unit</i>\n"
                    text += "• <b>/approve</b> <i>movement_id</i>\n"
                    text += "• <b>/approvebatch</b> <i>batch_id</i>\n"
                    text += "• <b>/rejectbatch</b> <i>batch_id</i>\n"
                    text += "• <b>/setthreshold</b> <i>qty</i>\n\n"
                
                # Reporting tools
                text += "📊 <b>REPORTS</b>\n"
                text += "• <b>/audit</b> - Low stock items\n"
                text += "• <b>/export onhand</b> - CSV export\n\n"
            
            # Pro tip
            text += "💡 <b>PRO TIP</b>\n"
            text += "Use <b>global parameters</b> for batch commands:\n"
            text += "<code>driver: name, project: name, from: location</code>"
            
            return await self.send_message(chat_id, text)
            
        except Exception as e:
            logger.error(f"Error sending help message: {e}")
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