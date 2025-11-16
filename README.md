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
graph TB
    subgraph Hardware["Hardware Layer"]
        RTL1["RTL-SDR #1<br/>Serial: FM1"]
        RTL2["RTL-SDR #2<br/>Serial: FM2"]
    end
    
    subgraph Exporter["RSSI Exporter - Python :9100"]
        POLL["Read Signal Strength<br/>SoapySDR/pyrtlsdr"]
        THRESHOLD["Threshold & Debounce<br/>≥8dB drop for ≥300ms"]
        METRICS["5 Metrics:<br/>rssi | active_rx | switch_events | threshold | gap"]
    end
    
    subgraph Monitoring["Monitoring"]
        PROM["Prometheus<br/>Scrape: 250ms"]
        GRAFANA["Grafana<br/>Dashboard"]
    end
    
    subgraph Processing["Audio Processing"]
        CONTROLLER["Failover<br/>Controller"]
        GNURADIO["GNU Radio<br/>WBFM + Hot-switch"]
        AUDIO["Audio Output"]
    end
    
    RTL1 -->|"RSSI Data"| POLL
    RTL2 -->|"RSSI Data"| POLL
    
    POLL --> THRESHOLD
    POLL --> METRICS
    
    METRICS -->|"Port 9100"| PROM
 
    PROM --> GRAFANA
    
    THRESHOLD -->|"Breach Detected"| CONTROLLER
    
    CONTROLLER -->|"Switch"| GNURADIO

    RTL1 -->|"Active Audio"| GNURADIO
    RTL2 -->|"Standby Audio"| GNURADIO
    
    GNURADIO --> AUDIO
    
    CONTROLLER -.->|"Log Events"| METRICS
    
    style Hardware fill:#ffffff,stroke:#000000,stroke-width:2px
    style Exporter fill:#ffffff,stroke:#000000,stroke-width:2px
    style Monitoring fill:#ffffff,stroke:#000000,stroke-width:2px
    style Processing fill:#ffffff,stroke:#000000,stroke-width:2px
    
    style RTL1 fill:#ffffff,stroke:#000000,stroke-width:2px
    style RTL2 fill:#ffffff,stroke:#000000,stroke-width:2px
    style POLL fill:#ffffff,stroke:#000000,stroke-width:2px
    style THRESHOLD fill:#ffffff,stroke:#000000,stroke-width:2px
    style METRICS fill:#ffffff,stroke:#000000,stroke-width:2px
    style PROM fill:#ffffff,stroke:#000000,stroke-width:2px
    style GRAFANA fill:#ffffff,stroke:#000000,stroke-width:2px
    style GNURADIO fill:#ffffff,stroke:#000000,stroke-width:2px
    style CONTROLLER fill:#ffffff,stroke:#000000,stroke-width:2px
    style AUDIO fill:#ffffff,stroke:#000000,stroke-width:2px
