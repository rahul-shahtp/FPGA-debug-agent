"""
CLI Interface for the FPGA Debug Agent.

Provides command-line access to VCD analysis with configurable options.
"""

import argparse
import logging
import sys
import os

# Add project root to path for module resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.reasoning_engine import ReasoningEngine
from agent.report_generator import ReportGenerator


def setup_logging(verbose: bool = False) -> None:
    """Configure logging based on verbosity setting."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="fpga-debug-agent",
        description=(
            "FPGA Debug Agent — Rule-based waveform intelligence system.\n"
            "Parses VCD files and automatically detects common "
            "FPGA/RTL design bugs."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m cli.main --vcd example.vcd\n"
            "  python -m cli.main --vcd example.vcd --clock auto "
            "--glitch-threshold 5\n"
            "  python -m cli.main --vcd example.vcd --json-output report.json\n"
        )
    )

    parser.add_argument(
        "--vcd", required=True,
        help="Path to the VCD file to analyze"
    )
    parser.add_argument(
        "--clock", default="auto",
        help="Clock signal name or 'auto' for detection (default: auto)"
    )
    parser.add_argument(
        "--glitch-threshold", type=int, default=5,
        help="Minimum pulse width for glitch detection (default: 5)"
    )
    parser.add_argument(
        "--stuck-threshold", type=int, default=100,
        help="Duration threshold for stuck state detection (default: 100)"
    )
    parser.add_argument(
        "--multi-driver-window", type=int, default=5,
        help="Time window for multi-driver detection (default: 5)"
    )
    parser.add_argument(
        "--multi-driver-toggles", type=int, default=3,
        help="Toggle threshold for multi-driver detection (default: 3)"
    )
    parser.add_argument(
        "--propagation-window", type=int, default=10,
        help="Window for X/Z propagation analysis (default: 10)"
    )
    parser.add_argument(
        "--json-output",
        help="Path to export JSON report"
    )
    parser.add_argument(
        "--no-color", action="store_true",
        help="Disable colored console output"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose/debug logging"
    )

    return parser


def main(argv=None) -> int:
    """
    Main entry point for the CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Validate input
    if not os.path.isfile(args.vcd):
        logger.error("VCD file not found: %s", args.vcd)
        print(f"Error: VCD file not found: {args.vcd}", file=sys.stderr)
        return 1

    try:
        # Run analysis
        engine = ReasoningEngine(
            clock_mode=args.clock,
            glitch_threshold=args.glitch_threshold,
            stuck_threshold=args.stuck_threshold,
            multi_driver_window=args.multi_driver_window,
            multi_driver_toggle_threshold=args.multi_driver_toggles,
            propagation_window=args.propagation_window,
        )
        result = engine.analyze(args.vcd)

        # Generate report
        reporter = ReportGenerator(use_color=not args.no_color)
        print(reporter.generate_console_report(result))

        # Export JSON if requested
        if args.json_output:
            reporter.export_json(result, args.json_output)
            print(f"\nJSON report exported to: {args.json_output}")

        return 0

    except FileNotFoundError as e:
        logger.error("File not found: %s", e)
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        logger.error("Invalid data: %s", e)
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
