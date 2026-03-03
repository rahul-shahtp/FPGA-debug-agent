"""Tests for the VCD parser module."""

import os
import tempfile

import pytest

from core.vcd_parser import VCDParser, VCDData, SignalDefinition


SAMPLE_VCD = """\
$date
   Mon Jan 01 00:00:00 2024
$end
$version
   Test VCD
$end
$timescale
   1ns
$end
$scope module top $end
$var wire 1 ! clk $end
$var wire 1 " rst $end
$var wire 4 # data [3:0] $end
$upscope $end
$enddefinitions $end
$dumpvars
0!
0"
b0000 #
$end
#0
0!
0"
b0000 #
#5
1!
#10
0!
1"
#15
1!
b0001 #
#20
0!
b0010 #
#25
1!
#30
0!
0"
#35
1!
#40
0!
"""


@pytest.fixture
def vcd_file(tmp_path):
    """Create a temporary VCD file for testing."""
    filepath = tmp_path / "test.vcd"
    filepath.write_text(SAMPLE_VCD)
    return str(filepath)


@pytest.fixture
def parsed_data(vcd_file):
    """Parse the sample VCD file."""
    parser = VCDParser()
    return parser.parse(vcd_file)


class TestVCDParser:
    """Tests for VCDParser class."""

    def test_parse_signals(self, parsed_data):
        """Test that signals are correctly parsed."""
        assert len(parsed_data.signals) == 3
        assert '!' in parsed_data.signals
        assert '"' in parsed_data.signals
        assert '#' in parsed_data.signals

    def test_signal_names(self, parsed_data):
        """Test signal name extraction."""
        clk = parsed_data.signals['!']
        assert clk.name == 'clk'
        assert clk.scope == 'top'
        assert clk.width == 1

    def test_vector_signal(self, parsed_data):
        """Test vector signal parsing."""
        data = parsed_data.signals['#']
        assert data.name == 'data'
        assert data.width == 4

    def test_transitions(self, parsed_data):
        """Test that transitions are recorded."""
        clk_trans = parsed_data.get_transitions('!')
        assert len(clk_trans) > 0
        # First transition should be at time 0
        assert clk_trans[0][0] == 0

    def test_end_time(self, parsed_data):
        """Test end time detection."""
        assert parsed_data.end_time == 40

    def test_timescale(self, parsed_data):
        """Test timescale parsing."""
        assert '1ns' in parsed_data.timescale

    def test_get_signal_by_name(self, parsed_data):
        """Test signal lookup by name."""
        sig = parsed_data.get_signal_by_name('clk')
        assert sig is not None
        assert sig.identifier == '!'

    def test_get_signal_by_full_name(self, parsed_data):
        """Test signal lookup by full hierarchical name."""
        sig = parsed_data.get_signal_by_name('top.clk')
        assert sig is not None
        assert sig.identifier == '!'

    def test_get_signal_names(self, parsed_data):
        """Test getting all signal names."""
        names = parsed_data.get_signal_names()
        assert 'top.clk' in names
        assert 'top.rst' in names
        assert 'top.data' in names

    def test_file_not_found(self):
        """Test that FileNotFoundError is raised for missing files."""
        parser = VCDParser()
        with pytest.raises(FileNotFoundError):
            parser.parse("/nonexistent/file.vcd")

    def test_vector_transitions(self, parsed_data):
        """Test vector signal value changes."""
        data_trans = parsed_data.get_transitions('#')
        values = [v for _, v in data_trans]
        assert '0000' in values
        assert '0001' in values
        assert '0010' in values

    def test_scalar_transitions(self, parsed_data):
        """Test scalar signal value changes."""
        rst_trans = parsed_data.get_transitions('"')
        values = [v for _, v in rst_trans]
        assert '0' in values
        assert '1' in values
