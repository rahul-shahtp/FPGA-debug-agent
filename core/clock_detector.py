"""
Automatic Clock Detection Module.

Identifies potential clock signals by analyzing signal periodicity,
frequency, duty cycle, and stability.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core.vcd_parser import VCDData

logger = logging.getLogger(__name__)


@dataclass
class ClockInfo:
    """Information about a detected clock signal."""
    signal_name: str
    identifier: str
    frequency: float
    period: int
    duty_cycle: float
    stability: float  # 0.0 to 1.0
    edge_count: int
    first_edge: int
    last_edge: int


class ClockDetector:
    """
    Detects clock signals in VCD data by analyzing signal periodicity.

    A clock signal is characterized by:
    - Regular toggling between two values (0 and 1)
    - Consistent period between transitions
    - High stability (low jitter)
    """

    def __init__(self, stability_threshold: float = 0.8) -> None:
        """
        Args:
            stability_threshold: Minimum stability score to consider
                                 a signal as a clock (0.0 to 1.0).
        """
        self._stability_threshold = stability_threshold

    def detect(self, vcd_data: VCDData) -> List[ClockInfo]:
        """
        Detect all potential clock signals in the VCD data.

        Args:
            vcd_data: Parsed VCD data.

        Returns:
            List of ClockInfo objects for detected clocks,
            sorted by stability (best first).
        """
        logger.info("Starting automatic clock detection")
        candidates: List[ClockInfo] = []

        for identifier, signal in vcd_data.signals.items():
            if signal.width != 1:
                continue  # Clocks are single-bit signals

            transitions = vcd_data.get_transitions(identifier)
            if len(transitions) < 4:
                continue  # Need enough transitions to analyze

            clock_info = self._analyze_signal(
                identifier, signal, transitions
            )
            if clock_info and clock_info.stability >= self._stability_threshold:
                candidates.append(clock_info)

        candidates.sort(key=lambda c: c.stability, reverse=True)
        logger.info("Detected %d clock candidate(s)", len(candidates))
        for c in candidates:
            logger.info(
                "  Clock: %s (period=%d, stability=%.2f, duty=%.1f%%)",
                c.signal_name, c.period, c.stability, c.duty_cycle * 100
            )
        return candidates

    def get_primary_clock(self, vcd_data: VCDData) -> Optional[ClockInfo]:
        """
        Detect and return the primary (most stable) clock signal.

        Args:
            vcd_data: Parsed VCD data.

        Returns:
            ClockInfo for the primary clock, or None if no clock is found.
        """
        clocks = self.detect(vcd_data)
        return clocks[0] if clocks else None

    def _analyze_signal(
        self, identifier: str, signal, transitions: List[Tuple[int, str]]
    ) -> Optional[ClockInfo]:
        """Analyze a single signal for clock-like behavior."""
        # Filter to only 0/1 transitions and deduplicate consecutive same values
        valid_transitions = []
        for t, v in transitions:
            if v not in ('0', '1'):
                continue
            if valid_transitions and valid_transitions[-1][1] == v:
                continue  # Skip duplicate consecutive values (e.g., from dumpvars)
            valid_transitions.append((t, v))
        if len(valid_transitions) < 4:
            return None

        # Check that it toggles between 0 and 1
        values = [v for _, v in valid_transitions]
        for i in range(1, len(values)):
            if values[i] == values[i - 1]:
                return None  # Non-toggling behavior

        # Compute half-periods
        timestamps = [t for t, _ in valid_transitions]
        half_periods = [
            timestamps[i] - timestamps[i - 1]
            for i in range(1, len(timestamps))
        ]

        if not half_periods:
            return None

        # Compute full periods (pair consecutive half-periods)
        full_periods: List[int] = []
        for i in range(0, len(half_periods) - 1, 2):
            full_periods.append(half_periods[i] + half_periods[i + 1])

        if not full_periods:
            return None

        avg_period = sum(full_periods) / len(full_periods)
        if avg_period == 0:
            return None

        # Compute stability as inverse of coefficient of variation
        deviations = [abs(p - avg_period) for p in full_periods]
        avg_dev = sum(deviations) / len(deviations)
        stability = max(0.0, 1.0 - (avg_dev / avg_period)) if avg_period > 0 else 0.0

        # Compute duty cycle from first half-period vs. full period
        avg_high = sum(half_periods[0::2]) / len(half_periods[0::2])
        duty_cycle = avg_high / avg_period if avg_period > 0 else 0.5

        # If first value after first transition is '1', we measured high time
        # Otherwise we measured low time and need to flip
        if valid_transitions[0][1] == '0':
            duty_cycle = 1.0 - duty_cycle

        # Compute frequency (assuming timescale is in ns by default)
        frequency = 1.0 / avg_period if avg_period > 0 else 0.0

        full_name = f"{signal.scope}.{signal.name}" if signal.scope else signal.name

        return ClockInfo(
            signal_name=full_name,
            identifier=identifier,
            frequency=frequency,
            period=int(round(avg_period)),
            duty_cycle=duty_cycle,
            stability=stability,
            edge_count=len(valid_transitions),
            first_edge=timestamps[0],
            last_edge=timestamps[-1]
        )
