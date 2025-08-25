"""Query and reporting service for the Construction Inventory Bot."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from ..schemas import DailyReport
from ..airtable_client import AirtableClient

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
                date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
            
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
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting inventory summary: {e}")
            return {
                "low_stock_count": 0,
                "low_stock_items": [],
                "pending_approvals": 0,
                "last_updated": datetime.utcnow().isoformat(),
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

