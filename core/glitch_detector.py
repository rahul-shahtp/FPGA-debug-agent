"""
Glitch Detection Module.

Identifies signal glitches — pulses shorter than a defined threshold,
and multi-toggle events within a single clock cycle.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core.vcd_parser import VCDData
from core.clock_detector import ClockInfo

logger = logging.getLogger(__name__)


@dataclass
class GlitchEvent:
    """Represents a detected glitch or multi-toggle event."""
    event_type: str  # 'glitch' or 'multi_toggle'
    signal_name: str
    timestamp: int
    pulse_width: int
    description: str
    severity: str  # 'HIGH', 'MEDIUM', 'LOW'


class GlitchDetector:
    """
    Detects glitches and multi-toggle events in VCD signals.

    A glitch is a pulse shorter than a defined threshold.
    A multi-toggle is multiple transitions on the same signal within
    a single clock cycle.
    """

    def __init__(
        self,
        glitch_threshold: int = 5,
        clock_info: Optional[ClockInfo] = None
    ) -> None:
        """
        Args:
            glitch_threshold: Minimum pulse width (time units). Pulses
                              shorter than this are considered glitches.
            clock_info: Optional clock information for cycle-based analysis.
        """
        self._glitch_threshold = glitch_threshold
        self._clock_info = clock_info

    def set_clock(self, clock_info: ClockInfo) -> None:
        """Set clock information for cycle-based analysis."""
        self._clock_info = clock_info

    def detect(self, vcd_data: VCDData) -> List[GlitchEvent]:
        """
        Detect glitches and multi-toggle events across all signals.

        Args:
            vcd_data: Parsed VCD data.

        Returns:
            List of detected glitch events.
        """
        logger.info(
            "Starting glitch detection (threshold=%d)",
            self._glitch_threshold
        )
        events: List[GlitchEvent] = []

        for identifier, signal in vcd_data.signals.items():
            transitions = vcd_data.get_transitions(identifier)
            if len(transitions) < 2:
                continue

            full_name = (
                f"{signal.scope}.{signal.name}" if signal.scope else signal.name
            )

            events.extend(
                self._detect_short_pulses(full_name, transitions)
            )
            events.extend(
                self._detect_multi_toggle(full_name, transitions)
            )

        logger.info("Glitch detection found %d event(s)", len(events))
        return events

    def _detect_short_pulses(
        self, signal_name: str, transitions: List[Tuple[int, str]]
    ) -> List[GlitchEvent]:
        """Detect pulses shorter than the threshold."""
        events: List[GlitchEvent] = []

        for i in range(1, len(transitions)):
            pulse_width = transitions[i][0] - transitions[i - 1][0]
            if 0 < pulse_width < self._glitch_threshold:
                events.append(GlitchEvent(
                    event_type='glitch',
                    signal_name=signal_name,
                    timestamp=transitions[i - 1][0],
                    pulse_width=pulse_width,
                    description=(
                        f"Short pulse on {signal_name}: width={pulse_width} "
                        f"at t={transitions[i - 1][0]}"
                    ),
                    severity='MEDIUM'
                ))

        return events

    def _detect_multi_toggle(
        self, signal_name: str, transitions: List[Tuple[int, str]]
    ) -> List[GlitchEvent]:
        """Detect multiple toggles within one clock cycle."""
        events: List[GlitchEvent] = []

        if not self._clock_info or self._clock_info.period == 0:
            return events

        period = self._clock_info.period

        # Group transitions by clock cycle
        cycle_transitions: Dict[int, List[Tuple[int, str]]] = {}
        for ts, val in transitions:
            cycle = ts // period
            if cycle not in cycle_transitions:
                cycle_transitions[cycle] = []
            cycle_transitions[cycle].append((ts, val))

        for cycle, trans in cycle_transitions.items():
            if len(trans) > 2:  # More than 2 transitions in a cycle
                events.append(GlitchEvent(
                    event_type='multi_toggle',
                    signal_name=signal_name,
                    timestamp=trans[0][0],
                    pulse_width=0,
                    description=(
                        f"Multi-toggle on {signal_name}: "
                        f"{len(trans)} transitions in cycle {cycle} "
                        f"(period={period})"
                    ),
                    severity='HIGH'
                ))

        return events
