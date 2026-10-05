# Flavours of Elastic

[![CI](https://github.com/MysterionRise/flavours-of-elastic/actions/workflows/ci.yml/badge.svg)](https://github.com/MysterionRise/flavours-of-elastic/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Docker Compose stacks for Elasticsearch and OpenSearch, a checked-in movie dataset, and an evaluator
that compares BM25, dense and hybrid (RRF) retrieval on 40 labelled queries. It doubles as the lab for
a 4-day Elasticsearch course.

## Quick start

```bash
cp .env.example .env
make setup
make demo
```

This starts Elastic Single (waiting until it is healthy), loads the checked-in movie dataset, creates both
lexical and embedding indices, runs the evaluation and opens a Streamlit UI for comparing:

- BM25 lexical search
- dense vector kNN search
- hybrid RRF search: on a trial licence (the ML stacks) Elasticsearch's `rrf` retriever fuses the
  rankings; on a basic licence and on OpenSearch the client fuses them itself, with the same formula

For semantic search with in-cluster models (multilingual E5 vectors and ELSER), use an ML stack:

```bash
make up-elk-ml && make load-small load-ml STACK=elk-ml && make evaluate STACK=elk-ml EVAL_MODES=bm25,dense,hybrid_rrf,elser,hybrid_all
```

Run the evaluation again at any time (against the running `STACK`):

```bash
make evaluate
```

The evaluator reports `NDCG@10`, `MRR@10`, `Recall@10`, p50 latency, and p95 latency over the 40 hand-labeled
queries in `evaluation/movie_queries.yml` (English paraphrases, French and Kazakh); `--fail-under
evaluation/floors.yml` turns the per-mode floors into a gate. Results per stack are in
[`docs/benchmark-report.md`](docs/benchmark-report.md).

## What's in it

- Retrieval: BM25, dense (offline hash vectors or in-cluster E5), ELSER and hybrid RRF. RRF uses the
  server-side retriever where the licence allows and client-side fusion elsewhere. Plus RAG with cited answers.
- Evaluation: labelled queries, relevance and latency metrics, and per-mode quality floors enforced in CI.
- Stacks: checked-in CSV data, Docker Compose for Elasticsearch 8.19/9.5 and OpenSearch 2/3, a stack registry
  and Make targets.
- Course: slides and exercises for a 4-day Elasticsearch course; every snippet runs in CI on both
  Elasticsearch tracks.
- Operations: validation scripts, benchmark notes and production-readiness notes.

## Core Commands

Run `make` for the full list. `STACK` defaults to `elk-single`; `ENV_FILE` defaults to `.env`, falling back to
`.env.example`.

```bash
make setup                  # .venv with dependencies + git hooks (PEP 668-safe)
uv sync --locked            # alternative: the locked environment from uv.lock (+ foe-* commands)
make test                   # unit tests, compose policy, doc version check (no containers)
make lint                   # every pre-commit hook, same as CI

make up-elk-single          # start a stack and wait until healthy (any docker/<stack>)
make load-small             # load the lexical movies index into the running STACK
make load-embeddings        # load the 384-dim embedding index (offline hash vectors)
make load-ml                # ML stacks: E5 vectors + ELSER, computed in the cluster
make evaluate               # BM25 + dense + hybrid (EVAL_MODES=... to change)
make down-elk-single        # stop, keeping the data
make reset-elk-single       # stop and DELETE the data

make validate STACK=elk-ml  # full validation in an isolated project (your stack is untouched)
```

Direct commands:

```bash
python data/load_data.py --dataset movies --size small
python data/load_data.py --dataset movies --size full
python data/load_data.py --dataset movies --embeddings hash
python data/load_data.py --dataset movies --embeddings e5 --with-elser   # elk-ml / elk-ml-9
python search/evaluate.py --mode bm25,dense,hybrid_rrf --queries evaluation/movie_queries.yml
streamlit run apps/search_demo/Home.py
```

## Architecture Docs

- [Architecture](docs/architecture.md)
- [Production readiness](docs/production-readiness.md)
- [Benchmark report](docs/benchmark-report.md)
- [ADRs](docs/adrs)

## Supported Stacks

| Stack | Version | Use Case |
|-------|---------|----------|
| Elastic Single | 8.19.x | Default quick-start stack, HTTP, auth, low memory |
| Elastic Stack | 8.19.x | Production-like 2-node cluster with TLS |
| Elastic ML | 8.19.x | ELSER, `semantic_text`, ML exercises |
| Elastic 9 | 9.5.x | 9.x track of Elastic Single |
| Elastic ML 9 | 9.5.x | 9.x track of Elastic ML (Day 4) |
| OpenSearch | 2.19.x | Open-source comparison stack |
| OpenSearch 3 | 3.9.x | Next-gen OpenSearch 2-node stack |
| Elastic OSS | 7.10.2 | Legacy Apache-2.0 release (frozen) |

## Data

The checked-in source of truth is `data/movies_enriched.csv` (5,100 MovieLens movies up to 2002; `--size small` loads a curated 200-movie sample). It includes MovieLens-derived ratings (`vote_average` 1-10, `vote_count`). Data terms: [data/LICENSE-DATA.md](data/LICENSE-DATA.md).

`data/load_data.py` normalizes rows into:

- `id`, `movieId`, `title`, `title_raw`, `year`
- `genres`
- `overview`
- `abstract_en`, `abstract_kk`, `abstract_fr`
- `description_en`, `description_kk`, `description_fr`
- `searchable_text`
- optional `overview_embedding`

The `--embeddings hash` path uses deterministic 384-dimensional local embeddings so vector and hybrid search
work offline on any stack. On the ML stacks (`elk-ml`, `elk-ml-9`), `--embeddings e5 --with-elser` embeds the
movies inside Elasticsearch with the multilingual E5 model and adds an ELSER `semantic_text` field
(see `data/README.md`).

### Retrieval-augmented generation

`python -m search.rag` answers questions about the movies with an LLM (via OpenRouter), grounded in what the
search modes retrieve. Answers cite movie ids (`[318]`) and are checked against the retrieved set:

```bash
python -m search.rag --stage hybrid --retrieve-only --question "films about escaping from prison"
export OPENROUTER_API_KEY=...        # your own key; never commit it
python -m search.rag --stage hybrid  # interactive (stages: bm25, knn, hybrid, elser, hybrid_all)
```

## Course Structure

The course materials live in `course/`.

| Day | Topic | Duration | Stack |
|-----|-------|----------|-------|
| 1 | Fundamentals, core concepts, CRUD | 2h | `elk-single` / `elk-9` |
| 2 | Query DSL, full-text/term/bool, ES\|QL | 2h | `elk-single` / `elk-9` |
| 3 | Indexing, text analysis, aggregations, nested/join | 3h | `elk-single` / `elk-9` |
| 4 | Vector search, ELSER, `semantic_text`, hybrid RRF | 3h | `elk-ml` / `elk-ml-9` |

Slide and exercise PDFs: download them from the [latest release](https://github.com/MysterionRise/flavours-of-elastic/releases/latest) or build them with `make slides`. See [course/README.md](course/README.md).

## Running Individual Stacks

```bash
# <stack>: elk-single, elk, elk-ml, elk-9, elk-ml-9, opensearch, opensearch-3, elk-oss
docker compose -f docker/<stack>/docker-compose.yml --env-file .env up
```

## Requirements

- Docker 20.10+ with the Compose v2 plugin (`docker compose`, 2.20+)
- Python 3.11+
- ~4GB of Docker memory for Elastic Single / Elastic 9
- ~10GB of Docker memory for Elastic ML / Elastic ML 9 (two 4GB ML nodes + Kibana)

The multi-node stacks enforce Elasticsearch's bootstrap checks and need
`vm.max_map_count` of at least 262144 (Linux host, or the Docker VM on macOS/Windows):

```bash
sudo sysctl -w vm.max_map_count=262144                  # Linux
rdctl shell sudo sysctl -w vm.max_map_count=262144      # Rancher Desktop
```

All stacks publish ports on `127.0.0.1` only and share 9200/5601, so run one
at a time (or override `ES_PORT` / `KIBANA_PORT` in `.env`). Bring a stack up
and wait until it is healthy with `up -d --wait`.

## Validation

```bash
python validate.py --stack elk-single          # one stack (isolated project, torn down afterwards)
python validate.py --stack all                 # every stack, one after another
python validate.py --stack elk-ml --port-offset 10000   # while your own stack holds 9200/5601
python validate.py --list                      # registered stacks and versions
```

Validation never touches the stack you started yourself or its data volumes.

## License

MIT, see [LICENSE](LICENSE).
