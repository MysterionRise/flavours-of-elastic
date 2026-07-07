# ADR 0002: Compare Dense, Sparse, and Hybrid Retrieval

## Decision

Expose BM25, dense vector, hybrid RRF, and optional ELSER paths instead of choosing one retrieval strategy.

## Rationale

The portfolio goal is to show AI/search judgment. A comparison demo with evaluation metrics is stronger evidence than a single search mode because it shows quality, latency, and operational tradeoffs.

## Consequences

- `search/evaluate.py` reports metrics per retrieval mode.
- The Streamlit app compares modes side by side.
- ELSER remains optional because it requires the heavier `elk-ml` stack.
