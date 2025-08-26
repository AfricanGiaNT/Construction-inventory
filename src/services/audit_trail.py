"""Audit trail service for tracking inventory stocktake operations."""

import logging
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class StocktakeAuditRecord:
    """Audit record for a single inventory item change."""
    batch_id: str
    date: str  # ISO date string
    logged_by: str  # Comma-separated names
    item_name: str
    counted_qty: float
    previous_on_hand: float
    new_on_hand: float
    applied_at: datetime
    applied_by: str


class AuditTrailService:
    """Service for managing audit trail records for inventory operations."""
    
    def __init__(self, airtable_client):
        """Initialize the audit trail service."""
        self.airtable = airtable_client
    
    def generate_batch_id(self) -> str:
        """Generate a unique batch ID for inventory operations."""
        return f"stocktake_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"
    
    async def create_audit_records(self, 
                                 batch_id: str,
                                 date: str,
                                 logged_by: List[str],
                                 entries: List[Dict],
                                 user_name: str) -> List[StocktakeAuditRecord]:
        """
        Create audit records for successful inventory entries.
        
        Args:
            batch_id: Unique identifier for this batch
            date: ISO date string
            logged_by: List of user names who performed the stocktake
            entries: List of processed entry results
            user_name: Name of the user applying the changes
            
        Returns:
            List of audit records created
        """
        audit_records = []
        logged_by_str = ", ".join(logged_by)
        applied_at = datetime.now()
        
        for entry in entries:
            if entry["success"]:
                # Create audit record for successful entries
                audit_record = StocktakeAuditRecord(
                    batch_id=batch_id,
                    date=date,
                    logged_by=logged_by_str,
                    item_name=entry["item_name"],
                    counted_qty=entry["quantity"],
                    previous_on_hand=entry["previous_quantity"],
                    new_on_hand=entry["quantity"],  # New on hand is the counted quantity
                    applied_at=applied_at,
                    applied_by=user_name
                )
                
                audit_records.append(audit_record)
                
                # Store in Airtable
                try:
                    await self._store_audit_record(audit_record)
                    logger.info(f"Created audit record for {entry['item_name']} in batch {batch_id}")
                except Exception as e:
                    logger.error(f"Failed to create audit record for {entry['item_name']}: {e}")
                    # Continue with other records even if one fails
        
        logger.info(f"Created {len(audit_records)} audit records for batch {batch_id}")
        return audit_records
    
    async def get_audit_records_for_batch(self, batch_id: str) -> List[StocktakeAuditRecord]:
        """Retrieve all audit records for a specific batch."""
        try:
            # This would query the Stocktakes table for records with matching batch_id
            # For now, we'll log the intention - actual implementation depends on Airtable schema
            logger.info(f"Would retrieve audit records for batch: {batch_id}")
            
            # TODO: Implement actual Airtable query when schema is ready
            # records = await self.airtable.get_stocktake_records_by_batch(batch_id)
            # return [StocktakeAuditRecord(...) for record in records]
            
            return []
            
        except Exception as e:
            logger.error(f"Error retrieving audit records for batch {batch_id}: {e}")
            raise
    
    async def get_audit_records_for_item(self, item_name: str, limit: int = 100) -> List[StocktakeAuditRecord]:
        """Retrieve recent audit records for a specific item."""
        try:
            # This would query the Stocktakes table for records with matching item_name
            # For now, we'll log the intention - actual implementation depends on Airtable schema
            logger.info(f"Would retrieve audit records for item: {item_name}, limit: {limit}")
            
            # TODO: Implement actual Airtable query when schema is ready
            # records = await self.airtable.get_stocktake_records_by_item(item_name, limit)
            # return [StocktakeAuditRecord(...) for record in records]
            
            return []
            
        except Exception as e:
            logger.error(f"Error retrieving audit records for item {item_name}: {e}")
            raise
    
    async def get_audit_records_by_date_range(self, 
                                            start_date: str, 
                                            end_date: str, 
                                            limit: int = 100) -> List[StocktakeAuditRecord]:
        """Retrieve audit records within a date range."""
        try:
            # This would query the Stocktakes table for records within the date range
            # For now, we'll log the intention - actual implementation depends on Airtable schema
            logger.info(f"Would retrieve audit records from {start_date} to {end_date}, limit: {limit}")
            
            # TODO: Implement actual Airtable query when schema is ready
            # records = await self.airtable.get_stocktake_records_by_date_range(start_date, end_date, limit)
            # return [StocktakeAuditRecord(...) for record in records]
            
            return []
            
        except Exception as e:
            logger.error(f"Error retrieving audit records for date range {start_date} to {end_date}: {e}")
            raise
    
    async def _store_audit_record(self, audit_record: StocktakeAuditRecord):
        """Store an audit record in the Stocktakes Airtable table."""
        try:
            # Calculate discrepancy if we have both previous and new values
            discrepancy = None
            if audit_record.previous_on_hand is not None and audit_record.new_on_hand is not None:
                discrepancy = audit_record.new_on_hand - audit_record.previous_on_hand
            
            # Create the stocktake record in Airtable
            record_id = await self.airtable.create_stocktake_record(
                batch_id=audit_record.batch_id,
                date=audit_record.date,
                logged_by=audit_record.logged_by,
                item_name=audit_record.item_name,
                counted_qty=audit_record.counted_qty,
                previous_on_hand=audit_record.previous_on_hand,
                new_on_hand=audit_record.new_on_hand,
                applied_at=audit_record.applied_at,
                applied_by=audit_record.applied_by,
                notes=f"Stocktake: {audit_record.previous_on_hand} → {audit_record.new_on_hand}",
                discrepancy=discrepancy
            )
            
            if record_id:
                logger.info(f"Created stocktake record {record_id} for {audit_record.item_name} in batch {audit_record.batch_id}")
            else:
                logger.error(f"Failed to create stocktake record for {audit_record.item_name}")
                
        except Exception as e:
            logger.error(f"Error storing audit record in Airtable: {e}")
            raise
    
    def format_audit_summary(self, audit_records: List[StocktakeAuditRecord]) -> str:
        """Format audit records into a human-readable summary."""
        if not audit_records:
            return "No audit records found."
        
        # Group by batch
        batches = {}
        for record in audit_records:
            if record.batch_id not in batches:
                batches[record.batch_id] = []
            batches[record.batch_id].append(record)
        
        summary = f"📊 <b>Audit Trail Summary</b>\n\n"
        
        for batch_id, records in batches.items():
            summary += f"🆔 <b>Batch:</b> {batch_id}\n"
            summary += f"📅 <b>Date:</b> {records[0].date}\n"
            summary += f"👥 <b>Logged by:</b> {records[0].logged_by}\n"
            summary += f"👤 <b>Applied by:</b> {records[0].applied_by}\n"
            summary += f"⏰ <b>Applied at:</b> {records[0].applied_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            summary += "📋 <b>Changes:</b>\n"
            for record in records:
                summary += f"• {record.item_name}: {record.previous_on_hand} → {record.new_on_hand} (counted: {record.counted_qty})\n"
            
            summary += "\n" + "─" * 40 + "\n\n"
        
        return summary

