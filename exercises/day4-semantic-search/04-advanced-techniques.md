# Exercise 4: Advanced Semantic Search Techniques (Optional)

Advanced topics for those wanting to go deeper into production semantic search.

## Part 1: Filtered Vector Search Performance

Pre-filtering vs post-filtering affects performance dramatically.

### Pre-filtering (Recommended)
Filter is applied BEFORE kNN search:

```json
GET /movies-embeddings/_search
{
  "knn": {
    "field": "overview_embedding",
    "query_vector": [...],
    "k": 10,
    "num_candidates": 100,
    "filter": {
      "term": { "genres": "Drama" }
    }
  }
}
```

### Post-filtering
Filter applied AFTER kNN (can return fewer than k results):

```json
GET /movies-embeddings/_search
{
  "knn": {
    "field": "overview_embedding",
    "query_vector": [...],
    "k": 10,
    "num_candidates": 100
  },
  "post_filter": {
    "term": { "genres": "Drama" }
  }
}
```

### Task 4.1
When would you use post-filtering instead of pre-filtering?

## Part 2: Quantization for Efficiency

Reduce memory usage with scalar quantization:

```json
PUT /movies-quantized
{
  "mappings": {
    "properties": {
      "overview_embedding": {
        "type": "dense_vector",
        "dims": 384,
        "index": true,
        "similarity": "cosine",
        "index_options": {
          "type": "int8_hnsw",
          "m": 16,
          "ef_construction": 100
        }
      }
    }
  }
}
```

**Trade-offs:**
- ~4x memory reduction
- Slight accuracy loss (usually < 5%)
- Good for large-scale deployments

## Part 3: Chunking Strategies

For long documents, split into chunks with overlap:

```python
def chunk_text(text, chunk_size=500, overlap=50):
    """Split text into overlapping chunks."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks

# Example document
long_overview = "Very long movie plot... " * 100

chunks = chunk_text(long_overview)
for i, chunk in enumerate(chunks):
    # Index each chunk as separate document
    doc = {
        "movie_id": 1,
        "chunk_id": i,
        "chunk_text": chunk,
        "chunk_embedding": get_embedding(chunk)  # Your embedding function
    }
```

### Index Structure for Chunks

```json
PUT /movies-chunked
{
  "mappings": {
    "properties": {
      "movie_id": { "type": "integer" },
      "chunk_id": { "type": "integer" },
      "chunk_text": { "type": "text" },
      "chunk_embedding": {
        "type": "dense_vector",
        "dims": 384,
        "index": true,
        "similarity": "cosine"
      }
    }
  }
}
```

### Querying Chunked Documents

```json
GET /movies-chunked/_search
{
  "knn": {
    "field": "chunk_embedding",
    "query_vector": [...],
    "k": 20,
    "num_candidates": 100
  },
  "collapse": {
    "field": "movie_id"
  },
  "size": 5
}
```

The `collapse` ensures we get unique movies, not multiple chunks from the same movie.

## Part 4: Custom Inference Endpoints

Use external embedding services:

### OpenAI Embeddings
```json
PUT /_inference/text_embedding/openai-embeddings
{
  "service": "openai",
  "service_settings": {
    "api_key": "your-api-key",
    "model_id": "text-embedding-3-small"
  }
}
```

### Hugging Face Models
```json
PUT /_inference/text_embedding/huggingface-embeddings
{
  "service": "hugging_face",
  "service_settings": {
    "api_key": "your-api-key",
    "url": "https://api-inference.huggingface.co/models/sentence-transformers/all-MiniLM-L6-v2"
  }
}
```

### Task 4.2
Research: What are the trade-offs between using ELSER vs external embedding models like OpenAI?

## Part 5: Performance Monitoring

### Check Index Stats
```json
GET /movies-embeddings/_stats/dense_vector
```

### Monitor kNN Performance
```json
GET /movies-embeddings/_search
{
  "profile": true,
  "knn": {
    "field": "overview_embedding",
    "query_vector": [...],
    "k": 10,
    "num_candidates": 100
  }
}
```

Look at the `profile` section to understand query execution time.

### Memory Usage
```json
GET /_nodes/stats/indices/segments?human
```

Dense vector fields consume significant memory - monitor this in production.

## Part 6: Approximate vs Exact kNN

### Approximate (Default, Fast)
Uses HNSW index for fast approximate search:

```json
GET /movies-embeddings/_search
{
  "knn": {
    "field": "overview_embedding",
    "query_vector": [...],
    "k": 10,
    "num_candidates": 100
  }
}
```

### Exact (Slow but Perfect)
Uses script_score for exact brute-force search:

```json
GET /movies-embeddings/_search
{
  "query": {
    "script_score": {
      "query": { "match_all": {} },
      "script": {
        "source": "cosineSimilarity(params.query_vector, 'overview_embedding') + 1.0",
        "params": {
          "query_vector": [...]
        }
      }
    }
  }
}
```

### Task 4.3
Run both queries on your movies dataset. Compare:
1. Execution time
2. Result ordering
3. When would exact search be worth the performance cost?

## Part 7: Building a Search Application

### Python Client Example

```python
from elasticsearch import Elasticsearch

es = Elasticsearch(
    "https://localhost:9200",
    basic_auth=("elastic", "elastic"),
    verify_certs=False
)

def semantic_search(query_text, query_embedding, k=10):
    """Hybrid search with RRF."""
    return es.search(
        index="movies-embeddings",
        body={
            "retriever": {
                "rrf": {
                    "retrievers": [
                        {
                            "standard": {
                                "query": {
                                    "multi_match": {
                                        "query": query_text,
                                        "fields": ["title^2", "overview"]
                                    }
                                }
                            }
                        },
                        {
                            "knn": {
                                "field": "overview_embedding",
                                "query_vector": query_embedding,
                                "k": k,
                                "num_candidates": k * 5
                            }
                        }
                    ]
                }
            },
            "_source": ["title", "overview", "genres"],
            "size": k
        }
    )

# Usage
results = semantic_search(
    "space adventure",
    get_embedding("space adventure"),  # Your embedding function
    k=5
)
for hit in results['hits']['hits']:
    print(f"{hit['_source']['title']}: {hit['_score']}")
```

## Part 8: Best Practices Checklist

- [ ] Choose appropriate embedding dimensions (384-768 for most use cases)
- [ ] Use quantization for large indices (>1M documents)
- [ ] Implement chunking for long documents
- [ ] Use pre-filtering for performance
- [ ] Monitor memory usage on ML nodes
- [ ] Set appropriate `num_candidates` (higher = better recall, slower)
- [ ] Test hybrid vs single-method search for your use case
- [ ] Cache frequently-used query embeddings
- [ ] Use collapse for chunked document search

## Answers

<details>
<summary>Task 4.1 Answer</summary>

Use post-filtering when:
1. You want to show users why results don't match their filters (for UI feedback)
2. The filter is very selective (few documents match) and you want more diverse kNN candidates
3. You're computing facet counts alongside results

Use pre-filtering (default) in most cases for better performance.
</details>

<details>
<summary>Task 4.2 Answer</summary>

**ELSER:**
- Pros: No external API calls, no API costs, data stays on-premises
- Cons: Requires ML node resources, only English, sparse embeddings

**External Models (OpenAI, etc.):**
- Pros: State-of-the-art quality, multi-language, no local GPU needed
- Cons: API costs, data sent externally, latency, vendor dependency
</details>

<details>
<summary>Task 4.3 Answer</summary>

Exact kNN is worth the cost when:
1. Dataset is small (<10K documents)
2. You need 100% accuracy for evaluation/testing
3. Building ground truth for comparing approximate methods
4. Filter conditions result in very few candidates anyway
</details>

## Resources

- [Elasticsearch Vector Search Tuning](https://www.elastic.co/guide/en/elasticsearch/reference/current/tune-knn-search.html)
- [Dense Vector Field Type](https://www.elastic.co/guide/en/elasticsearch/reference/current/dense-vector.html)
- [HNSW Algorithm Explained](https://www.pinecone.io/learn/hnsw/)
- [Chunking Strategies for RAG](https://www.pinecone.io/learn/chunking-strategies/)
