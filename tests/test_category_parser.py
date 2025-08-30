"""Test script for the enhanced category parser."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from services.category_parser import category_parser


def test_category_parsing():
    """Test the category parser with various item names."""
    
    print("=== Testing Enhanced Category Parser ===\n")
    
    # Test cases from Phase 1 requirements
    test_items = [
        "Paint 20ltrs",
        "Copper Wire 100m", 
        "PVC Pipe 3m",
        "Hammer",
        "LED Bulb 10W",
        "Power Adapter",
        "Toilet Seat",
        "Plywood Sheet",
        "Safety Helmet",
        "Steel Beam",
        "Interior Paint 5ltrs",
        "Electrical Switch",
        "Plumbing Fitting",
        "Hand Tool Set",
        "Construction Cement 50kg",
        "Metal Sheet 2m",
        "Wood Screw 100pc",
        "Safety Gloves",
        "Fluorescent Tube 4ft",
        "Pipe Adapter 2inch"
    ]
    
    print("Testing Smart Category Detection:")
    print("-" * 60)
    
    for item_name in test_items:
        detected_category = category_parser.parse_category(item_name)
        print(f"✅ {item_name:<25} → {detected_category}")
    
    print("\n" + "=" * 60)
    
    # Test category listing
    print("\nAvailable Main Categories:")
    print("-" * 30)
    main_categories = category_parser.get_main_categories()
    for category in main_categories:
        print(f"• {category}")
    
    print("\n" + "=" * 60)
    
    # Test subcategory mappings
    print("\nHierarchical Categories Available:")
    print("-" * 40)
    all_categories = category_parser.get_all_categories()
    hierarchical_categories = [cat for cat in all_categories if ' > ' in cat]
    for category in hierarchical_categories:
        print(f"• {category}")
    
    print("\n" + "=" * 60)
    
    # Test category search
    print("\nTesting Category Search:")
    print("-" * 25)
    search_queries = ["paint", "electrical", "tools", "safety", "steel"]
    for query in search_queries:
        matches = category_parser.search_categories(query)
        print(f"Search '{query}': {', '.join(matches)}")
    
    print("\n" + "=" * 60)
    
    # Test priority rules
    print("\nTesting Priority Rules:")
    print("-" * 20)
    priority_test_items = [
        "Electrical Paint",  # Should prioritize Paint over Electrical
        "Power Tool",        # Should prioritize Tool over Power
        "Electrical Pipe",   # Should prioritize Pipe over Electrical
        "Safety Equipment"   # Should prioritize Safety over Equipment
    ]
    
    for item_name in priority_test_items:
        detected_category = category_parser.parse_category(item_name)
        print(f"🔍 {item_name:<20} → {detected_category}")
    
    print("\n" + "=" * 60)
    
    # Test validation
    print("\nTesting Category Validation:")
    print("-" * 25)
    test_categories = [
        "Paint",
        "Electrical > Cables",
        "CustomCategory",
        "invalid category",
        "",
        "Electrical > ",
        " > Cables"
    ]
    
    for category in test_categories:
        is_valid = category_parser.validate_category(category)
        status = "✅ Valid" if is_valid else "❌ Invalid"
        print(f"{status:<12} '{category}'")
    
    print("\n" + "=" * 60)
    
    # Test edge cases
    print("\nTesting Edge Cases:")
    print("-" * 18)
    edge_case_items = [
        "Multi-purpose Tool",
        "Custom Material XYZ",
        "12345",
        "",
        "The Great Paint",
        "Paint and More Paint"
    ]
    
    for item_name in edge_case_items:
        detected_category = category_parser.parse_category(item_name)
        print(f"🎯 {item_name:<25} → {detected_category}")
    
    print("\n" + "=" * 60)
    print("✅ Category Parser Testing Complete!")
    print("=" * 60)


if __name__ == "__main__":
    test_category_parsing()
