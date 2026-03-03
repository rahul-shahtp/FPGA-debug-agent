"""
Reasoning Engine Module.

Orchestrates all analysis modules and aggregates findings
into a unified result set with severity ranking.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from core.vcd_parser import VCDParser, VCDData
from core.clock_detector import ClockDetector, ClockInfo
from core.reset_analyzer import ResetAnalyzer
from core.glitch_detector import GlitchDetector
from core.fsm_checker import FSMChecker
from core.x_propagation import XPropagationDetector
from core.multi_driver_detector import MultiDriverDetector

logger = logging.getLogger(__name__)


class FindingType(Enum):
    """Types of findings the engine can produce."""
    CLOCK_DETECTED = "clock_detected"
    RESET_GLITCH = "reset_glitch"
    RESET_DEASSERTION = "reset_deassertion"
    REGISTER_NOT_RESET = "register_not_reset"
    SIGNAL_GLITCH = "signal_glitch"
    MULTI_TOGGLE = "multi_toggle"
    ILLEGAL_TRANSITION = "illegal_transition"
    STUCK_STATE = "stuck_state"
    UNREACHABLE_STATE = "unreachable_state"
    X_VALUE = "x_value"
    Z_VALUE = "z_value"
    X_PROPAGATION = "x_propagation"
    MULTI_DRIVER = "multi_driver"


class Severity(Enum):
    """Severity levels for findings."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class Finding:
    """
    Unified finding from any analysis module.

    This is the core data structure that all checkers emit
    and the report layer reads from.
    """
    finding_type: FindingType
    signal: str
    timestamp: int
    severity: Severity
    description: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    clock_domain: str = ""
    explanation: str = ""  # Placeholder for future AI-based explanation


@dataclass
class AnalysisResult:
    """Complete result from running all analyses."""
    vcd_file: str
    findings: List[Finding] = field(default_factory=list)
    clock_info: Optional[ClockInfo] = None
    summary: Dict[str, int] = field(default_factory=dict)

    @property
    def total_issues(self) -> int:
        """Total number of issues found."""
        return len(self.findings)

    @property
    def high_severity_count(self) -> int:
        """Count of HIGH severity findings."""
        return sum(1 for f in self.findings if f.severity == Severity.HIGH)

    @property
    def medium_severity_count(self) -> int:
        """Count of MEDIUM severity findings."""
        return sum(1 for f in self.findings if f.severity == Severity.MEDIUM)

    @property
    def low_severity_count(self) -> int:
        """Count of LOW severity findings."""
        return sum(1 for f in self.findings if f.severity == Severity.LOW)


class ReasoningEngine:
    """
    Orchestrates all FPGA debug analysis modules.

    Parses a VCD file, runs all checkers, and produces a unified
    set of findings ranked by severity.

    Future extension hook: AI-based root cause reasoning.
    """

    def __init__(
        self,
        clock_mode: str = "auto",
        glitch_threshold: int = 5,
        stuck_threshold: int = 100,
        multi_driver_window: int = 5,
        multi_driver_toggle_threshold: int = 3,
        propagation_window: int = 10
    ) -> None:
        """
        Args:
            clock_mode: 'auto' for automatic detection, or signal name.
            glitch_threshold: Minimum pulse width for glitch detection.
            stuck_threshold: Duration threshold for stuck state detection.
            multi_driver_window: Time window for multi-driver detection.
            multi_driver_toggle_threshold: Toggle count threshold.
            propagation_window: Window for X/Z propagation analysis.
        """
        self._clock_mode = clock_mode
        self._glitch_threshold = glitch_threshold
        self._stuck_threshold = stuck_threshold
        self._multi_driver_window = multi_driver_window
        self._multi_driver_toggle_threshold = multi_driver_toggle_threshold
        self._propagation_window = propagation_window

    def analyze(self, vcd_file: str) -> AnalysisResult:
        """
        Run complete analysis on a VCD file.

        Args:
            vcd_file: Path to the VCD file.

        Returns:
            AnalysisResult containing all findings.
        """
        logger.info("Starting analysis of %s", vcd_file)
        result = AnalysisResult(vcd_file=vcd_file)

        # Step 1: Parse VCD
        parser = VCDParser()
        vcd_data = parser.parse(vcd_file)

        # Step 2: Clock detection
        clock_detector = ClockDetector()
        clock_info = self._detect_clock(clock_detector, vcd_data)
        result.clock_info = clock_info

        if clock_info:
            result.findings.append(Finding(
                finding_type=FindingType.CLOCK_DETECTED,
                signal=clock_info.signal_name,
                timestamp=clock_info.first_edge,
                severity=Severity.LOW,
                description=(
                    f"Clock detected: {clock_info.signal_name} "
                    f"(period={clock_info.period}, "
                    f"duty={clock_info.duty_cycle:.1%}, "
                    f"stability={clock_info.stability:.2f})"
                ),
                evidence={
                    "period": clock_info.period,
                    "frequency": clock_info.frequency,
                    "duty_cycle": clock_info.duty_cycle,
                    "stability": clock_info.stability,
                }
            ))

        # Step 3: Reset analysis
        self._run_reset_analysis(result, vcd_data, clock_info)

        # Step 4: Glitch detection
        self._run_glitch_detection(result, vcd_data, clock_info)

        # Step 5: FSM analysis
        self._run_fsm_analysis(result, vcd_data, clock_info)

        # Step 6: X/Z propagation
        self._run_xz_detection(result, vcd_data)

        # Step 7: Multi-driver detection
        self._run_multi_driver_detection(result, vcd_data)

        # Build summary
        result.summary = self._build_summary(result)

        # Sort findings by severity
        severity_order = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
        result.findings.sort(key=lambda f: severity_order[f.severity])

        logger.info(
            "Analysis complete: %d findings (%d HIGH, %d MEDIUM, %d LOW)",
            result.total_issues,
            result.high_severity_count,
            result.medium_severity_count,
            result.low_severity_count
        )
        return result

    def _detect_clock(
        self, detector: ClockDetector, vcd_data: VCDData
    ) -> Optional[ClockInfo]:
        """Detect clock based on mode setting."""
        if self._clock_mode == "auto":
            return detector.get_primary_clock(vcd_data)

        # Manual clock selection by signal name
        sig = vcd_data.get_signal_by_name(self._clock_mode)
        if sig:
            clocks = detector.detect(vcd_data)
            for c in clocks:
                if c.identifier == sig.identifier:
                    return c
        logger.warning("Specified clock signal '%s' not found", self._clock_mode)
        return None

    def _run_reset_analysis(
        self, result: AnalysisResult, vcd_data: VCDData,
        clock_info: Optional[ClockInfo]
    ) -> None:
        """Run reset analysis and add findings."""
        analyzer = ResetAnalyzer(
            glitch_threshold=self._glitch_threshold,
            clock_info=clock_info
        )
        for issue in analyzer.analyze(vcd_data):
            type_map = {
                'glitch': FindingType.RESET_GLITCH,
                'bad_deassertion': FindingType.RESET_DEASSERTION,
                'register_not_reset': FindingType.REGISTER_NOT_RESET,
            }
            result.findings.append(Finding(
                finding_type=type_map.get(
                    issue.issue_type, FindingType.RESET_GLITCH
                ),
                signal=issue.signal_name,
                timestamp=issue.timestamp,
                severity=Severity[issue.severity],
                description=issue.description,
            ))

    def _run_glitch_detection(
        self, result: AnalysisResult, vcd_data: VCDData,
        clock_info: Optional[ClockInfo]
    ) -> None:
        """Run glitch detection and add findings."""
        detector = GlitchDetector(
            glitch_threshold=self._glitch_threshold,
            clock_info=clock_info
        )
        for event in detector.detect(vcd_data):
            type_map = {
                'glitch': FindingType.SIGNAL_GLITCH,
                'multi_toggle': FindingType.MULTI_TOGGLE,
            }
            result.findings.append(Finding(
                finding_type=type_map.get(
                    event.event_type, FindingType.SIGNAL_GLITCH
                ),
                signal=event.signal_name,
                timestamp=event.timestamp,
                severity=Severity[event.severity],
                description=event.description,
                evidence={"pulse_width": event.pulse_width},
            ))

    def _run_fsm_analysis(
        self, result: AnalysisResult, vcd_data: VCDData,
        clock_info: Optional[ClockInfo]
    ) -> None:
        """Run FSM analysis and add findings."""
        checker = FSMChecker(
            stuck_threshold=self._stuck_threshold,
            clock_info=clock_info
        )
        issues, _ = checker.analyze(vcd_data)
        for issue in issues:
            type_map = {
                'illegal_transition': FindingType.ILLEGAL_TRANSITION,
                'stuck_state': FindingType.STUCK_STATE,
                'unreachable_state': FindingType.UNREACHABLE_STATE,
            }
            result.findings.append(Finding(
                finding_type=type_map.get(
                    issue.issue_type, FindingType.STUCK_STATE
                ),
                signal=issue.signal_name,
                timestamp=issue.timestamp,
                severity=Severity[issue.severity],
                description=issue.description,
                evidence={
                    "from_state": issue.from_state,
                    "to_state": issue.to_state,
                },
            ))

    def _run_xz_detection(
        self, result: AnalysisResult, vcd_data: VCDData
    ) -> None:
        """Run X/Z propagation detection and add findings."""
        detector = XPropagationDetector(
            propagation_window=self._propagation_window
        )
        for event in detector.detect(vcd_data):
            type_map = {
                'x_value': FindingType.X_VALUE,
                'z_value': FindingType.Z_VALUE,
                'x_propagation': FindingType.X_PROPAGATION,
            }
            result.findings.append(Finding(
                finding_type=type_map.get(
                    event.event_type, FindingType.X_VALUE
                ),
                signal=event.signal_name,
                timestamp=event.timestamp,
                severity=Severity[event.severity],
                description=event.description,
                evidence={"value": event.value},
            ))

    def _run_multi_driver_detection(
        self, result: AnalysisResult, vcd_data: VCDData
    ) -> None:
        """Run multi-driver detection and add findings."""
        detector = MultiDriverDetector(
            window_size=self._multi_driver_window,
            toggle_threshold=self._multi_driver_toggle_threshold
        )
        for event in detector.detect(vcd_data):
            result.findings.append(Finding(
                finding_type=FindingType.MULTI_DRIVER,
                signal=event.signal_name,
                timestamp=event.timestamp,
                severity=Severity[event.severity],
                description=event.description,
                evidence={
                    "toggle_count": event.toggle_count,
                    "window_size": event.window_size,
                },
            ))

    @staticmethod
    def _build_summary(result: AnalysisResult) -> Dict[str, int]:
        """Build a summary count of findings by type."""
        summary: Dict[str, int] = {}
        for finding in result.findings:
            key = finding.finding_type.value
            summary[key] = summary.get(key, 0) + 1
        return summary
