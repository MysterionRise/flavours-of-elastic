# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Flavours of Elastic is an educational repository for a **4-day Elasticsearch course**, providing Docker Compose configurations for running and comparing Elasticsearch-based search engines with support for modern features like vector search and semantic search.

### Available Stacks

1. **Elastic Single** (8.19.11) - Beginner-friendly single-node, HTTP, auth, 4GB RAM
2. **Elastic Stack** (8.19.11) - Production-like 2-node cluster, HTTPS + auth
3. **Elastic ML** (8.19.11) - ML-enabled for ELSER/vector search, 8GB+ RAM
4. **Elastic 9** (9.3.0) - Next-gen single-node, HTTP, auth, 4GB RAM
5. **OpenSearch** (2.19.4) - Open-source alternative with Dashboards, HTTPS + auth
6. **OpenSearch 3** (3.5.0) - Next-gen 2-node cluster, HTTPS + auth
7. **Elasticsearch OSS** (7.10.2) - Legacy open-source version, HTTP, no auth (frozen)

## Common Commands

### Running Stacks

```bash
# Elastic Single (beginners, 4GB RAM)
docker compose -f docker/elk-single/docker-compose.yml --env-file .env up

# Elastic Stack (auth: elastic/elastic)
docker compose -f docker/elk/docker-compose.yml --env-file .env up

# Elastic ML (for ELSER/semantic search, 8GB+ RAM)
docker compose -f docker/elk-ml/docker-compose.yml --env-file .env up

# Elastic 9 (next-gen, 4GB RAM)
docker compose -f docker/elk-9/docker-compose.yml --env-file .env up

# OpenSearch (auth: admin/MyStrongPassword123!)
docker compose -f docker/opensearch/docker-compose.yml --env-file .env up

# OpenSearch 3 (auth: admin/MyStrongPassword123!)
docker compose -f docker/opensearch-3/docker-compose.yml --env-file .env up

# Elasticsearch OSS (no auth)
docker compose -f docker/elk-oss/docker-compose.yml --env-file .env up
```

### Loading Sample Data

```bash
# Load small movies dataset (100 docs)
python data/load_data.py --dataset movies --size small

# Load full movies dataset (5000 docs)
python data/load_data.py --dataset movies --size full

# Load movies with embeddings (for Day 4 vector search)
python data/load_data.py --dataset movies --with-embeddings
```

### Validation & Testing

```bash
# Validate all stacks
python validate.py --stack all

# Validate specific stack
python validate.py --stack elk-single
python validate.py --stack elk-ml
python validate.py --stack elastic
python validate.py --stack opensearch
python validate.py --stack elk-oss
python validate.py --stack elk-9
python validate.py --stack opensearch-3
```

### Code Quality

```bash
# Install pre-commit hooks (run once)
pip install -r requirements.txt
pip install pre-commit
pre-commit install

# Run all checks manually
pre-commit run --all-files
```

Pre-commit runs: check-yaml, end-of-file-fixer, trailing-whitespace, detect-private-key, black, isort, flake8 (max-line-length=120, ignores W605, E203, W503)

### Cleanup

```bash
docker compose -f docker/<stack>/docker-compose.yml down -v
```

## Architecture

### Directory Structure

- `docker/elk-single/` - Single-node for beginners (HTTP, auth)
- `docker/elk/` - Elastic Stack with TLS cert generation and 2-node cluster (has Dockerfile for ingest-opennlp)
- `docker/elk-ml/` - ML-enabled 2-node cluster for ELSER
- `docker/elk-9/` - Elasticsearch 9 single-node (HTTP, auth)
- `docker/opensearch/` - OpenSearch 2-node cluster with Dashboards (has Dockerfile)
- `docker/opensearch-3/` - OpenSearch 3 two-node cluster with Dashboards
- `docker/elk-oss/` - Elasticsearch OSS 2-node cluster, legacy (has Dockerfile for ingest-opennlp)
- `data/` - Sample datasets, data loader, and enrichment pipeline scripts
- `data/load_data.py` - Main data loader for course exercises (auto-detects stack)
- `data/generate_descriptions.py` - Generate multilingual descriptions via OpenRouter LLM API
- `data/generate_embeddings.py` - Generate 768-dim embeddings via EmbeddingGemma-300M
- `data/index.py` - Index enriched movies with embeddings into Elasticsearch
- `data/movies_enriched.csv` - 5100 movies with multilingual abstracts/descriptions (18MB)
- `data/movies_enriched_1000.csv` - 1000-movie subset (3.5MB)
- `course/` - Marp Markdown slides and exercises for the 4-day course
- `course/README.md` - Course build instructions for Marp CLI
- `course/theme/epam.css` - Custom Marp theme (black bg #000000 + cyan accent #00F6FF)
- `course/day1-fundamentals/` - Day 1 slides (~53) and exercises (6 tasks, 14 subtasks)
- `course/day2-query-dsl/` - Day 2 slides (~54) and exercises (13 tasks)
- `course/day3-indexing-analysis/` - Day 3 slides (~59) and exercises (19 tasks across 4 parts)
- `course/day4-semantic-search/` - Day 4 slides (~52) and exercises (18 tasks across 4 parts)
- `validate.py` - Stack validation script with OOP design
- `benchmarks/` - Performance test CSV files and benchmark reports (geonames, noaa)
- `.marprc.yml` - Marp CLI configuration (theme and font settings)
- `.env.example` - Environment variable template with documentation
- `ISSUES.md` - Issue tracker with prioritized improvements (P0-P3)

### Stack Differences

| Stack | Protocol | Auth | JVM Heap | System RAM | Nodes | ML/Vector |
|-------|----------|------|----------|------------|-------|-----------|
| Elastic Single | HTTP | elastic/elastic | 1GB | ~4GB | 1 | Basic |
| Elastic Stack | HTTPS | elastic/elastic | 1GB x2 | ~6GB | 2 | Basic |
| Elastic ML | HTTPS | elastic/elastic | 2GB x2 | ~8GB+ | 2 | Full ELSER |
| Elastic 9 | HTTP | elastic/elastic | 1GB | ~4GB | 1 | Basic |
| OpenSearch | HTTPS | admin/MyStrongPassword123! | 2GB x2 | ~6GB | 2 | No |
| OpenSearch 3 | HTTPS | admin/MyStrongPassword123! | 2GB x2 | ~6GB | 2 | No |
| OSS | HTTP | none | 512MB x2 | ~2GB | 2 | No |

### Validation Script Design

`validate.py` uses inheritance:
- `StackValidator` - Base class with common operations (start, wait, health check, test ops)
- `ElasticSingleValidator` - HTTP, auth, single node
- `ElasticValidator` - HTTPS, basic auth, 2-node
- `ElasticMLValidator` - HTTPS, auth, ML checks, vector operations
- `Elastic9Validator` - HTTP, auth, single node (ES 9)
- `OpenSearchValidator` - HTTPS, basic auth
- `OpenSearch3Validator` - HTTPS, basic auth (OS 3)
- `ElasticOSSValidator` - HTTP, no auth

### Key Configuration

Environment variables in `.env`:
- `ELK_VERSION` (8.19.11), `ELK9_VERSION` (9.3.0), `OPENSEARCH_VERSION` (2.19.4), `OPENSEARCH3_VERSION` (3.5.0), `ELK_OSS_VERSION` (7.10.2)
- `ELASTIC_PASSWORD`, `KIBANA_PASSWORD`, `OPENSEARCH_INITIAL_ADMIN_PASSWORD`

### CI Pipeline

GitHub Actions runs on push/PR to main/master:
- **lint** - black, isort, flake8 checks
- **validate-yaml** - yamllint on all docker-compose files
- **test-elk-single** - Start, health check, CRUD, UI test
- **test-elk-oss** - Start, health check, CRUD, UI test
- **test-opensearch** - Start, health check, CRUD, UI test
- **test-elastic** - Start, health check, 2-node verification, CRUD, UI test
- **test-elk-ml** - Start, health check, ML node check, vector index + kNN query test
- **test-elk-9** - Start, health check, CRUD, UI test
- **test-opensearch-3** - Start, health check, CRUD, UI test

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

### Building Course Slides

```bash
# Install Marp CLI
npm install -g @marp-team/marp-cli

# Build a single day's slides to PDF
marp course/day1-fundamentals/day1-slides.md --theme course/theme/epam.css --allow-local-files -o /tmp/day1.pdf

# Live preview
marp --server --theme course/theme/epam.css course/day1-fundamentals/day1-slides.md
```

## Known Issues & Technical Debt

- **Missing dataset JSON files**: `load_data.py` references `datasets/movies_100.json`, `datasets/movies_5000.json`, `datasets/movies_embeddings.json` — these files do not exist in the repo; the script will fail
- **Hardcoded encryption key in elk-ml**: `docker/elk-ml/docker-compose.yml` contains `XPACK_ENCRYPTEDSAVEDOBJECTS_ENCRYPTIONKEY` in plaintext — should be in .env
- **Hardcoded credentials**: Python scripts (load_data.py, index.py, validate.py) hardcode auth instead of reading from .env
- See `ISSUES.md` for the full prioritized tracker

## System Requirements

- Docker 20.10+, Docker Compose 1.29+
- RAM: 4GB (elk-single), 6GB (elastic/opensearch), 8GB+ (elk-ml)
- Linux: `sudo sysctl -w vm.max_map_count=262144`
