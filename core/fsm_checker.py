"""
FSM (Finite State Machine) Analysis Module.

Tracks state signal transitions, detects illegal transitions,
stuck states, and unreachable states from observed data.
"""

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from core.vcd_parser import VCDData
from core.clock_detector import ClockInfo

logger = logging.getLogger(__name__)


@dataclass
class FSMIssue:
    """Represents a detected FSM issue."""
    issue_type: str  # 'illegal_transition', 'stuck_state', 'unreachable_state'
    signal_name: str
    timestamp: int
    from_state: str
    to_state: str
    description: str
    severity: str  # 'HIGH', 'MEDIUM', 'LOW'


@dataclass
class FSMProfile:
    """Profile of an observed FSM."""
    signal_name: str
    states_observed: Set[str] = field(default_factory=set)
    transitions_observed: Set[Tuple[str, str]] = field(default_factory=set)
    state_durations: Dict[str, List[int]] = field(default_factory=dict)
    transition_count: int = 0


class FSMChecker:
    """
    Analyzes FSM signals in VCD data.

    Detects:
    - Illegal state transitions (based on observed transition patterns)
    - Stuck states (state remains unchanged for too long)
    - Unreachable states (defined but never observed)
    """

    # Common FSM state signal name patterns
    STATE_PATTERNS = ('state', 'fsm', 'cs', 'ns', 'current_state', 'next_state')

    def __init__(
        self,
        stuck_threshold: int = 100,
        clock_info: Optional[ClockInfo] = None,
        expected_states: Optional[Set[str]] = None
    ) -> None:
        """
        Args:
            stuck_threshold: Number of time units without state change to
                             consider a state as stuck.
            clock_info: Optional clock information.
            expected_states: Optional set of expected states for unreachable
                             state detection.
        """
        self._stuck_threshold = stuck_threshold
        self._clock_info = clock_info
        self._expected_states = expected_states or set()

    def set_clock(self, clock_info: ClockInfo) -> None:
        """Set clock information."""
        self._clock_info = clock_info

    def analyze(self, vcd_data: VCDData) -> Tuple[List[FSMIssue], List[FSMProfile]]:
        """
        Run FSM analysis on all potential state signals.

        Args:
            vcd_data: Parsed VCD data.

        Returns:
            Tuple of (issues list, FSM profiles list).
        """
        logger.info("Starting FSM analysis")
        issues: List[FSMIssue] = []
        profiles: List[FSMProfile] = []

        state_signals = self._find_state_signals(vcd_data)
        if not state_signals:
            logger.info("No FSM state signals detected")
            return issues, profiles

        logger.info("Found %d potential FSM signal(s)", len(state_signals))

        for identifier in state_signals:
            signal = vcd_data.signals[identifier]
            full_name = (
                f"{signal.scope}.{signal.name}" if signal.scope else signal.name
            )
            transitions = vcd_data.get_transitions(identifier)

            profile = self._build_profile(full_name, transitions)
            profiles.append(profile)

            issues.extend(self._check_illegal_transitions(profile, transitions))
            issues.extend(self._check_stuck_states(full_name, transitions))
            issues.extend(self._check_unreachable_states(profile))

        logger.info("FSM analysis found %d issue(s)", len(issues))
        return issues, profiles

    def _find_state_signals(self, vcd_data: VCDData) -> List[str]:
        """Identify signals that are likely FSM state signals."""
        state_ids: List[str] = []
        for identifier, signal in vcd_data.signals.items():
            name_lower = signal.name.lower()
            if any(pat in name_lower for pat in self.STATE_PATTERNS):
                state_ids.append(identifier)
        return state_ids

    def _build_profile(
        self, signal_name: str, transitions: List[Tuple[int, str]]
    ) -> FSMProfile:
        """Build an FSM profile from observed transitions."""
        profile = FSMProfile(signal_name=signal_name)

        if not transitions:
            return profile

        prev_state = transitions[0][1]
        prev_time = transitions[0][0]
        profile.states_observed.add(prev_state)

        for ts, val in transitions[1:]:
            profile.states_observed.add(val)
            if val != prev_state:
                profile.transitions_observed.add((prev_state, val))
                profile.transition_count += 1

                # Track state durations
                duration = ts - prev_time
                if prev_state not in profile.state_durations:
                    profile.state_durations[prev_state] = []
                profile.state_durations[prev_state].append(duration)

                prev_state = val
                prev_time = ts

        return profile

    def _check_illegal_transitions(
        self, profile: FSMProfile, transitions: List[Tuple[int, str]]
    ) -> List[FSMIssue]:
        """
        Detect potentially illegal transitions.

        Uses a heuristic: if a transition is seen only once while other
        transitions from the same source state are seen multiple times,
        it may be illegal.
        """
        issues: List[FSMIssue] = []

        if len(transitions) < 2:
            return issues

        # Count transition frequency
        trans_counter: Counter = Counter()
        prev_state = transitions[0][1]

        for ts, val in transitions[1:]:
            if val != prev_state:
                trans_counter[(prev_state, val)] += 1
                prev_state = val

        # Find transitions that are rare (potential illegal transitions)
        total_transitions = sum(trans_counter.values())
        if total_transitions < 5:
            return issues  # Not enough data to judge

        prev_state = transitions[0][1]
        for ts, val in transitions[1:]:
            if val != prev_state:
                count = trans_counter.get((prev_state, val), 0)
                # If this transition represents less than 5% of total transitions
                # and has been seen very rarely, flag it
                if count == 1 and total_transitions > 10:
                    issues.append(FSMIssue(
                        issue_type='illegal_transition',
                        signal_name=profile.signal_name,
                        timestamp=ts,
                        from_state=prev_state,
                        to_state=val,
                        description=(
                            f"Rare transition {prev_state} -> {val} "
                            f"(seen {count}/{total_transitions} times)"
                        ),
                        severity='HIGH'
                    ))
                prev_state = val

        return issues

    def _check_stuck_states(
        self, signal_name: str, transitions: List[Tuple[int, str]]
    ) -> List[FSMIssue]:
        """Detect states that remain unchanged for too long."""
        issues: List[FSMIssue] = []

        if len(transitions) < 2:
            return issues

        for i in range(1, len(transitions)):
            duration = transitions[i][0] - transitions[i - 1][0]
            if duration > self._stuck_threshold:
                issues.append(FSMIssue(
                    issue_type='stuck_state',
                    signal_name=signal_name,
                    timestamp=transitions[i - 1][0],
                    from_state=transitions[i - 1][1],
                    to_state=transitions[i - 1][1],
                    description=(
                        f"State {transitions[i - 1][1]} held for {duration} "
                        f"time units (threshold: {self._stuck_threshold})"
                    ),
                    severity='MEDIUM'
                ))

        return issues

    def _check_unreachable_states(
        self, profile: FSMProfile
    ) -> List[FSMIssue]:
        """Detect expected states that were never observed."""
        issues: List[FSMIssue] = []

        if not self._expected_states:
            return issues

        unreachable = self._expected_states - profile.states_observed
        for state in unreachable:
            issues.append(FSMIssue(
                issue_type='unreachable_state',
                signal_name=profile.signal_name,
                timestamp=0,
                from_state='',
                to_state=state,
                description=(
                    f"Expected state '{state}' was never observed "
                    f"in {profile.signal_name}"
                ),
                severity='LOW'
            ))

        return issues
