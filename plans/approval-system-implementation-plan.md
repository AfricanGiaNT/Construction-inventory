# Approval System and Enhanced Summaries Implementation Plan

## Overview

This document outlines the implementation plan for adding a comprehensive approval system for all inventory movements (single and batch entries) in the Construction Inventory Bot. The system will require admin approval for all stock movements, provide pre-approval summaries, and generate detailed success reports after approval.

## Objectives

1. Require admin approval for all inventory movements (in/out/adjust)
2. Show pre-approval summary of items to be processed
3. Process movements only after admin approval
4. Show detailed success summary after processing, including before/after stock levels
5. Support batch approval via inline buttons
6. Track and report errors for failed items

## Implementation Phases

### Phase 1: Schema Updates

**Objective**: Update data models to support the approval workflow

1. Update MovementStatus enum to include new statuses:
   - Add `PENDING_APPROVAL` status for items awaiting approval
   - Add `REJECTED` status for rejected items

2. Create BatchApproval model to track approval requests:
   - Unique batch ID for reference
   - List of movements in the batch
   - User information
   - Stock levels before/after processing
   - Timestamp and status tracking
   - Failed entries tracking

**Files to modify**:
- `src/schemas.py`

**Testing for Phase 1**:
1. **Unit Tests**:
   - Test that the MovementStatus enum correctly includes new statuses
   - Verify BatchApproval model can be instantiated with all required fields
   - Verify BatchApproval validates required fields properly
   - Test serialization/deserialization of BatchApproval objects

2. **Test Code**:
```python
def test_movement_status_enum():
    # Verify new statuses are available
    assert MovementStatus.PENDING_APPROVAL.value == "Pending Approval"
    assert MovementStatus.REJECTED.value == "Rejected"
    
    # Test usage in a StockMovement
    movement = StockMovement(
        item_name="cement",
        movement_type=MovementType.IN,
        quantity=10.0,
        unit="bags",
        signed_base_quantity=10.0,
        status=MovementStatus.PENDING_APPROVAL,
        user_id="123",
        user_name="Test User"
    )
    assert movement.status == MovementStatus.PENDING_APPROVAL

def test_batch_approval_model():
    # Create a batch approval object
    batch = BatchApproval(
        batch_id="test_batch_001",
        movements=[],
        user_id="123",
        user_name="Test User",
        chat_id=456,
        before_levels={"cement": 10.0}
    )
    
    # Test defaults
    assert batch.status == "Pending"
    assert batch.after_levels == {}
    assert batch.failed_entries == []
    
    # Test adding movements
    movement = StockMovement(...)  # Create a test movement
    batch.movements.append(movement)
    assert len(batch.movements) == 1
```

### Phase 2: Batch Stock Service Enhancement

**Objective**: Modify batch processing to support approval workflow

1. Implement method to prepare batch approvals without processing:
   - Create unique batch ID
   - Collect current stock levels for items
   - Create batch approval object
   - Store pending approvals in memory or database

2. Add pending approvals storage and management:
   - In-memory dictionary for development
   - Later can be migrated to database storage

**Files to modify**:
- `src/services/batch_stock.py`

**Testing for Phase 2**:
1. **Unit Tests**:
   - Test batch ID generation is unique
   - Test current stock levels are correctly collected
   - Test batch approval objects are stored and retrievable
   - Verify before/after stock level tracking works correctly

2. **Integration Tests**:
   - Test interaction with AirtableClient to fetch current stock levels
   - Verify batch preparation works with real stock items

3. **Test Code**:
```python
@pytest.mark.asyncio
async def test_prepare_batch_approval():
    # Setup mock airtable client that returns predetermined item levels
    mock_airtable = MockAirtableClient()
    mock_airtable.add_item("cement", 100.0)
    mock_airtable.add_item("steel", 50.0)
    
    batch_service = BatchStockService(mock_airtable, settings, mock_stock_service)
    
    # Create test movements
    movements = [
        StockMovement(item_name="cement", quantity=10, unit="bags", ...),
        StockMovement(item_name="steel", quantity=20, unit="pieces", ...)
    ]
    
    # Test prepare_batch_approval
    success, batch_id, batch_approval = await batch_service.prepare_batch_approval(
        movements, UserRole.STAFF, 12345, 678, "Test User"
    )
    
    # Verify results
    assert success is True
    assert batch_id is not None
    assert batch_id.startswith("batch_")
    assert len(batch_service.pending_approvals) == 1
    assert batch_id in batch_service.pending_approvals
    
    # Verify before levels are correctly captured
    assert batch_approval.before_levels["cement"] == 100.0
    assert batch_approval.before_levels["steel"] == 50.0
    
    # Test unique batch IDs
    success2, batch_id2, _ = await batch_service.prepare_batch_approval(
        movements, UserRole.STAFF, 12345, 678, "Test User"
    )
    assert batch_id != batch_id2  # Should be unique
```

### Phase 3: Approval Service Enhancement

**Objective**: Extend the approval service to handle batch approvals

1. Implement batch approval method:
   - Validate admin permissions
   - Process movements only after approval
   - Track before/after stock levels
   - Handle and track failures

2. Implement batch rejection method:
   - Allow admins to reject batches
   - Clean up pending approvals

**Files to modify**:
- `src/services/approvals.py`

**Testing for Phase 3**:
1. **Unit Tests**:
   - Test admin-only access control works correctly
   - Test approval processing works for valid batches
   - Test rejection processing works correctly
   - Test error handling for missing or invalid batch IDs
   - Verify after-levels are correctly captured

2. **Integration Tests**:
   - Test end-to-end approval flow with mock Airtable
   - Test approval of real batch movements affects stock levels

3. **Test Code**:
```python
@pytest.mark.asyncio
async def test_approve_batch():
    # Setup mock services
    mock_airtable = MockAirtableClient()
    mock_airtable.add_item("cement", 100.0)
    
    batch_service = BatchStockService(mock_airtable, settings, mock_stock_service)
    approval_service = ApprovalService(mock_airtable, batch_service)
    
    # Create and store a test batch
    movements = [StockMovement(item_name="cement", quantity=10, ...)]
    success, batch_id, batch_approval = await batch_service.prepare_batch_approval(
        movements, UserRole.STAFF, 12345, 678, "Test User"
    )
    
    # Test approve_batch with non-admin
    success, message, _ = await approval_service.approve_batch(
        batch_id, "Non-Admin", UserRole.STAFF
    )
    assert success is False
    assert "administrators" in message.lower()
    
    # Test approve_batch with admin
    success, message, batch_result = await approval_service.approve_batch(
        batch_id, "Admin User", UserRole.ADMIN
    )
    
    assert success is True
    assert batch_result is not None
    assert batch_result.successful_entries == 1
    
    # Verify after levels
    assert batch_approval.after_levels["cement"] == 110.0  # 100 + 10
    
    # Verify batch was removed from pending
    assert batch_id not in batch_service.pending_approvals
    
    # Test invalid batch ID
    success, message, _ = await approval_service.approve_batch(
        "non_existent_batch", "Admin", UserRole.ADMIN
    )
    assert success is False
    assert "not found" in message.lower()
```

### Phase 4: Telegram Service Enhancement

**Objective**: Add UI components for approval workflow

1. Add batch approval request method:
   - Display summary of items and quantities
   - Create approval/reject buttons
   - Format message for readability

2. Add batch success summary method:
   - Show processed items with quantities
   - Display before/after stock levels for each item
   - List any errors for failed items

**Files to modify**:
- `src/telegram_service.py`

**Testing for Phase 4**:
1. **Unit Tests**:
   - Test message formatting is correct
   - Test button generation works properly
   - Test error handling in message sending
   - Verify success summary includes all required elements

2. **Integration Tests**:
   - Test with mock Telegram Bot API
   - Verify HTML formatting works with the Telegram API

3. **Test Code**:
```python
@pytest.mark.asyncio
async def test_send_batch_approval_request():
    # Setup mock telegram bot
    mock_bot = MockTelegramBot()
    telegram_service = TelegramService(settings)
    telegram_service.bot = mock_bot
    
    # Create test data
    batch_id = "test_batch_001"
    movements = [
        StockMovement(item_name="cement", quantity=10, unit="bags", 
                     movement_type=MovementType.IN, ...),
        StockMovement(item_name="steel", quantity=20, unit="pieces", 
                     movement_type=MovementType.OUT, ...)
    ]
    before_levels = {"cement": 100.0, "steel": 50.0}
    
    # Test send_batch_approval_request
    success = await telegram_service.send_batch_approval_request(
        12345, batch_id, movements, before_levels, "Test User"
    )
    
    # Verify results
    assert success is True
    assert len(mock_bot.sent_messages) == 1
    
    # Check message content
    message = mock_bot.sent_messages[0]
    assert message["chat_id"] == 12345
    assert "Approval Required for Batch" in message["text"]
    assert batch_id in message["text"]
    assert "cement: 10 bags" in message["text"]
    assert "steel: 20 pieces" in message["text"]
    
    # Check buttons
    assert "approvebatch" in str(message["reply_markup"])
    assert "rejectbatch" in str(message["reply_markup"])
```

### Phase 5: Command Processing Updates

**Objective**: Update command handlers to use the new approval flow

1. Add callback query handler for button interactions:
   - Handle approve/reject button clicks
   - Process batch accordingly
   - Update UI to show status

2. Modify in/out/adjust command handlers:
   - Use prepare_batch_approval instead of direct processing
   - Send approval requests for both single and batch entries

**Files to modify**:
- `src/main.py`

**Testing for Phase 5**:
1. **Unit Tests**:
   - Test callback query parsing works correctly
   - Test command handlers create approval requests instead of processing directly
   - Verify proper error responses for unauthorized users

2. **Integration Tests**:
   - Test end-to-end flow from command input to approval request
   - Test callback query handling through the bot

3. **Test Code**:
```python
@pytest.mark.asyncio
async def test_process_callback_query():
    # Setup mock services
    bot = ConstructionInventoryBot()
    # Replace services with mocks
    bot.airtable_client = MockAirtableClient()
    bot.bot = MockTelegramBot()
    bot.approval_service = MockApprovalService()
    bot.batch_stock_service = MockBatchStockService()
    
    # Create mock callback query
    callback_query = MockCallbackQuery()
    callback_query.data = "approvebatch:test_batch_001"
    callback_query.from_user.id = 123
    callback_query.from_user.first_name = "Test"
    callback_query.message.chat.id = 456
    
    # Setup auth service to return valid admin
    bot.auth_service = MockAuthService()
    bot.auth_service.set_user_role(123, UserRole.ADMIN)
    
    # Test process_callback_query
    await bot.process_callback_query(callback_query)
    
    # Verify approvals service was called
    assert bot.approval_service.approve_batch_called
    assert bot.approval_service.approve_batch_batch_id == "test_batch_001"
    
    # Test unauthorized user
    bot.auth_service.set_user_role(123, UserRole.VIEWER)
    
    # Reset tracking
    bot.approval_service.approve_batch_called = False
    
    # Test again with unauthorized user
    await bot.process_callback_query(callback_query)
    
    # Verify approval was not called
    assert not bot.approval_service.approve_batch_called
```

### Phase 6: Testing and Refinement

**Objective**: Ensure the system works correctly in all scenarios

1. **Comprehensive Integration Tests**:
   - Test single entry approval flow:
     - Test for all movement types (in/out/adjust)
     - Verify before/after levels are correctly calculated
     - Test approval and rejection

   - Test batch entry approval flow:
     - Test with various batch sizes
     - Test with mixed movement types
     - Verify all items process correctly

   - Test error handling:
     - Test with invalid items
     - Test with insufficient stock
     - Verify errors are properly reported

2. **Real-World Testing Scenarios**:
   - **Scenario 1: Standard Workflow**
     1. User submits `/in cement, 10 bags`
     2. System shows approval request
     3. Admin approves
     4. System shows success with before/after levels

   - **Scenario 2: Batch Workflow**
     1. User submits multiple items with `/in cement, 10 bags\nsand, 5 bags`
     2. System shows approval request with all items listed
     3. Admin approves
     4. System processes all items and shows comprehensive summary

   - **Scenario 3: Rejection Flow**
     1. User submits stock movement
     2. Admin rejects
     3. System discards movement without processing

   - **Scenario 4: Error Handling**
     1. User submits invalid item
     2. Admin approves
     3. System processes valid items and reports error for invalid item

3. **Performance Testing**:
   - Test with large batches (10+ items)
   - Measure response time for approval processing
   - Test concurrent approvals from multiple users

4. **Security Testing**:
   - Verify non-admins cannot approve movements
   - Test permission checks are consistent across all methods
   - Verify that batch IDs cannot be guessed or manipulated

**Test Implementation**:
```python
@pytest.mark.asyncio
async def test_end_to_end_approval_flow():
    """Test the complete flow from command to approval to processing."""
    # Setup the bot
    bot = ConstructionInventoryBot()
    # Replace with mock services for controlled testing
    
    # Mock user sending an in command
    update = MockUpdate()
    update.message.text = "/in cement, 10 bags"
    update.message.from_user.id = 123
    update.message.chat.id = 456
    
    # Process the command
    await bot.process_update(update)
    
    # Verify approval request was sent
    assert len(bot.telegram_service.bot.sent_messages) == 1
    approval_message = bot.telegram_service.bot.sent_messages[0]
    assert "Approval Required" in approval_message["text"]
    
    # Mock admin clicking approve button
    callback_query = MockCallbackQuery()
    # Extract batch_id from the message
    batch_id = extract_batch_id(approval_message["text"])
    callback_query.data = f"approvebatch:{batch_id}"
    callback_query.from_user.id = 789  # Admin user
    callback_query.message = approval_message
    
    # Process the approval
    await bot.process_callback_query(callback_query)
    
    # Verify success summary was sent
    assert len(bot.telegram_service.bot.sent_messages) == 3  # Original + updated + summary
    summary_message = bot.telegram_service.bot.sent_messages[2]
    assert "Batch Processed Successfully" in summary_message["text"]
    assert "cement: 10 bags" in summary_message["text"]
    
    # Verify stock was updated
    item = await bot.airtable_client.get_item("cement")
    # Calculate expected new stock level
    assert item.on_hand == initial_cement_stock + 10
```

## Technical Design

### BatchApproval Model

```python
class BatchApproval(BaseModel):
    """Batch approval request."""
    batch_id: str  # Unique identifier for this batch
    movements: List[StockMovement]  # List of movements in this batch
    user_id: str
    user_name: str
    timestamp: datetime = Field(default_factory=datetime.now)
    chat_id: int
    status: str = "Pending"  # Pending, Approved, Rejected
    before_levels: Dict[str, float] = Field(default_factory=dict)  # Stock levels before batch processing
    after_levels: Dict[str, float] = Field(default_factory=dict)   # Stock levels after batch processing
    failed_entries: List[Dict[str, Any]] = Field(default_factory=list)  # Entries that failed processing
```

### Approval Flow

1. User submits stock movement command (single or batch)
2. System prepares movements but does not process them
3. System shows summary with approval buttons
4. Admin clicks approve or reject
5. If approved, system processes movements
6. System shows detailed success summary with before/after levels
7. If rejected, system discards movements

### Database Changes

For a full implementation, we would need to add:
1. New field in Stock Movements table for batch_id
2. Potentially a new Batch Approvals table for tracking
3. Support for the new status values

However, for the initial implementation, we'll use in-memory storage for pending approvals to avoid complex database changes.

## UI Elements

### Pre-Approval Summary

```
🔔 Approval Required for Batch

Requested by: John Smith
Batch ID: batch_1234567890_123456
Items to process: 3

Items:
1. ➕ Cement: 50 bags
2. ➕ Steel bars: 100 pieces
3. ➕ Safety helmets: 10 pieces

Please approve or reject this batch request.
[Approve] [Reject]
```

### Success Summary

```
✅ Batch Processed Successfully

Batch ID: batch_1234567890_123456
Items processed: 3

Inventory Changes:
• ➕ Cement: 50 bags
  Stock: 100 → 150 (+50)
• ➕ Safety helmets: 10 pieces
  Stock: 5 → 15 (+10)
• ➕ Steel bars: 100 pieces
  Stock: 200 → 300 (+100)
```

## Error Handling and Edge Cases

1. **Timeout Handling**:
   - Implement automatic cleanup for pending approvals older than 24 hours
   - Send notification to user if their approval request expires

2. **Concurrent Approvals**:
   - Handle multiple admins trying to approve the same batch
   - Implement locking mechanism to prevent race conditions

3. **Network Issues**:
   - Save approval state to prevent double-processing on connection issues
   - Use idempotency keys to prevent duplicate processing

4. **Recovery Mechanism**:
   - Add `/pendingapprovals` command to list all pending batches
   - Allow admins to force-approve or force-reject stuck batches

## Monitoring and Logging

1. **Activity Logging**:
   - Log all approval requests with timestamps
   - Log admin actions (approve/reject) with user identification
   - Track approval time (time between request and approval)

2. **Metrics**:
   - Track approval rate (approved vs. rejected)
   - Measure average response time for approvals
   - Count frequency of errors during processing

3. **Health Checks**:
   - Monitor pending approval count
   - Alert if pending approvals exceed threshold
   - Monitor approval processing time

## Future Enhancements

1. Persistent storage for pending approvals
2. Individual item approval/rejection within a batch
3. Time expiry for pending approvals
4. Enhanced validation rules for specific items
5. Integration with notification systems for urgent approvals
6. Approval delegation to temporarily authorized users
7. Customizable approval thresholds based on item value/quantity

## Conclusion

This phased approach allows for incremental implementation and testing of the approval system. The system will provide better data quality control by requiring admin approval for all inventory movements while maintaining detailed tracking of stock changes. The comprehensive testing strategy for each phase ensures reliability and correctness of the implementation.

## Implementation Timeline

| Phase | Description | Estimated Time | Dependencies |
|-------|-------------|----------------|-------------|
| 1 | Schema Updates | 1 day | None |
| 2 | Batch Stock Service Enhancement | 2 days | Phase 1 |
| 3 | Approval Service Enhancement | 2 days | Phase 2 |
| 4 | Telegram Service Enhancement | 2 days | Phase 1 |
| 5 | Command Processing Updates | 3 days | Phases 3, 4 |
| 6 | Testing and Refinement | 3 days | All previous phases |

Total estimated time: 13 days of development work