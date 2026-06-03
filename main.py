"""
CUNetPerfTest — Control Unit Network Performance Test Framework
==============================================================
Simulates a vehicle CAN bus network and measures performance across 3 scenarios:
  1. Baseline — nominal ECU operation
  2. Stress   — 3x message load
  3. OTA      — firmware update impact on network latency

Usage:
  python main.py                    # run all scenarios, print report
  python main.py --scenario baseline
  python main.py --scenario stress
  python main.py --scenario ota
  python main.py --report           # also generate HTML report
  python main.py --duration 5       # set scenario duration (seconds)
"""

import argparse
import sys
import os
import webbrowser
import time
from datetime import datetime

from simulator.can_bus_simulator import CANBusSimulator
from analyzer.performance_analyzer import NetworkPerformanceAnalyzer
from reporter.html_reporter import HTMLReporter


SEPARATOR = "─" * 60


def print_stats(label: str, stats: dict):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  Messages    : {stats.get('total_messages', 0)}")
    print(f"  Duration    : {stats.get('duration_s', 0)} s")
    print(f"  Throughput  : {stats.get('throughput_msg_per_s', 0)} msg/s")
    lat = stats.get("latency_ms", {})
    print(f"\n  Latency (ms)")
    print(f"    Mean  : {lat.get('mean', 0)}")
    print(f"    Min   : {lat.get('min', 0)}")
    print(f"    Max   : {lat.get('max', 0)}")
    print(f"    P50   : {lat.get('p50', 0)}")
    print(f"    P95   : {lat.get('p95', 0)}")
    print(f"    P99   : {lat.get('p99', 0)}")
    print(f"    Stdev : {lat.get('stdev', 0)}")
    if stats.get("bus_load_percent") is not None:
        print(f"\n  Bus Load    : {stats['bus_load_percent']}%")
    per_ecu = stats.get("per_ecu", {})
    if per_ecu:
        print(f"\n  Per-ECU Mean Latency:")
        for ecu, s in per_ecu.items():
            print(f"    {ecu:6s} : {s['mean']} ms (P99={s['p99']} ms)")


def print_comparison(comparison: dict):
    print(f"\n{'='*60}")
    print("  SCENARIO COMPARISON")
    print(f"{'='*60}")
    print(f"  Stress vs Baseline latency Δ : {comparison.get('latency_increase_stress_vs_baseline_pct', 0)}%")
    print(f"  OTA    vs Baseline latency Δ : {comparison.get('latency_increase_ota_vs_baseline_pct', 0)}%")
    print(f"  Stress throughput Δ          : {comparison.get('throughput_change_stress_vs_baseline_pct', 0)}%")
    print(f"  Stress SLA (latency < 2x)    : {'✓ PASS' if comparison.get('stress_within_budget') else '✗ FAIL'}")
    print(f"  OTA    SLA (latency < 1.5x)  : {'✓ PASS' if comparison.get('ota_within_budget') else '✗ FAIL'}")
    print(f"\n  P99 Comparison:")
    print(f"    Baseline : {comparison.get('baseline_p99_ms', 0)} ms")
    print(f"    Stress   : {comparison.get('stress_p99_ms', 0)} ms")
    print(f"    OTA      : {comparison.get('ota_p99_ms', 0)} ms")


def print_bottlenecks(bottlenecks: list):
    if not bottlenecks:
        print("\n  No performance bottlenecks detected.")
        return
    print(f"\n{'='*60}")
    print("  BOTTLENECKS DETECTED")
    print(f"{'='*60}")
    for b in bottlenecks:
        print(f"\n  ECU: {b['ecu']}")
        for issue in b["issues"]:
            print(f"    ⚠ {issue}")


def run_all(duration: float, generate_report: bool):
    print(f"\n{'='*60}")
    print("  CUNetPerfTest — Control Unit Network Performance Tests")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    analyzer = NetworkPerformanceAnalyzer()
    bus = CANBusSimulator()

    # ── Scenario 1: Baseline ──────────────────────────────────────────────────
    print(f"\n[1/3] Running BASELINE scenario ({duration}s)...")
    t0 = time.time()
    baseline_msgs = bus.run_baseline(duration_s=duration)
    baseline_bus = bus.get_bus_stats(baseline_msgs)
    baseline_stats = analyzer.analyze(baseline_msgs, baseline_bus)
    print_stats("BASELINE — Nominal ECU Operation", baseline_stats)
    print(f"  (completed in {time.time()-t0:.1f}s)")

    # ── Scenario 2: Stress ────────────────────────────────────────────────────
    print(f"\n[2/3] Running STRESS scenario (3x load, {duration}s)...")
    t0 = time.time()
    stress_msgs = bus.run_stress(duration_s=duration, load_factor=3.0)
    stress_bus = bus.get_bus_stats(stress_msgs)
    stress_stats = analyzer.analyze(stress_msgs, stress_bus)
    print_stats("STRESS — 3x Message Load", stress_stats)
    print(f"  (completed in {time.time()-t0:.1f}s)")

    # ── Scenario 3: OTA ───────────────────────────────────────────────────────
    print(f"\n[3/3] Running OTA UPDATE scenario...")
    t0 = time.time()
    ota_msgs = bus.run_ota_scenario(n_chunks=20)
    ota_stats = analyzer.analyze(ota_msgs)
    print_stats("OTA UPDATE — Firmware Flash Sequence", ota_stats)
    print(f"  (completed in {time.time()-t0:.1f}s)")

    # ── Comparison & Bottlenecks ──────────────────────────────────────────────
    comparison = analyzer.compare_scenarios(baseline_stats, stress_stats, ota_stats)
    print_comparison(comparison)
    bottlenecks = analyzer.detect_bottlenecks(stress_stats.get("per_ecu", {}))
    print_bottlenecks(bottlenecks)

    # ── HTML Report ───────────────────────────────────────────────────────────
    if generate_report:
        reporter = HTMLReporter()
        report_path = os.path.join(
            os.path.dirname(__file__),
            f"perf_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        )
        out = reporter.generate(
            baseline=baseline_stats,
            stress=stress_stats,
            ota=ota_stats,
            comparison=comparison,
            bottlenecks=bottlenecks,
            output_path=report_path,
        )
        print(f"\n  HTML report saved: {out}")
        webbrowser.open(f"file://{os.path.abspath(out)}")

    print(f"\n{'='*60}")
    print("  All scenarios completed.")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="CUNetPerfTest — Control Unit Network Performance Test Framework"
    )
    parser.add_argument("--scenario", choices=["baseline", "stress", "ota", "all"], default="all")
    parser.add_argument("--duration", type=float, default=2.0, help="Scenario duration in seconds")
    parser.add_argument("--report", action="store_true", help="Generate HTML performance report")
    args = parser.parse_args()

    if args.scenario == "all":
        run_all(duration=args.duration, generate_report=args.report)
    else:
        analyzer = NetworkPerformanceAnalyzer()
        bus = CANBusSimulator()
        if args.scenario == "baseline":
            msgs = bus.run_baseline(duration_s=args.duration)
            stats = analyzer.analyze(msgs, bus.get_bus_stats(msgs))
            print_stats("BASELINE", stats)
        elif args.scenario == "stress":
            msgs = bus.run_stress(duration_s=args.duration)
            stats = analyzer.analyze(msgs, bus.get_bus_stats(msgs))
            print_stats("STRESS", stats)
        elif args.scenario == "ota":
            msgs = bus.run_ota_scenario()
            stats = analyzer.analyze(msgs)
            print_stats("OTA UPDATE", stats)


if __name__ == "__main__":
    main()
