"""Tests for the reasoning engine and report generator."""

import json
import os
import tempfile

import pytest

from agent.reasoning_engine import ReasoningEngine, AnalysisResult, Severity
from agent.report_generator import ReportGenerator


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
$var wire 1 # data $end
$upscope $end
$enddefinitions $end
$dumpvars
0!
0"
0#
$end
#0
0!
0"
0#
#5
1!
#10
0!
1"
#15
1!
#20
0!
1#
#25
1!
#30
0!
0#
#35
1!
0"
#40
0!
#45
1!
#50
0!
"""


@pytest.fixture
def vcd_file(tmp_path):
    """Create a temporary VCD file."""
    filepath = tmp_path / "test.vcd"
    filepath.write_text(SAMPLE_VCD)
    return str(filepath)


class TestReasoningEngine:
    """Tests for ReasoningEngine class."""

    def test_basic_analysis(self, vcd_file):
        """Test that analysis runs without error."""
        engine = ReasoningEngine()
        result = engine.analyze(vcd_file)
        assert isinstance(result, AnalysisResult)
        assert result.vcd_file == vcd_file

    def test_clock_detected(self, vcd_file):
        """Test that a clock is detected."""
        engine = ReasoningEngine(clock_mode="auto")
        result = engine.analyze(vcd_file)
        assert result.clock_info is not None

    def test_summary_populated(self, vcd_file):
        """Test that summary is populated."""
        engine = ReasoningEngine()
        result = engine.analyze(vcd_file)
        assert isinstance(result.summary, dict)

    def test_severity_counts(self, vcd_file):
        """Test severity count properties."""
        engine = ReasoningEngine()
        result = engine.analyze(vcd_file)
        total = (
            result.high_severity_count +
            result.medium_severity_count +
            result.low_severity_count
        )
        assert total == result.total_issues


class TestReportGenerator:
    """Tests for ReportGenerator class."""

    def test_console_report(self, vcd_file):
        """Test console report generation."""
        engine = ReasoningEngine()
        result = engine.analyze(vcd_file)

        reporter = ReportGenerator(use_color=False)
        report = reporter.generate_console_report(result)
        assert "FPGA Debug Agent" in report
        assert "Summary" in report

    def test_json_report(self, vcd_file):
        """Test JSON report generation."""
        engine = ReasoningEngine()
        result = engine.analyze(vcd_file)

        reporter = ReportGenerator()
        json_str = reporter.generate_json_report(result)
        data = json.loads(json_str)

        assert "findings" in data
        assert "summary" in data
        assert data["vcd_file"] == vcd_file

    def test_json_export(self, vcd_file, tmp_path):
        """Test JSON export to file."""
        engine = ReasoningEngine()
        result = engine.analyze(vcd_file)

        reporter = ReportGenerator()
        output = str(tmp_path / "report.json")
        reporter.export_json(result, output)

        assert os.path.isfile(output)
        with open(output) as f:
            data = json.loads(f.read())
        assert "findings" in data
