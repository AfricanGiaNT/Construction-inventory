#!/usr/bin/env python3
"""Test script to verify Airtable field mapping fixes."""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from airtable_client import AirtableClient
from config import Settings

async def test_airtable_fix():
    """Test the Airtable connection and field mapping."""
    try:
        print("Testing Airtable connection and field mapping...")
        
        # Initialize settings and client
        settings = Settings()
        client = AirtableClient(settings)
        
        # Test connection
        print("Testing connection...")
        connected = await client.test_connection()
        print(f"Connection: {connected}")
        
        if not connected:
            print("❌ Connection failed")
            return
        
        # Test getting items
        print("Getting items...")
        items = await client.get_all_items()
        print(f"Found {len(items)} items")
        
        if items:
            print("\nFirst few items:")
            for i, item in enumerate(items[:3]):
                print(f"  {i+1}. {item.name}")
                print(f"     Stock: {item.on_hand}")
                print(f"     Category: {item.category}")
                print(f"     Base Unit: {item.base_unit}")
                print()
        
        print("✅ Airtable field mapping test completed")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_airtable_fix())
