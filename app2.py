import math
import random
import time
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ---------- Page config (must be the first Streamlit call) ----------
st.set_page_config(page_title="Smart Load Monitor", page_icon="⚡", layout="wide")

# ---------- Constants ----------
MAX_HISTORY = 100
REFRESH_MS = 3000
MODERATE_LIMIT = 4.0   # A (total load)
HIGH_LIMIT = 8.0       # A
GAUGE_MAX = 12.0       # A

# Household appliances (rated power in W, rated power factor)
APPLIANCES = [
    {"name": "Ceiling Fan",    "icon": "🌀", "watts": 75,   "pf": 0.85, "always_on": False},
    {"name": "LED Lights",     "icon": "💡", "watts": 20,   "pf": 0.90, "always_on": False},
    {"name": "Refrigerator",   "icon": "🧊", "watts": 150,  "pf": 0.80, "always_on": True},
    {"name": "Television",     "icon": "📺", "watts": 100,  "pf": 0.95, "always_on": False},
    {"name": "Room Heater",    "icon": "🔥", "watts": 1000, "pf": 1.00, "always_on": False},
    {"name": "Water Pump",     "icon": "🚰", "watts": 750,  "pf": 0.75, "always_on": False},
]
NAMES = [a["name"] for a in APPLIANCES]
FAULTS = ["None", "Overload", "Low power factor", "Standby leakage"]

# ---------- Styling ----------
st.markdown(
    """
    <style>
        .block-container {padding-top: 1.8rem;}
        div[data-testid="stMetric"] {
            background: rgba(120, 130, 150, 0.08);
            border: 1px solid rgba(120, 130, 150, 0.25);
            border-radius: 12px;
            padding: 14px 18px;
        }
        div[data-testid="stMetricLabel"] {opacity: 0.75;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- Session state ----------
def reset_state():
    st.session_state.history = []
    st.session_state.energy = {n: 0.0 for n in NAMES}      # kWh
    st.session_state.on_hours = {n: 0.0 for n in NAMES}    # total simulated hours ON
    st.session_state.run_hours = {n: 0.0 for n in NAMES}   # continuous hours ON
    st.session_state.sim_hours = 0.0
    st.session_state.last_run = time.time()


if "history" not in st.session_state:
    reset_state()

# ---------- Sidebar ----------
with st.sidebar:
    st.header("⚙️ Controls")
    live = st.toggle("Live updates (every 3 s)", value=True)

    st.subheader("🔌 Appliances")
    states = {}
    for a in APPLIANCES:
        default_on = a["name"] in ("Refrigerator", "LED Lights", "Ceiling Fan")
        states[a["name"]] = st.toggle(
            f'{a["icon"]} {a["name"]} ({a["watts"]} W)',
            value=default_on,
            key=f'on_{a["name"]}',
        )

    st.subheader("💰 Cost")
    rate = st.number_input("Electricity rate (₹/unit)", 0.0, value=8.0, step=0.5)

    st.subheader("⏱️ Demo time")
    speed = st.slider(
        "Time acceleration (×)", 1, 3600, 600,
        help="1 real second = this many simulated seconds, so energy builds up visibly.",
    )
    forgot_hours = st.slider("Forgotten-ON alert after (sim. hours)", 1.0, 12.0, 4.0, 0.5)

    with st.expander("🧪 Fault simulation (demo)"):
        fault_target = st.selectbox("Appliance", NAMES)
        fault_type = st.selectbox("Fault type", FAULTS)

    if st.button("🗑️ Reset all data", use_container_width=True):
        reset_state()

    st.divider()
    st.caption("Mode: Software simulation")

if live:
    st_autorefresh(interval=REFRESH_MS, key="refresh")

# ---------- Simulated readings ----------
voltage = random.uniform(215, 235)  # V

now = time.time()
dt_real = min(now - st.session_state.last_run, 10) if live else 0.0
st.session_state.last_run = now
dt_h = dt_real * speed / 3600       # simulated hours since last update

rows = []
alerts = []
total_p = total_q = 0.0

for a in APPLIANCES:
    name, rated_w, rated_pf = a["name"], a["watts"], a["pf"]
    is_on = states[name]
    fault = fault_type if name == fault_target else "None"

    # Real power (W), power factor, apparent power (VA)
    if is_on:
        p = rated_w * random.uniform(0.95, 1.05)
        pf_i = rated_pf
        if fault == "Overload":
            p *= 1.6
        elif fault == "Low power factor":
            pf_i = max(0.4, rated_pf - 0.3)
        va = p / pf_i
    elif fault == "Standby leakage":
        p, pf_i = random.uniform(8, 15), 0.5
        va = p / pf_i
    else:
        p, pf_i, va = 0.0, 1.0, 0.0

    q = math.sqrt(max(va**2 - p**2, 0.0))   # reactive power (VAr)
    total_p += p
    total_q += q

    # Energy and run-time tracking
    st.session_state.energy[name] += p * dt_h / 1000
    if is_on:
        st.session_state.on_hours[name] += dt_h
        st.session_state.run_hours[name] += dt_h
    else:
        st.session_state.run_hours[name] = 0.0

    # ---- Fault detection ----
    health = "✅ OK"
    if is_on and p > rated_w * 1.25:
        health = "🔴 Overload"
        alerts.append(("error", name,
            f"Overload — drawing {p:.0f} W vs {rated_w} W rated "
            f"(+{(p / rated_w - 1) * 100:.0f}%). Possible motor/element fault."))
    elif is_on and pf_i < rated_pf - 0.15:
        health = "🟠 Low PF"
        alerts.append(("warning", name,
            f"Low power factor {pf_i:.2f} (normal ≈ {rated_pf:.2f}). "
            "Possible winding or capacitor degradation."))
    elif (not is_on) and p > 2:
        health = "🔴 Leakage"
        alerts.append(("error", name,
            f"Drawing {p:.0f} W while switched OFF. Possible leakage / insulation fault."))
    elif is_on and (not a["always_on"]) and st.session_state.run_hours[name] >= forgot_hours:
        health = "🟡 Left ON"
        alerts.append(("warning", name,
            f"ON for {st.session_state.run_hours[name]:.1f} h continuously. "
            "Switch off if not in use."))

    energy_kwh = st.session_state.energy[name]
    rows.append({
        "Appliance": f'{a["icon"]} {name}',
        "_name": name,
        "State": "ON" if is_on else "OFF",
        "Power (W)": round(p, 1),
        "Current (A)": round(va / voltage, 2),
        "PF": round(pf_i, 2) if (is_on or p > 0) else None,
        "Energy (kWh)": round(energy_kwh, 3),
        "Cost (₹)": round(energy_kwh * rate, 2),
        "Health": health,
    })

st.session_state.sim_hours += dt_h

# Household totals (real, reactive and apparent power add up correctly via P and Q)
total_s = math.hypot(total_p, total_q)           # VA
total_pf = total_p / total_s if total_s else 1.0
total_current = total_s / voltage

df = pd.DataFrame(rows)
total_energy = sum(st.session_state.energy.values())
total_cost = total_energy * rate

if total_current < MODERATE_LIMIT:
    status, icon = "NORMAL", "🟢"
elif total_current < HIGH_LIMIT:
    status, icon = "MODERATE", "🟡"
else:
    status, icon = "HIGH", "🔴"

# Store history (total + per-appliance power)
if live or not st.session_state.history:
    entry = {
        "Time": datetime.now(),
        "Voltage (V)": round(voltage, 2),
        "Total Current (A)": round(total_current, 2),
        "Total Real Power (W)": round(total_p, 2),
        "Total Apparent Power (VA)": round(total_s, 2),
        "Power Factor": round(total_pf, 2),
    }
    for r in rows:
        entry[f'{r["_name"]} (W)'] = r["Power (W)"]
    st.session_state.history.append(entry)
    st.session_state.history = st.session_state.history[-MAX_HISTORY:]
history = pd.DataFrame(st.session_state.history)

# ---------- Header ----------
st.title("⚡ Smart Electrical Load Monitor")
st.caption(
    "IoT-based household load monitoring with per-appliance tracking and fault detection · "
    "Readings are simulated, not measured from physical sensors."
)

banner = f"{icon} **Household load: {status}** — {total_current:.1f} A · {total_p:.0f} W"
if status == "NORMAL":
    st.success(banner)
elif status == "MODERATE":
    st.warning(banner)
else:
    st.error(banner + " · High load, consider switching off heavy appliances!")

if alerts:
    st.error(f"🚨 {len(alerts)} active alert(s) — see the **Fault Detection** tab.")

# ---------- Live readings ----------
st.subheader("Live Readings")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Voltage", f"{voltage:.1f} V")
c2.metric("Total Current", f"{total_current:.2f} A")
c3.metric("Real Power", f"{total_p:.0f} W")
c4.metric("Apparent Power", f"{total_s:.0f} VA")
c5.metric("Power Factor", f"{total_pf:.2f}")

# ---------- Tabs ----------
tab_over, tab_app, tab_fault, tab_an, tab_data = st.tabs(
    ["📈 Overview", "🔌 Appliances", "🚨 Fault Detection", "🔍 Analysis", "📄 Data"]
)

# ----- Overview -----
with tab_over:
    left, right = st.columns([2, 1])
    with left:
        options = [
            "Total Real Power (W)", "Total Apparent Power (VA)", "Voltage (V)",
            "Total Current (A)", "Power Factor",
        ] + [f"{n} (W)" for n in NAMES]
        parameter = st.selectbox("Parameter", options)
        fig = px.line(history, x="Time", y=parameter, markers=True)
        fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=10, b=10),
                          height=340, xaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)
    with right:
        gauge = go.Figure(go.Indicator(
            mode="gauge+number", value=total_current,
            number={"suffix": " A"}, title={"text": "Total Load Level"},
            gauge={
                "axis": {"range": [0, GAUGE_MAX]},
                "bar": {"color": "#374151"},
                "steps": [
                    {"range": [0, MODERATE_LIMIT], "color": "#bbf7d0"},
                    {"range": [MODERATE_LIMIT, HIGH_LIMIT], "color": "#fde68a"},
                    {"range": [HIGH_LIMIT, GAUGE_MAX], "color": "#fecaca"},
                ],
            },
        ))
        gauge.update_layout(height=340, margin=dict(l=20, r=20, t=60, b=10))
        st.plotly_chart(gauge, use_container_width=True)

# ----- Appliances -----
with tab_app:
    st.caption("Which appliance is using how much power right now.")
    bar = px.bar(
        df, x="Power (W)", y="Appliance", orientation="h", text="Power (W)",
        color="State", color_discrete_map={"ON": "#2563eb", "OFF": "#9ca3af"},
    )
    bar.update_layout(template="plotly_white", height=320,
                      margin=dict(l=10, r=10, t=10, b=10), yaxis_title=None)
    st.plotly_chart(bar, use_container_width=True)

    view = df.drop(columns="_name").copy()
    view["Share (%)"] = (
        (df["Power (W)"] / total_p * 100).round(1) if total_p else 0.0
    )
    st.dataframe(
        view[["Appliance", "State", "Power (W)", "Share (%)", "Current (A)", "PF", "Health"]],
        use_container_width=True, hide_index=True,
    )

# ----- Fault detection -----
with tab_fault:
    st.caption(
        "Checks: overload (>125% of rating), low power factor, "
        "leakage while OFF, and appliances left ON too long."
    )
    if not alerts:
        st.success("✅ No faults detected. All appliances look healthy.")
    for level, name, msg in alerts:
        (st.error if level == "error" else st.warning)(f"**{name}:** {msg}")
    st.dataframe(
        df[["Appliance", "State", "Power (W)", "PF", "Health"]],
        use_container_width=True, hide_index=True,
    )
    st.caption("Tip: use *Fault simulation* in the sidebar to demo each fault.")

# ----- Analysis -----
with tab_an:
    st.caption(f"Simulated time tracked: {st.session_state.sim_hours:.1f} hours")
    a1, a2 = st.columns(2)
    a1.metric("Total Energy", f"{total_energy:.3f} kWh")
    a2.metric("Total Cost", f"₹{total_cost:.2f}")

    if total_energy <= 0:
        st.info("Let the dashboard run for a few seconds to collect usage data.")
    else:
        used = df[df["Energy (kWh)"] > 0]
        pie = px.pie(used, names="Appliance", values="Energy (kWh)", hole=0.45)
        pie.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(pie, use_container_width=True)

        st.subheader("💡 Where to cut usage")
        ranked = df.sort_values("Energy (kWh)", ascending=False).head(3)
        for _, r in ranked.iterrows():
            if r["Energy (kWh)"] <= 0:
                continue
            name = r["_name"]
            share = r["Energy (kWh)"] / total_energy * 100
            on_h = st.session_state.on_hours[name]
            avg_kw = r["Energy (kWh)"] / on_h if on_h > 0 else 0
            saving = avg_kw * 1 * 30 * rate   # 1 hour/day less, for 30 days
            st.markdown(
                f"- **{r['Appliance']}** — {share:.0f}% of energy "
                f"(₹{r['Cost (₹)']:.2f}). Using it **1 hour/day less** saves "
                f"≈ **₹{saving:.0f}/month**."
            )
        st.caption("Always-on appliances like the refrigerator are hard to cut; "
                   "focus on heaters, pumps and lights.")

# ----- Data -----
with tab_data:
    st.dataframe(history.sort_values("Time", ascending=False),
                 use_container_width=True, hide_index=True)
    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Download readings (CSV)",
                       data=history.to_csv(index=False).encode("utf-8"),
                       file_name="electrical_load_readings.csv", mime="text/csv")
    d2.download_button("⬇️ Download appliance summary (CSV)",
                       data=df.drop(columns="_name").to_csv(index=False).encode("utf-8"),
                       file_name="appliance_summary.csv", mime="text/csv")

st.divider()
st.caption(
    "Real power = V × I × PF. Voltage, PF and appliance loads are simulated; "
    "a real setup needs per-appliance meters (e.g. PZEM-004T / CT sensors on ESP32)."
)