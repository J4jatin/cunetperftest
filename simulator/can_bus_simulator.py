"""CAN Bus Network Simulator (WIP)"""
from .ecu_simulator import ECUNode, STANDARD_ECUS

class CANBusSimulator:
    def __init__(self):
        self.nodes = {cfg.node_id: ECUNode(cfg) for cfg in STANDARD_ECUS}
