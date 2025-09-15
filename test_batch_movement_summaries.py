"""Tests for batch movement summary generation."""

import pytest
from unittest.mock import MagicMock
from src.services.batch_movement_processor import BatchMovementProcessor
from src.schemas import MovementType, BatchInfo, BatchItem


class TestBatchMovementSummaries:
    """Test summary generation functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_airtable = MagicMock()
        self.mock_settings = MagicMock()
        self.mock_stock_service = MagicMock()
        
        self.processor = BatchMovementProcessor(
            airtable_client=self.mock_airtable,
            settings=self.mock_settings,
            stock_service=self.mock_stock_service
        )
    
    def test_generate_summary_single_batch_in(self):
        """Test generating summary for single batch /in command."""
        batches = [
            BatchInfo(
                batch_number=1,
                project="mzuzu",
                driver="Dani maliko",
                from_location="supplier warehouse",
                items=[
                    BatchItem(item_name="Solar floodlight panel FS-SFL800", quantity=4.0),
                    BatchItem(item_name="Solar floodlight 800W", quantity=4.0),
                    BatchItem(item_name="Cable 2.5sqmm black 100m", quantity=1.0)
                ]
            )
        ]
        
        summary = self.processor.get_batch_summary(batches)
        
        assert "Found 1 batch(es):" in summary
        assert "Batch 1: 3 items from supplier warehouse" in summary
        assert "(Project: mzuzu, Driver: Dani maliko)" in summary
        assert "Total items: 3" in summary
    
    def test_generate_summary_single_batch_out(self):
        """Test generating summary for single batch /out command."""
        batches = [
            BatchInfo(
                batch_number=1,
                project="mzuzu",
                driver="Dani maliko",
                to_location="mzuzu houses",
                items=[
                    BatchItem(item_name="Solar floodlight panel FS-SFL800", quantity=4.0),
                    BatchItem(item_name="Solar floodlight 800W", quantity=4.0)
                ]
            )
        ]
        
        summary = self.processor.get_batch_summary(batches)
        
        assert "Found 1 batch(es):" in summary
        assert "Batch 1: 2 items to mzuzu houses" in summary
        assert "(Project: mzuzu, Driver: Dani maliko)" in summary
        assert "Total items: 2" in summary
    
    def test_generate_summary_multiple_batches(self):
        """Test generating summary for multiple batches."""
        batches = [
            BatchInfo(
                batch_number=1,
                project="mzuzu",
                driver="Dani maliko",
                to_location="mzuzu houses",
                items=[
                    BatchItem(item_name="Solar floodlight panel FS-SFL800", quantity=4.0),
                    BatchItem(item_name="Solar floodlight 800W", quantity=4.0)
                ]
            ),
            BatchInfo(
                batch_number=2,
                project="lilongwe",
                driver="John Banda",
                to_location="lilongwe site",
                items=[
                    BatchItem(item_name="Cable 2.5sqmm black 100m", quantity=1.0),
                    BatchItem(item_name="Cable 2.5sqmm green 100m", quantity=1.0),
                    BatchItem(item_name="Cable 2.5sqmm red 100m", quantity=1.0)
                ]
            )
        ]
        
        summary = self.processor.get_batch_summary(batches)
        
        assert "Found 2 batch(es):" in summary
        assert "Batch 1: 2 items to mzuzu houses" in summary
        assert "Batch 2: 3 items to lilongwe site" in summary
        assert "Total items: 5" in summary
        assert "(Project: mzuzu, Driver: Dani maliko)" in summary
        assert "(Project: lilongwe, Driver: John Banda)" in summary
    
    def test_generate_summary_with_defaults(self):
        """Test generating summary with default values."""
        batches = [
            BatchInfo(
                batch_number=1,
                project="not described",
                driver="not described",
                to_location="external",
                items=[
                    BatchItem(item_name="Test item", quantity=10.0)
                ]
            )
        ]
        
        summary = self.processor.get_batch_summary(batches)
        
        assert "Found 1 batch(es):" in summary
        assert "Batch 1: 1 items to external" in summary
        assert "(Project: not described, Driver: not described)" in summary
        assert "Total items: 1" in summary
    
    def test_generate_summary_empty_batches(self):
        """Test generating summary for empty batches list."""
        batches = []
        
        summary = self.processor.get_batch_summary(batches)
        
        assert summary == "No batches found"
    
    def test_generate_summary_mixed_movement_types(self):
        """Test generating summary with mixed movement types."""
        batches = [
            BatchInfo(
                batch_number=1,
                project="mzuzu",
                driver="Dani maliko",
                from_location="supplier",
                items=[
                    BatchItem(item_name="Incoming item", quantity=5.0)
                ]
            ),
            BatchInfo(
                batch_number=2,
                project="lilongwe",
                driver="John Banda",
                to_location="construction site",
                items=[
                    BatchItem(item_name="Outgoing item", quantity=3.0)
                ]
            )
        ]
        
        summary = self.processor.get_batch_summary(batches)
        
        assert "Found 2 batch(es):" in summary
        assert "Batch 1: 1 items from supplier" in summary
        assert "Batch 2: 1 items to construction site" in summary
        assert "Total items: 2" in summary
    
    def test_generate_summary_large_quantities(self):
        """Test generating summary with large quantities."""
        batches = [
            BatchInfo(
                batch_number=1,
                project="large project",
                driver="Heavy Duty Driver",
                to_location="mega construction site",
                items=[
                    BatchItem(item_name="Cement", quantity=1000.0),
                    BatchItem(item_name="Steel bars", quantity=500.0),
                    BatchItem(item_name="Sand", quantity=2000.0)
                ]
            )
        ]
        
        summary = self.processor.get_batch_summary(batches)
        
        assert "Found 1 batch(es):" in summary
        assert "Batch 1: 3 items to mega construction site" in summary
        assert "(Project: large project, Driver: Heavy Duty Driver)" in summary
        assert "Total items: 3" in summary
    
    def test_generate_summary_special_characters(self):
        """Test generating summary with special characters in names."""
        batches = [
            BatchInfo(
                batch_number=1,
                project="Test Project, Inc.",
                driver="John Doe, Jr.",
                to_location="Test Location, LLC",
                items=[
                    BatchItem(item_name="Item with spaces & symbols", quantity=10.0),
                    BatchItem(item_name="Item-with-dashes", quantity=5.0),
                    BatchItem(item_name="Item_with_underscores", quantity=3.0)
                ]
            )
        ]
        
        summary = self.processor.get_batch_summary(batches)
        
        assert "Found 1 batch(es):" in summary
        assert "Batch 1: 3 items to Test Location, LLC" in summary
        assert "(Project: Test Project, Inc., Driver: John Doe, Jr.)" in summary
        assert "Total items: 3" in summary
    
    def test_generate_summary_unicode_characters(self):
        """Test generating summary with unicode characters."""
        batches = [
            BatchInfo(
                batch_number=1,
                project="测试项目",
                driver="测试司机",
                to_location="测试地点",
                items=[
                    BatchItem(item_name="太阳能灯板 FS-SFL800", quantity=4.0),
                    BatchItem(item_name="电缆 2.5平方毫米 黑色 100米", quantity=1.0)
                ]
            )
        ]
        
        summary = self.processor.get_batch_summary(batches)
        
        assert "Found 1 batch(es):" in summary
        assert "Batch 1: 2 items to 测试地点" in summary
        assert "(Project: 测试项目, Driver: 测试司机)" in summary
        assert "Total items: 2" in summary
    
    def test_generate_summary_many_batches(self):
        """Test generating summary with many batches."""
        batches = []
        for i in range(10):
            batches.append(BatchInfo(
                batch_number=i + 1,
                project=f"Project {i + 1}",
                driver=f"Driver {i + 1}",
                to_location=f"Location {i + 1}",
                items=[
                    BatchItem(item_name=f"Item {i + 1}a", quantity=1.0),
                    BatchItem(item_name=f"Item {i + 1}b", quantity=2.0)
                ]
            ))
        
        summary = self.processor.get_batch_summary(batches)
        
        assert "Found 10 batch(es):" in summary
        assert "Total items: 20" in summary
        # Check that all batches are mentioned
        for i in range(10):
            assert f"Batch {i + 1}: 2 items to Location {i + 1}" in summary
    
    def test_generate_summary_single_item_batches(self):
        """Test generating summary with single item batches."""
        batches = [
            BatchInfo(
                batch_number=1,
                project="project1",
                driver="driver1",
                to_location="location1",
                items=[BatchItem(item_name="Single item 1", quantity=1.0)]
            ),
            BatchInfo(
                batch_number=2,
                project="project2",
                driver="driver2",
                to_location="location2",
                items=[BatchItem(item_name="Single item 2", quantity=1.0)]
            ),
            BatchInfo(
                batch_number=3,
                project="project3",
                driver="driver3",
                to_location="location3",
                items=[BatchItem(item_name="Single item 3", quantity=1.0)]
            )
        ]
        
        summary = self.processor.get_batch_summary(batches)
        
        assert "Found 3 batch(es):" in summary
        assert "Batch 1: 1 items to location1" in summary
        assert "Batch 2: 1 items to location2" in summary
        assert "Batch 3: 1 items to location3" in summary
        assert "Total items: 3" in summary
    
    def test_generate_summary_items_with_units(self):
        """Test generating summary with items that have units."""
        batches = [
            BatchInfo(
                batch_number=1,
                project="construction",
                driver="materials driver",
                from_location="supplier warehouse",
                items=[
                    BatchItem(item_name="Cement", quantity=50.0, unit="bags"),
                    BatchItem(item_name="Steel bars", quantity=100.0, unit="pieces"),
                    BatchItem(item_name="Paint", quantity=20.0, unit="liters")
                ]
            )
        ]
        
        summary = self.processor.get_batch_summary(batches)
        
        assert "Found 1 batch(es):" in summary
        assert "Batch 1: 3 items from supplier warehouse" in summary
        assert "(Project: construction, Driver: materials driver)" in summary
        assert "Total items: 3" in summary
    
    def test_generate_summary_decimal_quantities(self):
        """Test generating summary with decimal quantities."""
        batches = [
            BatchInfo(
                batch_number=1,
                project="precision project",
                driver="precision driver",
                to_location="precision location",
                items=[
                    BatchItem(item_name="Cable", quantity=2.5, unit="meters"),
                    BatchItem(item_name="Paint", quantity=1.5, unit="liters"),
                    BatchItem(item_name="Steel", quantity=0.5, unit="tons")
                ]
            )
        ]
        
        summary = self.processor.get_batch_summary(batches)
        
        assert "Found 1 batch(es):" in summary
        assert "Batch 1: 3 items to precision location" in summary
        assert "(Project: precision project, Driver: precision driver)" in summary
        assert "Total items: 3" in summary


if __name__ == "__main__":
    pytest.main([__file__])
