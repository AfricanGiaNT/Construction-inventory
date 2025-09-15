"""Test Phase 3 User Interaction Features for Batch Duplicate Handling."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.schemas import (
    BatchItem, DuplicateItem, DuplicateMatchType, MovementType, 
    DuplicateProcessingResult, DuplicateConfirmationAction
)
from src.services.batch_duplicate_handler import BatchDuplicateHandler
from src.services.enhanced_batch_processor import EnhancedBatchProcessor
from src.telegram_service import TelegramService


class TestPhase3UserInteractionFeatures:
    """Test comprehensive user interaction features for Phase 3."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock dependencies
        self.mock_airtable = AsyncMock()
        self.mock_stock_service = AsyncMock()
        self.mock_settings = MagicMock()
        
        # Create services
        self.duplicate_handler = BatchDuplicateHandler(self.mock_airtable, self.mock_stock_service)
        self.enhanced_processor = EnhancedBatchProcessor(
            self.mock_airtable, self.mock_settings, self.mock_stock_service
        )
        self.telegram_service = TelegramService(self.mock_settings)
        
        # Sample test data
        self.sample_duplicates = [
            DuplicateItem(
                batch_item={'item_name': 'Cement 50kg', 'quantity': 10},
                existing_item={'name': 'Cement 50kg bags', 'on_hand': 25, 'project': 'Site A', 'units': [{'name': 'bags', 'conversion_factor': 1.0}]},
                similarity_score=0.95,
                match_type=DuplicateMatchType.EXACT,
                batch_number=1,
                item_index=0
            ),
            DuplicateItem(
                batch_item={'item_name': 'Steel Bar 12mm', 'quantity': 5},
                existing_item={'name': 'Steel Bars 12mm', 'on_hand': 15, 'project': 'Site B', 'units': [{'name': 'pieces', 'conversion_factor': 1.0}]},
                similarity_score=0.88,
                match_type=DuplicateMatchType.SIMILAR,
                batch_number=1,
                item_index=1
            )
        ]
    
    @pytest.mark.asyncio
    async def test_user_confirmation_workflow(self):
        """Test the complete user confirmation workflow."""
        # Test individual confirmation
        duplicate = self.sample_duplicates[0]
        result = await self.duplicate_handler.process_user_confirmation(
            duplicate, "confirm", MovementType.IN, 123, "Test User"
        )
        
        assert result.success_count == 1
        assert len(result.processed_duplicates) == 1
        assert len(result.merged_items) == 1
    
    @pytest.mark.asyncio
    async def test_individual_duplicate_confirmation(self):
        """Test individual duplicate confirmation processing."""
        duplicate = self.sample_duplicates[1]
        
        # Test confirm action
        result = await self.duplicate_handler.process_user_confirmation(
            duplicate, "confirm", MovementType.IN, 123, "Test User"
        )
        
        assert result.success_count == 1
        assert len(result.processed_duplicates) == 1
    
    @pytest.mark.asyncio
    async def test_duplicate_cancellation(self):
        """Test duplicate cancellation workflow."""
        duplicate = self.sample_duplicates[0]
        
        result = await self.duplicate_handler.process_user_confirmation(
            duplicate, "cancel", MovementType.IN, 123, "Test User"
        )
        
        assert result.failure_count == 1
        assert len(result.rejected_duplicates) == 1
        assert result.success_count == 0
    
    @pytest.mark.asyncio
    async def test_create_new_item_for_duplicate(self):
        """Test creating new item for duplicate instead of merging."""
        duplicate = self.sample_duplicates[1]
        
        # Mock successful stock movement creation
        self.mock_stock_service.stock_in = AsyncMock(return_value=(True, "Success", 0.0, 10.0))
        
        result = await self.duplicate_handler.process_user_confirmation(
            duplicate, "create_new", MovementType.IN, 123, "Test User"
        )
        
        assert result.success_count == 1
        assert len(result.new_items_created) == 1
        self.mock_stock_service.stock_in.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stock_level_validation_for_out_movements(self):
        """Test stock level validation for OUT movements with duplicates."""
        # Test with sufficient stock
        duplicate_sufficient = DuplicateItem(
            batch_item={'item_name': 'Cement 50kg', 'quantity': 10},
            existing_item={'name': 'Cement 50kg bags', 'on_hand': 25, 'units': [{'name': 'bags', 'conversion_factor': 1.0}]},
            similarity_score=0.95,
            match_type=DuplicateMatchType.EXACT,
            batch_number=1,
            item_index=0
        )
        
        result = await self.duplicate_handler.validate_stock_levels(
            [duplicate_sufficient], MovementType.OUT
        )
        
        assert result["valid"] is True
        assert len(result["warnings"]) == 0
        
        # Test with insufficient stock
        duplicate_insufficient = DuplicateItem(
            batch_item={'item_name': 'Steel Bar 12mm', 'quantity': 20},
            existing_item={'name': 'Steel Bars 12mm', 'on_hand': 15, 'units': [{'name': 'pieces', 'conversion_factor': 1.0}]},
            similarity_score=0.88,
            match_type=DuplicateMatchType.SIMILAR,
            batch_number=1,
            item_index=1
        )
        
        result = await self.duplicate_handler.validate_stock_levels(
            [duplicate_insufficient], MovementType.OUT
        )
        
        assert result["valid"] is False
        assert len(result["insufficient_stock"]) == 1
        assert result["insufficient_stock"][0]["shortfall"] == 5
    
    @pytest.mark.asyncio
    async def test_project_conflict_handling(self):
        """Test project conflict handling by appending new projects."""
        duplicate = self.sample_duplicates[0]
        new_project = "Site C"
        
        # Mock successful Airtable update
        self.mock_airtable.update_item = AsyncMock(return_value=True)
        
        result = await self.duplicate_handler.handle_project_conflicts(
            duplicate, new_project
        )
        
        assert result["success"] is True
        assert "Site A, Site C" in result["updated_projects"]
        self.mock_airtable.update_item.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_duplicate_confirmation_data_storage(self):
        """Test storing and retrieving duplicate confirmation data."""
        chat_id = 12345
        duplicates = self.sample_duplicates
        movement_type = MovementType.IN
        user_id = 123
        user_name = "Test User"
        
        # Store data
        await self.enhanced_processor._store_duplicate_confirmation_data(
            chat_id, duplicates, movement_type, user_id, user_name
        )
        
        # Retrieve data
        stored_data = await self.enhanced_processor.get_duplicate_confirmation_data(chat_id)
        
        assert stored_data is not None
        assert stored_data['movement_type'] == movement_type
        assert stored_data['user_id'] == user_id
        assert stored_data['user_name'] == user_name
        assert len(stored_data['duplicates']) == 2
        assert len(stored_data['confirmed_items']) == 0
        assert len(stored_data['cancelled_items']) == 0
    
    @pytest.mark.asyncio
    async def test_individual_duplicate_confirmation_processing(self):
        """Test processing individual duplicate confirmations."""
        chat_id = 12345
        
        # Store test data
        await self.enhanced_processor._store_duplicate_confirmation_data(
            chat_id, self.sample_duplicates, MovementType.IN, 123, "Test User"
        )
        
        # Process individual confirmation
        result = await self.enhanced_processor.process_duplicate_confirmation(
            chat_id, "confirm", item_index=0
        )
        
        assert result["success"] is True
        assert "Processed item 1" in result["message"]
        assert result["all_processed"] is False  # Only 1 of 2 items processed
    
    @pytest.mark.asyncio
    async def test_bulk_duplicate_confirmation_processing(self):
        """Test processing bulk duplicate confirmations."""
        chat_id = 12345
        
        # Store test data
        await self.enhanced_processor._store_duplicate_confirmation_data(
            chat_id, self.sample_duplicates, MovementType.IN, 123, "Test User"
        )
        
        # Process bulk confirmation
        result = await self.enhanced_processor.process_duplicate_confirmation(
            chat_id, "confirm_all"
        )
        
        assert result["success"] is True
        assert result["confirmed_count"] == 2
        assert result["cancelled_count"] == 0
    
    @pytest.mark.asyncio
    async def test_telegram_confirmation_dialog_creation(self):
        """Test creating Telegram confirmation dialogs."""
        duplicates = self.sample_duplicates
        movement_type = "IN"
        batch_info = {"batch_number": 1, "total_batches": 2}
        
        # Test message formatting
        message = self.telegram_service._format_duplicate_confirmation_message(
            duplicates, movement_type, batch_info
        )
        
        assert "Potential Duplicates Detected!" in message
        assert "Batch 1 of 2" in message
        assert "Cement 50kg" in message
        assert "Steel Bar 12mm" in message
        assert "Similarity: 95.0%" in message
        assert "Similarity: 88.0%" in message
    
    @pytest.mark.asyncio
    async def test_telegram_keyboard_creation(self):
        """Test creating Telegram inline keyboards for duplicate confirmation."""
        # Test with individual buttons (≤5 duplicates)
        keyboard = self.telegram_service._create_duplicate_confirmation_keyboard(
            self.sample_duplicates
        )
        
        assert keyboard is not None
        # Should have individual buttons for each duplicate plus bulk actions
        
        # Test with bulk buttons (>5 duplicates)
        many_duplicates = self.sample_duplicates * 3  # 6 duplicates
        keyboard = self.telegram_service._create_duplicate_confirmation_keyboard(
            many_duplicates
        )
        
        assert keyboard is not None
        # Should fall back to bulk action buttons
    
    @pytest.mark.asyncio
    async def test_enhanced_batch_processing_with_user_confirmation(self):
        """Test enhanced batch processing that requires user confirmation."""
        command_text = """
        -batch 1-
        project: test site, driver: test driver
        Cement 50kg, 10 bags
        Steel Bar 12mm, 5 pieces
        """
        
        # Mock existing items for duplicate detection
        existing_items = [
            {
                'name': 'Cement 50kg bags',
                'on_hand': 25,
                'project': 'Site A',
                'units': [{'name': 'bags', 'conversion_factor': 1.0}]
            },
            {
                'name': 'Steel Bars 12mm',
                'on_hand': 15,
                'project': 'Site B',
                'units': [{'name': 'pieces', 'conversion_factor': 1.0}]
            }
        ]
        
        self.mock_airtable.get_all_items = AsyncMock(return_value=existing_items)
        
        # Mock the parser to return valid result
        with patch('src.services.enhanced_batch_processor.BatchMovementParser') as mock_parser:
            mock_parse_result = MagicMock()
            mock_parse_result.is_valid = True
            mock_parse_result.batches = [MagicMock()]
            mock_parse_result.errors = []
            mock_parser.return_value.parse_batch_command.return_value = mock_parse_result
            
            # Mock duplicate analysis
            with patch.object(self.enhanced_processor.duplicate_handler, 'identify_duplicates') as mock_identify:
                from src.schemas import DuplicateAnalysis
                mock_analysis = DuplicateAnalysis()
                mock_analysis.duplicate_count = 2
                mock_analysis.non_duplicate_count = 0
                mock_analysis.duplicates = self.sample_duplicates
                mock_analysis.total_items = 2
                mock_identify.return_value = mock_analysis
                
                # Mock non-duplicate processing
                with patch.object(self.enhanced_processor.duplicate_handler, 'process_non_duplicates') as mock_non_duplicates:
                    mock_non_duplicates.return_value = DuplicateProcessingResult()
                    
                    # Mock duplicate processing with user confirmation required
                    with patch.object(self.enhanced_processor.duplicate_handler, 'process_duplicates') as mock_duplicates:
                        mock_duplicate_result = DuplicateProcessingResult()
                        mock_duplicate_result.requires_user_confirmation = True
                        mock_duplicate_result.pending_duplicates = self.sample_duplicates
                        mock_duplicates.return_value = mock_duplicate_result
                        
                        # Process the command
                        result = await self.enhanced_processor.process_batch_command_with_duplicates(
                            command_text, MovementType.IN, 123, "Test User"
                        )
                        
                        # Verify that user confirmation data was stored
                        stored_data = await self.enhanced_processor.get_duplicate_confirmation_data(123)  # Use user_id as chat_id
                        assert stored_data is not None
                        assert len(stored_data['duplicates']) == 2
    
    @pytest.mark.asyncio
    async def test_error_handling_in_user_confirmation(self):
        """Test error handling in user confirmation workflows."""
        # Test with invalid action
        duplicate = self.sample_duplicates[0]
        result = await self.duplicate_handler.process_user_confirmation(
            duplicate, "invalid_action", MovementType.IN, 123, "Test User"
        )
        
        assert result.failure_count == 1
        assert result.success_count == 0
        
        # Test with missing confirmation data
        result = await self.enhanced_processor.process_duplicate_confirmation(
            99999, "confirm", item_index=0
        )
        
        assert result["success"] is False
        assert "No pending duplicate confirmations found" in result["message"]
    
    @pytest.mark.asyncio
    async def test_stock_validation_edge_cases(self):
        """Test edge cases in stock validation."""
        # Test with IN movement (should always be valid)
        result = await self.duplicate_handler.validate_stock_levels(
            self.sample_duplicates, MovementType.IN
        )
        
        assert result["valid"] is True
        assert len(result["warnings"]) == 0
        
        # Test with empty duplicates list
        result = await self.duplicate_handler.validate_stock_levels(
            [], MovementType.OUT
        )
        
        assert result["valid"] is True
        assert len(result["warnings"]) == 0
    
    @pytest.mark.asyncio
    async def test_project_conflict_edge_cases(self):
        """Test edge cases in project conflict handling."""
        duplicate = self.sample_duplicates[0]
        
        # Test with project that already exists
        existing_item = duplicate.existing_item.copy()
        existing_item['project'] = 'Site C'
        duplicate_with_existing = DuplicateItem(
            batch_item=duplicate.batch_item,
            existing_item=existing_item,
            similarity_score=duplicate.similarity_score,
            match_type=duplicate.match_type,
            batch_number=duplicate.batch_number,
            item_index=duplicate.item_index
        )
        
        result = await self.duplicate_handler.handle_project_conflicts(
            duplicate_with_existing, 'Site C'
        )
        
        assert result["success"] is True
        assert "already exists" in result["message"]
        
        # Test with database update failure
        self.mock_airtable.update_item = AsyncMock(return_value=False)
        
        result = await self.duplicate_handler.handle_project_conflicts(
            duplicate, 'Site D'
        )
        
        assert result["success"] is False
        assert "Failed to update project field" in result["message"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
