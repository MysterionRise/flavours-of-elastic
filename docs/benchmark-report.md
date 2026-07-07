# Benchmark Report

The `benchmarks/` directory contains historical Rally-style benchmark outputs for Elasticsearch and OpenSearch workloads.

## What Exists

- `benchmarks/elk-geonames1.rep` and `.csv`: Elasticsearch geonames benchmark output.
- `benchmarks/odfe-geonames1.rep` and `.csv`: OpenSearch/ODFE geonames benchmark output.
- `benchmarks/odfe-noaa1.csv`: OpenSearch/ODFE NOAA benchmark output.

## How To Read It

The report files include:

- indexing throughput and latency
- query throughput and latency
- merge, refresh, flush, and GC timings
- store and translog size
- task-level error rates

## Portfolio Interpretation

These artifacts prove familiarity with search benchmark tooling, but they are not yet a controlled comparison because hardware, JVM settings, corpus versions, and run dates are not documented alongside the results.

The next portfolio-grade benchmark should include:

- exact machine specs and Docker resource limits
- stack version and compose file
- corpus and track configuration
- warmup duration and run duration
- p50/p95/p99 latency
- error rate
- plain-English conclusion about the engineering decision made from the data

## Next Benchmark Target

Add a local semantic-search benchmark that compares:

- BM25 over `movies`
- deterministic dense kNN over `movies-embeddings`
- hybrid RRF over `movies-embeddings`
- optional model-backed dense vectors
- optional ELSER over `elk-ml`

The benchmark should publish relevance metrics and latency together, because CTO-level search decisions require both quality and cost/latency evidence.
