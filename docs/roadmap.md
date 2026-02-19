# Roadmap

This roadmap outlines potential improvements that would move the system
closer to a production-grade GPU inference platform.

The current version focuses on single-node control, observability, and deterministic backpressure.

---

## Short-Term Improvements

### Semantic Caching (Redis)

Reduce redundant GPU work by caching repeated prompts.

- Cache key: model + prompt + decoding parameters
- Cache only successful responses
- Optional TTL for memory control
- Metrics for cache hit rate

Impact:
- Lower GPU utilization under repeated traffic
- Reduced latency for identical queries

---

### Precise Token Accounting

Replace approximate token counting with exact tokenizer-based accounting.

- Use model tokenizer inside gateway
- Track:
  - prompt tokens
  - completion tokens
  - total tokens
- Expose metrics per request

Impact:
- Accurate usage metrics
- Cost modeling readiness
- Better throughput visibility

---

## Mid-Term Improvements

### Request Prioritization

Introduce request classes to differentiate traffic types.

- High priority (interactive)
- Low priority (batch)
- Basic fairness logic
- Starvation protection

Impact:
- Improved tail latency for critical traffic
- More realistic production behavior

---

### Multiple vLLM Backends

Support routing across multiple GPU inference backends.

- Static backend list
- Simple round-robin or load-aware routing
- Health-based routing
- Backend-level metrics

Impact:
- Horizontal scaling capability
- Increased throughput ceiling

---

## Long-Term Improvements

### Kubernetes Deployment

Deploy the system to Kubernetes.

- Separate control plane and inference plane
- Custom metrics adapter (queue depth, saturation)
- HPA based on real load signals
- GPU-aware scheduling

Impact:
- Closer alignment with production environments
- Control-plane scaling independent of GPU nodes

---

### Distributed Rate Limiting & Authentication

Introduce basic identity and traffic isolation.

- API keys
- Per-user rate limits
- Optional quota enforcement
- Metrics per identity

Impact:
- Multi-tenant readiness
- Safer public exposure

---

## Design Principle

Future improvements must preserve:

- Deterministic backpressure
- Explicit concurrency control
- Measurable saturation
- Clear separation of inference and control layers