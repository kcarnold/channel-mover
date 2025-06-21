# Channel Mover - Refactored Architecture

## Overview

The channel mover application has been refactored into a modular, testable architecture. This makes it easier to add new features (like bus reordering) and maintain the codebase.

## Core Classes

### `Crossbar`
Represents a 1-to-1 mapping between old and new positions. This is the fundamental data structure for all remapping operations.

**Key Methods:**
- `connect(old, new)` - Maps an old position to a new position
- `disconnect(old, new)` - Removes a mapping
- `get_mappings()` - Returns all current mappings
- `get_unmapped_olds()` - Returns positions that haven't been mapped yet

### `ConfigLine`
Represents a single configuration line from the scene file.

**Key Methods:**
- `match_context(path)` - Check if this line is in a specific context (e.g., "/ch")
- `with_replaced_path_part(index, value)` - Create a new ConfigLine with a modified path

### `ChannelLink`
Represents a stereo link between two channels.

**Key Methods:**
- `contains_channel(channel)` - Check if a channel is part of this link
- `get_partner(channel)` - Get the partner channel in the link
- `get_side(channel)` - Get whether this is the 'L' or 'R' side

### `SceneParser`
Handles parsing and extracting information from scene files.

**Key Methods:**
- `parse_scene_file(content)` - Parse the entire scene file
- `get_channel_link_info(channel)` - Get link information for a specific channel

### `ChannelMapper`
Handles the logic for mapping channels and validating links.

**Key Methods:**
- `get_new_channel_links()` - Map old channel links to new positions
- `validate_channel_links(links)` - Check for broken or invalid links
- `get_link_states_for_export()` - Convert links to the format needed for file export

### `SceneGenerator`
Handles generation of new scene files with remapped channels.

**Key Methods:**
- `generate_new_scene()` - Create a complete new scene file with all remappings applied

## Benefits of This Architecture

1. **Separation of Concerns**: Each class has a single, well-defined responsibility
2. **Testability**: Each component can be tested independently
3. **Extensibility**: Easy to add new features like bus remapping
4. **Maintainability**: Clear interfaces make the code easier to understand and modify
5. **Reusability**: Components can be reused for different types of remapping

## Adding Bus Reordering

To add bus reordering, you would:

1. Create a `BusMapper` class similar to `ChannelMapper`
2. Add bus parsing logic to `SceneParser`
3. Update `SceneGenerator` to handle bus remapping
4. Add a `BusCrossbar` or reuse the existing `Crossbar` class

The modular structure makes this straightforward to implement without affecting existing channel functionality.

## Testing

The refactored code includes comprehensive tests in `test_channel_mover.py`. Run tests with:

```bash
uv run test_channel_mover.py
```

All existing functionality has been preserved while making the code more maintainable and extensible.
