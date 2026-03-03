"""Tests for the glitch detector module."""

import pytest

from core.vcd_parser import VCDData, SignalDefinition
from core.clock_detector import ClockInfo
from core.glitch_detector import GlitchDetector


def _make_vcd(signals_dict, transitions_dict):
    """Helper to build VCDData."""
    data = VCDData()
    data.signals = signals_dict
    data.transitions = transitions_dict
    return data


class TestGlitchDetector:
    """Tests for GlitchDetector class."""

    def test_detect_short_pulse(self):
        """Test detection of a pulse shorter than threshold."""
        signals = {
            '!': SignalDefinition(
                identifier='!', name='sig', width=1,
                scope='top', var_type='wire'
            )
        }
        # Glitch: 2ns pulse at time 100
        trans = [
            (0, '0'), (100, '1'), (102, '0'), (200, '1')
        ]
        data = _make_vcd(signals, {'!': trans})

        detector = GlitchDetector(glitch_threshold=5)
        events = detector.detect(data)

        glitches = [e for e in events if e.event_type == 'glitch']
        assert len(glitches) >= 1
        assert glitches[0].timestamp == 100
        assert glitches[0].pulse_width == 2

    def test_no_glitch_for_normal_signal(self):
        """Test no false positives on a normal signal."""
        signals = {
            '!': SignalDefinition(
                identifier='!', name='sig', width=1,
                scope='top', var_type='wire'
            )
        }
        trans = [
            (0, '0'), (50, '1'), (100, '0'), (150, '1')
        ]
        data = _make_vcd(signals, {'!': trans})

        detector = GlitchDetector(glitch_threshold=5)
        events = detector.detect(data)

        glitches = [e for e in events if e.event_type == 'glitch']
        assert len(glitches) == 0

    def test_detect_multi_toggle(self):
        """Test detection of multiple toggles within one clock cycle."""
        signals = {
            '!': SignalDefinition(
                identifier='!', name='sig', width=1,
                scope='top', var_type='wire'
            )
        }
        # 3 transitions in one clock cycle (period=10)
        trans = [
            (0, '0'), (1, '1'), (2, '0'), (3, '1'), (50, '0')
        ]
        data = _make_vcd(signals, {'!': trans})

        clock_info = ClockInfo(
            signal_name='clk', identifier='c', frequency=0.1,
            period=10, duty_cycle=0.5, stability=1.0,
            edge_count=20, first_edge=0, last_edge=200
        )
        detector = GlitchDetector(glitch_threshold=5, clock_info=clock_info)
        events = detector.detect(data)

        multi_toggles = [e for e in events if e.event_type == 'multi_toggle']
        assert len(multi_toggles) >= 1

    def test_no_multi_toggle_without_clock(self):
        """Test that multi-toggle detection requires clock info."""
        signals = {
            '!': SignalDefinition(
                identifier='!', name='sig', width=1,
                scope='top', var_type='wire'
            )
        }
        trans = [(0, '0'), (1, '1'), (2, '0'), (3, '1')]
        data = _make_vcd(signals, {'!': trans})

        detector = GlitchDetector(glitch_threshold=5)
        events = detector.detect(data)

        multi_toggles = [e for e in events if e.event_type == 'multi_toggle']
        assert len(multi_toggles) == 0
