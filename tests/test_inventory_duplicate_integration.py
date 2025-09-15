"""Tests for inventory service duplicate detection integration."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import List

from src.services.inventory import InventoryService, InventoryEntry, InventoryHeader, InventoryParseResult
from src.services.duplicate_detection import DuplicateDetectionService, PotentialDuplicate, DuplicateDetectionResult


class TestInventoryDuplicateIntegration:
    """Test cases for inventory service duplicate detection integration."""
    
    @pytest.fixture
    def mock_airtable(self):
        """Create mock Airtable client."""
        mock = Mock()
        mock.get_item = AsyncMock()
        mock.create_item_if_not_exists = AsyncMock()
        mock.update_item_stock = AsyncMock()
        return mock
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        mock = Mock()
        return mock
    
    @pytest.fixture
    def mock_duplicate_detection_service(self):
        """Create mock duplicate detection service."""
        mock = Mock()
        mock.find_potential_duplicates = AsyncMock()
        mock._calculate_duplicate_similarity = Mock()
        mock.similarity_threshold = 0.7
        return mock
    
    @pytest.fixture
    def inventory_service(self, mock_airtable, mock_settings, mock_duplicate_detection_service):
        """Create InventoryService instance with mocked dependencies."""
        return InventoryService(
            airtable_client=mock_airtable,
            settings=mock_settings,
            duplicate_detection_service=mock_duplicate_detection_service
        )
    
    @pytest.fixture
    def sample_entries(self):
        """Create sample inventory entries for testing."""
        return [
            InventoryEntry(
                item_name="Cement 32.5",
                quantity=50.0,
                line_number=2,
                raw_text="Cement 32.5, 50"
            ),
            InventoryEntry(
                item_name="12mm rebar",
                quantity=120.0,
                line_number=3,
                raw_text="12mm rebar, 120"
            )
        ]
    
    @pytest.fixture
    def sample_duplicates(self):
        """Create sample potential duplicates for testing."""
        return [
            PotentialDuplicate(
                item_name="32.5 Cement",
                quantity=45.0,
                unit="bags",
                similarity_score=0.95,
                movement_id="movement_1",
                timestamp=datetime.now() - timedelta(days=2),
                location="Warehouse A",
                category="Construction Materials",
                user_name="John"
            ),
            PotentialDuplicate(
                item_name="Cement 32.5",
                quantity=50.0,
                unit="bags",
                similarity_score=0.98,
                movement_id="movement_2",
                timestamp=datetime.now() - timedelta(days=1),
                location="Warehouse B",
                category="Construction Materials",
                user_name="Sarah"
            )
        ]
    
    @pytest.fixture
    def sample_parse_result(self, sample_entries):
        """Create sample parse result for testing."""
        header = InventoryHeader(
            date="25/08/25",
            logged_by=["Trevor", "Kayesera"],
            category="Construction Materials",
            raw_text="logged by: Trevor,Kayesera",
            normalized_date="2025-08-25"
        )
        
        return InventoryParseResult(
            header=header,
            entries=sample_entries,
            total_lines=3,
            valid_entries=2,
            errors=[],
            is_valid=True,
            blank_lines=0,
            comment_lines=0,
            skipped_lines=0
        )
    
    @pytest.mark.asyncio
    async def test_check_for_duplicates(self, inventory_service, sample_entries, sample_duplicates):
        """Test checking for duplicates in inventory entries."""
        # Mock the duplicate detection service
        inventory_service.duplicate_detection_service.find_potential_duplicates.return_value = sample_duplicates
        
        # Check for duplicates
        result = await inventory_service._check_for_duplicates(sample_entries, "Test User")
        
        # Verify result
        assert result.has_duplicates == True
        assert len(result.potential_duplicates) == 4  # 2 entries × 2 duplicates each
        assert len(result.new_entries) == 2
        assert result.requires_confirmation == True
        
        # Verify that find_potential_duplicates was called for each entry
        assert inventory_service.duplicate_detection_service.find_potential_duplicates.call_count == 2
    
    @pytest.mark.asyncio
    async def test_check_for_duplicates_no_duplicates(self, inventory_service, sample_entries):
        """Test checking for duplicates when none are found."""
        # Mock the duplicate detection service to return no duplicates
        inventory_service.duplicate_detection_service.find_potential_duplicates.return_value = []
        
        # Check for duplicates
        result = await inventory_service._check_for_duplicates(sample_entries, "Test User")
        
        # Verify result
        assert result.has_duplicates == False
        assert len(result.potential_duplicates) == 0
        assert len(result.new_entries) == 0
        assert result.requires_confirmation == False
    
    @pytest.mark.asyncio
    async def test_check_for_duplicates_error_handling(self, inventory_service, sample_entries):
        """Test error handling in duplicate checking."""
        # Mock the duplicate detection service to raise an exception
        inventory_service.duplicate_detection_service.find_potential_duplicates.side_effect = Exception("Test error")
        
        # Check for duplicates
        result = await inventory_service._check_for_duplicates(sample_entries, "Test User")
        
        # Verify result shows no duplicates due to error
        assert result.has_duplicates == False
        assert len(result.potential_duplicates) == 0
        assert len(result.new_entries) == 0
        assert result.requires_confirmation == False
    
    @pytest.mark.asyncio
    async def test_store_duplicate_data(self, inventory_service, sample_duplicates, sample_parse_result):
        """Test storing duplicate data for later processing."""
        duplicate_result = DuplicateDetectionResult(
            has_duplicates=True,
            potential_duplicates=sample_duplicates,
            new_entries=sample_parse_result.entries,
            requires_confirmation=True
        )
        
        # Store duplicate data
        await inventory_service._store_duplicate_data(
            chat_id=12345,
            duplicate_result=duplicate_result,
            parse_result=sample_parse_result,
            user_id=67890,
            user_name="Test User"
        )
        
        # Verify data was stored
        assert hasattr(inventory_service, '_pending_duplicates')
        assert 12345 in inventory_service._pending_duplicates
        
        stored_data = inventory_service._pending_duplicates[12345]
        assert stored_data['user_id'] == 67890
        assert stored_data['user_name'] == "Test User"
        assert stored_data['duplicate_result'] == duplicate_result
        assert stored_data['parse_result'] == sample_parse_result
    
    @pytest.mark.asyncio
    async def test_process_duplicate_confirmation_confirm(self, inventory_service, sample_duplicates, sample_parse_result):
        """Test processing duplicate confirmation with confirm action."""
        # Store duplicate data
        duplicate_result = DuplicateDetectionResult(
            has_duplicates=True,
            potential_duplicates=sample_duplicates,
            new_entries=sample_parse_result.entries,
            requires_confirmation=True
        )
        
        await inventory_service._store_duplicate_data(
            chat_id=12345,
            duplicate_result=duplicate_result,
            parse_result=sample_parse_result,
            user_id=67890,
            user_name="Test User"
        )
        
        # Mock the consolidation processing
        inventory_service._process_duplicate_consolidation = AsyncMock(return_value=(True, "Consolidation successful"))
        
        # Process confirmation
        success, message = await inventory_service.process_duplicate_confirmation(
            chat_id=12345,
            action="confirm_duplicates",
            telegram_service=None
        )
        
        # Verify result
        assert success == True
        assert message == "Consolidation successful"
        assert inventory_service._process_duplicate_consolidation.called
    
    @pytest.mark.asyncio
    async def test_process_duplicate_confirmation_cancel(self, inventory_service, sample_duplicates, sample_parse_result):
        """Test processing duplicate confirmation with cancel action."""
        # Store duplicate data
        duplicate_result = DuplicateDetectionResult(
            has_duplicates=True,
            potential_duplicates=sample_duplicates,
            new_entries=sample_parse_result.entries,
            requires_confirmation=True
        )
        
        await inventory_service._store_duplicate_data(
            chat_id=12345,
            duplicate_result=duplicate_result,
            parse_result=sample_parse_result,
            user_id=67890,
            user_name="Test User"
        )
        
        # Mock the normal processing
        inventory_service._process_normal_inventory = AsyncMock(return_value=(True, "Normal processing successful"))
        
        # Process cancellation
        success, message = await inventory_service.process_duplicate_confirmation(
            chat_id=12345,
            action="cancel_duplicates",
            telegram_service=None
        )
        
        # Verify result
        assert success == True
        assert message == "Normal processing successful"
        assert inventory_service._process_normal_inventory.called
    
    @pytest.mark.asyncio
    async def test_process_duplicate_confirmation_no_data(self, inventory_service):
        """Test processing duplicate confirmation when no data is stored."""
        # Process confirmation without storing data first
        success, message = await inventory_service.process_duplicate_confirmation(
            chat_id=12345,
            action="confirm_duplicates",
            telegram_service=None
        )
        
        # Verify result
        assert success == False
        assert "No pending duplicate data found" in message
    
    @pytest.mark.asyncio
    async def test_process_duplicate_confirmation_unknown_action(self, inventory_service, sample_duplicates, sample_parse_result):
        """Test processing duplicate confirmation with unknown action."""
        # Store duplicate data
        duplicate_result = DuplicateDetectionResult(
            has_duplicates=True,
            potential_duplicates=sample_duplicates,
            new_entries=sample_parse_result.entries,
            requires_confirmation=True
        )
        
        await inventory_service._store_duplicate_data(
            chat_id=12345,
            duplicate_result=duplicate_result,
            parse_result=sample_parse_result,
            user_id=67890,
            user_name="Test User"
        )
        
        # Process unknown action
        success, message = await inventory_service.process_duplicate_confirmation(
            chat_id=12345,
            action="unknown_action",
            telegram_service=None
        )
        
        # Verify result
        assert success == False
        assert "Unknown action" in message
    
    def test_entries_similar(self, inventory_service, sample_entries, sample_duplicates):
        """Test entry similarity checking."""
        entry = sample_entries[0]  # Cement 32.5
        duplicate = sample_duplicates[0]  # 32.5 Cement
        
        # Mock the similarity calculation
        inventory_service.duplicate_detection_service._calculate_duplicate_similarity.return_value = 0.95
        
        # Check similarity
        result = inventory_service._entries_similar(entry, duplicate)
        
        # Verify result
        assert result == True
        inventory_service.duplicate_detection_service._calculate_duplicate_similarity.assert_called_once_with(
            entry.item_name, duplicate.item_name
        )
    
    def test_entries_similar_below_threshold(self, inventory_service, sample_entries, sample_duplicates):
        """Test entry similarity checking when below threshold."""
        entry = sample_entries[0]  # Cement 32.5
        duplicate = sample_duplicates[0]  # 32.5 Cement
        
        # Mock the similarity calculation to return low score
        inventory_service.duplicate_detection_service._calculate_duplicate_similarity.return_value = 0.5
        
        # Check similarity
        result = inventory_service._entries_similar(entry, duplicate)
        
        # Verify result
        assert result == False
    
    def test_entries_similar_error_handling(self, inventory_service, sample_entries, sample_duplicates):
        """Test entry similarity checking error handling."""
        entry = sample_entries[0]  # Cement 32.5
        duplicate = sample_duplicates[0]  # 32.5 Cement
        
        # Mock the similarity calculation to raise an exception
        inventory_service.duplicate_detection_service._calculate_duplicate_similarity.side_effect = Exception("Test error")
        
        # Check similarity
        result = inventory_service._entries_similar(entry, duplicate)
        
        # Verify result
        assert result == False


class TestInventoryDuplicateProcessing:
    """Test cases for duplicate processing workflows."""
    
    @pytest.fixture
    def mock_airtable(self):
        """Create mock Airtable client."""
        mock = Mock()
        mock.get_item = AsyncMock()
        mock.create_item_if_not_exists = AsyncMock()
        mock.update_item_stock = AsyncMock()
        return mock
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        mock = Mock()
        return mock
    
    @pytest.fixture
    def mock_duplicate_detection_service(self):
        """Create mock duplicate detection service."""
        mock = Mock()
        mock.find_potential_duplicates = AsyncMock()
        mock._calculate_duplicate_similarity = Mock()
        mock.similarity_threshold = 0.7
        return mock
    
    @pytest.fixture
    def inventory_service(self, mock_airtable, mock_settings, mock_duplicate_detection_service):
        """Create InventoryService instance with mocked dependencies."""
        return InventoryService(
            airtable_client=mock_airtable,
            settings=mock_settings,
            duplicate_detection_service=mock_duplicate_detection_service
        )
    
    @pytest.fixture
    def sample_parse_result(self):
        """Create sample parse result for testing."""
        header = InventoryHeader(
            date="25/08/25",
            logged_by=["Trevor", "Kayesera"],
            category="Construction Materials",
            raw_text="logged by: Trevor,Kayesera",
            normalized_date="2025-08-25"
        )
        
        entries = [
            InventoryEntry(
                item_name="Cement 32.5",
                quantity=50.0,
                line_number=2,
                raw_text="Cement 32.5, 50"
            ),
            InventoryEntry(
                item_name="12mm rebar",
                quantity=120.0,
                line_number=3,
                raw_text="12mm rebar, 120"
            )
        ]
        
        return InventoryParseResult(
            header=header,
            entries=entries,
            total_lines=3,
            valid_entries=2,
            errors=[],
            is_valid=True,
            blank_lines=0,
            comment_lines=0,
            skipped_lines=0
        )
    
    @pytest.mark.asyncio
    async def test_process_inventory_stocktake_with_duplicates(self, inventory_service, sample_parse_result):
        """Test processing inventory with duplicate detection enabled."""
        # Mock the parser to return a valid parse result
        inventory_service.parser.parse_inventory_command = Mock(return_value=sample_parse_result)
        
        # Mock telegram service
        mock_telegram_service = Mock()
        mock_telegram_service.send_duplicate_confirmation = AsyncMock(return_value=1)
        
        # Mock duplicate detection
        inventory_service._check_for_duplicates = AsyncMock(return_value=DuplicateDetectionResult(
            has_duplicates=True,
            potential_duplicates=[],
            new_entries=[],
            requires_confirmation=True
        ))
        
        # Mock storing duplicate data
        inventory_service._store_duplicate_data = AsyncMock()
        
        # Process inventory
        success, message = await inventory_service.process_inventory_stocktake(
            command_text="test command",
            user_id=12345,
            user_name="Test User",
            validate_only=False,
            telegram_service=mock_telegram_service,
            chat_id=67890
        )
        
        # Verify result
        assert success == True
        assert message == "duplicate_detection_sent"
        assert inventory_service._check_for_duplicates.called
        assert inventory_service._store_duplicate_data.called
    
    @pytest.mark.asyncio
    async def test_process_inventory_stocktake_without_duplicates(self, inventory_service, sample_parse_result):
        """Test processing inventory without duplicates."""
        # Mock the parser to return a valid parse result
        inventory_service.parser.parse_inventory_command = Mock(return_value=sample_parse_result)
        
        # Mock duplicate detection
        inventory_service._check_for_duplicates = AsyncMock(return_value=DuplicateDetectionResult(
            has_duplicates=False,
            potential_duplicates=[],
            new_entries=[],
            requires_confirmation=False
        ))
        
        # Mock normal processing
        inventory_service._process_inventory_entry = AsyncMock(return_value={
            "success": True,
            "created": False,
            "item_name": "Test Item",
            "quantity": 10.0,
            "previous_quantity": 5.0,
            "new_total": 15.0,
            "message": "Test message"
        })
        
        # Process inventory
        success, message = await inventory_service.process_inventory_stocktake(
            command_text="test command",
            user_id=12345,
            user_name="Test User",
            validate_only=False,
            telegram_service=None,
            chat_id=None
        )
        
        # Verify result
        assert success == True
        assert "duplicate_detection_sent" not in message
    
    @pytest.mark.asyncio
    async def test_process_inventory_stocktake_validation_only(self, inventory_service, sample_parse_result):
        """Test processing inventory in validation mode."""
        # Mock the parser to return a valid parse result
        inventory_service.parser.parse_inventory_command = Mock(return_value=sample_parse_result)
        
        # Process inventory in validation mode
        success, message = await inventory_service.process_inventory_stocktake(
            command_text="test command",
            user_id=12345,
            user_name="Test User",
            validate_only=True,
            telegram_service=None,
            chat_id=None
        )
        
        # Verify result
        assert success == True
        assert "Validation" in message or "validation" in message


class TestInventoryDuplicateConsolidation:
    """Test cases for duplicate consolidation processing."""
    
    @pytest.fixture
    def mock_airtable(self):
        """Create mock Airtable client."""
        mock = Mock()
        mock.get_item = AsyncMock()
        mock.create_item_if_not_exists = AsyncMock()
        mock.update_item_stock = AsyncMock()
        return mock
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        mock = Mock()
        return mock
    
    @pytest.fixture
    def mock_duplicate_detection_service(self):
        """Create mock duplicate detection service."""
        mock = Mock()
        mock.find_potential_duplicates = AsyncMock()
        mock._calculate_duplicate_similarity = Mock()
        mock.similarity_threshold = 0.7
        return mock
    
    @pytest.fixture
    def inventory_service(self, mock_airtable, mock_settings, mock_duplicate_detection_service):
        """Create InventoryService instance with mocked dependencies."""
        return InventoryService(
            airtable_client=mock_airtable,
            settings=mock_settings,
            duplicate_detection_service=mock_duplicate_detection_service
        )
    
    @pytest.fixture
    def sample_entries(self):
        """Create sample inventory entries for testing."""
        return [
            InventoryEntry(
                item_name="Cement 32.5",
                quantity=50.0,
                line_number=2,
                raw_text="Cement 32.5, 50"
            ),
            InventoryEntry(
                item_name="12mm rebar",
                quantity=120.0,
                line_number=3,
                raw_text="12mm rebar, 120"
            )
        ]
    
    @pytest.fixture
    def sample_duplicates(self):
        """Create sample potential duplicates for testing."""
        return [
            PotentialDuplicate(
                item_name="32.5 Cement",
                quantity=45.0,
                unit="bags",
                similarity_score=0.95,
                movement_id="movement_1",
                timestamp=datetime.now() - timedelta(days=2),
                location="Warehouse A",
                category="Construction Materials",
                user_name="John"
            ),
            PotentialDuplicate(
                item_name="Cement 32.5",
                quantity=50.0,
                unit="bags",
                similarity_score=0.98,
                movement_id="movement_2",
                timestamp=datetime.now() - timedelta(days=1),
                location="Warehouse B",
                category="Construction Materials",
                user_name="Sarah"
            )
        ]
    
    @pytest.mark.asyncio
    async def test_consolidate_with_duplicates(self, inventory_service, sample_entries, sample_duplicates):
        """Test consolidating inventory entry with duplicates."""
        entry = sample_entries[0]  # Cement 32.5
        duplicates = [sample_duplicates[0]]  # 32.5 Cement
        
        # Mock existing item
        mock_item = Mock()
        mock_item.on_hand = 100.0
        inventory_service.airtable.get_item.return_value = mock_item
        
        # Mock stock update
        inventory_service._update_item_stock = AsyncMock(return_value=True)
        
        # Consolidate
        result = await inventory_service._consolidate_with_duplicates(
            entry, duplicates, "2025-08-25", "Test User", "Construction Materials"
        )
        
        # Verify result
        assert result["success"] == True
        assert result["created"] == False
        assert result["item_name"] == duplicates[0].item_name
        assert result["quantity"] == entry.quantity
        assert result["previous_quantity"] == 100.0
        assert result["new_total"] == 150.0
        assert "Consolidated" in result["message"]
    
    @pytest.mark.asyncio
    async def test_consolidate_with_duplicates_item_not_found(self, inventory_service, sample_entries, sample_duplicates):
        """Test consolidating when duplicate item is not found."""
        entry = sample_entries[0]  # Cement 32.5
        duplicates = [sample_duplicates[0]]  # 32.5 Cement
        
        # Mock item not found
        inventory_service.airtable.get_item.return_value = None
        
        # Mock normal processing
        inventory_service._process_inventory_entry = AsyncMock(return_value={
            "success": True,
            "created": True,
            "item_name": entry.item_name,
            "quantity": entry.quantity,
            "previous_quantity": 0.0,
            "message": "Created new item"
        })
        
        # Consolidate
        result = await inventory_service._consolidate_with_duplicates(
            entry, duplicates, "2025-08-25", "Test User", "Construction Materials"
        )
        
        # Verify result falls back to normal processing
        assert result["success"] == True
        assert result["created"] == True
        assert result["item_name"] == entry.item_name
        assert inventory_service._process_inventory_entry.called
    
    @pytest.mark.asyncio
    async def test_consolidate_with_duplicates_error_handling(self, inventory_service, sample_entries, sample_duplicates):
        """Test error handling in duplicate consolidation."""
        entry = sample_entries[0]  # Cement 32.5
        duplicates = [sample_duplicates[0]]  # 32.5 Cement
        
        # Mock exception
        inventory_service.airtable.get_item.side_effect = Exception("Test error")
        
        # Consolidate
        result = await inventory_service._consolidate_with_duplicates(
            entry, duplicates, "2025-08-25", "Test User", "Construction Materials"
        )
        
        # Verify result
        assert result["success"] == False
        assert result["created"] == False
        assert result["item_name"] == entry.item_name
        assert "Error consolidating" in result["message"]
