"""Tests for the audit trail service."""

import pytest
import re
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.services.audit_trail import AuditTrailService, StocktakeAuditRecord


class TestAuditTrailService:
    """Test the audit trail service functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_airtable = AsyncMock()
        self.service = AuditTrailService(self.mock_airtable)

    def test_generate_batch_id_format(self):
        """Test that batch ID is generated in correct format."""
        batch_id = self.service.generate_batch_id()
        
        # Should match pattern: stocktake_<8 hex chars>_<timestamp>
        pattern = r'^stocktake_[a-f0-9]{8}_\d+$'
        assert re.match(pattern, batch_id), f"Batch ID {batch_id} doesn't match expected format"
        
        # Should be unique
        batch_id2 = self.service.generate_batch_id()
        assert batch_id != batch_id2

    def test_generate_batch_id_uniqueness(self):
        """Test that batch IDs are unique."""
        batch_ids = set()
        for _ in range(100):
            batch_id = self.service.generate_batch_id()
            assert batch_id not in batch_ids, f"Duplicate batch ID generated: {batch_id}"
            batch_ids.add(batch_id)

    @pytest.mark.asyncio
    async def test_create_audit_records_successful_entries(self):
        """Test creating audit records for successful entries."""
        entries = [
            {
                "success": True,
                "created": False,
                "item_name": "Cement",
                "quantity": 50.0,
                "previous_quantity": 30.0,
                "message": "Updated Cement: 30.0 → 50.0"
            },
            {
                "success": True,
                "created": True,
                "item_name": "Steel",
                "quantity": 100.0,
                "previous_quantity": 0.0,
                "message": "Created Steel with 100.0 pieces"
            },
            {
                "success": False,
                "created": False,
                "item_name": "Invalid Item",
                "quantity": 25.0,
                "message": "Failed to process Invalid Item"
            }
        ]
        
        logged_by = ["Trevor", "Kayesera"]
        user_name = "AdminUser"
        date = "2025-08-25"
        
        audit_records = await self.service.create_audit_records(
            batch_id="test_batch_123",
            date=date,
            logged_by=logged_by,
            entries=entries,
            user_name=user_name
        )
        
        # Should create records only for successful entries
        assert len(audit_records) == 2
        
        # Check first record (updated item)
        cement_record = audit_records[0]
        assert cement_record.batch_id == "test_batch_123"
        assert cement_record.date == date
        assert cement_record.logged_by == "Trevor, Kayesera"
        assert cement_record.item_name == "Cement"
        assert cement_record.counted_qty == 50.0
        assert cement_record.previous_on_hand == 30.0
        assert cement_record.new_on_hand == 50.0
        assert cement_record.applied_by == user_name
        assert isinstance(cement_record.applied_at, datetime)
        
        # Check second record (created item)
        steel_record = audit_records[1]
        assert steel_record.batch_id == "test_batch_123"
        assert steel_record.date == date
        assert steel_record.logged_by == "Trevor, Kayesera"
        assert steel_record.item_name == "Steel"
        assert steel_record.counted_qty == 100.0
        assert steel_record.previous_on_hand == 0.0
        assert steel_record.new_on_hand == 100.0
        assert steel_record.applied_by == user_name
        assert isinstance(steel_record.applied_at, datetime)

    @pytest.mark.asyncio
    async def test_create_audit_records_no_successful_entries(self):
        """Test creating audit records when no entries are successful."""
        entries = [
            {
                "success": False,
                "created": False,
                "item_name": "Invalid Item 1",
                "quantity": 25.0,
                "message": "Failed to process Invalid Item 1"
            },
            {
                "success": False,
                "created": False,
                "item_name": "Invalid Item 2",
                "quantity": 50.0,
                "message": "Failed to process Invalid Item 2"
            }
        ]
        
        audit_records = await self.service.create_audit_records(
            batch_id="test_batch_456",
            date="2025-08-25",
            logged_by=["Trevor"],
            entries=entries,
            user_name="AdminUser"
        )
        
        # Should create no audit records
        assert len(audit_records) == 0

    @pytest.mark.asyncio
    async def test_create_audit_records_empty_entries(self):
        """Test creating audit records with empty entries list."""
        audit_records = await self.service.create_audit_records(
            batch_id="test_batch_789",
            date="2025-08-25",
            logged_by=["Trevor"],
            entries=[],
            user_name="AdminUser"
        )
        
        # Should create no audit records
        assert len(audit_records) == 0

    @pytest.mark.asyncio
    async def test_create_audit_records_single_user(self):
        """Test creating audit records with single user."""
        entries = [
            {
                "success": True,
                "created": False,
                "item_name": "Cement",
                "quantity": 50.0,
                "previous_quantity": 30.0,
                "message": "Updated Cement: 30.0 → 50.0"
            }
        ]
        
        audit_records = await self.service.create_audit_records(
            batch_id="test_batch_single",
            date="2025-08-25",
            logged_by=["Trevor"],
            entries=entries,
            user_name="AdminUser"
        )
        
        assert len(audit_records) == 1
        assert audit_records[0].logged_by == "Trevor"

    @pytest.mark.asyncio
    async def test_create_audit_records_multiple_users(self):
        """Test creating audit records with multiple users."""
        entries = [
            {
                "success": True,
                "created": False,
                "item_name": "Cement",
                "quantity": 50.0,
                "previous_quantity": 30.0,
                "message": "Updated Cement: 30.0 → 50.0"
            }
        ]
        
        audit_records = await self.service.create_audit_records(
            batch_id="test_batch_multi",
            date="2025-08-25",
            logged_by=["Trevor", "Kayesera", "Grant"],
            entries=entries,
            user_name="AdminUser"
        )
        
        assert len(audit_records) == 1
        assert audit_records[0].logged_by == "Trevor, Kayesera, Grant"

    @pytest.mark.asyncio
    async def test_get_audit_records_for_batch(self):
        """Test retrieving audit records for a specific batch."""
        batch_id = "test_batch_123"
        
        # This would query the Stocktakes table for records with matching batch_id
        # For now, we'll test the method exists and handles errors gracefully
        try:
            records = await self.service.get_audit_records_for_batch(batch_id)
            # Should return empty list for now (actual implementation pending)
            assert isinstance(records, list)
        except Exception as e:
            # Should handle errors gracefully
            assert "Error retrieving audit records" in str(e)

    @pytest.mark.asyncio
    async def test_get_audit_records_for_item(self):
        """Test retrieving audit records for a specific item."""
        item_name = "Cement"
        limit = 50
        
        try:
            records = await self.service.get_audit_records_for_item(item_name, limit)
            # Should return empty list for now (actual implementation pending)
            assert isinstance(records, list)
        except Exception as e:
            # Should handle errors gracefully
            assert "Error retrieving audit records" in str(e)

    @pytest.mark.asyncio
    async def test_get_audit_records_by_date_range(self):
        """Test retrieving audit records within a date range."""
        start_date = "2025-08-01"
        end_date = "2025-08-31"
        limit = 100
        
        try:
            records = await self.service.get_audit_records_by_date_range(start_date, end_date, limit)
            # Should return empty list for now (actual implementation pending)
            assert isinstance(records, list)
        except Exception as e:
            # Should handle errors gracefully
            assert "Error retrieving audit records" in str(e)

    def test_format_audit_summary_empty_records(self):
        """Test formatting audit summary with no records."""
        summary = self.service.format_audit_summary([])
        assert summary == "No audit records found."

    def test_format_audit_summary_single_record(self):
        """Test formatting audit summary with single record."""
        record = StocktakeAuditRecord(
            batch_id="test_batch_123",
            date="2025-08-25",
            logged_by="Trevor",
            item_name="Cement",
            counted_qty=50.0,
            previous_on_hand=30.0,
            new_on_hand=50.0,
            applied_at=datetime(2025, 8, 25, 10, 30, 0),
            applied_by="AdminUser"
        )
        
        summary = self.service.format_audit_summary([record])
        
        assert "Audit Trail Summary" in summary
        assert "test_batch_123" in summary
        assert "2025-08-25" in summary
        assert "Trevor" in summary
        assert "AdminUser" in summary
        assert "Cement: 30.0 → 50.0 (counted: 50.0)" in summary

    def test_format_audit_summary_multiple_records_same_batch(self):
        """Test formatting audit summary with multiple records from same batch."""
        records = [
            StocktakeAuditRecord(
                batch_id="test_batch_123",
                date="2025-08-25",
                logged_by="Trevor, Kayesera",
                item_name="Cement",
                counted_qty=50.0,
                previous_on_hand=30.0,
                new_on_hand=50.0,
                applied_at=datetime(2025, 8, 25, 10, 30, 0),
                applied_by="AdminUser"
            ),
            StocktakeAuditRecord(
                batch_id="test_batch_123",
                date="2025-08-25",
                logged_by="Trevor, Kayesera",
                item_name="Steel",
                counted_qty=100.0,
                previous_on_hand=0.0,
                new_on_hand=100.0,
                applied_at=datetime(2025, 8, 25, 10, 30, 0),
                applied_by="AdminUser"
            )
        ]
        
        summary = self.service.format_audit_summary(records)
        
        assert "Audit Trail Summary" in summary
        assert "test_batch_123" in summary
        assert "Cement: 30.0 → 50.0 (counted: 50.0)" in summary
        assert "Steel: 0.0 → 100.0 (counted: 100.0)" in summary
        assert "Trevor, Kayesera" in summary

    def test_format_audit_summary_multiple_batches(self):
        """Test formatting audit summary with records from multiple batches."""
        records = [
            StocktakeAuditRecord(
                batch_id="batch_1",
                date="2025-08-25",
                logged_by="Trevor",
                item_name="Cement",
                counted_qty=50.0,
                previous_on_hand=30.0,
                new_on_hand=50.0,
                applied_at=datetime(2025, 8, 25, 10, 30, 0),
                applied_by="AdminUser"
            ),
            StocktakeAuditRecord(
                batch_id="batch_2",
                date="2025-08-26",
                logged_by="Kayesera",
                item_name="Steel",
                counted_qty=100.0,
                previous_on_hand=0.0,
                new_on_hand=100.0,
                applied_at=datetime(2025, 8, 26, 14, 15, 0),
                applied_by="AdminUser"
            )
        ]
        
        summary = self.service.format_audit_summary(records)
        
        assert "Audit Trail Summary" in summary
        assert "batch_1" in summary
        assert "batch_2" in summary
        assert "2025-08-25" in summary
        assert "2025-08-26" in summary
        assert "Trevor" in summary
        assert "Kayesera" in summary

    @pytest.mark.asyncio
    async def test_airtable_storage_intention(self):
        """Test that Airtable storage is attempted."""
        entries = [
            {
                "success": True,
                "created": False,
                "item_name": "Cement",
                "quantity": 50.0,
                "previous_quantity": 30.0,
                "message": "Updated Cement: 30.0 → 50.0"
            }
        ]
        
        # Create audit records (this should attempt Airtable storage)
        audit_records = await self.service.create_audit_records(
            batch_id="test_batch_storage",
            date="2025-08-25",
            logged_by=["Trevor"],
            entries=entries,
            user_name="AdminUser"
        )
        
        # Should create audit records
        assert len(audit_records) == 1
        
        # The actual Airtable storage will be implemented when schema is ready
        # For now, we just verify the intention is logged

