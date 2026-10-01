---
marp: true
theme: epam
paginate: true
---

<!-- _class: title -->

# Vector Search, Semantic Search & Hybrid Search

## Day 4 — 4-Day Elasticsearch Course

Elasticsearch 8.19 / 9.5 | dense_vector · E5 · ELSER · semantic_text · RRF

---

# Agenda

1. Setup — ML stack, licence, data
2. Vector Search Fundamentals
3. Embeddings in the Cluster — Inference API, E5
4. **Practice 4A** — Vector Search
5. ELSER & `semantic_text`
6. **Practice 4B** — Semantic Search
7. Hybrid Search with RRF
8. **Practice 4C** — Hybrid Search
9. Production Topics — quantization, memory, defaults
10. **Practice 4D** — Advanced (Bonus)
11. Bonus: RAG · Course Wrap-up

---

<!-- _class: small -->

# Stack Check

Today needs an **ML stack**: two nodes with ML roles and a trial licence (~10 GB Docker memory).

```bash
# 8.19 track (on the 9.5 track: elk-9 -> elk-ml-9)
docker compose -f docker/elk-single/docker-compose.yml --env-file .env down
docker compose -f docker/elk-ml/docker-compose.yml --env-file .env up -d --wait
```

**Endpoints:**
- Elasticsearch: `https://localhost:9200` (auth: `elastic` / `elastic`) — TLS with a self-signed CA
- Kibana: `http://localhost:5601` — Dev Tools handles the certificate for you

---

<!-- _class: small -->

# Load Today's Data

```bash
# Days 1-3 index (BM25)
python data/load_data.py --dataset movies --size small

# movies-embeddings: E5 vectors + ELSER, computed inside Elasticsearch
python data/load_data.py --dataset movies --size small --embeddings e5 --with-elser
```

- The first run **downloads and deploys** two models (~0.9 GB) — about 5 minutes on a laptop
- `--warm-only` deploys the models without loading anything (do it before class)
- `movies-embeddings` = the 200 movies + `overview_embedding` (E5, 384 dims) + `overview_semantic` (ELSER)

---

# Licence & ML Check

```json
GET _license
// → {"license": {"type": "trial", "status": "active"}}
```

```json
GET _inference/_all
```

- Three **preconfigured** inference endpoints: `.multilingual-e5-small-elasticsearch`, `.elser-2-elasticsearch`, `.rerank-v1-elasticsearch`
- They deploy their model on first use — no `PUT _inference/...` needed

> **`trial`** E5, ELSER and the `rrf` retriever need a trial or paid licence. The trial ends 30 days after the stack's first start; `make reset-elk-ml` starts over with a new trial (and deletes the data).

---

<!-- _class: divider -->

# Vector Search Fundamentals

## From keywords to meaning

---

# The Evolution of Search

```
Keyword Search (BM25)          Vector Search              Hybrid Search
"jailbreak"                    [0.05, -0.03, ...]         BM25 + kNN + RRF
     ↓                              ↓                          ↓
Exact term matching            Semantic similarity        Best of both worlds
0 hits — no movie says it      The Shawshank Redemption   Exact + semantic
```

| Generation | Technology | Weakness |
|-----------|------------|----------|
| **Keyword** | BM25 (inverted index) | Misses synonyms, paraphrases, other languages |
| **Semantic** | Embeddings + kNN | May miss exact terms, rare names, titles |
| **Hybrid** | BM25 + kNN + RRF | More moving parts, but the most robust |

---

# What Are Embeddings?

Embeddings are **numerical representations** of text (or images) in a high-dimensional space.

```
"escaping from prison"  → [0.079, -0.019, -0.056, -0.116, ...]   384 dims (E5)
"évasion de prison"     → [0.071, -0.024, -0.049, -0.108, ...]   ← close: same meaning
"apple pie recipe"      → [-0.031, 0.058, 0.012, 0.044, ...]     ← far
```

**Key insight:** Similar meanings → similar vectors → small distance

Models we use today, all **inside Elasticsearch**:
- **E5** (`multilingual-e5-small`) — dense, 384 dims, ~100 languages
- **ELSER** (Elastic Learned Sparse EncodeR) — sparse, English

---

<!-- _class: small -->

# dense_vector Field Type

A tiny index with **3-dimensional** toy vectors:

```json
PUT /toy-vectors
{
  "mappings": {
    "properties": {
      "title": { "type": "text" },
      "embedding": { "type": "dense_vector", "dims": 3, "similarity": "cosine" }
    }
  }
}

POST /toy-vectors/_bulk
{"index": {"_id": "1"}}
{"title": "Action Movie", "embedding": [1.0, 0.2, 0.1]}
{"index": {"_id": "2"}}
{"title": "Romantic Comedy", "embedding": [0.1, 1.0, 0.2]}
{"index": {"_id": "3"}}
{"title": "Sci-Fi Thriller", "embedding": [0.8, 0.3, 0.9]}
```

Real models use 384–1536 dimensions; `dims` must match the model.

---

# Similarity Metrics

```
Cosine Similarity          L2 Norm (Euclidean)         Dot Product
    A · B                  √Σ(Ai - Bi)²               Σ(Ai × Bi)
  ─────────
  |A| × |B|
```

| Metric | Best For | Note |
|--------|----------|------|
| **cosine** | Text embeddings | Direction matters, not magnitude |
| **l2_norm** | Image/spatial | Actual distance between points |
| **dot_product** | Unit-length vectors | Fastest — rejects vectors that are not normalized |
| **max_inner_product** | Unnormalized vectors | Magnitude counts |

> **Default choice:** Use `cosine` for text search.

---

# HNSW: How kNN Search is Fast

**HNSW** (Hierarchical Navigable Small World) — an approximate nearest neighbor algorithm:

```
Layer 2:  [A] ---- [D]              ← Long-range connections
           |        |
Layer 1:  [A] - [B] - [D] - [F]    ← Medium connections
           |   |   |   |   |
Layer 0:  [A]-[B]-[C]-[D]-[E]-[F]  ← All nodes, local connections
```

- Multi-layer graph structure
- Search starts at top layer (coarse), drills down (fine)
- Trade-off: accuracy vs speed (controlled by `num_candidates`)
- Not exact — "approximate" nearest neighbors (ANN)

---

<!-- _class: small -->

# kNN Query

```json top=1
GET /toy-vectors/_search
{
  "knn": { "field": "embedding", "query_vector": [0.9, 0.3, 0.2], "k": 2, "num_candidates": 10 },
  "_source": ["title"]
}
```

| Parameter | Purpose |
|-----------|---------|
| `k` | Number of nearest neighbors to return |
| `num_candidates` | Candidates examined per shard (higher = more accurate, slower) |
| `query_vector` | The vector to find neighbors for |

> `_score` is derived from the similarity: for `cosine`, `_score = (1 + cosine) / 2`. Action Movie scores 0.993.

---

<!-- _class: divider -->

# Embeddings in the Cluster

## The Inference API and E5

---

# The Inference API

Turn text into a vector — no Python, no external service:

```json
POST _inference/text_embedding/.multilingual-e5-small-elasticsearch
{ "input": "escaping from prison" }
```

```json
{ "text_embedding": [ { "embedding": [0.079, -0.019, -0.056, -0.116, ...] } ] }
```

- 384 floats per input; `"input"` can also be a list of texts
- A first call may answer **408** while the model deploys — just retry
- The same API serves sparse models (ELSER), rerankers and external services (OpenAI, Cohere, …)

---

<!-- _class: small -->

# Embedding at Ingest: a Pipeline

The loader created this pipeline and made it the index's `default_pipeline`:

```json
GET _ingest/pipeline/movies-embeddings-e5
```

```json
{
  "processors": [
    { "inference": {
        "model_id": ".multilingual-e5-small-elasticsearch",
        "input_output": { "input_field": "searchable_text", "output_field": "overview_embedding" }
    } },
    { "remove": { "field": "model_id", "ignore_missing": true } }
  ]
}
```

- Every document written to `movies-embeddings` is embedded on the way in — including yours
- E5 expects `passage:` / `query:` prefixes: Elasticsearch adds them for you

---

<!-- _class: small -->

# Query Text, Not Vectors

`query_vector_builder` lets Elasticsearch embed the query with the same model:

```json contains=318,1262
GET /movies-embeddings/_search
{
  "knn": {
    "field": "overview_embedding",
    "k": 5,
    "num_candidates": 50,
    "query_vector_builder": {
      "text_embedding": {
        "model_id": ".multilingual-e5-small-elasticsearch",
        "model_text": "escaping from prison"
      }
    }
  },
  "_source": ["title", "year"]
}
```

The Great Escape, The Defiant Ones, The Shawshank Redemption — none of them says "escaping".

---

# kNN with Filtering (Pre-filtering)

```json contains=924,260
GET /movies-embeddings/_search
{
  "knn": {
    "field": "overview_embedding",
    "k": 3,
    "num_candidates": 50,
    "query_vector_builder": {
      "text_embedding": { "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "space adventure" }
    },
    "filter": { "range": { "year": { "lt": 1980 } } }
  },
  "_source": ["title", "year"]
}
```

- The filter is applied **during** the kNN search: you still get `k` matching movies
- Filters use the same Query DSL as regular searches

---

<!-- _class: small -->

# Multilingual Search

The same English index, queried in French and Kazakh:

```json contains=318
GET /movies-embeddings/_search
{
  "knn": { "field": "overview_embedding", "k": 3, "num_candidates": 50,
    "query_vector_builder": { "text_embedding": {
      "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "évasion de prison" } } },
  "_source": ["title"]
}
```

```json contains=318
GET /movies-embeddings/_search
{
  "knn": { "field": "overview_embedding", "k": 3, "num_candidates": 50,
    "query_vector_builder": { "text_embedding": {
      "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "түрмеден қашу" } } },
  "_source": ["title"]
}
```

E5 maps all ~100 of its languages into one vector space: no translation, no per-language analyzer.

---

# Where Are the Vectors?

```json
GET /movies-embeddings/_search
{
  "query": { "ids": { "values": ["318"] } },
  "_source": { "exclude_vectors": false }
}
```

> **`9.x`** Since 9.2, `_source` **omits vectors** by default — they live only in the vector index (smaller indices, faster fetches). `"exclude_vectors": false` brings them back.

> **`8.19`** Vectors are stored in `_source` and returned with every hit — another reason to list the `_source` fields you need.

---

<!-- _class: exercise -->

# Practice 4A

## Vector Search

`day4-exercises.md` — Part A (5 tasks) | ~25 min

---

<!-- _class: divider -->

# ELSER & semantic_text

## Semantic search without managing vectors

---

<!-- _class: small -->

# What is ELSER?

**Elastic Learned Sparse EncodeR** — Elastic's own retrieval model.

| Feature | Detail |
|---------|--------|
| **Type** | Sparse embedding model (weighted terms) |
| **Language** | English |
| **Runs on** | ML nodes, in the cluster — no external API |
| **Endpoint** | `.elser-2-elasticsearch` (picks the right build for your CPU) |
| **Size** | 438 MB model, ~2 GB of ML memory when deployed |

**Sparse vs Dense:**
- **Dense (E5):** `[0.079, -0.019, …]` — 384 numbers, each meaningless on its own
- **Sparse (ELSER):** `{"prison": 2.18, "escape": 1.79, "jail": 1.35, …}` — readable terms

---

# ELSER in Action

```json
POST _inference/sparse_embedding/.elser-2-elasticsearch
{ "input": "Two men escape from a maximum security prison" }
```

Top weighted tokens:

```
prison 2.18 · maximum 2.05 · escape 1.79 · men 1.57 · jail 1.35 · man 1.26 · two 1.18 · prisoner 1.17 …
```

> ELSER **expands** the text: `jail` and `prisoner` are not in the input. Documents and queries both expand, so they meet on related terms.

---

# semantic_text Field Type

The simplest way to semantic search — Elasticsearch embeds, chunks and queries for you:

```json
PUT /semantic-demo
{
  "mappings": {
    "properties": {
      "title": { "type": "text" },
      "overview": { "type": "text", "copy_to": "overview_semantic" },
      "overview_semantic": {
        "type": "semantic_text",
        "inference_id": ".elser-2-elasticsearch"
      }
    }
  }
}
```

- `copy_to` fills `overview_semantic` from `overview`: index the text once
- **Always set `inference_id`** — the default endpoint is not the same in every version

---

# Indexing into semantic_text

```json
PUT /semantic-demo/_doc/demo-1
{ "title": "Demo", "overview": "Two convicts dig a tunnel to break out of a fortress jail." }

GET /semantic-demo/_search
{
  "query": {
    "semantic": { "field": "overview_semantic", "query": "prison escape" }
  }
}
```

- ELSER runs **at index time** (slower writes) and on the query text (at search time)
- Your text stays in `_source`; the embeddings live in hidden fields

---

# semantic_text: How It Works

```
overview text ──► chunks (sentences, ~250 words) ──► ELSER per chunk ──► stored with the document
query text ─────────────────────────────────────────► ELSER ──► best-matching chunk scores the document
```

- **Chunking** is automatic: long texts are split, each chunk embedded
- Chunks are hidden nested documents: `_cat/indices` counts 400 docs for 200 movies; `_count` says 200
- Change models by changing `inference_id` on a new index and reindexing

---

# Semantic Query on the Movies

```json contains=318,1153
GET /movies-embeddings/_search
{
  "query": {
    "semantic": {
      "field": "overview_semantic",
      "query": "jailbreak"
    }
  },
  "_source": ["title", "year"]
}
```

Raw Deal, Rififi, The Shawshank Redemption, The Green Mile.

> `match` works on a `semantic_text` field too: `{ "match": { "overview_semantic": "jailbreak" } }`.

---

# Keyword vs Semantic: Side by Side

```json expect=empty
GET /movies-embeddings/_search
{ "query": { "match": { "overview": "mobsters" } } }
```

```json contains=858,16
GET /movies-embeddings/_search
{ "query": { "semantic": { "field": "overview_semantic", "query": "mobsters" } } }
```

| Query | BM25 | ELSER | E5 |
|-------|------|-------|----|
| `jailbreak` | 0 hits | prison films | prison films |
| `mobsters` | 0 hits | The Godfather, Casino | weak |
| `heist` | Heat, Rififi | same + more | same + more |

No single method wins every query — that is the case for hybrid search.

---

# Semantic Highlighting

Which part of the text matched? Ask for the best chunks:

```json contains=1153
GET /movies-embeddings/_search
{
  "query": { "semantic": { "field": "overview_semantic", "query": "escaping from prison" } },
  "highlight": {
    "fields": { "overview_semantic": { "type": "semantic", "number_of_fragments": 1 } }
  },
  "_source": ["title"]
}
```

Returns the chunk itself: *"A desperate convict escapes prison with the help of a woman …"* (Raw Deal).

---

<!-- _class: small -->

# Chunking Settings

```json
PUT /chunk-demo
{
  "mappings": {
    "properties": {
      "body": {
        "type": "semantic_text",
        "inference_id": ".multilingual-e5-small-elasticsearch",
        "chunking_settings": { "strategy": "sentence", "max_chunk_size": 40, "sentence_overlap": 0 }
      }
    }
  }
}
```

| Strategy | Splits on | Overlap |
|----------|-----------|---------|
| `sentence` | Sentence boundaries, up to `max_chunk_size` words | `sentence_overlap` (0–1) |
| `word` | Every `max_chunk_size` words | `overlap` words |

`semantic_text` can use E5 too: point `inference_id` at the E5 endpoint for multilingual semantic search.

---

# When to Use What

| Use `semantic_text` | Use `dense_vector` |
|---------------------|--------------------|
| Simplest setup, chunking included | Full control: pipeline, quantization, kNN options |
| Any inference endpoint (ELSER, E5, external) | Vectors computed elsewhere |
| `semantic` / `match` queries | `knn` with filters, `similarity`, `rescore_vector` |

**ELSER vs E5:** ELSER (sparse) is strong on English keywords and explainable; E5 (dense) is multilingual.

---

<!-- _class: exercise -->

# Practice 4B

## ELSER & Semantic Search

`day4-exercises.md` — Part B (4 tasks) | ~25 min

---

<!-- _class: divider -->

# Hybrid Search with RRF

## The best of both worlds

---

# Why Hybrid?

| Query | BM25 finds | Semantic finds | Hybrid finds |
|-------|-----------|----------------|-------------|
| "Shawshank" | Exact title match | Maybe (a rare word) | Title match |
| "jailbreak" | Nothing | Prison films | Prison films |
| "space adventure" | Destiny in Space, Armageddon | 2001, Voyage to the Bottom of the Sea | Both sets, best first |

**Neither method alone is perfect.** Hybrid combines their strengths.

---

# Reciprocal Rank Fusion (RRF)

Combines rankings from multiple retrievers without needing score normalization:

```
RRF(d) = Σ  1 / (k + rank_i(d))
```

**Example:**

| Document | BM25 Rank | kNN Rank | RRF Score (k=60) |
|----------|-----------|----------|-------------------|
| Movie A | 1 | 5 | 1/61 + 1/65 = **0.0318** |
| Movie B | 3 | 1 | 1/63 + 1/61 = **0.0323** |
| Movie C | 2 | 10 | 1/62 + 1/70 = **0.0304** |

Movie B wins — ranked highly by **both** retrievers.

---

<!-- _class: small -->

# The Retriever API

```json contains=924,4856
GET /movies-embeddings/_search
{
  "retriever": {
    "rrf": {
      "retrievers": [
        { "standard": { "query": {
            "multi_match": { "query": "space adventure", "fields": ["title^2", "overview"] } } } },
        { "knn": {
            "field": "overview_embedding", "k": 20, "num_candidates": 50,
            "query_vector_builder": { "text_embedding": {
              "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "space adventure" } } } }
      ],
      "rank_window_size": 20
    }
  },
  "size": 5, "_source": ["title"]
}
```

> **`trial`** The `rrf` retriever needs an enterprise or trial licence. On a basic licence, fuse in the application (`search/client.py` does).

---

# RRF Parameters

| Parameter | Default | Effect |
|-----------|---------|--------|
| `rank_constant` | 60 | Higher = flatter: lower ranks count almost as much as the top |
| `rank_window_size` | `size` | How many results each retriever contributes |

```
rank_constant 1:    the #1 result of each retriever dominates
rank_constant 60:   balanced — a good default
rank_constant 1000: nearly flat — every rank counts about the same
```

> Set `rank_window_size` above `size` (e.g. 20–100): a movie ranked 15th by both retrievers deserves a chance.

---

<!-- _class: small -->

# Filters on Hybrid Search

`filter` on the `rrf` retriever applies to **every** sub-retriever:

```json contains=318
GET /movies-embeddings/_search
{
  "retriever": {
    "rrf": {
      "retrievers": [
        { "standard": { "query": {
            "multi_match": { "query": "prison escape", "fields": ["title^2", "overview"] } } } },
        { "knn": { "field": "overview_embedding", "k": 20, "num_candidates": 50,
            "query_vector_builder": { "text_embedding": {
              "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "prison escape" } } } }
      ],
      "rank_window_size": 20,
      "filter": { "range": { "year": { "gte": 1990 } } }
    }
  },
  "size": 5,
  "_source": ["title", "year"]
}
```

---

<!-- _class: small -->

# Three-way Hybrid: BM25 + kNN + Semantic

```json contains=1262,318
GET /movies-embeddings/_search
{
  "retriever": {
    "rrf": {
      "retrievers": [
        { "standard": { "query": {
            "multi_match": { "query": "escaping from prison", "fields": ["title^2", "overview"] } } } },
        { "knn": { "field": "overview_embedding", "k": 20, "num_candidates": 50,
            "query_vector_builder": { "text_embedding": {
              "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "escaping from prison" } } } },
        { "standard": { "query": {
            "semantic": { "field": "overview_semantic", "query": "escaping from prison" } } } }
      ],
      "rank_window_size": 20
    }
  },
  "size": 5,
  "_source": ["title"]
}
```

The Great Escape, Raw Deal, The Shawshank Redemption, The Defiant Ones, Rififi.

---

<!-- _class: small -->

# Weighted Fusion: the linear Retriever

```json contains=1262,318
GET /movies-embeddings/_search
{
  "retriever": {
    "linear": {
      "retrievers": [
        { "retriever": { "standard": { "query": { "match": { "overview": "prison escape" } } } },
          "weight": 1, "normalizer": "minmax" },
        { "retriever": { "knn": { "field": "overview_embedding", "k": 10, "num_candidates": 50,
            "query_vector_builder": { "text_embedding": {
              "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "prison escape" } } } },
          "weight": 2, "normalizer": "minmax" }
      ]
    }
  },
  "size": 3,
  "_source": ["title"]
}
```

- Normalizes each retriever's scores (`minmax`: 0–1), then adds them with your **weights**
- RRF needs no tuning; `linear` lets you say "vectors count twice"

---

<!-- _class: exercise -->

# Practice 4C

## Hybrid Search with RRF

`day4-exercises.md` — Part C (5 tasks) | ~30 min

---

<!-- _class: divider -->

# Production Topics

## Memory, quantization and defaults

---

<!-- _class: small -->

# Quantization: Bytes per Vector

| `index_options.type` | Stored as | Bytes / vector (384 dims) | Relative |
|---------|-----------|---------------:|---------:|
| `hnsw` | float32 | 4 × 384 = 1,536 | 1× |
| `int8_hnsw` | 1 byte / dim | 384 + 4 = 388 | ~¼ |
| `int4_hnsw` | ½ byte / dim | 192 + 4 = 196 | ~⅛ |
| `bbq_hnsw` | 1 bit / dim | 48 + 14 = 62 | ~1/25 |
| `flat`, `int8_flat`, … | no graph | same as above | exact search |

- RAM for fast kNN ≈ vectors × bytes per vector (+ the HNSW graph: ~4 × `m` bytes per vector)
- 1M E5 vectors: ~1.5 GB float32, ~390 MB int8, ~60 MB BBQ

> **`9.x`** `bbq_disk` (9.2+) keeps vectors on disk for huge indices; not available on 8.19.

---

# Defaults Differ Between Tracks

```json
PUT /q-default
{ "mappings": { "properties": { "v": { "type": "dense_vector", "dims": 384, "similarity": "cosine" } } } }

GET /q-default/_mapping/field/v?include_defaults=true
```

> **`8.19`** `"index_options": {"type": "int8_hnsw", "m": 16, "ef_construction": 100}`

> **`9.x`** `"index_options": {"type": "bbq_hnsw", ..., "rescore_vector": {"oversample": 3.0}}` (9.1+, 384+ dims)

The loader pins `int8_hnsw` explicitly, so `movies-embeddings` behaves the same on both tracks. **Set `index_options` yourself** when results must not change with an upgrade.

---

# Rescoring Quantized Vectors

Quantized search is approximate twice (HNSW + compression). `rescore_vector` fetches more candidates and re-ranks them with the original float vectors:

```json contains=924
GET /movies-embeddings/_search
{
  "knn": {
    "field": "overview_embedding", "k": 3, "num_candidates": 50,
    "query_vector_builder": { "text_embedding": {
      "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "space adventure" } },
    "rescore_vector": { "oversample": 2.0 }
  },
  "_source": ["title"]
}
```

`oversample: 2.0` → score 2 × k candidates with full precision, keep the best `k`.

---

# How Big Is It Really?

```json
POST /movies-embeddings/_disk_usage?run_expensive_tasks=true
```

| Field (200 movies) | On disk |
|--------------------|--------:|
| `overview` (text) | ~30 KB |
| `overview_embedding` (E5, int8) | ~380 KB |
| `overview_semantic` (ELSER chunks) | ~420 KB |

```json
GET _cat/indices/movies*?v&h=index,docs.count,store.size
```

> **`8.19`** ~6.6 MB for `movies-embeddings` — the vectors are also in `_source`. **9.x**: ~4 MB.

---

# Approximate vs Exact kNN

| | HNSW (`hnsw`, `int8_hnsw`, …) | Flat (`flat`, `int8_flat`, …) |
|--|------|------|
| How | Walks a graph of neighbours | Compares the query with every vector |
| Speed | Fast at any scale | O(n) — fine below ~10K vectors or with selective filters |
| Recall | High, tunable with `num_candidates` | Exact |

- Elasticsearch also searches **exactly** when a filter leaves few documents
- `similarity` on a `knn` query sets a minimum: it is the raw vector similarity (cosine), not `_score`

---

# Pre-filtering vs Post-filtering

| | `knn.filter` (pre) | `post_filter` |
|--|-----------|-------------|
| When | During the kNN search | After the top `k` are found |
| Result count | Always `k` (if enough match) | ≤ `k` — maybe zero |
| Use when | Default choice | You need aggregations over the unfiltered hits |

```json test=skip
"knn": { "field": "overview_embedding", "k": 10, "num_candidates": 100,
         "query_vector_builder": { ... }, "filter": { "term": { "genres": "Drama" } } }
```

---

# External Models via the Inference API

```json test=skip
PUT _inference/text_embedding/openai-embeddings
{
  "service": "openai",
  "service_settings": {
    "api_key": "<your OpenAI API key>",
    "model_id": "text-embedding-3-small"
  }
}
```

- Same `semantic_text`, `query_vector_builder` and pipelines — only the `inference_id` changes
- Services: OpenAI, Azure OpenAI, Cohere, Google Vertex AI, Hugging Face, Amazon Bedrock, …
- Trade-offs: better models and no ML nodes, but **latency, cost and data leaving your cluster**

---

# Production Architecture

```
┌──────────────┐     ┌────────────────────────────────────────────┐
│  Application │     │  Elasticsearch cluster                     │
│              │────▶│  data nodes:  movies-embeddings            │
│  sends TEXT  │     │               (BM25 + vectors + ELSER)     │
│  (query)     │     │  ingest:      pipeline → inference         │
│              │◀────│  ML nodes:    E5 + ELSER deployments       │
└──────────────┘     │               (adaptive allocations)       │
                     └────────────────────────────────────────────┘
```

**Key decisions:**
- In-cluster models (ML nodes) vs external inference services
- Quantization and rescoring for large vector indices
- Hybrid fusion: RRF (no tuning) vs linear (weights)
- Size ML memory: ~2 GB each for ELSER and E5 here

---

<!-- _class: exercise -->

# Practice 4D

## Advanced Techniques (Bonus)

`day4-exercises.md` — Part D (4 tasks) | ~20 min

---

<!-- _class: divider -->

# Bonus: Retrieval-Augmented Generation

---

# RAG: Search + an LLM

```
question ─► hybrid search (top 5 movies) ─► prompt with [id] citations ─► LLM ─► answer [318]
                                                                     └─► check: cited ids ⊆ retrieved?
```

```bash
# See what would be sent (no key needed)
python -m search.rag --stage hybrid --retrieve-only --question "films about escaping from prison"

# With an LLM via OpenRouter (bring your own key)
export OPENROUTER_API_KEY=...
python -m search.rag --stage hybrid
```

- Retrieval quality **is** answer quality: the LLM only knows what you retrieved
- Citations make answers checkable; an uncited or unknown id is a hallucination signal

---

<!-- _class: divider -->

# Course Wrap-up

---

# 4-Day Recap

| Day | Topic | Key Skills |
|-----|-------|-----------|
| **Day 1** | Fundamentals | Cluster concepts, CRUD, inverted index |
| **Day 2** | Query DSL & ES\|QL | match, bool, highlighting, pipe syntax |
| **Day 3** | Indexing & Analysis | Bulk ops, analyzers, mappings, aggregations |
| **Day 4** | Semantic Search | Vectors, E5, ELSER, hybrid RRF, production tips |

---

# What to Explore Next

- **Semantic reranking** — `text_similarity_reranker` with the preconfigured `.rerank-v1-elasticsearch`
- **ES|QL** — `LOOKUP JOIN`, full-text and semantic functions in ES|QL
- **Index Lifecycle Management** — automated rollover and deletion
- **Observability & Security** — logs, metrics, APM, SIEM on the same engine
- **Cross-cluster search** — federated search across clusters

---

# Resources

- **This repository** — keep it for reference and continued practice
- [Elasticsearch documentation](https://www.elastic.co/docs/solutions/search)
- [Vector search](https://www.elastic.co/docs/solutions/search/vector)
- [Semantic search with semantic_text](https://www.elastic.co/docs/solutions/search/semantic-search/semantic-search-semantic-text)
- [Hybrid search and retrievers](https://www.elastic.co/docs/solutions/search/retrievers-overview)
- [Elasticsearch Labs](https://www.elastic.co/search-labs)

---

<!-- _class: title -->

# Thank You!

## Congratulations on completing the course!

4-Day Elasticsearch Course | Elasticsearch 8.19 / 9.5
