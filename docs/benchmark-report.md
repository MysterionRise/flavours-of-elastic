# Benchmark Report

Search quality and latency of every retrieval mode, per stack, measured with the repository's own tools. The raw
reports are in [`benchmarks/`](benchmarks/) (`<stack>.json` from `search/evaluate.py --output`, `<stack>.load-*.json`
from `data/load_data.py --json`).

## Setup

- **Machine:** Apple M4 Pro laptop, macOS, Rancher Desktop (Docker 29.1) with 4 CPUs and 16 GB for the VM;
  arm64 images. Run on 2026-10-01.
- **Stacks:** the compose files of this repository with their default limits (`ML_NODE_MEM_LIMIT=4g`), started in
  isolated projects by `scripts.with_stack`; versions from `.env.example` (Elasticsearch 8.19.x and 9.5.x,
  OpenSearch 3.9.x).
- **Data:** the curated small sample, 200 movies (`--size small`); `movies-embeddings` with hash vectors, or E5 +
  ELSER on the ML stacks.
- **Queries:** the 40 graded queries of `evaluation/movie_queries.yml` — 24 descriptive, 12 conceptual paraphrases,
  2 French, 2 Kazakh — at k = 10, `num_candidates` 50, RRF `rank_constant` 60.
- **Latency:** client-side round trip per query (Python, localhost), p50/p95 over the 40 queries; one run each, no
  warm-up beyond the load. Treat it as relative, not as capacity numbers.

Reproduce one stack:

```bash
python -m scripts.with_stack elk-ml-9 -- sh -c '
  python data/load_data.py --size small &&
  python data/load_data.py --size small --embeddings e5 --with-elser &&
  python search/evaluate.py --mode bm25,dense,hybrid_rrf,elser,hybrid_all --fail-under evaluation/floors.yml'
```

## Quality (k = 10)

| Stack | Mode | Embedding | Fusion | NDCG | MRR | Recall |
|-------|------|-----------|--------|-----:|----:|-------:|
| any | bm25 | — | — | 0.930 | 0.924 | 0.967 |
| elk-single (8.19, basic) | dense | hash | — | 0.685 | 0.650 | 0.817 |
| elk-9 (9.5, basic) | dense | hash | — | 0.731 | 0.709 | 0.817 |
| opensearch-3 | dense | hash | — | 0.727 | 0.697 | 0.842 |
| elk-single | hybrid_rrf | hash | client | 0.882 | 0.883 | 0.912 |
| elk-9 | hybrid_rrf | hash | client | 0.895 | 0.896 | 0.925 |
| opensearch-3 | hybrid_rrf | hash | client | 0.894 | 0.896 | 0.925 |
| elk-ml (8.19, trial) / elk-ml-9 (9.5, trial) | dense | E5 | — | **0.947** | 0.933 | **0.988** |
| elk-ml / elk-ml-9 | hybrid_rrf | E5 | server | 0.956 | 0.958 | 0.967 |
| elk-ml / elk-ml-9 | elser | ELSER | — | 0.899 | 0.904 | 0.912 |
| elk-ml / elk-ml-9 | hybrid_all (BM25 + E5 + ELSER) | E5 | server | **0.970** | **0.975** | 0.975 |

BM25 scores the same everywhere. With the in-cluster models, 8.19 and 9.5 give identical results; with hash
vectors the approximate kNN differs a little between engines and versions.

## Latency (ms, p50 / p95)

| Mode | elk-single | elk-9 | opensearch-3 | elk-ml | elk-ml-9 |
|------|-----------:|------:|-------------:|-------:|---------:|
| bm25 | 3.6 / 5.3 | 4.2 / 6.5 | 9.3 / 21.8 | 3.2 / 11.5 | 2.6 / 7.4 |
| dense | 3.5 / 5.7 | 5.8 / 40.4 | 10.3 / 24.3 | 73.9 / 108.5 | 52.7 / 78.8 |
| hybrid_rrf | 13.4 / 21.9 | 12.7 / 14.8 | 20.1 / 22.5 | 8.1 / 29.5 | 7.5 / 9.0 |
| elser | | | | 205.3 / 366.0 | 148.8 / 263.2 |
| hybrid_all | | | | 14.4 / 28.8 | 11.0 / 30.8 |

- Dense with E5 includes embedding the query on the ML node (`query_vector_builder`), ~50–75 ms on CPU; with hash
  vectors the client embeds in microseconds.
- ELSER's sparse queries are the slowest single mode at this size (query expansion plus many weighted terms).
- Server-side hybrid is faster than its own dense leg here: Elasticsearch caches the query embedding within the
  request, and the client-side fusion pays two round trips.

## Load times (200 movies)

| Stack | `movies` | `movies-embeddings` | Model deployment on first use |
|-------|---------:|--------------------:|------------------------------|
| elk-single, elk-9, opensearch-3 | < 1 s | < 1 s (hash) | — |
| elk-ml (8.19) | 1.5 s | 461 s (E5 + ELSER) | E5 26 s, ELSER 22 s |
| elk-ml-9 (9.5) | 0.7 s | 324 s (E5 + ELSER) | E5 45 s, ELSER < 1 s (after E5) |

ELSER inference at ingest dominates; x86 CI runners load the same sample in a few minutes too.

## Conclusions

- **In-cluster E5 is the biggest quality lever:** dense NDCG@10 0.73 → 0.95 over hash vectors, and it finds the
  French and Kazakh queries that hash vectors and BM25 miss.
- **Hybrid helps most when one leg is weak:** with hash vectors, hybrid recovers most of BM25's quality; with E5,
  three-way hybrid is the best mode on every metric except recall, where E5 alone finds slightly more.
- **Client-side fusion is a good fallback:** on a basic licence and OpenSearch it gives the same scores as server
  fusion would with the same legs; the cost is a second round trip.
- **Costs:** E5 and ELSER need ~2 GB of ML memory each, a trial or paid licence, and minutes of ingest per few
  hundred documents on CPU; budget that before choosing semantic modes for a large corpus.

## Historical benchmarks

Older Rally geonames and NOAA reports for Elasticsearch and OpenSearch/ODFE were removed in `d3df72d` (git history
keeps them). Their hardware, versions and settings were never recorded, so they were not comparable with each other
or with the numbers above.
