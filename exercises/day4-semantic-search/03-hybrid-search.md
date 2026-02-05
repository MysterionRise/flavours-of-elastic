# Exercise 3: Hybrid Search with RRF

Learn to combine keyword (BM25) and vector search using Reciprocal Rank Fusion (RRF) for best-of-both-worlds retrieval.

## Why Hybrid Search?

| Search Type | Strengths | Weaknesses |
|-------------|-----------|------------|
| Keyword (BM25) | Exact matches, rare terms, proper nouns | Misses synonyms, paraphrases |
| Semantic (Vector) | Understands meaning, handles paraphrases | May miss exact matches, specific terms |
| **Hybrid** | Combines both strengths | More complex to tune |

## Part 1: Setup Index for Hybrid Search

Create an index that supports both search types:

```json
PUT /movies-hybrid
{
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "analyzer": "english"
      },
      "overview": {
        "type": "text",
        "analyzer": "english"
      },
      "overview_embedding": {
        "type": "dense_vector",
        "dims": 384,
        "index": true,
        "similarity": "cosine"
      },
      "genres": {
        "type": "keyword"
      },
      "vote_average": {
        "type": "float"
      },
      "release_date": {
        "type": "date"
      }
    }
  }
}
```

## Part 2: Load Data

Use the pre-computed embeddings dataset:

```bash
python data/load_data.py --dataset movies --with-embeddings
```

Or manually reindex to our hybrid index:

```json
POST /_reindex
{
  "source": {
    "index": "movies-embeddings"
  },
  "dest": {
    "index": "movies-hybrid"
  }
}
```

## Part 3: Understanding RRF

Reciprocal Rank Fusion combines rankings from multiple retrievers:

**RRF Score Formula:**
```
RRF(d) = Σ 1 / (k + rank_i(d))
```

Where:
- `d` is a document
- `k` is the rank constant (default 60)
- `rank_i(d)` is the rank of document `d` in retriever `i`

**Example:**
- Document ranked #1 by BM25, #5 by kNN
- RRF score = 1/(60+1) + 1/(60+5) = 0.0164 + 0.0154 = 0.0318

Documents that rank highly in BOTH retrievers get boosted.

## Part 4: Basic Hybrid Query

Use the retriever API with RRF:

```json
GET /movies-embeddings/_search
{
  "retriever": {
    "rrf": {
      "retrievers": [
        {
          "standard": {
            "query": {
              "multi_match": {
                "query": "space exploration science",
                "fields": ["title^2", "overview"]
              }
            }
          }
        },
        {
          "knn": {
            "field": "overview_embedding",
            "query_vector": [0.02, -0.05, 0.08, ...],
            "k": 10,
            "num_candidates": 50
          }
        }
      ],
      "rank_window_size": 100,
      "rank_constant": 60
    }
  },
  "_source": ["title", "overview", "genres"],
  "size": 5
}
```

**Parameters:**
- `rank_window_size`: How many results to consider from each retriever
- `rank_constant`: The `k` value in RRF formula (higher = more equal weight)

### Task 3.1
What happens if you set `rank_constant` to 1? To 1000? Run experiments and observe.

## Part 5: Practical Hybrid Search

Since we need a query vector, let's use a document's embedding as our query:

1. First, get an embedding from an existing document:
```json
GET /movies-embeddings/_doc/8
```
(This is Interstellar - a space movie)

2. Use that embedding in a hybrid query:
```json
GET /movies-embeddings/_search
{
  "retriever": {
    "rrf": {
      "retrievers": [
        {
          "standard": {
            "query": {
              "match": {
                "overview": "space travel exploration humanity survival"
              }
            }
          }
        },
        {
          "knn": {
            "field": "overview_embedding",
            "query_vector": [/* paste embedding from step 1 */],
            "k": 10,
            "num_candidates": 50
          }
        }
      ]
    }
  },
  "_source": ["title", "overview"],
  "size": 10
}
```

### Task 3.2
Compare the results of:
1. BM25 only (just the standard retriever)
2. kNN only (just the kNN retriever)
3. Hybrid with RRF

Which gives the best results for finding space-related movies?

## Part 6: Adding Filters to Hybrid Search

Apply filters that work across both retrievers:

```json
GET /movies-embeddings/_search
{
  "retriever": {
    "rrf": {
      "retrievers": [
        {
          "standard": {
            "query": {
              "bool": {
                "must": {
                  "match": { "overview": "crime family" }
                },
                "filter": {
                  "range": { "vote_average": { "gte": 8.0 } }
                }
              }
            }
          }
        },
        {
          "knn": {
            "field": "overview_embedding",
            "query_vector": [/* embedding */],
            "k": 10,
            "num_candidates": 50,
            "filter": {
              "range": { "vote_average": { "gte": 8.0 } }
            }
          }
        }
      ]
    }
  }
}
```

**Important:** Filters must be applied to EACH retriever separately.

### Task 3.3
Create a hybrid query that:
1. Searches for "war battle conflict"
2. Filters to only Drama or War genres
3. Requires vote_average >= 7.5

## Part 7: Tuning Hybrid Search

### Adjusting Rank Constant

```json
# Lower rank_constant (e.g., 10): Top results matter more
# Higher rank_constant (e.g., 100): More equal weighting across ranks

GET /movies-embeddings/_search
{
  "retriever": {
    "rrf": {
      "retrievers": [...],
      "rank_constant": 10
    }
  }
}
```

### Adjusting Rank Window Size

```json
# Larger window = considers more candidates = better recall, slower
GET /movies-embeddings/_search
{
  "retriever": {
    "rrf": {
      "retrievers": [...],
      "rank_window_size": 200
    }
  }
}
```

### Task 3.4
Experiment with these combinations:
- rank_constant=10, rank_window_size=50
- rank_constant=60, rank_window_size=100
- rank_constant=100, rank_window_size=200

Which combination gives the best results for your use case?

## Part 8: When to Use Hybrid Search

**Use Hybrid When:**
- Users search with mixed intent (some keyword, some conceptual)
- You need to balance precision (exact matches) with recall (related content)
- Building e-commerce, document search, or content discovery

**Skip Hybrid When:**
- Pure keyword search is sufficient (e.g., SKU lookup)
- Latency is critical and results are acceptable with single method
- You don't have embeddings infrastructure

## Real-World Example: E-commerce Search

```json
# User searches for "comfortable running shoes for marathon"
GET /products/_search
{
  "retriever": {
    "rrf": {
      "retrievers": [
        {
          "standard": {
            "query": {
              "multi_match": {
                "query": "comfortable running shoes marathon",
                "fields": ["name^3", "description", "category"],
                "type": "best_fields"
              }
            }
          }
        },
        {
          "knn": {
            "field": "description_embedding",
            "query_vector": [/* from embedding API */],
            "k": 20,
            "num_candidates": 100
          }
        }
      ],
      "rank_window_size": 100
    }
  }
}
```

This finds:
- Exact matches: "Marathon Running Shoes - Comfortable Fit"
- Semantic matches: "Ultralight Distance Trainers - Perfect for Long Runs"

## Answers

<details>
<summary>Task 3.1 Answer</summary>

- `rank_constant=1`: Only the very top results from each retriever matter. #1 gets score 0.5, #2 gets 0.33, etc. Very steep dropoff.
- `rank_constant=1000`: All top 100 results get similar scores (0.001 range). Rankings become nearly equal weight.
- Default 60 is a good balance for most use cases.
</details>

<details>
<summary>Task 3.3 Answer</summary>

```json
GET /movies-embeddings/_search
{
  "retriever": {
    "rrf": {
      "retrievers": [
        {
          "standard": {
            "query": {
              "bool": {
                "must": {
                  "match": { "overview": "war battle conflict" }
                },
                "filter": [
                  { "terms": { "genres": ["Drama", "War"] } },
                  { "range": { "vote_average": { "gte": 7.5 } } }
                ]
              }
            }
          }
        },
        {
          "knn": {
            "field": "overview_embedding",
            "query_vector": [/* embedding for war/battle concept */],
            "k": 10,
            "num_candidates": 50,
            "filter": {
              "bool": {
                "must": [
                  { "terms": { "genres": ["Drama", "War"] } },
                  { "range": { "vote_average": { "gte": 7.5 } } }
                ]
              }
            }
          }
        }
      ]
    }
  }
}
```
</details>

## Cleanup

```json
DELETE /movies-hybrid
```

## Next Steps

Continue to Exercise 4 for advanced techniques including custom embedding models and performance optimization.
