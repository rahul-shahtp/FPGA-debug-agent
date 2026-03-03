"""Tests for the X/Z propagation detector module."""

import pytest

from core.vcd_parser import VCDData, SignalDefinition
from core.x_propagation import XPropagationDetector


def _make_vcd(signals_dict, transitions_dict):
    """Helper to build VCDData."""
    data = VCDData()
    data.signals = signals_dict
    data.transitions = transitions_dict
    return data


class TestXPropagationDetector:
    """Tests for XPropagationDetector class."""

    def test_detect_x_value(self):
        """Test detection of X values."""
        signals = {
            '!': SignalDefinition(
                identifier='!', name='sig', width=1,
                scope='top', var_type='wire'
            ),
        }
        trans = {'!': [(0, '0'), (10, 'x'), (20, '1')]}
        data = _make_vcd(signals, trans)

        detector = XPropagationDetector()
        events = detector.detect(data)

        x_events = [e for e in events if e.event_type == 'x_value']
        assert len(x_events) >= 1
        assert x_events[0].timestamp == 10

    def test_detect_z_value(self):
        """Test detection of Z values."""
        signals = {
            '!': SignalDefinition(
                identifier='!', name='sig', width=1,
                scope='top', var_type='wire'
            ),
        }
        trans = {'!': [(0, '0'), (10, 'z'), (20, '1')]}
        data = _make_vcd(signals, trans)

        detector = XPropagationDetector()
        events = detector.detect(data)

        z_events = [e for e in events if e.event_type == 'z_value']
        assert len(z_events) >= 1

    def test_no_xz_in_clean_signal(self):
        """Test no false positives for clean signals."""
        signals = {
            '!': SignalDefinition(
                identifier='!', name='sig', width=1,
                scope='top', var_type='wire'
            ),
        }
        trans = {'!': [(0, '0'), (10, '1'), (20, '0')]}
        data = _make_vcd(signals, trans)

        detector = XPropagationDetector()
        events = detector.detect(data)
        assert len(events) == 0

    def test_detect_propagation(self):
        """Test detection of X/Z propagation across signals."""
        signals = {
            '!': SignalDefinition(
                identifier='!', name='sig_a', width=1,
                scope='top', var_type='wire'
            ),
            '"': SignalDefinition(
                identifier='"', name='sig_b', width=1,
                scope='top', var_type='wire'
            ),
        }
        # Both signals go X within propagation window
        trans = {
            '!': [(0, '0'), (10, 'x'), (20, '1')],
            '"': [(0, '0'), (15, 'x'), (25, '1')],
        }
        data = _make_vcd(signals, trans)

        detector = XPropagationDetector(propagation_window=10)
        events = detector.detect(data)

        prop_events = [e for e in events if e.event_type == 'x_propagation']
        assert len(prop_events) >= 1

    def test_vector_x_detection(self):
        """Test X detection in vector signals."""
        signals = {
            '#': SignalDefinition(
                identifier='#', name='bus', width=4,
                scope='top', var_type='wire'
            ),
        }
        trans = {'#': [(0, '0000'), (10, 'xx00'), (20, '1111')]}
        data = _make_vcd(signals, trans)

        detector = XPropagationDetector()
        events = detector.detect(data)

        x_events = [e for e in events if e.event_type == 'x_value']
        assert len(x_events) >= 1
