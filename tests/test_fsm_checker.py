"""Tests for the FSM checker module."""

import pytest

from core.vcd_parser import VCDData, SignalDefinition
from core.fsm_checker import FSMChecker


def _make_vcd(signals_dict, transitions_dict):
    """Helper to build VCDData."""
    data = VCDData()
    data.signals = signals_dict
    data.transitions = transitions_dict
    return data


class TestFSMChecker:
    """Tests for FSMChecker class."""

    def test_find_state_signals(self):
        """Test that FSM state signals are identified by name."""
        signals = {
            '%': SignalDefinition(
                identifier='%', name='state', width=4,
                scope='top', var_type='wire'
            ),
        }
        trans = {
            '%': [(0, '0000'), (10, '0001'), (20, '0010'), (30, '0000')],
        }
        data = _make_vcd(signals, trans)

        checker = FSMChecker()
        issues, profiles = checker.analyze(data)
        assert len(profiles) >= 1
        assert profiles[0].signal_name == 'top.state'

    def test_detect_stuck_state(self):
        """Test detection of a stuck state."""
        signals = {
            '%': SignalDefinition(
                identifier='%', name='fsm_state', width=4,
                scope='top', var_type='wire'
            ),
        }
        # State stuck for 200 time units (threshold default=100)
        trans = {
            '%': [(0, '0000'), (200, '0001'), (210, '0010')],
        }
        data = _make_vcd(signals, trans)

        checker = FSMChecker(stuck_threshold=100)
        issues, _ = checker.analyze(data)

        stuck = [i for i in issues if i.issue_type == 'stuck_state']
        assert len(stuck) >= 1

    def test_no_stuck_for_normal_operation(self):
        """Test no false positives for normal FSM transitions."""
        signals = {
            '%': SignalDefinition(
                identifier='%', name='current_state', width=4,
                scope='top', var_type='wire'
            ),
        }
        trans = {
            '%': [(i * 10, f'000{i % 4}') for i in range(10)],
        }
        data = _make_vcd(signals, trans)

        checker = FSMChecker(stuck_threshold=100)
        issues, _ = checker.analyze(data)

        stuck = [i for i in issues if i.issue_type == 'stuck_state']
        assert len(stuck) == 0

    def test_detect_unreachable_states(self):
        """Test detection of expected states never observed."""
        signals = {
            '%': SignalDefinition(
                identifier='%', name='state', width=4,
                scope='top', var_type='wire'
            ),
        }
        trans = {
            '%': [(0, '00'), (10, '01'), (20, '00')],
        }
        data = _make_vcd(signals, trans)

        checker = FSMChecker(
            expected_states={'00', '01', '10', '11'}
        )
        issues, _ = checker.analyze(data)

        unreachable = [i for i in issues if i.issue_type == 'unreachable_state']
        assert len(unreachable) == 2  # '10' and '11'

    def test_no_fsm_signals(self):
        """Test when no FSM signals are present."""
        signals = {
            '!': SignalDefinition(
                identifier='!', name='data', width=1,
                scope='top', var_type='wire'
            ),
        }
        trans = {'!': [(0, '0'), (10, '1')]}
        data = _make_vcd(signals, trans)

        checker = FSMChecker()
        issues, profiles = checker.analyze(data)
        assert len(issues) == 0
        assert len(profiles) == 0
