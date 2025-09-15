#!/usr/bin/env python3
"""Debug script to check what tables and data exist."""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from airtable_client import AirtableClient
from config import Settings

async def debug_tables():
    """Debug tables and data in the database."""
    print("Debugging tables and data...")
    
    # Initialize services
    settings = Settings()
    airtable_client = AirtableClient(settings)
    
    try:
        # Check Items table
        print("Checking Items table...")
        items = airtable_client.items_table.all(max_records=5)
        print(f"Found {len(items)} items")
        
        if items:
            print("\nSample item:")
            sample_item = items[0]
            print(f"Item ID: {sample_item['id']}")
            print(f"Fields: {list(sample_item['fields'].keys())}")
            print(f"Item name: {sample_item['fields'].get('Name', 'N/A')}")
        
        # Check if the specific item exists
        print(f"\nLooking for 'CAT Serial 1201817 HYDROLIC filter'...")
        item = await airtable_client.get_item("CAT Serial 1201817 HYDROLIC filter")
        if item:
            print(f"Found item: {item.name} (ID: {item.id})")
            print(f"Category: {item.category}")
            print(f"On hand: {item.on_hand}")
        else:
            print("Item not found")
            
        # Check all tables
        print("\nChecking all available tables...")
        tables = [
            ("Items", airtable_client.items_table),
            ("Stock Movements", airtable_client.movements_table),
            ("Telegram Users", airtable_client.users_table),
            ("Item Units", airtable_client.units_table),
            ("Locations", airtable_client.locations_table),
            ("People", airtable_client.people_table),
            ("Bot Meta", airtable_client.bot_meta_table),
            ("Stocktakes", airtable_client.stocktakes_table),
        ]
        
        for table_name, table in tables:
            try:
                records = table.all(max_records=3)
                print(f"{table_name}: {len(records)} records")
                if records and table_name == "Stock Movements":
                    print(f"  Sample fields: {list(records[0]['fields'].keys())}")
            except Exception as e:
                print(f"{table_name}: Error - {e}")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_tables())
