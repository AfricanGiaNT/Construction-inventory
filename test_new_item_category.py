#!/usr/bin/env python3
"""Test script to verify that new items get correct categories automatically."""

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

async def test_new_item_category():
    """Test that new items get correct categories automatically."""
    try:
        print("Testing automatic category detection for new items...")
        
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
        
        # Test item that should auto-detect category
        test_item_name = "Test Paint 20ltrs Can"
        
        # Check if item already exists
        existing_item = await client.get_item(test_item_name)
        if existing_item:
            print(f"❌ Test item '{test_item_name}' already exists. Please delete it first or use a different name.")
            return
        
        print(f"\nTesting with new item: {test_item_name}")
        print("Expected category: Paint (based on 'paint' in name)")
        
        # Create a test stock movement
        print("\nCreating test stock movement...")
        test_movement = StockMovement(
            item_name=test_item_name,
            movement_type=MovementType.IN,
            quantity=5.0,
            unit="bag",
            signed_base_quantity=5.0,
            location=None,
            note="Test category detection",
            status=MovementStatus.POSTED,
            user_id="123",
            user_name="Test User",
            timestamp=datetime.now(UTC),
            driver_name=None,
            from_location=None,
            to_location=None,
            project="Test Project"
        )
        
        # Create the movement (this should auto-create the item with correct category)
        movement_id = await client.create_movement(test_movement)
        if movement_id:
            print(f"✅ Movement created: {movement_id}")
            
            # Wait a moment for Airtable to update
            print("Waiting for Airtable to update...")
            await asyncio.sleep(2)
            
            # Check if the item was created with correct category
            created_item = await client.get_item(test_item_name)
            if created_item:
                print(f"\n✅ Item created successfully!")
                print(f"  Name: {created_item.name}")
                print(f"  Category: {created_item.category}")
                print(f"  Base Unit: {created_item.base_unit}")
                print(f"  Stock: {created_item.on_hand}")
                
                if created_item.category == "Cement":
                    print("✅ Category detection working correctly!")
                else:
                    print(f"❌ Category detection failed. Expected 'Cement', got '{created_item.category}'")
            else:
                print("❌ Item was not created")
        else:
            print("❌ Failed to create movement")
        
        print("\n✅ New item category test completed")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_new_item_category())
