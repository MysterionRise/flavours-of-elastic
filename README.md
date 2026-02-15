# Flavours of Elastic - Educational Elasticsearch Repository

[![CI](https://github.com/MysterionRise/flavours-of-elastic/actions/workflows/ci.yml/badge.svg)](https://github.com/MysterionRise/flavours-of-elastic/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Docker Compose configurations for running and comparing Elasticsearch-based search engines, designed for a **4-day educational course** covering modern search techniques including vector search and semantic search.

## What's Supported

| Stack | Version | Use Case |
|-------|---------|----------|
| **Elastic Stack** | 8.19.11 | Production-like 2-node cluster with TLS |
| **Elastic Single** | 8.19.11 | Beginner-friendly single-node (4GB RAM) |
| **Elastic ML** | 8.19.11 | ML/ELSER features for semantic search (8GB+ RAM) |
| **Elastic 9** | 9.3.0 | Next-gen single-node for testing ES 9 features |
| **OpenSearch** | 2.19.4 | Open-source alternative |
| **OpenSearch 3** | 3.5.0 | Next-gen OpenSearch 2-node cluster |
| **Elastic OSS** | 7.10.2 | Legacy support (frozen, no updates) |

## Quick Start

### For Beginners (Day 1-2)

Start with the single-node configuration - simpler setup, lower memory:

```bash
# Start Elastic Single (4GB RAM required)
docker compose -f docker/elk-single/docker-compose.yml --env-file .env up

# Access Elasticsearch
curl http://localhost:9200 -u elastic:elastic

# Access Kibana at http://localhost:5601 (login: elastic/elastic)
```

### For Full Course (Day 3-4)

Use the ML-enabled configuration for vector/semantic search:

```bash
# Start Elastic ML (8GB+ RAM required)
docker compose -f docker/elk-ml/docker-compose.yml --env-file .env up

# Access via HTTPS
curl --insecure https://localhost:9200 -u elastic:elastic
```

### Load Sample Data

```bash
# Install requirements
pip install requests

# Load movies dataset (100 docs - quick start)
python data/load_data.py --dataset movies --size small

# Load full dataset (5000 docs)
python data/load_data.py --dataset movies --size full

# Load with embeddings (for Day 4 vector search)
python data/load_data.py --dataset movies --with-embeddings
```

## 4-Day Course Structure

All course materials (Marp slides + exercises) are in the `course/` directory. See `course/README.md` for build instructions.

### Day 1: Elasticsearch Fundamentals (2h) — `elk-single`
- What is Elasticsearch, ES vs databases, Elastic ecosystem
- Core concepts: cluster, node, index, shard, inverted index, BM25
- Setup, Kibana tour (Discover, Dev Tools, Dashboards)
- CRUD operations with the movies dataset
- **Exercises:** 6 tasks (cluster exploration, CRUD, shard allocation)

### Day 2: Query DSL & ES|QL (2h) — `elk-single`
- Full-text: `match`, `multi_match`, `match_phrase` (operator, slop, boosting)
- Term-level: `term`, `terms`, `range`, `exists`, `prefix`
- Compound: `bool` (must/filter/should/must_not), nested bools
- Pagination, sorting, highlighting
- ES|QL: pipe syntax, EVAL, STATS...BY, Kibana Discover integration
- **Exercises:** 7 Query DSL tasks + 6 ES|QL tasks

### Day 3: Indexing, Text Analysis & Aggregations (3h) — `elk-single` or `elastic`
- Index API, bulk operations, refresh/flush, reindex, aliases, templates
- Text analysis: analyzers, custom analyzers, edge_ngram autocomplete, synonyms
- Mappings: dynamic vs explicit, text vs keyword, multi-fields
- Aggregations: metric, bucket, nested, pipeline aggs, Kibana Lens
- Nested & join types: nested objects, parent-child relationships
- **Exercises:** 19 tasks across 4 parts (Indexing, Analyzers, Aggs, Nested/Join)

### Day 4: Vector Search, Semantic Search & Hybrid (3h) — `elk-ml`
- Vector fundamentals: embeddings, dense_vector, HNSW, kNN, filtered kNN
- ELSER deployment, inference endpoints, semantic_text field, semantic queries
- Hybrid search: RRF formula, Retriever API, BM25+kNN+semantic, tuning
- Advanced: quantization (int8_hnsw), chunking, pre/post filtering, custom embeddings
- **Exercises:** 18 tasks across 4 parts (Vector, ELSER, RRF, Advanced)

## Stack Comparison

| Feature | Elastic Stack | Elastic Single | Elastic ML | Elastic 9 | OpenSearch | OpenSearch 3 | Elastic OSS |
|---------|--------------|----------------|------------|-----------|------------|--------------|-------------|
| **Nodes** | 2 | 1 | 2 | 1 | 2 | 2 | 2 |
| **Protocol** | HTTPS | HTTP | HTTPS | HTTP | HTTPS | HTTPS | HTTP |
| **Auth** | elastic/elastic | elastic/elastic | elastic/elastic | elastic/elastic | admin/password | admin/password | None |
| **Memory** | 2-3GB | ~2GB | 6-8GB | ~2GB | 4GB | 4GB | 1GB |
| **ML/ELSER** | No | No | **Yes** | No | No | No | No |
| **Best For** | Production-like | Beginners | Day 4 Semantic | ES 9 features | Open source | OS 3 features | Legacy |

### When to Use Each

- **Elastic Single**: Learning basics, limited RAM, Days 1-2
- **Elastic Stack**: Production-like testing, TLS experience
- **Elastic ML**: Vector search, semantic search, ELSER, Day 4
- **Elastic 9**: Testing Elasticsearch 9.x new features
- **OpenSearch**: Open-source preference, AWS compatibility
- **OpenSearch 3**: Testing OpenSearch 3.x new features
- **Elastic OSS**: Legacy 7.x applications only

## Prerequisites

- **Docker**: 20.10+ ([Install Docker](https://docs.docker.com/install/))
- **Docker Compose**: 1.29+ ([Install Docker Compose](https://docs.docker.com/compose/install/))
- **RAM Requirements**:
  - Elastic Single: 4GB minimum
  - Elastic Stack/OpenSearch: 6GB minimum
  - Elastic ML: 8GB recommended
- **Disk Space**: 10GB free
- **Ports**: 9200, 5601

**Linux users**: Increase `vm.max_map_count`:
```bash
sudo sysctl -w vm.max_map_count=262144
```

## Running All Stacks

```bash
# Elastic Single (beginners, low memory)
docker compose -f docker/elk-single/docker-compose.yml --env-file .env up

# Elastic Stack (production-like, 2 nodes)
docker compose -f docker/elk/docker-compose.yml --env-file .env up

# Elastic ML (for ELSER/semantic search)
docker compose -f docker/elk-ml/docker-compose.yml --env-file .env up

# Elasticsearch 9 (next-gen single-node)
docker compose -f docker/elk-9/docker-compose.yml --env-file .env up

# OpenSearch
docker compose -f docker/opensearch/docker-compose.yml --env-file .env up

# OpenSearch 3 (next-gen)
docker compose -f docker/opensearch-3/docker-compose.yml --env-file .env up

# Elasticsearch OSS (legacy)
docker compose -f docker/elk-oss/docker-compose.yml --env-file .env up
```

## Sample Queries

### Basic Search (Days 1-2)

```bash
# Create an index
curl -X PUT "http://localhost:9200/movies" -u elastic:elastic

# Add a document
curl -X POST "http://localhost:9200/movies/_doc/1" \
  -u elastic:elastic \
  -H 'Content-Type: application/json' \
  -d '{"title": "The Matrix", "year": 1999}'

# Search
curl "http://localhost:9200/movies/_search?q=Matrix" -u elastic:elastic
```

### ES|QL Query (Day 2)

```
POST /_query
{
  "query": "FROM movies | WHERE year > 1990 | STATS count = COUNT(*) BY genres | SORT count DESC"
}
```

### Vector Search (Day 4)

```json
GET /movies-embeddings/_search
{
  "knn": {
    "field": "overview_embedding",
    "query_vector": [0.1, 0.2, ...],
    "k": 10,
    "num_candidates": 100
  }
}
```

### Hybrid Search with RRF (Day 4)

```json
GET /movies-embeddings/_search
{
  "retriever": {
    "rrf": {
      "retrievers": [
        { "standard": { "query": { "match": { "overview": "space adventure" } } } },
        { "knn": { "field": "overview_embedding", "query_vector": [...], "k": 10 } }
      ]
    }
  }
}
```

## Project Structure

```
flavours-of-elastic/
├── course/                        # Marp slides + exercises (4-day course)
│   ├── README.md                  # Build instructions
│   ├── theme/epam.css             # Custom Marp theme
│   ├── day1-fundamentals/         # Slides (~50) + exercises (6 tasks)
│   ├── day2-query-dsl/            # Slides (~55) + exercises (13 tasks)
│   ├── day3-indexing-analysis/    # Slides (~65) + exercises (19 tasks)
│   └── day4-semantic-search/      # Slides (~55) + exercises (18 tasks)
├── docker/
│   ├── elk/              # Elastic Stack (2-node, TLS)
│   ├── elk-single/       # Single-node for beginners
│   ├── elk-ml/           # ML-enabled for ELSER
│   ├── elk-9/            # Elasticsearch 9 single-node
│   ├── opensearch/       # OpenSearch cluster
│   ├── opensearch-3/     # OpenSearch 3 cluster
│   └── elk-oss/          # Legacy OSS (7.10.2)
├── data/
│   ├── datasets/         # Sample datasets (movies)
│   ├── load_data.py      # Unified data loader
│   └── README.md         # Data loading guide
├── benchmarks/           # Performance test files and reports
├── .env                  # Environment configuration
├── validate.py           # Stack validation script
└── README.md
```

## Validation & Testing

### Validate Stacks Locally

```bash
pip install -r requirements.txt

# Test all stacks
python validate.py --stack all

# Test specific stack
python validate.py --stack elk-single
python validate.py --stack elk-ml
python validate.py --stack elastic
python validate.py --stack opensearch
python validate.py --stack elk-oss
python validate.py --stack elk-9
python validate.py --stack opensearch-3
```

### CI Pipeline

GitHub Actions automatically tests:
- YAML validation
- All stack configurations
- Health checks and CRUD operations
- Vector operations (elk-ml)

## Troubleshooting

### Out of Memory
- Use `elk-single` for limited RAM
- Reduce heap size in docker-compose.yml: `ES_JAVA_OPTS=-Xms512m -Xmx512m`

### Port Already in Use
```bash
# Check what's using port 9200
sudo lsof -i :9200

# Stop existing containers
docker compose down
```

### vm.max_map_count Too Low (Linux)
```bash
sudo sysctl -w vm.max_map_count=262144
# Permanent: echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

### Connection Refused
- Wait 2-5 minutes for initial startup
- Check container status: `docker compose ps`
- View logs: `docker compose logs`

### Certificate Errors
```bash
# Use --insecure with curl for self-signed certs
curl --insecure https://localhost:9200 -u elastic:elastic
```

## Cleanup

```bash
# Stop and remove volumes
docker compose -f docker/<stack>/docker-compose.yml down -v

# Remove all Docker resources
docker system prune -a --volumes
```

## Contributing

1. Fork and clone the repository
2. Install pre-commit hooks: `pip install pre-commit && pre-commit install`
3. Make changes and test with `python validate.py`
4. Submit a Pull Request

## Resources

- [Elasticsearch Documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- [ES|QL Getting Started](https://www.elastic.co/guide/en/elasticsearch/reference/current/esql-getting-started.html)
- [Vector Search Guide](https://www.elastic.co/guide/en/elasticsearch/reference/current/dense-vector.html)
- [Semantic Search with ELSER](https://www.elastic.co/guide/en/elasticsearch/reference/current/semantic-search-elser.html)
- [OpenSearch Documentation](https://opensearch.org/docs/latest/)

## License

See [LICENSE](LICENSE) file for details.
