#!/usr/bin/env python3
"""Test script to verify Airtable connection and basic functionality."""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Load environment variables
from dotenv import load_dotenv
load_dotenv('config/.env')

async def test_connection():
    """Test basic Airtable connection and functionality."""
    
    print("🧪 Testing Airtable Connection and Basic Functionality")
    print("=" * 60)
    
    try:
        # Test environment variables
        print("0. Checking environment variables...")
        api_key = os.getenv("AIRTABLE_API_KEY")
        base_id = os.getenv("AIRTABLE_BASE_ID")
        
        if not api_key or not base_id:
            print("   ❌ Missing environment variables")
            print(f"   API Key: {'Set' if api_key else 'Missing'}")
            print(f"   Base ID: {'Set' if base_id else 'Missing'}")
            return
        
        print("   ✅ Environment variables loaded")
        print(f"   API Key: {api_key[:10]}...{api_key[-4:]}")
        print(f"   Base ID: {base_id}")
        
        # Test direct Airtable connection
        print("\n1. Testing direct Airtable connection...")
        from pyairtable import Api, Base
        
        api = Api(api_key)
        base = api.base(base_id)
        
        # Get tables
        tables = base.tables()
        print(f"   ✅ Connected to Airtable base")
        print(f"   Tables found: {len(tables)}")
        for table in tables:
            print(f"      - {table.name}")
        
        # Test getting an item
        print("\n2. Testing item retrieval...")
        items_table = base.table("Items")
        test_sku = "STL-101"  # Using the SKU from your sample data
        
        formula = f"{{SKU}} = '{test_sku}'"
        records = items_table.all(formula=formula)
        
        if records:
            record = records[0]
            print(f"   ✅ Item found: {record['fields'].get('Name', 'Unknown')}")
            print(f"      SKU: {record['fields'].get('SKU', 'Unknown')}")
            print(f"      Base Unit: {record['fields'].get('Base Unit', 'Unknown')}")
            print(f"      On Hand: {record['fields'].get('On Hand', 'Unknown')}")
            print(f"      Category: {record['fields'].get('Category', 'Unknown')}")
            print(f"      Large Qty Threshold: {record['fields'].get('Large Qty Threshold', 'Unknown')}")
        else:
            print(f"   ❌ Item not found: {test_sku}")
            return
        
        # Test searching items
        print("\n3. Testing item search...")
        all_items = items_table.all(max_records=5)
        print(f"   ✅ Sample items:")
        for record in all_items:
            print(f"      - {record['fields'].get('SKU', 'Unknown')}: {record['fields'].get('Name', 'Unknown')}")
        
        # Test getting low stock items
        print("\n4. Testing low stock items...")
        low_stock_items = []
        for record in all_items:
            on_hand = record['fields'].get('On Hand', 0)
            reorder_level = record['fields'].get('Reorder Level')
            if reorder_level and on_hand <= reorder_level:
                low_stock_items.append(record['fields'].get('SKU', 'Unknown'))
        
        print(f"   ✅ Low stock items: {len(low_stock_items)} found")
        for item_sku in low_stock_items[:5]:
            print(f"      - {item_sku}")
        
        # Test getting pending approvals
        print("\n5. Testing pending approvals...")
        movements_table = base.table("Stock Movements")
        pending_formula = "{Status} = 'Requested'"
        pending_records = movements_table.all(formula=pending_formula, max_records=3)
        
        print(f"   ✅ Pending approvals: {len(pending_records)} found")
        for record in pending_records:
            qty = record['fields'].get('Qty Entered', 'Unknown')
            unit = record['fields'].get('Unit Entered', 'Unknown')
            print(f"      - {qty} {unit}")
        
        # Test daily movements
        print("\n6. Testing daily movements...")
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        today_formula = f"{{Created At}} = '{today}'"
        today_movements = movements_table.all(formula=today_formula)
        
        total_in = 0
        total_out = 0
        for record in today_movements:
            if record['fields'].get('Status') == 'Posted':
                qty = record['fields'].get('Signed Base Qty', 0)
                if record['fields'].get('Type') == 'In':
                    total_in += qty
                elif record['fields'].get('Type') == 'Out':
                    total_out += qty
        
        print(f"   ✅ Daily movements for {today}:")
        print(f"      Total In: {total_in}")
        print(f"      Total Out: {total_out}")
        print(f"      Count: {len(today_movements)}")
        
        print("\n🎉 All tests completed successfully!")
        print("\nYour Airtable integration is working correctly!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_connection())
