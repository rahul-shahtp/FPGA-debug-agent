"""
X/Z Propagation Detection Module.

Detects undefined (X) and high-impedance (Z) values in signals,
traces their propagation paths, and reports first occurrence timestamps.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core.vcd_parser import VCDData

logger = logging.getLogger(__name__)


@dataclass
class XZEvent:
    """Represents a detected X or Z propagation event."""
    event_type: str  # 'x_value', 'z_value', 'x_propagation'
    signal_name: str
    timestamp: int
    value: str
    description: str
    severity: str  # 'HIGH', 'MEDIUM', 'LOW'


class XPropagationDetector:
    """
    Detects X (undefined) and Z (high-impedance) values in VCD data.

    Checks for:
    - First occurrence of X/Z values on any signal
    - Signals that remain X/Z for extended periods
    - Potential propagation paths (signals going X/Z in temporal proximity)
    """

    def __init__(self, propagation_window: int = 10) -> None:
        """
        Args:
            propagation_window: Time window (in time units) to consider
                                X/Z events as related (potential propagation).
        """
        self._propagation_window = propagation_window

    def detect(self, vcd_data: VCDData) -> List[XZEvent]:
        """
        Detect all X/Z value occurrences and potential propagation.

        Args:
            vcd_data: Parsed VCD data.

        Returns:
            List of X/Z events sorted by timestamp.
        """
        logger.info("Starting X/Z propagation detection")
        events: List[XZEvent] = []
        xz_timeline: List[Tuple[int, str, str]] = []  # (timestamp, signal, value)

        for identifier, signal in vcd_data.signals.items():
            transitions = vcd_data.get_transitions(identifier)
            full_name = (
                f"{signal.scope}.{signal.name}" if signal.scope else signal.name
            )

            first_x = True
            first_z = True

            for ts, val in transitions:
                has_x = 'x' in val.lower()
                has_z = 'z' in val.lower()

                if has_x:
                    severity = 'HIGH' if first_x else 'MEDIUM'
                    events.append(XZEvent(
                        event_type='x_value',
                        signal_name=full_name,
                        timestamp=ts,
                        value=val,
                        description=(
                            f"{'First X' if first_x else 'X'} value on "
                            f"{full_name} at t={ts}: {val}"
                        ),
                        severity=severity
                    ))
                    xz_timeline.append((ts, full_name, val))
                    first_x = False

                if has_z:
                    severity = 'HIGH' if first_z else 'MEDIUM'
                    events.append(XZEvent(
                        event_type='z_value',
                        signal_name=full_name,
                        timestamp=ts,
                        value=val,
                        description=(
                            f"{'First Z' if first_z else 'Z'} value on "
                            f"{full_name} at t={ts}: {val}"
                        ),
                        severity=severity
                    ))
                    xz_timeline.append((ts, full_name, val))
                    first_z = False

        # Detect potential propagation chains
        events.extend(self._detect_propagation(xz_timeline))

        events.sort(key=lambda e: e.timestamp)
        logger.info("X/Z detection found %d event(s)", len(events))
        return events

    def _detect_propagation(
        self, xz_timeline: List[Tuple[int, str, str]]
    ) -> List[XZEvent]:
        """Detect potential X/Z propagation chains."""
        events: List[XZEvent] = []

        if len(xz_timeline) < 2:
            return events

        # Sort by timestamp
        xz_timeline.sort(key=lambda x: x[0])

        # Look for clusters of X/Z events within the propagation window
        i = 0
        while i < len(xz_timeline):
            cluster_signals: List[str] = [xz_timeline[i][1]]
            cluster_start = xz_timeline[i][0]
            j = i + 1

            while (j < len(xz_timeline) and
                   xz_timeline[j][0] - cluster_start <= self._propagation_window):
                if xz_timeline[j][1] not in cluster_signals:
                    cluster_signals.append(xz_timeline[j][1])
                j += 1

            if len(cluster_signals) > 1:
                events.append(XZEvent(
                    event_type='x_propagation',
                    signal_name=cluster_signals[0],
                    timestamp=cluster_start,
                    value='x',
                    description=(
                        f"Potential X/Z propagation at t={cluster_start}: "
                        f"{' -> '.join(cluster_signals)}"
                    ),
                    severity='HIGH'
                ))

            i = j if j > i + 1 else i + 1

        return events
