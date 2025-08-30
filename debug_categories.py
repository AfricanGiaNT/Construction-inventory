#!/usr/bin/env python3
"""Debug script to see what categories are actually available in Airtable."""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from airtable_client import AirtableClient
from config import Settings

async def debug_categories():
    """Debug what categories are actually available in Airtable."""
    try:
        print("Debugging available categories in Airtable...")
        
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
        
        # Get all items to see what categories exist
        print("\nGetting all items to see existing categories...")
        all_items = await client.get_all_items()
        print(f"Found {len(all_items)} items")
        
        # Collect all unique categories
        categories = set()
        for item in all_items:
            if item.category:
                categories.add(item.category)
        
        print(f"\nUnique categories found in Items table:")
        for category in sorted(categories):
            print(f"  '{category}'")
        
        # Also check the raw data to see if there are any other category values
        print("\nChecking raw Airtable data for categories...")
        raw_records = client.items_table.all()
        
        raw_categories = set()
        for record in raw_records:
            category = record["fields"].get("Category", "")
            if category:
                raw_categories.add(category)
        
        print(f"\nRaw categories from Airtable:")
        for category in sorted(raw_categories):
            print(f"  '{category}'")
        
        print("\n✅ Category debugging completed")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_categories())
