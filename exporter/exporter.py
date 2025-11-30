#!/usr/bin/env python3
import time
import random
import os
import requests
import math
import numpy as np
from prometheus_client import start_http_server, Gauge, Counter

# Metrics
rssi_gauge = Gauge('fm_rssi_dbm', 'Current RSSI in dBm', ['receiver'])
active_gauge = Gauge('fm_active_receiver', 'Currently active receiver', ['receiver'])
switch_counter = Counter('fm_switch_events_total', 'Receiver switches', ['from_receiver', 'to_receiver'])
threshold_gauge = Gauge('fm_rssi_threshold_dbm', 'Configured RSSI threshold', [])
threshold_gauge.set(-65)

# State
active = os.getenv('ACTIVE_RECEIVER', 'FM1')
base_rssi_fm1 = -45.0
base_rssi_fm2 = -48.0
last_switch_time = 0
debounce_seconds = 1.0


def simulate_rssi(base):
    t = time.time()
    fading = 8 * math.sin(t / 180) + 4 * math.sin(t / 47) + 2 * math.sin(t / 13)
    multipath = 6 * np.sin(2 * np.pi * 15 * t) * np.exp(-0.1 * abs(np.sin(2 * np.pi * 0.3 * t)))
    noise = random.gauss(0, 2.2)
    return base + fading + multipath + noise


now = time.time()

if random.random() < 0.008:
    blockage_duration = random.uniform(4, 18)
    blockage_start = now
    print(f"REALISTIC BLOCKAGE STARTED for {blockage_duration:.1f}s")

if 'blockage_start' in locals() and now - blockage_start < blockage_duration:
    rssi_fm1 = random.uniform(-96, -88) + random.gauss(0, 3)
    print(f"BLOCKAGE ACTIVE → FM1 = {rssi_fm1:.1f} dBm")
else:
    if 'blockage_start' in locals():
        del blockage_start
        print("Blockage ended — signal recovered")
    rssi_fm1 = simulate_rssi(base_rssi_fm1)

def trigger_switch(new_receiver):
    global active, last_switch_time
    old = active
    active = new_receiver
    last_switch_time = time.time()
    switch_counter.labels(from_receiver=old, to_receiver=new_receiver).inc()
    try:
        requests.post(f"http://gnuradio:8080/switch/{new_receiver}", timeout=2)
        print(f"FAILOVER: {old} → {new_receiver}  (RSSI FM1={rssi_gauge.labels(receiver='FM1')._value.get():.1f} dBm)")
    except:
        pass

def main():
    start_http_server(9100)
    print("Simulated RSSI exporter STARTED – no hardware required")

    while True:
        now = time.time()


        if 10 < now % 30 < 15:
            rssi_fm1 = -95
            print(f"SIMULATED BLOCKAGE → FM1 = {rssi_fm1:.1f} dBm")
        else:
            rssi_fm1 = simulate_rssi(base_rssi_fm1)

        rssi_fm2 = simulate_rssi(base_rssi_fm2)

        # Failover logic
        if active == 'FM1' and rssi_fm1 < -65 and (now - last_switch_time) > debounce_seconds:
            if rssi_fm2 > -60:  # FM2 is good
                trigger_switch('FM2')
        elif active == 'FM2' and rssi_fm2 < -65 and (now - last_switch_time) > debounce_seconds:
            if rssi_fm1 > -60:
                trigger_switch('FM1')

        # Update metrics
        rssi_gauge.labels(receiver='FM1').set(round(rssi_fm1, 2))
        rssi_gauge.labels(receiver='FM2').set(round(rssi_fm2, 2))
        active_gauge.labels(receiver='FM1').set(1 if active == 'FM1' else 0)
        active_gauge.labels(receiver='FM2').set(1 if active == 'FM2' else 0)

        time.sleep(0.25)

if __name__ == '__main__':
    main()