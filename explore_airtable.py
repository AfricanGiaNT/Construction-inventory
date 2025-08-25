#!/usr/bin/env python3
"""Airtable Base Exploration Script for Construction Inventory Bot."""

import os
import json
from typing import Dict, List, Any
from pyairtable import Api, Base
from pyairtable.formulas import match
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv('config/.env')

def explore_airtable_base(api_key: str, base_id: str):
    """Explore the Airtable base structure and content."""
    
    print("🔍 Exploring Airtable Base...")
    print("=" * 50)
    
    try:
        # Initialize API and base
        api = Api(api_key)
        base = api.base(base_id)
        
        # Get all tables in the base
        print("\n📋 AVAILABLE TABLES:")
        print("-" * 30)
        
        tables = base.tables()
        table_names = [table.name for table in tables]
        
        for i, table_name in enumerate(table_names, 1):
            print(f"{i}. {table_name}")
        
        print(f"\nTotal tables found: {len(table_names)}")
        
        # Explore each table in detail
        for table_name in table_names:
            explore_table(base, table_name)
            
    except Exception as e:
        print(f"❌ Error accessing Airtable: {e}")
        print("\nPlease check:")
        print("- Your API key is correct")
        print("- Your base ID is correct")
        print("- You have access to the base")

def explore_table(base: Base, table_name: str):
    """Explore a specific table and show its structure."""
    
    print(f"\n📊 TABLE: {table_name}")
    print("=" * 60)
    
    try:
        table = base.table(table_name)
        records = table.all(max_records=3)  # Get first 3 records for sample data
        
        if not records:
            print(f"   No records found in {table_name}")
            return
        
        print(f"   Records found: {len(records)} (showing first 3)")
        
        # Get the actual schema from Airtable
        try:
            schema = table.schema()
            fields = schema.fields
            print(f"\n   📝 FIELDS:")
            print("   " + "-" * 40)
            
            # Sort fields alphabetically
            sorted_fields = sorted([field.name for field in fields])
            
            for field_name in sorted_fields:
                # Find the field in schema to get its type
                field_obj = next((f for f in fields if f.name == field_name), None)
                if field_obj:
                    field_type = field_obj.type
                    print(f"   • {field_name:<30} ({field_type})")
                else:
                    print(f"   • {field_name:<30} (unknown)")
                    
        except Exception as schema_error:
            print(f"   ❌ Error getting schema: {schema_error}")
            # Fallback to inferring from sample data
            print(f"\n   📝 FIELDS (inferred from sample data):")
            print("   " + "-" * 40)
            
            # Get all unique field names from records
            all_fields = set()
            for record in records:
                all_fields.update(record["fields"].keys())
            
            sorted_fields = sorted(all_fields)
            
            for field_name in sorted_fields:
                field_type = get_field_type(records, field_name)
                print(f"   • {field_name:<30} ({field_type})")
        
        # Show sample data
        print(f"\n   📋 SAMPLE DATA:")
        print("   " + "-" * 40)
        
        for i, record in enumerate(records, 1):
            print(f"\n   Record {i}:")
            print(f"   ID: {record['id']}")
            
            for field_name in sorted_fields:
                if field_name in record["fields"]:
                    value = record["fields"][field_name]
                    # Truncate long values for readability
                    if isinstance(value, str) and len(value) > 50:
                        value = value[:47] + "..."
                    print(f"   {field_name}: {value}")
                else:
                    print(f"   {field_name}: (empty)")
        
        # Check for rollup fields (if this is the Items table)
        if table_name.lower() == "items":
            check_rollup_fields(base, table_name)
            
    except Exception as e:
        print(f"   ❌ Error exploring table {table_name}: {e}")

def get_field_type(records: List[Dict[str, Any]], field_name: str) -> str:
    """Determine the type of a field based on sample data."""
    
    types_found = set()
    
    for record in records:
        if field_name in record["fields"]:
            value = record["fields"][field_name]
            if value is None:
                types_found.add("null")
            elif isinstance(value, str):
                types_found.add("text")
            elif isinstance(value, (int, float)):
                types_found.add("number")
            elif isinstance(value, bool):
                types_found.add("boolean")
            elif isinstance(value, list):
                types_found.add("array")
            elif isinstance(value, dict):
                types_found.add("object")
            else:
                types_found.add(type(value).__name__)
    
    if not types_found:
        return "unknown"
    
    # Return the most common type, or multiple if mixed
    if len(types_found) == 1:
        return list(types_found)[0]
    else:
        return "mixed: " + ", ".join(sorted(types_found))

def check_rollup_fields(base: Base, table_name: str):
    """Check for rollup fields in the Items table."""
    
    print(f"\n   🔗 ROLLUP FIELDS CHECK:")
    print("   " + "-" * 40)
    
    try:
        # Look for common rollup field names
        rollup_patterns = ["on hand", "total", "sum", "count", "rollup"]
        
        table = base.table(table_name)
        records = table.all(max_records=1)
        
        if records:
            fields = records[0]["fields"]
            rollup_fields = []
            
            for field_name in fields.keys():
                field_lower = field_name.lower()
                if any(pattern in field_lower for pattern in rollup_patterns):
                    rollup_fields.append(field_name)
            
            if rollup_fields:
                print(f"   Potential rollup fields found:")
                for field in rollup_fields:
                    print(f"   • {field}")
            else:
                print("   No obvious rollup fields found")
                print("   (This is normal - rollups may have different names)")
        
    except Exception as e:
        print(f"   ❌ Error checking rollup fields: {e}")

def check_airtable_connectivity(api_key: str, base_id: str):
    """Test basic connectivity to Airtable."""
    
    print("🔌 Testing Airtable Connectivity...")
    print("=" * 50)
    
    try:
        api = Api(api_key)
        base = api.base(base_id)
        
        # Try to get table list
        tables = base.tables()
        print(f"✅ Successfully connected to base!")
        print(f"✅ Found {len(tables)} tables")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def check_stock_movements_table(api_key: str, base_id: str):
    """Check specifically for Project field in Stock Movements table."""
    
    print("\n🔍 Checking Stock Movements Table...")
    print("=" * 60)
    
    try:
        # Initialize API and base
        api = Api(api_key)
        base = api.base(base_id)
        
        # Get the Stock Movements table
        table = base.table("Stock Movements")
        
        # Get schema
        try:
            schema = table.schema()
            fields = schema.fields
            print(f"\n📝 STOCK MOVEMENTS FIELDS:")
            print("-" * 60)
            
            # Sort fields alphabetically
            sorted_fields = sorted([field.name for field in fields])
            
            # Check specifically for Project or similar fields
            project_fields = []
            location_fields = []
            
            for field_name in sorted_fields:
                # Find the field in schema to get its type
                field_obj = next((f for f in fields if f.name == field_name), None)
                if field_obj:
                    field_type = field_obj.type
                    print(f"• {field_name:<30} ({field_type})")
                    
                    # Check if this might be a project field
                    if "project" in field_name.lower():
                        project_fields.append(field_name)
                    
                    # Check if this might be a location field
                    if "location" in field_name.lower() or "from" in field_name.lower() or "to" in field_name.lower():
                        location_fields.append(field_name)
                        
            # Summary of findings
            print("\n📊 FIELD ANALYSIS:")
            print("-" * 60)
            
            if project_fields:
                print(f"✅ Project-related fields found: {', '.join(project_fields)}")
            else:
                print("❌ No Project field found. You need to add a 'Project' field to your Stock Movements table.")
            
            if location_fields:
                print(f"✅ Location-related fields found: {', '.join(location_fields)}")
            
            # Get a sample record to see actual data
            records = table.all(max_records=1)
            if records:
                print("\n📋 SAMPLE RECORD:")
                print("-" * 60)
                record = records[0]
                for field_name, value in record["fields"].items():
                    # Truncate long values for readability
                    if isinstance(value, str) and len(value) > 50:
                        value = value[:47] + "..."
                    print(f"{field_name}: {value}")
            
        except Exception as schema_error:
            print(f"❌ Error getting schema: {schema_error}")
            
    except Exception as e:
        print(f"❌ Error accessing Stock Movements table: {e}")
        print("Please check that the 'Stock Movements' table exists in your base.")

def main():
    """Main function to run the exploration."""
    
    print("🚀 Airtable Base Explorer for Construction Inventory Bot")
    print("=" * 70)
    
    # Get credentials from environment
    api_key = os.getenv("AIRTABLE_API_KEY")
    base_id = os.getenv("AIRTABLE_BASE_ID")
    
    print(f"🔑 API Key loaded: {'Yes' if api_key else 'No'}")
    print(f"🏢 Base ID loaded: {'Yes' if base_id else 'No'}")
    
    if not api_key:
        print("❌ AIRTABLE_API_KEY not found in environment!")
        print("Please check your .env file in the config/ directory")
        return
    
    if not base_id:
        print("❌ AIRTABLE_BASE_ID not found in environment!")
        print("Please check your .env file in the config/ directory")
        return
    
    print(f"\n🔑 API Key: {api_key[:10]}...{api_key[-4:]}")
    print(f"🏢 Base ID: {base_id}")
    
    # Test connectivity first
    if check_airtable_connectivity(api_key, base_id):
        # Check specifically for the Stock Movements table and Project field
        check_stock_movements_table(api_key, base_id)
        
        print("\n" + "=" * 70)
        print("🎉 Analysis complete!")
        
    else:
        print("\n❌ Cannot proceed without successful connection")

if __name__ == "__main__":
    main()
