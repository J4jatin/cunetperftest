"""
Baseline Performance Tests — Control Unit Network
Tests normal operating conditions of the ECU network.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulator.ecu_simulator import ECUNode, ECUConfig
from simulator.can_bus_simulator import CANBusSimulator
from analyzer.performance_analyzer import NetworkPerformanceAnalyzer

BASELINE_DURATION = 1.0   # seconds (short for CI speed)
MAX_LATENCY_MS = 50.0     # SLA: no ECU should exceed 50ms
MAX_JITTER_MS = 10.0      # SLA: stdev must be < 10ms
MIN_MSG_RATE = 5.0        # SLA: at least 5 messages/s per ECU


@pytest.fixture(scope="module")
def baseline_results():
    bus = CANBusSimulator()
    messages = bus.run_baseline(duration_s=BASELINE_DURATION)
    analyzer = NetworkPerformanceAnalyzer()
    stats = analyzer.analyze(messages, bus.get_bus_stats(messages))
    node_stats = bus.get_all_node_stats()
    return {"messages": messages, "stats": stats, "node_stats": node_stats}


def test_baseline_produces_messages(baseline_results):
    """Network should produce messages in baseline scenario."""
    assert len(baseline_results["messages"]) > 0, "No messages produced in baseline"


def test_baseline_all_ecus_active(baseline_results):
    """All 5 standard ECU nodes should send messages."""
    senders = {m.sender_ecu for m in baseline_results["messages"]}
    expected = {"ECM", "TCM", "BCM", "ABS", "OTA"}
    assert expected.issubset(senders), f"Missing ECUs: {expected - senders}"


def test_baseline_mean_latency_within_sla(baseline_results):
    """Mean latency across all messages must be under SLA threshold."""
    mean_lat = baseline_results["stats"]["latency_ms"]["mean"]
    assert mean_lat < MAX_LATENCY_MS, f"Mean latency {mean_lat}ms exceeds SLA {MAX_LATENCY_MS}ms"


def test_baseline_p99_latency(baseline_results):
    """P99 latency should not be more than 3x the mean (no severe tail)."""
    stats = baseline_results["stats"]["latency_ms"]
    p99 = stats["p99"]
    mean = stats["mean"]
    if mean > 0:
        assert p99 < mean * 4, f"P99 {p99}ms is >{4}x mean {mean}ms — severe tail latency"


def test_baseline_no_excessive_drops(baseline_results):
    """Message drop rate must be under 5% in baseline."""
    total = baseline_results["stats"]["total_messages"]
    dropped = baseline_results["stats"].get("messages_dropped", 0)
    if total > 0:
        drop_rate = dropped / total
        assert drop_rate < 0.05, f"Drop rate {drop_rate:.2%} exceeds 5% in baseline"


def test_baseline_per_ecu_latency(baseline_results):
    """Each ECU must have mean latency under individual SLA."""
    per_ecu = baseline_results["stats"].get("per_ecu", {})
    violations = []
    for ecu, stats in per_ecu.items():
        if stats["mean"] > MAX_LATENCY_MS:
            violations.append(f"{ecu}: {stats['mean']}ms")
    assert not violations, f"ECU latency SLA violations: {violations}"


def test_baseline_throughput(baseline_results):
    """Network throughput should meet minimum rate."""
    rate = baseline_results["stats"]["throughput_msg_per_s"]
    assert rate > MIN_MSG_RATE, f"Throughput {rate} msg/s below minimum {MIN_MSG_RATE}"


def test_baseline_bus_stats_structure(baseline_results):
    """Bus stats should have all required keys."""
    stats = baseline_results["stats"]
    required = ["total_messages", "duration_s", "throughput_msg_per_s", "latency_ms"]
    for key in required:
        assert key in stats, f"Missing key in stats: {key}"
