"""
Reset Analysis Module.

Detects reset signals, analyzes deassertion timing, detects reset glitches,
and checks whether registers properly reset.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core.vcd_parser import VCDData
from core.clock_detector import ClockInfo

logger = logging.getLogger(__name__)


@dataclass
class ResetIssue:
    """Represents a detected reset-related issue."""
    issue_type: str  # 'glitch', 'bad_deassertion', 'register_not_reset'
    signal_name: str
    timestamp: int
    description: str
    severity: str  # 'HIGH', 'MEDIUM', 'LOW'


class ResetAnalyzer:
    """
    Analyzes reset signals in VCD data.

    Checks for:
    - Reset signal identification (signals named *rst*, *reset*)
    - Reset glitches (short pulses on reset line)
    - Deassertion timing relative to clock edges
    - Registers not properly resetting
    """

    # Common reset signal name patterns
    RESET_PATTERNS = ('rst', 'reset', 'rstn', 'rst_n', 'reset_n', 'nrst')

    def __init__(
        self,
        glitch_threshold: int = 5,
        clock_info: Optional[ClockInfo] = None
    ) -> None:
        """
        Args:
            glitch_threshold: Minimum pulse width (in time units) below which
                              a pulse is considered a glitch.
            clock_info: Optional clock information for timing analysis.
        """
        self._glitch_threshold = glitch_threshold
        self._clock_info = clock_info

    def set_clock(self, clock_info: ClockInfo) -> None:
        """Set clock information for timing-relative analysis."""
        self._clock_info = clock_info

    def analyze(self, vcd_data: VCDData) -> List[ResetIssue]:
        """
        Run all reset analysis checks.

        Args:
            vcd_data: Parsed VCD data.

        Returns:
            List of detected reset issues.
        """
        logger.info("Starting reset analysis")
        issues: List[ResetIssue] = []

        reset_signals = self._find_reset_signals(vcd_data)
        if not reset_signals:
            logger.info("No reset signals detected")
            return issues

        logger.info("Found %d reset signal(s)", len(reset_signals))

        for identifier in reset_signals:
            signal = vcd_data.signals[identifier]
            full_name = (
                f"{signal.scope}.{signal.name}" if signal.scope else signal.name
            )
            transitions = vcd_data.get_transitions(identifier)

            issues.extend(self._check_glitches(full_name, transitions))
            issues.extend(
                self._check_deassertion_timing(full_name, transitions)
            )

        issues.extend(
            self._check_registers_reset(vcd_data, reset_signals)
        )

        logger.info("Reset analysis found %d issue(s)", len(issues))
        return issues

    def _find_reset_signals(self, vcd_data: VCDData) -> List[str]:
        """Identify signals that are likely reset signals."""
        reset_ids: List[str] = []
        for identifier, signal in vcd_data.signals.items():
            name_lower = signal.name.lower()
            if any(pat in name_lower for pat in self.RESET_PATTERNS):
                if signal.width == 1:
                    reset_ids.append(identifier)
        return reset_ids

    def _check_glitches(
        self, signal_name: str, transitions: List[Tuple[int, str]]
    ) -> List[ResetIssue]:
        """Check for glitches on the reset signal."""
        issues: List[ResetIssue] = []
        for i in range(1, len(transitions)):
            pulse_width = transitions[i][0] - transitions[i - 1][0]
            if 0 < pulse_width < self._glitch_threshold:
                issues.append(ResetIssue(
                    issue_type='glitch',
                    signal_name=signal_name,
                    timestamp=transitions[i - 1][0],
                    description=(
                        f"Reset glitch detected: pulse width {pulse_width} "
                        f"(threshold: {self._glitch_threshold})"
                    ),
                    severity='HIGH'
                ))
        return issues

    def _check_deassertion_timing(
        self, signal_name: str, transitions: List[Tuple[int, str]]
    ) -> List[ResetIssue]:
        """Check reset deassertion timing relative to clock edges."""
        issues: List[ResetIssue] = []
        if not self._clock_info:
            return issues

        period = self._clock_info.period
        if period == 0:
            return issues

        for i in range(1, len(transitions)):
            ts = transitions[i][0]
            val = transitions[i][1]

            # Deassertion: active-low reset going high, or active-high going low
            if val in ('1', '0'):
                # Check if deassertion happens near clock edge
                offset = ts % period
                # If deassertion is too close to clock edge (within 10% of period)
                edge_proximity = min(offset, period - offset)
                margin = max(1, int(period * 0.1))
                if edge_proximity < margin:
                    issues.append(ResetIssue(
                        issue_type='bad_deassertion',
                        signal_name=signal_name,
                        timestamp=ts,
                        description=(
                            f"Reset deassertion at t={ts} is within {edge_proximity} "
                            f"time units of clock edge (margin: {margin})"
                        ),
                        severity='MEDIUM'
                    ))
        return issues

    def _check_registers_reset(
        self,
        vcd_data: VCDData,
        reset_ids: List[str]
    ) -> List[ResetIssue]:
        """Check if registers properly reset when reset is asserted."""
        issues: List[ResetIssue] = []

        # Find reset assertion periods
        for reset_id in reset_ids:
            transitions = vcd_data.get_transitions(reset_id)
            reset_signal = vcd_data.signals[reset_id]
            reset_name = (
                f"{reset_signal.scope}.{reset_signal.name}"
                if reset_signal.scope else reset_signal.name
            )

            # Determine active-level (active-low if name contains 'n')
            is_active_low = any(
                p in reset_signal.name.lower()
                for p in ('_n', 'n_', 'rstn', 'nrst')
            )

            # Find periods where reset is active
            reset_active_periods = self._find_active_periods(
                transitions, is_active_low
            )

            # Check other single-bit signals during reset
            for sig_id, signal in vcd_data.signals.items():
                if sig_id in reset_ids:
                    continue
                if signal.width != 1:
                    continue

                sig_transitions = vcd_data.get_transitions(sig_id)
                sig_name = (
                    f"{signal.scope}.{signal.name}"
                    if signal.scope else signal.name
                )

                for start, end in reset_active_periods:
                    # Check if signal changes during reset (which is unexpected)
                    changes_during_reset = [
                        (t, v) for t, v in sig_transitions
                        if start < t < end
                    ]
                    if len(changes_during_reset) > 1:
                        issues.append(ResetIssue(
                            issue_type='register_not_reset',
                            signal_name=sig_name,
                            timestamp=start,
                            description=(
                                f"Signal {sig_name} has {len(changes_during_reset)} "
                                f"transitions during reset active period "
                                f"[{start}, {end}]"
                            ),
                            severity='HIGH'
                        ))
        return issues

    def _find_active_periods(
        self,
        transitions: List[Tuple[int, str]],
        is_active_low: bool
    ) -> List[Tuple[int, int]]:
        """Find periods where reset is active."""
        active_value = '0' if is_active_low else '1'
        periods: List[Tuple[int, int]] = []
        active_start: Optional[int] = None

        for ts, val in transitions:
            if val == active_value and active_start is None:
                active_start = ts
            elif val != active_value and active_start is not None:
                periods.append((active_start, ts))
                active_start = None

        return periods
