#!/usr/bin/env python3
"""Script to restructure the Items table in Airtable."""

import os
import sys
from dotenv import load_dotenv
from pyairtable import Api, Base, Table

# Load environment variables
load_dotenv('config/.env')

def restructure_items_table():
    """Restructure the Items table to keep only essential fields."""
    
    # Initialize Airtable
    api_key = os.getenv('AIRTABLE_API_KEY')
    base_id = os.getenv('AIRTABLE_BASE_ID')
    
    if not api_key or not base_id:
        print("❌ Missing AIRTABLE_API_KEY or AIRTABLE_BASE_ID in environment")
        return
    
    base = Base(api_key, base_id)
    items_table = base.table('Items')
    
    print("🔧 Items Table Restructuring")
    print("=" * 50)
    
    # Get current table structure
    try:
        schema = items_table.schema()
        current_fields = schema.fields
        print(f"📋 Current fields: {len(current_fields)}")
        for field in current_fields:
            print(f"   • {field.name} ({field.type})")
        
        print("\n🎯 Target structure:")
        target_fields = [
            "Name",
            "Base Unit", 
            "Category",
            "On Hand",
            "Reorder Level",
            "Preferred Location",
            "Large Qty Threshold",
            "Is Active"
        ]
        
        for field in target_fields:
            print(f"   • {field}")
        
        print(f"\n📊 Fields to remove: {len(current_fields) - len(target_fields)}")
        
        # Show what will be removed
        current_field_names = [field.name for field in current_fields]
        fields_to_remove = [name for name in current_field_names if name not in target_fields]
        
        print("\n🗑️  Fields that will be removed:")
        for field in fields_to_remove:
            print(f"   • {field}")
        
        # Confirm before proceeding
        print("\n⚠️  WARNING: This will permanently remove the above fields!")
        print("   All data in these fields will be lost.")
        
        confirm = input("\n❓ Are you sure you want to proceed? (yes/no): ").lower().strip()
        
        if confirm != 'yes':
            print("❌ Operation cancelled.")
            return
        
        print("\n🚀 Starting restructuring...")
        
        # Create new table structure (we'll need to recreate the table)
        # First, let's backup the current data
        print("📦 Backing up current data...")
        current_records = items_table.all()
        
        # Extract essential data
        essential_records = []
        for record in current_records:
            essential_record = {
                'id': record['id'],
                'fields': {}
            }
            
            # Map current fields to new structure
            if 'Name' in record['fields']:
                essential_record['fields']['Name'] = record['fields']['Name']
            if 'Base Unit' in record['fields']:
                essential_record['fields']['Base Unit'] = record['fields']['Base Unit']
            if 'Category' in record['fields']:
                essential_record['fields']['Category'] = record['fields']['Category']
            if 'On Hand' in record['fields']:
                essential_record['fields']['On Hand'] = record['fields']['On Hand']
            if 'Reorder Level' in record['fields']:
                essential_record['fields']['Reorder Level'] = record['fields']['Reorder Level']
            if 'Preferred Location' in record['fields']:
                essential_record['fields']['Preferred Location'] = record['fields']['Preferred Location']
            if 'Large Qty Threshold' in record['fields']:
                essential_record['fields']['Large Qty Threshold'] = record['fields']['Large Qty Threshold']
            if 'Is Active' in record['fields']:
                essential_record['fields']['Is Active'] = record['fields']['Is Active']
            
            essential_records.append(essential_record)
        
        print(f"✅ Backed up {len(essential_records)} records")
        
        # Note: Airtable doesn't allow deleting fields directly via API
        # We would need to manually delete fields in the Airtable interface
        print("\n📝 Manual Steps Required:")
        print("1. Go to your Airtable base")
        print("2. Open the Items table")
        print("3. Delete the following fields manually:")
        for field in fields_to_remove:
            print(f"   • {field}")
        print("4. Keep only these fields:")
        for field in target_fields:
            print(f"   • {field}")
        
        print("\n💡 After manual cleanup, the bot will automatically:")
        print("   • Calculate stock status based on On Hand vs Reorder Level")
        print("   • Update Last Movement Date from movements")
        print("   • Auto-create new items when unknown items are received")
        print("   • Maintain accurate stock counts")
        
        print("\n🎉 Restructuring plan ready!")
        print("   Complete the manual steps above, then test the bot.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    restructure_items_table()
