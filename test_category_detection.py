#!/usr/bin/env python3
"""Test script to debug category detection for specific items."""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from airtable_client import AirtableClient
from config import Settings

async def test_category_detection():
    """Test category detection for specific items."""
    try:
        print("Testing category detection for specific items...")
        
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
        
        # Test items that should have different categories
        test_items = [
            "20 ltrs white sheen paint",
            "60 metres electric wire", 
            "Steel Beam 6m",
            "Steel Plate 3mm"
        ]
        
        print("\nTesting category detection for each item:")
        for item_name in test_items:
            print(f"\n--- {item_name} ---")
            
            # Test the category detection logic
            item_lower = item_name.lower()
            
            # Check what the current logic would detect
            if any(paint_word in item_lower for paint_word in ['paint', 'white', 'bitumec', 'ltrs', 'litres']):
                detected_category = "Paint"
            elif any(electrical_word in item_lower for electrical_word in ['wire', 'cable', 'electrical', 'electric']):
                detected_category = "Electrical"
            elif any(steel_word in item_lower for steel_word in ['steel', 'beam', 'plate', 'angle']):
                detected_category = "Steel"
            elif any(cement_word in item_lower for cement_word in ['cement', 'concrete']):
                detected_category = "Cement"
            else:
                detected_category = "General"
            
            print(f"  Detected category: {detected_category}")
            
            # Check if this item already exists in Airtable
            existing_item = await client.get_item(item_name)
            if existing_item:
                print(f"  Existing in Airtable: {existing_item.name}")
                print(f"  Current category: {existing_item.category}")
                print(f"  Current stock: {existing_item.on_hand}")
            else:
                print(f"  Not found in Airtable")
        
        print("\n✅ Category detection test completed")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_category_detection())
