# FM Radio Dual-Receiver Failover System

## Overview

This project implements a dual-receiver delay-disruptant FM radio using two RTL-SDR devices with an active–passive failover design. The system continuously monitors RSSI (received signal strength) from the primary receiver and automatically switches to the backup receiver when the signal drops below a defined threshold.

The focus of this implementation is on **signal-level failover control and observability**; audio playback is not required for validation and is left as future work.


## Architecture
```
           ┌────────────────────┐
           │    RTL-SDR #1      │
           │   (Primary / FM1)  │
           └─────────┬──────────┘
                     │
                     ▼
              [RSSI Measurement]
                     │
                     ▼
           ┌────────────────────┐
           │ Prometheus Exporter│
           │  - RSSI (FM1/FM2)  │
           │  - Active Receiver │
           │  - Switch Counter  │
           └─────────┬──────────┘
                     │      (metrics)
          Prometheus Scrape (250ms)
                     │
                     ▼
      ┌──────────────────────────────┐
      │          Prometheus          │
      └──────────────────────────────┘
                     │
                     ▼
      ┌──────────────────────────────┐
      │           Grafana            │
      │ - RSSI graph (FM1/FM2)       │
      │ - Active receiver indicator  │
      │ - Failover counter           │
      └──────────────────────────────┘
                     ▲
           control (REST/env/ZMQ)
                     │
           ┌─────────┴──────────┐
           │    GNU Radio       │
           │   (Source switch)  │
           └────────────────────┘
                     ▲
                     │
           ┌────────────────────┐
           │    RTL-SDR #2      │
           │ (Backup / Passive) │
           └────────────────────┘
             
```


## Prerequisites

### Hardware
- **2× RTL-SDR Blog V4** (R828D + RTL2832U, 1 PPM TCXO) dongles
  - Supported by rtl_sdr, pyrtlsdr, and gr-osmosdr
  - Each includes a dipole antenna kit for FM reception
  - Identical models ensure matched frequency and RSSI comparison
- **2× FM antennas** (included with RTL-SDR Blog V4)

### Software 
- Docker + Docker Compose
- Prometheus
- Grafana
- GNU Radio (inside container)
- Python 3.11 + required libraries:
  - prometheus-client
  - numpy
  - requests
  - pyrtlsdr


## Quick Start

### Step 1: Clone the repository
```bash
git clone https://github.com/csrihat/Delay-Disruptant-FM-Radio
cd Delay-Disruptant-FM-Radio
```

### Step 2: Start all containers
```bash
docker compose up -d
```
### Step 3: Confirm exporter is running
```bash
curl http://localhost:9100/metrics
```
You should see metrics like:
```bash
fm_rssi_dbm{receiver="FM1"} -45.0
fm_active_receiver{receiver="FM1"} 1
```

### Step 4: Open Prometheus
```bash
http://localhost:9090
```
### Step 5: Open Grafana
```bash
http://localhost:3000
```
Default login:

user: admin

pass: admin


## Metrics Exposed

| Metric                                                           | Description | Example |
|------------------------------------------------------------------|-------------|---------|
| `fm_rssi_dbm{receiver="FM1\|FM2"}`                               | Signal strength in dBm | -45.2   |
| `fm_active_receiver{receiver="FM1\|FM2"}`                        | Active (1) or Standby (0) | 1       |
| `fm_switch_events_total{from_receiver="FM1", to_receiver="FM2"}` | Total failover switches | 5       |
| `fm_rssi_threshold_dbm`                                          | Configured threshold | -65     |


## Testing Failover

1. **Open Grafana**  
   Navigate to: http://localhost:3000 and open the FM Radio Dashboard.

2. **Verify baseline**  
   - FM1 and FM2 both report RSSI values (e.g., –40 to –60 dBm)
   - FM1 should be the active receiver (Active Receiver panel = FM1)

3. **Trigger a failover condition**  
   You may simulate a weak signal by:
   - Covering or moving FM1’s antenna (if available), **or**
   - Lowering FM1 RSSI inside the exporter (for testing)

4. **Observe behavior in Grafana**  
   - FM1 RSSI drops below the configured threshold
   - After the debounce period (300–1000 ms), the system switches to FM2  
   - `fm_active_receiver` flips from FM1 → FM2  
   - `fm_switch_events_total{from_receiver="FM1", to_receiver="FM2"}` increments  
   - RSSI graph and Active Receiver panel update in real time

This validates that the RSSI-based failover logic is functioning correctly.


## Troubleshooting

### No RSSI Data Appearing
- Ensure the Prometheus exporter is running:
  ```bash
  docker compose logs fm-exporter

- Confirm the metrics endpoint is reachable:
    ```bash
    curl http://localhost:9100/metrics
    ```
### Prometheus shows target DOWN
- Check Prometheus targets at: http://localhost:9090/targets
- Restart the exporter:
    ```bash
    docker compose restart fm-exporter
    ```
### Grafana shows no time series
- Verify the Grafana data source is set to Prometheus
- Confirm the query:
  ```bash
  fm_rssi_dbm
  ```
### Switch event counter not changing
- Make sure RSSI drops below the threshold you set
- Confirm the debounce interval isn’t too long
- Check the failover logs:
  ```bash
  docker compose logs gnuradio
  ```

## Commands
```bash
# Start system
docker compose up -d

# Stop system
docker compose down

# Check Prometheus targets
http://localhost:9090/targets

# View exporter logs
docker compose logs -f fm-exporter

# Rebuild exporter container
docker compose build fm-exporter
docker compose up -d

# Test metric output
curl http://localhost:9100/metrics

```

