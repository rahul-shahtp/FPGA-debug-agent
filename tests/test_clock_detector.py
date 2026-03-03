"""Tests for the clock detector module."""

import pytest

from core.vcd_parser import VCDParser, VCDData, SignalDefinition
from core.clock_detector import ClockDetector, ClockInfo


def _make_vcd_with_clock(transitions, signals=None):
    """Helper to build VCDData with specific transitions."""
    data = VCDData()
    if signals is None:
        signals = {
            '!': SignalDefinition(
                identifier='!', name='clk', width=1,
                scope='top', var_type='wire'
            )
        }
    data.signals = signals
    data.transitions = {k: list(v) for k, v in transitions.items()}
    return data


class TestClockDetector:
    """Tests for ClockDetector class."""

    def test_detect_perfect_clock(self):
        """Test detection of a perfect 50% duty cycle clock."""
        # 10ns period clock: toggles at 0, 5, 10, 15, 20, ...
        trans = [(i * 5, str(i % 2)) for i in range(20)]
        data = _make_vcd_with_clock({'!': trans})

        detector = ClockDetector()
        clocks = detector.detect(data)

        assert len(clocks) >= 1
        clk = clocks[0]
        assert clk.period == 10
        assert abs(clk.duty_cycle - 0.5) < 0.1
        assert clk.stability > 0.9

    def test_no_clock_in_static_signal(self):
        """Test that a static signal is not detected as clock."""
        trans = [(0, '0'), (100, '1')]
        data = _make_vcd_with_clock({'!': trans})

        detector = ClockDetector()
        clocks = detector.detect(data)
        assert len(clocks) == 0

    def test_get_primary_clock(self):
        """Test getting the primary (most stable) clock."""
        trans = [(i * 5, str(i % 2)) for i in range(20)]
        data = _make_vcd_with_clock({'!': trans})

        detector = ClockDetector()
        primary = detector.get_primary_clock(data)

        assert primary is not None
        assert primary.signal_name == 'top.clk'

    def test_no_primary_clock(self):
        """Test when no clock is found."""
        data = VCDData()
        detector = ClockDetector()
        assert detector.get_primary_clock(data) is None

    def test_multi_bit_signal_ignored(self):
        """Test that multi-bit signals are not considered as clocks."""
        signals = {
            '#': SignalDefinition(
                identifier='#', name='bus', width=4,
                scope='top', var_type='wire'
            )
        }
        trans = [(i * 5, str(i % 2)) for i in range(20)]
        data = _make_vcd_with_clock({'#': trans}, signals)

        detector = ClockDetector()
        clocks = detector.detect(data)
        assert len(clocks) == 0

    def test_unstable_signal_not_clock(self):
        """Test that an unstable signal with varying periods isn't detected."""
        # Irregular transitions
        trans = [
            (0, '0'), (5, '1'), (10, '0'), (100, '1'),
            (105, '0'), (200, '1')
        ]
        data = _make_vcd_with_clock({'!': trans})

        detector = ClockDetector(stability_threshold=0.9)
        clocks = detector.detect(data)
        assert len(clocks) == 0
