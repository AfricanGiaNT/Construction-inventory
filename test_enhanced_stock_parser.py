#!/usr/bin/env python3
"""Test script for Phase 1: Enhanced Command Parsing of the Enhanced Stock Movements System."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.services.enhanced_stock_parser import (
    EnhancedStockCommandParser, 
    InCommandParseResult, 
    OutCommandParseResult
)


def test_phase1_command_parsing():
    """Test enhanced command parsing functionality."""
    
    print("🧪 Testing Phase 1: Enhanced Command Parsing")
    print("=" * 60)
    
    # Initialize the parser
    parser = EnhancedStockCommandParser()
    
    # Test 1: IN command parsing
    print("\n📥 Test 1: IN Command Parsing")
    print("-" * 40)
    
    test_in_command = """
    /in project: Site A, driver: John; Paint 20ltrs, 5
    Copper Wire 100m, 2
    HDPE Pipe 250mm 3/4, 5
    Red Electric Wire 50 meters, 3
    """
    
    print(f"Input: {test_in_command.strip()}")
    result = parser.parse_in_command(test_in_command)
    
    print(f"✅ Valid: {result.is_valid}")
    print(f"📋 Project: {result.project}")
    print(f"🚗 Driver: {result.driver}")
    print(f"📍 From Location: {result.from_location}")
    print(f"📦 Items: {len(result.items)}")
    
    for i, item in enumerate(result.items, 1):
        print(f"  {i}. {item['name']} - {item['quantity']} {item['unit']}")
        print(f"     Category: {item['category']}")
        print(f"     Unit Size: {item['unit_size']}, Unit Type: {item['unit_type']}")
        if item['note']:
            print(f"     Note: {item['note']}")
    
    if result.errors:
        print(f"❌ Errors: {result.errors}")
    
    # Test 2: OUT command parsing
    print("\n📤 Test 2: OUT Command Parsing")
    print("-" * 40)
    
    test_out_command = """
    /out project: Site A, to: Site B, driver: John; Paint 20ltrs, 3
    Copper Wire 100m, 1
    """
    
    print(f"Input: {test_out_command.strip()}")
    result = parser.parse_out_command(test_out_command)
    
    print(f"✅ Valid: {result.is_valid}")
    print(f"📋 Project: {result.project}")
    print(f"🎯 To Location: {result.to_location}")
    print(f"🚗 Driver: {result.driver}")
    print(f"📦 Items: {len(result.items)}")
    
    for i, item in enumerate(result.items, 1):
        print(f"  {i}. {item['name']} - {item['quantity']} {item['unit']}")
        print(f"     Category: {item['category']}")
        print(f"     Unit Size: {item['unit_size']}, Unit Type: {item['unit_type']}")
        if item['note']:
            print(f"     Note: {item['note']}")
    
    if result.errors:
        print(f"❌ Errors: {result.errors}")
    
    # Test 3: Parameter extraction
    print("\n🔍 Test 3: Parameter Extraction")
    print("-" * 40)
    
    test_params = [
        "project: Bridge Project, driver: Mr Longwe",
        "driver: John, from: Supplier Warehouse",
        "to: Site C, project: Road Construction",
        "project: Office Building, driver: Sarah, to: Warehouse"
    ]
    
    for test_param in test_params:
        print(f"Input: {test_param}")
        params = parser._extract_parameters(test_param)
        print(f"Extracted: {params}")
        print()
    
    # Test 4: Item parsing edge cases
    print("\n🔧 Test 4: Item Parsing Edge Cases")
    print("-" * 40)
    
    edge_case_items = [
        "Paint 20ltrs, 5",
        "Steel Bars 50mm, 10 pieces",
        "Cement, 100 bags, delivered today",
        "Safety Equipment, 25 sets, from office",
        "HDPE Pipe 250mm 3/4, 5, urgent delivery"
    ]
    
    for item_text in edge_case_items:
        print(f"Input: {item_text}")
        parsed = parser._parse_single_item(item_text)
        if parsed:
            print(f"✅ Parsed: {parsed['name']} - {parsed['quantity']} {parsed['unit']}")
            print(f"   Category: {parsed['category']}")
            print(f"   Unit Size: {parsed['unit_size']}, Unit Type: {parsed['unit_type']}")
            if parsed['note']:
                print(f"   Note: {parsed['note']}")
        else:
            print(f"❌ Failed to parse")
        print()
    
    # Test 5: Unit extraction
    print("\n📏 Test 5: Unit Extraction")
    print("-" * 40)
    
    unit_test_items = [
        "Paint 20ltrs",
        "Copper Wire 100m",
        "HDPE Pipe 250mm 3/4",
        "Red Electric Wire 50 meters",
        "Steel Bars 50mm",
        "Cement 25kg bags",
        "Safety Helmets 10 pieces"
    ]
    
    for item_name in unit_test_items:
        unit_size, unit_type = parser._extract_unit_info(item_name)
        print(f"Item: {item_name}")
        print(f"  Unit Size: {unit_size}, Unit Type: {unit_type}")
    
    # Test 6: Validation errors
    print("\n⚠️ Test 6: Validation Errors")
    print("-" * 40)
    
    # Test missing destination for OUT command
    invalid_out = "/out project: Site A, driver: John; Paint 20ltrs, 5"
    print(f"Input: {invalid_out}")
    result = parser.parse_out_command(invalid_out)
    print(f"Valid: {result.is_valid}")
    if result.errors:
        print(f"Errors: {result.errors}")
    
    # Test empty command
    empty_command = "/in"
    print(f"\nInput: {empty_command}")
    result = parser.parse_in_command(empty_command)
    print(f"Valid: {result.is_valid}")
    if result.errors:
        print(f"Errors: {result.errors}")
    
    print("\n" + "=" * 60)
    print("🎯 Phase 1 Testing Complete!")
    print("=" * 60)


if __name__ == "__main__":
    test_phase1_command_parsing()

