# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Flavours of Elastic is an educational repository for a **4-day Elasticsearch course**, providing Docker Compose configurations for running and comparing Elasticsearch-based search engines with support for modern features like vector search and semantic search.

### Available Stacks

1. **Elastic Single** (8.19.x) - Beginner-friendly single-node, HTTP, auth, 4GB RAM
2. **Elastic Stack** (8.19.x) - Production-like 2-node cluster, HTTPS + auth
3. **Elastic ML** (8.19.x) - ML-enabled for ELSER/vector search, ~10GB Docker memory
4. **Elastic 9** (9.5.x) - Next-gen single-node, HTTP, auth, 4GB RAM (9.x track of Elastic Single)
5. **Elastic ML 9** (9.5.x) - 9.x track of Elastic ML: 2-node TLS cluster, trial license, ~10GB Docker memory
6. **OpenSearch** (2.19.x) - Open-source alternative with Dashboards, HTTPS + auth
7. **OpenSearch 3** (3.9.x) - Next-gen 2-node cluster, HTTPS + auth
8. **Elasticsearch OSS** (7.10.2) - Legacy Apache-2.0 release, HTTP, no auth (frozen)

## Common Commands

### Running Stacks

```bash
# Elastic Single (beginners, 4GB RAM)
docker compose -f docker/elk-single/docker-compose.yml --env-file .env up

# Elastic Stack (auth: elastic/elastic)
docker compose -f docker/elk/docker-compose.yml --env-file .env up

# Elastic ML (for ELSER/semantic search, ~10GB Docker memory)
docker compose -f docker/elk-ml/docker-compose.yml --env-file .env up

# Elastic 9 (next-gen, 4GB RAM)
docker compose -f docker/elk-9/docker-compose.yml --env-file .env up

# Elastic ML 9 (Day 4 on the 9.x track, ~10GB Docker memory)
docker compose -f docker/elk-ml-9/docker-compose.yml --env-file .env up

# OpenSearch (auth: admin/MyStrongPassword123!)
docker compose -f docker/opensearch/docker-compose.yml --env-file .env up

# OpenSearch 3 (auth: admin/MyStrongPassword123!)
docker compose -f docker/opensearch-3/docker-compose.yml --env-file .env up

# Elasticsearch OSS (no auth)
docker compose -f docker/elk-oss/docker-compose.yml --env-file .env up
```

### Make Targets

`make` lists everything. `STACK` defaults to `elk-single`, `ENV_FILE` to `.env` (falls back to `.env.example`).
`make setup` (venv + hooks), `make test` (unit + compose policy + doc versions), `make lint`, `make up-<stack>`
(waits until healthy), `make down-<stack>` (keeps data), `make reset-<stack>` (deletes data), `make load-small`,
`make load-embeddings`, `make evaluate` and `make demo` (all against the running `STACK`), `make validate STACK=...`.

### Loading Sample Data

```bash
# Load the curated small sample (200 movies) into `movies`
python data/load_data.py --dataset movies --size small

# Load the full dataset (5,100 movies)
python data/load_data.py --dataset movies --size full

# Load `movies-embeddings` with 384-d hash vectors (offline toy embeddings)
python data/load_data.py --dataset movies --embeddings hash

# ML stacks: in-cluster E5 vectors (ingest pipeline) + ELSER semantic_text; --warm-only just deploys the models
python data/load_data.py --dataset movies --embeddings e5 --with-elser

# Pick the cluster explicitly, skip reloads of identical data, print a JSON summary
python data/load_data.py --stack elk-ml --size full --skip-if-current --json
```

The loader lives in `search/loader.py` (`data/load_data.py` is the entry point the course uses). It finds the
cluster via `--stack`, `--url`, the environment from `scripts.with_stack`, or auto-detection (a 401 never
counts as found), and exits 0 ok, 2 usage, 3 connection/credentials, 4 refused (e.g. vectors on OSS), 5 partial
load, 6 inference not ready (`search/inference.py` waits for the E5/ELSER deployments). `search/connection.py` (retries, readable `EsError`), `search/capabilities.py` (distribution, licence,
ML nodes) and `search/mappings.py` (explicit `int8_hnsw` / OpenSearch `knn_vector`, `_meta`) are shared with
the search client: `search/client.py` builds bodies with `search/queries.py`, embeds queries with the model
recorded in the index `_meta` (`search/embedders.py`), and runs `hybrid_rrf` with the `rrf` retriever on a
trial licence or fuses client-side otherwise. `search/evaluate.py --fail-under evaluation/floors.yml`
fails below the per-mode quality floors (CI runs it in `scripts/smoke_data.py`).

### Validation & Testing

```bash
# Validate one stack, several, or all (each runs in an isolated compose project
# `foe-validate-<stack>` and is torn down afterwards; your own stack and data are untouched)
python validate.py --stack elk-single
python validate.py --stack elk-ml,opensearch-3
python validate.py --stack all

# Your stack holds 9200/5601? Validate an isolated copy on other ports
python validate.py --stack elk-single --port-offset 10000

# The stack registry (what CI builds its matrix from)
python validate.py --list [--json]

# Run any command against a stack (started in isolation, or --attach to a running one)
python -m scripts.with_stack elk-ml -- python search/evaluate.py --mode bm25,dense

# Unit tests and the compose policy check (no containers needed for the tests)
python -m unittest discover -s tests
python -m scripts.check_compose
```

### Code Quality

```bash
# Install pre-commit hooks (run once)
pip install -r requirements-dev.txt
pre-commit install

# Run all checks manually (same as the CI lint job)
pre-commit run --all-files
```

Pre-commit runs (all versions pinned in `.pre-commit-config.yaml`): pre-commit-hooks (yaml/toml/json, whitespace,
line endings, merge conflicts, large files, private keys), ruff check + ruff format (config in `pyproject.toml`:
format width 88, lint limit 120), gitleaks (config in `.gitleaks.toml`), yamllint (`.yamllint.yaml`), actionlint,
and check-jsonschema for GitHub workflows (every job needs `timeout-minutes`).

### Cleanup

```bash
docker compose -f docker/<stack>/docker-compose.yml down -v
```

## Architecture

### Directory Structure

- `docker/elk-single/` - Single-node for beginners (HTTP, auth)
- `docker/elk/` - Elastic Stack with TLS cert generation and 2-node cluster
- `docker/elk-ml/` - ML-enabled 2-node cluster for ELSER
- `docker/elk-9/` - Elasticsearch 9 single-node (HTTP, auth)
- `docker/elk-ml-9/` - ML-enabled 2-node cluster on Elasticsearch 9 (same as elk-ml, 9.x track)
- `docker/opensearch/` - OpenSearch 2-node cluster with Dashboards
- `docker/opensearch-3/` - OpenSearch 3 two-node cluster with Dashboards
- `docker/elk-oss/` - Elasticsearch OSS 2-node cluster, legacy
- `data/` - Sample datasets, data loader, and enrichment pipeline scripts
- `data/load_data.py` - Entry point of the data loader (`search/loader.py`) used by the course
- `data/generate_descriptions.py` - Generate multilingual descriptions via OpenRouter LLM API
- `data/generate_embeddings.py` - Generate 768-dim embeddings via EmbeddingGemma-300M
- `data/index.py` - Index enriched movies with embeddings into Elasticsearch
- `data/movies_enriched.csv` - 5100 movies with multilingual abstracts/descriptions and MovieLens ratings
  (`vote_average` 1-10, `vote_count`); `--size small` loads the curated 200-movie sample
- `data/add_ratings.py` - maintainer tool that computes the rating columns from MovieLens ml-32m
- `data/build_sample.py` + `data/sample.yml` - deterministic curated `--size small` sample (200 movies) written to
  `data/movies_small_ids.txt`; always contains the films listed in `course/movies.yml`
- `search/movies.py` - title normalisation ("Godfather, The" -> "The Godfather", alternate titles -> `title_aka`)
- `course/movies.yml` - the films the course may name (+ stand-ins for post-2002 films, which are not in the data)
- `data/LICENSE-DATA.md` - MovieLens terms (attribution, non-commercial) and synthetic-text disclosure
- `course/` - Marp Markdown slides and exercises for the 4-day course
- `course/README.md` - Course build instructions for Marp CLI
- `course/theme/epam.css` - Custom Marp theme (black bg #000000 + cyan accent #00F6FF)
- `course/day1-fundamentals/` - Day 1 slides (~53) and exercises (6 tasks, 14 subtasks)
- `course/day2-query-dsl/` - Day 2 slides (~54) and exercises (13 tasks)
- `course/day3-indexing-analysis/` - Day 3 slides (~59) and exercises (19 tasks across 4 parts)
- `course/day4-semantic-search/` - Day 4 slides (~52) and exercises (18 tasks across 4 parts)
- `data/embedding_service.py` - Embedding generation service for vector search
- `data/load_hybrid_index.py` - Load hybrid (BM25 + vector) index
- `data/rag_stage1_bm25.py` - RAG demo: BM25 retrieval stage
- `data/rag_stage2_knn.py` - RAG demo: kNN retrieval stage
- `data/rag_stage3_hybrid.py` - RAG demo: hybrid retrieval (BM25 + kNN)
- `validate.py` - Stack validation script with OOP design
- `.marprc.yml` - Marp CLI configuration (theme and font settings)
- `.env.example` - Environment variable template with documentation

### Stack Differences

| Stack | Protocol | Auth | JVM Heap | Container limits (ES + UI) | Nodes | License / ML |
|-------|----------|------|----------|----------------------------|-------|--------------|
| Elastic Single | HTTP | elastic/elastic | 1GB | 2GB + 2GB | 1 | `LICENSE` (basic) |
| Elastic Stack | HTTPS | elastic/elastic | 1GB x2 | 2GB x2 + 2GB | 2 | `LICENSE` (basic) |
| Elastic ML | HTTPS | elastic/elastic | 1GB x2 | 4GB x2 + 2GB (ML: 2GB/node) | 2 | `ELK_ML_LICENSE` (trial): ELSER, RRF |
| Elastic 9 | HTTP | elastic/elastic | 1GB | 2GB + 2GB | 1 | `LICENSE` (basic) |
| Elastic ML 9 | HTTPS | elastic/elastic | 1GB x2 | 4GB x2 + 2GB (ML: 2GB/node) | 2 | `ELK_ML_LICENSE` (trial): ELSER, RRF |
| OpenSearch | HTTPS | admin/MyStrongPassword123! | 1GB x2 | 2GB x2 + 2GB | 2 | n/a |
| OpenSearch 3 | HTTPS | admin/MyStrongPassword123! | 1GB x2 | 2GB x2 + 2GB | 2 | n/a |
| OSS | HTTP | none | 512MB x2 | 1GB x2 + 1.5GB | 2 | n/a |

All stacks bind to 127.0.0.1, fail fast when `--env-file` is missing, and become healthy under
`docker compose ... up -d --wait`. Heap and limits are overridable (`ES_HEAP`, `ES_MEM_LIMIT`,
`KIBANA_MEM_LIMIT`, `ML_NODE_HEAP`, `ML_NODE_MEM_LIMIT`; see `.env.example`). `scripts/check_compose.py`
enforces these rules in CI.

### Stack Registry and Validation

- `scripts/stacks.py` - the single source of truth for every stack (compose file, URL, auth variables, version
  variable, distribution, node count, licence, capabilities, course days). Stdlib-only at import time. Provides
  `running_stack()` (isolated `foe-<purpose>-<stack>` project, `up -d --wait`, logs on failure, always torn
  down), `attach()` and `Connection.export_env()`.
- `scripts/with_stack.py` - runs a command against a stack with `ELASTICSEARCH_URL`, `ELASTIC_USER`/`PASSWORD`,
  `ELASTIC_VERIFY_SSL`, `KIBANA_URL` and `FOE_*` variables set.
- `validate.py` - thin CLI over the registry. Checks per stack (selected by capabilities): identity (version and
  distribution match `.env`), cluster (health + node count), license, CRUD round trip, vectors (dense_vector /
  knn_vector), ML (roles + ML memory on elk-ml / elk-ml-9), RRF retriever (trial), UI (Kibana / Dashboards available).
- `scripts/check_compose.py` - policy checks on the compose files (localhost ports, limits, healthchecks,
  no passwords in rendered commands).

### Key Configuration

Environment variables in `.env`:
- `ELK_VERSION` (8.19.x), `ELK9_VERSION` (9.5.x), `OPENSEARCH_VERSION` (2.19.x), `OPENSEARCH3_VERSION` (3.9.x), `ELK_OSS_VERSION` (7.10.2, frozen) — exact patch versions live only in `.env.example`
- `ELASTIC_PASSWORD`, `KIBANA_PASSWORD`, `OPENSEARCH_INITIAL_ADMIN_PASSWORD`

### Version Updates

Renovate (`renovate.json`) bumps the stack versions in `.env.example` (annotated `# renovate:` lines),
GitHub Actions, pre-commit hooks and Python dependencies. Track rules: `ELK_VERSION` stays on 8.x,
`OPENSEARCH_VERSION` on 2.x, `ELK_OSS_VERSION` is frozen; majors need dashboard approval; stack patch
bumps automerge once CI is green. Docs cite minor versions only (`8.19.x`) — `python -m
scripts.check_doc_versions [--fix]` (also a pre-commit hook) fails when a minor bump leaves docs stale.

### CI Pipeline

GitHub Actions (`.github/workflows/ci.yml`) runs on pushes to main/master, every pull request and manually
(optionally for a single stack):
- **lint** - `pre-commit run --all-files` (ruff, yamllint, actionlint, workflow schema, file hygiene)
- **unit** - `python -m unittest discover -s tests` on Python 3.11 and 3.14
- **secrets** - gitleaks over the commits a push/PR introduces (full history on manual runs)
- **compose-config** - `python -m scripts.check_compose`
- **plan** + **stacks** - matrix from `python validate.py --list --json`; each cell runs `python validate.py --stack X`
  plus `scripts/smoke_data.py` (movies load + evaluation with every mode the stack supports)
- **course** - snippet runner per course day and track (Days 1-3: elk-single + elk-9; Day 4: elk-ml + elk-ml-9);
  activates once `tests/course/run.py` exists
- nightly schedule: full matrix + full-history secret scan
- **ci-ok** - single aggregate status for branch protection

### Data Pipeline

The `data/` directory contains a pipeline for generating enriched movie data:

```
movies source → generate_descriptions.py → movies_enriched.csv
             → generate_embeddings.py → movies_enriched_with_embeddings.json
             → index.py → Elasticsearch (movies_enriched index, 768-dim vectors)
```

- `generate_descriptions.py` uses OpenRouter LLM API (Gemini 2.0 Flash) for multilingual text (en/kk/fr)
- `generate_embeddings.py` uses EmbeddingGemma-300M for 768-dim embeddings
- Enriched CSV fields: movieId, title, genres, abstract_en/kk/fr, description_en/kk/fr

## Course Structure (4 Days)

| Day | Topic | Duration | Stack | Slides | Exercises |
|-----|-------|----------|-------|--------|-----------|
| 1 | Fundamentals, core concepts, CRUD | 2h | `elk-single` | ~53 | 6 tasks (14 subtasks) |
| 2 | Query DSL, full-text/term/bool, ES\|QL | 2h | `elk-single` | ~54 | 13 tasks |
| 3 | Indexing, text analysis, aggregations, nested/join | 3h | `elk-single` or `elastic` | ~59 | 19 tasks (4 parts) |
| 4 | Vector search, ELSER, semantic_text, hybrid RRF | 3h | `elk-ml` | ~52 | 18 tasks (4 parts) |

### Testing the Course Snippets

`tests/course/` executes every Dev Tools snippet of a day against a live stack (`make course-test DAY=2 STACK=elk-9`,
or `python -m tests.course.run --day 2 --stack elk-single`). `manifest.yml` lists each day's decks and fixtures;
`baseline.yml` is a per-track ratchet of known failures (fixing content removes entries). Fence annotations
(`test=skip`, `expect=empty|404|4xx|any|warning`, `min=`, `top=`, `contains=`, `track=8|9`, `requires=trial|ml`)
and `// → {json}` expectations are documented in `course/README.md`. CI runs it per day and track (`course` job).

### Building Course Slides

```bash
make slides          # render all 8 decks to dist/slides/*.pdf (Marp CLI Docker image, pinned)
make slides-serve    # live preview on http://localhost:8080
```

`.marprc.yml` registers `course/theme/epam.css` (decks use `theme: epam`). PDFs are not committed: the
"Course slides" workflow renders them on every PR (artifact) and attaches them to a GitHub Release for
`course-v*` tags. Theme notes: `section { color-scheme: dark }` keeps syntax colours readable; callouts are
blockquotes starting with bold code (`> **`9.x`** ...`); hint slides use `<!-- _class: hint -->`.

## System Requirements

- Docker 20.10+ with the Compose v2 plugin (2.20+)
- Docker memory: ~4GB (elk-single/elk-9), ~6GB (elk/opensearch), ~10GB (elk-ml/elk-ml-9)
- `vm.max_map_count >= 262144` for the multi-node stacks (Linux host or the Docker VM): `sudo sysctl -w vm.max_map_count=262144`
- Stacks bind to 127.0.0.1 and share ports 9200/5601 — one at a time, or override `ES_PORT`/`KIBANA_PORT`
