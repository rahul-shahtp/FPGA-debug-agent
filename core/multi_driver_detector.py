"""
Multi-Driver Heuristic Detection Module.

Detects conflicting toggles on the same signal within a short time window,
which may indicate multiple drivers on a single net.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core.vcd_parser import VCDData

logger = logging.getLogger(__name__)


@dataclass
class MultiDriverEvent:
    """Represents a suspected multi-driver event."""
    signal_name: str
    timestamp: int
    toggle_count: int
    window_size: int
    description: str
    severity: str  # 'HIGH', 'MEDIUM', 'LOW'


class MultiDriverDetector:
    """
    Detects signals with suspicious toggle patterns that suggest
    multiple drivers.

    A multi-driver condition is heuristically detected when a signal
    has an unusually high number of transitions within a short time window,
    or exhibits conflicting value changes (e.g., rapid toggling that
    doesn't match normal clock or data patterns).
    """

    def __init__(
        self,
        window_size: int = 5,
        toggle_threshold: int = 3
    ) -> None:
        """
        Args:
            window_size: Time window (in time units) to check for
                         conflicting toggles.
            toggle_threshold: Number of toggles within the window that
                              triggers a multi-driver flag.
        """
        self._window_size = window_size
        self._toggle_threshold = toggle_threshold

    def detect(self, vcd_data: VCDData) -> List[MultiDriverEvent]:
        """
        Detect potential multi-driver conditions across all signals.

        Args:
            vcd_data: Parsed VCD data.

        Returns:
            List of detected multi-driver events.
        """
        logger.info(
            "Starting multi-driver detection (window=%d, threshold=%d)",
            self._window_size, self._toggle_threshold
        )
        events: List[MultiDriverEvent] = []

        for identifier, signal in vcd_data.signals.items():
            transitions = vcd_data.get_transitions(identifier)
            if len(transitions) < self._toggle_threshold:
                continue

            full_name = (
                f"{signal.scope}.{signal.name}" if signal.scope else signal.name
            )

            events.extend(
                self._check_signal(full_name, transitions)
            )

        logger.info("Multi-driver detection found %d event(s)", len(events))
        return events

    def _check_signal(
        self, signal_name: str, transitions: List[Tuple[int, str]]
    ) -> List[MultiDriverEvent]:
        """Check a single signal for multi-driver patterns."""
        events: List[MultiDriverEvent] = []
        timestamps = [t for t, _ in transitions]

        i = 0
        while i < len(timestamps):
            # Count transitions within the window
            window_end = timestamps[i] + self._window_size
            count = 0
            j = i
            while j < len(timestamps) and timestamps[j] <= window_end:
                count += 1
                j += 1

            if count >= self._toggle_threshold:
                events.append(MultiDriverEvent(
                    signal_name=signal_name,
                    timestamp=timestamps[i],
                    toggle_count=count,
                    window_size=self._window_size,
                    description=(
                        f"Suspicious activity on {signal_name}: "
                        f"{count} toggles within {self._window_size} "
                        f"time units at t={timestamps[i]}"
                    ),
                    severity='MEDIUM'
                ))
                i = j  # Skip past the flagged window
            else:
                i += 1

        return events
