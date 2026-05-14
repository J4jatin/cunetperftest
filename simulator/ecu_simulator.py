"""
ECU Node Simulator
Simulates Electronic Control Unit nodes in a vehicle network.
Each ECU has a node ID, message send rate, and configurable behavior.
"""

import time
import random
import threading
from dataclasses import dataclass, field
from typing import List, Callable, Optional
from enum import Enum


class ECUState(Enum):
    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    DIAGNOSTIC = "DIAGNOSTIC"
    OTA_UPDATE = "OTA_UPDATE"
    ERROR = "ERROR"
    RESET = "RESET"


@dataclass
class CANMessage:
    """Simulated CAN bus message."""
    can_id: str
    sender_ecu: str
    timestamp: float
    data: bytes
    service_id: Optional[str] = None
    latency_ms: float = 0.0
    dropped: bool = False


@dataclass
class ECUConfig:
    """Configuration for an ECU node."""
    node_id: str
    name: str
    can_id: str
    send_rate_hz: float = 10.0          # messages per second
    response_latency_ms: float = 5.0    # base response latency
    latency_jitter_ms: float = 2.0      # random jitter added to latency
    drop_rate: float = 0.0              # message drop probability (0.0-1.0)
    ota_capable: bool = False
    diagnostic_supported: bool = True


# Standard ECU node configurations (mimics real vehicle network)
STANDARD_ECUS = [
    ECUConfig("ECM", "Engine Control Module",       "0x7E0", send_rate_hz=20.0, response_latency_ms=3.0),
    ECUConfig("TCM", "Transmission Control Module", "0x7E1", send_rate_hz=10.0, response_latency_ms=5.0),
    ECUConfig("BCM", "Body Control Module",         "0x7E2", send_rate_hz=5.0,  response_latency_ms=8.0),
    ECUConfig("ABS", "Anti-lock Brake System",      "0x7E3", send_rate_hz=50.0, response_latency_ms=2.0),
    ECUConfig("OTA", "OTA Update Module",           "0x7E4", send_rate_hz=2.0,  response_latency_ms=10.0, ota_capable=True),
]


class ECUNode:
    """Simulates a single ECU node in the vehicle network."""

    def __init__(self, config: ECUConfig):
        self.config = config
        self.state = ECUState.IDLE
        self.message_log: List[CANMessage] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._message_callbacks: List[Callable] = []
        self.stats = {
            "sent": 0,
            "dropped": 0,
            "errors": 0,
            "latencies_ms": [],
        }

    def add_message_callback(self, cb: Callable):
        self._message_callbacks.append(cb)

    def start(self):
        self._running = True
        self.state = ECUState.ACTIVE
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self.state = ECUState.IDLE

    def _run(self):
        interval = 1.0 / self.config.send_rate_hz
        while self._running:
            self._send_periodic_message()
            time.sleep(interval)

    def _send_periodic_message(self):
        # Simulate drop
        if random.random() < self.config.drop_rate:
            self.stats["dropped"] += 1
            return

        latency = self.config.response_latency_ms + random.uniform(
            -self.config.latency_jitter_ms,
            self.config.latency_jitter_ms
        )
        latency = max(0.1, latency)

        data = self._generate_data()
        msg = CANMessage(
            can_id=self.config.can_id,
            sender_ecu=self.config.node_id,
            timestamp=time.time(),
            data=data,
            latency_ms=latency,
        )
        time.sleep(latency / 1000.0)

        with self._lock:
            self.message_log.append(msg)
            self.stats["sent"] += 1
            self.stats["latencies_ms"].append(latency)

        for cb in self._message_callbacks:
            try:
                cb(msg)
            except Exception:
                pass

    def _generate_data(self) -> bytes:
        nid = self.config.node_id
        if nid == "ECM":
            rpm = random.randint(800, 6000)
            throttle = random.randint(0, 100)
            return bytes([0x02, 0x41, 0x0C, (rpm >> 8) & 0xFF, rpm & 0xFF, throttle, 0x00, 0x00])
        elif nid == "ABS":
            speed = random.randint(0, 250)
            return bytes([0x02, 0x41, 0x0D, speed, 0x00, 0x00, 0x00, 0x00])
        elif nid == "OTA":
            chunk = random.randint(0, 255)
            return bytes([0x10, 0x06, 0x34, chunk, 0x00, 0x00, 0x00, 0x00])
        else:
            return bytes([random.randint(0, 255) for _ in range(8)])

    def simulate_uds_request(self, service_id: int, data: bytes = b"") -> CANMessage:
        """Simulate a UDS diagnostic request/response cycle."""
        latency = self.config.response_latency_ms + random.uniform(0, self.config.latency_jitter_ms)
        time.sleep(latency / 1000.0)
        response_sid = service_id + 0x40 if service_id < 0x40 else service_id
        response_data = bytes([0x02, response_sid]) + data[:6]
        msg = CANMessage(
            can_id=self.config.can_id,
            sender_ecu=self.config.node_id,
            timestamp=time.time(),
            data=response_data,
            service_id=f"0x{service_id:02X}",
            latency_ms=latency,
        )
        with self._lock:
            self.message_log.append(msg)
            self.stats["sent"] += 1
            self.stats["latencies_ms"].append(latency)
        return msg

    def simulate_ota_update(self, n_chunks: int = 10) -> List[CANMessage]:
        """Simulate an OTA firmware update sequence."""
        if not self.config.ota_capable:
            raise RuntimeError(f"ECU {self.config.node_id} does not support OTA")
        prev_state = self.state
        self.state = ECUState.OTA_UPDATE
        messages = []
        # RequestDownload
        messages.append(self.simulate_uds_request(0x34, b"\x00\x44\x00\x00\x10\x00"))
        # TransferData chunks
        for i in range(n_chunks):
            msg = self.simulate_uds_request(0x36, bytes([i & 0xFF] + [random.randint(0, 255)] * 5))
            msg.service_id = f"0x36 chunk {i+1}/{n_chunks}"
            messages.append(msg)
        # RequestTransferExit
        messages.append(self.simulate_uds_request(0x37))
        self.state = prev_state
        return messages

    def get_stats(self) -> dict:
        import statistics as _stats
        lats = self.stats["latencies_ms"]
        return {
            "node_id": self.config.node_id,
            "name": self.config.name,
            "state": self.state.value,
            "messages_sent": self.stats["sent"],
            "messages_dropped": self.stats["dropped"],
            "drop_rate_actual": round(self.stats["dropped"] / max(1, self.stats["sent"] + self.stats["dropped"]), 4),
            "latency_ms": {
                "mean": round(_stats.mean(lats), 3) if lats else 0,
                "min": round(min(lats), 3) if lats else 0,
                "max": round(max(lats), 3) if lats else 0,
                "p95": round(sorted(lats)[int(len(lats) * 0.95)], 3) if len(lats) > 5 else 0,
                "p99": round(sorted(lats)[int(len(lats) * 0.99)], 3) if len(lats) > 10 else 0,
                "stdev": round(_stats.stdev(lats), 3) if len(lats) > 1 else 0,
            }
        }
