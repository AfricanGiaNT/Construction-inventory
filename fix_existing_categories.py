#!/usr/bin/env python3
"""Script to fix existing items with wrong categories."""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from airtable_client import AirtableClient
from config import Settings

async def fix_existing_categories():
    """Fix existing items with wrong categories."""
    try:
        print("Fixing existing items with wrong categories...")
        
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
        
        # Get all items
        print("\nGetting all items...")
        all_items = await client.get_all_items()
        print(f"Found {len(all_items)} items")
        
        # Items that need category fixes
        category_fixes = {
            "20 ltrs white sheen paint": "Paint",
            "60 metres electric wire": "Electrical"
        }
        
        print("\nChecking items that need category fixes:")
        for item in all_items:
            if item.name in category_fixes:
                expected_category = category_fixes[item.name]
                current_category = item.category
                
                print(f"\n--- {item.name} ---")
                print(f"  Current category: {current_category}")
                print(f"  Expected category: {expected_category}")
                
                if current_category != expected_category:
                    print(f"  ❌ Category mismatch - needs fixing")
                    
                    # Get the item record ID
                    item_id = await client._get_item_id_by_name(item.name)
                    if item_id:
                        print(f"  Updating category from '{current_category}' to '{expected_category}'...")
                        
                        # Update the category
                        try:
                            client.items_table.update(item_id, {"Category": expected_category})
                            print(f"  ✅ Category updated successfully")
                        except Exception as e:
                            print(f"  ❌ Failed to update category: {e}")
                    else:
                        print(f"  ❌ Could not find item ID for update")
                else:
                    print(f"  ✅ Category is already correct")
        
        print("\n✅ Category fix process completed")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fix_existing_categories())
