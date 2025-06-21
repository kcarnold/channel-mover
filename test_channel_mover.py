import pytest
from channel_mover import (
    Crossbar, ConfigLine, ChannelLink, SceneParser, 
    ChannelMapper, SceneGenerator, parse_cfgline
)


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
        
        from channel_mover import SourceCodeMapper
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
        
        from channel_mover import SourceCodeMapper
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
        
        from channel_mover import SourceCodeMapper
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
        
        from channel_mover import SourceCodeMapper
        mapper = SourceCodeMapper(channel_crossbar, bus_crossbar)
        
        # Test bus source codes (4-19 -> buses 1-16)
        assert mapper.remap_source_code_convention2(4) == 7   # Bus 1 -> Bus 4
        assert mapper.remap_source_code_convention2(5) == 0   # Unmapped bus -> OFF


# Run with: pytest test_channel_mover.py
