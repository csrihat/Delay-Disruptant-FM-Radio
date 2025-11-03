# Delay-Disruptant FM Radio
Dual-Receiver Delay-Disruptant FM Radio with Active–Passive Failover

### 1. Objectives
- Build a dual-receiver delay-disruptant FM radio with active–passive failover.
- Measure RSSI on Receiver #1 using a Prometheus exporter (no CSV files).
- When RSSI drops below a threshold, trigger GNU Radio to switch to Receiver #2 with minimal audio gap.
- Expose runtime metrics (RSSI, active receiver, switch events) for observability.
---

### 2. Requirements
#### Hardware
- **Raspberry Pi 5** (8 GB) - host platform for all containers.  
- **2 × RTL-SDR Blog V4 (R828D + RTL2832U, 1 PPM TCXO)** dongles  
  - Supported by `rtl_sdr`, `pyrtlsdr`, and `gr-osmosdr`.  
  - Each includes a dipole antenna kit for FM reception.  
  - Identical models ensure matched frequency and RSSI comparison.  

#### Software
- **Docker & Docker Compose** - all components must run in containers.  
- **Python (Prometheus RSSI Exporter)**  
- **Prometheus** - for metric collection and monitoring.  
- **GNU Radio** - WBFM demodulator flowgraph with controllable source selector.  
- *(Optional)* **Alertmanager** and **Grafana** for alerting and visualization.

#### Configuration
- Assign unique serials to each RTL-SDR dongle:  
  ```bash
  rtl_eeprom -d 0 -s FM1
  rtl_eeprom -d 1 -s FM2
  # Replug both after programming
---
  ### 3. Design 
```mermaid
flowchart LR
  A[RTL-SDR #1] --> E[Prometheus Exporter]
  B[RTL-SDR #2] --> E
  E --> P[Prometheus]
  P --> G[GNU Radio Flowgraph]
  G --> S[Audio Output]
