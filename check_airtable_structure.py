#!/usr/bin/env python3
"""Script to check Airtable table structure and identify missing fields."""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.append('src')

from config import Settings
from airtable_client import AirtableClient

async def check_airtable_structure():
    """Check the structure of both Airtable tables."""
    
    # Load configuration
    load_dotenv('config/.env')
    settings = Settings()
    
    # Initialize Airtable client
    airtable = AirtableClient(settings)
    
    print("🔍 Checking Airtable Table Structure...")
    print("=" * 50)
    
    try:
        # Check Items table structure
        print("\n📋 ITEMS TABLE STRUCTURE:")
        print("-" * 30)
        
        # Get raw fields from Airtable
        raw_items = airtable.items_table.all(max_records=1)
        if raw_items:
            fields = raw_items[0]['fields']
            print(f"Available fields in Items table:")
            for field_name, field_value in fields.items():
                field_type = type(field_value).__name__
                print(f"  ✅ {field_name} ({field_type})")
        else:
            print("  ⚠️  No items found in Items table")
        
        # Check Stock Movements table structure
        print("\n📦 STOCK MOVEMENTS TABLE STRUCTURE:")
        print("-" * 40)
        
        # Get raw fields from Airtable
        raw_movements = airtable.movements_table.all(max_records=1)
        if raw_movements:
            fields = raw_movements[0]['fields']
            print(f"Available fields in Stock Movements table:")
            for field_name, field_value in fields.items():
                field_type = type(field_value).__name__
                print(f"  ✅ {field_name} ({field_type})")
        else:
            print("  ⚠️  No stock movements found in Stock Movements table")
        
        # Check for required fields
        print("\n🔍 REQUIRED FIELD ANALYSIS:")
        print("-" * 30)
        
        # Items table required fields
        items_required_fields = [
            "Name", "Category", "Base Unit", "Unit Size", "Unit Type", 
            "On Hand", "Reorder Level", "Large Qty Threshold", 
            "Preferred Location", "Is Active", "Last Stocktake Date", "Last Stocktake By"
        ]
        
        # Stock Movements table required fields
        movements_required_fields = [
            "Item Name", "Movement Type", "Quantity", "Unit", "Signed Base Quantity",
            "Unit Size", "Unit Type", "Location", "Note", "Status", "User ID", 
            "User Name", "Timestamp", "Approved By", "Approved At", "Reason",
            "Source", "Driver Name", "From Location", "To Location", "Project", "Batch ID"
        ]
        
        print("\n📋 Items Table Required Fields:")
        if raw_items:
            existing_fields = set(raw_items[0]['fields'].keys())
            for field in items_required_fields:
                if field in existing_fields:
                    print(f"  ✅ {field}")
                else:
                    print(f"  ❌ {field} - MISSING")
        else:
            print("  ⚠️  Cannot check Items table fields")
        
        print("\n📦 Stock Movements Table Required Fields:")
        if raw_movements:
            existing_fields = set(raw_movements[0]['fields'].keys())
            for field in movements_required_fields:
                if field in existing_fields:
                    print(f"  ✅ {field}")
                else:
                    print(f"  ❌ {field} - MISSING")
        else:
            print("  ⚠️  Cannot check Stock Movements table fields")
        
        # Check if Category field exists in both tables
        print("\n🎯 CATEGORY FIELD STATUS:")
        print("-" * 30)
        
        items_has_category = False
        movements_has_category = False
        
        if raw_items:
            items_has_category = "Category" in raw_items[0]['fields']
            print(f"Items Table Category field: {'✅ EXISTS' if items_has_category else '❌ MISSING'}")
        
        if raw_movements:
            movements_has_category = "Category" in raw_movements[0]['fields']
            print(f"Stock Movements Table Category field: {'✅ EXISTS' if movements_has_category else '❌ MISSING'}")
        
        # Recommendations
        print("\n💡 RECOMMENDATIONS:")
        print("-" * 20)
        
        if not items_has_category:
            print("  🔧 Add 'Category' field to Items table (Single Select type)")
        
        if not movements_has_category:
            print("  🔧 Add 'Category' field to Stock Movements table (Single Select type)")
        
        if items_has_category and movements_has_category:
            print("  ✅ Both Category fields exist - ready for enhanced functionality!")
            print("  🧪 Test with: /inventory date:27/08/25 logged by: TestUser")
            print("              Paint 20ltrs, 5")
        
        print("\n" + "=" * 50)
        
    except Exception as e:
        print(f"❌ Error checking Airtable structure: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_airtable_structure())
