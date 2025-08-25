# Stock Query Feature Implementation Plan

## Overview

This document outlines the implementation plan for adding a comprehensive stock query feature to the Construction Inventory Bot. The feature will allow users to search for items using fuzzy matching, view detailed stock information, and see pending movements for each item.

## Objectives

1. Enable users to query stock levels using `/stock <item_name>` command
2. Implement fuzzy search to find items with similar names
3. Display search results with numbered options for user selection
4. Show comprehensive stock information including pending movements
5. Integrate with existing approval system to show pending batch status
6. Implement intelligent caching for performance optimization

## Implementation Phases

### Phase 1: Command Parser and Routing

**Objective**: Add the `/stock` command to the bot's command system

**Tasks**:
1. Add stock command pattern to CommandParser
2. Update command routing in main bot
3. Create basic command handler structure

**Files to modify**:
- `src/commands.py` - Add stock command pattern
- `src/main.py` - Add stock command handler

**Testing for Phase 1**:
1. **Unit Tests**:
   - Test that `/stock` command is correctly parsed
   - Verify command arguments are captured properly
   - Test command routing to correct handler

2. **Test Code**:
```python
def test_stock_command_parsing():
    parser = CommandParser()
    
    # Test valid stock command
    command = parser.parse_command("/stock cement", 123, 456, "Test User", 1, 1)
    assert command.command == "stock"
    assert command.args == ["cement"]
    
    # Test stock command with spaces
    command = parser.parse_command("/stock m24 bolts 100x20mm", 123, 456, "Test User", 1, 1)
    assert command.command == "stock"
    assert command.args == ["m24 bolts 100x20mm"]
    
    # Test invalid stock command (no query)
    command = parser.parse_command("/stock", 123, 456, "Test User", 1, 1)
    assert command is None

def test_stock_command_routing():
    router = CommandRouter()
    
    # Test routing to stock handler
    command, error = await router.route_command("/stock cement", 123, 456, "Test User", 1, 1)
    assert command is not None
    assert command.command == "stock"
    assert error is None
```

### Phase 2: Fuzzy Search Service Implementation

**Objective**: Create the core fuzzy search functionality for finding items

**Tasks**:
1. Create StockQueryService with fuzzy search algorithm
2. Implement similarity scoring using difflib.SequenceMatcher
3. Add result ranking and limiting
4. Implement caching mechanism

**Files to create/modify**:
- `src/services/stock_query.py` - New service
- `src/airtable_client.py` - Add methods for bulk item retrieval

**Testing for Phase 2**:
1. **Unit Tests**:
   - Test fuzzy search algorithm accuracy
   - Test result ranking and limiting
   - Test caching functionality
   - Test edge cases (empty queries, no results)

2. **Test Code**:
```python
def test_fuzzy_search_algorithm():
    service = StockQueryService(mock_airtable_client)
    
    # Test exact match
    results = service.fuzzy_search_items("cement", limit=5)
    assert len(results) > 0
    assert results[0].name.lower() == "cement"
    
    # Test partial match
    results = service.fuzzy_search_items("cem", limit=5)
    assert len(results) > 0
    assert any("cement" in result.name.lower() for result in results)
    
    # Test fuzzy match
    results = service.fuzzy_search_items("cement bags", limit=5)
    assert len(results) > 0
    assert any("cement" in result.name.lower() for result in results)
    
    # Test no results
    results = service.fuzzy_search_items("nonexistentitem", limit=5)
    assert len(results) == 0

def test_result_ranking():
    service = StockQueryService(mock_airtable_client)
    
    # Test exact matches come first
    results = service.fuzzy_search_items("cement", limit=5)
    exact_matches = [r for r in results if r.name.lower() == "cement"]
    fuzzy_matches = [r for r in results if r.name.lower() != "cement"]
    
    # Exact matches should come before fuzzy matches
    if exact_matches and fuzzy_matches:
        exact_indices = [results.index(r) for r in exact_matches]
        fuzzy_indices = [results.index(r) for r in fuzzy_matches]
        assert max(exact_indices) < min(fuzzy_indices)

def test_caching():
    service = StockQueryService(mock_airtable_client)
    
    # First search should populate cache
    results1 = service.fuzzy_search_items("cement", limit=5)
    assert len(results1) > 0
    
    # Second search should use cache
    results2 = service.fuzzy_search_items("cement", limit=5)
    assert results1 == results2
    
    # Cache should be invalidated after TTL
    # (Test with mocked time)
```

### Phase 3: Enhanced Airtable Client Methods

**Objective**: Extend Airtable client to support stock query requirements

**Tasks**:
1. Add method to retrieve all items for fuzzy search
2. Add method to get item movement history
3. Add method to check pending approvals for items
4. Optimize queries for performance

**Files to modify**:
- `src/airtable_client.py`

**Testing for Phase 3**:
1. **Unit Tests**:
   - Test bulk item retrieval
   - Test movement history retrieval
   - Test pending approvals query
   - Test query performance with large datasets

2. **Test Code**:
```python
def test_get_all_items():
    client = AirtableClient(mock_settings)
    
    # Test retrieving all items
    items = await client.get_all_items()
    assert len(items) > 0
    assert all(isinstance(item, Item) for item in items)
    
    # Test item structure
    item = items[0]
    assert hasattr(item, 'name')
    assert hasattr(item, 'on_hand')
    assert hasattr(item, 'base_unit')

def test_get_item_movements():
    client = AirtableClient(mock_settings)
    
    # Test movement retrieval
    movements = await client.get_item_movements("cement")
    assert isinstance(movements, list)
    
    # Test movement structure
    if movements:
        movement = movements[0]
        assert hasattr(movement, 'item_name')
        assert hasattr(movement, 'quantity')
        assert hasattr(movement, 'movement_type')

def test_get_pending_approvals():
    client = AirtableClient(mock_settings)
    
    # Test pending approvals retrieval
    approvals = await client.get_pending_approvals_for_item("cement")
    assert isinstance(approvals, list)
    
    # Test approval structure
    if approvals:
        approval = approvals[0]
        assert hasattr(approval, 'batch_id')
        assert hasattr(approval, 'status')
```

### Phase 4: Stock Query Handler Implementation

**Objective**: Implement the main stock query logic in the bot

**Tasks**:
1. Create stock command handler in main bot
2. Integrate with StockQueryService
3. Handle user confirmation flow
4. Implement error handling and help messages

**Files to modify**:
- `src/main.py`

**Testing for Phase 4**:
1. **Integration Tests**:
   - Test complete stock query flow
   - Test user confirmation handling
   - Test error scenarios
   - Test help message display

2. **Test Code**:
```python
async def test_stock_command_handler():
    bot = ConstructionInventoryBot()
    
    # Test successful stock query
    await bot.handle_stock_command(123, 456, "Test User", "cement")
    
    # Verify message was sent
    assert len(bot.telegram_service.bot.sent_messages) == 1
    message = bot.telegram_service.bot.sent_messages[0]
    assert "Stock Query Results" in message["text"]
    
    # Test help message for empty query
    await bot.handle_stock_command(123, 456, "Test User", "")
    assert len(bot.telegram_service.bot.sent_messages) == 2
    help_message = bot.telegram_service.bot.sent_messages[1]
    assert "Usage" in help_message["text"]

async def test_user_confirmation_flow():
    bot = ConstructionInventoryBot()
    
    # Test number selection
    await bot.handle_stock_confirmation(123, 456, "Test User", "1")
    
    # Test exact name confirmation
    await bot.handle_stock_confirmation(123, 456, "Test User", "cement bags")
    
    # Test invalid confirmation
    await bot.handle_stock_confirmation(123, 456, "Test User", "invalid")
    # Should show error message
```

### Phase 5: Telegram Service Display Methods

**Objective**: Create user-friendly display methods for stock query results

**Tasks**:
1. Implement search results display
2. Implement detailed item information display
3. Add pending movements and batch status display
4. Format messages for readability

**Files to modify**:
- `src/telegram_service.py`

**Testing for Phase 5**:
1. **Unit Tests**:
   - Test message formatting
   - Test HTML formatting
   - Test emoji usage
   - Test message length limits

2. **Test Code**:
```python
def test_search_results_display():
    service = TelegramService(mock_settings)
    
    # Test search results formatting
    results = [mock_item1, mock_item2, mock_item3]
    success = await service.send_stock_search_results(123, "cement", results, {})
    
    assert success is True
    assert len(service.bot.sent_messages) == 1
    
    message = service.bot.sent_messages[0]
    assert "Stock Query Results" in message["text"]
    assert "1." in message["text"]
    assert "2." in message["text"]
    assert "3." in message["text"]

def test_item_details_display():
    service = TelegramService(mock_settings)
    
    # Test detailed item display
    success = await service.send_item_details(123, mock_item, [], False)
    
    assert success is True
    message = service.bot.sent_messages[0]
    assert "On Hand" in message["text"]
    assert "Location" in message["text"]
    assert "Project" in message["text"]
    assert "Last Updated" in message["text"]

def test_pending_movements_display():
    service = TelegramService(mock_settings)
    
    # Test pending movements display
    pending_movements = [mock_movement1, mock_movement2]
    success = await service.send_item_details(123, mock_item, pending_movements, True)
    
    assert success is True
    message = service.bot.sent_messages[0]
    assert "Pending: 2 movements" in message["text"]
    assert "Pending Batch" in message["text"]
```

### Phase 6: Integration and End-to-End Testing

**Objective**: Ensure all components work together seamlessly

**Tasks**:
1. Integrate all services and handlers
2. Test complete user workflows
3. Performance testing with large datasets
4. Error handling and edge case testing

**Testing for Phase 6**:
1. **End-to-End Tests**:
   - Complete stock query workflow
   - User confirmation and detail display
   - Error handling scenarios
   - Performance with large item tables

2. **Test Code**:
```python
async def test_complete_stock_query_workflow():
    """Test the complete stock query workflow from command to result display."""
    bot = ConstructionInventoryBot()
    
    # Step 1: User sends stock query
    await bot.process_update(mock_update("/stock cement"))
    
    # Step 2: Bot shows search results
    assert len(bot.telegram_service.bot.sent_messages) == 1
    results_message = bot.telegram_service.bot.sent_messages[0]
    assert "Stock Query Results" in results_message["text"]
    
    # Step 3: User confirms selection
    await bot.process_update(mock_update("cement bags"))
    
    # Step 4: Bot shows detailed information
    assert len(bot.telegram_service.bot.sent_messages) == 2
    details_message = bot.telegram_service.bot.sent_messages[1]
    assert "On Hand" in details_message["text"]
    assert "cement bags" in details_message["text"]

async def test_performance_with_large_dataset():
    """Test performance with large number of items."""
    bot = ConstructionInventoryBot()
    
    # Mock large dataset (1000+ items)
    mock_large_dataset(1000)
    
    # Test search performance
    start_time = time.time()
    await bot.handle_stock_command(123, 456, "Test User", "test")
    end_time = time.time()
    
    # Should complete within reasonable time
    assert (end_time - start_time) < 2.0  # 2 seconds max
    
    # Verify results are limited
    message = bot.telegram_service.bot.sent_messages[0]
    assert message["text"].count("1.") <= 5  # Max 5 results
```

## Implementation Order

1. **Phase 1**: Command Parser and Routing (Foundation)
2. **Phase 2**: Fuzzy Search Service (Core Logic)
3. **Phase 3**: Enhanced Airtable Client (Data Access)
4. **Phase 4**: Stock Query Handler (Integration)
5. **Phase 5**: Telegram Service Display (User Interface)
6. **Phase 6**: Integration and Testing (Quality Assurance)

## Success Criteria

- Users can successfully query stock using `/stock <item_name>`
- Fuzzy search finds items with similar names
- Search results are displayed clearly with numbered options
- Detailed stock information is shown after user confirmation
- Pending movements and batch status are displayed
- Performance is acceptable with large item tables
- All error scenarios are handled gracefully
- Comprehensive test coverage is maintained

## Dependencies

- Existing command parsing system
- Airtable client infrastructure
- Telegram service framework
- Approval system integration
- Caching mechanism

## Risk Mitigation

1. **Performance**: Implement result limiting and caching
2. **User Experience**: Clear error messages and help text
3. **Data Accuracy**: Validate all queries and handle edge cases
4. **Integration**: Thorough testing of all service interactions
