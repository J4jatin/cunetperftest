"""
Stress Performance Tests — Control Unit Network
Tests network behavior under high load (3x nominal message rate).
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulator.can_bus_simulator import CANBusSimulator
from analyzer.performance_analyzer import NetworkPerformanceAnalyzer

STRESS_DURATION = 1.0
STRESS_LOAD_FACTOR = 3.0
LATENCY_INCREASE_THRESHOLD = 3.0   # stress latency must be < 3x baseline


@pytest.fixture(scope="module")
def scenario_results():
    bus = CANBusSimulator()
    baseline_msgs = bus.run_baseline(duration_s=STRESS_DURATION)
    stress_msgs = bus.run_stress(duration_s=STRESS_DURATION, load_factor=STRESS_LOAD_FACTOR)
    analyzer = NetworkPerformanceAnalyzer()
    baseline_stats = analyzer.analyze(baseline_msgs)
    stress_stats = analyzer.analyze(stress_msgs)
    comparison = analyzer.compare_scenarios(baseline_stats, stress_stats, stress_stats)
    bottlenecks = analyzer.detect_bottlenecks(stress_stats.get("per_ecu", {}))
    return {
        "baseline": baseline_stats,
        "stress": stress_stats,
        "comparison": comparison,
        "bottlenecks": bottlenecks,
    }


def test_stress_produces_more_messages(scenario_results):
    """Stress scenario should produce more messages than baseline."""
    assert scenario_results["stress"]["total_messages"] > scenario_results["baseline"]["total_messages"]


def test_stress_latency_increase_bounded(scenario_results):
    """Stress latency should not exceed 3x baseline latency."""
    b_lat = scenario_results["baseline"]["latency_ms"]["mean"]
    s_lat = scenario_results["stress"]["latency_ms"]["mean"]
    if b_lat > 0:
        ratio = s_lat / b_lat
        assert ratio < LATENCY_INCREASE_THRESHOLD, (
            f"Stress latency {s_lat:.1f}ms is {ratio:.1f}x baseline {b_lat:.1f}ms — exceeds threshold"
        )


def test_stress_comparison_keys(scenario_results):
    """Comparison report must contain all required metrics."""
    required = [
        "latency_increase_stress_vs_baseline_pct",
        "throughput_change_stress_vs_baseline_pct",
        "stress_p99_ms",
        "baseline_p99_ms",
    ]
    for key in required:
        assert key in scenario_results["comparison"], f"Missing comparison key: {key}"


def test_stress_bottleneck_detection_runs(scenario_results):
    """Bottleneck detection should run without error."""
    bottlenecks = scenario_results["bottlenecks"]
    assert isinstance(bottlenecks, list)


def test_stress_throughput_scales(scenario_results):
    """Stress throughput should be higher than baseline."""
    b_thr = scenario_results["baseline"]["throughput_msg_per_s"]
    s_thr = scenario_results["stress"]["throughput_msg_per_s"]
    assert s_thr > b_thr, f"Stress throughput {s_thr} not higher than baseline {b_thr}"
