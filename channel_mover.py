import streamlit as st
import re
import json
from collections import namedtuple
from typing import List, Optional, Tuple

scene_file = st.file_uploader("Scene file", type="scn")
if not scene_file:
    st.stop()

class Crossbar:
    """Represents a 1-to-1 mapping between old and new.
    
    Example:
    
    >>> cb = Crossbar(n=4)
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

    def connect(self, old: int, new: int) -> None:
        self.old_to_new[old] = new
        self.new_to_old[new] = old

    def disconnect(self, old: int, new: int) -> None:
        self.old_to_new[old] = None
        self.new_to_old[new] = None

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

# run those doctests
import doctest
doctest.testmod()


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
    
    # ConfigLine(path=['ch', '01', 'config'], value='xxxxx xxxx'])
    ConfigLine(path="/ch/01/config", value="xxxxx xxxx")
    """
    parts = line.split(" ", 1)
    path = parts[0]#.split("/")[1:]
    value = parts[1]
    return ConfigLine(path, value)

# Match channel number and name
# e.g.,
# /ch/01/config "Acoustic Gtr" 23 RD 1
# should match 01 and "Acoustic Gtr"
channel_pattern = re.compile(r"/ch/(\d+)/config\s+\"(.+)\"")

channel_names = {}
lines = scene_file.read().decode('utf-8').splitlines()
# The file starts with a header line
# example:
# #4.0# "Choir" "" %000000000 1    
header = lines.pop(0)
parsed_lines = [parse_cfgline(line) for line in lines]
for line in lines:
    if line.startswith("/config/chlink"):
        link_states = [x == "ON" for x in line.split(" ")[1:]]
        assert len(link_states) == 16
        # Convert boolean links to the new tuple format
        # Each channel link is represented as either:
        # - None: channel is not linked
        # - (other_channel_number, 'L'|'R'): channel is linked to other_channel_number,
        #   where 'L' means this is the left channel, 'R' means this is the right channel
        # Each pair represents channels (2i, 2i+1) where i is the link index
        channel_links: List[Optional[Tuple[int, str]]] = [None] * 32
        for i, is_linked in enumerate(link_states):
            if is_linked:
                left_ch = i * 2
                right_ch = i * 2 + 1
                channel_links[left_ch] = (right_ch, 'L')
                channel_links[right_ch] = (left_ch, 'R')
    if match := channel_pattern.match(line):
        channel_number = match.group(1)
        channel_name = match.group(2)
        channel_names[f"ch{channel_number}"] = channel_name

for i in range(32):
    num = str(i+1).zfill(2)
    channel_names[f"ch{num}"] = channel_names.get(f"ch{num}", f"Ch {num}")

# The channel crossbar maps old to new channels.
if st.session_state.get('channel_crossbar') is None or st.button("Reset channels"):
    st.session_state.channel_crossbar = Crossbar(n=32)
channel_crossbar = st.session_state.channel_crossbar

load_crossbar = st.text_input("Paste crossbar JSON here")
# Example crossbar: [[0, 9], [1, 8], [2, 10], [3, 13], [4, 18], [5, 11], [6, 3], [7, 4], [8, 5], [9, 12], [10, 6], [11, 7], [12, 0], [13, 1], [14, 14], [15, 15], [16, 16], [17, 17], [18, 2], [19, 19], [20, 20], [21, 21], [22, 22], [23, 23], [24, 24], [25, 25], [26, 26], [27, 27], [28, 28], [29, 29], [30, 30], [31, 31]]
if load_crossbar:
    st.session_state.channel_crossbar = channel_crossbar = Crossbar(n=32)
    for old, new in json.loads(load_crossbar):
        channel_crossbar.connect(old, new)

st.header("New Channels")

def handle_change(key: str, prev_old: Optional[int], prev_new: int) -> None:
    cur_old_channel = st.session_state[key]
    if prev_old is not None:
        channel_crossbar.disconnect(old=prev_old, new=prev_new)
    if cur_old_channel is not None:
        channel_crossbar.connect(old=cur_old_channel, new=prev_new)

for i in range(32):
    num = str(i+1).zfill(2)
    key = f"ch{num}"

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
            link_info = channel_links[x]
            is_linked = link_info is not None
            link_text = ""
            if is_linked:
                other_ch, side = link_info
                link_text = f" (linked {side} with Ch {other_ch + 1})"
            return channel_names[f"ch{x+1:02d}"] + f" ({x+1})" + link_text

    st.selectbox(
        f"Channel {num}", options,
        key=key, index=index,
        format_func=format_func,
        on_change=handle_change,
        kwargs=dict(key=key, prev_old=already_mapped_old_channel_num, prev_new=i))

# Map old channel links to new channel positions
# Each new channel inherits the link information from its corresponding old channel
new_channel_links: List[Optional[Tuple[int, str]]] = [None] * 32
for i in range(32):
    old_channel_idx = channel_crossbar.new_to_old[i]
    if old_channel_idx is not None:
        old_link = channel_links[old_channel_idx]
        if old_link is not None:
            # This old channel was linked, find where its partner maps to
            old_partner_ch, side = old_link
            new_partner_ch = channel_crossbar.old_to_new[old_partner_ch]
            if new_partner_ch is not None:
                new_channel_links[i] = (new_partner_ch, side)
            else:
                st.warning(f"Channel {old_channel_idx + 1} was linked to channel {old_partner_ch + 1}, but the partner is not mapped")

# Convert back to boolean format for the link pairs for file output
link_states = [False] * 16
for i in range(16):
    left_ch = i * 2
    right_ch = i * 2 + 1
    left_link = new_channel_links[left_ch]
    right_link = new_channel_links[right_ch]
    
    # Check if these channels are linked to each other
    if (left_link is not None and left_link[0] == right_ch and left_link[1] == 'L' and
        right_link is not None and right_link[0] == left_ch and right_link[1] == 'R'):
        link_states[i] = True
    elif left_link is not None or right_link is not None:
        # One is linked but not to the expected partner
        if left_link:
            partner_ch, side = left_link
            # Get the old channel names that map to these new positions
            left_old_ch = channel_crossbar.new_to_old[left_ch]
            partner_old_ch = channel_crossbar.new_to_old[partner_ch]
            right_old_ch = channel_crossbar.new_to_old[right_ch]
            
            left_name = channel_names[f"ch{left_old_ch + 1:02d}"] if left_old_ch is not None else f"Ch {left_ch + 1}"
            partner_name = channel_names[f"ch{partner_old_ch + 1:02d}"] if partner_old_ch is not None else f"Ch {partner_ch + 1}"
            right_name = channel_names[f"ch{right_old_ch + 1:02d}"] if right_old_ch is not None else f"Ch {right_ch + 1}"
            
            st.warning(f"Link mismatch: {left_name} (New Ch {left_ch + 1}, Left) is linked to {partner_name} (New Ch {partner_ch + 1}) but should be linked to {right_name} (New Ch {right_ch + 1}, Right)")
        if right_link:
            partner_ch, side = right_link
            # Get the old channel names that map to these new positions
            right_old_ch = channel_crossbar.new_to_old[right_ch]
            partner_old_ch = channel_crossbar.new_to_old[partner_ch]
            left_old_ch = channel_crossbar.new_to_old[left_ch]
            
            right_name = channel_names[f"ch{right_old_ch + 1:02d}"] if right_old_ch is not None else f"Ch {right_ch + 1}"
            partner_name = channel_names[f"ch{partner_old_ch + 1:02d}"] if partner_old_ch is not None else f"Ch {partner_ch + 1}"
            left_name = channel_names[f"ch{left_old_ch + 1:02d}"] if left_old_ch is not None else f"Ch {left_ch + 1}"
            
            st.warning(f"Link mismatch: {right_name} (New Ch {right_ch + 1}, Right) is linked to {partner_name} (New Ch {partner_ch + 1}) but should be linked to {left_name} (New Ch {left_ch + 1}, Left)")

# Check if links have changed by comparing original and new link states
original_link_states = [False] * 16
for i in range(16):
    left_ch = i * 2
    right_ch = i * 2 + 1
    left_link = channel_links[left_ch]
    right_link = channel_links[right_ch]
    
    if (left_link is not None and left_link[0] == right_ch and left_link[1] == 'L' and
        right_link is not None and right_link[0] == left_ch and right_link[1] == 'R'):
        original_link_states[i] = True

if link_states != original_link_states:
    st.write("New channel links:", ["ON" if x else "OFF" for x in link_states])
else:
    st.write("Channel links unchanged")

# Source codes
# 0-3: off, mainL/R, mono
# 4-19: mixbuses 1-16
# 20-25: Matrix 1-6
# 26-57: Channels 1-32
# 58-63: Aux 1-6
# 64-73: FX1L-FX4R
# 74-76: monL, monR, talkback

# Regenerate the scene file
already_warned = {}
new_scene = [header]
for setting in parsed_lines:
    if setting.path.startswith("/config/chlink"):
        setting = ConfigLine(
            path=setting.path,
            value=" ".join(["ON" if x else "OFF" for x in link_states]))
    elif setting.match_context("/ch"):
        old_channel_num = int(setting.path_parts[1]) - 1
        new_channel_number = channel_crossbar.old_to_new[old_channel_num]
        if new_channel_number is None:
            if not already_warned.get(old_channel_num):
                old_channel_name = channel_names[f"ch{old_channel_num+1:02d}"]
                st.write("Skipping channel ", old_channel_name, " because it is not mapped.")
                already_warned[old_channel_num] = True
            continue
        setting = setting.with_replaced_path_part(1, str(new_channel_number + 1).zfill(2))
    elif setting.path.startswith("/outputs") and len(setting.path_parts) == 3:
        src_code_raw = setting.value.split(" ")[0]
        src_code = int(src_code_raw)
        if 26 <= src_code <= 57:
            old_channel_num = src_code - 26
            new_channel_number = channel_crossbar.old_to_new[old_channel_num]
            if new_channel_number is None:
                new_src_code = 0
                st.warning(f"Main output {setting.path} was from un-mapped channel {old_channel_num}. Setting to off.")
            else:
                new_src_code = new_channel_number + 26
            setting = ConfigLine(
                path=setting.path,
                value=f"{new_src_code} {setting.value.split(' ', 1)[1]}")
    new_scene.append(str(setting))

new_scene_serialized = "\n".join(new_scene) + "\n"
st.download_button("Download new scene", new_scene_serialized, "scene.scn", mime="text/plain")

st.info("Remember to turn off param and channel safes before loading the new scene!")

st.header("Debug")
st.code(json.dumps(channel_crossbar.get_mappings()))
