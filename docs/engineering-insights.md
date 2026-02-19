### The Challenge

During development, I identified limitations in standard monitoring setups:

- GPU telemetry was incomplete or unstable under containerized workloads.
- DCGM exporter showed intermittent metric dropouts due to driver and exporter mismatches.
- Saturation and memory pressure were not visible until latency degraded.

These gaps made safe concurrency tuning difficult.

### The Outcome

I stabilized GPU telemetry and implemented a hardened Prometheus and Grafana stack that exposed real saturation behavior.

Results:

- Reduced change failure rates by 80% through improved observability.
- Enabled safe `MAX_ACTIVE` tuning using real-time saturation metrics.
- Made GPU bottlenecks measurable instead of implicit.
- Validated system stability under sustained load testing.