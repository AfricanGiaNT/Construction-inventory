# Batch Command Enhancement Plan

**Project:** Construction Inventory Bot  
**Feature:** Global Parameters for Batch Commands  
**Status:** ✅ Implemented

## Feature Overview

Enhance the batch command structure to support global parameters that apply to all entries in a batch, reducing repetition for common fields like driver, location, and project.

## Requirements

- Add support for global parameters at the beginning of batch commands
- Support `driver:`, `from:`, `to:`, and `project:` global parameters
- Apply global parameters to all entries unless explicitly overridden
- Maintain backward compatibility with existing batch commands
- Update help and validation systems to include global parameter examples
- Provide clear feedback on how global parameters are applied

## Proposed Syntax

```
/in driver: Mr Longwe, from: chigumula office, project: Bridge Construction
item1, quantity1 unit1
item2, quantity2 unit2
item3, quantity3 unit3
```

Key aspects:
- Global parameters are specified at the beginning of the command
- Parameters use a `key: value` format
- Global parameters apply to all entries unless explicitly overridden
- Backward compatible with existing batch commands

## Implementation Phases

### Phase 1: Enhanced Parser for Global Parameters

#### Objectives
- Modify NLP Parser to detect and extract global parameters
- Implement parameter inheritance logic
- Update data models to support global parameters
- Maintain backward compatibility

#### Technical Changes

1. **Global Parameter Detection**:
   - Add function to extract global parameters from command text
   - Support `driver:`, `from:`, `to:`, and `project:` parameters
   - Handle various formats and spacing

2. **Parameter Inheritance Logic**:
   - Apply global parameters to entries that don't specify these fields
   - Allow individual entries to override global parameters
   - Maintain backward compatibility with existing batch formats

3. **Data Model Updates**:
   - Update `BatchParseResult` to include global parameters
   - Add project field to `StockMovement` model
   - Update schemas for batch processing

#### Test Plan for Phase 1

**Unit Tests**:
- Test parsing of individual global parameters (driver, from, to, project)
- Test parsing multiple global parameters in different orders
- Test parsing with various formatting and spacing
- Test handling of malformed global parameters
- Test extracting remaining text after global parameters
- Test parameter inheritance for entries without specific fields
- Test entry-specific parameters overriding global parameters
- Test backward compatibility with existing batch formats

**Integration Tests**:
- Test integration with existing NLP parser
- Test compatibility with different batch formats (newline, semicolon, mixed)
- Test parameter application to batch entries

### Phase 2: Command Processing with Global Parameters

#### Objectives
- Update batch processing service to handle global parameters
- Ensure proper Airtable integration for new fields
- Implement validation for global parameters
- Maintain rollback functionality

#### Technical Changes

1. **Batch Processing Service Updates**:
   - Modify `process_batch_movements` to handle global parameters
   - Apply global parameters to individual movements
   - Update error handling for invalid global parameters
   - Maintain rollback functionality

2. **Airtable Integration**:
   - Update Airtable client to handle project field
   - Ensure proper mapping between command parameters and Airtable fields
   - Add validation for required fields

3. **Command Router Updates**:
   - Update command routing to handle global parameters
   - Ensure proper parsing and validation

#### Test Plan for Phase 2

**Unit Tests**:
- Test applying global parameters during batch processing
- Test validation of global parameter values
- Test error handling for invalid global parameters
- Test rollback functionality with global parameters

**Integration Tests**:
- Test end-to-end processing with global parameters
- Verify Airtable records have correct values from global parameters
- Test mixed global and entry-specific parameters
- Test error handling and recovery

### Phase 3: User Experience Improvements

#### Objectives
- Update help system to include global parameter examples
- Enhance validation command to show global parameters
- Improve feedback messages for batch commands
- Provide clear indication of parameter application

#### Technical Changes

1. **Help System Updates**:
   - Update `/batchhelp` command to include global parameter examples
   - Add documentation for parameter inheritance rules
   - Include examples for different combinations of global parameters

2. **Validation Command Enhancement**:
   - Update `/validate` command to show global parameters
   - Provide feedback on how global parameters will be applied
   - Show which entries inherit which global parameters

3. **Feedback Improvements**:
   - Show applied global parameters in batch confirmation message
   - Include global parameter usage in result statistics
   - Enhance error messages for global parameter issues

#### Test Plan for Phase 3

**Unit Tests**:
- Test help message generation with global parameter examples
- Test validation command with global parameters
- Test feedback message generation

**Integration Tests**:
- Test help system with various command examples
- Test validation command with different global parameter combinations
- Test user feedback for successful and failed operations
- Test clarity of error messages related to global parameters

## Technical Design

### Global Parameter Parsing Algorithm

```python
def parse_global_parameters(text: str) -> Tuple[Dict[str, str], str]:
    """Extract global parameters from the beginning of a command."""
    global_params = {}
    remaining_text = text
    
    # Look for global parameters at the beginning
    global_pattern = r'^(driver:|from:|to:|project:)\s*([^,]+)(?:,\s*|$)'
    
    # Continue extracting parameters until no more found
    match = re.search(global_pattern, remaining_text)
    while match:
        key = match.group(1).rstrip(':')
        value = match.group(2).strip()
        global_params[key] = value
        
        # Remove the matched parameter from the text
        remaining_text = remaining_text[match.end():].strip()
        if remaining_text.startswith(','):
            remaining_text = remaining_text[1:].strip()
        
        # Look for next parameter
        match = re.search(global_pattern, remaining_text)
    
    return global_params, remaining_text
```

### Parameter Application Logic

```python
def apply_global_parameters(movement: StockMovement, global_params: Dict[str, str]) -> StockMovement:
    """Apply global parameters to a movement if not already specified."""
    # Apply driver if not already set
    if not movement.driver_name and 'driver' in global_params:
        movement.driver_name = global_params['driver']
    
    # Apply from_location if not already set
    if not movement.from_location and 'from' in global_params:
        movement.from_location = global_params['from']
    
    # Apply to_location if not already set
    if not movement.to_location and 'to' in global_params:
        movement.to_location = global_params['to']
    
    # Apply project if not already set
    if not movement.project and 'project' in global_params:
        movement.project = global_params['project']
    
    return movement
```

### Data Model Updates

```python
# Update StockMovement to include project field
class StockMovement(BaseModel):
    """Stock movement record."""
    id: Optional[str] = None
    item_name: str
    movement_type: MovementType
    quantity: float
    unit: str
    signed_base_quantity: float
    location: Optional[str] = None
    note: Optional[str] = None
    status: MovementStatus = MovementStatus.POSTED
    user_id: str
    user_name: str
    timestamp: datetime = Field(default_factory=datetime.now)
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    reason: Optional[str] = None
    source: str = "Telegram"
    driver_name: Optional[str] = None
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    project: Optional[str] = None  # New field for project

# Update BatchParseResult to include global parameters
class BatchParseResult(BaseModel):
    """Result of parsing a batch of stock movements."""
    format: BatchFormat
    movements: List[StockMovement]
    total_entries: int
    valid_entries: int
    errors: List[str] = []
    is_valid: bool = True
    global_parameters: Dict[str, str] = {}  # New field for global parameters
```

## Usage Examples

### Example 1: Driver and Location as Global Parameters

```
/in driver: Mr Longwe, from: chigumula office, project: Bridge Construction
cement, 50 bags
steel bars, 100 pieces
safety equipment, 20 sets
```

### Example 2: Mixed Global and Entry-Specific Parameters

```
/in driver: Mr Longwe, project: Bridge Construction
cement, 50 bags, from supplier
steel bars, 100 pieces, from warehouse
safety equipment, 20 sets, from office
```

### Example 3: Semicolon Format with Global Parameters

```
/in driver: Mr Longwe, from: chigumula, project: Bridge Construction
cement, 50 bags; steel bars, 100 pieces; safety equipment, 20 sets
```

## Risk Assessment

**High Risk**:
- Parser complexity with mixed global and entry-specific parameters
- Backward compatibility with existing batch formats
- Data consistency with partially applied global parameters

**Medium Risk**:
- User confusion about parameter inheritance rules
- Error handling for invalid global parameters
- Performance impact of additional parsing steps

**Mitigation Strategies**:
- Comprehensive testing of all parameter combinations
- Clear documentation and examples in help system
- Detailed validation feedback before processing
- Thorough error handling with specific error messages

## Success Criteria

1. **Functionality**: Global parameters correctly applied to all entries
2. **Usability**: Reduced repetition in batch commands
3. **Compatibility**: Existing batch commands continue to work
4. **Feedback**: Clear indication of how global parameters are applied
5. **Validation**: Proper validation of required fields like project

## Implementation Summary

All planned features have been successfully implemented:

### Phase 1: Enhanced Parser for Global Parameters ✅
- Implemented global parameter detection and extraction
- Added parameter inheritance logic
- Updated data models to support global parameters
- Fixed issues with multi-line command parsing
- Added comprehensive unit tests

### Phase 2: Command Processing with Global Parameters ✅
- Updated batch processing service to handle global parameters
- Integrated with Airtable using the correct field name ("From/To Project")
- Implemented validation for required fields including project
- Maintained rollback functionality for batch operations

### Phase 3: User Experience Improvements ✅
- Redesigned help system to be more concise and visually appealing
- Enhanced validation command to show global parameters
- Improved feedback messages for batch commands
- Added clear examples of global parameter usage
- Fixed HTML parsing issues in Telegram messages

### Challenges Overcome
- Multi-line command parsing with regex
- HTML parsing limitations in Telegram
- Airtable field name mismatch ("Project" vs "From/To Project")
- Parameter inheritance and override logic
- Command parsing indentation errors

## Future Enhancements

1. **Parameter Templates**: Save and reuse common parameter combinations
2. **Default Parameters**: User-configurable default parameters
3. **Advanced Parameter Rules**: Conditional parameter application
4. **Parameter Aliases**: Short forms for common parameters
5. **Batch Macros**: Define reusable batch command templates
6. **Project Autocomplete**: Suggest project names based on recent entries

