#!/usr/bin/env python3
"""Script to inspect Airtable tables and fields for enhanced item structure implementation."""

import asyncio
import os
import sys
from typing import Dict, List, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import Settings
from airtable_client import AirtableClient

async def inspect_airtable_fields():
    """Inspect all Airtable tables and their fields."""
    print("🔍 Inspecting Airtable Tables and Fields...")
    print("=" * 60)
    
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
        
        # Get all tables in the base
        print("📋 Available Tables:")
        print("-" * 30)
        
        # List of expected tables based on the codebase
        expected_tables = [
            "Items",
            "Stock Movements", 
            "Telegram Users",
            "Item Units",
            "Locations",
            "People",
            "Bot Meta",
            "Stocktakes"
        ]
        
        # Get table metadata
        base = client.base
        tables = base.tables()
        
        print(f"Found {len(tables)} tables in base:")
        for table in tables:
            print(f"  • {table.name}")
        
        print(f"\nExpected tables: {len(expected_tables)}")
        for table_name in expected_tables:
            if any(t.name == table_name for t in tables):
                print(f"  ✅ {table_name}")
            else:
                print(f"  ❌ {table_name} (MISSING)")
        
        # Inspect each table's fields by getting sample records
        print("\n" + "=" * 60)
        print("📊 DETAILED FIELD INSPECTION")
        print("=" * 60)
        
        for table in tables:
            print(f"\n🔍 Table: {table.name}")
            print("-" * 40)
            
            try:
                # Get a sample record to see the fields
                records = table.all(max_records=1)
                if records:
                    sample_record = records[0]
                    fields = sample_record.get('fields', {})
                    
                    print(f"Fields: {len(fields)}")
                    for field_name, field_value in fields.items():
                        # Determine field type from the value
                        if isinstance(field_value, list):
                            if field_value and isinstance(field_value[0], str):
                                field_type = "linkedRecord"
                            else:
                                field_type = "multipleSelect"
                        elif isinstance(field_value, bool):
                            field_type = "checkbox"
                        elif isinstance(field_value, (int, float)):
                            field_type = "number"
                        elif isinstance(field_value, str):
                            field_type = "singleLineText"
                        else:
                            field_type = "unknown"
                        
                        print(f"  • {field_name} ({field_type})")
                        if field_type == "linkedRecord" and field_value:
                            print(f"    Sample value: {field_value[:2]}...")  # Show first 2 linked records
                        elif field_type != "linkedRecord":
                            print(f"    Sample value: {field_value}")
                
            except Exception as e:
                print(f"  ❌ Error inspecting table: {e}")
        
        # Specific analysis for Items table
        print("\n" + "=" * 60)
        print("🎯 ENHANCED ITEM STRUCTURE ANALYSIS")
        print("=" * 60)
        
        try:
            items_table = client.items_table
            records = items_table.all(max_records=1)
            
            if records:
                sample_record = records[0]
                fields = sample_record.get('fields', {})
                
                print(f"\n📦 Items Table Analysis:")
                print("-" * 30)
                
                # Check for required fields
                required_fields = {
                    "Unit Size": "number",
                    "Unit Type": "singleSelect", 
                    "Base Unit": "singleSelect"
                }
                
                existing_fields = {}
                for field_name, field_value in fields.items():
                    # Determine field type from the value
                    if isinstance(field_value, list):
                        if field_value and isinstance(field_value[0], str):
                            existing_fields[field_name] = "linkedRecord"
                        else:
                            existing_fields[field_name] = "multipleSelect"
                    elif isinstance(field_value, bool):
                        existing_fields[field_name] = "checkbox"
                    elif isinstance(field_value, (int, float)):
                        existing_fields[field_name] = "number"
                    elif isinstance(field_value, str):
                        existing_fields[field_name] = "singleSelect"  # Assume it's a select field
                    else:
                        existing_fields[field_name] = "unknown"
                
                print("Required fields for enhanced item structure:")
                for field_name, field_type in required_fields.items():
                    if field_name in existing_fields:
                        current_type = existing_fields[field_name]
                        if current_type == field_type:
                            print(f"  ✅ {field_name} ({field_type}) - Correct type")
                        else:
                            print(f"  ⚠️  {field_name} ({current_type}) - Expected {field_type}")
                    else:
                        print(f"  ❌ {field_name} ({field_type}) - MISSING")
                
                # Check for Total Volume field (should be auto-calculated)
                if "Total Volume" in existing_fields:
                    print(f"  ✅ Total Volume field exists ({existing_fields['Total Volume']})")
                else:
                    print(f"  ❌ Total Volume field - MISSING (should be auto-calculated)")
                
                # Show current field types
                print(f"\nCurrent Items table fields:")
                for field_name, field_type in existing_fields.items():
                    print(f"  • {field_name} ({field_type})")
                    
        except Exception as e:
            print(f"❌ Error analyzing Items table: {e}")
        
        # Recommendations
        print("\n" + "=" * 60)
        print("💡 RECOMMENDATIONS")
        print("=" * 60)
        
        print("\n1. Add these fields to the Items table:")
        print("   • Unit Size (Number) - Size of each unit (e.g., 20 for 20ltr cans)")
        print("   • Unit Type (Single Select) - Type of unit (e.g., 'ltrs', 'kg', 'm', 'piece')")
        print("   • Total Volume (Number) - Auto-calculated field (Unit Size × On Hand)")
        
        print("\n2. Update Base Unit field:")
        print("   • Ensure it's a Single Select field")
        print("   • Add common unit options: piece, ltrs, kg, m, ton, bag")
        
        print("\n3. Field validation:")
        print("   • Unit Size: Must be > 0")
        print("   • Unit Type: Must not be empty")
        print("   • Total Volume: Auto-calculated formula: {Unit Size} * {On Hand}")
        
        print("\n4. Default values for existing items:")
        print("   • Unit Size: 1.0")
        print("   • Unit Type: 'piece'")
        print("   • Total Volume: Will be calculated automatically")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during inspection: {e}")
        return False

async def main():
    """Main function."""
    success = await inspect_airtable_fields()
    if success:
        print("\n🎉 Field inspection completed successfully!")
    else:
        print("\n❌ Field inspection failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 
