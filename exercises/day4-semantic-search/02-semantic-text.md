# Exercise 2: Semantic Text Field

Learn to use Elasticsearch's `semantic_text` field type for zero-configuration semantic search.

## Prerequisites

- **ELSER model deployed** (requires `elk-ml` config with 8GB+ RAM)
- Kibana access for model management

## Part 1: Deploy ELSER Model

The `semantic_text` field requires a deployed inference model. ELSER (Elastic Learned Sparse EncodeR) is Elastic's built-in model.

### Via Kibana UI (Recommended)
1. Open Kibana at http://localhost:5601
2. Go to **Machine Learning** > **Trained Models**
3. Find `.elser_model_2_linux-x86_64` (or similar)
4. Click **Download** then **Deploy**
5. Wait for deployment to complete (status: "started")

### Via API (Alternative)
```json
# Download model
PUT /_ml/trained_models/.elser_model_2_linux-x86_64
{
  "input": {
    "field_names": ["text_field"]
  }
}

# Start deployment
POST /_ml/trained_models/.elser_model_2_linux-x86_64/deployment/_start?wait_for=started
```

Check deployment status:
```json
GET /_ml/trained_models/.elser_model_2_linux-x86_64/_stats
```

## Part 2: Create Inference Endpoint

Create an inference endpoint that uses ELSER:

```json
PUT /_inference/sparse_embedding/my-elser-endpoint
{
  "service": "elser",
  "service_settings": {
    "num_allocations": 1,
    "num_threads": 1
  }
}
```

## Part 3: Create Index with semantic_text

Create an index that automatically generates embeddings:

```json
PUT /movies-semantic
{
  "mappings": {
    "properties": {
      "title": {
        "type": "text"
      },
      "overview": {
        "type": "text"
      },
      "overview_semantic": {
        "type": "semantic_text",
        "inference_id": "my-elser-endpoint"
      },
      "genres": {
        "type": "keyword"
      },
      "vote_average": {
        "type": "float"
      }
    }
  }
}
```

**Key insight:** The `semantic_text` field will automatically generate embeddings when documents are indexed. You don't need to pre-compute or manage embeddings yourself.

## Part 4: Index Documents

Add some movies - embeddings are generated automatically:

```json
POST /movies-semantic/_bulk
{"index": {"_id": "1"}}
{"title": "The Shawshank Redemption", "overview": "Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency.", "overview_semantic": "Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency.", "genres": ["Drama"], "vote_average": 8.7}
{"index": {"_id": "2"}}
{"title": "The Godfather", "overview": "The aging patriarch of an organized crime dynasty transfers control of his clandestine empire to his reluctant son.", "overview_semantic": "The aging patriarch of an organized crime dynasty transfers control of his clandestine empire to his reluctant son.", "genres": ["Crime", "Drama"], "vote_average": 8.7}
{"index": {"_id": "3"}}
{"title": "Inception", "overview": "A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea into the mind of a CEO.", "overview_semantic": "A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea into the mind of a CEO.", "genres": ["Action", "Science Fiction"], "vote_average": 8.4}
{"index": {"_id": "4"}}
{"title": "Interstellar", "overview": "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.", "overview_semantic": "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.", "genres": ["Adventure", "Drama", "Science Fiction"], "vote_average": 8.4}
{"index": {"_id": "5"}}
{"title": "The Matrix", "overview": "A computer hacker learns from mysterious rebels about the true nature of his reality and his role in the war against its controllers.", "overview_semantic": "A computer hacker learns from mysterious rebels about the true nature of his reality and his role in the war against its controllers.", "genres": ["Action", "Science Fiction"], "vote_average": 8.2}
```

**Note:** We copy the same text to both `overview` (for keyword search) and `overview_semantic` (for semantic search).

## Part 5: Semantic Query

Now query using natural language:

```json
GET /movies-semantic/_search
{
  "query": {
    "semantic": {
      "field": "overview_semantic",
      "query": "movies about escaping from prison"
    }
  }
}
```

### Task 2.1
Try these semantic queries and observe the results:
- "films about family and power"
- "movies about virtual reality or simulations"
- "space exploration adventures"

### Task 2.2
Compare semantic vs keyword search:

```json
# Keyword search
GET /movies-semantic/_search
{
  "query": {
    "match": {
      "overview": "escaping prison"
    }
  }
}

# Semantic search
GET /movies-semantic/_search
{
  "query": {
    "semantic": {
      "field": "overview_semantic",
      "query": "escaping prison"
    }
  }
}
```

Which finds "The Shawshank Redemption"? Why?

## Part 6: Combining Semantic with Filters

Add filters to semantic queries:

```json
GET /movies-semantic/_search
{
  "query": {
    "bool": {
      "must": {
        "semantic": {
          "field": "overview_semantic",
          "query": "science fiction technology"
        }
      },
      "filter": {
        "range": {
          "vote_average": { "gte": 8.0 }
        }
      }
    }
  }
}
```

### Task 2.3
Write a query that:
1. Uses semantic search for "family drama"
2. Filters to only "Drama" genre
3. Requires vote_average >= 8.5

## Part 7: When to Use semantic_text

**Advantages:**
- Zero configuration - no external embedding pipeline
- Embeddings updated automatically on document updates
- Simpler architecture

**Disadvantages:**
- Requires ML nodes with adequate memory
- Indexing is slower (embedding generation takes time)
- Less flexibility than custom embeddings

**Use semantic_text when:**
- You want simplicity over control
- You have ML infrastructure available
- Your use case fits ELSER's strengths (English text)

**Use dense_vector when:**
- You need custom embedding models
- You need to share embeddings across systems
- You want maximum indexing speed

## Part 8: Inspecting Generated Embeddings

View what the semantic_text field generated:

```json
GET /movies-semantic/_doc/1
```

The `overview_semantic` field will contain the original text plus inference results stored as sparse vectors.

## Answers

<details>
<summary>Task 2.2 Answer</summary>

The keyword search for "escaping prison" likely won't find "The Shawshank Redemption" because the overview doesn't contain those exact words. It talks about "imprisoned men" and "redemption".

The semantic search WILL find it because ELSER understands that "escaping prison" is semantically related to the concept of "imprisoned men" finding "redemption".

This demonstrates the key advantage of semantic search: understanding meaning, not just matching words.
</details>

<details>
<summary>Task 2.3 Answer</summary>

```json
GET /movies-semantic/_search
{
  "query": {
    "bool": {
      "must": {
        "semantic": {
          "field": "overview_semantic",
          "query": "family drama"
        }
      },
      "filter": [
        { "term": { "genres": "Drama" } },
        { "range": { "vote_average": { "gte": 8.5 } } }
      ]
    }
  }
}
```
</details>

## Cleanup

```json
DELETE /movies-semantic
DELETE /_inference/sparse_embedding/my-elser-endpoint
```

## Next Steps

Continue to Exercise 3 to learn about hybrid search, combining the best of keyword and semantic approaches.
