# Channel Mover

A Streamlit application for reordering channels in Behringer X32 scene files without changing DSP settings.

## Features

- Upload X32 scene files (.scn format)
- Visually map old channels to new positions
- Preserve channel names and settings
- Maintain stereo links where possible
- Download modified scene files
- Validation and warnings for broken stereo links

## Usage

- Run the application: `uv run streamlit run channel_mover.py`
- Upload your X32 scene file
- Use the dropdown menus to map old channels to new positions
- Download the modified scene file

## Architecture

The application has been refactored into a modular, testable architecture:

- **Crossbar**: Core mapping logic between old and new positions
- **SceneParser**: Handles parsing X32 scene files
- **ChannelMapper**: Manages channel mapping and validation
- **SceneGenerator**: Creates new scene files with remapped channels
- **ConfigLine**: Represents individual configuration lines

See `ARCHITECTURE.md` for detailed documentation.

## Testing

Run tests with:
```bash
uv run pytest 
```

## Future Features

The modular architecture makes it easy to add:

- Bus reordering
- Matrix output remapping  
- Effect send/return reordering
- Batch processing of multiple scenes
