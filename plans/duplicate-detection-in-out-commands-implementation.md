# Duplicate Detection for /in and /out Commands - Implementation Plan

**Date:** September 10, 2025  
**Author:** AI Assistant  
**Feature:** Duplicate Detection for Stock Movement Commands  
**Status:** 📋 PLANNING  

## Overview

Extend the existing duplicate detection system to cover `/in` and `/out` commands, preventing duplicate logging of similar items during stock movements. The system will detect potential duplicates after the approval workflow, present consolidated confirmation dialogs, and handle project conflicts and stock level validation.

## Requirements

### User Requirements
- Detect when stock movement items are similar to existing items
- Handle keyword order differences (e.g., "cement 50kgs bags" vs "50kgs bags cement")
- Allow up to 1 missing keyword in similarity matching
- Show confirmation dialog with inline keyboard buttons
- Consolidate quantities when duplicates are confirmed
- Search against all historical items (no time window limits)
- No unit conversion (e.g., "5kg cement" vs "5000g cement" are not duplicates)
- No synonym matching (e.g., "cement" vs "concrete" are not duplicates)

### Technical Requirements
- **Approval Integration:** Duplicate detection happens **AFTER** approval workflow
- **Batch Handling:** Show **ALL duplicates at once** with individual confirm/cancel options
- **OUT Movement Logic:** Check stock levels and show both duplicates AND current stock
- **Project Conflicts:** Treat as duplicates, **append new project** to existing project field
- **Location Handling:** **Only item name** (ignore location)
- **Unit Conversion:** **No unit conversion** for duplicate detection

## Current System Analysis

### Existing /in and /out Flow
```
/in cement, 50 bags
    ↓
Parse Movement (NLP Parser)
    ↓
Single Entry → Batch Approval Workflow
    ↓
Process Movement (Stock Service)
```

```
/in cement, 50 bags
    steel bars, 100 pieces
    ↓
Parse Movements (NLP Parser)
    ↓
Batch Entry → Batch Processing
    ↓
Process Batch (Batch Stock Service)
```

### Key Differences from /inventory
- Uses **NLP parser** instead of inventory parser
- Has **approval workflow** for single entries
- Supports **batch processing** for multiple items
- Different data structures (`StockMovement` vs `InventoryEntry`)

## Implementation Phases

### Phase 1: Extend Duplicate Detection Service 🔧

**Files to Modify:**
- `src/services/duplicate_detection.py` - Add movement-specific methods

**New Methods:**
```python
async def find_potential_duplicates_for_movements(
    self, 
    movements: List[StockMovement]
) -> Dict[str, MovementDuplicateResult]

async def find_potential_duplicates_for_single_movement(
    self, 
    movement: StockMovement
) -> MovementDuplicateResult

async def _check_out_movement_stock(
    self, 
    movement: StockMovement, 
    duplicate: PotentialDuplicate
) -> Tuple[bool, float]  # (has_sufficient_stock, current_stock)

async def _handle_project_conflict(
    self, 
    existing_item: Item, 
    new_movement: StockMovement
) -> str
```

**Key Features:**
- Handle `StockMovement` objects instead of `InventoryEntry`
- Support both single and batch scenarios
- Check stock levels for OUT movements
- Ignore location in similarity calculation
- No unit conversion
- Project conflict resolution

### Phase 2: New Data Structures 📊

**New Data Classes:**
```python
@dataclass
class MovementDuplicateResult:
    movement_id: str
    movement: StockMovement
    potential_duplicates: List[PotentialDuplicate]
    has_duplicates: bool
    stock_check_results: Dict[str, Tuple[bool, float]]  # For OUT movements

@dataclass
class MovementDuplicateDetectionResult:
    movement_results: List[MovementDuplicateResult]
    has_any_duplicates: bool
    total_movements: int
    total_duplicates: int
    requires_stock_check: bool  # True if any OUT movements
```

### Phase 3: Extend Telegram Service 💬

**Files to Modify:**
- `src/telegram_service.py` - Add movement duplicate confirmation methods

**New Methods:**
```python
async def send_movement_duplicate_confirmation(
    self, 
    chat_id: int, 
    movement_duplicates: Dict[str, MovementDuplicateResult], 
    movements: List[StockMovement]
) -> int

def _format_movement_duplicate_message(
    self, 
    movement_duplicates: Dict[str, MovementDuplicateResult], 
    movements: List[StockMovement]
) -> str

def _create_movement_duplicate_keyboard(
    self, 
    movement_duplicates: Dict[str, MovementDuplicateResult]
) -> InlineKeyboardMarkup

async def send_movement_duplicate_result(
    self, 
    chat_id: int, 
    message: str
)
```

**Key Features:**
- Show all duplicates in one dialog
- Individual confirm/cancel buttons for each movement
- Display stock levels for OUT movements
- Show project information and conflicts
- Handle mixed scenarios (some duplicates, some not)

### Phase 4: Extend Main Bot Handlers 🤖

**Files to Modify:**
- `src/main.py` - Add movement duplicate callback handlers

**New Callback Handlers:**
```python
async def _process_movement_duplicate_confirmation(self, callback_query, user_name: str)
async def _process_movement_duplicate_cancellation(self, callback_query, user_name: str)
async def _show_all_movement_duplicate_matches(self, callback_query, user_name: str)
```

**Integration Points:**
- **Single Entry Flow:** After batch approval, before movement processing
- **Batch Entry Flow:** After batch approval, before batch processing
- **Callback Routing:** Add new callback types

### Phase 5: Extend Batch Stock Service 📦

**Files to Modify:**
- `src/services/batch_stock.py` - Add movement duplicate processing

**New Methods:**
```python
async def process_movement_duplicate_confirmation(
    self, 
    chat_id: int, 
    action: str, 
    movement_id: str = None
) -> Tuple[bool, str]

async def _consolidate_movement_duplicates(
    self, 
    movement: StockMovement, 
    duplicates: List[PotentialDuplicate]
) -> Dict

async def _handle_project_conflict_update(
    self, 
    existing_item: Item, 
    new_movement: StockMovement
) -> str
```

## Updated Implementation Flow

### Single Entry Flow
```
/in cement, 50 bags
    ↓
Parse Movement (NLP Parser)
    ↓
Go Through Approval Workflow ← EXISTING
    ↓
Check for Duplicates ← NEW (after approval)
    ↓
Show Confirmation Dialog ← NEW
    ↓
User Confirms/Cancels ← NEW
    ↓
Process Movement (existing flow)
```

### Batch Entry Flow
```
/in cement, 50 bags
    steel bars, 100 pieces
    ↓
Parse Movements (NLP Parser)
    ↓
Go Through Batch Approval Workflow ← EXISTING
    ↓
Check Each Movement for Duplicates ← NEW (after approval)
    ↓
Show Consolidated Dialog with Individual Options ← NEW
    ↓
User Confirms/Cancels Individual Items ← NEW
    ↓
Process Batch (existing flow)
```

## User Experience Design

### Single Movement Dialog
```
⚠️ Potential Duplicate Detected!

Stock IN: cement, 50 bags
Similar to:
• cement 50kg bags, 25.0 pieces (95% match) - Added by John
  Project: Site A
  Current Stock: 25.0 pieces

Action Required: Choose how to proceed.
Note: Confirming will add quantities together.

[Confirm] [Cancel] [Show All Matches]
```

### Batch Movement Dialog
```
⚠️ Potential Duplicates Detected!

Found similar items in your batch:

Stock IN: cement, 50 bags
• cement 50kg bags, 25.0 pieces (95% match) - Added by John
  Project: Site A
  Current Stock: 25.0 pieces
  [Confirm] [Cancel]

Stock OUT: steel bars, 100 pieces
• steel bar 100mm, 50.0 pieces (88% match) - Added by Mary
  Project: Site B
  Current Stock: 50.0 pieces
  ⚠️ Insufficient stock! (Need: 100, Have: 50)
  [Confirm] [Cancel]

Stock IN: safety equipment, 20 sets
• No duplicates found
  [Continue]

[Confirm All] [Cancel All] [Review Individual]
```

## Project Conflict Handling

### Project Field Updates
```python
async def _handle_project_conflict(
    self, 
    existing_item: Item, 
    new_movement: StockMovement
) -> str:
    """Handle project conflicts by appending new project."""
    existing_projects = existing_item.project or ""
    new_project = new_movement.project or ""
    
    if not existing_projects:
        return new_project
    elif new_project not in existing_projects:
        return f"{existing_projects}, {new_project}"
    else:
        return existing_projects
```

### Example Project Updates
- **Existing:** "Site A"
- **New:** "Site B"
- **Result:** "Site A, Site B"

- **Existing:** "Site A, Site B"
- **New:** "Site C"
- **Result:** "Site A, Site B, Site C"

## Stock Level Integration

### OUT Movement Stock Checks
```python
async def _check_out_movement_stock(
    self, 
    movement: StockMovement, 
    duplicate: PotentialDuplicate
) -> Tuple[bool, float]:
    """Check if there's enough stock for OUT movement."""
    current_stock = duplicate.quantity
    required_quantity = movement.quantity
    
    has_sufficient = current_stock >= required_quantity
    return has_sufficient, current_stock
```

### Stock Level Display
- ✅ **Sufficient stock:** "Current Stock: 50.0 pieces"
- ⚠️ **Insufficient stock:** "Current Stock: 25.0 pieces (Need: 50)"
- ❌ **No stock:** "Current Stock: 0.0 pieces (Need: 50)"

## Callback Handling

### New Callback Types
```python
# Individual movement callbacks
"confirm_movement_duplicate_{movement_id}"
"cancel_movement_duplicate_{movement_id}"

# Batch callbacks
"confirm_all_movement_duplicates"
"cancel_all_movement_duplicates"
"show_all_movement_duplicate_matches"
```

### Callback Processing
```python
async def process_movement_duplicate_confirmation(
    self, 
    chat_id: int, 
    action: str, 
    movement_id: str = None
) -> Tuple[bool, str]:
    """Process individual movement duplicate confirmation."""
    
    if action.startswith("confirm_movement_duplicate_"):
        # Process single movement confirmation
        movement_id = action.split("_")[-1]
        return await self._process_single_movement_confirmation(chat_id, movement_id)
    
    elif action == "confirm_all_movement_duplicates":
        # Process all movements confirmation
        return await self._process_all_movements_confirmation(chat_id)
    
    elif action == "cancel_all_movement_duplicates":
        # Cancel all movements
        return await self._process_all_movements_cancellation(chat_id)
```

## Error Handling & Edge Cases

### Special Scenarios
1. **Mixed Duplicates:** Some movements have duplicates, others don't
2. **Stock Insufficient:** OUT movement with insufficient stock
3. **Project Conflicts:** Multiple projects for same item
4. **Partial Confirmation:** User confirms some, cancels others
5. **Timeout Handling:** User doesn't respond to dialog

### Error Handling
```python
# Handle insufficient stock for OUT movements
if movement.movement_type == MovementType.OUT and not has_sufficient_stock:
    # Show warning but allow confirmation
    warning_message = f"⚠️ Insufficient stock! (Need: {required}, Have: {current})"
    # Still allow confirmation but log the warning
```

## Testing Strategy

### Test Categories
1. **Unit Tests** - Duplicate detection algorithms
2. **Integration Tests** - Service interactions
3. **End-to-End Tests** - Complete user workflows
4. **Edge Case Tests** - Error scenarios
5. **Performance Tests** - Large batch processing

### Test Scenarios
- Single IN movement with exact duplicate
- Single OUT movement with sufficient stock
- Single OUT movement with insufficient stock
- Batch with mixed duplicates
- Batch with no duplicates
- Project conflict scenarios
- Partial confirmation scenarios
- User cancellation scenarios
- Network timeout scenarios

### Test Files
- `tests/test_movement_duplicate_detection.py` - Core algorithm tests
- `tests/test_movement_duplicate_telegram_integration.py` - Telegram interface tests
- `tests/test_movement_duplicate_callback_handlers.py` - Callback handler tests
- `tests/test_movement_duplicate_batch_integration.py` - Batch processing tests
- `tests/test_complete_movement_duplicate_workflow.py` - End-to-end tests

## Performance Considerations

### Optimizations
- **Batch Stock Checks** - Check all OUT movements in one query
- **Caching** - Cache item data across movements
- **Async Processing** - Parallel duplicate detection
- **Memory Management** - Clean up pending data

### Expected Performance
- **Single movement:** <3 seconds (including approval)
- **Batch (10 items):** <8 seconds (including approval)
- **Batch (50 items):** <20 seconds (including approval)

## Implementation Priority

### Phase 1 (High Priority)
1. Extend DuplicateDetectionService for movements
2. Add stock level checking for OUT movements
3. Basic single movement duplicate detection
4. Project conflict handling

### Phase 2 (Medium Priority)
5. Batch movement duplicate detection
6. Enhanced confirmation dialogs
7. Individual movement confirmation/cancellation
8. Error handling and edge cases

### Phase 3 (Low Priority)
9. Performance optimizations
10. Advanced analytics and reporting
11. User preference settings
12. Bulk operations

## Dependencies

### Existing Systems
- **DuplicateDetectionService** - Core similarity algorithms
- **TelegramService** - User interface components
- **BatchStockService** - Movement processing
- **AirtableClient** - Data persistence
- **AuditTrailService** - Change tracking

### New Dependencies
- **MovementDuplicateResult** - Data structures
- **Stock level validation** - OUT movement checks
- **Project conflict resolution** - Field updates

## Success Metrics

### Functional Requirements
- ✅ 100% duplicate detection accuracy for exact matches
- ✅ 95% accuracy for near-matches (keyword order differences)
- ✅ Stock level validation for OUT movements
- ✅ Project conflict resolution
- ✅ Individual movement confirmation/cancellation

### Performance Requirements
- ✅ Single movement: <3 seconds end-to-end
- ✅ Batch (10 items): <8 seconds end-to-end
- ✅ Batch (50 items): <20 seconds end-to-end
- ✅ 99.9% uptime during duplicate detection

### User Experience Requirements
- ✅ Clear confirmation dialogs
- ✅ Individual movement control
- ✅ Stock level warnings
- ✅ Project conflict information
- ✅ Intuitive keyboard navigation

## Risk Assessment

### High Risk
- **Approval Integration Complexity** - Ensuring duplicate detection works after approval
- **Batch Processing Performance** - Large batches may be slow
- **Project Conflict Resolution** - Complex field updates

### Medium Risk
- **Stock Level Validation** - OUT movement stock checks
- **User Experience Complexity** - Multiple confirmation options
- **Error Handling** - Edge cases and timeouts

### Low Risk
- **Similarity Algorithm** - Already proven with /inventory
- **Telegram Integration** - Similar to existing patterns
- **Data Persistence** - Standard Airtable operations

## Conclusion

This comprehensive plan provides a detailed roadmap for implementing duplicate detection in the `/in` and `/out` commands while maintaining the existing approval workflow and adding the specific features requested. The implementation can be done incrementally, starting with single movements and expanding to batch processing.

The key success factors are:
1. **Proper Integration** - Seamless integration with existing approval workflow
2. **User Experience** - Clear and intuitive confirmation dialogs
3. **Performance** - Fast duplicate detection and processing
4. **Reliability** - Robust error handling and edge case management
5. **Maintainability** - Clean code structure and comprehensive testing

This implementation will significantly improve the accuracy of stock movements by preventing duplicate entries while maintaining the existing user workflow and approval processes.
