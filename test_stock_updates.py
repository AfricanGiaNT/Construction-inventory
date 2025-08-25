#!/usr/bin/env python3
"""Test script to verify automatic stock updates are working."""

import sys
import os
import asyncio

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.airtable_client import AirtableClient
from src.schemas import StockMovement, MovementType, MovementStatus
from datetime import datetime

async def test_stock_updates():
    """Test automatic stock updates."""
    print("🧪 Testing Automatic Stock Updates")
    print("=" * 50)
    
    # Initialize client
    client = AirtableClient()
    
    try:
        # Test 1: Check current items
        print("\n1. 📋 Checking current items...")
        all_items = client.items_table.all()
        print(f"   Found {len(all_items)} items in table")
        
        for item in all_items[:3]:  # Show first 3 items
            fields = item['fields']
            print(f"   • {fields.get('Name', 'N/A')}: {fields.get('On Hand', 0)} {fields.get('Base Unit', 'N/A')}")
        
        # Test 2: Create a test movement
        print("\n2. 📝 Creating test movement...")
        test_movement = StockMovement(
            item_name="Test Cement",
            movement_type=MovementType.IN,
            quantity=50.0,
            unit="bags",
            signed_base_quantity=50.0,
            location="Warehouse",
            note="Test movement for stock update verification",
            status=MovementStatus.POSTED,
            user_id="123",
            user_name="TestUser",
            timestamp=datetime.utcnow(),
            driver_name="Test Driver",
            from_location="Test Supplier"
        )
        
        # Create the movement
        movement_id = await client.create_movement(test_movement)
        if movement_id:
            print(f"   ✅ Movement created: {movement_id}")
            
            # Check if stock was updated
            print("\n3. 🔍 Checking if stock was updated...")
            updated_item = await client.get_item("Test Cement")
            if updated_item:
                print(f"   ✅ Item found: {updated_item.name}")
                print(f"   📊 Stock: {updated_item.on_hand} {updated_item.base_unit}")
            else:
                print("   ❌ Item not found after movement")
        else:
            print("   ❌ Failed to create movement")
        
        # Test 3: Create another movement for existing item
        print("\n4. 📝 Creating movement for existing item...")
        if all_items:
            existing_item = all_items[0]
            item_name = existing_item['fields'].get('Name', 'Unknown')
            current_stock = existing_item['fields'].get('On Hand', 0)
            
            print(f"   Using existing item: {item_name} (current stock: {current_stock})")
            
            test_movement2 = StockMovement(
                item_name=item_name,
                movement_type=MovementType.IN,
                quantity=10.0,
                unit=existing_item['fields'].get('Base Unit', 'pieces'),
                signed_base_quantity=10.0,
                location="Test Location",
                note="Test movement for existing item",
                status=MovementStatus.POSTED,
                user_id="123",
                user_name="TestUser",
                timestamp=datetime.utcnow()
            )
            
            movement_id2 = await client.create_movement(test_movement2)
            if movement_id2:
                print(f"   ✅ Movement created: {movement_id2}")
                
                # Check updated stock
                updated_item2 = await client.get_item(item_name)
                if updated_item2:
                    print(f"   📊 Stock updated: {current_stock} → {updated_item2.on_hand}")
                else:
                    print("   ❌ Failed to get updated item")
            else:
                print("   ❌ Failed to create movement")
        
        print("\n🎉 Stock update testing complete!")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_stock_updates())
