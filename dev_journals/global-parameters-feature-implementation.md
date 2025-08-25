# Global Parameters Feature Implementation

## What I Built

I implemented a global parameters feature for batch commands in my construction inventory Telegram bot, allowing common values like driver, location, and project to be specified once and applied to all entries in a batch command.

## The Problem

My existing batch command system required repetitive entry of the same information (driver, location, project) for each item in a batch. For example, when logging multiple items from the same location with the same driver, I had to repeat this information for every entry:

```
/in cement, 50 bags, by Mr Longwe, from chigumula office, for Bridge project
steel bars, 100 pieces, by Mr Longwe, from chigumula office, for Bridge project
safety equipment, 20 sets, by Mr Longwe, from chigumula office, for Bridge project
```

This was tedious, error-prone, and made batch commands unnecessarily verbose.

## My Solution

I enhanced the batch command parser to support global parameters at the beginning of commands, which are then applied to all entries in the batch unless explicitly overridden:

```
/in driver: Mr Longwe, from: chigumula office, project: Machinga
cement, 50 bags
steel bars, 100 pieces
safety equipment, 20 sets
```

This solution significantly reduces repetition, improves readability, and decreases the chance of input errors.

## How It Works: The Technical Details

### Architecture

The implementation follows a three-phase approach:

1. **Enhanced Parser**: Detects and extracts global parameters from command text
2. **Command Processing**: Applies global parameters to individual movements
3. **User Experience**: Provides clear feedback and help on global parameter usage

### Data Flow

1. User sends a batch command with global parameters
2. Command router extracts the full text and passes it to the NLP parser
3. NLP parser identifies global parameters and remaining batch entries
4. Global parameters are applied to each entry that doesn't override them
5. Batch is validated and processed normally
6. Results show which global parameters were applied

### Technologies Used

- **Python 3.12**: Core programming language
- **python-telegram-bot**: Telegram Bot API integration
- **pyairtable**: Airtable API client for database operations
- **Pydantic**: Data validation and configuration management
- **regex**: For flexible input parsing and global parameter extraction

### Data Models

I extended the existing data models to support global parameters:

```python
# Added to StockMovement
project: Optional[str] = None  # New field for project

# Added to BatchParseResult
global_parameters: Dict[str, str] = Field(default_factory=dict)
```

### Global Parameter Parsing

The core of the implementation is the `parse_global_parameters` method that extracts global parameters from the beginning of a command:

```python
def parse_global_parameters(self, text: str) -> Tuple[Dict[str, str], str]:
    """Extract global parameters from the beginning of a command."""
    global_params = {}
    remaining_text = text.strip()
    
    # Check if there are newlines in the text
    first_line = remaining_text.split('\n')[0] if '\n' in remaining_text else remaining_text
    
    # Define global parameter patterns
    global_patterns = {
        'driver': r'driver:\s*([^,\n]+)(?:,\s*|$|\n)',
        'from': r'from:\s*([^,\n]+)(?:,\s*|$|\n)',
        'to': r'to:\s*([^,\n]+)(?:,\s*|$|\n)',
        'project': r'project:\s*([^,\n]+)(?:,\s*|$|\n)'
    }
    
    # Extract command prefix if present
    command_prefix = ""
    command_match = re.match(r'^(/in|/out|/adjust|in|out|adjust)\s+', first_line)
    if command_match:
        command_prefix = command_match.group(0)
        first_line = first_line[len(command_prefix):].strip()
    
    # Look for global parameters at the beginning of the first line
    original_first_line = first_line
    for param_name, pattern in global_patterns.items():
        match = re.search(pattern, first_line, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            global_params[param_name] = value
            
            # Remove the matched parameter from the text
            start, end = match.span()
            first_line = first_line[:start] + first_line[end:]
            
            # Clean up any leftover commas or whitespace
            first_line = re.sub(r'^,\s*', '', first_line)
            first_line = first_line.strip()
    
    # Reconstruct the remaining text
    if not global_params:
        remaining_text = text.strip()  # Restore original text if no global params found
    else:
        if '\n' in remaining_text:
            remaining_lines = remaining_text.split('\n')[1:]
            if first_line:
                remaining_text = command_prefix + first_line + '\n' + '\n'.join(remaining_lines)
            else:
                remaining_text = command_prefix + '\n'.join(remaining_lines)
        else:
            remaining_text = command_prefix + first_line
    
    return global_params, remaining_text
```

### Parameter Application

Global parameters are applied to each entry that doesn't explicitly override them:

```python
def apply_global_parameters(self, movements: List[StockMovement], global_params: Dict[str, str]) -> List[StockMovement]:
    """Apply global parameters to movements if not already set."""
    if not global_params:
        return movements
    
    for movement in movements:
        if 'driver' in global_params and not movement.driver_name:
            movement.driver_name = global_params['driver']
        if 'from' in global_params and not movement.from_location:
            movement.from_location = global_params['from']
        if 'to' in global_params and not movement.to_location:
            movement.to_location = global_params['to']
        if 'project' in global_params and not movement.project:
            movement.project = global_params['project']
    
    return movements
```

### Validation

I enhanced the validation to ensure all required fields are present, including the new project field:

```python
# Check for project field (required)
if not movement.project:
    errors.append(
        f"Entry #{i+1}: Missing project name. Please specify a project using 'project:' parameter "
        f"at the beginning of your command."
    )
```

### Help System

I completely redesigned the help system to make it more concise and visually appealing, with a focus on the new global parameters feature:

```python
# Global parameters - most important feature
text += "🔑 <b>GLOBAL PARAMETERS</b> (recommended)\n"
text += "Add at the beginning of your command:\n"
text += "<code>driver: name, from: location, to: location, project: name</code>\n\n"
text += "<i>Example:</i>\n"
text += "/in <b>project: Bridge, driver: Mr Longwe</b>\n"
text += "cement, 50 bags\n"
text += "steel bars, 100 pieces\n\n"
```

## The Impact / Result

This feature has significantly improved my workflow:

1. **Reduced Input Time**: Batch commands are now ~60% shorter for multi-item entries
2. **Fewer Errors**: Less repetition means fewer chances for typos and inconsistencies
3. **Better Readability**: Commands are more concise and easier to understand
4. **Required Project Tracking**: Every movement now includes project information
5. **Improved UX**: Help messages are more concise and focused on key features

## Key Lessons Learned

1. **Regex Complexity**: Parsing natural language with regex requires careful consideration of edge cases. The initial implementation had issues with newlines and command prefixes.

2. **Parameter Inheritance**: Designing a system that allows both global parameters and entry-specific overrides requires clear rules about which values take precedence.

3. **HTML Parsing Issues**: Telegram's HTML parsing is strict and can fail with certain tag combinations. Adding a fallback to plain text mode improved reliability.

4. **Field Name Matching**: The Airtable field name ("From/To Project") differed from our internal field name ("Project"), causing initial errors. Always verify external system field names before implementation.

5. **Help Message Design**: Concise, visually structured help messages with code examples are more effective than lengthy explanations. Using HTML formatting and emojis improves readability.

6. **Multi-line Command Parsing**: Regular expressions that work with single-line input might fail with multi-line input. Using `[\s\S]+` instead of `.+` ensures newlines are captured correctly.

## Future Improvements

1. **Parameter Templates**: Save and reuse common parameter combinations
2. **Default Parameters**: User-configurable default parameters
3. **Parameter Aliases**: Short forms for common parameters (e.g., "d:" for "driver:")
4. **Batch Macros**: Define reusable batch command templates
5. **Project Autocomplete**: Suggest project names based on recent entries