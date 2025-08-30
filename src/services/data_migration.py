"""Data migration service for the Construction Inventory Bot."""

import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, UTC

from schemas import Item
from airtable_client import AirtableClient
from services.category_parser import category_parser

logger = logging.getLogger(__name__)


class DataMigrationService:
    """Service for handling data migration tasks, including retroactive categorization."""
    
    def __init__(self, airtable_client: AirtableClient):
        """Initialize the data migration service."""
        self.airtable = airtable_client
    
    async def migrate_existing_items_to_categories(self, dry_run: bool = True, batch_size: int = 10) -> Dict[str, Any]:
        """
        Migrate existing items to use the new category system.
        
        Args:
            dry_run: If True, only show what would be changed without making changes
            batch_size: Number of items to process in each batch
            
        Returns:
            Dictionary with migration results
        """
        try:
            logger.info(f"Starting category migration (dry_run={dry_run}, batch_size={batch_size})")
            
            # Get all items from Airtable
            all_items = await self.airtable.get_all_items()
            if not all_items:
                return {
                    "success": False,
                    "error": "No items found to migrate",
                    "total_items": 0,
                    "migrated_items": 0,
                    "skipped_items": 0,
                    "errors": []
                }
            
            # Filter items that need categorization
            items_to_migrate = []
            items_to_skip = []
            
            for item in all_items:
                if not item.category or item.category == "Steel":  # "Steel" seems to be a default placeholder
                    items_to_migrate.append(item)
                else:
                    items_to_skip.append(item)
            
            logger.info(f"Found {len(items_to_migrate)} items to migrate, {len(items_to_skip)} to skip")
            
            if not items_to_migrate:
                return {
                    "success": True,
                    "message": "No items need migration - all items already have proper categories",
                    "total_items": len(all_items),
                    "migrated_items": 0,
                    "skipped_items": len(items_to_skip),
                    "errors": []
                }
            
            # Process items in batches
            migration_results = {
                "total_items": len(all_items),
                "items_to_migrate": len(items_to_migrate),
                "skipped_items": len(items_to_skip),
                "migrated_items": 0,
                "errors": [],
                "migration_details": [],
                "dry_run": dry_run
            }
            
            # Process first batch for testing
            test_batch = items_to_migrate[:batch_size]
            
            for item in test_batch:
                try:
                    # Detect category using smart parsing
                    detected_category = category_parser.parse_category(item.name)
                    
                    migration_detail = {
                        "item_name": item.name,
                        "old_category": item.category,
                        "new_category": detected_category,
                        "stock_level": item.on_hand,
                        "unit_info": f"{item.unit_size} {item.unit_type}" if item.unit_size and item.unit_type else "1 piece"
                    }
                    
                    if not dry_run:
                        # Update the item in Airtable
                        success = await self.airtable.update_item_category(item.name, detected_category)
                        if success:
                            migration_detail["status"] = "success"
                            migration_results["migrated_items"] += 1
                        else:
                            migration_detail["status"] = "failed"
                            migration_detail["error"] = "Failed to update in Airtable"
                            migration_results["errors"].append(f"Failed to update {item.name}")
                    else:
                        migration_detail["status"] = "would_migrate"
                        migration_results["migrated_items"] += 1
                    
                    migration_results["migration_details"].append(migration_detail)
                    
                except Exception as e:
                    error_msg = f"Error processing {item.name}: {str(e)}"
                    logger.error(error_msg)
                    migration_results["errors"].append(error_msg)
                    
                    migration_results["migration_details"].append({
                        "item_name": item.name,
                        "old_category": item.category,
                        "new_category": "ERROR",
                        "status": "error",
                        "error": str(e)
                    })
            
            # Generate summary message
            if dry_run:
                migration_results["message"] = f"DRY RUN: Would migrate {migration_results['migrated_items']} items to new categories"
            else:
                migration_results["message"] = f"Successfully migrated {migration_results['migrated_items']} items to new categories"
            
            migration_results["success"] = len(migration_results["errors"]) == 0
            
            logger.info(f"Category migration completed: {migration_results['migrated_items']} items processed")
            return migration_results
            
        except Exception as e:
            logger.error(f"Error in category migration: {e}")
            return {
                "success": False,
                "error": str(e),
                "total_items": 0,
                "migrated_items": 0,
                "skipped_items": 0,
                "errors": [str(e)]
            }
    
    async def get_migration_preview(self, limit: int = 20) -> Dict[str, Any]:
        """
        Get a preview of what would be migrated without making changes.
        
        Args:
            limit: Maximum number of items to show in preview
            
        Returns:
            Dictionary with migration preview
        """
        try:
            # Get all items
            all_items = await self.airtable.get_all_items()
            if not all_items:
                return {"error": "No items found"}
            
            # Filter items that need categorization
            items_to_migrate = []
            items_to_skip = []
            
            for item in all_items:
                if not item.category or item.category == "Steel":
                    items_to_migrate.append(item)
                else:
                    items_to_skip.append(item)
            
            # Generate preview for first N items
            preview_items = items_to_migrate[:limit]
            preview_data = []
            
            for item in preview_items:
                detected_category = category_parser.parse_category(item.name)
                preview_data.append({
                    "item_name": item.name,
                    "current_category": item.category or "None",
                    "proposed_category": detected_category,
                    "stock_level": item.on_hand,
                    "unit_info": f"{item.unit_size} {item.unit_type}" if item.unit_size and item.unit_type else "1 piece"
                })
            
            return {
                "total_items": len(all_items),
                "items_to_migrate": len(items_to_migrate),
                "items_to_skip": len(items_to_skip),
                "preview_items": preview_data,
                "preview_limit": limit,
                "message": f"Preview of {len(preview_data)} items that would be migrated"
            }
            
        except Exception as e:
            logger.error(f"Error getting migration preview: {e}")
            return {"error": str(e)}
    
    async def validate_migration_data(self) -> Dict[str, Any]:
        """
        Validate that the migration can proceed safely.
        
        Returns:
            Dictionary with validation results
        """
        try:
            # Get all items
            all_items = await self.airtable.get_all_items()
            if not all_items:
                return {"error": "No items found"}
            
            validation_results = {
                "total_items": len(all_items),
                "items_with_categories": 0,
                "items_without_categories": 0,
                "items_with_default_category": 0,
                "category_distribution": {},
                "validation_passed": True,
                "warnings": [],
                "errors": []
            }
            
            for item in all_items:
                if item.category:
                    validation_results["items_with_categories"] += 1
                    
                    # Count category distribution
                    if item.category not in validation_results["category_distribution"]:
                        validation_results["category_distribution"][item.category] = 0
                    validation_results["category_distribution"][item.category] += 1
                    
                    # Check for default/placeholder categories
                    if item.category == "Steel":
                        validation_results["items_with_default_category"] += 1
                        validation_results["warnings"].append(f"Item '{item.name}' has placeholder category 'Steel'")
                else:
                    validation_results["items_without_categories"] += 1
                    validation_results["warnings"].append(f"Item '{item.name}' has no category")
            
            # Check if migration is needed
            if validation_results["items_without_categories"] == 0 and validation_results["items_with_default_category"] == 0:
                validation_results["migration_needed"] = False
                validation_results["message"] = "No migration needed - all items have proper categories"
            else:
                validation_results["migration_needed"] = True
                validation_results["message"] = f"Migration needed: {validation_results['items_without_categories']} items without categories, {validation_results['items_with_default_category']} with placeholder categories"
            
            # Check for potential issues
            if validation_results["items_without_categories"] > 0:
                validation_results["warnings"].append(f"{validation_results['items_without_categories']} items have no category and will be auto-categorized")
            
            if validation_results["items_with_default_category"] > 0:
                validation_results["warnings"].append(f"{validation_results['items_with_default_category']} items have placeholder category 'Steel' and will be re-categorized")
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating migration data: {e}")
            return {"error": str(e)}
    
    async def rollback_migration(self, backup_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Rollback category changes using backup data.
        
        Args:
            backup_data: List of backup records with original category information
            
        Returns:
            Dictionary with rollback results
        """
        try:
            logger.info(f"Starting migration rollback for {len(backup_data)} items")
            
            rollback_results = {
                "total_items": len(backup_data),
                "rolled_back": 0,
                "failed": 0,
                "errors": []
            }
            
            for backup_record in backup_data:
                try:
                    item_name = backup_record.get("item_name")
                    original_category = backup_record.get("original_category")
                    
                    if not item_name:
                        rollback_results["errors"].append("Backup record missing item name")
                        continue
                    
                    # Restore original category
                    success = await self.airtable.update_item_category(item_name, original_category)
                    
                    if success:
                        rollback_results["rolled_back"] += 1
                        logger.info(f"Rolled back {item_name} to category: {original_category}")
                    else:
                        rollback_results["failed"] += 1
                        rollback_results["errors"].append(f"Failed to rollback {item_name}")
                        
                except Exception as e:
                    error_msg = f"Error rolling back {backup_record.get('item_name', 'Unknown')}: {str(e)}"
                    logger.error(error_msg)
                    rollback_results["errors"].append(error_msg)
                    rollback_results["failed"] += 1
            
            rollback_results["success"] = len(rollback_results["errors"]) == 0
            rollback_results["message"] = f"Rollback completed: {rollback_results['rolled_back']} items restored, {rollback_results['failed']} failed"
            
            logger.info(f"Migration rollback completed: {rollback_results['rolled_back']} items restored")
            return rollback_results
            
        except Exception as e:
            logger.error(f"Error in migration rollback: {e}")
            return {
                "success": False,
                "error": str(e),
                "total_items": 0,
                "rolled_back": 0,
                "failed": 0,
                "errors": [str(e)]
            }
