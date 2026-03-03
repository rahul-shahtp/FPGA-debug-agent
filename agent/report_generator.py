"""
Report Generator Module.

Generates structured reports from analysis findings in multiple formats:
console output, JSON export.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agent.reasoning_engine import AnalysisResult, Finding, Severity

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Generates analysis reports in various formats.

    Supports:
    - Console text output with color-coded severity
    - JSON export for programmatic consumption
    - Summary statistics

    Future extension hooks:
    - HTML/Markdown report generation
    - Web dashboard data feed
    """

    # ANSI color codes for terminal output
    _COLORS = {
        'HIGH': '\033[91m',    # Red
        'MEDIUM': '\033[93m',  # Yellow
        'LOW': '\033[94m',     # Blue
        'RESET': '\033[0m',    # Reset
        'BOLD': '\033[1m',
        'GREEN': '\033[92m',
    }

    def __init__(self, use_color: bool = True) -> None:
        """
        Args:
            use_color: Whether to use ANSI colors in console output.
        """
        self._use_color = use_color

    def generate_console_report(self, result: AnalysisResult) -> str:
        """
        Generate a formatted console report.

        Args:
            result: Analysis result to report on.

        Returns:
            Formatted string for console output.
        """
        lines: List[str] = []
        lines.append(self._header("FPGA Debug Agent — Analysis Report"))
        lines.append(f"VCD File: {result.vcd_file}")
        lines.append(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append("")

        # Clock info
        if result.clock_info:
            lines.append(self._header("Clock Information"))
            ci = result.clock_info
            lines.append(f"  Signal:    {ci.signal_name}")
            lines.append(f"  Period:    {ci.period} time units")
            lines.append(f"  Frequency: {ci.frequency:.4f} (1/time_units)")
            lines.append(f"  Duty Cycle: {ci.duty_cycle:.1%}")
            lines.append(f"  Stability: {ci.stability:.2f}")
            lines.append(f"  Edges:     {ci.edge_count}")
            lines.append("")

        # Summary
        lines.append(self._header("Summary"))
        lines.append(f"  Total Findings: {result.total_issues}")
        lines.append(
            f"  {self._colorize('HIGH', 'HIGH')}: {result.high_severity_count}  "
            f"{self._colorize('MEDIUM', 'MEDIUM')}: {result.medium_severity_count}  "
            f"{self._colorize('LOW', 'LOW')}: {result.low_severity_count}"
        )
        lines.append("")

        if result.summary:
            lines.append("  By Type:")
            for finding_type, count in sorted(result.summary.items()):
                lines.append(f"    {finding_type}: {count}")
            lines.append("")

        # Findings detail
        if result.findings:
            lines.append(self._header("Findings"))
            for i, finding in enumerate(result.findings, 1):
                lines.append(self._format_finding(i, finding))
            lines.append("")

        # Footer
        lines.append(self._separator())
        lines.append(
            f"{self._colorize('GREEN', '✓')} Analysis complete. "
            f"Review findings above for potential design issues."
        )

        return '\n'.join(lines)

    def generate_json_report(self, result: AnalysisResult) -> str:
        """
        Generate a JSON report.

        Args:
            result: Analysis result to report on.

        Returns:
            JSON string of the report.
        """
        report: Dict[str, Any] = {
            "vcd_file": result.vcd_file,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_findings": result.total_issues,
                "high_severity": result.high_severity_count,
                "medium_severity": result.medium_severity_count,
                "low_severity": result.low_severity_count,
                "by_type": result.summary,
            },
        }

        if result.clock_info:
            ci = result.clock_info
            report["clock"] = {
                "signal": ci.signal_name,
                "period": ci.period,
                "frequency": ci.frequency,
                "duty_cycle": ci.duty_cycle,
                "stability": ci.stability,
                "edge_count": ci.edge_count,
            }

        report["findings"] = [
            self._finding_to_dict(f) for f in result.findings
        ]

        return json.dumps(report, indent=2, default=str)

    def export_json(
        self, result: AnalysisResult, filepath: str
    ) -> None:
        """
        Export the report as a JSON file.

        Args:
            result: Analysis result to export.
            filepath: Output file path.
        """
        json_str = self.generate_json_report(result)
        with open(filepath, 'w') as f:
            f.write(json_str)
        logger.info("JSON report exported to %s", filepath)

    def _format_finding(self, index: int, finding: Finding) -> str:
        """Format a single finding for console output."""
        severity_str = self._colorize(
            finding.severity.value, finding.severity.value
        )
        return (
            f"  [{index:3d}] {severity_str} | "
            f"{finding.finding_type.value:25s} | "
            f"t={finding.timestamp:<10d} | "
            f"{finding.signal}\n"
            f"        {finding.description}"
        )

    @staticmethod
    def _finding_to_dict(finding: Finding) -> Dict[str, Any]:
        """Convert a Finding to a dictionary for JSON serialization."""
        return {
            "type": finding.finding_type.value,
            "signal": finding.signal,
            "timestamp": finding.timestamp,
            "severity": finding.severity.value,
            "description": finding.description,
            "evidence": finding.evidence,
            "clock_domain": finding.clock_domain,
        }

    def _header(self, text: str) -> str:
        """Format a section header."""
        line = self._separator()
        return f"{line}\n{self._colorize('BOLD', text)}\n{line}"

    def _separator(self) -> str:
        """Return a separator line."""
        return "=" * 72

    def _colorize(self, color_key: str, text: str) -> str:
        """Apply ANSI color if enabled."""
        if not self._use_color:
            return text
        color = self._COLORS.get(color_key, '')
        reset = self._COLORS['RESET']
        return f"{color}{text}{reset}" if color else text
