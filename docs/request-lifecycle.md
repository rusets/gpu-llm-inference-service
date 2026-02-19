## Request lifecycle

1. **Client request**
   - A client (Open WebUI, curl, or any OpenAI-compatible SDK) sends:
     ```
     POST /v1/chat/completions
     ```
   - Request is sent to the **API Gateway**, not directly to vLLM.

2. **Health & readiness check**
   - API Gateway verifies that vLLM is reachable and has at least one loaded model.
   - If vLLM is unavailable:
     - Request is rejected with `503 Service Unavailable`.

3. **Concurrency gate (GPU protection)**
   - The gateway enforces `MAX_ACTIVE`:
     - This represents the **maximum number of concurrent GPU inference streams**.
   - If a slot is free → request proceeds immediately.
   - If no slot is free:
     - `QUEUE_MODE=queue` → request enters a bounded queue.
     - `QUEUE_MODE=reject` → request fails fast with `429`.

4. **Queueing & backpressure**
   - Queue is bounded (`QUEUE_MAX`).
   - Each queued request:
     - Waits up to `QUEUE_TIMEOUT_S`.
     - If timeout is exceeded → `503 Queue timeout`.
   - Queue depth is tracked as a Prometheus gauge.

5. **Streaming inference**
   - Once a GPU slot is acquired:
     - Request is forwarded to:
       ```
       vLLM /v1/chat/completions (stream=true)
       ```
   - Tokens are streamed back to the client as **Server-Sent Events (SSE)**.
   - Gateway does **not buffer** full responses.

6. **Metrics & accounting**
   - During streaming:
     - Active requests gauge is incremented.
     - Tokens are counted approximately.
     - Time to first token and throughput are estimated.
   - On completion:
     - Latency histogram is observed.
     - GPU slot is released.
     - Queue depth is updated.

7. **Client receives final event**
   - Final SSE frame contains:
     - Approximate token count
     - Total latency
     - Tokens-per-second estimate