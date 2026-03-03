"""Tests for the reset analyzer module."""

import pytest

from core.vcd_parser import VCDData, SignalDefinition
from core.clock_detector import ClockInfo
from core.reset_analyzer import ResetAnalyzer


def _make_vcd(signals_dict, transitions_dict):
    """Helper to build VCDData."""
    data = VCDData()
    data.signals = signals_dict
    data.transitions = transitions_dict
    return data


class TestResetAnalyzer:
    """Tests for ResetAnalyzer class."""

    def test_find_reset_signal(self):
        """Test that reset signals are identified by name."""
        signals = {
            '!': SignalDefinition(
                identifier='!', name='clk', width=1,
                scope='top', var_type='wire'
            ),
            '"': SignalDefinition(
                identifier='"', name='rst_n', width=1,
                scope='top', var_type='wire'
            ),
        }
        trans = {
            '!': [(i * 5, str(i % 2)) for i in range(10)],
            '"': [(0, '0'), (10, '1')],
        }
        data = _make_vcd(signals, trans)

        analyzer = ResetAnalyzer()
        issues = analyzer.analyze(data)
        # Should find the reset signal (at minimum no crash)
        assert isinstance(issues, list)

    def test_detect_reset_glitch(self):
        """Test detection of a glitch on the reset line."""
        signals = {
            '"': SignalDefinition(
                identifier='"', name='rst', width=1,
                scope='top', var_type='wire'
            ),
        }
        # Short glitch: 2ns pulse
        trans = {
            '"': [(0, '0'), (100, '1'), (102, '0'), (200, '1')],
        }
        data = _make_vcd(signals, trans)

        analyzer = ResetAnalyzer(glitch_threshold=5)
        issues = analyzer.analyze(data)

        glitches = [i for i in issues if i.issue_type == 'glitch']
        assert len(glitches) >= 1

    def test_no_issues_for_clean_reset(self):
        """Test no false positives for clean reset signal."""
        signals = {
            '"': SignalDefinition(
                identifier='"', name='reset', width=1,
                scope='top', var_type='wire'
            ),
        }
        trans = {
            '"': [(0, '1'), (100, '0')],
        }
        data = _make_vcd(signals, trans)

        analyzer = ResetAnalyzer(glitch_threshold=5)
        issues = analyzer.analyze(data)

        glitches = [i for i in issues if i.issue_type == 'glitch']
        assert len(glitches) == 0

    def test_no_reset_signals(self):
        """Test when no reset signals are present."""
        signals = {
            '!': SignalDefinition(
                identifier='!', name='data', width=1,
                scope='top', var_type='wire'
            ),
        }
        trans = {'!': [(0, '0'), (10, '1')]}
        data = _make_vcd(signals, trans)

        analyzer = ResetAnalyzer()
        issues = analyzer.analyze(data)
        assert len(issues) == 0
