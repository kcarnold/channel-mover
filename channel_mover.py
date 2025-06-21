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
    BUS_PATTERN = re.compile(r"/bus/(\d+)/config\s+\"(.+)\"")
    
    def __init__(self):
        self.header: str = ""
        self.channel_names: Dict[str, str] = {}
        self.bus_names: Dict[str, str] = {}
        self.channel_links: List[ChannelLink] = []
        self.bus_links: List[ChannelLink] = []
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
        self._extract_bus_names(lines)
        self._extract_channel_links(lines)
        self._extract_bus_links(lines)
        self._ensure_all_channels_named()
        self._ensure_all_buses_named()
    
    def _extract_channel_names(self, lines: List[str]) -> None:
        """Extract channel names from config lines."""
        for line in lines:
            if match := self.CHANNEL_PATTERN.match(line):
                channel_number = match.group(1)
                channel_name = match.group(2)
                self.channel_names[f"ch{channel_number}"] = channel_name
    
    def _extract_bus_names(self, lines: List[str]) -> None:
        """Extract bus names from config lines."""
        for line in lines:
            if match := self.BUS_PATTERN.match(line):
                bus_number = match.group(1)
                bus_name = match.group(2)
                self.bus_names[f"bus{bus_number}"] = bus_name
    
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
    
    def _extract_bus_links(self, lines: List[str]) -> None:
        """Extract bus link information from config lines."""
        for line in lines:
            if line.startswith("/config/buslink"):
                link_states = [x == "ON" for x in line.split(" ")[1:]]
                assert len(link_states) == 8
                
                # Convert boolean links to ChannelLink objects for buses
                self.bus_links = []
                for i, is_linked in enumerate(link_states):
                    if is_linked:
                        left_bus = i * 2
                        right_bus = i * 2 + 1
                        self.bus_links.append(ChannelLink(left_bus, right_bus))
                break
    
    def _ensure_all_channels_named(self) -> None:
        """Ensure all 32 channels have names, using defaults if needed."""
        for i in range(32):
            num = str(i+1).zfill(2)
            channel_key = f"ch{num}"
            if channel_key not in self.channel_names:
                self.channel_names[channel_key] = f"Ch {num}"
    
    def _ensure_all_buses_named(self) -> None:
        """Ensure all 16 buses have names, using defaults if needed."""
        for i in range(16):
            num = str(i+1).zfill(2)
            bus_key = f"bus{num}"
            if bus_key not in self.bus_names:
                self.bus_names[bus_key] = f"Bus {num}"
    
    def get_channel_link_info(self, channel: int) -> Optional[Tuple[int, str]]:
        """Get link information for a channel (partner channel and side)."""
        for link in self.channel_links:
            if link.contains_channel(channel):
                partner = link.get_partner(channel)
                side = link.get_side(channel)
                return (partner, side) if partner is not None and side is not None else None
        return None

    def get_bus_link_info(self, bus: int) -> Optional[Tuple[int, str]]:
        """Get link information for a bus (partner bus and side)."""
        for link in self.bus_links:
            if link.contains_channel(bus):  # ChannelLink works for buses too
                partner = link.get_partner(bus)
                side = link.get_side(bus)
                return (partner, side) if partner is not None and side is not None else None
        return None


class ChannelMapper:
    """Handles channel mapping logic and validation."""
    
    def __init__(self, scene_parser: SceneParser, crossbar: Crossbar, bus_crossbar: Crossbar):
        self.scene_parser = scene_parser
        self.crossbar = crossbar
        self.bus_crossbar = bus_crossbar
    
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
    
    def get_new_bus_links(self) -> List[ChannelLink]:
        """Map old bus links to new bus positions."""
        new_links = []
        
        # Track which new buses are already linked to avoid duplicates
        linked_buses = set()
        
        for old_link in self.scene_parser.bus_links:
            # Find where the old linked buses map to
            new_left = self.bus_crossbar.old_to_new[old_link.left_channel]
            new_right = self.bus_crossbar.old_to_new[old_link.right_channel]
            
            # Only create new link if both buses are mapped
            if (new_left is not None and new_right is not None and 
                new_left not in linked_buses and new_right not in linked_buses):
                new_links.append(ChannelLink(new_left, new_right))
                linked_buses.add(new_left)
                linked_buses.add(new_right)
        
        return new_links
    
    def validate_bus_links(self, new_links: List[ChannelLink]) -> List[str]:
        """Validate new bus links and return any warnings."""
        warnings = []
        
        # Check for expected stereo pairs that are broken
        for i in range(8):
            left_bus = i * 2
            right_bus = i * 2 + 1
            
            # Check if these buses should be linked based on new mapping
            left_old = self.bus_crossbar.new_to_old[left_bus]
            right_old = self.bus_crossbar.new_to_old[right_bus]
            
            if left_old is not None and right_old is not None:
                # Check if the old buses were linked
                old_link_info_left = self.scene_parser.get_bus_link_info(left_old)
                old_link_info_right = self.scene_parser.get_bus_link_info(right_old)
                
                # If old buses were linked to each other, check if new ones are too
                if (old_link_info_left and old_link_info_left[0] == right_old and
                    old_link_info_right and old_link_info_right[0] == left_old):
                    
                    # They should be linked in new positions
                    new_link_found = any(
                        link.left_channel == left_bus and link.right_channel == right_bus
                        for link in new_links
                    )
                    
                    if not new_link_found:
                        left_name = self.scene_parser.bus_names[f"bus{left_old + 1:02d}"]
                        right_name = self.scene_parser.bus_names[f"bus{right_old + 1:02d}"]
                        warnings.append(
                            f"Bus stereo link broken: {left_name} and {right_name} "
                            f"were linked but are now on non-adjacent buses "
                            f"{left_bus + 1} and {right_bus + 1}"
                        )
        
        return warnings
    
    def get_bus_link_states_for_export(self, new_links: List[ChannelLink]) -> List[bool]:
        """Convert new bus links back to boolean format for file export."""
        link_states = [False] * 8
        
        for link in new_links:
            # Check if this is a standard stereo pair (adjacent buses)
            if link.right_channel == link.left_channel + 1 and link.left_channel % 2 == 0:
                pair_index = link.left_channel // 2
                if 0 <= pair_index < 8:
                    link_states[pair_index] = True
        
        return link_states


@dataclass
class SourceCodeMapper:
    """Handles remapping of source codes used throughout the X32 configuration.
    
    The X32 uses different source code conventions in different contexts:
    
    Convention 1 (0-64 range): Used by channel sources, gate/dyn key sources, aux input sources
    - 0: OFF
    - 1-32: In01-32 (Channels)
    - 33-38: Aux 1-6  
    - 39-40: USB L/R
    - 41-48: Fx 1L-Fx 4R
    - 49-64: Bus 01-16
    
    Convention 2 (0-76 range): Used by output sources
    - 0-3: off, mainL/R, mono
    - 4-19: mixbuses 1-16
    - 20-25: Matrix 1-6
    - 26-57: Channels 1-32
    - 58-63: Aux 1-6
    - 64-73: FX1L-FX4R
    - 74-76: monL, monR, talkback
    """
    
    channel_crossbar: Crossbar
    bus_crossbar: Crossbar
    
    def remap_source_code_convention1(self, src_code: int) -> int:
        """Remap source codes using Convention 1 (0-64 range)."""
        # Channel source codes are 1-32 (channels 1-32)
        if 1 <= src_code <= 32:
            old_channel_num = src_code - 1
            new_channel_number = self.channel_crossbar.old_to_new[old_channel_num]
            
            if new_channel_number is None:
                return 0  # Set to off
            else:
                return new_channel_number + 1
        
        # Mix bus source codes are 49-64 (buses 1-16)
        elif 49 <= src_code <= 64:
            old_bus_num = src_code - 49
            new_bus_number = self.bus_crossbar.old_to_new[old_bus_num]
            
            if new_bus_number is None:
                return 0  # Set to off
            else:
                return new_bus_number + 49
        
        # All other source codes remain unchanged (OFF, Aux, USB, FX)
        return src_code
    
    def remap_source_code_convention2(self, src_code: int) -> int:
        """Remap source codes using Convention 2 (0-76 range)."""
        # Channel source codes are 26-57 (channels 1-32)
        if 26 <= src_code <= 57:
            old_channel_num = src_code - 26
            new_channel_number = self.channel_crossbar.old_to_new[old_channel_num]
            
            if new_channel_number is None:
                return 0  # Set to off
            else:
                return new_channel_number + 26
        
        # Mix bus source codes are 4-19 (buses 1-16)
        elif 4 <= src_code <= 19:
            old_bus_num = src_code - 4
            new_bus_number = self.bus_crossbar.old_to_new[old_bus_num]
            
            if new_bus_number is None:
                return 0  # Set to off
            else:
                return new_bus_number + 4
        
        # All other source codes remain unchanged
        return src_code


class SceneGenerator:
    """Handles generation of new scene files."""
    
    def __init__(self, scene_parser: SceneParser, channel_mapper: ChannelMapper):
        self.scene_parser = scene_parser
        self.channel_mapper = channel_mapper
        self.source_mapper = SourceCodeMapper(
            channel_mapper.crossbar, 
            channel_mapper.bus_crossbar
        )
    
    def generate_new_scene(self) -> str:
        """Generate a new scene file with remapped channels and buses."""
        new_links = self.channel_mapper.get_new_channel_links()
        link_states = self.channel_mapper.get_link_states_for_export(new_links)
        
        new_bus_links = self.channel_mapper.get_new_bus_links()
        bus_link_states = self.channel_mapper.get_bus_link_states_for_export(new_bus_links)
        
        new_scene = [self.scene_parser.header]
        already_warned = set()
        
        for setting in self.scene_parser.config_lines:
            if setting.path.startswith("/config/chlink"):
                # Update channel links
                setting = ConfigLine(
                    path=setting.path,
                    value=" ".join(["ON" if x else "OFF" for x in link_states])
                )
            elif setting.path.startswith("/config/buslink"):
                # Update bus links
                setting = ConfigLine(
                    path=setting.path,
                    value=" ".join(["ON" if x else "OFF" for x in bus_link_states])
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
                
                # Remap any source codes within channel settings
                setting = self._remap_setting_source_codes(setting)
                
            elif setting.match_context("/bus"):
                # Remap bus settings
                old_bus_num = int(setting.path_parts[1]) - 1
                new_bus_number = self.channel_mapper.bus_crossbar.old_to_new[old_bus_num]
                
                if new_bus_number is None:
                    # Skip unmapped buses
                    continue
                
                setting = setting.with_replaced_path_part(1, str(new_bus_number + 1).zfill(2))
                
                # Remap any source codes within bus settings
                setting = self._remap_setting_source_codes(setting)
                
            elif setting.match_context("/auxin"):
                # Remap aux input source codes
                setting = self._remap_setting_source_codes(setting)
                
            elif setting.match_context("/mtx"):
                # Remap matrix source codes (assuming they use Convention 1)
                setting = self._remap_setting_source_codes(setting)
                
            elif setting.path.startswith("/outputs") and len(setting.path_parts) == 3:
                # Remap output sources (uses Convention 2)
                setting = self._remap_output_source(setting)
            
            elif setting.path.startswith("/p16") or setting.path.startswith("/dp48"):
                # Remap DP48/P16 source codes (likely Convention 1, but need to verify)
                setting = self._remap_setting_source_codes(setting)
            
            # Remap any other source codes that might be missed
            elif self._setting_contains_source_code(setting):
                setting = self._remap_setting_source_codes(setting)
            
            new_scene.append(str(setting))
        
        return "\n".join(new_scene) + "\n"
    
    def _setting_contains_source_code(self, setting: ConfigLine) -> bool:
        """Check if a setting contains source codes that need remapping."""
        # Common paths that contain source codes (Convention 1: 0-64 range)
        convention1_paths = [
            "/config/source",  # Channel and aux sources
            "/gate/keysrc",    # Gate key sources
            "/dyn/keysrc",     # Dynamics key sources
        ]
        
        return any(setting.path.endswith(path) for path in convention1_paths)
    
    def _remap_setting_source_codes(self, setting: ConfigLine) -> ConfigLine:
        """Remap source codes within a setting value."""
        if not self._setting_contains_source_code(setting):
            return setting
        
        # These settings use Convention 1 (0-64 range)
        try:
            src_code = int(setting.value.strip())
            new_src_code = self.source_mapper.remap_source_code_convention1(src_code)
            return ConfigLine(setting.path, str(new_src_code))
        except ValueError:
            # If we can't parse as int, leave unchanged
            return setting
    
    def _remap_output_source(self, setting: ConfigLine) -> ConfigLine:
        """Remap output source codes for main outputs (Convention 2: 0-76 range)."""
        src_code_raw = setting.value.split(" ")[0]
        try:
            src_code = int(src_code_raw)
            new_src_code = self.source_mapper.remap_source_code_convention2(src_code)
            
            return ConfigLine(
                path=setting.path,
                value=f"{new_src_code} {setting.value.split(' ', 1)[1]}"
            )
        except (ValueError, IndexError):
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
    
    # Initialize or reset bus crossbar
    if st.session_state.get('bus_crossbar') is None:
        st.session_state.bus_crossbar = Crossbar(n=16)
    bus_crossbar = st.session_state.bus_crossbar

    # Load crossbar from JSON
    load_crossbar = st.text_input("Paste crossbar JSON here")
    if load_crossbar:
        st.session_state.channel_crossbar = channel_crossbar = Crossbar(n=32)
        st.session_state.bus_crossbar = bus_crossbar = Crossbar(n=16)
        data = json.loads(load_crossbar)
        if "channels" in data:
            for old, new in data["channels"]:
                channel_crossbar.connect(old, new)
        if "buses" in data:
            for old, new in data["buses"]:
                bus_crossbar.connect(old, new)
    
    # Create channel mapper
    channel_mapper = ChannelMapper(scene_parser, channel_crossbar, bus_crossbar)
    
    # UI for channel mapping
    with st.expander("Channel Mapping", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Set One-to-One Channel Mappings"):
                channel_crossbar.initialize_noop()
        with col2:
            if st.button("Clear All Channel Mappings"):
                channel_crossbar.clear_all_mappings()
        
        _render_channel_mapping_ui(scene_parser, channel_crossbar)
    
    # UI for bus mapping
    with st.expander("Mix Bus Mapping", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Set One-to-One Bus Mappings"):
                bus_crossbar.initialize_noop()
        with col2:
            if st.button("Clear All Bus Mappings"):
                bus_crossbar.clear_all_mappings()
        
        _render_bus_mapping_ui(scene_parser, bus_crossbar)
    
    # Show channel link validation
    new_links = channel_mapper.get_new_channel_links()
    warnings = channel_mapper.validate_channel_links(new_links)
    
    # Show bus link validation
    new_bus_links = channel_mapper.get_new_bus_links()
    bus_warnings = channel_mapper.validate_bus_links(new_bus_links)
    
    # Display all warnings
    all_warnings = warnings + bus_warnings
    if all_warnings:
        for warning in all_warnings:
            st.warning(warning)
    
    # Show link states
    link_states = channel_mapper.get_link_states_for_export(new_links)
    original_link_states = _get_original_link_states(scene_parser.channel_links)
    
    bus_link_states = channel_mapper.get_bus_link_states_for_export(new_bus_links)
    original_bus_link_states = _get_original_bus_link_states(scene_parser.bus_links)
    
    if link_states != original_link_states:
        st.write("New channel links:", ["ON" if x else "OFF" for x in link_states])
    else:
        st.write("Channel links unchanged")
    
    if bus_link_states != original_bus_link_states:
        st.write("New bus links:", ["ON" if x else "OFF" for x in bus_link_states])
    else:
        st.write("Bus links unchanged")
    
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
    st.subheader("Channel Mappings")
    st.code(json.dumps(channel_crossbar.get_mappings()))
    st.subheader("Bus Mappings")
    st.code(json.dumps(bus_crossbar.get_mappings()))


def _render_channel_mapping_ui(scene_parser: SceneParser, channel_crossbar: Crossbar):
    """Render the UI for mapping channels."""
    
    # Handle edit mode state
    if 'editing_channel' not in st.session_state:
        st.session_state.editing_channel = None
    
    # Handle channel selection
    if st.session_state.get('selected_old_channel') is not None:
        selected_old = st.session_state.selected_old_channel
        editing_new = st.session_state.editing_channel
        
        if editing_new is not None:
            # Clear old mapping if exists
            old_mapping = channel_crossbar.new_to_old[editing_new]
            if old_mapping is not None:
                channel_crossbar.disconnect(old=old_mapping, new=editing_new)
            
            # Set new mapping
            channel_crossbar.connect(old=selected_old, new=editing_new)
        
        # Clear edit state
        st.session_state.editing_channel = None
        st.session_state.selected_old_channel = None
        st.rerun()
    
    # Two column layout
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("New Channels")
        for i in range(32):
            new_num = i + 1
            mapped_old = channel_crossbar.new_to_old[i]
            
            # Show current mapping
            if mapped_old is not None:
                old_name = scene_parser.channel_names[f"ch{mapped_old+1:02d}"]
                link_info = scene_parser.get_channel_link_info(mapped_old)
                link_text = ""
                if link_info:
                    other_ch, side = link_info
                    link_text = f" (linked {side} with Ch {other_ch + 1})"
                display_text = f"**Ch {new_num:02d}**: {old_name} (was Ch {mapped_old+1}){link_text}"
            else:
                display_text = f"**Ch {new_num:02d}**: *unmapped*"
            
            # Create columns for text and button
            text_col, btn_col = st.columns([3, 1])
            with text_col:
                st.write(display_text)
            with btn_col:
                if st.button("Edit", key=f"edit_ch_{i}"):
                    st.session_state.editing_channel = i
                    st.rerun()
    
    with col2:
        if st.session_state.editing_channel is not None:
            editing_new = st.session_state.editing_channel
            st.subheader(f"Select source for Channel {editing_new + 1:02d}")
            
            # Get available old channels
            available_olds = channel_crossbar.get_unmapped_olds()
            current_old = channel_crossbar.new_to_old[editing_new]
            if current_old is not None:
                available_olds = [current_old] + available_olds
            
            # Add clear option
            if st.button("Clear mapping", key="clear_mapping"):
                if current_old is not None:
                    channel_crossbar.disconnect(old=current_old, new=editing_new)
                st.session_state.editing_channel = None
                st.rerun()
            
            st.write("Available channels:")
            for old_ch in available_olds:
                old_name = scene_parser.channel_names[f"ch{old_ch+1:02d}"]
                link_info = scene_parser.get_channel_link_info(old_ch)
                link_text = ""
                if link_info:
                    other_ch, side = link_info
                    link_text = f" (linked {side} with Ch {other_ch + 1})"
                
                button_text = f"Ch {old_ch+1:02d}: {old_name}{link_text}"
                if st.button(button_text, key=f"select_old_{old_ch}"):
                    st.session_state.selected_old_channel = old_ch
                    st.rerun()
            
            if st.button("Cancel", key="cancel_edit"):
                st.session_state.editing_channel = None
                st.rerun()
        else:
            st.subheader("Channel Mapping")
            st.write("Click 'Edit' next to a channel to change its mapping.")


def _render_bus_mapping_ui(scene_parser: SceneParser, bus_crossbar: Crossbar):
    """Render the UI for mapping buses."""
    
    # Handle edit mode state
    if 'editing_bus' not in st.session_state:
        st.session_state.editing_bus = None
    
    # Handle bus selection
    if st.session_state.get('selected_old_bus') is not None:
        selected_old = st.session_state.selected_old_bus
        editing_new = st.session_state.editing_bus
        
        if editing_new is not None:
            # Clear old mapping if exists
            old_mapping = bus_crossbar.new_to_old[editing_new]
            if old_mapping is not None:
                bus_crossbar.disconnect(old=old_mapping, new=editing_new)
            
            # Set new mapping
            bus_crossbar.connect(old=selected_old, new=editing_new)
        
        # Clear edit state
        st.session_state.editing_bus = None
        st.session_state.selected_old_bus = None
        st.rerun()
    
    # Two column layout
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("New Buses")
        for i in range(16):
            new_num = i + 1
            mapped_old = bus_crossbar.new_to_old[i]
            
            # Show current mapping
            if mapped_old is not None:
                old_name = scene_parser.bus_names[f"bus{mapped_old+1:02d}"]
                link_info = scene_parser.get_bus_link_info(mapped_old)
                link_text = ""
                if link_info:
                    other_bus, side = link_info
                    link_text = f" (linked {side} with Bus {other_bus + 1})"
                display_text = f"**Bus {new_num:02d}**: {old_name} (was Bus {mapped_old+1}){link_text}"
            else:
                display_text = f"**Bus {new_num:02d}**: *unmapped*"
            
            # Create columns for text and button
            text_col, btn_col = st.columns([3, 1])
            with text_col:
                st.write(display_text)
            with btn_col:
                if st.button("Edit", key=f"edit_bus_{i}"):
                    st.session_state.editing_bus = i
                    st.rerun()
    
    with col2:
        if st.session_state.editing_bus is not None:
            editing_new = st.session_state.editing_bus
            st.subheader(f"Select source for Bus {editing_new + 1:02d}")
            
            # Get available old buses
            available_olds = bus_crossbar.get_unmapped_olds()
            current_old = bus_crossbar.new_to_old[editing_new]
            if current_old is not None:
                available_olds = [current_old] + available_olds
            
            # Add clear option
            if st.button("Clear mapping", key="clear_bus_mapping"):
                if current_old is not None:
                    bus_crossbar.disconnect(old=current_old, new=editing_new)
                st.session_state.editing_bus = None
                st.rerun()
            
            st.write("Available buses:")
            for old_bus in available_olds:
                old_name = scene_parser.bus_names[f"bus{old_bus+1:02d}"]
                link_info = scene_parser.get_bus_link_info(old_bus)
                link_text = ""
                if link_info:
                    other_bus, side = link_info
                    link_text = f" (linked {side} with Bus {other_bus + 1})"
                
                button_text = f"Bus {old_bus+1:02d}: {old_name}{link_text}"
                if st.button(button_text, key=f"select_old_bus_{old_bus}"):
                    st.session_state.selected_old_bus = old_bus
                    st.rerun()
            
            if st.button("Cancel", key="cancel_bus_edit"):
                st.session_state.editing_bus = None
                st.rerun()
        else:
            st.subheader("Bus Mapping")
            st.write("Click 'Edit' next to a bus to change its mapping.")


def _get_original_bus_link_states(bus_links: List[ChannelLink]) -> List[bool]:
    """Convert ChannelLink objects to boolean bus link states."""
    link_states = [False] * 8
    for link in bus_links:
        if link.right_channel == link.left_channel + 1 and link.left_channel % 2 == 0:
            pair_index = link.left_channel // 2
            if 0 <= pair_index < 8:
                link_states[pair_index] = True
    return link_states


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
