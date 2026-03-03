"""Tests for the multi-driver detector module."""

import pytest

from core.vcd_parser import VCDData, SignalDefinition
from core.multi_driver_detector import MultiDriverDetector


def _make_vcd(signals_dict, transitions_dict):
    """Helper to build VCDData."""
    data = VCDData()
    data.signals = signals_dict
    data.transitions = transitions_dict
    return data


class TestMultiDriverDetector:
    """Tests for MultiDriverDetector class."""

    def test_detect_rapid_toggles(self):
        """Test detection of rapid toggles suggesting multi-driver."""
        signals = {
            '!': SignalDefinition(
                identifier='!', name='bus_line', width=1,
                scope='top', var_type='wire'
            ),
        }
        # 5 toggles within 3 time units
        trans = {
            '!': [
                (100, '0'), (101, '1'), (102, '0'),
                (103, '1'), (104, '0'), (200, '1')
            ],
        }
        data = _make_vcd(signals, trans)

        detector = MultiDriverDetector(window_size=5, toggle_threshold=3)
        events = detector.detect(data)

        assert len(events) >= 1
        assert events[0].signal_name == 'top.bus_line'

    def test_no_multi_driver_for_normal_signal(self):
        """Test no false positives on a normal signal."""
        signals = {
            '!': SignalDefinition(
                identifier='!', name='sig', width=1,
                scope='top', var_type='wire'
            ),
        }
        trans = {
            '!': [(0, '0'), (50, '1'), (100, '0'), (150, '1')],
        }
        data = _make_vcd(signals, trans)

        detector = MultiDriverDetector(window_size=5, toggle_threshold=3)
        events = detector.detect(data)
        assert len(events) == 0

    def test_too_few_transitions(self):
        """Test signals with too few transitions are skipped."""
        signals = {
            '!': SignalDefinition(
                identifier='!', name='sig', width=1,
                scope='top', var_type='wire'
            ),
        }
        trans = {'!': [(0, '0'), (10, '1')]}
        data = _make_vcd(signals, trans)

        detector = MultiDriverDetector(window_size=5, toggle_threshold=3)
        events = detector.detect(data)
        assert len(events) == 0
