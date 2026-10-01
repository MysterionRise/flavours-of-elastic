# ADR 0007: Licence-Aware Hybrid Search

Status: accepted
Date: 2026-10

## Decision

Hybrid search uses Elasticsearch's `rrf` retriever when the licence allows it (trial or enterprise) and fuses
the BM25 and kNN rankings client-side with the same formula otherwise (basic licence, OpenSearch).
Capabilities come from the cluster itself (`search/capabilities.py`), not from configuration.

## Rationale

- The `rrf` and `linear` retrievers need an enterprise or trial licence; the default stacks run the basic
  licence, so `make demo` failed on `elk-single`.
- Client-side RRF needs no tuning, gives comparable quality (NDCG@10 0.88 client vs 0.90 server on the small
  sample) and works on every engine with vectors.

## Consequences

- `SearchResponse.fusion` and the evaluation report say which fusion ran.
- The course teaches the server-side retriever on the trial-licensed ML stacks and mentions the fallback.
- Evaluation floors (`evaluation/floors.yml`) gate every mode in CI, per embedding backend.
