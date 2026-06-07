import streamlit as st
import random
import time
import statistics

st.set_page_config(
    page_title="CUNetPerfTest — CAN Bus Network Benchmarking",
    page_icon="⚡",
    layout="wide"
)

st.markdown("""
<style>
    .metric-card { background: #1a1a2e; border-radius: 8px; padding: 1rem; border-left: 3px solid #0066cc; }
    .pass { color: #4caf50; font-weight: bold; }
    .warn { color: #ff9800; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("⚡ CUNetPerfTest")
st.markdown("**Control Unit Network Performance Test Framework** — ECU Simulation · CAN Bus · UDS · OTA")

ECU_NODES = {
    "ECM": {"name": "Engine Control Module",      "can_id": "0x7E0", "rate_hz": 20,  "base_latency_ms": 3.0},
    "TCM": {"name": "Transmission Control Module","can_id": "0x7E1", "rate_hz": 10,  "base_latency_ms": 5.0},
    "BCM": {"name": "Body Control Module",         "can_id": "0x7E2", "rate_hz": 5,   "base_latency_ms": 8.0},
    "ABS": {"name": "Anti-lock Brake System",      "can_id": "0x7E3", "rate_hz": 50,  "base_latency_ms": 2.0},
    "OTA": {"name": "OTA Update Module",           "can_id": "0x7E4", "rate_hz": 2,   "base_latency_ms": 10.0},
}

def simulate_scenario(scenario, duration=2.0, stress_factor=1.0):
    random.seed(42 if scenario == "baseline" else 7 if scenario == "stress" else 13)
    messages = []
    for ecu_id, ecu in ECU_NODES.items():
        rate = ecu["rate_hz"] * stress_factor
        count = int(rate * duration)
        base = ecu["base_latency_ms"] * stress_factor
        jitter = base * 0.3
        for _ in range(count):
            latency = max(0.5, random.gauss(base, jitter))
            messages.append({"ecu": ecu_id, "latency_ms": latency, "can_id": ecu["can_id"]})

    if scenario == "ota":
        # Add UDS OTA sequence
        for step in ["RequestDownload", "TransferData", "RequestTransferExit"]:
            for i in range(5 if step == "TransferData" else 1):
                messages.append({"ecu": "OTA", "latency_ms": random.gauss(12, 2), "can_id": "0x7E4", "uds": step})

    latencies = [m["latency_ms"] for m in messages]
    return {
        "messages": len(messages),
        "throughput": len(messages) / duration,
        "mean_ms": statistics.mean(latencies),
        "p95_ms": sorted(latencies)[int(len(latencies) * 0.95)],
        "p99_ms": sorted(latencies)[int(len(latencies) * 0.99)],
        "latencies": latencies,
        "per_ecu": {
            ecu: [m["latency_ms"] for m in messages if m["ecu"] == ecu]
            for ecu in ECU_NODES
        }
    }

# Sidebar
st.sidebar.header("⚙️ Configuration")
selected_scenarios = st.sidebar.multiselect(
    "Select Scenarios",
    ["Baseline", "Stress (3×)", "OTA Update"],
    default=["Baseline", "Stress (3×)", "OTA Update"]
)
duration = st.sidebar.slider("Simulation Duration (s)", 1.0, 5.0, 2.0, 0.5)
show_per_ecu = st.sidebar.checkbox("Show Per-ECU Breakdown", value=True)

st.sidebar.markdown("---")
st.sidebar.markdown("**ECU Nodes**")
for ecu_id, ecu in ECU_NODES.items():
    st.sidebar.markdown(f"`{ecu_id}` {ecu['name']} — {ecu['rate_hz']} Hz")

# Run button
if st.button("▶ Run Benchmark", type="primary", use_container_width=True):
    results = {}

    progress = st.progress(0)
    status = st.empty()

    scenario_map = {
        "Baseline": ("baseline", 1.0),
        "Stress (3×)": ("stress", 3.0),
        "OTA Update": ("ota", 1.0),
    }

    for i, name in enumerate(selected_scenarios):
        status.text(f"Running {name} scenario...")
        time.sleep(0.4)
        key, factor = scenario_map[name]
        results[name] = simulate_scenario(key, duration, factor)
        progress.progress((i + 1) / len(selected_scenarios))

    status.empty()
    progress.empty()

    # Results
    st.markdown("---")
    st.subheader("📊 Results")

    cols = st.columns(len(results))
    for col, (name, r) in zip(cols, results.items()):
        with col:
            st.markdown(f"**{name}**")
            st.metric("Messages", r["messages"])
            st.metric("Throughput", f"{r['throughput']:.1f} msg/s")
            st.metric("Mean Latency", f"{r['mean_ms']:.1f} ms")
            st.metric("P95 Latency", f"{r['p95_ms']:.1f} ms")
            st.metric("P99 Latency", f"{r['p99_ms']:.1f} ms")

    # SLA Check
    if "Baseline" in results and "Stress (3×)" in results:
        st.markdown("---")
        st.subheader("✅ SLA Compliance")
        baseline_mean = results["Baseline"]["mean_ms"]
        stress_mean = results["Stress (3×)"]["mean_ms"]
        ratio = stress_mean / baseline_mean
        stress_pass = ratio < 2.0

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Stress vs Baseline latency Δ:** `+{(ratio-1)*100:.1f}%`")
            if stress_pass:
                st.markdown('<p class="pass">✔ Stress SLA PASS (latency &lt; 2× baseline)</p>', unsafe_allow_html=True)
            else:
                st.markdown('<p class="warn">✘ Stress SLA FAIL</p>', unsafe_allow_html=True)

        if "OTA Update" in results:
            ota_mean = results["OTA Update"]["mean_ms"]
            ota_ratio = ota_mean / baseline_mean
            ota_pass = ota_ratio < 1.5
            with col2:
                st.markdown(f"**OTA vs Baseline latency Δ:** `+{(ota_ratio-1)*100:.1f}%`")
                if ota_pass:
                    st.markdown('<p class="pass">✔ OTA SLA PASS (latency &lt; 1.5× baseline)</p>', unsafe_allow_html=True)
                else:
                    st.markdown('<p class="warn">✘ OTA SLA FAIL</p>', unsafe_allow_html=True)

    # Charts
    st.markdown("---")
    st.subheader("📈 Latency Distribution")

    import pandas as pd
    chart_data = {}
    for name, r in results.items():
        chart_data[name] = pd.Series(sorted(r["latencies"][:100]))
    st.line_chart(pd.DataFrame(chart_data))

    if show_per_ecu and "Baseline" in results:
        st.markdown("---")
        st.subheader("🔧 Per-ECU Baseline Latency")
        ecu_data = {
            ecu: statistics.mean(lats) if lats else 0
            for ecu, lats in results["Baseline"]["per_ecu"].items()
        }
        st.bar_chart(ecu_data)

else:
    # Landing state
    st.markdown("---")
    st.info("👆 Click **Run Benchmark** to simulate CAN bus network performance across ECU nodes.")

    st.subheader("What this tests")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**🔵 Baseline**\nAll 5 ECUs at nominal rate. Establishes reference P50/P95/P99 latency.")
    with col2:
        st.markdown("**🔴 Stress (3×)**\n3× message load. Measures latency under congestion. SLA: < 2× baseline.")
    with col3:
        st.markdown("**🟡 OTA Update**\nFull RequestDownload → TransferData → RequestTransferExit sequence over CAN.")

    st.markdown("---")
    st.subheader("ECU Node Configuration")
    import pandas as pd
    df = pd.DataFrame([
        {"Node": k, "Name": v["name"], "CAN ID": v["can_id"], "Rate": f"{v['rate_hz']} Hz", "Base Latency": f"{v['base_latency_ms']} ms"}
        for k, v in ECU_NODES.items()
    ])
    st.dataframe(df, hide_index=True, use_container_width=True)

st.markdown("---")
st.markdown("Built by **Jattin Shah** · MSc Applied AI, TU Dresden · [github.com/J4jatin/cunetperftest](https://github.com/J4jatin/cunetperftest)")
