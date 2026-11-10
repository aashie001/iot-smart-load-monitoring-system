# Smart Electrical Load Monitoring System

IoT-based household load monitoring with per-appliance tracking and fault detection.

## Current Status
- Software dashboard (v1): Completed. Readings are **simulated**, not measured from physical sensors
- Hardware (ESP32 + sensors + PCB): In progress, components ordered

## Problem Statement
Households usually see only a monthly electricity bill and have no idea which appliance uses how much power, or when something is wrong. This project aims to monitor household load in real time, show per-appliance consumption and cost, and warn about faults such as overload or wasted power.

## Objectives
- Monitor voltage, current, real power, apparent power and power factor
- Track power consumption of individual appliances
- Calculate energy consumption and electricity cost
- Detect faults: overload, low power factor, standby leakage, forgotten-ON appliances
- Build the actual hardware using an ESP32 with voltage and current sensors

## Features
- Live dashboard with voltage, current, real power, apparent power, power factor
- Per-appliance power monitoring
- Energy consumption and electricity cost calculation
- Fault detection with alerts
- Graphs, analysis and data table

## Technologies Used
- Built: Python, Streamlit, Pandas, Plotly
- Planned (hardware): ESP32, SCT013 current sensor, ZMPT101B voltage sensor, MQTT

## Working Principle
- The user switches appliances ON/OFF in the sidebar. Each appliance has a fixed rated power (e.g. Ceiling Fan 75 W)
- Total load is built from the appliances that are ON, with small random variation to imitate real readings
- Real power = V x I x PF, and apparent power = V x I
- The dashboard refreshes automatically every 3 seconds to show live readings and graphs
- Cost is calculated from energy used and the electricity rate set by the user
- Fault checks run on the readings and show alerts on the Fault Detection tab
- Note: voltage, power factor and appliance loads are simulated. In the final system, real sensors will provide these values

## Screenshots
(will add below)
'''
## How to Run
pip install -r requirements.txt
streamlit run app2.py
'''
