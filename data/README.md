# Sample Data for Elasticsearch Course

This directory contains sample datasets and a loader script for the Elasticsearch course exercises.

## Quick Start

```bash
# Install requirements
pip install requests

# Load small movies dataset (100 docs) - great for quick testing
python data/load_data.py --dataset movies --size small

# Load full movies dataset (5000 docs) - for comprehensive exercises
python data/load_data.py --dataset movies --size full

# Load movies with pre-computed embeddings - for Day 4 vector search
python data/load_data.py --dataset movies --with-embeddings
```

## Datasets

### Movies Dataset

The movies dataset contains movie information suitable for demonstrating:
- Full-text search (title, overview fields)
- Faceted search (genres, release_date)
- Aggregations (vote averages, genre distributions)
- Vector/semantic search (with embeddings variant)

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Unique movie identifier |
| `title` | text | Movie title (English analyzer) |
| `overview` | text | Plot summary (English analyzer) |
| `genres` | keyword | List of genres (for filtering/aggregations) |
| `vote_average` | float | Average rating (0-10) |
| `release_date` | date | Release date (YYYY-MM-DD) |
| `overview_embedding` | dense_vector | 384-dim embedding (embeddings variant only) |

**Variants:**
- `movies_100.json` - 100 hand-curated classic movies (small, beginner-friendly)
- `movies_5000.json` - 5000 generated movies (full dataset)
- `movies_embeddings.json` - 500 movies with pre-computed 384-dim embeddings

## Usage Options

### Auto-Detection (Recommended)

The loader automatically detects which Elasticsearch stack is running:

```bash
# Just run - it will find your stack
python data/load_data.py --dataset movies --size small
```

Supported stacks:
- Elastic Stack (HTTPS with auth)
- Elastic Single-Node (HTTP with auth)
- OpenSearch (HTTPS with auth)
- Elastic OSS (HTTP, no auth)

### Manual Configuration

```bash
# Specify URL and credentials
python data/load_data.py --dataset movies --url https://localhost:9200 \
    --user elastic --password elastic --insecure

# For Elastic OSS (no auth)
python data/load_data.py --dataset movies --url http://localhost:9200 --no-auth
```

## Course Day Mapping

| Day | Recommended Dataset | Notes |
|-----|---------------------|-------|
| Day 1 | `--size small` | Quick setup, learn basics |
| Day 2 | `--size small` or `--size full` | Query exercises |
| Day 3 | `--size full` | Indexing and analysis practice |
| Day 4 | `--with-embeddings` | Semantic search exercises |

## Sample Queries

After loading data, try these in Kibana Dev Tools:

### Basic Search
```json
GET /movies/_search
{
  "query": {
    "match": {
      "title": "dark knight"
    }
  }
}
```

### Full-Text Search
```json
GET /movies/_search
{
  "query": {
    "multi_match": {
      "query": "space adventure",
      "fields": ["title^2", "overview"]
    }
  }
}
```

### Filtered Search
```json
GET /movies/_search
{
  "query": {
    "bool": {
      "must": {
        "match": { "overview": "war" }
      },
      "filter": [
        { "term": { "genres": "Drama" } },
        { "range": { "vote_average": { "gte": 8.0 } } }
      ]
    }
  }
}
```

### Aggregations
```json
GET /movies/_search
{
  "size": 0,
  "aggs": {
    "genres": {
      "terms": { "field": "genres", "size": 10 }
    },
    "avg_rating": {
      "avg": { "field": "vote_average" }
    },
    "by_decade": {
      "date_histogram": {
        "field": "release_date",
        "calendar_interval": "year"
      }
    }
  }
}
```

### Vector Search (with embeddings)
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

## Troubleshooting

### Connection Refused
- Make sure Elasticsearch is running
- Check the correct port (9200 is default)
- Verify auth credentials match your `.env` file

### SSL Certificate Errors
- Use `--insecure` flag for self-signed certificates
- Or use the Elastic Single-Node config which uses HTTP

### Out of Memory
- Use `--size small` for limited memory environments
- The full dataset requires adequate heap space

### Index Already Exists
- The loader automatically deletes and recreates indices
- This ensures clean data for each exercise
