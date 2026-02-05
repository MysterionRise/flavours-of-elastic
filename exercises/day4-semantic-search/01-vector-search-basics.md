# Exercise 1: Vector Search Basics

Learn the fundamentals of vector search in Elasticsearch using dense_vector fields and kNN queries.

## Part 1: Understanding Vectors

Vector search represents text (or images, audio, etc.) as numerical vectors in a high-dimensional space. Similar items have vectors that are close together.

Example: The words "king" and "queen" would have vectors close to each other, while "king" and "banana" would be far apart.

## Part 2: Create a Vector Index

First, let's create an index with a dense_vector field.

```json
PUT /vector-demo
{
  "mappings": {
    "properties": {
      "title": {
        "type": "text"
      },
      "description": {
        "type": "text"
      },
      "embedding": {
        "type": "dense_vector",
        "dims": 3,
        "index": true,
        "similarity": "cosine"
      }
    }
  }
}
```

**Key parameters:**
- `dims`: Number of dimensions (3 for demo, typically 384-1536 in production)
- `index`: Enable kNN indexing for fast similarity search
- `similarity`: Distance metric (cosine, dot_product, l2_norm)

## Part 3: Index Documents with Vectors

Add some sample documents with simple 3D vectors:

```json
POST /vector-demo/_bulk
{"index": {"_id": "1"}}
{"title": "Action Movie", "description": "Explosions and car chases", "embedding": [1.0, 0.2, 0.1]}
{"index": {"_id": "2"}}
{"title": "Romantic Comedy", "description": "Love and laughter", "embedding": [0.1, 1.0, 0.2]}
{"index": {"_id": "3"}}
{"title": "Sci-Fi Thriller", "description": "Space and suspense", "embedding": [0.8, 0.3, 0.9]}
{"index": {"_id": "4"}}
{"title": "Action Comedy", "description": "Funny action scenes", "embedding": [0.7, 0.8, 0.2]}
{"index": {"_id": "5"}}
{"title": "Horror Film", "description": "Scary and suspenseful", "embedding": [0.2, 0.1, 0.9]}
```

## Part 4: Basic kNN Query

Find the 3 most similar documents to a query vector:

```json
GET /vector-demo/_search
{
  "knn": {
    "field": "embedding",
    "query_vector": [0.9, 0.3, 0.2],
    "k": 3,
    "num_candidates": 10
  }
}
```

**Key parameters:**
- `k`: Number of results to return
- `num_candidates`: Initial candidate pool size (higher = more accurate, slower)

### Task 1.1
Try changing the query vector to `[0.1, 0.9, 0.1]`. Which movies are now most similar? Why?

### Task 1.2
Increase `num_candidates` to 50. Do the results change? When would you need higher values?

## Part 5: kNN with Filtering

Combine vector search with traditional filters:

```json
GET /vector-demo/_search
{
  "knn": {
    "field": "embedding",
    "query_vector": [0.8, 0.5, 0.3],
    "k": 3,
    "num_candidates": 10,
    "filter": {
      "match": {
        "title": "comedy"
      }
    }
  }
}
```

### Task 1.3
Create a filter that only returns documents where the description contains "suspense". Run the kNN query again.

## Part 6: Working with Real Embeddings

Now let's use the movies dataset with pre-computed 384-dimensional embeddings:

```bash
# Load the dataset (if not already done)
python data/load_data.py --dataset movies --with-embeddings
```

Query the movies index:

```json
GET /movies-embeddings/_search
{
  "knn": {
    "field": "overview_embedding",
    "query_vector": [/* 384 dimensions - see below */],
    "k": 5,
    "num_candidates": 50
  },
  "_source": ["title", "overview", "genres"]
}
```

**Note:** To generate a query vector, you would typically use an embedding model. For this exercise, use one of the existing document's embeddings as a query:

```json
GET /movies-embeddings/_doc/1
```

Copy the `overview_embedding` array and use it as the `query_vector` to find similar movies.

### Task 1.4
1. Get the embedding from movie ID 1 (The Shawshank Redemption)
2. Use it as a query vector to find similar movies
3. Do the results make sense thematically?

### Task 1.5
Add a filter to only search within "Drama" genre movies. How do results change?

## Part 7: Understanding Similarity Metrics

Create indices with different similarity metrics and compare:

```json
# Cosine similarity (angle between vectors, most common)
PUT /test-cosine
{
  "mappings": {
    "properties": {
      "vec": { "type": "dense_vector", "dims": 3, "index": true, "similarity": "cosine" }
    }
  }
}

# L2 norm (Euclidean distance)
PUT /test-l2
{
  "mappings": {
    "properties": {
      "vec": { "type": "dense_vector", "dims": 3, "index": true, "similarity": "l2_norm" }
    }
  }
}

# Dot product (requires normalized vectors)
PUT /test-dot
{
  "mappings": {
    "properties": {
      "vec": { "type": "dense_vector", "dims": 3, "index": true, "similarity": "dot_product" }
    }
  }
}
```

### Task 1.6
Research: When would you use each similarity metric? What are the trade-offs?

## Answers

<details>
<summary>Task 1.1 Answer</summary>

With query vector `[0.1, 0.9, 0.1]`, the "Romantic Comedy" (embedding `[0.1, 1.0, 0.2]`) should be most similar because the vectors are closest in the cosine similarity space.
</details>

<details>
<summary>Task 1.3 Answer</summary>

```json
GET /vector-demo/_search
{
  "knn": {
    "field": "embedding",
    "query_vector": [0.8, 0.5, 0.3],
    "k": 3,
    "num_candidates": 10,
    "filter": {
      "match": {
        "description": "suspense"
      }
    }
  }
}
```
</details>

<details>
<summary>Task 1.6 Answer</summary>

- **Cosine**: Best for text embeddings, ignores vector magnitude, focuses on direction
- **L2 Norm**: Good when magnitude matters, common in image search
- **Dot Product**: Fastest but requires pre-normalized vectors, good for recommendation systems
</details>

## Cleanup

```json
DELETE /vector-demo
DELETE /test-cosine
DELETE /test-l2
DELETE /test-dot
```

## Next Steps

Continue to Exercise 2 to learn about the `semantic_text` field type for zero-configuration semantic search.
