# ADR 0005: In-Cluster E5 and ELSER for Semantic Search and RAG

Status: accepted
Date: 2026-10

## Decision

Semantic search uses Elasticsearch's preconfigured inference endpoints: multilingual E5
(`.multilingual-e5-small-elasticsearch`, 384-dim dense) through an ingest pipeline and `query_vector_builder`,
and ELSER (`.elser-2-elasticsearch`) through `semantic_text`. The RAG demo (`python -m search.rag`) retrieves
through the same client. The client-side sentence-transformers / EmbeddingGemma pipeline is removed.

## Rationale

- A fresh clone could not reproduce the old pipeline: it needed a 768-dim model service, a hand-built index and
  pasted query vectors.
- In-cluster models work on Apple Silicon and x86 alike (the endpoints pick the right model build), need no
  Python ML dependencies, and teach the APIs students will use in production (Inference API, pipelines,
  `semantic_text`, retrievers).
- Measured on the small sample (40 graded queries): E5 dense NDCG@10 0.947 vs 0.73 for hash vectors; three-way
  hybrid 0.970; identical on 8.19 and 9.5.

## Consequences

- Day 4 and the ML smoke tests need `elk-ml` / `elk-ml-9`: a trial licence and ~2 GB of ML memory per model.
- First use downloads ~0.9 GB of models; `data/load_data.py --warm-only` deploys them ahead of time, and the
  loader exits 6 when they do not deploy in time.
- The offline hash embedder stays for stacks without ML (any Elasticsearch 8+/9+, OpenSearch) and for CI.
- The index `_meta` records the embedding backend, so queries are always embedded like the documents.
