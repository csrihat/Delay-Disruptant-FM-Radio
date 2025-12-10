#!/usr/bin/env python3
import time
import random
import os
import math
import requests

import numpy as np
from prometheus_client import start_http_server, Gauge, Counter

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------
THRESHOLD_DBM     = -65.0   # RSSI threshold where we consider a receiver "bad"
GOOD_MARGIN_DBM   = -60.0   # RSSI level where a receiver is considered "good"

DEBOUNCE_SECONDS  = 0.2     # Min time between any switches (avoid rapid flaps)
BAD_HOLD_SECONDS  = 1.5     # Must stay below threshold this long before failover
GOOD_HOLD_SECONDS = 5.0     # Must stay above good margin this long before failback

ACTIVE_DEFAULT = os.getenv("ACTIVE_RECEIVER", "FM1")

# "True" average levels for each receiver
BASE_RSSI_FM1 = -45.0       # Primary
BASE_RSSI_FM2 = -48.0       # Backup

# -------------------------------------------------------------------
# Prometheus metrics
# -------------------------------------------------------------------
rssi_gauge = Gauge(
    "fm_rssi_dbm",
    "Current RSSI in dBm",
    ["receiver"],
)

active_gauge = Gauge(
    "fm_active_receiver",
    "Currently active receiver (1 = active, 0 = inactive)",
    ["receiver"],
)

switch_counter = Counter(
    "fm_switch_events_total",
    "Number of receiver switches",
    ["from_receiver", "to_receiver"],
)

threshold_gauge = Gauge(
    "fm_rssi_threshold_dbm",
    "Configured RSSI failover threshold (dBm)",
)
threshold_gauge.set(THRESHOLD_DBM)


def simulate_rssi(base_dbm: float) -> float:
    """
    Baseline RSSI model: slow fading + multipath + Gaussian noise.
    """
    t = time.time()

    # Slow fading
    fading = 8 * math.sin(t / 180) + 4 * math.sin(t / 47) + 2 * math.sin(t / 13)

    # Multipath short ringing bursts
    multipath = (
        6
        * np.sin(2 * np.pi * 15 * t)
        * np.exp(-0.1 * abs(np.sin(2 * np.pi * 0.3 * t)))
    )

    # Receiver / thermal noise
    noise = random.gauss(0, 2.2)

    return base_dbm + fading + multipath + noise


def trigger_switch(new_receiver: str) -> None:
    """
    Change the active receiver, bump the counter, and notify GNU Radio if available.
    """
    global active, last_switch_time

    old = active
    if old == new_receiver:
        return

    active = new_receiver
    last_switch_time = time.time()

    # Increment directional counter
    switch_counter.labels(from_receiver=old, to_receiver=new_receiver).inc()

    # Log + optional callback to GNU Radio
    try:
        requests.post(
            f"http://gnuradio:8080/switch/{new_receiver}",
            timeout=2,
        )
        print(
            f"FAILOVER: {old} → {new_receiver}   "
            f"(FM1={rssi_gauge.labels(receiver='FM1')._value.get():.1f} dBm, "
            f"FM2={rssi_gauge.labels(receiver='FM2')._value.get():.1f} dBm)"
        )
    except Exception as e:
        print(f"FAILOVER (no GNU Radio callback): {old} → {new_receiver}  [{e}]")


# -------------------------------------------------------------------
# Main loop
# -------------------------------------------------------------------
def main() -> None:
    global active, last_switch_time

    active = ACTIVE_DEFAULT
    last_switch_time = 0.0

    # FM1 fade / blockage state
    fade_active   = False
    fade_start    = 0.0
    fade_end      = 0.0
    fade_duration = 0.0
    fade_depth    = THRESHOLD_DBM - 25.0

    # Track how long FM1/FM2 have been "bad" and FM1 "good"
    fm1_bad_since  = None
    fm2_bad_since  = None
    fm1_good_since = None

    # Parameters for FM1
    BLOCKAGE_PROBABILITY = 0.01
    BLOCK_MIN_DURATION   = 4.0
    BLOCK_MAX_DURATION   = 10.0

    start_http_server(9100)
    print("Simulated FM RSSI exporter STARTED on :9100 – no hardware required")
    print(f"Initial active receiver: {active}")
    print(f"Threshold: {THRESHOLD_DBM} dBm (good if above {GOOD_MARGIN_DBM} dBm)")

    while True:
        now = time.time()

        # ------------------------------------------------------------------
        # RSSI simulation
        # ------------------------------------------------------------------


        if (not fade_active) and (random.random() < BLOCKAGE_PROBABILITY):
            fade_active   = True
            fade_duration = random.uniform(BLOCK_MIN_DURATION, BLOCK_MAX_DURATION)
            fade_start    = now
            fade_end      = now + fade_duration


            fade_depth = random.uniform(THRESHOLD_DBM - 35.0, THRESHOLD_DBM + 5.0)

            print(
                f"FM1 FADING STARTED: duration {fade_duration:.1f}s, "
                f"depth {fade_depth:.1f} dBm"
            )

        if fade_active:

            progress = (now - fade_start) / max(fade_duration, 0.001)
            progress = min(max(progress, 0.0), 1.0)


            fade_alpha = 1.0 - abs(2.0 * progress - 1.0)

            normal  = simulate_rssi(BASE_RSSI_FM1)
            blocked = fade_depth + random.gauss(0, 2.0)


            if fade_alpha > 0.6:
                rssi_fm1 = blocked
            else:
                rssi_fm1 = (1.0 - fade_alpha) * normal + fade_alpha * blocked

            if now >= fade_end:
                fade_active = False
                print("FM1 fading ended")
        else:

            rssi_fm1 = simulate_rssi(BASE_RSSI_FM1)

        # ------------------------------------------------------------------
        # FM2: stable backup
        # ------------------------------------------------------------------
        raw_fm2 = simulate_rssi(BASE_RSSI_FM2)
        # Floor FM2 above the GOOD margin so it's always a valid backup
        rssi_fm2 = max(raw_fm2, GOOD_MARGIN_DBM + 1.0)  # e.g. -59 dBm

        # ------------------------------------------------------------------
        # Track how long each receiver has been bad / FM1 has been good
        # ------------------------------------------------------------------
        # FM1 bad / good tracking
        if rssi_fm1 < THRESHOLD_DBM:
            if fm1_bad_since is None:
                fm1_bad_since = now
            fm1_good_since = None  # reset good timer when it's bad
        else:
            fm1_bad_since = None
            if rssi_fm1 > GOOD_MARGIN_DBM:
                if fm1_good_since is None:
                    fm1_good_since = now
            else:
                fm1_good_since = None

        # FM2 bad tracking
        if rssi_fm2 < THRESHOLD_DBM:
            if fm2_bad_since is None:
                fm2_bad_since = now
        else:
            fm2_bad_since = None

        # ------------------------------------------------------------------
        # Failover logic (FM1 = primary, FM2 = backup)
        # ------------------------------------------------------------------
        time_since_switch = now - last_switch_time

        # 1) Currently on FM1: switch to FM2 if FM1 has been bad long enough
        if (
            active == "FM1"
            and fm1_bad_since is not None
            and (now - fm1_bad_since) >= BAD_HOLD_SECONDS
            and time_since_switch > DEBOUNCE_SECONDS
        ):
            if rssi_fm2 > GOOD_MARGIN_DBM:
                trigger_switch("FM2")

        # 2) Currently on FM2: switch back to FM1 once FM1 has been GOOD long enough
        elif (
            active == "FM2"
            and fm1_good_since is not None
            and (now - fm1_good_since) >= GOOD_HOLD_SECONDS
            and time_since_switch > DEBOUNCE_SECONDS
        ):

            if rssi_fm1 > GOOD_MARGIN_DBM:
                trigger_switch("FM1")

        # ------------------------------------------------------------------
        # Update Prometheus metrics
        # ------------------------------------------------------------------
        rssi_gauge.labels(receiver="FM1").set(round(rssi_fm1, 2))
        rssi_gauge.labels(receiver="FM2").set(round(rssi_fm2, 2))

        active_gauge.labels(receiver="FM1").set(1 if active == "FM1" else 0)
        active_gauge.labels(receiver="FM2").set(1 if active == "FM2" else 0)

        # 250 ms polling interval
        time.sleep(0.25)


if __name__ == "__main__":
    main()
