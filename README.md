# CUNetPerfTest — Control Unit Network Performance Test Framework

> **Performance testing framework for vehicle CAN bus control unit networks**  
> ECU Simulation | CAN Bus | UDS Diagnostics | OTA Update | Performance Analysis | pytest

![CI](https://github.com/J4jatin/cunetperftest/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Tests](https://img.shields.io/badge/tests-20%20passing-green)

---

## Overview

CUNetPerfTest simulates a vehicle CAN bus network with multiple ECU nodes and measures performance across three test scenarios. Built to mirror the performance testing work done in automotive diagnostic stack teams.

**Directly addresses the Porsche internship tasks:**
- *"Planning, execution and evaluation of performance tests in the control unit network"*
- *"Performance analyses and optimizations"*
- *"Preparation, organization, execution and evaluation of experimental setups"*

---

## Test Scenarios

| Scenario | Description | Measures |
|----------|-------------|---------|
| **Baseline** | All 5 ECUs at nominal rate | Reference latency, throughput, P95/P99 |
| **Stress** | 3x message load | Latency under congestion, drop rate, SLA check |
| **OTA Update** | Firmware flash simulation | OTA impact on background ECU latency |

---

## Architecture

```
CUNetPerfTest/
├── main.py                          # CLI entry point — run scenarios, print/export report
├── simulator/
│   ├── ecu_simulator.py             # ECU node simulation (5 nodes: ECM, TCM, BCM, ABS, OTA)
│   └── can_bus_simulator.py         # CAN bus network — runs 3 test scenarios
├── analyzer/
│   └── performance_analyzer.py      # Stats: mean, P50, P95, P99, stdev; bottleneck detection
├── reporter/
│   └── html_reporter.py             # Jinja2 HTML performance report generator
├── tests/
│   ├── test_baseline.py             # 8 baseline performance tests with SLA assertions
│   ├── test_stress.py               # 5 stress load tests
│   └── test_ota.py                  # 7 OTA update scenario tests
└── .github/workflows/ci.yml         # GitHub Actions CI
```

---

## ECU Nodes Simulated

| Node | Name | CAN ID | Rate | Latency |
|------|------|--------|------|---------|
| ECM | Engine Control Module | 0x7E0 | 20 Hz | 3ms |
| TCM | Transmission Control Module | 0x7E1 | 10 Hz | 5ms |
| BCM | Body Control Module | 0x7E2 | 5 Hz | 8ms |
| ABS | Anti-lock Brake System | 0x7E3 | 50 Hz | 2ms |
| OTA | OTA Update Module | 0x7E4 | 2 Hz | 10ms |

---

## Quick Start

```bash
# Install dependencies
pip install jinja2 pytest pytest-cov

# Run all scenarios
python main.py

# Run specific scenario
python main.py --scenario baseline
python main.py --scenario stress
python main.py --scenario ota

# Generate HTML report
python main.py --report

# Custom duration
python main.py --duration 10
```

---

## Sample Output

```
============================================================
  CUNetPerfTest — Control Unit Network Performance Tests
============================================================

[1/3] Running BASELINE scenario (2.0s)...
  Messages    : 347
  Throughput  : 87.4 msg/s
  Mean Latency: 5.1 ms
  P95 Latency : 9.8 ms
  P99 Latency : 11.2 ms

  SCENARIO COMPARISON
  Stress vs Baseline latency Δ : +47.3%
  Stress SLA (latency < 2x)    : ✓ PASS
  OTA    SLA (latency < 1.5x)  : ✓ PASS
```

---

## Performance SLAs

| Metric | Threshold |
|--------|-----------|
| Max mean latency | 50ms |
| Max jitter (stdev) | 10ms |
| Stress latency vs baseline | < 2x |
| OTA latency vs baseline | < 1.5x |
| Max drop rate | 5% |

---

## Running Tests

```bash
pytest tests/ -v --cov=.
# 20 tests | 3 test files | Baseline + Stress + OTA scenarios
```

---

## Author

**Jattin Shah** — MSc Applied AI, TU Dresden  
[github.com/J4jatin](https://github.com/J4jatin) | [linkedin.com/in/jattin-shah](https://linkedin.com/in/jattin-shah)
