# Batch Movement Commands Overhaul Implementation Plan

**Project:** Construction Inventory Bot  
**Feature:** Repurpose /in and /out Commands for Batch Processing  
**Status:** 🚧 Planning Phase

## Feature Overview

Completely overhaul the `/in` and `/out` commands to use a new batch-based approach that eliminates the need for complex parameter memorization and enables efficient processing of multiple batches with different locations, drivers, and projects in a single command.

## Current Pain Points

1. **Complex Parameter Syntax**: Current commands require remembering multiple parameters in specific order
2. **Single Batch Limitation**: Cannot process multiple batches with different locations/drivers in one command
3. **Workflow Inefficiency**: Must complete one batch before starting another
4. **Mixed Duplicate Handling**: No intelligent handling of mixed duplicate/non-duplicate items in batches

## Requirements

### Core Requirements
- Repurpose `/in` and `/out` commands to use batch-only processing
- Support multiple batches per command with simple separators (`-batch 1-`, `-batch 2-`)
- Essential parameters only: item name, item quantity
- Smart defaults: "not described" for missing project/driver, "external" for missing destination
- Process non-duplicates first, then handle duplicates separately
- Skip failed batches and continue with others
- Show batch summary before processing
- Show duplicate preview before processing duplicates

### User Experience Requirements
- Simple, memorable command syntax
- Clear batch separators
- Comprehensive error handling
- Progress feedback and final summaries
- Backward compatibility during transition

## Proposed Syntax

### New /in Command Format
```
/in
-batch 1-
project: mzuzu, driver: Dani maliko
Solar floodlight panel FS-SFL800, 4
Solar floodlight 800W, 4

-batch 2-
project: lilongwe, driver: John Banda
Cable 2.5sqmm black 100m, 1
Cable 2.5sqmm green 100m, 1
```

### New /out Command Format
```
/out
-batch 1-
project: mzuzu, driver: Dani maliko, to: mzuzu houses
Solar floodlight panel FS-SFL800, 4
Solar floodlight 800W, 4

-batch 2-
project: lilongwe, driver: John Banda, to: lilongwe site
Cable 2.5sqmm black 100m, 1
```

## Implementation Phases

### Phase 1: Core Batch Parser & Structure
**Duration:** 2-3 days  
**Goal:** Build the foundation for parsing batch commands

#### Objectives
- Create batch parser service for new command format
- Implement batch data models and validation
- Handle smart defaults and parameter reduction
- Build comprehensive test suite

#### Technical Changes

1. **Batch Parser Service** (`src/services/batch_movement_parser.py`):
   ```python
   class BatchMovementParser:
       def parse_batch_command(self, command_text: str) -> BatchParseResult
       def extract_batches(self, text: str) -> List[BatchInfo]
       def parse_batch_metadata(self, batch_header: str) -> BatchMetadata
       def parse_batch_items(self, items_text: str) -> List[BatchItem]
       def apply_smart_defaults(self, batch: BatchInfo) -> BatchInfo
   ```

2. **Batch Data Models** (update `src/schemas.py`):
   ```python
   class BatchInfo(BaseModel):
       batch_number: int
       project: Optional[str] = "not described"
       driver: Optional[str] = "not described"
       to_location: Optional[str] = "external"  # For /out only
       items: List[BatchItem]
   
   class BatchItem(BaseModel):
       item_name: str
       quantity: float
       unit: Optional[str] = None
   
   class BatchParseResult(BaseModel):
       batches: List[BatchInfo]
       total_items: int
       is_valid: bool
       errors: List[str] = []
   ```

3. **Smart Defaults Logic**:
   - Project: "not described" if not specified
   - Driver: "not described" if not specified
   - To location: "external" if not specified (for /out)
   - From location: "not described" if not specified (for /in)

#### Test Plan for Phase 1

**Unit Tests** (`test_batch_parser_basic.py`):
- Parse single batch with all parameters
- Parse single batch with missing parameters (test defaults)
- Parse multiple batches with different parameters
- Parse malformed batch separators
- Parse empty batches
- Parse batches with no items

**Edge Case Tests** (`test_batch_parser_edge_cases.py`):
- Extra whitespace and formatting variations
- Special characters in item names
- Very long batch commands
- Mixed valid/invalid batches
- Malformed parameter syntax

**Default Behavior Tests** (`test_batch_parser_defaults.py`):
- Verify "not described" defaults for project/driver
- Verify "external" default for to_location
- Test parameter override behavior
- Test mixed default/specified parameters

### Phase 2: Batch Movement Processing
**Duration:** 2-3 days  
**Goal:** Process multiple batches with error handling

#### Objectives
- Create batch processing service
- Implement error handling and recovery
- Generate batch summaries and progress feedback
- Integrate with existing movement services

#### Technical Changes

1. **Batch Movement Service** (`src/services/batch_movement.py`):
   ```python
   class BatchMovementProcessor:
       def process_batch_command(self, parse_result: BatchParseResult, movement_type: MovementType) -> BatchProcessResult
       def process_batch(self, batch: BatchInfo, movement_type: MovementType) -> BatchProcessResult
       def generate_batch_summary(self, batches: List[BatchInfo]) -> str
       def handle_batch_error(self, batch: BatchInfo, error: Exception) -> BatchErrorResult
   ```

2. **Enhanced Movement Services**:
   - Update existing `/in` and `/out` handlers to use batch processing
   - Remove single-item processing logic
   - Add batch validation and error handling
   - Integrate with Airtable client

3. **Error Handling Strategy**:
   - Skip failed batches and continue with others
   - Log detailed error information
   - Provide clear error messages to user
   - Maintain transaction integrity per batch

#### Test Plan for Phase 2

**Processing Tests** (`test_batch_movement_processing.py`):
- Process single batch successfully
- Process multiple batches successfully
- Handle batch processing errors
- Verify Airtable integration
- Test rollback functionality

**Error Handling Tests** (`test_batch_movement_errors.py`):
- Invalid project names
- Invalid driver names
- Database connection errors
- Partial batch failures
- Complete command failures

**Summary Generation Tests** (`test_batch_movement_summaries.py`):
- Generate accurate batch summaries
- Handle different batch configurations
- Format summaries for Telegram display
- Include error information in summaries

### Phase 3: Duplicate Detection Integration
**Duration:** 2-3 days  
**Goal:** Handle mixed duplicates in batch processing

#### Objectives
- Integrate duplicate detection with batch processing
- Process non-duplicates first, then handle duplicates
- Implement duplicate confirmation workflow
- Merge quantities for exact matches

#### Technical Changes

1. **Batch Duplicate Handler** (`src/services/batch_duplicate_handler.py`):
   ```python
   class BatchDuplicateHandler:
       def identify_duplicates(self, batches: List[BatchInfo]) -> DuplicateAnalysis
       def process_non_duplicates(self, batches: List[BatchInfo]) -> ProcessingResult
       def process_duplicates(self, duplicates: List[DuplicateItem]) -> ProcessingResult
       def merge_quantities(self, existing_item: Item, new_item: BatchItem) -> Item
   ```

2. **Duplicate Analysis Models**:
   ```python
   class DuplicateAnalysis(BaseModel):
       non_duplicates: List[BatchItem]
       duplicates: List[DuplicateItem]
       exact_matches: List[DuplicateItem]
       similar_items: List[DuplicateItem]
   
   class DuplicateItem(BaseModel):
       batch_item: BatchItem
       existing_item: Item
       similarity_score: float
       match_type: DuplicateMatchType
   ```

3. **Enhanced Batch Processing**:
   - Separate non-duplicates from duplicates
   - Process non-duplicates first
   - Show duplicate preview to user
   - Handle duplicate confirmations
   - Merge quantities for exact matches

#### Test Plan for Phase 3

**Duplicate Detection Tests** (`test_batch_duplicate_detection.py`):
- Identify exact duplicates
- Identify similar items
- Handle mixed duplicate/non-duplicate batches
- Test similarity scoring accuracy

**Processing Workflow Tests** (`test_batch_duplicate_processing.py`):
- Process non-duplicates first
- Handle duplicate confirmations
- Merge quantities correctly
- Handle user rejections

**Integration Tests** (`test_batch_duplicate_integration.py`):
- End-to-end duplicate handling
- Telegram interaction for confirmations
- Database updates for merged items
- Error handling in duplicate processing

### Phase 4: Telegram Integration & User Experience
**Duration:** 2-3 days  
**Goal:** Complete the user-facing implementation

#### Objectives
- Update Telegram command handlers
- Implement user interaction flows
- Add comprehensive help and guidance
- Ensure smooth user experience

#### Technical Changes

1. **Telegram Command Handlers** (update `src/telegram_service.py`):
   ```python
   async def handle_in_command(self, message: Message) -> None:
       # Parse batch command
       # Show batch summary
       # Process batches
       # Handle duplicates
       # Show final summary
   
   async def handle_out_command(self, message: Message) -> None:
       # Similar to /in but for outgoing movements
   ```

2. **User Experience Enhancements**:
   - Clear batch summary before processing
   - Progress indicators during processing
   - Duplicate confirmation dialogs
   - Final processing summaries
   - Comprehensive error messages

3. **Help System Updates**:
   - Update `/help` command to show new batch format
   - Add examples for common use cases
   - Provide troubleshooting guidance
   - Update command documentation

#### Test Plan for Phase 4

**Telegram Integration Tests** (`test_telegram_batch_commands.py`):
- End-to-end Telegram command processing
- User interaction flows
- Message formatting and display
- Error message handling

**User Experience Tests** (`test_batch_user_experience.py`):
- Batch summary display
- Duplicate confirmation workflow
- Progress feedback
- Final summary generation

**Help System Tests** (`test_batch_help_commands.py`):
- Help message generation
- Example command formatting
- Troubleshooting guidance
- Command discovery

### Phase 5: Migration & Cleanup
**Duration:** 1-2 days  
**Goal:** Remove old single-item processing and finalize

#### Objectives
- Remove legacy single-item movement code
- Update help commands and documentation
- Create migration guide
- Finalize implementation

#### Technical Changes

1. **Code Cleanup**:
   - Remove single-item movement processing
   - Clean up unused functions and imports
   - Update command routing
   - Remove legacy test files

2. **Documentation Updates**:
   - Update command documentation
   - Create migration guide for users
   - Update dev journal with implementation details
   - Document new command syntax

3. **Final Validation**:
   - Comprehensive system testing
   - Performance validation
   - User acceptance testing
   - Documentation review

#### Test Plan for Phase 5

**Migration Tests** (`test_migration_completeness.py`):
- Verify old code is removed
- Ensure no broken references
- Validate new command structure
- Test backward compatibility

**Final Integration Tests** (`test_final_integration.py`):
- Complete system validation
- End-to-end workflow testing
- Performance testing
- User acceptance testing

## Technical Design

### Batch Parser Algorithm

```python
def parse_batch_command(command_text: str) -> BatchParseResult:
    """Parse a batch command into structured data."""
    batches = []
    errors = []
    
    # Split by batch separators
    batch_sections = re.split(r'-batch\s+(\d+)-', command_text)
    
    for i in range(1, len(batch_sections), 2):
        batch_num = int(batch_sections[i])
        batch_content = batch_sections[i + 1].strip()
        
        try:
            batch = parse_single_batch(batch_content, batch_num)
            batches.append(batch)
        except Exception as e:
            errors.append(f"Batch {batch_num}: {str(e)}")
    
    return BatchParseResult(
        batches=batches,
        total_items=sum(len(batch.items) for batch in batches),
        is_valid=len(errors) == 0,
        errors=errors
    )
```

### Smart Defaults Implementation

```python
def apply_smart_defaults(batch: BatchInfo, movement_type: MovementType) -> BatchInfo:
    """Apply smart defaults to batch metadata."""
    if not batch.project:
        batch.project = "not described"
    
    if not batch.driver:
        batch.driver = "not described"
    
    if movement_type == MovementType.OUT and not batch.to_location:
        batch.to_location = "external"
    
    return batch
```

### Duplicate Processing Workflow

```python
def process_batch_with_duplicates(batches: List[BatchInfo]) -> ProcessingResult:
    """Process batches with intelligent duplicate handling."""
    # Step 1: Identify duplicates
    duplicate_analysis = identify_duplicates(batches)
    
    # Step 2: Process non-duplicates first
    non_duplicate_result = process_non_duplicates(duplicate_analysis.non_duplicates)
    
    # Step 3: Show duplicate preview
    show_duplicate_preview(duplicate_analysis.duplicates)
    
    # Step 4: Process duplicates with user confirmation
    duplicate_result = process_duplicates_with_confirmation(duplicate_analysis.duplicates)
    
    return combine_results(non_duplicate_result, duplicate_result)
```

## Usage Examples

### Example 1: Simple Single Batch
```
/in
-batch 1-
project: mzuzu, driver: Dani maliko
Solar floodlight panel FS-SFL800, 4
Solar floodlight 800W, 4
```

### Example 2: Multiple Batches with Different Locations
```
/out
-batch 1-
project: mzuzu, driver: Dani maliko, to: mzuzu houses
Solar floodlight panel FS-SFL800, 4
Solar floodlight 800W, 4

-batch 2-
project: lilongwe, driver: John Banda, to: lilongwe site
Cable 2.5sqmm black 100m, 1
Cable 2.5sqmm green 100m, 1
```

### Example 3: Mixed Duplicates and New Items
```
/in
-batch 1-
project: mzuzu, driver: Dani maliko
Solar floodlight panel FS-SFL800, 4  # New item
Cable 2.5sqmm black 100m, 1         # Duplicate
Solar floodlight 800W, 4             # New item
```

## Risk Assessment

**High Risk**:
- Complete command syntax change may confuse existing users
- Complex duplicate handling logic
- Error handling across multiple batches
- Performance impact of batch processing

**Medium Risk**:
- Telegram message length limits with large batches
- User experience during transition period
- Database transaction management across batches
- Duplicate detection accuracy

**Mitigation Strategies**:
- Comprehensive testing of all scenarios
- Clear migration documentation
- Gradual rollout with user feedback
- Robust error handling and recovery
- Performance optimization for large batches

## Success Criteria

1. **Functionality**: All batch processing features work correctly
2. **Usability**: Commands are significantly easier to use and remember
3. **Efficiency**: Users can process multiple batches in single commands
4. **Reliability**: Robust error handling and recovery
5. **User Experience**: Clear feedback and intuitive workflow

## Implementation Timeline

- **Phase 1:** 2-3 days (Parser foundation)
- **Phase 2:** 2-3 days (Core processing)
- **Phase 3:** 2-3 days (Duplicate handling)
- **Phase 4:** 2-3 days (Telegram integration)
- **Phase 5:** 1-2 days (Cleanup & docs)

**Total:** ~10-14 days

## Future Enhancements

1. **Batch Templates**: Save and reuse common batch configurations
2. **Smart Suggestions**: Suggest project/driver names based on history
3. **Batch Validation**: Pre-validate batches before processing
4. **Advanced Duplicate Handling**: More sophisticated duplicate detection
5. **Batch Analytics**: Track and analyze batch processing patterns
6. **Mobile Optimization**: Optimize for mobile device usage

## Dependencies

- Existing duplicate detection system
- Current movement processing services
- Airtable integration
- Telegram bot framework
- NLP parser for item recognition

## Notes

- This implementation completely replaces the current single-item movement system
- All existing functionality will be preserved but through the new batch interface
- Users will need to adapt to the new command syntax
- Comprehensive testing is critical due to the scope of changes
- Documentation and user training will be essential for successful adoption
