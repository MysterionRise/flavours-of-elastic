# Flavours of Elastic

[![CI](https://github.com/MysterionRise/flavours-of-elastic/actions/workflows/ci.yml/badge.svg)](https://github.com/MysterionRise/flavours-of-elastic/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Flavours of Elastic is a local AI/search portfolio project and a 4-day Elasticsearch course lab. It demonstrates reproducible search infrastructure, dense vector search, hybrid RRF retrieval, evaluation metrics, Docker operations, and production tradeoff thinking.

## 10-Minute Reviewer Path

```bash
cp .env.example .env
make setup
make demo
```

This starts Elastic Single (waiting until it is healthy), loads the checked-in movie dataset, creates both
lexical and embedding indices, runs the evaluation and opens a Streamlit UI for comparing:

- BM25 lexical search
- dense vector kNN search
- hybrid RRF search — on a trial licence (the ML stacks) Elasticsearch's `rrf` retriever fuses the
  rankings; on a basic licence and on OpenSearch the client fuses them itself, with the same formula

Run the evaluation again at any time (against the running `STACK`):

```bash
make evaluate
```

The evaluator reports `NDCG@10`, `MRR@10`, `Recall@10`, p50 latency, and p95 latency over the hand-labeled query set in `evaluation/movie_queries.yml`.

## What This Proves

- Search architecture: BM25, dense retrieval, hybrid RRF, and optional ELSER paths.
- AI evaluation discipline: labeled queries plus relevance and latency metrics.
- Reproducibility: checked-in CSV data, deterministic local embeddings, Docker Compose stacks, and Make targets.
- Operations thinking: env hygiene, validation scripts, CI, benchmark notes, and production-readiness docs.
- Communication: complete course slides and exercises for a 4-day Elasticsearch curriculum.

## Core Commands

Run `make` for the full list. `STACK` defaults to `elk-single`; `ENV_FILE` defaults to `.env`, falling back to
`.env.example`.

```bash
make setup                  # .venv with dependencies + git hooks (PEP 668-safe)
make test                   # unit tests, compose policy, doc version check (no containers)
make lint                   # every pre-commit hook, same as CI

make up-elk-single          # start a stack and wait until healthy (any docker/<stack>)
make load-small             # load the lexical movies index into the running STACK
make load-embeddings        # load the 384-dim embedding index
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
| Elastic Single | 8.19.x | Default reviewer path, HTTP, auth, low memory |
| Elastic Stack | 8.19.x | Production-like 2-node cluster with TLS |
| Elastic ML | 8.19.x | ELSER, `semantic_text`, ML exercises |
| Elastic 9 | 9.5.x | 9.x track of Elastic Single |
| Elastic ML 9 | 9.5.x | 9.x track of Elastic ML (Day 4) |
| OpenSearch | 2.19.x | Open-source comparison stack |
| OpenSearch 3 | 3.9.x | Next-gen OpenSearch 2-node stack |
| Elastic OSS | 7.10.2 | Legacy Apache-2.0 release (frozen) |

## Data

The checked-in source of truth is `data/movies_enriched.csv` (5,100 movies; `--size small` loads the first 100). It includes MovieLens-derived ratings (`vote_average` 1-10, `vote_count`). Data terms: [data/LICENSE-DATA.md](data/LICENSE-DATA.md).

`data/load_data.py` normalizes rows into:

- `id`, `movieId`, `title`, `title_raw`, `year`
- `genres`
- `overview`
- `abstract_en`, `abstract_kk`, `abstract_fr`
- `description_en`, `description_kk`, `description_fr`
- `searchable_text`
- optional `overview_embedding`

The `--embeddings hash` path uses deterministic 384-dimensional local embeddings so vector and hybrid search work without downloading models. For model-backed embeddings:

```bash
pip install -r requirements-ml.txt
python data/generate_embeddings.py --limit 100
python data/index.py --input data/movies_enriched_with_embeddings.json
```

Additional RAG retrieval examples live in `data/rag_stage1_bm25.py`,
`data/rag_stage2_knn.py`, `data/rag_stage3_hybrid.py`, and
`data/load_hybrid_index.py` for staged BM25, kNN, and hybrid workflows.
They call an LLM through OpenRouter and need your own key in the environment
(`export OPENROUTER_API_KEY=...`); never commit keys to the repository.

## Course Structure

The course materials remain in `course/` and are secondary evidence for teaching and communication.

| Day | Topic | Duration | Stack |
|-----|-------|----------|-------|
| 1 | Fundamentals, core concepts, CRUD | 2h | `elk-single` |
| 2 | Query DSL, full-text/term/bool, ES\|QL | 2h | `elk-single` |
| 3 | Indexing, text analysis, aggregations, nested/join | 3h | `elk-single` or `elastic` |
| 4 | Vector search, ELSER, `semantic_text`, hybrid RRF | 3h | `elk-ml` |

Slide and exercise PDFs: download them from the [latest release](https://github.com/MysterionRise/flavours-of-elastic/releases/latest) or build them with `make slides`. See [course/README.md](course/README.md).

## Running Individual Stacks

```bash
docker compose -f docker/elk-single/docker-compose.yml --env-file .env up
docker compose -f docker/elk/docker-compose.yml --env-file .env up
docker compose -f docker/elk-ml/docker-compose.yml --env-file .env up
docker compose -f docker/elk-9/docker-compose.yml --env-file .env up
docker compose -f docker/elk-ml-9/docker-compose.yml --env-file .env up
docker compose -f docker/opensearch/docker-compose.yml --env-file .env up
docker compose -f docker/opensearch-3/docker-compose.yml --env-file .env up
docker compose -f docker/elk-oss/docker-compose.yml --env-file .env up
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

See [LICENSE](LICENSE).
