import streamlit as st
import re
import json
from collections import namedtuple
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass


class Crossbar:
    """Represents a 1-to-1 mapping between old and new.
    
    Example:
    
    >>> cb = Crossbar(n=4)
    >>> cb.clear_all_mappings()
    >>> cb.connect(0, 1)
    >>> cb.connect(2, 3)
    >>> cb.get_unmapped_olds()
    [1, 3]
    >>> cb.get_unmapped_news()
    [0, 2]
    >>> cb.old_to_new
    [1, None, 3, None]
    >>> cb.new_to_old
    [None, 0, None, 2]
    >>> cb.disconnect(0, 1)
    >>> cb.old_to_new
    [None, None, 3, None]
    >>> cb.new_to_old
    [None, None, None, 2]
    >>> cb.get_unmapped_olds()
    [0, 1, 3]
    >>> cb.get_mappings()
    [(2, 3)]
    """

    def __init__(self, n: int) -> None:
        self.old_to_new: List[Optional[int]] = [None] * n
        self.new_to_old: List[Optional[int]] = [None] * n
        self.initialize_noop()

    def connect(self, old: int, new: int) -> None:
        self.old_to_new[old] = new
        self.new_to_old[new] = old

    def disconnect(self, old: int, new: int) -> None:
        self.old_to_new[old] = None
        self.new_to_old[new] = None
    
    def initialize_noop(self) -> None:
        """Initialize with a no-op mapping where each channel maps to itself."""
        for i in range(len(self.old_to_new)):
            self.old_to_new[i] = i
            self.new_to_old[i] = i
    
    def clear_all_mappings(self) -> None:
        """Clear all current mappings."""
        for i in range(len(self.old_to_new)):
            self.old_to_new[i] = None
            self.new_to_old[i] = None

    def get_mappings(self) -> List[Tuple[int, int]]:
        return [(i, v) for i, v in enumerate(self.old_to_new) if v is not None]
    
    def get_unmapped_olds(self) -> List[int]:
        return [i for i, v in enumerate(self.old_to_new) if v is None]
    
    def get_unmapped_news(self) -> List[int]:
        return [i for i, v in enumerate(self.new_to_old) if v is None]
    
    def __str__(self) -> str:
        return f"Crossbar(old_to_new={self.old_to_new}, new_to_old={self.new_to_old})"
    
    def __repr__(self) -> str:
        return str(self)
    
    def __len__(self) -> int:
        return len(self.old_to_new)


class ConfigLine(namedtuple("ConfigLine", 'path value')):
    def match_context(self, path: str) -> bool:
        return self.path.startswith(path)
    
    def match_setting(self, path: str) -> bool:
        return self.path.endswith(path)
    
    @property
    def path_parts(self) -> List[str]:
        return self.path.split("/")[1:]
    
    def __str__(self) -> str:
        return f"{self.path} {self.value}"
    
    def with_replaced_path_part(self, index: int, new_value: str) -> "ConfigLine":
        path_parts = self.path_parts.copy()
        path_parts[index] = new_value
        preamble = self.path.split("/")[0]
        return ConfigLine("/".join([preamble] + path_parts), self.value)


def parse_cfgline(line: str) -> ConfigLine:
    """Parse config lines into parts and values.
    Example:
    
    /ch/01/config xxxxx xxxx

    becomes
    
    ConfigLine(path="/ch/01/config", value="xxxxx xxxx")
    """
    parts = line.split(" ", 1)
    path = parts[0]
    value = parts[1] if len(parts) > 1 else ""
    return ConfigLine(path, value)


@dataclass
class ChannelLink:
    """Represents a stereo link between two channels."""
    left_channel: int
    right_channel: int
    
    def contains_channel(self, channel: int) -> bool:
        return channel == self.left_channel or channel == self.right_channel
    
    def get_partner(self, channel: int) -> Optional[int]:
        if channel == self.left_channel:
            return self.right_channel
        elif channel == self.right_channel:
            return self.left_channel
        return None
    
    def get_side(self, channel: int) -> Optional[str]:
        if channel == self.left_channel:
            return 'L'
        elif channel == self.right_channel:
            return 'R'
        return None


class SceneParser:
    """Handles parsing and processing of scene files."""
    
    CHANNEL_PATTERN = re.compile(r"/ch/(\d+)/config\s+\"(.+)\"")
    
    def __init__(self):
        self.header: str = ""
        self.channel_names: Dict[str, str] = {}
        self.channel_links: List[ChannelLink] = []
        self.config_lines: List[ConfigLine] = []
        
    def parse_scene_file(self, file_content: str) -> None:
        """Parse a scene file and extract all relevant information."""
        lines = file_content.splitlines()
        
        # Parse header
        if lines:
            self.header = lines.pop(0)
        
        # Parse config lines
        self.config_lines = [parse_cfgline(line) for line in lines]
        
        # Extract channel names and links
        self._extract_channel_names(lines)
        self._extract_channel_links(lines)
        self._ensure_all_channels_named()
    
    def _extract_channel_names(self, lines: List[str]) -> None:
        """Extract channel names from config lines."""
        for line in lines:
            if match := self.CHANNEL_PATTERN.match(line):
                channel_number = match.group(1)
                channel_name = match.group(2)
                self.channel_names[f"ch{channel_number}"] = channel_name
    
    def _extract_channel_links(self, lines: List[str]) -> None:
        """Extract channel link information from config lines."""
        for line in lines:
            if line.startswith("/config/chlink"):
                link_states = [x == "ON" for x in line.split(" ")[1:]]
                assert len(link_states) == 16
                
                # Convert boolean links to ChannelLink objects
                self.channel_links = []
                for i, is_linked in enumerate(link_states):
                    if is_linked:
                        left_ch = i * 2
                        right_ch = i * 2 + 1
                        self.channel_links.append(ChannelLink(left_ch, right_ch))
                break
    
    def _ensure_all_channels_named(self) -> None:
        """Ensure all 32 channels have names, using defaults if needed."""
        for i in range(32):
            num = str(i+1).zfill(2)
            channel_key = f"ch{num}"
            if channel_key not in self.channel_names:
                self.channel_names[channel_key] = f"Ch {num}"
    
    def get_channel_link_info(self, channel: int) -> Optional[Tuple[int, str]]:
        """Get link information for a channel (partner channel and side)."""
        for link in self.channel_links:
            if link.contains_channel(channel):
                partner = link.get_partner(channel)
                side = link.get_side(channel)
                return (partner, side) if partner is not None and side is not None else None
        return None


class ChannelMapper:
    """Handles channel mapping logic and validation."""
    
    def __init__(self, scene_parser: SceneParser, crossbar: Crossbar):
        self.scene_parser = scene_parser
        self.crossbar = crossbar
    
    def get_new_channel_links(self) -> List[ChannelLink]:
        """Map old channel links to new channel positions."""
        new_links = []
        
        # Track which new channels are already linked to avoid duplicates
        linked_channels = set()
        
        for old_link in self.scene_parser.channel_links:
            # Find where the old linked channels map to
            new_left = self.crossbar.old_to_new[old_link.left_channel]
            new_right = self.crossbar.old_to_new[old_link.right_channel]
            
            # Only create new link if both channels are mapped
            if (new_left is not None and new_right is not None and 
                new_left not in linked_channels and new_right not in linked_channels):
                new_links.append(ChannelLink(new_left, new_right))
                linked_channels.add(new_left)
                linked_channels.add(new_right)
        
        return new_links
    
    def validate_channel_links(self, new_links: List[ChannelLink]) -> List[str]:
        """Validate new channel links and return any warnings."""
        warnings = []
        
        # Check for expected stereo pairs that are broken
        for i in range(16):
            left_ch = i * 2
            right_ch = i * 2 + 1
            
            # Check if these channels should be linked based on new mapping
            left_old = self.crossbar.new_to_old[left_ch]
            right_old = self.crossbar.new_to_old[right_ch]
            
            if left_old is not None and right_old is not None:
                # Check if the old channels were linked
                old_link_info_left = self.scene_parser.get_channel_link_info(left_old)
                old_link_info_right = self.scene_parser.get_channel_link_info(right_old)
                
                # If old channels were linked to each other, check if new ones are too
                if (old_link_info_left and old_link_info_left[0] == right_old and
                    old_link_info_right and old_link_info_right[0] == left_old):
                    
                    # They should be linked in new positions
                    new_link_found = any(
                        link.left_channel == left_ch and link.right_channel == right_ch
                        for link in new_links
                    )
                    
                    if not new_link_found:
                        left_name = self.scene_parser.channel_names[f"ch{left_old + 1:02d}"]
                        right_name = self.scene_parser.channel_names[f"ch{right_old + 1:02d}"]
                        warnings.append(
                            f"Stereo link broken: {left_name} and {right_name} "
                            f"were linked but are now on non-adjacent channels "
                            f"{left_ch + 1} and {right_ch + 1}"
                        )
        
        return warnings
    
    def get_link_states_for_export(self, new_links: List[ChannelLink]) -> List[bool]:
        """Convert new channel links back to boolean format for file export."""
        link_states = [False] * 16
        
        for link in new_links:
            # Check if this is a standard stereo pair (adjacent channels)
            if link.right_channel == link.left_channel + 1 and link.left_channel % 2 == 0:
                pair_index = link.left_channel // 2
                if 0 <= pair_index < 16:
                    link_states[pair_index] = True
        
        return link_states


class SceneGenerator:
    """Handles generation of new scene files."""
    
    def __init__(self, scene_parser: SceneParser, channel_mapper: ChannelMapper):
        self.scene_parser = scene_parser
        self.channel_mapper = channel_mapper
    
    def generate_new_scene(self) -> str:
        """Generate a new scene file with remapped channels."""
        new_links = self.channel_mapper.get_new_channel_links()
        link_states = self.channel_mapper.get_link_states_for_export(new_links)
        
        new_scene = [self.scene_parser.header]
        already_warned = set()
        
        for setting in self.scene_parser.config_lines:
            if setting.path.startswith("/config/chlink"):
                # Update channel links
                setting = ConfigLine(
                    path=setting.path,
                    value=" ".join(["ON" if x else "OFF" for x in link_states])
                )
            elif setting.match_context("/ch"):
                # Remap channel settings
                old_channel_num = int(setting.path_parts[1]) - 1
                new_channel_number = self.channel_mapper.crossbar.old_to_new[old_channel_num]
                
                if new_channel_number is None:
                    # Skip unmapped channels
                    if old_channel_num not in already_warned:
                        already_warned.add(old_channel_num)
                    continue
                
                setting = setting.with_replaced_path_part(1, str(new_channel_number + 1).zfill(2))
            elif setting.path.startswith("/outputs") and len(setting.path_parts) == 3:
                # Remap output sources
                setting = self._remap_output_source(setting)
            
            new_scene.append(str(setting))
        
        return "\n".join(new_scene) + "\n"
    
    def _remap_output_source(self, setting: ConfigLine) -> ConfigLine:
        """Remap output source codes for main outputs."""
        src_code_raw = setting.value.split(" ")[0]
        src_code = int(src_code_raw)
        
        # Channel source codes are 26-57 (channels 1-32)
        if 26 <= src_code <= 57:
            old_channel_num = src_code - 26
            new_channel_number = self.channel_mapper.crossbar.old_to_new[old_channel_num]
            
            if new_channel_number is None:
                new_src_code = 0  # Set to off
            else:
                new_src_code = new_channel_number + 26
            
            return ConfigLine(
                path=setting.path,
                value=f"{new_src_code} {setting.value.split(' ', 1)[1]}"
            )
        
        return setting


def main():
    """Main Streamlit application."""
    st.title("Channel Mover")
    
    # File upload
    scene_file = st.file_uploader("Scene file", type="scn")
    if not scene_file:
        st.stop()
    
    # Parse the scene file
    scene_parser = SceneParser()
    file_content = scene_file.read().decode('utf-8')
    scene_parser.parse_scene_file(file_content)
    
    # Initialize or reset channel crossbar
    if st.session_state.get('channel_crossbar') is None:
        st.session_state.channel_crossbar = Crossbar(n=32)
    channel_crossbar = st.session_state.channel_crossbar
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Set One-to-One Mappings"):
            channel_crossbar.initialize_noop()
    with col2:
        if st.button("Clear All Mappings"):
            channel_crossbar.clear_all_mappings()

    # Load crossbar from JSON
    load_crossbar = st.text_input("Paste crossbar JSON here")
    if load_crossbar:
        st.session_state.channel_crossbar = channel_crossbar = Crossbar(n=32)
        for old, new in json.loads(load_crossbar):
            channel_crossbar.connect(old, new)
    
    # Create channel mapper
    channel_mapper = ChannelMapper(scene_parser, channel_crossbar)
    
    # UI for channel mapping
    st.header("New Channels")
    _render_channel_mapping_ui(scene_parser, channel_crossbar)
    
    # Show channel link validation
    new_links = channel_mapper.get_new_channel_links()
    warnings = channel_mapper.validate_channel_links(new_links)
    if warnings:
        for warning in warnings:
            st.warning(warning)
    
    # Show link states
    link_states = channel_mapper.get_link_states_for_export(new_links)
    original_link_states = _get_original_link_states(scene_parser.channel_links)
    
    if link_states != original_link_states:
        st.write("New channel links:", ["ON" if x else "OFF" for x in link_states])
    else:
        st.write("Channel links unchanged")
    
    # Generate and offer download of new scene
    scene_generator = SceneGenerator(scene_parser, channel_mapper)
    new_scene_content = scene_generator.generate_new_scene()
    
    st.download_button(
        "Download new scene", 
        new_scene_content, 
        "scene.scn", 
        mime="text/plain"
    )
    
    st.info("Remember to turn off param and channel safes before loading the new scene!")
    
    # Debug information
    st.header("Debug")
    st.code(json.dumps(channel_crossbar.get_mappings()))


def _render_channel_mapping_ui(scene_parser: SceneParser, channel_crossbar: Crossbar):
    """Render the UI for mapping channels."""
    def handle_change(key: str, prev_old: Optional[int], prev_new: int) -> None:
        cur_old_channel = st.session_state.get(key, None)
        if cur_old_channel is None:
            print(f"Warning: {key} is None, skipping change")
            return
        if prev_old is not None:
            channel_crossbar.disconnect(old=prev_old, new=prev_new)
        if cur_old_channel is not None:
            channel_crossbar.connect(old=cur_old_channel, new=prev_new)

    for i in range(32):
        num = str(i+1).zfill(2)
        key = f"ch{num}"
        st.session_state.pop(key, None)  # Reset state for this key

        available_channels = channel_crossbar.get_unmapped_olds()
        already_mapped_old_channel_num = channel_crossbar.new_to_old[i]
        options = available_channels
        if already_mapped_old_channel_num is not None:
            options = [already_mapped_old_channel_num] + options
        options = [None] + options
        index = options.index(already_mapped_old_channel_num)
        
        def format_func(x: Optional[int]) -> str:
            if x is None:
                return ''
            else:
                link_info = scene_parser.get_channel_link_info(x)
                link_text = ""
                if link_info:
                    other_ch, side = link_info
                    link_text = f" (linked {side} with Ch {other_ch + 1})"
                return scene_parser.channel_names[f"ch{x+1:02d}"] + f" ({x+1})" + link_text

        st.selectbox(
            f"Channel {num}", options,
            key=key, index=index,
            format_func=format_func,
            on_change=handle_change,
            kwargs=dict(key=key, prev_old=already_mapped_old_channel_num, prev_new=i))


def _get_original_link_states(channel_links: List[ChannelLink]) -> List[bool]:
    """Convert ChannelLink objects to boolean link states."""
    link_states = [False] * 16
    for link in channel_links:
        if link.right_channel == link.left_channel + 1 and link.left_channel % 2 == 0:
            pair_index = link.left_channel // 2
            if 0 <= pair_index < 16:
                link_states[pair_index] = True
    return link_states


# Run doctests
import doctest
doctest.testmod()

if __name__ == "__main__":
    main()
