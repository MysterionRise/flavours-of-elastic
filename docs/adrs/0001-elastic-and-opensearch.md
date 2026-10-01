# ADR 0001: Keep Elastic and OpenSearch Stacks

Status: accepted, amended 2026-10 (OpenSearch now runs dense and hybrid search too — client-side fusion, `knn_vector`)
Date: 2026-02

## Decision

Keep both Elastic and OpenSearch stacks in the repository, but make Elastic Single the default portfolio reviewer path.

## Rationale

Elastic Single gives the lowest-friction local demo and supports the default BM25, dense vector, and hybrid RRF workflow. OpenSearch remains valuable course material and comparison infrastructure, but its vector APIs differ enough that it should not be the default demo target.

## Consequences

- README and Make targets optimize for Elastic Single.
- OpenSearch remains validated as infrastructure, not as the primary semantic demo.
- Future OpenSearch vector support should be implemented as a separate compatibility track.
