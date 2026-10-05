---
marp: true
theme: epam
paginate: true
---

<!-- _class: title -->

# Day 4 Exercises: Vector Search, Semantic Search & Hybrid Search

**Stack:** `elk-ml` (8.19) or `elk-ml-9` (9.5) | **Duration:** ~100 minutes total | **Kibana Dev Tools:** `http://localhost:5601`

## Prerequisites

- Set up the day before: "Before Day 4" in `course/README.md` (~10 GB Docker memory, models deployed)
- The ML stack running (see the "Stack Check" slide) — `GET _license` shows `trial`
- `movies` and `movies-embeddings` loaded:
  `python data/load_data.py --dataset movies --size small --embeddings e5 --with-elser`

---

<!-- _class: divider -->

# Part A: Vector Search (5 tasks, ~25 min)

---

<!-- _class: small -->

## Task 1: Toy Vectors (Basic)

Create an index `vector-demo` with a 3-dimensional `dense_vector` field `embedding` (cosine similarity) and index:

| _id | title | embedding |
|-----|-------|-----------|
| 1 | Action Movie | `[1.0, 0.2, 0.1]` |
| 2 | Romantic Comedy | `[0.1, 1.0, 0.2]` |
| 3 | Sci-Fi Thriller | `[0.8, 0.3, 0.9]` |
| 4 | Action Comedy | `[0.7, 0.8, 0.2]` |
| 5 | Horror Film | `[0.2, 0.1, 0.9]` |

Run a kNN query with `[0.9, 0.3, 0.2]` (k=3), then with `[0.1, 0.9, 0.1]`.

**Questions:** What are the top 3 each time, and why? What are the `_score` values, and how do they relate to cosine similarity?

---

## Task 2: The Inference API (Basic)

1. Embed the text `"a heist that goes wrong"` with `POST _inference/text_embedding/.multilingual-e5-small-elasticsearch`. How many numbers come back?
2. Embed two texts in **one** request (`"input"` takes a list).
3. Search `movies-embeddings` for `"a heist that goes wrong"` with `knn` + `query_vector_builder` (k=5).

**Question:** Which movies come back? Would a `match` query on `overview` find them?

> **Hint:** `query_vector_builder.text_embedding` takes `model_id` (the endpoint id) and `model_text`.

---

## Task 3: Filtered kNN (Intermediate)

Search for `"space adventure"` with E5 kNN (k=5):

1. Without a filter
2. Only movies released **before 1980**
3. Only `Sci-Fi` movies from **1990 or later**

Compare the results. Do you always get 5 hits?

> **Hint:** Put a `filter` inside the `knn` object. Several conditions: `bool` with a `filter` array.

---

## Task 4: Multilingual Search (Intermediate)

The overviews are English. Search them in other languages with E5 kNN (k=3):

- French: `"famille mafieuse sicilienne"`
- Kazakh: `"ковбой қуыршақ ойыншық"` (cowboy doll toy)
- Your own language — try a plot you know

Then run the French query as a BM25 `match` on `overview`. What happens?

**Question:** Why does kNN work across languages when BM25 does not?

---

## Task 5: num_candidates and similarity (Intermediate)

Run the `"escaping from prison"` kNN query (k=5) with `num_candidates` 5, 50 and 200. Compare results and `took`.

Then add `"similarity": 0.8` to the `knn` object, and try `0.85`.

**Questions:**
1. At what point do the results stabilize?
2. With `similarity` set, why can you get fewer than k hits? How does `similarity` relate to `_score`?

> **Hint:** For `cosine`, `similarity` is the raw cosine; `_score = (1 + cosine) / 2`.

---

<!-- _class: divider -->

# Part B: ELSER & Semantic Search (4 tasks, ~25 min)

---

## Task 6: Look Inside ELSER (Basic)

Run `POST _inference/sparse_embedding/.elser-2-elasticsearch` on:

- `"Two men escape from a maximum security prison"`
- `"A young farm boy joins rebels against an evil galactic empire"`

**Questions:**
1. Which tokens have the highest weights?
2. Which tokens are **not** in the input text? Why are they there?

---

## Task 7: Build a semantic_text Index (Basic)

1. Create `my-semantic` with `title` (text), `overview` (text, `copy_to: overview_semantic`) and `overview_semantic` (`semantic_text`, `inference_id: .elser-2-elasticsearch`)
2. Fill it with `_reindex` from `movies` — only the movies with ids 1, 260, 318, 858 and 2571
3. Check `GET /my-semantic/_count`, then run a `semantic` query for `"computer hacker discovers the truth"`

**Question:** Which movie comes first? `_reindex` copied only `title` and `overview` — how did `overview_semantic` get filled?

> **Hint:** `_reindex` takes a `source.query` (`ids` query) and `source._source` (field list).

---

## Task 8: Keyword vs Semantic (Intermediate)

On `movies-embeddings`, run each query three ways: BM25 `match` on `overview`, `semantic` on `overview_semantic` (ELSER), and E5 kNN.

| Query |
|-------|
| `"jailbreak"` |
| `"mobsters"` |
| `"a toy cowboy gets jealous"` |
| `"dinosaurs"` |

**Questions:**
1. Which queries does BM25 miss entirely? Which method wins each query?
2. The data has no dinosaur films. What do the semantic methods return, and why is that a problem?

---

## Task 9: Semantic Search with Filters and Highlighting (Intermediate)

Find **dramas** from the **1990s** about `"redemption after a crime"`:

1. `bool` with `must`: `semantic` query on `overview_semantic`; `filter`: genres `Drama` and year 1990–1999
2. Add semantic highlighting (`"type": "semantic"`, one fragment)

**Question:** Does the highlighted fragment explain why each movie matched?

> **Hint:** Semantic highlighting returns whole chunks of the `semantic_text` field, best first.

---

<!-- _class: divider -->

# Part C: Hybrid Search with RRF (5 tasks, ~30 min)

---

## Task 10: BM25 vs kNN Side by Side (Basic)

For `"underdog sports team"` on `movies-embeddings`, run (size 5):

1. **BM25:** `multi_match` on `title^2` and `overview`
2. **kNN:** E5 with `query_vector_builder`

Which movies appear in both lists? Which only in one?

---

## Task 11: Hybrid with RRF (Basic)

Combine the two searches from Task 10 with an `rrf` retriever (`rank_window_size: 20`, `size: 5`).

**Questions:**
1. How does the hybrid top 5 compare with the two lists?
2. Remove `rank_window_size`. What does it default to, and does the result change?

> **Hint:** `"retriever": { "rrf": { "retrievers": [ { "standard": { "query": ... } }, { "knn": { ... } } ] } }`

---

## Task 12: Filtered Hybrid Search (Intermediate)

Hybrid search for `"crime family power"` (BM25 + E5 kNN), restricted to movies with genre `Crime` released **before 1980**.

1. With the `filter` parameter of the `rrf` retriever
2. With the same filter repeated inside both sub-retrievers

**Question:** Are the results the same? Which version is easier to maintain?

---

## Task 13: Tuning RRF (Intermediate)

Using the hybrid query from Task 11, compare:

| Experiment | rank_constant | rank_window_size |
|-----------|---------------|-----------------|
| A | 1 | 10 |
| B | 60 | 20 |
| C | 1000 | 50 |

**Questions:**
1. How does the order change between A and C?
2. Which experiment behaves most like "take the best of each list"?

---

## Task 14: Three-way Hybrid (Bonus)

Build a hybrid search for `"mobsters"` with **three** retrievers: BM25, E5 kNN and the ELSER `semantic` query.

Then try the `linear` retriever with the same three, weights 1 / 1 / 2 (`minmax` normalizer).

**Question:** BM25 finds nothing for `"mobsters"` — does hybrid still work? Which retriever carries the result?

---

<!-- _class: divider -->

# Part D: Advanced Techniques (4 tasks, ~20 min)

> Bonus tasks for students who finish early or want to explore further.

---

## Task 15: Build Your Own Vector Index (Intermediate)

1. Create `my-hybrid` with `title` (text), `searchable_text` (text), `year` (integer), `genres` (keyword) and `overview_embedding` (384 dims, cosine, `index_options` type `int4_hnsw`)
2. Fill it with `_reindex` from `movies`, embedding on the way in with the `movies-embeddings-e5` pipeline
3. Search it for `"escaping from prison"` with E5 kNN — same top 3 as `movies-embeddings`?

> **Hint:** `"dest": { "index": "my-hybrid", "pipeline": "movies-embeddings-e5" }`. The pipeline reads `searchable_text`.

---

## Task 16: Defaults and Rescoring (Intermediate)

1. Create `my-defaults` with a 384-dim `dense_vector` **without** `index_options`, and read the effective mapping with `include_defaults=true`. Which type did your track choose?
2. Re-run Task 15's kNN query on `my-hybrid` with `"rescore_vector": { "oversample": 3.0 }`. Does the order change?

**Question:** Why might an upgrade from 8.19 to 9.x change kNN results if you don't set `index_options`?

---

## Task 17: Where Does the Space Go? (Intermediate)

1. Compare `movies-embeddings` and `my-hybrid` with `GET _cat/indices/movies-embeddings,my-hybrid?v&h=index,docs.count,store.size`
2. Run `POST /movies-embeddings/_disk_usage?run_expensive_tasks=true` — which fields take the most space?
3. Estimate the vector RAM for **10 million** movies at `int8_hnsw` and at `bbq_hnsw`

**Question:** Why does `_cat/indices` count more documents than `_count`?

---

## Task 18: Chunking Long Texts (Bonus)

1. Create `my-chunks` with a `semantic_text` field `body` (ELSER endpoint) and `chunking_settings`: `sentence` strategy, `max_chunk_size: 20`, `sentence_overlap: 0`
2. Index one document whose `body` has three unrelated paragraphs (a heist in Las Vegas, an art theft in Paris, a beekeeper in the countryside)
3. Search for `"bee keeping"` with semantic highlighting (2 fragments)

**Question:** Which chunk is highlighted first? What would happen to a 50,000-word document without chunking?

---

## Cleanup

```json
DELETE /vector-demo,my-semantic,my-hybrid,my-defaults,my-chunks,toy-vectors,semantic-demo,chunk-demo,q-default?ignore_unavailable=true
```

> Keep `movies` and `movies-embeddings` to keep experimenting.

To stop the stack (keeping its data): `docker compose -f docker/elk-ml/docker-compose.yml --env-file .env down`
