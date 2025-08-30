#!/usr/bin/env python3
"""Test script for enhanced item structure functionality."""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import after adding to path
from services.inventory import InventoryService

async def test_enhanced_item_structure():
    """Test the enhanced item structure functionality."""
    print("🧪 Testing Enhanced Item Structure...")
    
    # Create a mock inventory service (without real Airtable client)
    service = InventoryService(None, None)
    
    # Test cases for unit extraction
    test_cases = [
        ("Paint 20ltrs", (20.0, "ltrs")),
        ("Cement 50kg", (50.0, "kg")),
        ("Steel Beam", (1.0, "piece")),
        ("Sand 2ton", (2.0, "ton")),
        ("Pipe 3m", (3.0, "m")),
        ("Bags 25bag", (25.0, "bag")),
        ("Paint 5ltr", (5.0, "ltrs")),  # Should map to ltrs
        ("Cement 100kgs", (100.0, "kg")),  # Should map to kg
        ("Steel 10pieces", (10.0, "piece")),  # Should map to piece
    ]
    
    print("\n📋 Testing Unit Extraction from Item Names:")
    print("-" * 50)
    
    all_passed = True
    for item_name, expected in test_cases:
        result = service._extract_unit_info_from_name(item_name)
        status = "✅" if result == expected else "❌"
        print(f"{status} {item_name:20} → {result} (expected: {expected})")
        
        if result != expected:
            all_passed = False
            print(f"    Expected: {expected}, Got: {result}")
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All tests passed! Enhanced item structure is working correctly.")
    else:
        print("❌ Some tests failed. Please check the implementation.")
    
    return all_passed

if __name__ == "__main__":
    # Run the test
    success = asyncio.run(test_enhanced_item_structure())
    sys.exit(0 if success else 1)
