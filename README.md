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

This starts Elastic Single, loads the checked-in movie dataset, creates both lexical and embedding indices, and opens a Streamlit UI for comparing:

- BM25 lexical search
- dense vector kNN search
- hybrid RRF search

Run evaluation metrics in another terminal:

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

```bash
# Install lightweight demo dependencies
make setup

# Validate Python and Docker Compose configuration
make test

# Start the default reviewer stack
make up-single

# Load lexical index only
make load-small

# Load deterministic 384-dim embedding index
make load-embeddings

# Evaluate BM25, dense, and hybrid retrieval
make evaluate

# Stop and remove local volumes
make down-single
```

Direct commands:

```bash
python data/load_data.py --dataset movies --size small
python data/load_data.py --dataset movies --size full
python data/load_data.py --dataset movies --with-embeddings
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
| Elastic Single | 8.19.11 | Default reviewer path, HTTP, auth, low memory |
| Elastic Stack | 8.19.11 | Production-like 2-node cluster with TLS |
| Elastic ML | 8.19.11 | ELSER, `semantic_text`, ML exercises |
| Elastic 9 | 9.3.0 | Next-gen single-node feature testing |
| OpenSearch | 2.19.4 | Open-source comparison stack |
| OpenSearch 3 | 3.5.0 | Next-gen OpenSearch 2-node stack |
| Elastic OSS | 7.10.2 | Legacy open-source version |

## Data

The checked-in source of truth is `data/movies_enriched.csv`, with a smaller local-review subset in `data/movies_enriched_1000.csv`.

`data/load_data.py` normalizes rows into:

- `id`, `movieId`, `title`, `title_raw`, `year`
- `genres`
- `overview`
- `abstract_en`, `abstract_kk`, `abstract_fr`
- `description_en`, `description_kk`, `description_fr`
- `searchable_text`
- optional `overview_embedding`

The default `--with-embeddings` path uses deterministic 384-dimensional local embeddings so vector and hybrid search work without downloading models. For model-backed embeddings:

```bash
pip install -r requirements-ml.txt
python data/generate_embeddings.py --limit 100
python data/index.py --input data/movies_enriched_with_embeddings.json
```

Additional RAG retrieval examples live in `data/rag_stage1_bm25.py`,
`data/rag_stage2_knn.py`, `data/rag_stage3_hybrid.py`, and
`data/load_hybrid_index.py` for staged BM25, kNN, and hybrid workflows.

## Course Structure

The course materials remain in `course/` and are secondary evidence for teaching and communication.

| Day | Topic | Duration | Stack |
|-----|-------|----------|-------|
| 1 | Fundamentals, core concepts, CRUD | 2h | `elk-single` |
| 2 | Query DSL, full-text/term/bool, ES\|QL | 2h | `elk-single` |
| 3 | Indexing, text analysis, aggregations, nested/join | 3h | `elk-single` or `elastic` |
| 4 | Vector search, ELSER, `semantic_text`, hybrid RRF | 3h | `elk-ml` |

See [course/README.md](course/README.md) for Marp build commands.

## Running Individual Stacks

```bash
docker compose -f docker/elk-single/docker-compose.yml --env-file .env up
docker compose -f docker/elk/docker-compose.yml --env-file .env up
docker compose -f docker/elk-ml/docker-compose.yml --env-file .env up
docker compose -f docker/elk-9/docker-compose.yml --env-file .env up
docker compose -f docker/opensearch/docker-compose.yml --env-file .env up
docker compose -f docker/opensearch-3/docker-compose.yml --env-file .env up
docker compose -f docker/elk-oss/docker-compose.yml --env-file .env up
```

## Requirements

- Docker 20.10+
- Docker Compose 1.29+
- Python 3.11+
- 4GB RAM for Elastic Single
- 8GB+ RAM for Elastic ML

Linux users may need:

```bash
sudo sysctl -w vm.max_map_count=262144
```

## Validation

```bash
python validate.py --stack elk-single
python validate.py --stack elk-ml
python validate.py --stack elastic
python validate.py --stack opensearch
python validate.py --stack elk-oss
python validate.py --stack elk-9
python validate.py --stack opensearch-3
```

## License

See [LICENSE](LICENSE).
