# 🔍 fpga-debug-agent

![status](https://img.shields.io/badge/status-alpha-orange)
![input](https://img.shields.io/badge/input-VCD%20%2F%20FSDB-blue)
![python](https://img.shields.io/badge/python-3.10%2B-blue)

Automated waveform analysis engine for FPGA simulation dumps.
Detects clock domain crossings, glitches, reset faults, FSM misbehavior, and X-propagation — then generates natural language debug reports.

---

## Features

### 🕐 Clock & Domain (Layer 1)
- Automatic primary clock detection
- Multi-clock domain identification and signal clustering

### ⚡ Signal Integrity (Layer 2)
- Detect signals changing outside clock edge
- Detect multiple toggles within one clock cycle
- Glitch detection (pulses shorter than ~0.3× clock period)
- X / undefined value propagation tracing
- Multi-driver / conflicting signal detection (heuristic)

### 🔁 Reset Analysis (Layer 3)
- Reset deassert timing analysis (sync vs. async)
- Reset glitch detection
- Registers not properly resetting on assertion

### 🧠 FSM Analysis (Layer 4)
- Illegal transition detection from observed state patterns
- Stuck state detection (FSM frozen with changing inputs)

### 📊 Signal Activity (Layer 5)
- Toggle rate per signal
- Constant / dead signal flagging
- Burst vs. steady activity classification

### 📝 Report Generation (Layer 6)
- Natural language bug explanation via LLM
- Debug summary report: cycle range + domain + suspected root cause

---

## Signal Integrity Check Reference

| Check | Method | Severity |
|---|---|---|
| Change outside clock edge | Flag transitions outside ±ε of active edge | High |
| Multiple toggles / cycle | Count transitions per period; flag > 1 | High |
| Glitch | Pulse width < 0.3× min clock period | Medium |
| X propagation | Track X signals; trace downstream fanout | High |
| Multi-driver | Signal changes with no active registered driver | Medium |
| Reset deassert timing | Check release within valid clock window | Medium |
| Registers not resetting | Verify reset-pin regs reach reset value in N cycles | High |

---

## Core Data Structure
```python
@dataclass
class Finding:
    type:         FindingType   # GLITCH | MULTI_TOGGLE | ILLEGAL_TRANS | X_PROP | ...
    signal:       str
    clock_domain: str
    cycle_start:  int
    cycle_end:    int
    severity:     Severity      # HIGH | MED | LOW
    evidence:     dict          # raw values, waveform slice
    explanation:  str           # filled by LLM in Layer 6
```

> Design this schema early — every checker emits a `Finding`, and the report layer reads from it.

---

## Report Pipeline
```
Raw Findings (JSON)
      ↓
Aggregator + Ranker
      ↓
Template + LLM Prompt
      ↓
Natural Language Explanation
      ↓
Debug Summary Report (Markdown / HTML)
```

Each report includes: cycle range · clock domain · suspected root cause · confidence · recommended fix.

---

## Implementation Order

1. **L1** — Clock detection & domain clustering *(no deps)*
2. **L2** — Signal integrity checks, parallelizable *(requires L1)*
3. **L3** — Reset analysis *(requires L1)*
4. **L4** — FSM illegal transition + stuck state *(requires L1, L2)*
5. **L5** — Activity profiling pass *(requires L1)*
6. **L6 schema** — Finding aggregator *(requires L2–L5)*
7. **L6 LLM** — NL report generation *(requires schema)*

---
