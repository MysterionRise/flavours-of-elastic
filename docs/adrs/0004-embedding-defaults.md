# ADR 0004: Deterministic Local Embeddings Plus Optional Model Embeddings

## Decision

Use deterministic 384-dimensional local embeddings for the default fresh-clone demo, and keep model-backed `all-MiniLM-L6-v2` generation as an optional upgrade path.

## Rationale

The default demo must work without network access, Hugging Face credentials, or large model downloads. Deterministic local embeddings are lower quality, but they make vector and hybrid retrieval reproducible. Model-backed embeddings can then be used to demonstrate quality improvement.

## Consequences

- `data/load_data.py --with-embeddings` works with checked-in CSV data only.
- `data/generate_embeddings.py` can produce model-backed embeddings when ML extras are installed.
- Evaluation should clearly distinguish local deterministic vectors from model-backed vectors.
