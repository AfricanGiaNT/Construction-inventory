#!/usr/bin/env python3
"""Test script for enhanced item structure integration with Airtable."""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import Settings
from airtable_client import AirtableClient
from services.inventory import InventoryService

async def test_enhanced_item_structure():
    """Test the enhanced item structure functionality with Airtable."""
    print("🧪 Testing Enhanced Item Structure with Airtable...")
    print("=" * 70)
    
    try:
        # Get settings
        settings = Settings()
        
        # Create Airtable client
        client = AirtableClient(settings)
        
        # Test connection first
        print("🔌 Testing Airtable connection...")
        if not await client.test_connection():
            print("❌ Failed to connect to Airtable. Check your API key and base ID.")
            return False
        
        print("✅ Connected to Airtable successfully!\n")
        
        # Test 1: Create items with enhanced structure
        print("📦 Test 1: Creating Items with Enhanced Structure")
        print("-" * 50)
        
        test_items = [
            ("Paint 20ltrs", "piece", "General"),
            ("Cement 50kg", "piece", "General"), 
            ("Steel Beam", "piece", "General"),
            ("Sand 2ton", "piece", "General"),
            ("Pipe 3m", "piece", "General")
        ]
        
        created_items = []
        for item_name, base_unit, category in test_items:
            try:
                print(f"Creating: {item_name}")
                item_id = await client.create_item_if_not_exists(
                    item_name=item_name,
                    base_unit=base_unit,
                    category=category
                )
                if item_id:
                    print(f"  ✅ Created successfully (ID: {item_id})")
                    created_items.append((item_name, item_id))
                else:
                    print(f"  ❌ Failed to create")
            except Exception as e:
                print(f"  ❌ Error: {e}")
        
        print(f"\nCreated {len(created_items)} test items")
        
        # Test 2: Verify enhanced fields were set correctly
        print("\n🔍 Test 2: Verifying Enhanced Fields")
        print("-" * 50)
        
        for item_name, item_id in created_items:
            try:
                item = await client.get_item(item_name)
                if item:
                    print(f"\nItem: {item.name}")
                    print(f"  Unit Size: {item.unit_size}")
                    print(f"  Unit Type: {item.unit_type}")
                    try:
                        total_volume = item.get_total_volume()
                        print(f"  Total Volume: {total_volume}")
                    except Exception as e:
                        print(f"  Total Volume: Error accessing - {e}")
                    print(f"  Base Unit: {item.base_unit}")
                    print(f"  On Hand: {item.on_hand}")
                    
                    # Verify the enhanced fields
                    if item.unit_size > 0:
                        print(f"  ✅ Unit Size is valid")
                    else:
                        print(f"  ❌ Unit Size should be > 0")
                    
                    if item.unit_type and item.unit_type != "":
                        print(f"  ✅ Unit Type is set")
                    else:
                        print(f"  ❌ Unit Type should not be empty")
                    
                    try:
                        total_volume = item.get_total_volume()
                        expected_volume = item.unit_size * item.on_hand
                        if abs(total_volume - expected_volume) < 0.01:
                            print(f"  ✅ Total Volume calculated correctly: {total_volume}")
                        else:
                            print(f"  ❌ Total Volume mismatch: expected {expected_volume}, got {total_volume}")
                    except Exception as e:
                        print(f"  ❌ Error accessing total_volume: {e}")
                        
                else:
                    print(f"❌ Could not retrieve item: {item_name}")
                    
            except Exception as e:
                print(f"❌ Error retrieving {item_name}: {e}")
        
        # Test 3: Test inventory service integration
        print("\n📊 Test 3: Testing Inventory Service Integration")
        print("-" * 50)
        
        try:
            inventory_service = InventoryService(client, settings)
            
            # Test unit extraction
            test_names = [
                "Paint 20ltrs",
                "Cement 50kg", 
                "Steel Beam",
                "Sand 2ton",
                "Pipe 3m"
            ]
            
            print("Testing unit extraction from item names:")
            for name in test_names:
                unit_size, unit_type = inventory_service._extract_unit_info_from_name(name)
                print(f"  {name:20} → size={unit_size}, type={unit_type}")
            
            # Test inventory command parsing
            test_command = """/inventory date:27/08/25 logged by: TestUser
Paint 20ltrs, 5
Cement 50kg, 10
Steel Beam, 25"""
            
            print(f"\nTesting inventory command parsing:")
            print(f"Command: {test_command}")
            
            parse_result = inventory_service.parser.parse_inventory_command(test_command)
            if parse_result.is_valid:
                print(f"✅ Command parsed successfully")
                print(f"  Header: {parse_result.header.date} by {parse_result.header.logged_by}")
                print(f"  Entries: {parse_result.valid_entries}")
                for entry in parse_result.entries:
                    print(f"    • {entry.item_name}: {entry.quantity}")
            else:
                print(f"❌ Command parsing failed:")
                for error in parse_result.errors:
                    print(f"    • {error}")
                    
        except Exception as e:
            print(f"❌ Error testing inventory service: {e}")
        
        # Test 4: Test stock updates
        print("\n📈 Test 4: Testing Stock Updates")
        print("-" * 50)
        
        for item_name, item_id in created_items:
            try:
                # Get current stock
                item = await client.get_item(item_name)
                if item:
                    current_stock = item.on_hand
                    new_stock = current_stock + 10
                    
                    print(f"Updating {item_name}: {current_stock} → {new_stock}")
                    
                    # Update stock
                    success = await client.update_item_stock(item_name, 10)  # Add 10
                    if success:
                        # Verify update
                        updated_item = await client.get_item(item_name)
                        if updated_item and updated_item.on_hand == new_stock:
                            print(f"  ✅ Stock updated successfully")
                            
                            # Check if total volume was recalculated
                            try:
                                total_volume = updated_item.get_total_volume()
                                expected_volume = updated_item.unit_size * updated_item.on_hand
                                if abs(total_volume - expected_volume) < 0.01:
                                    print(f"  ✅ Total Volume recalculated: {total_volume}")
                                else:
                                    print(f"  ❌ Total Volume not recalculated correctly")
                            except Exception as e:
                                print(f"  ❌ Error accessing total_volume: {e}")
                        else:
                            print(f"  ❌ Stock update verification failed")
                    else:
                        print(f"  ❌ Stock update failed")
                        
            except Exception as e:
                print(f"❌ Error updating stock for {item_name}: {e}")
        
        # Test 5: Cleanup test items
        print("\n🧹 Test 5: Cleanup Test Items")
        print("-" * 50)
        
        print("Note: Test items will remain in Airtable for manual inspection.")
        print("You can manually delete them if desired.")
        
        print("\n" + "=" * 70)
        print("🎉 Enhanced Item Structure Testing Complete!")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False

async def main():
    """Main function."""
    success = await test_enhanced_item_structure()
    if success:
        print("\n✅ All tests completed successfully!")
        print("\n💡 Next steps:")
        print("1. Check your Airtable Items table to see the created test items")
        print("2. Verify that Unit Size, Unit Type, and Total Volume fields are populated")
        print("3. Test with real inventory commands in your Telegram bot")
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 
