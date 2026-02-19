## Observability & Metrics

The system exposes metrics for all critical control points: concurrency, queueing, latency, errors, and GPU state.

### Metrics sources

- **API Gateway**
  - `http://api:8080/metrics`
  - Request rate, error rate, latency, active requests, queue depth, approximate tokens/sec

- **vLLM**
  - `http://vllm:8000/metrics`
  - Internal inference metrics (model-dependent)

- **DCGM Exporter (NVIDIA)**
  - `http://dcgm-exporter:9400/metrics`
  - GPU utilization, memory usage, temperature, power draw

### Core operational signals

**Traffic and errors**
- `api_requests_total` (rate)
- Error rate excluding `/metrics` and `/health`

**Latency**
- `api_request_latency_seconds_bucket`
  - p50 / p95 / p99 via `histogram_quantile()`

**Backpressure**
- `api_active_requests`
- `api_queue_depth`
- Saturation proxy: `api_active_requests / MAX_ACTIVE`

**GPU state**
- Utilization (%)
- Memory used / free (MiB)
- Temperature (°C)
- Power draw (W)

### Grafana dashboards

Dashboards are organized to show:

- Current system state
- Latency trends
- Queue and saturation behavior
- GPU limits and utilization

### Prometheus scrape targets

By default, Prometheus scrapes:

- `api:8080`
- `vllm:8000`
- `dcgm-exporter:9400`

If a target reports `up=0`, related panels will show no data.