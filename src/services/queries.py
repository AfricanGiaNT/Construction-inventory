"""Query and reporting service for the Construction Inventory Bot."""

import logging
from datetime import datetime, timedelta, UTC
from typing import List, Optional, Tuple, Dict, Any

from schemas import DailyReport
from airtable_client import AirtableClient

logger = logging.getLogger(__name__)


class QueryService:
    """Service for handling queries and reports."""
    
    def __init__(self, airtable_client: AirtableClient):
        """Initialize the query service."""
        self.airtable = airtable_client
    
    async def generate_daily_report(self, date: Optional[str] = None) -> DailyReport:
        """Generate a daily inventory report."""
        try:
            if not date:
                date = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")
            
            # Get daily movements
            movements = await self.airtable.get_daily_movements(date)
            
            # Get low stock items
            low_stock = await self.airtable.get_low_stock_items()
            
            # Get pending approvals
            pending_approvals = await self.airtable.get_pending_approvals()
            
            return DailyReport(
                date=date,
                total_in=movements["total_in"],
                total_out=movements["total_out"],
                movements_count=movements["movements_count"],
                low_stock_items=low_stock,
                pending_approvals=len(pending_approvals)
            )
            
        except Exception as e:
            logger.error(f"Error generating daily report: {e}")
            return DailyReport(
                date=date or "unknown",
                total_in=0.0,
                total_out=0.0,
                movements_count=0,
                low_stock_items=[],
                pending_approvals=0
            )
    
    async def get_inventory_summary(self) -> dict:
        """Get a summary of current inventory status."""
        try:
            # Get low stock items
            low_stock = await self.airtable.get_low_stock_items()
            
            # Get pending approvals
            pending_approvals = await self.airtable.get_pending_approvals()
            
            return {
                "low_stock_count": len(low_stock),
                "low_stock_items": low_stock,
                "pending_approvals": len(pending_approvals),
                "last_updated": datetime.now(UTC).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting inventory summary: {e}")
            return {
                "low_stock_count": 0,
                "low_stock_items": [],
                "pending_approvals": 0,
                "last_updated": datetime.now(UTC).isoformat(),
                "error": str(e)
            }
    
    async def export_inventory_csv(self) -> Tuple[bool, str, Optional[str]]:
        """Export current inventory to CSV format."""
        try:
            csv_data = await self.airtable.export_onhand_csv()
            if not csv_data:
                return False, "Failed to generate CSV export.", None
            
            return True, "CSV export generated successfully.", csv_data
            
        except Exception as e:
            logger.error(f"Error exporting CSV: {e}")
            return False, f"Error generating CSV export: {str(e)}", None
    
    async def get_movement_history(self, sku: str, days: int = 30) -> Tuple[bool, str, List[dict]]:
        """Get movement history for a specific item."""
        try:
            # This would require implementing a method to get movements by SKU and date range
            # For now, return a placeholder
            return True, f"Movement history for {sku} (last {days} days)", []
            
        except Exception as e:
            logger.error(f"Error getting movement history: {e}")
            return False, f"Error retrieving movement history: {str(e)}", []
    
    async def get_user_activity_summary(self, user_id: int, days: int = 7) -> dict:
        """Get activity summary for a specific user."""
        try:
            # This would require implementing user activity tracking
            # For now, return a placeholder
            return {
                "user_id": user_id,
                "period_days": days,
                "movements_count": 0,
                "last_activity": None,
                "items_handled": []
            }
            
        except Exception as e:
            logger.error(f"Error getting user activity summary: {e}")
            return {
                "user_id": user_id,
                "period_days": days,
                "error": str(e)
            }
    
    async def get_category_based_inventory_summary(self, category: str = None) -> Dict[str, Any]:
        """
        Get inventory summary grouped by category.
        
        Args:
            category: Optional specific category to filter by
            
        Returns:
            Dictionary with category-based inventory summary
        """
        try:
            # Get all items
            all_items = await self.airtable.get_all_items()
            if not all_items:
                return {"error": "No items found"}
            
            # Group items by category
            category_summary = {}
            total_items = 0
            total_stock_value = 0.0
            total_low_stock = 0
            
            for item in all_items:
                item_category = item.category or "Uncategorized"
                
                # Filter by specific category if requested
                if category and item_category.lower() != category.lower():
                    continue
                
                if item_category not in category_summary:
                    category_summary[item_category] = {
                        "item_count": 0,
                        "total_stock": 0.0,
                        "low_stock_count": 0,
                        "items": [],
                        "total_value": 0.0
                    }
                
                category_summary[item_category]["item_count"] += 1
                category_summary[item_category]["total_stock"] += item.on_hand
                category_summary[item_category]["items"].append({
                    "name": item.name,
                    "stock": item.on_hand,
                    "unit": item.unit_type or "piece",
                    "location": item.location,
                    "threshold": item.threshold,
                    "is_low_stock": item.threshold and item.on_hand <= item.threshold
                })
                
                # Check if item is low stock
                if item.threshold and item.on_hand <= item.threshold:
                    category_summary[item_category]["low_stock_count"] += 1
                    total_low_stock += 1
                
                total_items += 1
                total_stock_value += item.on_hand
            
            # Sort categories by item count (descending)
            sorted_categories = sorted(
                category_summary.items(),
                key=lambda x: x[1]["item_count"],
                reverse=True
            )
            
            return {
                "category_summary": dict(sorted_categories),
                "total_categories": len(category_summary),
                "total_items": total_items,
                "total_low_stock": total_low_stock,
                "last_updated": datetime.now(UTC).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting category-based inventory summary: {e}")
            return {"error": str(e)}
    
    async def get_category_movement_report(self, category: str, days: int = 30) -> Dict[str, Any]:
        """
        Get movement report for items in a specific category.
        
        Args:
            category: Category to get movements for
            days: Number of days to look back
            
        Returns:
            Dictionary with category movement report
        """
        try:
            # Get all items in the category
            all_items = await self.airtable.get_all_items()
            if not all_items:
                return {"error": "No items found"}
            
            # Filter items by category
            category_items = [
                item for item in all_items
                if item.category and item.category.lower() == category.lower()
            ]
            
            if not category_items:
                return {"error": f"No items found in category '{category}'"}
            
            # Get movements for these items (this would need to be implemented in Airtable client)
            # For now, return a placeholder structure
            movement_summary = {
                "category": category,
                "period_days": days,
                "items_count": len(category_items),
                "total_movements": 0,
                "movements_in": 0,
                "movements_out": 0,
                "movements_adjust": 0,
                "items": [item.name for item in category_items],
                "last_updated": datetime.now(UTC).isoformat()
            }
            
            return movement_summary
            
        except Exception as e:
            logger.error(f"Error getting category movement report: {e}")
            return {"error": str(e)}
    
    async def get_category_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics for all categories.
        
        Returns:
            Dictionary with category statistics
        """
        try:
            # Get all items
            all_items = await self.airtable.get_all_items()
            if not all_items:
                return {"error": "No items found"}
            
            # Calculate category statistics
            category_stats = {}
            total_categories = 0
            total_items = 0
            total_stock = 0.0
            total_low_stock = 0
            
            for item in all_items:
                category = item.category or "Uncategorized"
                
                if category not in category_stats:
                    category_stats[category] = {
                        "item_count": 0,
                        "total_stock": 0.0,
                        "low_stock_count": 0,
                        "avg_stock": 0.0,
                        "min_stock": float('inf'),
                        "max_stock": 0.0,
                        "items": []
                    }
                    total_categories += 1
                
                category_stats[category]["item_count"] += 1
                category_stats[category]["total_stock"] += item.on_hand
                category_stats[category]["min_stock"] = min(category_stats[category]["min_stock"], item.on_hand)
                category_stats[category]["max_stock"] = max(category_stats[category]["max_stock"], item.on_hand)
                category_stats[category]["items"].append(item.name)
                
                # Check if item is low stock
                if item.threshold and item.on_hand <= item.threshold:
                    category_stats[category]["low_stock_count"] += 1
                    total_low_stock += 1
                
                total_items += 1
                total_stock += item.on_hand
            
            # Calculate averages and finalize stats
            for category_data in category_stats.values():
                if category_data["item_count"] > 0:
                    category_data["avg_stock"] = category_data["total_stock"] / category_data["item_count"]
                if category_data["min_stock"] == float('inf'):
                    category_data["min_stock"] = 0.0
            
            # Sort categories by item count (descending)
            sorted_categories = sorted(
                category_stats.items(),
                key=lambda x: x[1]["item_count"],
                reverse=True
            )
            
            return {
                "category_statistics": dict(sorted_categories),
                "summary": {
                    "total_categories": total_categories,
                    "total_items": total_items,
                    "total_stock": total_stock,
                    "total_low_stock": total_low_stock,
                    "avg_items_per_category": total_items / total_categories if total_categories > 0 else 0,
                    "avg_stock_per_item": total_stock / total_items if total_items > 0 else 0
                },
                "last_updated": datetime.now(UTC).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting category statistics: {e}")
            return {"error": str(e)}

