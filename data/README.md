# Data Pipeline

This directory contains the checked-in movie data and scripts used by the course and portfolio demo.

## Source Files

- `movies_enriched.csv`: full enriched movie dataset.
- `movies_enriched.meta.json`: provenance of the rating columns (ml-32m checksums, rounding policy).
- `add_ratings.py`: maintainer tool that (re)computes `vote_average` / `vote_count` from MovieLens ml-32m.
- `LICENSE-DATA.md`: MovieLens usage terms and the synthetic-text disclosure.

`--size small` loads a curated 200-movie sample (1910s-2000s, all genres, every film the course names, see
`course/movies.yml`); `--size full` loads all 5,100. Titles are indexed in readable form ("The Godfather"),
alternate titles in `title_aka`, the MovieLens original in `title_raw`.
- `movies_small_ids.txt`: the curated `--size small` sample (200 movieIds), built by `build_sample.py` from `sample.yml`.
- `build_sample.py` / `sample.yml`: deterministic sample selection; `python data/build_sample.py report` prints counts.
- `movies_enriched_with_embeddings.json`: optional generated artifact, ignored by git.

## Load Data

```bash
# The curated 200-movie sample into `movies` (Days 1-3)
python data/load_data.py --dataset movies --size small

# All 5,100 movies into `movies`
python data/load_data.py --dataset movies --size full

# `movies-embeddings` with offline 384-dim hash vectors (any stack with vectors, OpenSearch included)
python data/load_data.py --dataset movies --embeddings hash

# `movies-embeddings` with in-cluster E5 vectors and ELSER (elk-ml / elk-ml-9: trial licence + ML nodes)
python data/load_data.py --dataset movies --embeddings e5 --with-elser

# Download and deploy E5 and ELSER ahead of class, without loading anything
python data/load_data.py --warm-only
```

The loader (`search/loader.py`) exits 0 ok, 3 connection/credentials, 4 refused (the cluster lacks the
capability, e.g. `--embeddings e5` on a basic licence), 5 partial load, 6 inference not ready (the models did
not deploy within `--inference-timeout`, default 900 s). `--skip-if-current` keeps an index that already holds
exactly this data; `--json` prints a summary.

### In-cluster inference (E5 and ELSER)

`--embeddings e5` creates the ingest pipeline `movies-embeddings-e5` (the preconfigured
`.multilingual-e5-small-elasticsearch` endpoint embeds `searchable_text` into `overview_embedding`) and makes it
the index's `default_pipeline`, so documents you add later are embedded too. Queries use
`query_vector_builder` with the same endpoint. Elasticsearch adds E5's `query: ` / `passage: ` prefixes itself.
`--with-elser` adds `overview_semantic`, a `semantic_text` field bound to `.elser-2-elasticsearch`.

Both endpoints download and deploy their model on first use; the loader waits for them (`--warm-only` does only
that). Measured on a 4-CPU Apple Silicon laptop (Docker 16 GB, `ML_NODE_MEM_LIMIT=4g`), small sample:

| Step | elk-ml (8.19) | elk-ml-9 (9.5) |
|------|--------------:|---------------:|
| first E5 deployment (`--warm-only`) | 26 s | 43 s |
| first ELSER deployment | 20 s | 3 s |
| load 200 movies with E5 + ELSER | 6.6 min | 4.5 min |

ELSER inference dominates the load time, so `--size full --with-elser` (5,100 movies) takes two to three
hours on such a machine; the course uses the small sample. On 9.x the vectors are not stored in
`_source` (`GET movies-embeddings/_doc/318` shows no `overview_embedding`); on 8.19 they are.

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
| `overview_embedding` | dense_vector | Optional 384-dim vector (`--embeddings hash` or `e5`) |
| `overview_semantic` | semantic_text | Optional ELSER field (`--with-elser`) |

## Embedding Modes

The `--embeddings hash` loader path uses deterministic local embeddings. This keeps vector and hybrid search reproducible without downloading ML models.

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
# after --embeddings e5 --with-elser, on an ML stack:
python search/evaluate.py --mode bm25,dense,hybrid_rrf,elser,hybrid_all --fail-under evaluation/floors.yml
```
