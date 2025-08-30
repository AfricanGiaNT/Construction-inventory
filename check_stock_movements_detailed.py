#!/usr/bin/env python3
"""Script to check Stock Movements table structure in detail."""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.append('src')

from config import Settings
from airtable_client import AirtableClient

async def check_stock_movements_detailed():
    """Check the Stock Movements table structure in detail."""
    
    # Load configuration
    load_dotenv('config/.env')
    settings = Settings()
    
    # Initialize Airtable client
    airtable = AirtableClient(settings)
    
    print("🔍 Detailed Stock Movements Table Analysis...")
    print("=" * 60)
    
    try:
        # Get multiple records to see field variations
        raw_movements = airtable.movements_table.all(max_records=5)
        
        if raw_movements:
            print(f"📦 Found {len(raw_movements)} stock movement records")
            print("\n" + "=" * 60)
            
            # Analyze each record
            for i, record in enumerate(raw_movements, 1):
                print(f"\n📋 RECORD #{i}:")
                print("-" * 30)
                
                fields = record['fields']
                for field_name, field_value in fields.items():
                    field_type = type(field_value).__name__
                    
                    # Handle different field types
                    if field_type == 'list':
                        if field_value:
                            print(f"  ✅ {field_name} (list): {field_value}")
                        else:
                            print(f"  ✅ {field_name} (list): [empty]")
                    elif field_type == 'dict':
                        if field_value:
                            print(f"  ✅ {field_name} (dict): {field_value}")
                        else:
                            print(f"  ✅ {field_name} (dict): {{empty}}")
                    elif field_value is None:
                        print(f"  ✅ {field_name} (None): [null]")
                    else:
                        print(f"  ✅ {field_name} ({field_type}): {field_value}")
            
            # Summary of all unique fields
            print("\n" + "=" * 60)
            print("📊 FIELD SUMMARY:")
            print("-" * 20)
            
            all_fields = set()
            for record in raw_movements:
                all_fields.update(record['fields'].keys())
            
            # Categorize fields by type
            field_types = {}
            for record in raw_movements:
                for field_name, field_value in record['fields'].items():
                    if field_name not in field_types:
                        field_types[field_name] = set()
                    field_types[field_name].add(type(field_value).__name__)
            
            for field_name in sorted(all_fields):
                types = field_types[field_name]
                type_str = ", ".join(sorted(types))
                print(f"  📝 {field_name}: {type_str}")
            
            # Check for Category field specifically
            print("\n🎯 CATEGORY FIELD ANALYSIS:")
            print("-" * 30)
            
            category_found = False
            for record in raw_movements:
                if "Category" in record['fields']:
                    category_found = True
                    category_value = record['fields']["Category"]
                    print(f"  ✅ Category field found with value: {category_value}")
                    break
            
            if not category_found:
                print("  ❌ Category field NOT found in any record")
                
                # Check for similar fields
                similar_fields = []
                for field_name in all_fields:
                    if 'category' in field_name.lower() or 'type' in field_name.lower() or 'group' in field_name.lower():
                        similar_fields.append(field_name)
                
                if similar_fields:
                    print(f"  🔍 Similar fields found: {', '.join(similar_fields)}")
            
            # Recommendations
            print("\n💡 RECOMMENDATIONS:")
            print("-" * 20)
            
            if category_found:
                print("  ✅ Category field exists - check if it has the right options")
                print("  🔧 Update Category field options to match Items table")
            else:
                print("  🔧 Add new 'Category' field (Single select type)")
                print("  📋 Set options: Paint, Electrical, Plumbing, Tools, Safety Equipment, etc.")
            
            print("  🔧 Add missing fields: Unit Size, Unit Type, Location, Note, User ID, User Name")
            print("  🔧 Add missing fields: Timestamp, Approved By, Approved At, From Location, To Location")
            print("  🔧 Add missing fields: Project, Batch ID")
            
        else:
            print("  ⚠️  No stock movements found in Stock Movements table")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"❌ Error checking Stock Movements table: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_stock_movements_detailed())
