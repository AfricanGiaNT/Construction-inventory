#!/usr/bin/env python3
"""Debug script to see actual Airtable field names and data."""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from airtable_client import AirtableClient
from config import Settings

async def debug_airtable_fields():
    """Debug the actual field names and data in Airtable."""
    try:
        print("Debugging Airtable field names and data...")
        
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
        
        # Get raw records to see actual field names
        print("\nGetting raw Airtable records...")
        raw_records = client.items_table.all()
        print(f"Found {len(raw_records)} raw records")
        
        if raw_records:
            print("\nFirst record structure:")
            first_record = raw_records[0]
            print(f"Record ID: {first_record['id']}")
            print("Fields:")
            for field_name, field_value in first_record['fields'].items():
                print(f"  '{field_name}': {field_value}")
            
            print("\nAll field names found:")
            all_field_names = set()
            for record in raw_records:
                all_field_names.update(record['fields'].keys())
            
            for field_name in sorted(all_field_names):
                print(f"  '{field_name}'")
        
        print("\n✅ Airtable field debugging completed")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_airtable_fields())
