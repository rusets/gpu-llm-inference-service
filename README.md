# \# GPU-Accelerated LLM Inference Service

# 

# Production-oriented, GPU-backed LLM inference with explicit concurrency limits, queueing, streaming responses, and Prometheus/Grafana observability.

# 

# ---

# 

# \## Overview

# 

# This project is a GPU-accelerated LLM inference service built around \*\*vLLM\*\*, with a custom \*\*API gateway\*\*, \*\*request queueing\*\*, and \*\*production-grade observability\*\*.

# 

# The system is designed to:

# \- serve large language models efficiently on a single GPU,

# \- control GPU saturation via concurrency limits and queueing,

# \- expose OpenAI-compatible APIs,

# \- provide clear operational visibility (latency, queue depth, errors, GPU usage).

# 

# The focus is not on fine-tuning or model training, but on \*\*reliable, observable inference under load\*\*.

# 

# ---

# 

# \## Why this project exists

# 

# Most LLM demos focus on model quality or UI, but avoid the hardest part of real-world inference:

# \*\*operating a GPU-backed service under load\*\*.

# 

# In practice, GPU inference introduces problems that do not exist in typical CPU services:

# \- GPU memory is a hard limit — requests cannot be scaled horizontally inside one card.

# \- Uncontrolled concurrency leads to OOM errors or extreme latency spikes.

# \- Traditional autoscaling does not apply to a single-GPU node.

# \- Without proper metrics, GPU saturation and queue buildup are invisible.

# 

# This project was built to address those gaps.

# 

# It demonstrates how to:

# \- protect a GPU using concurrency limits and explicit queueing,

# \- apply backpressure instead of crashing or timing out silently,

# \- expose meaningful operational metrics (latency, queue depth, error rate),

# \- treat LLM inference as an \*\*infrastructure problem\*\*, not just a model problem.

# 

# The goal is not to compete with hosted LLM platforms, but to show \*\*how such systems are actually built and operated\*\*.

# 

# ---

# 

# \## Architecture (Mermaid)

# 

# The system is intentionally split into clear operational layers:

# \- \*\*Inference engine\*\* (vLLM) — owns the GPU and executes model inference.

# \- \*\*API gateway\*\* — enforces concurrency limits, queueing, and exposes metrics.

# \- \*\*Observability stack\*\* — Prometheus + Grafana for real-time visibility.

# \- \*\*Optional UI\*\* — Open WebUI for manual interaction.

# 

# This separation allows GPU protection, predictable latency, and production-style monitoring.

# 

# ```mermaid

# flowchart LR

# &nbsp;   User\[Client / Open WebUI] -->|HTTP / OpenAI API| API\[API Gateway<br/>FastAPI]

# 

# &nbsp;   API -->|streamed requests| VLLM\[vLLM Inference Engine<br/>GPU]

# 

# &nbsp;   API -->|/metrics| Prometheus

# &nbsp;   VLLM -->|/metrics| Prometheus

# 

# &nbsp;   Prometheus --> Grafana\[Grafana Dashboards]

# 

# &nbsp;   subgraph GPU Node

# &nbsp;       VLLM

# &nbsp;   end

# 

# &nbsp;   subgraph Control Plane

# &nbsp;       API

# &nbsp;       Prometheus

# &nbsp;       Grafana

# &nbsp;   end

# ```

# 

# ---

# 

# \## Components

# 

# \### vLLM (Inference Engine)

# \- Runs the \*\*GPU-backed\*\* model server (OpenAI-compatible API).

# \- Exposes:

# &nbsp; - `GET /health`

# &nbsp; - `GET /v1/models`

# &nbsp; - `POST /v1/chat/completions` (streaming)

# &nbsp; - `GET /metrics` (Prometheus metrics from vLLM)

# 

# \### API Gateway (FastAPI)

# \- Single entrypoint you treat as “production API”.

# \- Responsibilities:

# &nbsp; - \*\*Concurrency control\*\* (`MAX\_ACTIVE`) to protect GPU

# &nbsp; - \*\*Queueing / backpressure\*\* (`QUEUE\_MODE=queue|reject`, `QUEUE\_MAX`, `QUEUE\_TIMEOUT\_S`)

# &nbsp; - \*\*Request timeouts\*\* (`REQUEST\_TIMEOUT\_S`)

# &nbsp; - Operational endpoints:

# &nbsp;   - `GET /health` (checks vLLM readiness)

# &nbsp;   - `GET /metrics` (gateway Prometheus metrics)

# &nbsp;   - `GET /v1/models` (proxy)

# &nbsp;   - `POST /v1/chat/completions` (proxy + queue + stream)

# 

# \### Prometheus

# \- Scrapes metrics from:

# &nbsp; - API Gateway: `http://api:8080/metrics`

# &nbsp; - vLLM: `http://vllm:8000/metrics`

# &nbsp; - (Optional) DCGM Exporter: `http://dcgm-exporter:9400/metrics`

# 

# \### Grafana

# \- Pre-provisioned Prometheus datasource.

# \- Dashboards stored as JSON in:

# &nbsp; - `monitoring/grafana/provisioning/dashboards/`

# 

# \### Open WebUI (Optional)

# \- Human-friendly UI to interact with the model.

# \- Points to the same OpenAI-compatible endpoints (either vLLM directly or the API gateway, depending on configuration).

# 

# ---

# 

# \## Request lifecycle

# 

# 1\. \*\*Client request\*\*

# &nbsp;  - A client (Open WebUI, curl, or any OpenAI-compatible SDK) sends:

# &nbsp;    ```

# &nbsp;    POST /v1/chat/completions

# &nbsp;    ```

# &nbsp;  - Request is sent to the \*\*API Gateway\*\*, not directly to vLLM.

# 

# 2\. \*\*Health \& readiness check\*\*

# &nbsp;  - API Gateway verifies that vLLM is reachable and has at least one loaded model.

# &nbsp;  - If vLLM is unavailable:

# &nbsp;    - Request is rejected with `503 Service Unavailable`.

# 

# 3\. \*\*Concurrency gate (GPU protection)\*\*

# &nbsp;  - The gateway enforces `MAX\_ACTIVE`:

# &nbsp;    - This represents the \*\*maximum number of concurrent GPU inference streams\*\*.

# &nbsp;  - If a slot is free → request proceeds immediately.

# &nbsp;  - If no slot is free:

# &nbsp;    - `QUEUE\_MODE=queue` → request enters a bounded queue.

# &nbsp;    - `QUEUE\_MODE=reject` → request fails fast with `429`.

# 

# 4\. \*\*Queueing \& backpressure\*\*

# &nbsp;  - Queue is bounded (`QUEUE\_MAX`).

# &nbsp;  - Each queued request:

# &nbsp;    - Waits up to `QUEUE\_TIMEOUT\_S`.

# &nbsp;    - If timeout is exceeded → `503 Queue timeout`.

# &nbsp;  - Queue depth is tracked as a Prometheus gauge.

# 

# 5\. \*\*Streaming inference\*\*

# &nbsp;  - Once a GPU slot is acquired:

# &nbsp;    - Request is forwarded to:

# &nbsp;      ```

# &nbsp;      vLLM /v1/chat/completions (stream=true)

# &nbsp;      ```

# &nbsp;  - Tokens are streamed back to the client as \*\*Server-Sent Events (SSE)\*\*.

# &nbsp;  - Gateway does \*\*not buffer\*\* full responses.

# 

# 6\. \*\*Metrics \& accounting\*\*

# &nbsp;  - During streaming:

# &nbsp;    - Active requests gauge is incremented.

# &nbsp;    - Tokens are counted approximately.

# &nbsp;    - Time to first token and throughput are estimated.

# &nbsp;  - On completion:

# &nbsp;    - Latency histogram is observed.

# &nbsp;    - GPU slot is released.

# &nbsp;    - Queue depth is updated.

# 

# 7\. \*\*Client receives final event\*\*

# &nbsp;  - Final SSE frame contains:

# &nbsp;    - Approximate token count

# &nbsp;    - Total latency

# &nbsp;    - Tokens-per-second estimate

# 

# ---

# 

# \## Observability \& Metrics

# 

# This project is built to be observable from day one: every critical bottleneck (GPU concurrency, queueing, latency, errors, GPU health) is measurable and dashboardable.

# 

# \### Metrics sources

# 

# \- \*\*API Gateway\*\* exposes Prometheus metrics:

# &nbsp; - `http://api:8080/metrics`

# &nbsp; - Focus: request rate, error rate, latency, active requests, queue depth, tokens/sec (approx)

# 

# \- \*\*vLLM\*\* exposes Prometheus metrics:

# &nbsp; - `http://vllm:8000/metrics`

# &nbsp; - Focus: vLLM internal performance counters (varies by version/model)

# 

# \- \*\*DCGM Exporter (NVIDIA)\*\* exposes GPU metrics:

# &nbsp; - `http://dcgm-exporter:9400/metrics`

# &nbsp; - Focus: GPU utilization, memory used/free, temperature, power, etc.

# 

# \### Key operational signals (what you should watch)

# 

# \*\*Traffic \& errors\*\*

# \- `api\_requests\_total` (rate)

# \- error rate excluding noise endpoints (`/metrics`, `/health`)

# 

# \*\*Latency\*\*

# \- `api\_request\_latency\_seconds\_bucket` (p50/p95/p99 via `histogram\_quantile()`)

# 

# \*\*Backpressure\*\*

# \- `api\_active\_requests`

# \- `api\_queue\_depth`

# \- saturation proxy: `api\_active\_requests / MAX\_ACTIVE`

# 

# \*\*GPU health (DCGM)\*\*

# \- GPU utilization (%)

# \- framebuffer memory used/free (MiB)

# \- temperature (°C)

# \- power draw (W)

# 

# \### Grafana dashboards

# 

# The included dashboard is designed for “operator view”:

# \- current health at a glance (stat panels)

# \- performance trends (time series)

# \- bottlenecks (queue vs saturation vs latency)

# \- GPU constraints (util/mem/temp)

# 

# \### Prometheus scrape targets

# 

# By default, Prometheus scrapes:

# \- `api:8080`

# \- `vllm:8000`

# \- `dcgm-exporter:9400`

# 

# If a target shows `up=0`, the dashboards will display `No data`.

# 

# ---

# 

# \## Queueing \& Backpressure

# 

# GPU is a shared and limited resource.  

# This project explicitly addresses this by enforcing \*\*controlled concurrency\*\* and \*\*backpressure\*\* at the API layer.

# 

# The goal is not just to “make requests work”, but to ensure \*\*predictable latency, stability, and observability under load\*\*.

# 

# \### Concurrency limit (GPU slots)

# 

# The API Gateway enforces a fixed upper bound on how many requests may actively use the GPU at the same time.

# 

# \- `MAX\_ACTIVE` — maximum number of concurrent GPU-backed requests

# \- Metrics:

# &nbsp; - `api\_active\_requests` — current number of active GPU requests

# &nbsp; - GPU saturation (proxy):

# &nbsp;   - `api\_active\_requests / MAX\_ACTIVE`

# 

# This prevents VRAM exhaustion and latency collapse.

# 

# \### Queue mode vs Reject mode

# 

# Two backpressure strategies are supported:

# 

# \#### Queue mode (`QUEUE\_MODE=queue`)

# \- Requests exceeding `MAX\_ACTIVE` are placed into an in-memory queue

# \- Limits:

# &nbsp; - `QUEUE\_MAX` — maximum queue length

# &nbsp; - `QUEUE\_TIMEOUT\_S` — maximum wait time before failing with 503

# 

# This mode maximizes throughput at the cost of higher tail latency.

# 

# \#### Reject mode (`QUEUE\_MODE=reject`)

# \- Requests are immediately rejected with HTTP 429 when GPU is busy

# \- Suitable when clients support retries with exponential backoff

# 

# This mode prioritizes latency predictability and fast failure.

# 

# \### Why this matters in production

# 

# Without backpressure:

# \- Latency grows unbounded

# \- Queues build up invisibly

# \- The system fails catastrophically under load

# 

# With explicit backpressure:

# \- Latency remains bounded

# \- Failures are intentional and observable (429 / 503)

# \- Bottlenecks are immediately visible in Grafana (queue depth, saturation)

# 

# \### Tuning guidelines

# 

# \- For \*\*maximum throughput\*\*:

# &nbsp; - Increase `MAX\_ACTIVE` cautiously (bounded by GPU memory)

# &nbsp; - Enable queueing with a reasonable timeout

# 

# \- For \*\*strict latency SLOs\*\*:

# &nbsp; - Use `QUEUE\_MODE=reject`

# &nbsp; - Handle retries on the client side

# 

# \- If `api\_queue\_depth` grows continuously:

# &nbsp; - Traffic exceeds GPU capacity, or

# &nbsp; - `MAX\_ACTIVE` is too low, or

# &nbsp; - The model / context size is too heavy

# 

# ---

# 

# \## How to run (local GPU)

# 

# This project is designed to run on a \*\*single GPU machine\*\* using Docker and NVIDIA Container Toolkit.

# 

# It has been tested with:

# \- NVIDIA GPUs (e.g. RTX 3090 / 4090 / A-series)

# \- NVIDIA drivers with CUDA support

# \- Docker + nvidia-container-toolkit

# 

# \### Prerequisites

# 

# \- Docker Engine

# \- Docker Compose v2

# \- NVIDIA driver installed on the host

# \- NVIDIA Container Toolkit (nvidia-ctk)

# 

# Verify GPU access from Docker:

# 

# docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi

# 

# If the GPU is visible, you are ready to proceed.

# 

# \### Project structure

# 

# gpu-llm-inference-service/

# ├── api/                    # FastAPI GPU gateway (queueing, metrics)

# ├── compose/                # docker-compose.yaml

# ├── monitoring/

# │   ├── prometheus/         # Prometheus config

# │   └── grafana/            # Grafana provisioning \& dashboards

# └── README.md

# 

# \### Start the stack

# 

# From the repository root:

# 

# cd compose

# docker compose up -d

# 

# This will start:

# \- vllm — GPU-backed LLM inference server

# \- api — API gateway with queueing \& metrics

# \- open-webui — Web UI (optional)

# \- prometheus — metrics collection

# \- grafana — dashboards

# 

# \### Verify services

# 

# API Gateway health:

# curl http://localhost:8080/health

# 

# vLLM model availability:

# curl http://localhost:8000/v1/models

# 

# Prometheus:

# http://localhost:9090

# 

# Grafana:

# http://localhost:9091

# 

# Default credentials:

# user: admin

# password: admin

# 

# \### Send a test request

# 

# Example chat request via API Gateway:

# 

# curl -X POST http://localhost:8080/v1/chat/completions \\

# &nbsp; -H "Content-Type: application/json" \\

# &nbsp; -d '{

# &nbsp;   "model": "qwen25-14b",

# &nbsp;   "messages": \[

# &nbsp;     { "role": "user", "content": "Hello!" }

# &nbsp;   ]

# &nbsp; }'

# 

# Responses are streamed using Server-Sent Events (SSE).

# 

# \### Stopping the stack

# 

# docker compose down

# 

# ---

# 

# \## Limitations

# 

# \- \*\*Single-node design\*\*

# &nbsp; - The project intentionally targets one GPU host (no multi-node scheduling, no sharding).

# \- \*\*No autoscaling\*\*

# &nbsp; - GPU capacity is fixed; excess load is handled via queueing or rejection.

# \- \*\*Approximate token accounting\*\*

# &nbsp; - Tokens-per-second and token counts are estimated from streaming deltas, not exact tokenizer output.

# \- \*\*No authentication / multi-tenant isolation\*\*

# &nbsp; - API is open by design to keep focus on infrastructure and operations.

# \- \*\*Local-first focus\*\*

# &nbsp; - Not optimized for cloud cost efficiency or managed GPU services out of the box.

# 

# These constraints are deliberate to keep the system understandable and auditable end-to-end.

# 

# ---

# 

# \## What this project demonstrates

# 

# \- \*\*GPU-aware system design\*\*

# &nbsp; - Treating GPU as a scarce, shared resource rather than an infinite backend.

# \- \*\*Production-style LLM serving\*\*

# &nbsp; - vLLM inference with an explicit API gateway instead of direct client access.

# \- \*\*Backpressure and queueing mechanics\*\*

# &nbsp; - Protecting GPU workloads under bursty or sustained load.

# \- \*\*Operational observability\*\*

# &nbsp; - Metrics that matter: latency, queue depth, active requests, throughput.

# \- \*\*Clean separation of concerns\*\*

# &nbsp; - Inference engine, API control plane, and observability stack are isolated.

# \- \*\*Portfolio-level engineering\*\*

# &nbsp; - A realistic system that mirrors how internal LLM services are built, not demo apps.

# 

# This is the kind of project that signals \*\*systems thinking\*\*, not just model usage.

# 

# 



