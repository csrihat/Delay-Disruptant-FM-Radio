# Delay-Disruptant-FM-Radio
Dual-Receiver Delay-Disruptant FM Radio with Active–Passive Failover

Objectives
Build a dual-receiver delay-disruptant FM radio with active–passive failover.
Measure RSSI on Receiver #1 using a Prometheus exporter (no CSV files).
When RSSI drops below a threshold, trigger GNU Radio to switch to Receiver #2 with minimal audio gap.
Expose runtime metrics (RSSI, active receiver, switch events) for observability.
