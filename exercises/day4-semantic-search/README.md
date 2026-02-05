# Day 4: Semantic Search Exercises

This module covers modern semantic search techniques in Elasticsearch 8.x, including:
- Vector search with `dense_vector` fields
- Pre-computed embeddings and kNN queries
- Semantic search with `semantic_text` field (zero-config)
- Hybrid search combining keyword and vector results with RRF

## Prerequisites

- Elasticsearch 8.18+ running (use `elk-ml` config for ELSER)
- Movies dataset loaded with embeddings
- Basic understanding of Query DSL

## Setup

### Option A: Using Pre-computed Embeddings (Faster)

```bash
# Start single-node cluster
docker compose -f docker/elk-single/docker-compose.yml --env-file .env up -d

# Load movies with embeddings
python data/load_data.py --dataset movies --with-embeddings
```

### Option B: Using ELSER (Recommended for production)

```bash
# Start ML-enabled cluster (requires 8GB+ RAM)
docker compose -f docker/elk-ml/docker-compose.yml --env-file .env up -d

# Wait for cluster to be ready, then deploy ELSER via Kibana
# Machine Learning > Trained Models > Download .elser_model_2_linux-x86_64
```

## Exercises

### Exercise 1: Understanding Vector Search

Work through `01-vector-search-basics.md` to learn:
- How dense_vector fields work
- Creating indices with vector mappings
- Basic kNN queries
- Similarity metrics (cosine, dot_product, l2_norm)

### Exercise 2: Semantic Text (Zero-Config)

Work through `02-semantic-text.md` to learn:
- The `semantic_text` field type
- Automatic embedding generation
- Semantic queries vs keyword queries
- When to use semantic_text vs dense_vector

### Exercise 3: Hybrid Search with RRF

Work through `03-hybrid-search.md` to learn:
- Combining BM25 and vector search
- Reciprocal Rank Fusion (RRF)
- Tuning hybrid search parameters
- Use cases for hybrid approach

### Exercise 4: Advanced (Optional)

Work through `04-advanced-techniques.md` to learn:
- Custom embedding models
- Chunking strategies for long documents
- Filtered vector search
- Performance optimization

## Quick Reference

### kNN Query Syntax
```json
{
  "knn": {
    "field": "embedding_field",
    "query_vector": [0.1, 0.2, ...],
    "k": 10,
    "num_candidates": 100
  }
}
```

### Semantic Query Syntax
```json
{
  "query": {
    "semantic": {
      "field": "semantic_text_field",
      "query": "natural language query"
    }
  }
}
```

### Hybrid Search with RRF
```json
{
  "retriever": {
    "rrf": {
      "retrievers": [
        { "standard": { "query": { "match": { "text": "query" } } } },
        { "knn": { "field": "embedding", "query_vector": [...], "k": 10 } }
      ],
      "rank_window_size": 100,
      "rank_constant": 60
    }
  }
}
```

## Resources

- [Elasticsearch Vector Search Guide](https://www.elastic.co/guide/en/elasticsearch/reference/current/dense-vector.html)
- [ELSER Documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current/semantic-search-elser.html)
- [Semantic Text Field](https://www.elastic.co/guide/en/elasticsearch/reference/current/semantic-text.html)
- [Reciprocal Rank Fusion](https://www.elastic.co/guide/en/elasticsearch/reference/current/rrf.html)
