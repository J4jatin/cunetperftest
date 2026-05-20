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
