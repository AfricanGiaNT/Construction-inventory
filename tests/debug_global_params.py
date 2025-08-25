"""Debug script for global parameters."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nlp_parser import NLPStockParser

def debug_global_params():
    """Debug global parameters parsing and application."""
    parser = NLPStockParser()
    
    # Test case 1: Newline format with entry-specific override
    text = "/in driver: Mr Longwe, from: chigumula office, project: Bridge Construction\ncement, 50 bags\nsteel bars, 100 pieces, by Mr Smith"
    
    print("=== Original Text ===")
    print(text)
    print("\n=== Parsing Global Parameters ===")
    global_params, remaining_text = parser.parse_global_parameters(text)
    print("Global Parameters:", global_params)
    print("Remaining Text:", remaining_text)
    
    print("\n=== Parsing Batch Entries ===")
    result = parser.parse_batch_entries(text, 123, "testuser")
    print("Format:", result.format)
    print("Global Parameters:", result.global_parameters)
    print("Total Entries:", result.total_entries)
    print("Valid Entries:", result.valid_entries)
    print("Is Valid:", result.is_valid)
    
    print("\n=== Movements ===")
    for i, movement in enumerate(result.movements):
        print(f"Movement {i+1}:")
        print(f"  Item: {movement.item_name}")
        print(f"  Quantity: {movement.quantity} {movement.unit}")
        print(f"  Driver: {movement.driver_name}")
        print(f"  From: {movement.from_location}")
        print(f"  To: {movement.to_location}")
        print(f"  Project: {movement.project}")
    
    print("\n=== Errors ===")
    for error in result.errors:
        print(f"- {error}")

if __name__ == "__main__":
    debug_global_params()
