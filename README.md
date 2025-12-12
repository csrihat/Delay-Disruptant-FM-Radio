# FM Radio Dual-Receiver Failover System

## Overview

This project implements a dual-receiver delay-disruptant FM radio using two RTL-SDR devices with an active–passive failover design. The system continuously monitors RSSI (received signal strength) from the primary receiver and automatically switches to the backup receiver when the signal drops below a defined threshold.

The focus of this implementation is on **signal-level failover control and observability**; audio playback is not required for validation.

For testing, the exporter supports controlled RSSI simulation to produce repeatable failover behavior without relying on unpredictable RF conditions.


## Requirements

### Functional Requirements

- The system reads RSSI values from two RTL-SDR receivers (FM1 and FM2).
- The system compares FM1 RSSI against a fixed threshold of -65 dBm.
- If FM1 RSSI stays below -65 dBm for at least 1.0 second, the system switches the active receiver from FM1 to FM2.
- When FM2 is active and FM1 RSSI rises back to -65 dBm or higher, the system switches the active receiver back to FM1 once the low-RSSI condition clears.
- The exporter exposes metrics for:
  - fm_rssi_dbm{receiver="FM1|FM2"}
  - fm_active_receiver{receiver="FM1|FM2"}
  - fm_switch_events_total{from_receiver="FM1", to_receiver="FM2"}
  - fm_switch_events_total{from_receiver="FM2", to_receiver="FM1"}
  - fm_rssi_threshold_dbm
- Prometheus scrapes these metrics, and Grafana visualizes RSSI, active receiver state, and switch events.


### Non-Functional Requirements
- Failover stability is achieved using a hold-down (debounce) timer to prevent rapid switching during brief signal fluctuations.
- The system should remain stable during continuous monitoring.
- All components run together via Docker Compose.

### Constraints
- Only two RTL-SDR Blog V4 devices are used.
- Real FM audio output is not implemented in this version.
- System runs entirely on a standard computer using Docker.

### Acceptance Criteria
- Both receivers show valid RSSI values at `/metrics`.
- Failover happens when FM1 stays below -65 dBm for about a second.
- The system switches back once FM1 comes back above the threshold.
- Grafana shows RSSI and the switch events correctly.
- Prometheus scrapes the exporter normally at the 250 ms interval.




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
## Failover Logic
This implementation relies on a hold-down timer for stability and does not implement a separate hysteresis margin.
```
                 ┌──────────────────────────┐
                 │   Poll RSSI (250 ms)     │
                 │  FM1_RSSI / FM2_RSSI     │
                 └─────────────┬────────────┘
                               │
                               ▼
                 ┌──────────────────────────┐
                 │ Is FM1_RSSI < -65 dBm ?  │
                 └───────┬──────────────────┘
                         │
          ┌──────────────┴──────────────┐
          │                             │
         No                            Yes
          │                             │
          ▼                             ▼
 ┌──────────────────────┐     ┌──────────────────────────┐
 │ Stay on current      │     │ Start / continue          │
 │ active receiver      │     │ low-RSSI timer            │
 └─────────┬────────────┘     └────────────┬──────────────┘
           │                                │
           ▼                                ▼
 ┌──────────────────────┐       ┌─────────────────────────────┐
 │ Reset low-RSSI timer │       │ Has FM1_RSSI been < -65 dBm │
 │ (condition cleared)  │       │ for ≥ 1.0 sec ?              │
 └─────────┬────────────┘       └──────────────┬──────────────┘
           │                                     │
           ▼                                     ▼
        (loop)                              ┌───────────────┐
                                            │ FAILOVER to   │
                                            │ FM2           │
                                            │ - Update      │
                                            │   metrics     │
                                            │ - Increment   │
                                            │   counter     │
                                            └───────┬───────┘
                                                    │
                                                    ▼
                                 ┌──────────────────────────┐
                                 │ While FM2 active:        │
                                 │ Check FM1_RSSI ≥ -65 dBm │
                                 └─────────────┬────────────┘
                                               │
                               ┌───────────────┴──────────────┐
                               │                              │
                              No                             Yes
                               │                              │
                               ▼                              ▼
                   ┌──────────────────────┐      ┌────────────────────────┐
                   │ Stay on FM2          │      │ RECOVERY to FM1        │
                   │ (FM1 still too weak) │      │ - Update metrics       │
                   └──────────────────────┘      │ - Increment counter    │
                                                 └────────────────────────┘


```
### How It Works


The exporter reads RSSI values for both receivers (FM1 and FM2).
Prometheus scrapes RSSI metrics every 250 ms.
If FM1 RSSI remains below the configured threshold for longer than the debounce interval:
- The exporter triggers a failover by signaling GNU Radio to switch the active receiver to FM2.
The exporter updates metrics immediately:
- fm_active_receiver
- fm_switch_events_total
Prometheus scrapes the updated metrics, and Grafana visualizes the changes in real time.



## Configuration

The exporter currently uses the following internal parameters:

| Parameter | Description | Default Source                  |
|----------|-------------|---------------------------------|
| `ACTIVE_RECEIVER` | Initial active receiver (`FM1` or `FM2`) | Environment variable or `'FM1'` |
| `fm_rssi_threshold_dbm` | RSSI threshold used for failover | Set at `-65`                    |
| `debounce_seconds` | Time RSSI must remain below threshold before switching | Set at `1.0` seconds            |


## Prerequisites

### Hardware
- **2× RTL-SDR Blog V4** (R828D RTL2832U, 1 PPM TCXO) dongles
  - Supported by rtl_sdr, pyrtlsdr, and gr-osmosdr
  - Each includes a dipole antenna kit for FM reception
  - Identical models reduce variability and simplify relative RSSI comparison.
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

## Project Structure
```bash
  Delay-Disruptant-FM-Radio/
├── exporter/
│   ├── exporter.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── gnuradio/
│   ├── fm_failover.py
│   └── Dockerfile
│
├── grafana/
│   └── provisioning/
│       └── dashboards/
│           ├── dashboard.yml
│           └── fm_dual_receiver.json
│
├── prometheus/
│   └── prometheus.yml
│
├── docker-compose.yml
└── README.md

```


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

SKIP


## Metrics Exposed

| Metric                                               | Description | Example |
|------------------------------------------------------|-------------|---------|
| `fm_rssi_dbm{receiver="FM1\|FM2"}`                   | Signal strength in dBm | -45.2   |
| `fm_active_receiver{receiver="FM1\|FM2"}`            | Active (1) or Standby (0) | 1       |
| `fm_switch_events_total{from_receiver, to_receiver}` | Total failover switches | 5       |
| `fm_rssi_threshold_dbm`                              | Configured threshold | -65     |


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


## Verification & Validation (V&V)

### Verification

- RSSI values for both FM1 and FM2 show up correctly at the `/metrics` endpoint.
- The system switches to FM2 when FM1 stays below -65 dBm for about one second.
- When FM1’s signal comes back above the threshold, the active receiver switches back to FM1.
- The exporter exposes the expected metrics (RSSI, active receiver, switch counter).
- Prometheus is able to scrape the exporter at the configured interval (250 ms).
- Grafana displays the RSSI values and failover activity as intended.
- All components run properly inside Docker without build or startup issues.

### Validation

- When FM1’s antenna is obstructed or signal drops, the failover to FM2 happens consistently.
- When FM1 recovers, the system switches back normally without rapid back-and-forth switching.
- The system ran for extended periods without crashes or unstable behavior.
- The Grafana dashboard clearly reflects RSSI trends and each switch event, making the system easy to monitor during testing.


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

