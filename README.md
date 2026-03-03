# 🔍 fpga-debug-agent

![status](https://img.shields.io/badge/status-v1.0-green)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
![input](https://img.shields.io/badge/input-VCD-blue)
![tests](https://img.shields.io/badge/tests-51%20passing-brightgreen)

A production-ready, rule-based waveform intelligence system that parses VCD files and automatically detects common FPGA/RTL design bugs.

---

## Problem Statement

Debugging FPGA designs from simulation waveforms is time-consuming and error-prone. Engineers manually inspect VCD dumps looking for glitches, reset issues, FSM problems, and undefined value propagation. **fpga-debug-agent** automates this process by applying rule-based analysis to VCD files and generating structured reports of detected issues.

---

## Architecture

The project uses a layered, modular architecture following SOLID principles:

```
fpga-debug-agent/
├── core/                        # Analysis modules
│   ├── vcd_parser.py            # IEEE VCD file parser
│   ├── clock_detector.py        # Automatic clock detection
│   ├── reset_analyzer.py        # Reset signal analysis
│   ├── glitch_detector.py       # Glitch & multi-toggle detection
│   ├── fsm_checker.py           # FSM state analysis
│   ├── x_propagation.py         # X/Z value propagation detection
│   └── multi_driver_detector.py # Multi-driver heuristic detection
├── agent/                       # Orchestration & reporting
│   ├── reasoning_engine.py      # Analysis orchestrator & Finding schema
│   └── report_generator.py      # Console & JSON report generation
├── cli/                         # Command-line interface
│   └── main.py                  # CLI entry point
├── tests/                       # Unit tests (pytest)
│   ├── test_vcd_parser.py
│   ├── test_clock_detector.py
│   ├── test_reset_analyzer.py
│   ├── test_glitch_detector.py
│   ├── test_fsm_checker.py
│   ├── test_x_propagation.py
│   ├── test_multi_driver_detector.py
│   ├── test_agent.py
│   └── test_cli.py
├── examples/                    # Sample VCD files
│   └── example.vcd
├── requirements.txt
└── README.md
```

**Data Flow:**
```
VCD File → VCDParser → VCDData
                          ↓
                   ReasoningEngine
                   ├── ClockDetector
                   ├── ResetAnalyzer
                   ├── GlitchDetector
                   ├── FSMChecker
                   ├── XPropagationDetector
                   └── MultiDriverDetector
                          ↓
                   List[Finding]
                          ↓
                   ReportGenerator → Console / JSON
```

---

## Features

### 🕐 VCD Parser
- Parses standard IEEE 1364-2001 VCD files
- Extracts signal definitions, scopes, and transitions
- Tracks timestamps with efficient streaming parsing
- Handles scalar and vector signals

### ⏱️ Automatic Clock Detection
- Identifies single-bit signals with periodic toggling
- Measures frequency, period, and duty cycle
- Validates clock stability with jitter analysis
- Handles duplicate initial values from `$dumpvars`

### 🔁 Reset Analysis
- Detects reset signals by name pattern matching
- Checks reset deassertion timing relative to clock edges
- Detects reset glitches (short pulses)
- Detects registers not properly resetting during reset

### ⚡ Glitch Detection
- Identifies pulses shorter than configurable threshold
- Detects multi-toggle events within one clock cycle
- Reports glitch timestamps and pulse widths

### 🧠 FSM Analysis
- Tracks state signal transitions and builds FSM profiles
- Detects illegal transitions (rare/anomalous state changes)
- Detects stuck states (state held too long)
- Detects unreachable states (expected but never observed)

### 🔴 X/Z Propagation Detection
- Detects undefined (X) and high-impedance (Z) values
- Traces potential propagation paths by temporal proximity
- Reports first occurrence timestamps with severity ranking

### 🔌 Multi-Driver Heuristic Detection
- Detects conflicting toggles on the same signal within short windows
- Flags suspicious activity patterns suggesting bus contention

---

## Signal Integrity Check Reference

| Check | Method | Severity |
|---|---|---|
| Multiple toggles / cycle | Count transitions per clock period; flag > 2 | High |
| Glitch | Pulse width < configurable threshold | Medium |
| X propagation | Track X/Z signals; detect temporal clusters | High |
| Multi-driver | Rapid toggles within time window | Medium |
| Reset deassert timing | Check release proximity to clock edges | Medium |
| Registers not resetting | Verify signal stability during reset | High |
| Illegal FSM transition | Detect rare state transitions | High |
| Stuck FSM state | State held beyond threshold duration | Medium |

---

## Core Data Structure

```python
@dataclass
class Finding:
    finding_type: FindingType   # SIGNAL_GLITCH | MULTI_TOGGLE | ILLEGAL_TRANSITION | ...
    signal:       str           # Full hierarchical signal name
    timestamp:    int           # Time of occurrence
    severity:     Severity      # HIGH | MEDIUM | LOW
    description:  str           # Human-readable description
    evidence:     dict          # Supporting data (pulse width, toggle count, etc.)
    clock_domain: str           # Associated clock domain
    explanation:  str           # Placeholder for future AI-based explanation
```

Every checker emits `Finding` objects, and the report layer consumes them.

---

## CLI Usage

### Basic Analysis
```bash
python -m cli.main --vcd examples/example.vcd
```

### With Options
```bash
python -m cli.main --vcd examples/example.vcd --clock auto --glitch-threshold 5
```

### JSON Export
```bash
python -m cli.main --vcd examples/example.vcd --json-output report.json --no-color
```

### All Options
```
--vcd                  Path to VCD file (required)
--clock                Clock signal name or 'auto' (default: auto)
--glitch-threshold     Minimum pulse width for glitch detection (default: 5)
--stuck-threshold      Duration threshold for stuck state detection (default: 100)
--multi-driver-window  Time window for multi-driver detection (default: 5)
--multi-driver-toggles Toggle threshold for multi-driver detection (default: 3)
--propagation-window   Window for X/Z propagation analysis (default: 10)
--json-output          Path to export JSON report
--no-color             Disable colored console output
--verbose / -v         Enable debug logging
```

---

## Sample Output

```
========================================================================
FPGA Debug Agent — Analysis Report
========================================================================
VCD File: examples/example.vcd
Timestamp: 2024-01-01 00:00:00 UTC

========================================================================
Clock Information
========================================================================
  Signal:    testbench.clk
  Period:    10 time units
  Frequency: 0.1000 (1/time_units)
  Duty Cycle: 50.0%
  Stability: 1.00
  Edges:     41

========================================================================
Summary
========================================================================
  Total Findings: 16
  HIGH: 8  MEDIUM: 7  LOW: 1

  By Type:
    clock_detected: 1
    illegal_transition: 5
    multi_driver: 2
    multi_toggle: 2
    reset_deassertion: 2
    signal_glitch: 3
    x_value: 1
```

---

## Installation & Running

```bash
# Clone the repository
git clone https://github.com/rahul-shahtp/FPGA-debug-agent.git
cd FPGA-debug-agent

# Install dependencies
pip install -r requirements.txt

# Run analysis on example VCD
python -m cli.main --vcd examples/example.vcd --no-color

# Run tests
python -m pytest tests/ -v
```

---

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test module
python -m pytest tests/test_vcd_parser.py -v

# Run with coverage
python -m pytest tests/ --cov=core --cov=agent --cov=cli
```

---

## Roadmap — Version 2 (AI Enhancement)

- **Natural language query interface**: Ask questions about waveform behavior in plain English
- **AI-based root cause reasoning**: Use LLMs to correlate findings and suggest root causes
- **Vivado waveform integration**: Direct import from Vivado simulation outputs
- **Web dashboard**: Interactive browser-based visualization of findings
- **FSDB support**: Extend parser to handle Synopsys FSDB format
- **Clock domain crossing analysis**: Detect CDC violations across multiple clock domains
- **Formal coverage integration**: Correlate findings with functional coverage data

---
