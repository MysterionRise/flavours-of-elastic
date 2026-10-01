# ADR 0004: Deterministic Local Embeddings Plus Optional Model Embeddings

Status: superseded in part by ADR 0005 (2026-10): model-backed embeddings now come from the in-cluster E5
endpoint (`--embeddings e5`); the client-side sentence-transformers path was removed.
Date: 2026-02

## Decision

Use deterministic 384-dimensional local embeddings for the default fresh-clone demo, and keep model-backed `all-MiniLM-L6-v2` generation as an optional upgrade path.

## Rationale

The default demo must work without network access, Hugging Face credentials, or large model downloads. Deterministic local embeddings are lower quality, but they make vector and hybrid retrieval reproducible. Model-backed embeddings can then be used to demonstrate quality improvement.

## Consequences

- `data/load_data.py --embeddings hash` works with checked-in CSV data only.
- `data/load_data.py --embeddings e5` produces model-backed embeddings on the ML stacks.
- Evaluation should clearly distinguish local deterministic vectors from model-backed vectors.
