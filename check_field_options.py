#!/usr/bin/env python3
"""Script to check field options for Single select fields in both tables."""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.append('src')

from config import Settings
from airtable_client import AirtableClient

async def check_field_options():
    """Check field options for Single select fields in both tables."""
    
    # Load configuration
    load_dotenv('config/.env')
    settings = Settings()
    
    # Initialize Airtable client
    airtable = AirtableClient(settings)
    
    print("🔍 Checking Field Options for Single Select Fields...")
    print("=" * 60)
    
    try:
        # Check Items table field options
        print("\n📋 ITEMS TABLE - Field Options:")
        print("-" * 40)
        
        # Get Items table metadata to see field types and options
        items_metadata = airtable.items_table.schema()
        if items_metadata:
            print("Items table schema found:")
            for field in items_metadata.fields:
                field_name = field.name
                field_type = field.type
                
                if field_type == 'singleSelect':
                    print(f"  📝 {field_name} (Single Select):")
                    if hasattr(field, 'options') and field.options:
                        choices = field.options.choices if hasattr(field.options, 'choices') else []
                        if choices:
                            for choice in choices:
                                print(f"    ✅ {choice.name}")
                        else:
                            print("    ⚠️  No options defined")
                    else:
                        print("    ⚠️  No options defined")
                else:
                    print(f"  📝 {field_name} ({field_type})")
        else:
            print("  ⚠️  Could not retrieve Items table schema")
        
        # Check Stock Movements table field options
        print("\n📦 STOCK MOVEMENTS TABLE - Field Options:")
        print("-" * 50)
        
        # Get Stock Movements table metadata to see field types and options
        movements_metadata = airtable.movements_table.schema()
        if movements_metadata:
            print("Stock Movements table schema found:")
            for field in movements_metadata.fields:
                field_name = field.name
                field_type = field.type
                
                if field_type == 'singleSelect':
                    print(f"  📝 {field_name} (Single Select):")
                    if hasattr(field, 'options') and field.options:
                        choices = field.options.choices if hasattr(field.options, 'choices') else []
                        if choices:
                            for choice in choices:
                                print(f"    ✅ {choice.name}")
                        else:
                            print("    ⚠️  No options defined")
                    else:
                        print("    ⚠️  No options defined")
                else:
                    print(f"  📝 {field_name} ({field_type})")
        else:
            print("  ⚠️  Could not retrieve Stock Movements table schema")
        
        # Alternative approach: check field types from data
        print("\n🔍 ALTERNATIVE: Checking Field Types from Data:")
        print("-" * 50)
        
        # Check Items table
        print("\n📋 Items Table - Field Types from Data:")
        raw_items = airtable.items_table.all(max_records=5)
        if raw_items:
            fields = raw_items[0]['fields']
            for field_name, field_value in fields.items():
                field_type = type(field_value).__name__
                print(f"  📝 {field_name}: {field_type}")
                
                # Check if it might be a Single select
                if field_type == 'str' and field_name in ['Category', 'Status', 'Type']:
                    # Get unique values to see if it's constrained
                    unique_values = set()
                    for item in raw_items:
                        if field_name in item['fields']:
                            unique_values.add(item['fields'][field_name])
                    
                    if len(unique_values) <= 20:  # Likely a Single select
                        print(f"    🔍 {field_name} appears to be constrained to: {sorted(unique_values)}")
        
        # Check Stock Movements table
        print("\n📦 Stock Movements Table - Field Types from Data:")
        raw_movements = airtable.movements_table.all(max_records=5)
        if raw_movements:
            fields = raw_movements[0]['fields']
            for field_name, field_value in fields.items():
                field_type = type(field_value).__name__
                print(f"  📝 {field_name}: {field_type}")
                
                # Check if it might be a Single select
                if field_type == 'str' and field_name in ['Type', 'Status', 'Source']:
                    # Get unique values to see if it's constrained
                    unique_values = set()
                    for movement in raw_movements:
                        if field_name in movement['fields']:
                            unique_values.add(movement['fields'][field_name])
                    
                    if len(unique_values) <= 20:  # Likely a Single select
                        print(f"    🔍 {field_name} appears to be constrained to: {sorted(unique_values)}")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"❌ Error checking field options: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_field_options())
