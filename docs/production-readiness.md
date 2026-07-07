# Production Readiness Notes

This repository is a local portfolio demo, not a production deployment. This document records the production concerns a CTO reviewer should expect to see.

## SLOs

- Search availability target: 99.9% for a managed production service.
- Query latency target: p95 under 250 ms for BM25 and under 500 ms for hybrid search on the expected corpus size.
- Index freshness target: new or updated documents searchable within 60 seconds for batch content pipelines.

## Security

- Local `.env` is ignored; `.env.example` contains non-secret development defaults.
- Production credentials should come from a secret manager, not files.
- TLS should be enabled at the load balancer and between clients and the search cluster.
- Role-based credentials should replace the local `elastic` superuser in any shared environment.

## Observability

- Track request rate, p50/p95/p99 latency, error rate, JVM heap, disk watermarks, indexing latency, refresh time, and rejected thread-pool tasks.
- Log query mode, query length, hit count, latency, and selected filters without logging sensitive user text in regulated environments.
- Monitor relevance drift with scheduled evaluation runs against fixed query judgments.

## Scaling

- Use index lifecycle and shard sizing based on corpus growth, not default shard counts.
- Keep vector fields in dedicated indices when memory and latency requirements diverge from lexical search.
- Tune `num_candidates`, `rank_window_size`, and HNSW parameters with evaluation data rather than intuition.

## Failure Modes

- Search cluster unavailable: the app should fail closed with a clear health message.
- Missing embedding index: disable dense/hybrid modes and continue serving BM25.
- Model download unavailable: use checked-in deterministic embeddings for local demos, and fail the model-backed generation job with actionable instructions.
- Relevance regression: compare new metric output against the baseline benchmark before release.

## Cost Model

- Main cost drivers are search node memory, vector index size, model inference, and ELSER allocation.
- Hybrid retrieval should be justified by measured relevance lift over BM25 at the target latency budget.
