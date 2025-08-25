#!/usr/bin/env python3
"""Test script for the NLP Stock Parser."""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from nlp_parser import NLPStockParser

def test_parser():
    """Test the NLP parser with various commands."""
    parser = NLPStockParser()
    
    test_cases = [
        # Stock IN - should extract "from_location"
        "/in diff water pump, 5 pieces, delivered by Mr longwe, from chigumula office",
        "/in cement, 100 bags, from main supplier, delivered by John",
        "/in steel bars, 30 pieces, from warehouse, by Mr Banda",
        
        # Stock OUT - should extract "to_location" 
        "/out diff water pump, 2 pieces, to site A, by Mr Longwe",
        "/out cement, 20 bags, to construction site, delivered by contractor",
        "/out steel bars, 15 pieces, to bridge project, by Mr Mhango",
        
        # Mixed formats
        "/in safety equipment, 10 pieces, from Lilongwe office, delivered by driver",
        "/out electrical wire, 50 meters, to office building, by electrician",
        
        # Complex scenarios
        "/in diff water pump- 5 pieces- delivered by Mr longwe- from chigumula office",
        "/out welding rods, 3 boxes, to site, Mr Banda, warehouse",
    ]
    
    print("🧪 Testing NLP Stock Parser with From/To Location Logic")
    print("=" * 60)
    print()
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"{i}. Testing: {test_case}")
        print("-" * 60)
        
        try:
            result = parser.parse_stock_command(test_case, 123, "TestUser")
            
            if result:
                print("✅ Parsed successfully!")
                print(f"   Item: {result.item_name}")
                print(f"   Type: {result.movement_type}")
                print(f"   Quantity: {result.quantity}")
                print(f"   Unit: {result.unit}")
                print(f"   Location: {result.location}")
                print(f"   Driver: {result.driver_name}")
                
                # Show location logic
                if result.movement_type.value == "In":
                    print(f"   From Location (source): {result.from_location}")
                    print(f"   To Location: {result.to_location}")
                else:
                    print(f"   From Location: {result.from_location}")
                    print(f"   To Location (destination): {result.to_location}")
                
                print(f"   Note: {result.note}")
            else:
                print("❌ Failed to parse")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print()
    
    print("🎉 NLP Parser testing complete!")

if __name__ == "__main__":
    test_parser()
