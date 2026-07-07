# Data Pipeline

This directory contains the checked-in movie data and scripts used by the course and portfolio demo.

## Source Files

- `movies_enriched.csv`: full enriched movie dataset.
- `movies_enriched_1000.csv`: smaller subset used for the default local reviewer path.
- `movies_embeddings_sample.json`: checked-in sample of the deterministic embedding document shape.
- `movies_enriched_with_embeddings.json`: optional generated artifact, ignored by git.

## Load Data

```bash
# Load 100 normalized movie documents into movies
python data/load_data.py --dataset movies --size small

# Load the full checked-in CSV into movies
python data/load_data.py --dataset movies --size full

# Load 100 movie documents with deterministic 384-dim vectors into movies-embeddings
python data/load_data.py --dataset movies --with-embeddings
```

## Normalized Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | MovieLens movie identifier |
| `movieId` | keyword | Original string ID from the CSV |
| `title` | text | Title with trailing release year removed |
| `title_raw` | keyword | Original title including release year |
| `year` | integer | Parsed trailing release year |
| `release_date` | date | Derived `YYYY-01-01` date from the title year |
| `genres` | keyword array | MovieLens genres |
| `overview` | text | English abstract used as the primary overview |
| `abstract_en/kk/fr` | text | Short descriptions in English, Kazakh, French |
| `description_en/kk/fr` | text | Longer descriptions in English, Kazakh, French |
| `searchable_text` | text | Combined text used for retrieval and embeddings |
| `overview_embedding` | dense_vector | Optional 384-dim vector |

## Embedding Modes

The default `--with-embeddings` loader path uses deterministic local embeddings. This keeps vector and hybrid search reproducible without downloading ML models.

For model-backed embeddings:

```bash
pip install -r requirements-ml.txt
python data/generate_embeddings.py --limit 100
python data/index.py --input data/movies_enriched_with_embeddings.json
```

The default model is `sentence-transformers/all-MiniLM-L6-v2`, which produces 384-dimensional embeddings that match the default mapping.

## Evaluation

After loading both `movies` and `movies-embeddings`, run:

```bash
python search/evaluate.py --mode bm25,dense,hybrid_rrf --queries evaluation/movie_queries.yml
```
