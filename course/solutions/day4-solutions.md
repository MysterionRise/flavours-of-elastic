---
marp: true
theme: epam
paginate: true
class: small
---

<!-- _class: title -->

# Day 4 Solutions

## Instructor answer key — checked in CI on Elasticsearch 8.19 and 9.5

---

## Task 1 — Toy Vectors

```json
PUT /vector-demo
{
  "mappings": {
    "properties": {
      "title": { "type": "text" },
      "embedding": { "type": "dense_vector", "dims": 3, "similarity": "cosine" }
    }
  }
}

POST /vector-demo/_bulk
{"index": {"_id": "1"}}
{"title": "Action Movie", "embedding": [1.0, 0.2, 0.1]}
{"index": {"_id": "2"}}
{"title": "Romantic Comedy", "embedding": [0.1, 1.0, 0.2]}
{"index": {"_id": "3"}}
{"title": "Sci-Fi Thriller", "embedding": [0.8, 0.3, 0.9]}
{"index": {"_id": "4"}}
{"title": "Action Comedy", "embedding": [0.7, 0.8, 0.2]}
{"index": {"_id": "5"}}
{"title": "Horror Film", "embedding": [0.2, 0.1, 0.9]}
```

---

## Task 1 — Toy Vectors (continued)

```json top=1
GET /vector-demo/_search
{ "knn": { "field": "embedding", "query_vector": [0.9, 0.3, 0.2], "k": 3, "num_candidates": 10 } }
```

```json top=2
GET /vector-demo/_search
{ "knn": { "field": "embedding", "query_vector": [0.1, 0.9, 0.1], "k": 3, "num_candidates": 10 } }
```

`[0.9, 0.3, 0.2]` → Action Movie (0.993), Action Comedy (0.934), Sci-Fi Thriller (0.911): the vectors pointing the
same way (a large first dimension). `[0.1, 0.9, 0.1]` → Romantic Comedy (0.998), Action Comedy, Sci-Fi Thriller.
For `cosine`, `_score = (1 + cosine) / 2`: Action Movie's cosine is 0.986.

---

## Task 2 — The Inference API

```json
POST _inference/text_embedding/.multilingual-e5-small-elasticsearch
{ "input": "a heist that goes wrong" }

POST _inference/text_embedding/.multilingual-e5-small-elasticsearch
{ "input": ["a heist that goes wrong", "un braquage qui tourne mal"] }
```

```json contains=6
GET /movies-embeddings/_search
{
  "knn": {
    "field": "overview_embedding", "k": 5, "num_candidates": 50,
    "query_vector_builder": { "text_embedding": {
      "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "a heist that goes wrong" } }
  },
  "_source": ["title", "year"]
}
```

384 numbers per text; a list input returns one embedding per text. The kNN search returns Heat and Clockwise first,
then crime and caper films such as The Usual Suspects, Rififi and Secret Agent. A `match` on `overview` finds only
Heat and Rififi, through the word "heist".

E5 runs as a different model build on x86 and Arm, so near-ties (scores within ~0.005) can swap places between
machines; the checks in this key assert only the robust results.

---

## Task 3 — Filtered kNN

```json contains=924,260 min=5
GET /movies-embeddings/_search
{
  "knn": {
    "field": "overview_embedding", "k": 5, "num_candidates": 50,
    "query_vector_builder": { "text_embedding": {
      "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "space adventure" } },
    "filter": { "range": { "year": { "lt": 1980 } } }
  },
  "_source": ["title", "year"]
}
```

---

## Task 3 — Filtered kNN (continued)

```json contains=1917,4343 min=5
GET /movies-embeddings/_search
{
  "knn": {
    "field": "overview_embedding", "k": 5, "num_candidates": 50,
    "query_vector_builder": { "text_embedding": {
      "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "space adventure" } },
    "filter": { "bool": { "filter": [
      { "term": { "genres": "Sci-Fi" } },
      { "range": { "year": { "gte": 1990 } } }
    ] } }
  },
  "_source": ["title", "year", "genres"]
}
```

Unfiltered, the top 5 mixes decades. Before 1980: 2001: A Space Odyssey, Voyage to the Bottom of the Sea, then films
such as Planet of the Apes, Star Wars and Around the World in 80 Days. Sci-Fi from 1990: Armageddon, Evolution, Dark City, then films
such as Twelve Monkeys or The Matrix. You still get 5 hits each time: the filter is applied **during** the search, so kNN looks for the 5
nearest movies **among** the matching ones.

---

## Task 4 — Multilingual Search

```json contains=858,1221
GET /movies-embeddings/_search
{
  "knn": { "field": "overview_embedding", "k": 3, "num_candidates": 50,
    "query_vector_builder": { "text_embedding": {
      "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "famille mafieuse sicilienne" } } },
  "_source": ["title"]
}
```

```json contains=60
GET /movies-embeddings/_search
{
  "knn": { "field": "overview_embedding", "k": 3, "num_candidates": 50,
    "query_vector_builder": { "text_embedding": {
      "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "ковбой қуыршақ ойыншық" } } },
  "_source": ["title"]
}
```

---

## Task 4 — Multilingual Search (continued)

```json expect=empty
GET /movies-embeddings/_search
{ "query": { "match": { "overview": "famille mafieuse sicilienne" } }, "_source": ["title"] }
```

French → The Godfather, The Godfather: Part II; Kazakh → The Indian in the Cupboard and Jumanji (toys and a game that
come alive), with Toy Story right behind. The French
`match` on `overview` finds nothing: the english analyzer turns the query into French terms that no English
overview contains. E5 maps every language into one vector space, so "famille mafieuse" lands next to "crime family".

---

## Task 5 — num_candidates and similarity

```json
GET /movies-embeddings/_search
{
  "knn": {
    "field": "overview_embedding", "k": 5, "num_candidates": 5,
    "query_vector_builder": { "text_embedding": {
      "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "escaping from prison" } }
  },
  "_source": ["title"]
}
```

---

## Task 5 — num_candidates and similarity (continued)

```json min=5
GET /movies-embeddings/_search
{
  "knn": {
    "field": "overview_embedding", "k": 5, "num_candidates": 200, "similarity": 0.8,
    "query_vector_builder": { "text_embedding": {
      "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "escaping from prison" } }
  },
  "_source": ["title"]
}
```

```json expect=empty
GET /movies-embeddings/_search
{
  "knn": {
    "field": "overview_embedding", "k": 5, "num_candidates": 200, "similarity": 0.85,
    "query_vector_builder": { "text_embedding": {
      "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "escaping from prison" } }
  },
  "_source": ["title"]
}
```

---

## Task 5 — num_candidates and similarity (answer)

With 200 movies the results are stable from about `num_candidates: 50` (with 5, the 5th hit can change); `took` barely
moves at this size. `similarity` is a minimum **cosine** (not `_score`): 0.8 keeps the 5 hits (their cosine is
0.81–0.83, `_score` 0.90–0.91), 0.85 keeps none. That is how you tell kNN "nothing relevant" instead of always
returning k movies.

---

## Task 6 — Look Inside ELSER

```json
POST _inference/sparse_embedding/.elser-2-elasticsearch
{ "input": "Two men escape from a maximum security prison" }

POST _inference/sparse_embedding/.elser-2-elasticsearch
{ "input": "A young farm boy joins rebels against an evil galactic empire" }
```

Prison sentence: `prison` 2.18, `maximum` 2.05, `escape` 1.79, `men`, `jail` 1.35, … `prisoner`, `brothers`. Farm boy:
`farm` 2.26, `boy`, `young`, `galactic`, `empire`, `rebels`, `evil`, `novel`, `rebel`, `farmer`. Expansions such as
`jail`, `prisoner`, `farmer` and `novel` are not in the text: ELSER learned which terms co-occur with the input,
so documents and queries meet even when they use different words.

---

## Task 7 — Build a semantic_text Index

```json
PUT /my-semantic
{
  "mappings": {
    "properties": {
      "title": { "type": "text" },
      "overview": { "type": "text", "copy_to": "overview_semantic" },
      "overview_semantic": { "type": "semantic_text", "inference_id": ".elser-2-elasticsearch" }
    }
  }
}

POST /_reindex
{
  "source": {
    "index": "movies",
    "query": { "ids": { "values": ["1", "260", "318", "858", "2571"] } },
    "_source": ["title", "overview"]
  },
  "dest": { "index": "my-semantic" }
}
```

---

## Task 7 — Build a semantic_text Index (continued)

```json top=2571
GET /my-semantic/_search
{ "query": { "semantic": { "field": "overview_semantic", "query": "computer hacker discovers the truth" } } }
```

`_count` is 5. The Matrix wins by far (19.96 vs 2.6 for the next). `copy_to` runs at index time for every document,
including the ones `_reindex` writes, so `overview_semantic` was filled from `overview` — and embedded by ELSER.

---

## Task 8 — Keyword vs Semantic

```json expect=empty
GET /movies-embeddings/_search
{ "query": { "match": { "overview": "mobsters" } } }
```

```json contains=858,16
GET /movies-embeddings/_search
{ "query": { "semantic": { "field": "overview_semantic", "query": "mobsters" } }, "_source": ["title"] }
```

```json
GET /movies-embeddings/_search
{
  "knn": { "field": "overview_embedding", "k": 4, "num_candidates": 50,
    "query_vector_builder": { "text_embedding": {
      "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "dinosaurs" } } },
  "_source": ["title"]
}
```

---

## Task 8 — Keyword vs Semantic (results)

| Query | BM25 (`match` on `overview`) | ELSER (`semantic`) | E5 (kNN) |
|-------|------|-------|----|
| `jailbreak` | 0 hits | Raw Deal, Rififi, Shawshank, The Green Mile | Raw Deal, Rififi, The Defiant Ones, … |
| `mobsters` | 0 hits | The Godfather, Rififi, Casino, Raw Deal | weak (Super Troopers, …) |
| `a toy cowboy gets jealous` | Toy Story first | Toy Story first | Toy Story first |
| `dinosaurs` | 0 hits | Evolution, … — no dinosaur film exists | Raiders of the Lost Ark, … |

---

## Task 8 — Keyword vs Semantic (answer)

BM25 misses `jailbreak`, `mobsters` and `dinosaurs` entirely: no overview contains those words. ELSER is best on
`mobsters` (its expansions know "mafia", "crime family"); all three find Toy Story for the jealous toy cowboy. There
are no dinosaur films, but semantic search **always** returns its nearest neighbours — set `similarity` (kNN) or
`min_score`, or combine with BM25, so "nothing relevant" stays empty.

---

## Task 9 — Semantic Search with Filters and Highlighting

```json contains=36,318
GET /movies-embeddings/_search
{
  "query": {
    "bool": {
      "must": { "semantic": { "field": "overview_semantic", "query": "redemption after a crime" } },
      "filter": [
        { "term": { "genres": "Drama" } },
        { "range": { "year": { "gte": 1990, "lte": 1999 } } }
      ]
    }
  },
  "highlight": { "fields": { "overview_semantic": { "type": "semantic", "number_of_fragments": 1 } } },
  "_source": ["title", "year"],
  "size": 5
}
```

Dead Man Walking, The Shawshank Redemption, Savior, Fargo, … Each highlight is the matching chunk itself: *"A nun becomes
the spiritual advisor to a death row inmate…"* — readable evidence for why a movie matched, which a dense score
alone does not give.

---

## Task 10 — BM25 vs kNN Side by Side

```json contains=54
GET /movies-embeddings/_search
{
  "query": { "multi_match": { "query": "underdog sports team", "fields": ["title^2", "overview"] } },
  "size": 5, "_source": ["title"]
}
```

```json top=54
GET /movies-embeddings/_search
{
  "knn": { "field": "overview_embedding", "k": 5, "num_candidates": 50,
    "query_vector_builder": { "text_embedding": {
      "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "underdog sports team" } } },
  "_source": ["title"]
}
```

BM25: Designing Woman, Son of Flubber, The Big Green, Lone Wolf McQuade, Mortal Kombat (words like "team").
kNN: The Big Green, The Odd Couple, The Defiant Ones, Cats & Dogs, Rocky. Only The Big Green is in both.

---

## Task 11 — Hybrid with RRF

```json top=54 contains=3360
GET /movies-embeddings/_search
{
  "retriever": {
    "rrf": {
      "retrievers": [
        { "standard": { "query": {
            "multi_match": { "query": "underdog sports team", "fields": ["title^2", "overview"] } } } },
        { "knn": { "field": "overview_embedding", "k": 20, "num_candidates": 50,
            "query_vector_builder": { "text_embedding": {
              "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "underdog sports team" } } } }
      ],
      "rank_window_size": 20
    }
  },
  "size": 5, "_source": ["title"]
}
```

The Big Green (top of both lists) comes first, then Son of Flubber, Armageddon, Hoosiers and Designing Woman. Hoosiers
and Armageddon were in neither top 5: they rank well in **both** windows of 20. `rank_window_size` defaults to
`size` (5): each retriever then contributes only its top 5, and the result is the two lists interleaved.

---

## Task 12 — Filtered Hybrid Search

```json contains=858,1221
GET /movies-embeddings/_search
{
  "retriever": {
    "rrf": {
      "retrievers": [
        { "standard": { "query": {
            "multi_match": { "query": "crime family power", "fields": ["title^2", "overview"] } } } },
        { "knn": { "field": "overview_embedding", "k": 20, "num_candidates": 50,
            "query_vector_builder": { "text_embedding": {
              "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "crime family power" } } } }
      ],
      "rank_window_size": 20,
      "filter": { "bool": { "filter": [ { "term": { "genres": "Crime" } }, { "range": { "year": { "lt": 1980 } } } ] } }
    }
  },
  "size": 5, "_source": ["title", "year"]
}
```

The Godfather, The Godfather: Part II, Cape Fear, Take the Money and Run, Dr. Mabuse: The Gambler. Repeating the
filter inside the `standard` query (`bool.filter`) and the `knn` (`filter`) gives the same result; the `rrf`
`filter` states it once, so the two retrievers can't drift apart.

---

## Task 13 — Tuning RRF

```json top=54
GET /movies-embeddings/_search
{
  "retriever": {
    "rrf": {
      "retrievers": [
        { "standard": { "query": {
            "multi_match": { "query": "underdog sports team", "fields": ["title^2", "overview"] } } } },
        { "knn": { "field": "overview_embedding", "k": 10, "num_candidates": 50,
            "query_vector_builder": { "text_embedding": {
              "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "underdog sports team" } } } }
      ],
      "rank_constant": 1,
      "rank_window_size": 10
    }
  },
  "size": 5, "_source": ["title"]
}
```

---

## Task 13 — Tuning RRF (answer)

Experiment A (`rank_constant: 1`) is shown: The Big Green 0.75, Designing Woman 0.5, Son of Flubber 0.46 — each
retriever's #1 dominates ("best of each list"). With 1000 the scores flatten and movies found by both retrievers
win, even from lower ranks; 60 sits in between.

---

## Task 14 — Three-way Hybrid

```json contains=858
GET /movies-embeddings/_search
{
  "retriever": {
    "rrf": {
      "retrievers": [
        { "standard": { "query": { "multi_match": { "query": "mobsters", "fields": ["title^2", "overview"] } } } },
        { "knn": { "field": "overview_embedding", "k": 20, "num_candidates": 50,
            "query_vector_builder": { "text_embedding": {
              "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "mobsters" } } } },
        { "standard": { "query": { "semantic": { "field": "overview_semantic", "query": "mobsters" } } } }
      ],
      "rank_window_size": 20
    }
  },
  "size": 5, "_source": ["title"]
}
```

---

## Task 14 — Three-way Hybrid (linear)

```json contains=858
GET /movies-embeddings/_search
{
  "retriever": {
    "linear": {
      "retrievers": [
        { "retriever": { "standard": { "query": { "multi_match": { "query": "mobsters", "fields": ["title^2", "overview"] } } } },
          "weight": 1, "normalizer": "minmax" },
        { "retriever": { "knn": { "field": "overview_embedding", "k": 20, "num_candidates": 50,
            "query_vector_builder": { "text_embedding": {
              "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "mobsters" } } } },
          "weight": 1, "normalizer": "minmax" },
        { "retriever": { "standard": { "query": { "semantic": { "field": "overview_semantic", "query": "mobsters" } } } },
          "weight": 2, "normalizer": "minmax" }
      ]
    }
  },
  "size": 5, "_source": ["title"]
}
```

Yes: BM25 contributes nothing for `mobsters`, and RRF simply fuses the two lists that have results — The Godfather
comes first, with Casino and The Usual Suspects close behind. In the `linear` version ELSER's weight 2 dominates:
The Godfather, Rififi, Casino, Raw Deal, Batman.

---

## Task 15 — Build Your Own Vector Index

```json
PUT /my-hybrid
{
  "mappings": {
    "properties": {
      "title": { "type": "text" },
      "searchable_text": { "type": "text" },
      "year": { "type": "integer" },
      "genres": { "type": "keyword" },
      "overview_embedding": {
        "type": "dense_vector", "dims": 384, "similarity": "cosine",
        "index_options": { "type": "int4_hnsw" }
      }
    }
  }
}

POST /_reindex
{
  "source": { "index": "movies", "_source": ["title", "searchable_text", "year", "genres"] },
  "dest": { "index": "my-hybrid", "pipeline": "movies-embeddings-e5" }
}
// → {"total": 200, "failures": []}
```

---

## Task 15 — Build Your Own Vector Index (continued)

```json contains=1262,4998
GET /my-hybrid/_search
{
  "knn": { "field": "overview_embedding", "k": 3, "num_candidates": 50,
    "query_vector_builder": { "text_embedding": {
      "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "escaping from prison" } } },
  "_source": ["title"]
}
```

On 9.5 the top 3 matches `movies-embeddings` (The Great Escape, The Defiant Ones, The Shawshank Redemption). On 8.19
`int4_hnsw` swaps Shawshank for Raw Deal at #3: 4 bits per dimension lose enough precision to reorder close
neighbours (their scores differ by 0.005). `dest.pipeline` embedded every reindexed movie on the way in.

---

## Task 16 — Defaults and Rescoring

```json
PUT /my-defaults
{ "mappings": { "properties": { "v": { "type": "dense_vector", "dims": 384, "similarity": "cosine" } } } }

GET /my-defaults/_mapping/field/v?include_defaults=true
```

```json contains=318,1262
GET /my-hybrid/_search
{
  "knn": { "field": "overview_embedding", "k": 3, "num_candidates": 50,
    "query_vector_builder": { "text_embedding": {
      "model_id": ".multilingual-e5-small-elasticsearch", "model_text": "escaping from prison" } },
    "rescore_vector": { "oversample": 3.0 } },
  "_source": ["title"]
}
```

8.19 picks `int8_hnsw`; 9.5 picks `bbq_hnsw` with `rescore_vector.oversample: 3.0` (9.1+, 384+ dims). With
`rescore_vector` the `int4_hnsw` search re-ranks 9 candidates with the float vectors, and Shawshank is back at #3 on
8.19 too. An upgrade changes the default quantization of every index created without `index_options` — results
(and memory) change silently, so set it explicitly.

---

## Task 17 — Where Does the Space Go?

```json
GET _cat/indices/movies-embeddings,my-hybrid?v&h=index,docs.count,store.size

POST /movies-embeddings/_disk_usage?run_expensive_tasks=true
```

`my-hybrid` is ~1.1 MB on 9.5 (3.5 MB on 8.19, which also keeps the vectors in `_source`); `movies-embeddings` 4 MB
(6.6 MB on 8.19) — it adds BM25 fields and ELSER. `_disk_usage`: the E5 vectors (~380 KB) and the ELSER chunks
(~420 KB) dominate; the text fields are tens of KB. RAM for 10 M vectors: int8 ≈ 10 M × 388 B ≈ 3.9 GB, BBQ ≈
10 M × 62 B ≈ 0.6 GB (plus the HNSW graph, ~0.6 GB at `m: 16`). `_cat/indices` counts the hidden nested chunk
documents of `overview_semantic`; `_count` counts movies.

---

## Task 18 — Chunking Long Texts

```json
PUT /my-chunks
{
  "mappings": {
    "properties": {
      "body": {
        "type": "semantic_text",
        "inference_id": ".elser-2-elasticsearch",
        "chunking_settings": { "strategy": "sentence", "max_chunk_size": 20, "sentence_overlap": 0 }
      }
    }
  }
}

PUT /my-chunks/_doc/1
{ "body": "The heist crew plans the robbery of a casino in Las Vegas. They study the vault for weeks and recruit a safecracker. Meanwhile a detective in Paris investigates a series of art thefts at the Louvre. She suspects an insider. Years later a quiet farmer raises bees in the countryside. He sells honey at the village market." }
```

```json top=1
GET /my-chunks/_search
{
  "query": { "semantic": { "field": "body", "query": "bee keeping" } },
  "highlight": { "fields": { "body": { "type": "semantic", "number_of_fragments": 2 } } }
}
```

The beekeeper chunk is highlighted first: with 20-word sentence chunks each paragraph is its own chunk, embedded on
its own. Without chunking, a 50,000-word document would be one embedding (models read ~512 tokens, the rest is cut
off) — a single vague vector for a whole book.

---

## Cleanup

```json
DELETE /vector-demo,my-semantic,my-hybrid,my-defaults,my-chunks?ignore_unavailable=true
```
