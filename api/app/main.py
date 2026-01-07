import asyncio
import json
import time
from dataclasses import dataclass
from typing import AsyncGenerator, Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest


@dataclass
class Settings:
    vllm_base_url: str
    model: str
    max_active: int
    queue_mode: str  # "queue" or "reject"
    queue_max: int
    queue_timeout_s: float
    request_timeout_s: float


def load_settings() -> Settings:
    import os

    return Settings(
        vllm_base_url=os.getenv("VLLM_BASE_URL", "http://vllm:8000"),
        model=os.getenv("MODEL_NAME", "qwen25-14b"),
        max_active=int(os.getenv("MAX_ACTIVE", "2")),
        queue_mode=os.getenv("QUEUE_MODE", "queue").lower(),
        queue_max=int(os.getenv("QUEUE_MAX", "100")),
        queue_timeout_s=float(os.getenv("QUEUE_TIMEOUT_S", "120")),
        request_timeout_s=float(os.getenv("REQUEST_TIMEOUT_S", "300")),
    )


S = load_settings()
app = FastAPI(title="GPU LLM API Gateway", version="1.0")

sema = asyncio.Semaphore(S.max_active)
wait_queue: "asyncio.Queue[float]" = asyncio.Queue(maxsize=S.queue_max)

REQS_TOTAL = Counter(
    "api_requests_total",
    "Total API requests",
    ["endpoint", "status"],
)

ACTIVE = Gauge(
    "api_active_requests",
    "Number of active GPU requests",
)

QUEUE_DEPTH = Gauge(
    "api_queue_depth",
    "Number of queued requests waiting for GPU",
)

LATENCY = Histogram(
    "api_request_latency_seconds",
    "End-to-end request latency (seconds)",
    ["endpoint"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 40, 80, 160),
)

READY = {"ok": False}


class HTTPError(Exception):
    def __init__(self, status: int, message: str, retry_after: int = 0):
        self.status = status
        self.message = message
        self.retry_after = retry_after
        super().__init__(message)


def _drain_one(wait_start: float) -> None:
    items = []
    try:
        while True:
            items.append(wait_queue.get_nowait())
    except Exception:
        pass

    kept = []
    removed = False
    for x in items:
        if (not removed) and x == wait_start:
            removed = True
            continue
        kept.append(x)

    for x in kept:
        try:
            wait_queue.put_nowait(x)
        except Exception:
            break


async def acquire_slot_or_queue() -> Optional[float]:
    try:
        await asyncio.wait_for(sema.acquire(), timeout=0.0)
        return None
    except Exception:
        if S.queue_mode == "reject":
            raise HTTPError(429, "GPU busy", retry_after=2)

        if wait_queue.full():
            raise HTTPError(429, "Queue full", retry_after=5)

        wait_start = time.monotonic()
        await wait_queue.put(wait_start)
        QUEUE_DEPTH.set(wait_queue.qsize())

        try:
            await asyncio.wait_for(sema.acquire(), timeout=S.queue_timeout_s)
        except asyncio.TimeoutError:
            _drain_one(wait_start)
            QUEUE_DEPTH.set(wait_queue.qsize())
            raise HTTPError(503, "Queue timeout", retry_after=5)

        _drain_one(wait_start)
        QUEUE_DEPTH.set(wait_queue.qsize())
        return wait_start


@app.get("/metrics")
async def metrics():
    data = generate_latest()
    return PlainTextResponse(content=data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health():
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{S.vllm_base_url}/v1/models")
            if r.status_code != 200:
                READY["ok"] = False
                return JSONResponse({"status": "degraded", "vllm": r.status_code}, status_code=503)

            data = r.json()
            models = [m.get("id") for m in data.get("data", []) if isinstance(m, dict)]
            if not models:
                READY["ok"] = False
                return JSONResponse({"status": "starting", "vllm": "no_models"}, status_code=503)

    except Exception:
        READY["ok"] = False
        return JSONResponse({"status": "down", "vllm": "unreachable"}, status_code=503)

    READY["ok"] = True
    return {"status": "ok", "models": models}


@app.get("/v1/models")
async def v1_models():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{S.vllm_base_url}/v1/models")
        return Response(
            content=r.content,
            status_code=r.status_code,
            media_type=r.headers.get("content-type", "application/json"),
        )
    except Exception as ex:
        return JSONResponse({"error": {"message": str(ex)[:500]}}, status_code=502)


@app.post("/v1/chat/completions")
async def v1_chat_completions(request: Request):
    start = time.monotonic()
    endpoint = "/v1/chat/completions"

    try:
        body = await request.json()
    except Exception:
        REQS_TOTAL.labels(endpoint=endpoint, status="400").inc()
        return JSONResponse({"error": {"message": "invalid_json"}}, status_code=400)

    if "model" not in body or not body.get("model"):
        body["model"] = S.model

    stream = bool(body.get("stream", False))

    try:
        await acquire_slot_or_queue()
    except HTTPError as e:
        REQS_TOTAL.labels(endpoint=endpoint, status=str(e.status)).inc()
        headers = {}
        if e.retry_after:
            headers["Retry-After"] = str(e.retry_after)
        return JSONResponse({"error": {"message": e.message}}, status_code=e.status, headers=headers)

    ACTIVE.inc()
    QUEUE_DEPTH.set(wait_queue.qsize())

    timeout = httpx.Timeout(
        timeout=S.request_timeout_s,
        connect=5.0,
        read=S.request_timeout_s,
        write=S.request_timeout_s,
    )

    async def finalize(status: str):
        duration = time.monotonic() - start
        LATENCY.labels(endpoint=endpoint).observe(duration)
        REQS_TOTAL.labels(endpoint=endpoint, status=status).inc()
        ACTIVE.dec()
        sema.release()
        QUEUE_DEPTH.set(wait_queue.qsize())

    if not stream:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(
                    f"{S.vllm_base_url}/v1/chat/completions",
                    headers={"Content-Type": "application/json"},
                    json=body,
                )
            await finalize(str(r.status_code))
            return Response(
                content=r.content,
                status_code=r.status_code,
                media_type=r.headers.get("content-type", "application/json"),
            )
        except Exception as ex:
            await finalize("502")
            return JSONResponse({"error": {"message": str(ex)[:500]}}, status_code=502)

    async def stream_proxy() -> AsyncGenerator[bytes, None]:
        status_for_metrics = "200"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{S.vllm_base_url}/v1/chat/completions",
                    headers={"Content-Type": "application/json"},
                    json=body,
                ) as r:
                    status_for_metrics = str(r.status_code)

                    if r.status_code != 200:
                        msg = (await r.aread()).decode("utf-8", errors="ignore")
                        err = {"error": {"message": msg[:500], "status": r.status_code}}
                        yield f"data: {json.dumps(err)}\n\n".encode("utf-8")
                        yield b"data: [DONE]\n\n"
                        return

                    async for chunk in r.aiter_raw():
                        if chunk:
                            yield chunk

        except Exception as ex:
            status_for_metrics = "502"
            err = {"error": {"message": str(ex)[:500]}}
            yield f"data: {json.dumps(err)}\n\n".encode("utf-8")
            yield b"data: [DONE]\n\n"
        finally:
            await finalize(status_for_metrics)

    return StreamingResponse(stream_proxy(), media_type="text/event-stream")