## Queueing & Backpressure

A GPU is a shared and limited resource.  
To keep behavior predictable, the gateway enforces explicit concurrency limits and backpressure at the API layer.

The goal is to keep latency bounded and system behavior measurable under load.

### Concurrency limit (GPU slots)

The API Gateway enforces a fixed upper bound on concurrent GPU-backed requests.

- `MAX_ACTIVE` — maximum number of simultaneous inference streams
- Metrics:
  - `api_active_requests` — current number of active requests
  - Saturation proxy:
    - `api_active_requests / MAX_ACTIVE`

This prevents VRAM exhaustion and uncontrolled latency growth.

### Queue mode vs Reject mode

Two backpressure strategies are supported.

#### Queue mode (`QUEUE_MODE=queue`)

- Requests exceeding `MAX_ACTIVE` enter a bounded in-memory queue
- Limits:
  - `QUEUE_MAX` — maximum queue length
  - `QUEUE_TIMEOUT_S` — maximum wait time before returning 503

This increases throughput at the cost of higher tail latency.

#### Reject mode (`QUEUE_MODE=reject`)

- Requests are immediately rejected with HTTP 429 when no GPU slot is available
- Intended for clients that implement retries with backoff

This keeps latency predictable and avoids queue buildup.

### Operational impact

Without explicit backpressure:

- Latency increases under burst traffic
- Queue growth is not visible
- GPU memory pressure can escalate

With explicit limits:

- Latency remains bounded
- Rejections are intentional (429 / 503)
- Saturation is visible via metrics and dashboards

### Tuning considerations

- To increase throughput:
  - Raise `MAX_ACTIVE` cautiously, within GPU memory limits
  - Use queue mode with a bounded timeout

- To prioritize latency:
  - Use reject mode
  - Handle retries client-side

- Continuous growth in `api_queue_depth` usually indicates:
  - Incoming traffic exceeds GPU capacity
  - `MAX_ACTIVE` is too low
  - Context size or model size is too heavy