"""
OTA Update Performance Tests — Control Unit Network
Tests the impact of OTA firmware update traffic on vehicle network latency.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulator.ecu_simulator import ECUNode, ECUConfig, STANDARD_ECUS
from simulator.can_bus_simulator import CANBusSimulator
from analyzer.performance_analyzer import NetworkPerformanceAnalyzer

OTA_CHUNKS = 10
OTA_LATENCY_BUDGET_FACTOR = 1.5   # OTA must not increase latency by more than 50%


@pytest.fixture(scope="module")
def ota_results():
    bus = CANBusSimulator()
    baseline_msgs = bus.run_baseline(duration_s=1.0)
    ota_msgs = bus.run_ota_scenario(n_chunks=OTA_CHUNKS)
    analyzer = NetworkPerformanceAnalyzer()
    baseline_stats = analyzer.analyze(baseline_msgs)
    ota_stats = analyzer.analyze(ota_msgs)
    comparison = analyzer.compare_scenarios(baseline_stats, ota_stats, ota_stats)
    return {
        "baseline": baseline_stats,
        "ota": ota_stats,
        "comparison": comparison,
        "ota_messages": ota_msgs,
    }


def test_ota_produces_messages(ota_results):
    """OTA scenario must produce messages."""
    assert len(ota_results["ota_messages"]) > 0


def test_ota_contains_transfer_data(ota_results):
    """OTA sequence must include TransferData (0x36) messages."""
    ota_msgs = ota_results["ota_messages"]
    transfer_msgs = [m for m in ota_msgs if m.service_id and "0x36" in m.service_id]
    assert len(transfer_msgs) > 0, "No TransferData messages found in OTA sequence"


def test_ota_contains_request_download(ota_results):
    """OTA sequence must start with RequestDownload (0x34)."""
    ota_msgs = ota_results["ota_messages"]
    download_msgs = [m for m in ota_msgs if m.service_id and "0x34" in m.service_id]
    assert len(download_msgs) > 0, "No RequestDownload message found in OTA sequence"


def test_ota_chunk_count(ota_results):
    """OTA transfer should produce the correct number of chunks."""
    ota_msgs = ota_results["ota_messages"]
    transfer_msgs = [m for m in ota_msgs if m.service_id and "0x36" in m.service_id]
    assert len(transfer_msgs) == OTA_CHUNKS, (
        f"Expected {OTA_CHUNKS} OTA chunks, got {len(transfer_msgs)}"
    )


def test_ota_latency_within_budget(ota_results):
    """OTA latency impact on background ECUs must be within budget."""
    comparison = ota_results["comparison"]
    assert comparison["ota_within_budget"], (
        f"OTA latency budget exceeded — latency increase: "
        f"{comparison['latency_increase_ota_vs_baseline_pct']}%"
    )


def test_ota_non_capable_ecu_raises(ota_results):
    """Non-OTA-capable ECU should raise error on OTA attempt."""
    from simulator.ecu_simulator import ECUConfig, ECUNode
    cfg = ECUConfig("ECM", "Engine Control Module", "0x7E0", ota_capable=False)
    node = ECUNode(cfg)
    with pytest.raises(RuntimeError):
        node.simulate_ota_update()


def test_uds_diagnostic_session():
    """Full UDS diagnostic session on ECM should complete without error."""
    bus = CANBusSimulator()
    messages = bus.run_uds_diagnostic_session(ecu_id="ECM")
    assert len(messages) == 8, f"Expected 8 UDS messages, got {len(messages)}"
    service_ids = [m.service_id for m in messages if m.service_id]
    assert len(service_ids) > 0
