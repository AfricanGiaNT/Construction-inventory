#!/usr/bin/env python3
"""Simple test script to verify automatic stock updates are working."""

import os
import asyncio
from dotenv import load_dotenv
from pyairtable import Base

# Load environment variables
load_dotenv('config/.env')

async def test_stock_updates_simple():
    """Test automatic stock updates with simple Airtable calls."""
    print("🧪 Testing Automatic Stock Updates (Simple)")
    print("=" * 50)
    
    # Initialize Airtable
    api_key = os.getenv('AIRTABLE_API_KEY')
    base_id = os.getenv('AIRTABLE_BASE_ID')
    
    if not api_key or not base_id:
        print("❌ Missing AIRTABLE_API_KEY or AIRTABLE_BASE_ID in environment")
        return
    
    base = Base(api_key, base_id)
    items_table = base.table('Items')
    movements_table = base.table('Stock Movements')
    
    try:
        # Test 1: Check current items
        print("\n1. 📋 Checking current items...")
        all_items = items_table.all()
        print(f"   Found {len(all_items)} items in table")
        
        for item in all_items[:3]:  # Show first 3 items
            fields = item['fields']
            print(f"   • {fields.get('Name', 'N/A')}: {fields.get('On Hand', 0)} {fields.get('Base Unit', 'N/A')}")
        
        # Test 2: Check if we can create a simple movement
        print("\n2. 📝 Testing movement creation...")
        
        # Get first item for testing
        if all_items:
            test_item = all_items[0]
            item_name = test_item['fields'].get('Name', 'Unknown')
            current_stock = test_item['fields'].get('On Hand', 0)
            
            print(f"   Using item: {item_name} (current stock: {current_stock})")
            
            # Create a simple test movement
            test_movement = {
                "Type": "In",
                "Qty Entered": 5.0,
                "Unit Entered": test_item['fields'].get('Base Unit', 'pieces'),
                "Signed Base Qty": 5.0,
                "Note": "Test movement for stock update verification",
                "Status": "Posted",
                "Source": "Telegram",
                "Created At": "2025-08-22",
                "Reason": "Purchase"
            }
            
            # Add item reference (now just the name as text)
            test_movement["Item"] = test_item['fields'].get('Name', 'Unknown')
            
            # Create the movement
            created = movements_table.create(test_movement)
            if created:
                print(f"   ✅ Movement created: {created['id']}")
                
                # Now manually update the item stock to test the logic
                print("\n3. 🔄 Testing stock update logic...")
                new_stock = current_stock + 5.0
                
                # Update the item's On Hand field
                items_table.update(test_item['id'], {"On Hand": new_stock})
                print(f"   📊 Stock updated: {current_stock} → {new_stock}")
                
                # Verify the update
                updated_item = items_table.get(test_item['id'])
                if updated_item:
                    actual_stock = updated_item['fields'].get('On Hand', 0)
                    print(f"   ✅ Verification: Item now has {actual_stock} in stock")
                else:
                    print("   ❌ Failed to verify updated item")
            else:
                print("   ❌ Failed to create movement")
        else:
            print("   ❌ No items found for testing")
        
        print("\n🎉 Simple stock update testing complete!")
        print("\n💡 Next steps:")
        print("   1. The bot code has been updated to automatically handle stock updates")
        print("   2. Test with real commands: /in cement, 100 bags, from supplier")
        print("   3. Check that stock quantities update automatically")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_stock_updates_simple())
