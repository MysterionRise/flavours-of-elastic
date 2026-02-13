# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Flavours of Elastic is an educational repository for a **4-day Elasticsearch course**, providing Docker Compose configurations for running and comparing Elasticsearch-based search engines with support for modern features like vector search and semantic search.

### Available Stacks

1. **Elastic Single** (8.18.0) - Beginner-friendly single-node, HTTP, auth, 4GB RAM
2. **Elastic Stack** (8.18.0) - Production-like 2-node cluster, HTTPS + auth
3. **Elastic ML** (8.18.0) - ML-enabled for ELSER/vector search, 8GB+ RAM
4. **OpenSearch** (2.19.1) - Open-source alternative with Dashboards, HTTPS + auth
5. **Elasticsearch OSS** (7.10.2) - Legacy open-source version, HTTP, no auth (frozen)

## Common Commands

### Running Stacks

```bash
# Elastic Single (beginners, 4GB RAM)
docker compose -f docker/elk-single/docker-compose.yml --env-file .env up

# Elastic Stack (auth: elastic/elastic)
docker compose -f docker/elk/docker-compose.yml --env-file .env up

# Elastic ML (for ELSER/semantic search, 8GB+ RAM)
docker compose -f docker/elk-ml/docker-compose.yml --env-file .env up

# OpenSearch (auth: admin/MyStrongPassword123!)
docker compose -f docker/opensearch/docker-compose.yml --env-file .env up

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
- `docker/elk/` - Elastic Stack with TLS cert generation and 2-node cluster
- `docker/elk-ml/` - ML-enabled 2-node cluster for ELSER
- `docker/opensearch/` - OpenSearch 2-node cluster with Dashboards
- `docker/elk-oss/` - Elasticsearch OSS 2-node cluster (legacy)
- `data/` - Sample datasets, data loader, and enrichment pipeline scripts
- `data/load_data.py` - Main data loader for course exercises (auto-detects stack)
- `data/generate_descriptions.py` - Generate multilingual descriptions via OpenRouter LLM API
- `data/generate_embeddings.py` - Generate 768-dim embeddings via EmbeddingGemma-300M
- `data/index.py` - Index enriched movies with embeddings into Elasticsearch
- `data/movies_enriched.csv` - 5100 movies with multilingual abstracts/descriptions (18MB)
- `data/movies_enriched_1000.csv` - 1000-movie subset (3.5MB)
- `course/` - Marp Markdown slides and exercises for the 4-day course
- `course/theme/epam.css` - Custom Marp theme (black bg #000000 + cyan accent #00F6FF)
- `course/day1-fundamentals/` - Day 1 slides (~53) and exercises (14 tasks)
- `course/day2-query-dsl/` - Day 2 slides (~54) and exercises (15 tasks)
- `course/day3-indexing-analysis/` - Day 3 slides (~59) and exercises (25 tasks)
- `course/day4-semantic-search/` - Day 4 slides (~52) and exercises (34 tasks)
- `exercises/day4-semantic-search/` - Legacy Day 4 exercise files (standalone)
- `validate.py` - Stack validation script with OOP design
- `benchmarks/` - Performance test CSV files (geonames, noaa)

### Stack Differences

| Stack | Protocol | Auth | Memory | Nodes | ML/Vector |
|-------|----------|------|--------|-------|-----------|
| Elastic Single | HTTP | elastic/elastic | ~2GB | 1 | Basic |
| Elastic Stack | HTTPS | elastic/elastic | ~3GB | 2 | Basic |
| Elastic ML | HTTPS | elastic/elastic | ~6GB | 2 | Full ELSER |
| OpenSearch | HTTPS | admin/password | ~4GB | 2 | No |
| OSS | HTTP | none | ~1GB | 2 | No |

### Validation Script Design

`validate.py` uses inheritance:
- `StackValidator` - Base class with common operations (start, wait, health check, test ops)
- `ElasticSingleValidator` - HTTP, auth, single node
- `ElasticValidator` - HTTPS, basic auth, 2-node
- `ElasticMLValidator` - HTTPS, auth, ML checks, vector operations
- `OpenSearchValidator` - HTTPS, basic auth
- `ElasticOSSValidator` - HTTP, no auth

### Key Configuration

Environment variables in `.env`:
- `ELK_VERSION` (8.18.0), `OPENSEARCH_VERSION` (2.19.1), `ELK_OSS_VERSION` (7.10.2)
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
| 1 | Fundamentals, core concepts, CRUD | 2h | `elk-single` | ~53 | 14 tasks |
| 2 | Query DSL, full-text/term/bool, ES\|QL | 2h | `elk-single` | ~54 | 15 tasks |
| 3 | Indexing, text analysis, aggregations, nested/join | 3h | `elk-single` or `elastic` | ~59 | 25 tasks |
| 4 | Vector search, ELSER, semantic_text, hybrid RRF | 3h | `elk-ml` | ~52 | 34 tasks |

### Building Course Slides

```bash
# Install Marp CLI
npm install -g @marp-team/marp-cli

# Build a single day's slides to PDF
marp course/day1-fundamentals/day1-slides.md --theme course/theme/epam.css --allow-local-files -o /tmp/day1.pdf

# Live preview
marp --server --theme course/theme/epam.css course/day1-fundamentals/day1-slides.md
```

## System Requirements

- Docker 20.10+, Docker Compose 1.29+
- RAM: 4GB (elk-single), 6GB (elastic/opensearch), 8GB+ (elk-ml)
- Linux: `sudo sysctl -w vm.max_map_count=262144`
