"""
CAN Bus Network Simulator
Simulates a vehicle CAN bus network with multiple ECU nodes.
Supports baseline, stress, and OTA update test scenarios.
"""

import time
import threading
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from .ecu_simulator import ECUNode, ECUConfig, CANMessage, STANDARD_ECUS


@dataclass
class BusStats:
    """Aggregated CAN bus network statistics."""
    total_messages: int = 0
    total_dropped: int = 0
    bus_load_percent: float = 0.0
    duration_s: float = 0.0
    messages_per_second: float = 0.0
    collision_count: int = 0


class CANBusSimulator:
    """
    Simulates a CAN bus network with multiple ECU nodes.
    Runs test scenarios and measures network performance.
    """

    # CAN bus parameters (500 kbps standard automotive)
    BUS_SPEED_KBPS = 500
    MAX_FRAME_BITS = 130  # max bits per standard CAN frame
    MAX_BUS_LOAD = 0.8    # 80% practical maximum

    def __init__(self, ecu_configs: Optional[List[ECUConfig]] = None):
        configs = ecu_configs or STANDARD_ECUS
        self.nodes: Dict[str, ECUNode] = {
            cfg.node_id: ECUNode(cfg) for cfg in configs
        }
        self._bus_messages: List[CANMessage] = []
        self._lock = threading.Lock()
        self._running = False

        # Register bus-level message collector
        for node in self.nodes.values():
            node.add_message_callback(self._on_message)

    def _on_message(self, msg: CANMessage):
        with self._lock:
            self._bus_messages.append(msg)

    # ── Scenario runners ──────────────────────────────────────────────────────

    def run_baseline(self, duration_s: float = 5.0) -> List[CANMessage]:
        """
        Baseline scenario: all ECUs running at nominal rate.
        Measures normal network performance as reference.
        """
        return self._run_scenario(duration_s, load_factor=1.0, scenario_name="baseline")

    def run_stress(self, duration_s: float = 5.0, load_factor: float = 3.0) -> List[CANMessage]:
        """
        Stress scenario: ECUs send at {load_factor}x nominal rate.
        Tests network behavior under high load — detects congestion, drops, latency spikes.
        """
        return self._run_scenario(duration_s, load_factor=load_factor, scenario_name="stress")

    def _run_scenario(self, duration_s: float, load_factor: float, scenario_name: str) -> List[CANMessage]:
        self._bus_messages = []
        # Adjust send rates
        for node in self.nodes.values():
            node.config.send_rate_hz = (
                STANDARD_ECUS[[e.node_id for e in STANDARD_ECUS].index(node.config.node_id)].send_rate_hz
                * load_factor
            )
        # Run
        for node in self.nodes.values():
            node.start()
        time.sleep(duration_s)
        for node in self.nodes.values():
            node.stop()
        return list(self._bus_messages)

    def run_ota_scenario(self, n_chunks: int = 20) -> List[CANMessage]:
        """
        OTA update scenario: OTA ECU simulates a firmware download sequence.
        Measures impact of OTA traffic on other ECU communication latencies.
        """
        messages = []
        # Start all non-OTA ECUs as background traffic
        background_nodes = [n for nid, n in self.nodes.items() if nid != "OTA"]
        for node in background_nodes:
            node.start()

        # Run OTA update
        ota_node = self.nodes.get("OTA")
        if ota_node:
            ota_messages = ota_node.simulate_ota_update(n_chunks=n_chunks)
            messages.extend(ota_messages)

        time.sleep(1.0)  # let background settle
        for node in background_nodes:
            node.stop()

        with self._lock:
            messages.extend(self._bus_messages)
        return messages

    def run_uds_diagnostic_session(self, ecu_id: str = "ECM") -> List[CANMessage]:
        """Run a full UDS diagnostic session on a target ECU."""
        node = self.nodes.get(ecu_id)
        if not node:
            raise ValueError(f"ECU {ecu_id} not found")
        messages = []
        uds_sequence = [
            (0x10, b"\x03"),          # DiagnosticSessionControl - extended
            (0x27, b"\x01"),          # SecurityAccess - request seed
            (0x27, b"\x02\xAB\xCD"), # SecurityAccess - send key
            (0x22, b"\xF1\x90"),     # ReadDataByIdentifier - VIN
            (0x22, b"\xF1\x86"),     # ReadDataByIdentifier - active diag session
            (0x19, b"\x02\xFF"),     # ReadDTCInformation - all DTCs
            (0x3E, b"\x00"),          # TesterPresent
            (0x10, b"\x01"),          # DiagnosticSessionControl - return to default
        ]
        for service_id, data in uds_sequence:
            msg = node.simulate_uds_request(service_id, data)
            messages.append(msg)
        return messages

    def get_bus_stats(self, messages: List[CANMessage]) -> BusStats:
        if not messages:
            return BusStats()
        timestamps = [m.timestamp for m in messages]
        duration = timestamps[-1] - timestamps[0] if len(timestamps) > 1 else 1.0
        dropped = sum(1 for m in messages if m.dropped)
        rate = len(messages) / duration if duration > 0 else 0
        # Bus load: (messages * avg frame bits) / (bus speed * duration)
        avg_bits = self.MAX_FRAME_BITS
        bus_load = (len(messages) * avg_bits) / (self.BUS_SPEED_KBPS * 1000 * duration) * 100
        return BusStats(
            total_messages=len(messages),
            total_dropped=dropped,
            bus_load_percent=round(min(bus_load, 100.0), 2),
            duration_s=round(duration, 3),
            messages_per_second=round(rate, 2),
        )

    def get_all_node_stats(self) -> List[dict]:
        return [node.get_stats() for node in self.nodes.values()]
