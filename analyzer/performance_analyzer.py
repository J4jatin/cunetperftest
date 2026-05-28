"""
Performance Analyzer for CAN Bus Network Tests.
Computes statistical performance metrics: latency, throughput, P95/P99.
"""

import statistics
from collections import defaultdict
from typing import List, Dict, Any, Tuple


class NetworkPerformanceAnalyzer:
    """
    Analyzes CAN bus network performance from simulated message traffic.
    Produces metrics used for performance test evaluation and optimization.
    """

    def analyze(self, messages, bus_stats=None) -> Dict[str, Any]:
        if not messages:
            return {"error": "No messages to analyze"}

        latencies = [m.latency_ms for m in messages if m.latency_ms > 0]
        timestamps = sorted(m.timestamp for m in messages)
        duration = timestamps[-1] - timestamps[0] if len(timestamps) > 1 else 1.0

        per_ecu = defaultdict(list)
        for m in messages:
            per_ecu[m.sender_ecu].append(m.latency_ms)

        ecu_stats = {}
        for ecu, lats in per_ecu.items():
            ecu_stats[ecu] = self._compute_latency_stats(lats)

        result = {
            "total_messages": len(messages),
            "duration_s": round(duration, 3),
            "throughput_msg_per_s": round(len(messages) / duration, 2),
            "latency_ms": self._compute_latency_stats(latencies),
            "per_ecu": ecu_stats,
        }
        if bus_stats:
            result["bus_load_percent"] = bus_stats.bus_load_percent
            result["messages_dropped"] = bus_stats.total_dropped
        return result

    def compare_scenarios(self, baseline: dict, stress: dict, ota: dict) -> Dict[str, Any]:
        """Compare performance across the three test scenarios."""
        def pct_change(a, b):
            if a == 0:
                return 0
            return round((b - a) / a * 100, 1)

        b_lat = baseline.get("latency_ms", {}).get("mean", 0)
        s_lat = stress.get("latency_ms", {}).get("mean", 0)
        o_lat = ota.get("latency_ms", {}).get("mean", 0)

        b_thr = baseline.get("throughput_msg_per_s", 0)
        s_thr = stress.get("throughput_msg_per_s", 0)
        o_thr = ota.get("throughput_msg_per_s", 0)

        return {
            "latency_increase_stress_vs_baseline_pct": pct_change(b_lat, s_lat),
            "latency_increase_ota_vs_baseline_pct": pct_change(b_lat, o_lat),
            "throughput_change_stress_vs_baseline_pct": pct_change(b_thr, s_thr),
            "throughput_change_ota_vs_baseline_pct": pct_change(b_thr, o_thr),
            "baseline_p99_ms": baseline.get("latency_ms", {}).get("p99", 0),
            "stress_p99_ms": stress.get("latency_ms", {}).get("p99", 0),
            "ota_p99_ms": ota.get("latency_ms", {}).get("p99", 0),
            "stress_within_budget": s_lat < b_lat * 2.0,
            "ota_within_budget": o_lat < b_lat * 1.5,
        }

    def detect_bottlenecks(self, per_ecu_stats: dict) -> List[Dict]:
        """Identify ECU nodes with abnormal latency or high jitter."""
        bottlenecks = []
        means = [s["mean"] for s in per_ecu_stats.values() if s.get("mean", 0) > 0]
        if not means:
            return []
        network_mean = statistics.mean(means)
        for ecu, stats in per_ecu_stats.items():
            issues = []
            if stats.get("mean", 0) > network_mean * 1.5:
                issues.append(f"High latency: {stats['mean']:.1f}ms (network mean: {network_mean:.1f}ms)")
            if stats.get("p99", 0) > stats.get("mean", 0) * 5:
                issues.append(f"High P99 spike: {stats['p99']:.1f}ms vs mean {stats['mean']:.1f}ms")
            if stats.get("stdev", 0) > stats.get("mean", 0) * 0.5:
                issues.append(f"High jitter: stdev={stats['stdev']:.1f}ms")
            if issues:
                bottlenecks.append({"ecu": ecu, "issues": issues, "stats": stats})
        return bottlenecks

    def latency_timeline(self, messages, bin_size_s: float = 0.5) -> Tuple[List[float], List[float]]:
        """Returns (time_bins, avg_latency_per_bin) for plotting."""
        if not messages:
            return [], []
        t0 = messages[0].timestamp
        t_end = messages[-1].timestamp
        bins, avgs = [], []
        t = t0
        while t < t_end:
            bin_msgs = [m for m in messages if t <= m.timestamp < t + bin_size_s]
            if bin_msgs:
                avg = sum(m.latency_ms for m in bin_msgs) / len(bin_msgs)
            else:
                avg = 0
            bins.append(round(t - t0, 2))
            avgs.append(round(avg, 3))
            t += bin_size_s
        return bins, avgs

    @staticmethod
    def _compute_latency_stats(latencies: list) -> dict:
        if not latencies:
            return {"mean": 0, "min": 0, "max": 0, "p50": 0, "p95": 0, "p99": 0, "stdev": 0}
        s = sorted(latencies)
        n = len(s)
        return {
            "mean":  round(statistics.mean(latencies), 3),
            "min":   round(s[0], 3),
            "max":   round(s[-1], 3),
            "p50":   round(s[n // 2], 3),
            "p95":   round(s[int(n * 0.95)], 3),
            "p99":   round(s[int(n * 0.99)], 3),
            "stdev": round(statistics.stdev(latencies), 3) if n > 1 else 0,
        }
