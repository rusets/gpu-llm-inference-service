# Limitations

This project is intentionally designed as a single-node, infrastructure-focused system.  
The following constraints are deliberate.

## Single-node design

- Runs on one GPU host.
- No multi-node scheduling, sharding, or horizontal scaling.
- No distributed coordination layer.

## No autoscaling

- GPU capacity is fixed.
- Excess load is handled via queueing or rejection.
- No automatic scaling of inference backends.

## Approximate token accounting

- Tokens-per-second and token counts are estimated from streaming deltas.
- Exact tokenizer-based accounting is not implemented in the gateway.

## No authentication or multi-tenant isolation

- The API is intentionally open.
- No rate limits per user.
- No tenant isolation model.

## Local-first focus

- Designed for local GPU hosts.
- Not optimized for managed cloud GPU platforms.
- No production-ready secrets management or identity layer.