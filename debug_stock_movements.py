#!/usr/bin/env python3
"""Debug script to see actual field names in Stock Movements table."""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from airtable_client import AirtableClient
from config import Settings

async def debug_stock_movements():
    """Debug the actual field names in Stock Movements table."""
    try:
        print("Debugging Stock Movements table field names...")
        
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
        
        # Get raw records from Stock Movements table
        print("\nGetting raw Stock Movements records...")
        raw_records = client.movements_table.all()
        print(f"Found {len(raw_records)} movement records")
        
        if raw_records:
            print("\nFirst movement record structure:")
            first_record = raw_records[0]
            print(f"Record ID: {first_record['id']}")
            print("Fields:")
            for field_name, field_value in first_record['fields'].items():
                print(f"  '{field_name}': {field_value}")
            
            print("\nAll field names found in Stock Movements:")
            all_field_names = set()
            for record in raw_records:
                all_field_names.update(record['fields'].keys())
            
            for field_name in sorted(all_field_names):
                print(f"  '{field_name}'")
        
        print("\n✅ Stock Movements field debugging completed")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_stock_movements())
