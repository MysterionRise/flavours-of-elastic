---
marp: true
theme: epam
paginate: true
---

<!-- _class: title -->

# Day 1 Solutions

## Instructor answer key — checked in CI on Elasticsearch 8.19 and 9.5

---

## Task 1 — Cluster Inspection

```json
GET _cluster/health

GET _cat/nodes?v&h=name,node.role,master

GET _cat/indices?v&expand_wildcards=all
```

1. **green** on a fresh node: system indices auto-expand their replicas to the node count. It turns
   **yellow** once `movies` exists (Task 2): its default replica cannot be placed on the only node.
2. One node, with every default role (`cdfhilmrstw`).
3. System indices start with `.` (e.g. `.security-*`, `.kibana*`) — hidden by default, hence `expand_wildcards=all`.

---

## Task 2 — Load Sample Data

```bash
python data/load_data.py --dataset movies --size small
```

```json
GET movies/_count
// → {"count": 200}

GET _cat/indices/movies,kibana_sample_data_ecommerce?v&s=index

GET _cat/shards/movies?v
```

1. 200 movies (the curated sample; `--size full` loads 5,100).
2. `kibana_sample_data_ecommerce`.
3. One primary shard each; the `movies` replica is `UNASSIGNED` on a single node.

---

## Task 3 — CRUD Operations

```json
PUT /my-movies/_doc/demo-1
{
  "title": "My Favorite Movie",
  "overview": "An amazing story about...",
  "genres": ["Drama", "Adventure"],
  "vote_average": 9.5,
  "release_date": "2024-01-15"
}

GET /my-movies/_doc/demo-1

POST /my-movies/_update/demo-1
{
  "doc": { "vote_average": 9.0 }
}

DELETE /my-movies/_doc/demo-1
```

```json expect=404
GET /my-movies/_doc/demo-1
```

The update merges `vote_average` into the stored document and bumps `_version`; after the delete the `GET`
returns `404` with `"found": false`.

---

## Task 4 — Understanding Mappings

```json
GET movies/_mapping
```

1. `title`: `text` with the `english` analyzer, plus a `title.keyword` sub-field for exact matches and sorting.
2. `genres`: `keyword` — values are labels (`Sci-Fi`, `Drama`) used for exact filters and aggregations.
3. `vote_average`: `float` (the loader sends an explicit mapping; `vote_count` is an `integer`).
4. Dynamic mapping adds the new field as `text` with a `keyword` sub-field:

```json
PUT /my-movies/_doc/demo-2
{ "title": "Interstellar", "director": "Nolan" }

GET my-movies/_mapping/field/director
// → {"my-movies": {"mappings": {"director": {"mapping": {"director": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}}}}}}}
```

---

## Task 5 — Shard Allocation

```json
GET _cat/shards/movies?v

GET _cluster/allocation/explain
{
  "index": "movies",
  "shard": 0,
  "primary": false
}
```

1. Yes — the replica of `movies` shard 0 is `UNASSIGNED`.
2. The `same_shard` decider: a copy of this shard is already on the only node.
3. With a second node the replica is allocated there and the cluster becomes **green**.

---

## Task 6 — Search Preview

```json contains=260
GET /movies/_search
{
  "query": { "match": { "title": "war" } }
}
```

```json contains=318
GET /movies/_search
{
  "query": {
    "bool": {
      "must": { "term": { "genres": "Drama" } },
      "filter": { "range": { "vote_average": { "gte": 8.5 } } }
    }
  }
}
```

1. Usually 6a: a short `title` field gives high BM25 scores. In 6b every hit scores the same constant —
   `term` on a keyword field matches exactly once per document.
2. `filter` clauses only include or exclude documents; they never add to `_score` (and they are cacheable).

---

## Cleanup

```json
DELETE /my-movies?ignore_unavailable=true
```
