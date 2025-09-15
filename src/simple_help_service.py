"""Simple help service for low-literacy users with visual elements."""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class SimpleHelpService:
    """Service for providing simplified, visual help for low-literacy users."""
    
    def __init__(self):
        """Initialize the simple help service."""
        self.visual_commands = {
            "in": {
                "emoji": "📦",
                "action": "Add materials",
                "simple_example": "/in cement 50",
                "description": "When new materials arrive"
            },
            "out": {
                "emoji": "📤", 
                "action": "Remove materials",
                "simple_example": "/out cement 25",
                "description": "When materials are used"
            },
            "stock": {
                "emoji": "🔍",
                "action": "Check what we have",
                "simple_example": "/stock cement",
                "description": "See how much is left"
            },
            "help": {
                "emoji": "❓",
                "action": "Get help",
                "simple_example": "/help",
                "description": "Show this help message"
            }
        }
    
    def get_simple_help_message(self) -> str:
        """Get a simplified help message with visual elements."""
        text = "🤖 <b>CONSTRUCTION INVENTORY BOT</b>\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        text += "📱 <b>HOW TO USE:</b>\n"
        text += "1️⃣ Type a command (start with /)\n"
        text += "2️⃣ Press send\n"
        text += "3️⃣ Wait for reply\n\n"
        
        text += "🎯 <b>MAIN COMMANDS:</b>\n\n"
        
        for cmd, info in self.visual_commands.items():
            text += f"{info['emoji']} <b>/{cmd}</b> - {info['action']}\n"
            text += f"   📝 Example: <code>{info['simple_example']}</code>\n"
            text += f"   💡 {info['description']}\n\n"
        
        text += "✅ <b>SUCCESS TIPS:</b>\n"
        text += "• Always start with /\n"
        text += "• Use simple words\n"
        text += "• Wait for bot reply\n"
        text += "• Ask supervisor if confused\n\n"
        
        text += "🆘 <b>NEED HELP?</b>\n"
        text += "• Type <code>/help</code> anytime\n"
        text += "• Ask your supervisor\n"
        text += "• Don't panic if you make a mistake\n"
        
        return text
    
    def get_command_help(self, command: str) -> str:
        """Get detailed help for a specific command."""
        if command not in self.visual_commands:
            return self.get_simple_help_message()
        
        info = self.visual_commands[command]
        
        text = f"{info['emoji']} <b>/{command.upper()} COMMAND</b>\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        text += f"<b>What it does:</b> {info['description']}\n\n"
        
        text += f"<b>How to use:</b>\n"
        text += f"1️⃣ Type <code>/{command}</code>\n"
        text += f"2️⃣ Add item name\n"
        text += f"3️⃣ Add amount (for in/out)\n"
        text += f"4️⃣ Press send\n\n"
        
        text += f"<b>Examples:</b>\n"
        if command == "in":
            text += "• <code>/in cement 50</code>\n"
            text += "• <code>/in steel 100</code>\n"
            text += "• <code>/in paint 20</code>\n\n"
        elif command == "out":
            text += "• <code>/out cement 25</code>\n"
            text += "• <code>/out steel 10</code>\n"
            text += "• <code>/out paint 5</code>\n\n"
        elif command == "stock":
            text += "• <code>/stock cement</code>\n"
            text += "• <code>/stock steel</code>\n"
            text += "• <code>/stock paint</code>\n\n"
        
        text += "✅ <b>Remember:</b>\n"
        text += "• Always start with /\n"
        text += "• Use simple words\n"
        text += "• Wait for bot reply\n"
        text += "• Ask supervisor if confused\n"
        
        return text
    
    def get_quick_reference(self) -> str:
        """Get a quick reference card."""
        text = "📋 <b>QUICK REFERENCE CARD</b>\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        text += "📦 <b>ADD MATERIALS:</b>\n"
        text += "<code>/in [item] [amount]</code>\n\n"
        
        text += "📤 <b>REMOVE MATERIALS:</b>\n"
        text += "<code>/out [item] [amount]</code>\n\n"
        
        text += "🔍 <b>CHECK STOCK:</b>\n"
        text += "<code>/stock [item]</code>\n\n"
        
        text += "❓ <b>GET HELP:</b>\n"
        text += "<code>/help</code>\n\n"
        
        text += "💡 <b>EXAMPLES:</b>\n"
        text += "• <code>/in cement 50</code>\n"
        text += "• <code>/out cement 25</code>\n"
        text += "• <code>/stock cement</code>\n"
        
        return text
    
    def get_troubleshooting_help(self) -> str:
        """Get troubleshooting help for common problems."""
        text = "🆘 <b>TROUBLESHOOTING HELP</b>\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        text += "❌ <b>Bot doesn't reply:</b>\n"
        text += "✅ Wait 10 seconds, then try again\n\n"
        
        text += "❌ <b>Bot says 'Error':</b>\n"
        text += "✅ Check your spelling, try again\n\n"
        
        text += "❌ <b>Can't find the bot:</b>\n"
        text += "✅ Ask supervisor for help\n\n"
        
        text += "❌ <b>Made a mistake:</b>\n"
        text += "✅ Tell supervisor immediately\n\n"
        
        text += "❌ <b>Forgot how to use:</b>\n"
        text += "✅ Type <code>/help</code>\n\n"
        
        text += "📞 <b>Still need help?</b>\n"
        text += "Ask your supervisor or manager\n"
        
        return text
    
    def get_welcome_message(self) -> str:
        """Get a welcome message for new users."""
        text = "🎉 <b>WELCOME TO THE CONSTRUCTION INVENTORY BOT!</b>\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        text += "🤖 <b>This bot helps you:</b>\n"
        text += "• Keep track of materials\n"
        text += "• Know what we have in stock\n"
        text += "• Record when materials are used\n\n"
        
        text += "📱 <b>It's easy to use:</b>\n"
        text += "• Just type simple commands\n"
        text += "• Bot will reply with results\n"
        text += "• Ask for help anytime\n\n"
        
        text += "🎯 <b>Start with these commands:</b>\n"
        text += "• <code>/help</code> - See all commands\n"
        text += "• <code>/stock cement</code> - Check cement stock\n"
        text += "• <code>/in cement 50</code> - Add 50 cement bags\n\n"
        
        text += "💡 <b>Remember:</b>\n"
        text += "• Always start with /\n"
        text += "• Use simple words\n"
        text += "• Ask supervisor if confused\n"
        text += "• Don't panic if you make a mistake\n\n"
        
        text += "🚀 <b>Ready to start?</b>\n"
        text += "Type <code>/help</code> to see all commands!\n"
        
        return text

