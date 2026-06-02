"""
HTML Performance Report Generator for CUNetPerfTest.
Produces a professional test results report using Jinja2.
"""

import os
from datetime import datetime

try:
    from jinja2 import Template
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False

REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>CU Network Performance Test Report</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f0f14; color: #e0e0e0; }
  .header { background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 2rem; border-bottom: 2px solid #c00; }
  .header h1 { color: #fff; font-size: 1.8rem; }
  .header .sub { color: #aaa; font-size: 0.85rem; margin-top: 0.3rem; }
  .container { max-width: 1200px; margin: 2rem auto; padding: 0 1.5rem; }
  .section { background: #1a1a2e; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #2a2a4a; }
  .section h2 { color: #c00; font-size: 1rem; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 1rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; }
  .metric { background: #12122a; border-radius: 6px; padding: 1rem; text-align: center; border: 1px solid #2a2a4a; }
  .metric .value { font-size: 1.6rem; font-weight: 700; color: #fff; }
  .metric .label { font-size: 0.7rem; color: #888; margin-top: 0.3rem; text-transform: uppercase; }
  .scenarios { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; }
  .scenario { background: #12122a; border-radius: 6px; padding: 1.2rem; border: 1px solid #2a2a4a; }
  .scenario h3 { color: #74c0fc; margin-bottom: 0.8rem; font-size: 0.9rem; text-transform: uppercase; }
  .scenario .stat { display: flex; justify-content: space-between; margin-bottom: 0.4rem; font-size: 0.82rem; }
  .scenario .stat .key { color: #888; }
  .scenario .stat .val { color: #fff; font-weight: 600; }
  table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
  th { background: #12122a; color: #aaa; padding: 0.6rem 0.8rem; text-align: left; font-weight: 600; text-transform: uppercase; font-size: 0.72rem; }
  td { padding: 0.5rem 0.8rem; border-bottom: 1px solid #1f1f3a; }
  tr:hover td { background: #1f1f3a; }
  .pass { color: #69db7c; font-weight: 700; }
  .fail { color: #ff6b6b; font-weight: 700; }
  .warn { color: #ffd43b; font-weight: 700; }
  .footer { text-align: center; color: #444; font-size: 0.78rem; padding: 2rem; }
</style>
</head>
<body>
<div class="header">
  <h1>&#9889; Control Unit Network Performance Test Report</h1>
  <div class="sub">Generated: {{ generated_at }} &nbsp;|&nbsp; CUNetPerfTest v1.0 &nbsp;|&nbsp; Scenarios: Baseline · Stress · OTA</div>
</div>
<div class="container">

  <!-- Summary -->
  <div class="section">
    <h2>&#9654; Test Summary</h2>
    <div class="grid">
      <div class="metric"><div class="value">3</div><div class="label">Scenarios Run</div></div>
      <div class="metric"><div class="value">{{ total_messages }}</div><div class="label">Total Messages</div></div>
      <div class="metric"><div class="value">{{ baseline.latency_ms.mean }}ms</div><div class="label">Baseline Mean Latency</div></div>
      <div class="metric"><div class="value">{{ stress.latency_ms.mean }}ms</div><div class="label">Stress Mean Latency</div></div>
      <div class="metric"><div class="value">{{ comparison.latency_increase_stress_vs_baseline_pct }}%</div><div class="label">Latency Δ (Stress)</div></div>
      <div class="metric"><div class="value">{{ "PASS" if comparison.stress_within_budget else "FAIL" }}</div><div class="label">Stress SLA</div></div>
    </div>
  </div>

  <!-- Scenario Comparison -->
  <div class="section">
    <h2>&#128202; Scenario Comparison</h2>
    <div class="scenarios">
      <!-- Baseline -->
      <div class="scenario">
        <h3>&#9679; Baseline</h3>
        {% for k, v in [("Messages", baseline.total_messages), ("Throughput", baseline.throughput_msg_per_s|string + " msg/s"), ("Mean Latency", baseline.latency_ms.mean|string + " ms"), ("P95 Latency", baseline.latency_ms.p95|string + " ms"), ("P99 Latency", baseline.latency_ms.p99|string + " ms"), ("Duration", baseline.duration_s|string + " s")] %}
        <div class="stat"><span class="key">{{ k }}</span><span class="val">{{ v }}</span></div>
        {% endfor %}
      </div>
      <!-- Stress -->
      <div class="scenario">
        <h3>&#128293; Stress (3x Load)</h3>
        {% for k, v in [("Messages", stress.total_messages), ("Throughput", stress.throughput_msg_per_s|string + " msg/s"), ("Mean Latency", stress.latency_ms.mean|string + " ms"), ("P95 Latency", stress.latency_ms.p95|string + " ms"), ("P99 Latency", stress.latency_ms.p99|string + " ms"), ("SLA", "PASS" if comparison.stress_within_budget else "FAIL")] %}
        <div class="stat"><span class="key">{{ k }}</span><span class="val">{{ v }}</span></div>
        {% endfor %}
      </div>
      <!-- OTA -->
      <div class="scenario">
        <h3>&#128268; OTA Update</h3>
        {% for k, v in [("Messages", ota.total_messages), ("Throughput", ota.throughput_msg_per_s|string + " msg/s"), ("Mean Latency", ota.latency_ms.mean|string + " ms"), ("P95 Latency", ota.latency_ms.p95|string + " ms"), ("P99 Latency", ota.latency_ms.p99|string + " ms"), ("SLA", "PASS" if comparison.ota_within_budget else "FAIL")] %}
        <div class="stat"><span class="key">{{ k }}</span><span class="val">{{ v }}</span></div>
        {% endfor %}
      </div>
    </div>
  </div>

  <!-- Per-ECU Baseline Stats -->
  {% if baseline.per_ecu %}
  <div class="section">
    <h2>&#128268; ECU Node Performance (Baseline)</h2>
    <table>
      <thead><tr><th>ECU</th><th>Mean (ms)</th><th>Min (ms)</th><th>Max (ms)</th><th>P95 (ms)</th><th>P99 (ms)</th><th>Stdev (ms)</th></tr></thead>
      <tbody>
        {% for ecu, stats in baseline.per_ecu.items() %}
        <tr>
          <td><strong>{{ ecu }}</strong></td>
          <td>{{ stats.mean }}</td>
          <td>{{ stats.min }}</td>
          <td>{{ stats.max }}</td>
          <td>{{ stats.p95 }}</td>
          <td>{{ stats.p99 }}</td>
          <td>{{ stats.stdev }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

  <!-- Bottlenecks -->
  {% if bottlenecks %}
  <div class="section">
    <h2>&#9888; Detected Bottlenecks</h2>
    <table>
      <thead><tr><th>ECU</th><th>Issues</th></tr></thead>
      <tbody>
        {% for b in bottlenecks %}
        <tr><td>{{ b.ecu }}</td><td>{{ b.issues | join("; ") }}</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

</div>
<div class="footer">CUNetPerfTest — Control Unit Network Performance Test Framework &nbsp;|&nbsp; Jattin Shah &nbsp;|&nbsp; github.com/J4jatin</div>
</body>
</html>"""


class HTMLReporter:
    def generate(self, baseline, stress, ota, comparison, bottlenecks, output_path):
        ctx = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "baseline": baseline,
            "stress": stress,
            "ota": ota,
            "comparison": comparison,
            "bottlenecks": bottlenecks,
            "total_messages": (
                baseline.get("total_messages", 0) +
                stress.get("total_messages", 0) +
                ota.get("total_messages", 0)
            ),
        }
        if HAS_JINJA2:
            html = Template(REPORT_TEMPLATE).render(**ctx)
        else:
            html = f"<html><body><h1>CUNetPerfTest Report</h1><pre>{ctx}</pre></body></html>"
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        return output_path
