#!/usr/bin/env python3
"""Test script to run the bot locally."""

import asyncio
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.main import ConstructionInventoryBot

async def test_bot():
    """Test the bot locally."""
    print("🚀 Starting Construction Inventory Bot (Local Test)")
    print("=" * 50)
    
    try:
        # Create bot instance
        bot = ConstructionInventoryBot()
        print("✅ Bot initialized successfully")
        
        # Test basic functionality
        print("\n🧪 Testing basic functionality...")
        
        # Check if services are working
        print(f"   • Airtable Client: {'✅' if bot.airtable_client else '❌'}")
        print(f"   • Stock Service: {'✅' if bot.stock_service else '❌'}")
        print(f"   • Telegram Service: {'✅' if bot.telegram_service else '❌'}")
        print(f"   • Command Router: {'✅' if bot.command_router else '❌'}")
        
        # Test settings loading
        print(f"\n⚙️  Settings loaded:")
        print(f"   • Log Level: {bot.settings.log_level}")
        print(f"   • Worker Sleep: {bot.settings.worker_sleep_interval}s")
        print(f"   • Default Approval Threshold: {bot.settings.default_approval_threshold}")
        
        print("\n🎉 Bot is ready for testing!")
        print("\n💡 To test with real Telegram commands:")
        print("   1. Make sure your .env file has valid credentials")
        print("   2. Run: python -m src.main")
        print("   3. Send commands to your bot in Telegram")
        
    except Exception as e:
        print(f"❌ Error testing bot: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_bot())
