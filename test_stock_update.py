#!/usr/bin/env python3
"""Test script to verify stock movements update the Items table correctly."""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from airtable_client import AirtableClient
from config import Settings
from schemas import StockMovement, MovementType, MovementStatus
from datetime import datetime, UTC

async def test_stock_update():
    """Test that stock movements properly update the Items table."""
    try:
        print("Testing stock movement updates to Items table...")
        
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
        
        # Get current stock levels
        print("\nGetting current stock levels...")
        items_before = await client.get_all_items()
        print(f"Found {len(items_before)} items")
        
        # Find Steel Beam 6m to test with
        test_item = None
        for item in items_before:
            if "Steel Beam" in item.name:
                test_item = item
                break
        
        if not test_item:
            print("❌ Test item 'Steel Beam 6m' not found")
            return
        
        print(f"\nTest item: {test_item.name}")
        print(f"Current stock: {test_item.on_hand}")
        print(f"Category: {test_item.category}")
        print(f"Base Unit: {test_item.base_unit}")
        
        # Create a test stock movement
        print("\nCreating test stock movement...")
        test_movement = StockMovement(
            item_name=test_item.name,
            movement_type=MovementType.IN,
            quantity=5.0,
            unit="piece",
            signed_base_quantity=5.0,
            location=None,
            note="Test stock movement",
            status=MovementStatus.POSTED,
            user_id="123",
            user_name="Test User",
            timestamp=datetime.now(UTC),
            driver_name=None,
            from_location=None,
            to_location=None,
            project="Test Project"
        )
        
        # Create the movement
        movement_id = await client.create_movement(test_movement)
        if movement_id:
            print(f"✅ Movement created: {movement_id}")
        else:
            print("❌ Failed to create movement")
            return
        
        # Wait a moment for Airtable to update
        print("Waiting for Airtable to update...")
        await asyncio.sleep(2)
        
        # Check updated stock levels
        print("\nChecking updated stock levels...")
        items_after = await client.get_all_items()
        
        # Find the updated item
        updated_item = None
        for item in items_after:
            if "Steel Beam" in item.name:
                updated_item = item
                break
        
        if updated_item:
            print(f"Updated item: {updated_item.name}")
            print(f"New stock: {updated_item.on_hand}")
            print(f"Stock change: {test_item.on_hand} → {updated_item.on_hand}")
            
            if updated_item.on_hand == test_item.on_hand + 5.0:
                print("✅ Stock update successful!")
            else:
                print("❌ Stock update failed - quantity not updated correctly")
        else:
            print("❌ Could not find updated item")
        
        print("\n✅ Stock update test completed")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_stock_update())
