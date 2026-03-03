"""Tests for the CLI module."""

import os
import sys

import pytest

from cli.main import main, build_parser


SAMPLE_VCD = """\
$date Mon Jan 01 00:00:00 2024 $end
$version Test $end
$timescale 1ns $end
$scope module top $end
$var wire 1 ! clk $end
$var wire 1 " data $end
$upscope $end
$enddefinitions $end
$dumpvars
0!
0"
$end
#0
0!
0"
#5
1!
#10
0!
1"
#15
1!
#20
0!
0"
#25
1!
#30
0!
#35
1!
#40
0!
"""


@pytest.fixture
def vcd_file(tmp_path):
    """Create a temporary VCD file."""
    filepath = tmp_path / "test.vcd"
    filepath.write_text(SAMPLE_VCD)
    return str(filepath)


class TestCLI:
    """Tests for CLI interface."""

    def test_missing_vcd_file(self):
        """Test error when VCD file doesn't exist."""
        result = main(["--vcd", "/nonexistent/file.vcd"])
        assert result == 1

    def test_basic_run(self, vcd_file, capsys):
        """Test basic CLI execution."""
        result = main(["--vcd", vcd_file, "--no-color"])
        assert result == 0
        captured = capsys.readouterr()
        assert "FPGA Debug Agent" in captured.out

    def test_json_export(self, vcd_file, tmp_path):
        """Test CLI with JSON export."""
        json_output = str(tmp_path / "report.json")
        result = main([
            "--vcd", vcd_file,
            "--json-output", json_output,
            "--no-color"
        ])
        assert result == 0
        assert os.path.isfile(json_output)

    def test_custom_thresholds(self, vcd_file):
        """Test CLI with custom thresholds."""
        result = main([
            "--vcd", vcd_file,
            "--glitch-threshold", "10",
            "--stuck-threshold", "200",
            "--no-color"
        ])
        assert result == 0

    def test_parser_arguments(self):
        """Test that argument parser has expected arguments."""
        parser = build_parser()
        args = parser.parse_args(["--vcd", "test.vcd"])
        assert args.vcd == "test.vcd"
        assert args.clock == "auto"
        assert args.glitch_threshold == 5
