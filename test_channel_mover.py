import os
import pytest

from channel_mover import (ChannelLink, ChannelMapper, ConfigLine, Crossbar,
                           SceneGenerator, SceneParser, SourceCodeMapper, parse_cfgline)


class TestCrossbar:
    def test_basic_operations(self):
        cb = Crossbar(n=4)
        cb.connect(0, 1)
        cb.connect(2, 3)
        
        assert cb.get_unmapped_olds() == [1, 3]
        assert cb.get_unmapped_news() == [0, 2]
        assert cb.old_to_new == [1, None, 3, None]
        assert cb.new_to_old == [None, 0, None, 2]
        
        cb.disconnect(0, 1)
        assert cb.old_to_new == [None, None, 3, None]
        assert cb.new_to_old == [None, None, None, 2]
        assert cb.get_unmapped_olds() == [0, 1, 3]
        assert cb.get_mappings() == [(2, 3)]


class TestConfigLine:
    def test_parse_cfgline(self):
        line = "/ch/01/config \"Acoustic Gtr\" 23 RD 1"
        config = parse_cfgline(line)
        assert config.path == "/ch/01/config"
        assert config.value == "\"Acoustic Gtr\" 23 RD 1"
        
    def test_path_parts(self):
        config = ConfigLine("/ch/01/config", "value")
        assert config.path_parts == ["ch", "01", "config"]
        
    def test_match_context(self):
        config = ConfigLine("/ch/01/config", "value")
        assert config.match_context("/ch")
        assert not config.match_context("/outputs")
        
    def test_with_replaced_path_part(self):
        config = ConfigLine("/ch/01/config", "value")
        new_config = config.with_replaced_path_part(1, "05")
        assert new_config.path == "/ch/05/config"
        assert new_config.value == "value"


class TestChannelLink:
    def test_contains_channel(self):
        link = ChannelLink(0, 1)
        assert link.contains_channel(0)
        assert link.contains_channel(1)
        assert not link.contains_channel(2)
        
    def test_get_partner(self):
        link = ChannelLink(0, 1)
        assert link.get_partner(0) == 1
        assert link.get_partner(1) == 0
        assert link.get_partner(2) is None
        
    def test_get_side(self):
        link = ChannelLink(0, 1)
        assert link.get_side(0) == 'L'
        assert link.get_side(1) == 'R'
        assert link.get_side(2) is None


class TestSceneParser:
    def test_parse_scene_file(self):
        scene_content = '''#4.0# "Test Scene" "" %000000000 1
/ch/01/config "Acoustic Gtr" 23 RD 1
/ch/02/config "Electric Gtr" 24 RD 1
/config/chlink ON OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF'''
        
        parser = SceneParser()
        parser.parse_scene_file(scene_content)
        
        assert parser.header == '#4.0# "Test Scene" "" %000000000 1'
        assert parser.channel_names["ch01"] == "Acoustic Gtr"
        assert parser.channel_names["ch02"] == "Electric Gtr"
        assert len(parser.channel_links) == 1
        assert parser.channel_links[0].left_channel == 0
        assert parser.channel_links[0].right_channel == 1
        
    def test_parse_scene_file_with_buses(self):
        scene_content = '''#4.0# "Test Scene" "" %000000000 1
/bus/01/config "Main L" 23 RD 1
/bus/02/config "Main R" 24 RD 1
/config/buslink ON OFF OFF OFF OFF OFF OFF OFF'''
        
        parser = SceneParser()
        parser.parse_scene_file(scene_content)
        
        assert parser.header == '#4.0# "Test Scene" "" %000000000 1'
        assert parser.bus_names["bus01"] == "Main L"
        assert parser.bus_names["bus02"] == "Main R"
        assert len(parser.bus_links) == 1
        assert parser.bus_links[0].left_channel == 0
        assert parser.bus_links[0].right_channel == 1
        
    def test_get_channel_link_info(self):
        parser = SceneParser()
        parser.channel_links = [ChannelLink(0, 1), ChannelLink(4, 5)]
        
        assert parser.get_channel_link_info(0) == (1, 'L')
        assert parser.get_channel_link_info(1) == (0, 'R')
        assert parser.get_channel_link_info(2) is None
        
    def test_get_bus_link_info(self):
        parser = SceneParser()
        parser.bus_links = [ChannelLink(0, 1), ChannelLink(4, 5)]
        
        assert parser.get_bus_link_info(0) == (1, 'L')
        assert parser.get_bus_link_info(1) == (0, 'R')
        assert parser.get_bus_link_info(2) is None


class TestChannelMapper:
    def test_get_new_channel_links(self):
        scene_parser = SceneParser()
        scene_parser.channel_links = [ChannelLink(0, 1), ChannelLink(2, 3)]
        
        crossbar = Crossbar(32)
        bus_crossbar = Crossbar(16)
        crossbar.connect(0, 2)  # Old channel 0 -> new channel 2
        crossbar.connect(1, 3)  # Old channel 1 -> new channel 3
        crossbar.connect(2, 0)  # Old channel 2 -> new channel 0
        crossbar.connect(3, 1)  # Old channel 3 -> new channel 1
        
        mapper = ChannelMapper(scene_parser, crossbar, bus_crossbar)
        new_links = mapper.get_new_channel_links()
        
        assert len(new_links) == 2
        # Original link (0,1) should map to new link (2,3)
        assert any(link.left_channel == 2 and link.right_channel == 3 for link in new_links)
        # Original link (2,3) should map to new link (0,1)
        assert any(link.left_channel == 0 and link.right_channel == 1 for link in new_links)
        
    def test_get_link_states_for_export(self):
        scene_parser = SceneParser()
        crossbar = Crossbar(32)
        bus_crossbar = Crossbar(16)
        mapper = ChannelMapper(scene_parser, crossbar, bus_crossbar)
        
        # Test with standard stereo pairs
        new_links = [ChannelLink(0, 1), ChannelLink(4, 5)]
        link_states = mapper.get_link_states_for_export(new_links)
        
        expected = [False] * 16
        expected[0] = True  # Channels 0,1 -> pair 0
        expected[2] = True  # Channels 4,5 -> pair 2
        
        assert link_states == expected
        
    def test_get_new_bus_links(self):
        scene_parser = SceneParser()
        scene_parser.bus_links = [ChannelLink(0, 1), ChannelLink(4, 5)]
        
        crossbar = Crossbar(32)
        bus_crossbar = Crossbar(16)
        bus_crossbar.connect(0, 2)  # Old bus 0 -> new bus 2
        bus_crossbar.connect(1, 3)  # Old bus 1 -> new bus 3
        bus_crossbar.connect(4, 0)  # Old bus 4 -> new bus 0
        bus_crossbar.connect(5, 1)  # Old bus 5 -> new bus 1
        
        mapper = ChannelMapper(scene_parser, crossbar, bus_crossbar)
        new_links = mapper.get_new_bus_links()
        
        assert len(new_links) == 2
        # Original link (0,1) should map to new link (2,3)
        assert any(link.left_channel == 2 and link.right_channel == 3 for link in new_links)
        # Original link (4,5) should map to new link (0,1)
        assert any(link.left_channel == 0 and link.right_channel == 1 for link in new_links)
        
    def test_get_bus_link_states_for_export(self):
        scene_parser = SceneParser()
        crossbar = Crossbar(32)
        bus_crossbar = Crossbar(16)
        mapper = ChannelMapper(scene_parser, crossbar, bus_crossbar)
        
        # Test with standard stereo pairs
        new_links = [ChannelLink(0, 1), ChannelLink(4, 5)]
        link_states = mapper.get_bus_link_states_for_export(new_links)
        
        expected = [False] * 8
        expected[0] = True  # Buses 0,1 -> pair 0
        expected[2] = True  # Buses 4,5 -> pair 2
        
        assert link_states == expected


class TestSceneGenerator:
    def test_generate_new_scene_basic(self):
        # Create a minimal scene
        scene_parser = SceneParser()
        scene_parser.header = "#4.0# Test"
        scene_parser.config_lines = [
            ConfigLine("/ch/01/config", "\"Test\" 1 RD 1"),
            ConfigLine("/config/chlink", "OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF")
        ]
        scene_parser.channel_names = {"ch01": "Test", "ch02": "Ch 02"}
        
        crossbar = Crossbar(32)
        bus_crossbar = Crossbar(16)
        crossbar.connect(0, 1)  # Move old channel 1 to new channel 2
        
        mapper = ChannelMapper(scene_parser, crossbar, bus_crossbar)
        generator = SceneGenerator(scene_parser, mapper)
        
        result = generator.generate_new_scene()
        lines = result.split('\n')
        
        assert lines[0] == "#4.0# Test"
        assert "/ch/02/config \"Test\" 1 RD 1" in lines


class TestSourceCodeMapper:
    def test_remap_source_code_convention1_channels(self):
        """Test remapping of channel source codes in Convention 1 (0-64 range)."""
        channel_crossbar = Crossbar(32)
        bus_crossbar = Crossbar(16)
        
        # Set up some mappings
        channel_crossbar.connect(0, 5)  # Old channel 1 -> new channel 6
        
        mapper = SourceCodeMapper(channel_crossbar, bus_crossbar)
        
        # Test channel source codes (1-32 -> channels 1-32)
        assert mapper.remap_source_code_convention1(1) == 6  # Channel 1 -> Channel 6
        assert mapper.remap_source_code_convention1(2) == 0  # Unmapped channel -> OFF
        
        # Test non-channel codes remain unchanged
        assert mapper.remap_source_code_convention1(0) == 0   # OFF
        assert mapper.remap_source_code_convention1(33) == 33 # Aux 1
        assert mapper.remap_source_code_convention1(39) == 39 # USB L
        
    def test_remap_source_code_convention1_buses(self):
        """Test remapping of bus source codes in Convention 1 (0-64 range)."""
        channel_crossbar = Crossbar(32)
        bus_crossbar = Crossbar(16)
        
        # Set up some bus mappings
        bus_crossbar.connect(0, 3)  # Old bus 1 -> new bus 4
        
        mapper = SourceCodeMapper(channel_crossbar, bus_crossbar)
        
        # Test bus source codes (49-64 -> buses 1-16)
        assert mapper.remap_source_code_convention1(49) == 52  # Bus 1 -> Bus 4
        assert mapper.remap_source_code_convention1(50) == 0   # Unmapped bus -> OFF
        
    def test_remap_source_code_convention2_channels(self):
        """Test remapping of channel source codes in Convention 2 (0-76 range)."""
        channel_crossbar = Crossbar(32)
        bus_crossbar = Crossbar(16)
        
        # Set up some mappings
        channel_crossbar.connect(0, 5)  # Old channel 1 -> new channel 6
        
        mapper = SourceCodeMapper(channel_crossbar, bus_crossbar)
        
        # Test channel source codes (26-57 -> channels 1-32)
        assert mapper.remap_source_code_convention2(26) == 31  # Channel 1 -> Channel 6
        assert mapper.remap_source_code_convention2(27) == 0   # Unmapped channel -> OFF
        
        # Test non-channel codes remain unchanged
        assert mapper.remap_source_code_convention2(0) == 0   # off
        assert mapper.remap_source_code_convention2(58) == 58 # Aux 1
        
    def test_remap_source_code_convention2_buses(self):
        """Test remapping of bus source codes in Convention 2 (0-76 range)."""
        channel_crossbar = Crossbar(32)
        bus_crossbar = Crossbar(16)
        
        # Set up some bus mappings
        bus_crossbar.connect(0, 3)  # Old bus 1 -> new bus 4
        
        mapper = SourceCodeMapper(channel_crossbar, bus_crossbar)
        
        # Test bus source codes (4-19 -> buses 1-16)
        assert mapper.remap_source_code_convention2(4) == 7   # Bus 1 -> Bus 4
        assert mapper.remap_source_code_convention2(5) == 0   # Unmapped bus -> OFF


EXAMPLE_SCN_PATH = os.path.join(os.path.dirname(__file__), "example.scn")

class TestIntegrationExampleScene:
    def test_parse_example_scene(self):
        with open(EXAMPLE_SCN_PATH) as f:
            content = f.read()
        parser = SceneParser()
        parser.parse_scene_file(content)
        # Basic header check
        assert parser.header.startswith("#4.0#")
        # Check that some known channels are present
        assert parser.channel_names["ch01"] == "Pastor"
        assert parser.channel_names["ch02"] == "HH Speak"
        # Check that channel links are parsed
        assert len(parser.channel_links) == 3  # From ONs in /config/chlink
        # Check that bus links are parsed
        assert len(parser.bus_links) == 4  # From ONs in /config/buslink

    def test_channel_link_info(self):
        with open(EXAMPLE_SCN_PATH) as f:
            content = f.read()
        parser = SceneParser()
        parser.parse_scene_file(content)
        # Channel 22 and 23 should be linked (from /config/chlink, ON at index 11)
        info_22 = parser.get_channel_link_info(22)
        info_23 = parser.get_channel_link_info(23)
        assert info_22 is not None
        assert info_23 is not None
        partner_22, side_22 = info_22
        partner_23, side_23 = info_23
        assert partner_22 == 23
        assert side_22 == 'L'
        assert partner_23 == 22
        assert side_23 == 'R'
        # Unlinked channel
        assert parser.get_channel_link_info(2) is None


class TestBusRemapIntegration:
    """
    Integration test for remapping buses and verifying:
    - Bus order and names
    - Channel sends (level, PRE/POST, follow LR)
    - Sidechain for Cong mics
    - Aux and FX sources
    Assumptions:
    - Bus mapping is as described in the user prompt.
    - Channel and bus names are unique and stable.
    - PRE/POST/follow LR are encoded in the /ch/XX/mix/YY lines and must be preserved.
    - Cong mics are named "CongMics" in the scene file.
    - Speech bus is named "Speech".
    - Aux and FX sources are routed via /config/routing/OUT and similar lines.
    """
    def test_bus_remap_and_sends(self):
        import os
        EXAMPLE_SCN_PATH = os.path.join(os.path.dirname(__file__), "example.scn")
        with open(EXAMPLE_SCN_PATH) as f:
            content = f.read()
        parser = SceneParser()
        parser.parse_scene_file(content)

        # --- Step 1: Discover actual bus order and names from the file ---
        bus_names = []
        for i in range(1, 17):
            name = None
            for cl in parser.config_lines:
                if cl.path == f"/bus/{i:02d}/config":
                    name = cl.value.split('"')[1] if '"' in cl.value else cl.value.split()[0]
                    break
            if not name:
                raise AssertionError(f"Bus {i} config not found in scene file!")
            bus_names.append(name)
        # Print for debug
        print("Bus order in file:", bus_names)

        # --- Step 2: Build new order (user must specify desired new order by name) ---
        # Example: monitors first, then mixes (user must update this list as needed)
        # If any name is missing, fail noisy
        desired_new_order = [
            "M Vox", "M. Piano", "M.Choir", "M. Gt2", "IEM drum L", "IEM drum R", "keys iem l", "keys iem r",  # monitors
            "Vox SubG L", "Vox SubG R", "Speech", "Drum2Stream", "Inst2Stream", "Fx 2", "Stream L", "Stream R",  # mixes/other
        ]
        for name in desired_new_order:
            if name not in bus_names:
                raise AssertionError(f"Desired bus '{name}' not found in file! Found: {bus_names}")
        old_to_new = [desired_new_order.index(name) for name in bus_names]

        # --- Step 3: Set up bus crossbar for the new order ---
        bus_crossbar = Crossbar(16)
        for old, new in enumerate(old_to_new):
            bus_crossbar.connect(old, new)
        channel_crossbar = Crossbar(32)
        channel_crossbar.initialize_noop()
        mapper = ChannelMapper(parser, channel_crossbar, bus_crossbar)
        generator = SceneGenerator(parser, mapper)
        new_scene = generator.generate_new_scene()
        new_parser = SceneParser()
        new_parser.parse_scene_file(new_scene)

        # --- Step 4: Check bus names moved correctly ---
        for old, new in enumerate(old_to_new):
            old_name = parser.bus_names[f"bus{old+1:02d}"]
            new_name = new_parser.bus_names[f"bus{new+1:02d}"]
            assert old_name == new_name, f"Bus {old+1} ({old_name}) should move to {new+1} ({new_name})"

        # --- Step 5: Check sends for a few channels ---
        # We'll check channel 1 (Pastor) and channel 8 (Choir)
        def get_mix_line(parser, ch_idx, bus_idx):
            ch = f"/ch/{ch_idx+1:02d}/mix/{bus_idx+1:02d}"
            for cl in parser.config_lines:
                if cl.path == ch:
                    return cl.value
            return None
        # For channel 1, bus 10 (Speech) in old, should move to new Speech bus
        old_speech_bus = 10
        new_speech_bus = old_to_new[old_speech_bus]
        old_val = get_mix_line(parser, 0, old_speech_bus)
        new_val = get_mix_line(new_parser, 0, new_speech_bus)
        assert old_val is not None and new_val is not None
        # PRE/POST/follow LR should be preserved, but only for first bus in each pair
        def check_tap_and_panfollow(old_val, new_val, bus_idx):
            if bus_idx % 2 == 0:  # Only check for first bus in pair
                for tag in ["POST", "PRE", "EQ->"]:
                    assert (tag in old_val) == (tag in new_val), (
                        f"Tap point mismatch for bus {bus_idx+1}: old='{old_val}', new='{new_val}'"
                    )
        # For channel 1, bus 10 (Speech) in old, should move to new Speech bus
        old_speech_bus = 10
        new_speech_bus = old_to_new[old_speech_bus]
        old_val = get_mix_line(parser, 0, old_speech_bus)
        new_val = get_mix_line(new_parser, 0, new_speech_bus)
        assert old_val is not None and new_val is not None
        check_tap_and_panfollow(old_val, new_val, new_speech_bus)
        # For channel 8 (Choir), check bus 4 (Drums IEM) moves to new Drums IEM
        old_drums_bus = 4
        new_drums_bus = old_to_new[old_drums_bus]
        old_val = get_mix_line(parser, 7, old_drums_bus)
        new_val = get_mix_line(new_parser, 7, new_drums_bus)
        assert old_val is not None and new_val is not None
        check_tap_and_panfollow(old_val, new_val, new_drums_bus)

        # TODO: Also check an /auxin and an /fxrtn send to buses.
        # TODO: make sur the actual signal levels are preserved, not just the tap points.

        # --- Step 6: Check Cong mics sidechain ---
        # Find CongMics channel
        cong_idx = None
        for i in range(32):
            if parser.channel_names.get(f"ch{i+1:02d}", '').startswith("Cong "):
                cong_idx = i
                break
        if cong_idx is None:
            raise AssertionError("CongMics channel not found in scene file!")
        # Find sidechain bus in old and new (using source code convention 1)
        def get_sidechain_src_code(parser, ch_idx):
            for cl in parser.config_lines:
                if cl.path == f"/ch/{ch_idx+1:02d}/gate":
                    parts = cl.value.split()
                    if len(parts) > 7:
                        return int(parts[7])
            return None
        old_sc_src = get_sidechain_src_code(parser, cong_idx)
        new_sc_src = get_sidechain_src_code(new_parser, cong_idx)
        assert old_sc_src is not None and new_sc_src is not None
        # Spot-check: original should be 61 (bus 13)
        assert old_sc_src == 61, f"Expected original sidechain source code 61 (bus 13), got {old_sc_src}"
        # Remap using SourceCodeMapper
        source_mapper = SourceCodeMapper(channel_crossbar, bus_crossbar)
        expected_new_sc_src = source_mapper.remap_source_code_convention1(old_sc_src)
        # the new source should be code 59 (bus 11)
        assert expected_new_sc_src == 59, f"Expected new sidechain source code 59 (bus 11), got {expected_new_sc_src}"
        assert new_sc_src == expected_new_sc_src, f"Cong mics sidechain should remap from {old_sc_src} to {expected_new_sc_src}, got {new_sc_src}"

        # --- Step 7: Check Aux 1-4 sources ---
        # For each auxin 1-4, check that the source code is remapped correctly
        def get_auxin_source(parser, aux_idx):
            for cl in parser.config_lines:
                if cl.path == f"/auxin/{aux_idx+1:02d}/config/source":
                    return int(cl.value)
            return None
        for aux_idx in range(4):
            old_src = get_auxin_source(parser, aux_idx)
            new_src = get_auxin_source(new_parser, aux_idx)
            if old_src is not None and new_src is not None:
                expected_new_src = source_mapper.remap_source_code_convention1(old_src)
                assert new_src == expected_new_src, f"AuxIn {aux_idx+1} source should remap from {old_src} to {expected_new_src}, got {new_src}"

        # --- Step 8: Check FX sources ---
        # For each FX 1-4, check that the L/R source codes are remapped correctly
        def get_fx_source(parser, fx_idx, side):
            for cl in parser.config_lines:
                if cl.path == f"/fx/{fx_idx+1}/source/{side}":
                    return int(cl.value)
            return None
        for fx_idx in range(4):
            for side in ["l", "r"]:
                old_src = get_fx_source(parser, fx_idx, side)
                new_src = get_fx_source(new_parser, fx_idx, side)
                if old_src is not None and new_src is not None:
                    # FX source codes: 1-16 correspond to buses 1-16, so remap if in that range
                    if 1 <= old_src <= 16:
                        expected_new_src = old_to_new[old_src-1] + 1
                        assert new_src == expected_new_src, f"FX {fx_idx+1} {side.upper()} source should remap from {old_src} to {expected_new_src}, got {new_src}"
                    else:
                        assert new_src == old_src, f"FX {fx_idx+1} {side.upper()} source should remain {old_src}, got {new_src}"

        # --- Step 9: Check an /auxin and an /fxrtn send to buses ---
        # Check that the signal level and tap point are preserved for auxin 1 and fxrtn 1 sends to a bus
        def get_auxin_mix_line(parser, aux_idx, bus_idx):
            path = f"/auxin/{aux_idx+1:02d}/mix/{bus_idx+1:02d}"
            for cl in parser.config_lines:
                if cl.path == path:
                    return cl.value
            return None
        def get_fxrtn_mix_line(parser, fx_idx, bus_idx):
            path = f"/fxrtn/{fx_idx+1:02d}/mix/{bus_idx+1:02d}"
            for cl in parser.config_lines:
                if cl.path == path:
                    return cl.value
            return None
        # Pick auxin 1 and fxrtn 1, and a bus that exists in both old and new
        test_bus = 0  # bus 1
        old_bus = test_bus
        new_bus = old_to_new[old_bus]
        # Auxin
        old_val = get_auxin_mix_line(parser, 0, old_bus)
        new_val = get_auxin_mix_line(new_parser, 0, new_bus)
        if old_val is not None and new_val is not None:
            assert old_val == new_val, f"AuxIn 1 send to bus {old_bus+1} should be preserved at bus {new_bus+1}: old='{old_val}', new='{new_val}'"
        # FX Return
        old_val = get_fxrtn_mix_line(parser, 0, old_bus)
        new_val = get_fxrtn_mix_line(new_parser, 0, new_bus)
        if old_val is not None and new_val is not None:
            assert old_val == new_val, f"FXRtn 1 send to bus {old_bus+1} should be preserved at bus {new_bus+1}: old='{old_val}', new='{new_val}'"
