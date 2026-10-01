---
marp: true
theme: epam
paginate: true
---

<!-- _class: title -->

# Indexing, Text Analysis & Aggregations

## Day 3 — 4-Day Elasticsearch Course

Elasticsearch 8.19 / 9.5 | Bulk API · Analyzers · Mappings · Aggregations · Nested/Join

---

# Agenda

1. Index API & Bulk Operations
2. **Practice 3A** — Indexing
3. Text Analysis Pipeline
4. Mappings & Field Types
5. **Practice 3B** — Analyzers & Mappings
6. Aggregations
7. **Practice 3C** — Aggregations
8. Nested & Join Types
9. **Practice 3D** — Nested/Join
10. Summary

---

<!-- _class: divider -->

# Index API & Bulk Operations

## Efficient data management

---

<!-- _class: small -->

# Index Settings

Every index has configurable settings:

```json
PUT /settings-demo
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "refresh_interval": "5s"
  },
  "mappings": {
    "properties": {
      "title": { "type": "text" }
    }
  }
}
```

- `settings` — shards, replicas, refresh, and `analysis` (custom analyzers, later today)
- `mappings` — the field types (after the analysis section)

---

# Index Settings: Defaults

| Setting | Default | Note |
|---------|---------|------|
| `number_of_shards` | 1 | Fixed at creation |
| `number_of_replicas` | 1 | Dynamic — on one node replicas stay unassigned (yellow) |
| `refresh_interval` | `1s` | Dynamic — `-1` disables refresh |

Dynamic settings change on a live index:

```json
PUT /settings-demo/_settings
{ "index": { "refresh_interval": "1s" } }
```

> Shard count is **fixed at creation time**. To change it, use `_split` / `_shrink` or reindex.

---

<!-- _class: small -->

# Bulk API

Index many documents in one request:

```json
POST /_bulk
{"index": {"_index": "my-movies", "_id": "demo-1"}}
{"title": "Movie A", "genres": ["Drama"], "vote_average": 7.5}
{"index": {"_index": "my-movies", "_id": "demo-2"}}
{"title": "Movie B", "genres": ["Action"], "vote_average": 4.2}
{"create": {"_index": "my-movies", "_id": "demo-3"}}
{"title": "Movie C", "genres": ["Comedy"], "vote_average": 6.1}
{"update": {"_index": "my-movies", "_id": "demo-1"}}
{"doc": {"vote_average": 8.0}}
{"delete": {"_index": "my-movies", "_id": "demo-3"}}
```

**Actions:** `index` (create or replace), `create` (fails if the ID exists), `update` (partial), `delete` (no document line)

> Demo documents use `demo-N` IDs in a scratch index, `my-movies` — the real `movies` index stays intact.

---

<!-- _class: small -->

# Bulk API: Error Handling

The bulk response tells you which operations succeeded/failed:

```json
{
  "took": 30,
  "errors": true,
  "items": [
    { "index":  { "_id": "demo-1", "status": 200, "result": "updated" } },
    { "create": { "_id": "demo-3", "status": 409,
                  "error": { "type": "version_conflict_engine_exception" } } }
  ]
}
```

- Check `errors: true` to see if any operations failed
- Each item has its own `status` code — e.g. `create` on an existing ID gives 409
- Failed items don't affect successful ones (partial success)

> **Performance tip:** Size matters more than document count — start around 5–15 MB per request and measure.

---

# Update Operations

### Partial update (merge)

```json
POST /my-movies/_update/demo-1
{
  "doc": {
    "tagline": "Hope can set you free"
  }
}
```

Only the fields in `doc` change; a new field like `tagline` gets a dynamic mapping.

---

# Update Operations: Script

```json
POST /my-movies/_update/demo-1
{
  "script": {
    "source": "ctx._source.vote_average += params.boost",
    "params": { "boost": 0.5 }
  }
}
```

Use `params` instead of literals: Elasticsearch caches the compiled script, and a changed literal would compile a new one.

---

# Update Operations: Upsert

### Upsert (insert if not exists)

```json
POST /my-movies/_update/demo-4
{
  "doc": { "vote_average": 8.0 },
  "upsert": { "title": "New Movie", "vote_average": 8.0 }
}
```

- If document `demo-4` exists → merge `doc` fields
- If document `demo-4` does not exist → insert the `upsert` body
- `"doc_as_upsert": true` inserts `doc` itself when the document is missing

---

# Delete Operations

### Delete by ID

```json
DELETE /my-movies/_doc/demo-4
```

---

# Delete by Query

```json
POST /my-movies/_delete_by_query
{
  "query": {
    "range": {
      "vote_average": { "lt": 5.0 }
    }
  }
}
// → {"deleted": 1}
```

> `_delete_by_query` searches first, then deletes every match — heavy on large indices. Add `?wait_for_completion=false` to run it as a background task.

---

# Refresh, Translog & Flush

```
write ─┬─► in-memory buffer ──[refresh]──► new segment → searchable
       └─► translog (fsynced before the write returns) → durable
[flush] = Lucene commit: segments fsynced to disk, translog trimmed
```

```json
# Make recent writes searchable now
POST /my-movies/_refresh

# Commit segments to disk and trim the translog
POST /my-movies/_flush
```

---

# Refresh, Translog & Flush: Timing

| Operation | When | What it gives you |
|-----------|------|-------------------|
| Refresh | Every 1 s (on indices searched in the last 30 s) | New documents become searchable |
| Translog fsync | Every write request (default) | Acknowledged writes survive a crash |
| Flush | Automatic, as the translog grows | Lucene commit; the translog can be trimmed |

> You rarely call `_flush` yourself — durability comes from the translog.

> **Performance tip:** For big bulk loads set `"refresh_interval": "-1"`, then restore it and `_refresh` afterwards.

---

<!-- _class: small -->

# Reindex API

Copies **documents** from one index to another — not mappings or settings. Create the destination first, or it gets dynamic mappings:

```json
PUT /movies-v2
{
  "mappings": {
    "properties": {
      "title": {
        "type": "text", "analyzer": "english",
        "fields": { "keyword": { "type": "keyword" } }
      },
      "genres": { "type": "keyword" },
      "year": { "type": "integer" },
      "vote_average": { "type": "float" }
    }
  }
}

POST /_reindex
{ "source": { "index": "movies" }, "dest": { "index": "movies-v2" } }
```

---

<!-- _class: small -->

# Reindex with Query Filter

```json
POST /_reindex
{
  "source": { "index": "movies", "query": { "range": { "vote_average": { "gte": 7.0 } } } },
  "dest": { "index": "good-movies" }
}

GET /good-movies/_mapping/field/genres
```

`good-movies` did not exist, so dynamic mapping made `genres` a `text` field with a `.keyword` sub-field — not the `keyword` it is in `movies`.

> Reindex when you need new mappings, analyzers or shard counts — an existing field can't change type in place.

---

<!-- _class: small -->

# Aliases

A virtual name that points to one or more indices — applications query the alias:

```json
# Create an alias
POST /_aliases
{
  "actions": [
    { "add": { "index": "movies", "alias": "catalog" } }
  ]
}
```

```json
# Swap it to the new index (atomic)
POST /_aliases
{
  "actions": [
    { "remove": { "index": "movies", "alias": "catalog" } },
    { "add": { "index": "movies-v2", "alias": "catalog" } }
  ]
}
```

---

# Aliases: Use Cases

```json
GET /catalog/_count
```

Same request as before the swap — now answered by `movies-v2`.

- **Zero-downtime reindexing** — swap the alias from the old to the new index
- **Grouping time-based indices** — `logs-2024-*` → `logs`
- **A/B testing** different mappings or analyzers

> Alias operations are **atomic** — no downtime when swapping indices. An alias can't share its name with an index.

---

<!-- _class: small -->

# Index Templates

Automatically apply settings/mappings when new indices match a pattern:

```json
PUT /_index_template/movies-template
{
  "index_patterns": ["movies-*"],
  "template": {
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 0
    },
    "mappings": {
      "properties": {
        "title": { "type": "text", "analyzer": "english" },
        "genres": { "type": "keyword" }
      }
    }
  },
  "priority": 100
}
```

---

# Index Templates: Usage

A new index called `movies-2024` gets the template's settings and mappings:

```json
PUT /movies-2024/_doc/1
{ "title": "Test Movie", "genres": ["Action"] }

GET /movies-2024/_mapping
```

- Templates apply only when an index is **created** — existing indices are not touched
- Higher `priority` wins when multiple templates match
- Component templates allow reusable building blocks

---

<!-- _class: exercise -->

# Practice 3A

## Indexing Operations

`day3-exercises.md` — Part A (5 tasks) | ~20 min

---

<!-- _class: divider -->

# Text Analysis

## How Elasticsearch understands text

---

# The Analysis Pipeline

```
"The Quick Brown FOX jumped!"
       ↓
┌─────────────────────┐
│   Character Filter   │  → Strip HTML, map characters
├─────────────────────┤
│     Tokenizer        │  → Split into tokens
├─────────────────────┤
│   Token Filters      │  → Lowercase, stemming, stop words
└─────────────────────┘
       ↓
["quick", "brown", "fox", "jump"]     (english analyzer)
```

Each step transforms the text. The final tokens go into the **inverted index**.

---

# The _analyze API

Test any analyzer interactively:

```json
GET /_analyze
{
  "analyzer": "standard",
  "text": "The Quick Brown FOX jumped over the lazy dog!"
}
```

---

# _analyze API: Response

```json
{
  "tokens": [
    { "token": "the", "position": 0 },
    { "token": "quick", "position": 1 },
    { "token": "brown", "position": 2 },
    { "token": "fox", "position": 3 },
    { "token": "jumped", "position": 4 },
    { "token": "over", "position": 5 },
    { "token": "the", "position": 6 },
    { "token": "lazy", "position": 7 },
    { "token": "dog", "position": 8 }
  ]
}
```

9 tokens: lowercased, punctuation removed, no stemming or stop-word removal.

---

# Built-in Analyzers

| Analyzer | Tokenizer | Token Filters | Output for "The Quick FOX!" |
|----------|-----------|---------------|---------------------------|
| `standard` | standard | lowercase | `[the, quick, fox]` |
| `english` | standard | lowercase, stop, stemmer | `[quick, fox]` |
| `whitespace` | whitespace | (none) | `[The, Quick, FOX!]` |
| `keyword` | keyword | (none) | `[The Quick FOX!]` |
| `simple` | letter | lowercase | `[the, quick, fox]` |

---

# Standard Analyzer

```json
GET /_analyze
{
  "analyzer": "standard",
  "text": "The runners were running quickly"
}
// → ["the", "runners", "were", "running", "quickly"]
```

- Splits on word boundaries (Unicode rules), then lowercases
- Keeps every token, including stop words ("the", "were")

---

# English Analyzer

```json
GET /_analyze
{
  "analyzer": "english",
  "text": "The runners were running quickly"
}
// → ["runner", "were", "run", "quickli"]
```

- **Removes stop words** — a short list: "the" goes, "were" stays
- **Stems** words → "running", "runs" and "run" all become `run`, so they match each other
- Stems needn't be real words (`quickli`) — indexing and searching produce the same one

---

# Custom Analyzers

Build your own analysis pipeline:

```json
PUT /analyzer-demo
{
  "settings": {
    "analysis": {
      "analyzer": {
        "my_custom_analyzer": {
          "type": "custom",
          "char_filter": ["html_strip"],
          "tokenizer": "standard",
          "filter": ["lowercase", "stop", "snowball"]
        }
      }
    }
  }
}
```

---

# Testing Custom Analyzers

```json
GET /analyzer-demo/_analyze
{
  "analyzer": "my_custom_analyzer",
  "text": "<p>The Quick Runners are running!</p>"
}
// → ["quick", "runner", "run"]
```

- `html_strip` removes `<p>` tags
- `lowercase` → `the quick runners are running`
- `stop` removes "the", "are"
- `snowball` stems "runners" → "runner", "running" → "run"

---

<!-- _class: small -->

# Synonym Filter

Map related terms to each other:

```json
"filter": {
  "my_synonyms": {
    "type": "synonym_graph",
    "synonyms": [
      "film, movie, picture",
      "scary, horror, frightening",
      "sci-fi => science fiction"
    ]
  }
}
```

- `"film, movie, picture"` — equivalent: each one expands to all three
- `"sci-fi => science fiction"` — one-way replacement (multi-word: hence `synonym_graph`)
- Use it in a **search** analyzer, **after** `lowercase` — changing synonyms then needs no reindex

---

<!-- _class: small -->

# Synonym Filter: Analyzer

```json
PUT /synonym-demo
{
  "settings": {
    "analysis": {
      "filter": {
        "my_synonyms": {
          "type": "synonym_graph",
          "synonyms": ["film, movie, picture", "scary, horror, frightening", "sci-fi => science fiction"]
        }
      },
      "analyzer": {
        "synonym_analyzer": { "tokenizer": "standard", "filter": ["lowercase", "my_synonyms"] }
      }
    }
  },
  "mappings": {
    "properties": { "overview": { "type": "text", "analyzer": "standard", "search_analyzer": "synonym_analyzer" } }
  }
}
```

---

# Synonyms: Try It

```json
PUT /synonym-demo/_doc/1
{ "overview": "A scary story about a haunted house" }

GET /synonym-demo/_search
{ "query": { "match": { "overview": "horror film" } } }
```

- The query `horror film` becomes `(horror OR scary OR frightening) (film OR movie OR picture)`
- It finds the document through "scary" — a word the query never used
- See the expansion: `GET /synonym-demo/_analyze` with `"analyzer": "synonym_analyzer"`

---

<!-- _class: small -->

# Synonyms API

Store synonyms in the cluster instead of the index settings:

```json
PUT /_synonyms/movie-synonyms
{
  "synonyms_set": [
    { "id": "film", "synonyms": "film, movie, picture" },
    { "id": "scary", "synonyms": "scary, horror, frightening" }
  ]
}
```

Reference the set from a search-time filter: `{ "type": "synonym_graph", "synonyms_set": "movie-synonyms", "updateable": true }`. Then edit a rule — the analyzers using it reload, no reindex:

```json
PUT /_synonyms/movie-synonyms/sci-fi
{ "synonyms": "sci-fi => science fiction" }
```

---

<!-- _class: small -->

# Edge N-gram: Autocomplete

Tokenize prefix substrings for type-ahead search:

```json
PUT /autocomplete-demo
{
  "settings": {
    "analysis": {
      "filter": {
        "edge_ngram_filter": {
          "type": "edge_ngram", "min_gram": 2, "max_gram": 15
        }
      },
      "analyzer": {
        "autocomplete_analyzer": {
          "tokenizer": "standard",
          "filter": ["lowercase", "edge_ngram_filter"]
        }
      }
    }
  }
}
```

---

# Edge N-gram: How It Works

```json
GET /autocomplete-demo/_analyze
{ "analyzer": "autocomplete_analyzer", "text": "Matrix" }
// → ["ma", "mat", "matr", "matri", "matrix"]
```

- Each token generates prefix substrings from `min_gram` to `max_gram`
- Typing "mat" matches the indexed token "mat"
- Trade-off: larger index size for instant type-ahead results

---

# search_analyzer

Use different analyzers for **indexing** vs **searching**:

```json
PUT /autocomplete-demo/_mapping
{
  "properties": {
    "title": {
      "type": "text",
      "analyzer": "autocomplete_analyzer",
      "search_analyzer": "standard"
    }
  }
}
```

- **Index time:** `"Matrix"` → `["ma", "mat", "matr", ...]`
- **Search time:** `"mat"` → `["mat"]` (standard, no edge_ngram)
- Without `search_analyzer`, the query would also be edge-n-grammed → bad results

---

<!-- _class: divider -->

# Mappings & Field Types

## Defining your schema

---

# Dynamic Mapping

ES auto-detects field types from the first document:

```json
POST /dynamic-demo/_doc/1
{
  "name": "John",         // → text + keyword
  "age": 30,              // → long
  "score": 9.5,           // → float
  "active": true,         // → boolean
  "created": "2024-01-01" // → date
}

GET /dynamic-demo/_mapping
```

Convenient for prototyping, but not ideal for production.

---

# Explicit Mapping

Define field types upfront:

```json
PUT /explicit-demo
{
  "mappings": {
    "properties": {
      "name": { "type": "text" },
      "age": { "type": "integer" },
      "score": { "type": "float" }
    }
  }
}
```

> **Best practice:** Always define explicit mappings for production indices.

---

# Common Field Types

| Type | Use Case | Example |
|------|----------|---------|
| `text` | Full-text search (analyzed) | Title, description |
| `keyword` | Exact match, sort, aggregate | Genre, status, email |
| `integer` / `long` | Whole numbers | Count, ID |
| `float` / `double` | Decimal numbers | Price, rating |
| `date` | Dates and timestamps | `"2024-01-15"` |
| `boolean` | True/false | `active`, `published` |
| `object` | Nested JSON (flattened) | Address, metadata |
| `nested` | Independent inner objects | Tags with attributes |
| `dense_vector` | ML embeddings | 384-dim E5 vectors (Day 4) |

---

# text vs keyword

```json
"properties": {
  "title": {
    "type": "text",          // Analyzed → inverted index
    "analyzer": "english"    // "The Godfather" → ["godfath"]
  },
  "status": {
    "type": "keyword"        // Exact value → "Published"
  }
}
```

---

# text vs keyword: Comparison

| | `text` | `keyword` |
|--|--------|-----------|
| Analyzed? | Yes (tokenized) | No (exact string) |
| Search with | `match`, `multi_match` | `term`, `terms` |
| Sortable? | No | Yes |
| Aggregatable? | No | Yes |
| Long values | Fine | Values over `ignore_above` are not indexed (dynamic `.keyword`: 256) |

> Use **multi-fields** to get both: full-text search + exact match on the same field.

---

# Multi-fields

Index the same data in **multiple ways**:

```json
"properties": {
  "title": {
    "type": "text",
    "analyzer": "english",
    "fields": {
      "keyword": {
        "type": "keyword",
        "ignore_above": 256
      },
      "autocomplete": {
        "type": "text",
        "analyzer": "autocomplete_analyzer"
      }
    }
  }
}
```

---

<!-- _class: small -->

# Viewing & Updating Mappings

### View current mapping

```json
GET /movies/_mapping
```

### Add a new field (non-breaking)

```json
PUT /movies/_mapping
{ "properties": { "tagline": { "type": "text" } } }
```

### Change an existing field's type — rejected

```json expect=4xx
PUT /movies/_mapping
{ "properties": { "year": { "type": "keyword" } } }
// → 400: mapper [year] cannot be changed from type [integer] to [keyword]
```

> You **cannot change** an existing field's type. Reindex into a new index with the correct mapping.

---

<!-- _class: exercise -->

# Practice 3B

## Analyzers & Mappings

`day3-exercises.md` — Part B (5 tasks) | ~25 min

---

<!-- _class: divider -->

# Aggregations

## Analytics and data exploration

---

# Aggregation Basics

Aggregations let you **summarize data** alongside search results:

```json test=skip
GET /movies/_search
{
  "size": 0,
  "aggs": {
    "my_agg_name": {
      "agg_type": {
        "field": "field_name"
      }
    }
  }
}
```

- `size: 0` — skip search hits, only return aggregation results
- Three types: **Metric**, **Bucket**, **Pipeline**
- Aggregations can be **nested** (bucket inside bucket)

---

# Metric Aggregations

Calculate a single value from documents:

```json
GET /movies/_search
{
  "size": 0,
  "aggs": {
    "avg_rating": {
      "avg": { "field": "vote_average" }
    },
    "max_rating": {
      "max": { "field": "vote_average" }
    },
    "rating_stats": {
      "stats": { "field": "vote_average" }
    }
  }
}
```

---

# Metric Aggregation Types

| Agg | Returns |
|-----|---------|
| `avg`, `sum`, `min`, `max` | Single value |
| `stats` | count, min, max, avg, sum |
| `extended_stats` | + std deviation, variance |
| `cardinality` | Approximate distinct count |
| `percentiles` | Distribution breakdown |

> `stats` is a convenient shortcut — one aggregation returns 5 values. Its `count` only includes documents that have the field.

---

# Bucket Aggregations: terms

Group documents into buckets:

```json
GET /movies/_search
{
  "size": 0,
  "aggs": {
    "genres_breakdown": {
      "terms": {
        "field": "genres",
        "size": 10
      }
    }
  }
}
```

---

# terms Aggregation: Response

```json
"genres_breakdown": {
  "buckets": [
    { "key": "Drama", "doc_count": 2447 },
    { "key": "Comedy", "doc_count": 1788 },
    { "key": "Romance", "doc_count": 837 }
  ]
}
```

- `size` controls how many buckets to return (default: 10), largest first
- Works on `keyword`, numeric, date and boolean fields — not on analyzed `text`
- With several shards, counts can be approximate (`doc_count_error_upper_bound`)

---

# Bucket Aggregations: date_histogram

Group by time intervals:

```json
GET /movies/_search
{
  "size": 0,
  "aggs": {
    "movies_per_year": {
      "date_histogram": { "field": "release_date", "calendar_interval": "year" }
    }
  }
}
```

**Interval options:**
- `"calendar_interval": "year"` / `"month"` / `"week"` / `"day"`
- `"fixed_interval": "30d"` / `"1h"` / `"90m"`

---

<!-- _class: small -->

# Bucket Aggregations: range

Custom numeric range buckets:

```json
GET /movies/_search
{
  "size": 0,
  "aggs": {
    "rating_ranges": {
      "range": {
        "field": "vote_average",
        "ranges": [
          { "to": 6.0, "key": "Low" },
          { "from": 6.0, "to": 8.0, "key": "Medium" },
          { "from": 8.0, "key": "High" }
        ]
      }
    }
  }
}
```

`from` is inclusive, `to` is exclusive.

---

# Bucket Aggregations: histogram

Even intervals (auto-bucketing):

```json
GET /movies/_search
{
  "size": 0,
  "aggs": {
    "movies_by_decade": {
      "histogram": { "field": "year", "interval": 10 }
    }
  }
}
```

Creates buckets keyed by their lower bound: `1910`, `1920`, …, `2000`

- `range` — you define the bucket boundaries
- `histogram` — ES creates even-width buckets automatically

---

<!-- _class: small -->

# Sub-aggregations

Put metric aggs **inside** bucket aggs:

```json
GET /movies/_search
{
  "size": 0,
  "aggs": {
    "genres": {
      "terms": { "field": "genres", "size": 5 },
      "aggs": {
        "avg_rating": {
          "avg": { "field": "vote_average" }
        },
        "best_rated": {
          "max": { "field": "vote_average" }
        }
      }
    }
  }
}
```

---

# Aggregations + Query Scope

Aggregations run on the **filtered result set**:

```json
GET /movies/_search
{
  "size": 0,
  "query": {
    "range": {
      "release_date": {
        "gte": "2000-01-01"
      }
    }
  },
  "aggs": {
    "genre_counts": {
      "terms": { "field": "genres", "size": 10 }
    }
  }
}
```

---

# Pipeline Aggregations

Compute on the output of **other** aggregations:

```json
GET /movies/_search
{
  "size": 0,
  "aggs": {
    "by_year": {
      "date_histogram": { "field": "release_date", "calendar_interval": "year" },
      "aggs": {
        "avg_rating": { "avg": { "field": "vote_average" } }
      }
    },
    "max_avg_rating_year": {
      "max_bucket": { "buckets_path": "by_year>avg_rating" }
    }
  }
}
```

---

# Pipeline Aggregations: Sibling vs Parent

`max_bucket` finds the year with the **highest** average rating — it's a **sibling**: it sits next to `by_year` and returns one result.

| Kind | Where | Examples |
|------|-------|----------|
| **Sibling** | Next to the bucket agg → one result | `max_bucket`, `min_bucket`, `avg_bucket`, `stats_bucket` |
| **Parent** | Inside a histogram → a value per bucket | `cumulative_sum`, `derivative`, `moving_fn`, `bucket_script` |

> `buckets_path` points at the data: `by_year>avg_rating` for a sub-aggregation, `_count` for the document count.

---

# Parent Pipeline: cumulative_sum

```json
GET /movies/_search
{
  "size": 0,
  "aggs": {
    "by_decade": {
      "histogram": { "field": "year", "interval": 10 },
      "aggs": {
        "running_total": {
          "cumulative_sum": { "buckets_path": "_count" }
        }
      }
    }
  }
}
```

Each decade bucket gets `running_total`: the number of movies released up to the end of that decade.

---

# ES|QL vs Aggregations

The same analysis, two syntaxes:

### Query DSL Aggregations

```json
GET /movies/_search
{
  "size": 0,
  "aggs": {
    "genres": {
      "terms": { "field": "genres", "size": 5 },
      "aggs": {
        "avg_rating": { "avg": { "field": "vote_average" } }
      }
    }
  }
}
```

---

# ES|QL: Same Query, Simpler Syntax

```sql
FROM movies
| STATS avg_rating = AVG(vote_average), count = COUNT(*) BY genres
| SORT count DESC
| LIMIT 5
```

- `BY genres` puts a movie in the group of each of its genres — like `terms`
- You need `MV_EXPAND genres` only to filter, sort or keep the genres one row at a time
- Query DSL aggregations are more flexible (deep nesting, pipelines); ES|QL is easier to read

---

# Kibana Lens: Data View

Lens charts a **data view**. Create one for `movies` in Dev Tools (or **Stack Management** → **Data Views**):

```json
POST kbn:/api/data_views/data_view
{
  "data_view": { "id": "movies", "title": "movies", "name": "Movies" },
  "override": true
}
```

- `kbn:` sends the request to Kibana instead of Elasticsearch
- No time field on purpose: charts then show every movie, not just the last 15 minutes

---

# Kibana Lens Visualizations

Turn aggregations into charts without code:

1. **Kibana** → **Visualize Library** → **Create visualization** → **Lens**
2. Pick the **Movies** data view, drag fields to the axes
3. Lens picks the right aggregation for you

**Try these:**
- Bar chart: movie count by genre (`genres` on the X-axis)
- Line chart: average rating by year (`year` on the X-axis, average of `vote_average`)
- Pie chart: rating distribution (`vote_average` with ranges)

> Lens is the recommended way to build dashboards in Kibana.

---

<!-- _class: exercise -->

# Practice 3C

## Aggregations

`day3-exercises.md` — Part C (6 tasks) | ~25 min

---

<!-- _class: divider -->

# Nested & Join Types

## Modeling relationships in Elasticsearch

---

# The Problem with Object Arrays

```json
PUT /blog-flat/_doc/1
{
  "title": "ES Guide",
  "comments": [
    { "author": "Alice", "rating": 5 },
    { "author": "Bob", "rating": 2 }
  ]
}
```

Internally, ES **flattens** this:
```json
{
  "comments.author": ["Alice", "Bob"],
  "comments.rating": [5, 2]
}
```

---

# Object Arrays: The False Positive

"Find posts where **Alice** gave rating **2**":

```json
GET /blog-flat/_search
{
  "query": {
    "bool": {
      "must": [
        { "term": { "comments.author.keyword": "Alice" } },
        { "term": { "comments.rating": 2 } }
      ]
    }
  }
}
```

It finds the post — but Alice gave 5 and Bob gave 2. The association between author and rating is **lost**.

---

# Solution: Nested Type

```json
PUT /blog-nested
{
  "mappings": {
    "properties": {
      "title": { "type": "text" },
      "comments": {
        "type": "nested",
        "properties": {
          "author": { "type": "keyword" },
          "rating": { "type": "integer" }
        }
      }
    }
  }
}
```

Each object in the array is stored as a **separate hidden document** → associations preserved.

---

<!-- _class: small -->

# Nested Query

```json
PUT /blog-nested/_doc/1
{ "title": "ES Guide", "comments": [{ "author": "Alice", "rating": 5 }, { "author": "Bob", "rating": 2 }] }

GET /blog-nested/_search
{
  "query": {
    "nested": {
      "path": "comments",
      "query": { "bool": { "must": [
        { "term": { "comments.author": "Alice" } },
        { "range": { "comments.rating": { "gte": 4 } } }
      ] } }
    }
  }
}
```

Finds the post: **Alice herself** rated it ≥ 4. With `"term": { "comments.rating": 2 }` it now finds nothing. Nested queries need the `nested` wrapper with the `path`.

---

# Nested Aggregation

```json
GET /blog-nested/_search
{
  "size": 0,
  "aggs": {
    "comments": {
      "nested": { "path": "comments" },
      "aggs": {
        "by_author": {
          "terms": { "field": "comments.author" },
          "aggs": { "avg_rating": { "avg": { "field": "comments.rating" } } }
        }
      }
    }
  }
}
```

`nested` steps into the hidden comment documents; `reverse_nested` steps back out to the posts.

---

<!-- _class: small -->

# Join Field Type (Parent-Child)

For truly independent documents with a relationship:

```json
PUT /blog-join
{
  "mappings": {
    "properties": {
      "join_field": {
        "type": "join",
        "relations": {
          "post": "comment"
        }
      },
      "title": { "type": "text" },
      "body": { "type": "text" },
      "author": { "type": "keyword" }
    }
  }
}
```

---

<!-- _class: small -->

# Parent-Child: Indexing

```json
# Parent document
PUT /blog-join/_doc/1
{
  "title": "ES Guide",
  "body": "Learn Elasticsearch...",
  "join_field": "post"
}
```

```json
# Child document (must specify routing!)
PUT /blog-join/_doc/c1?routing=1
{
  "author": "Alice",
  "body": "Great post!",
  "join_field": {
    "name": "comment",
    "parent": "1"
  }
}
```

---

# has_child Query

Find posts that have a comment by Alice:

```json
GET /blog-join/_search
{
  "query": {
    "has_child": {
      "type": "comment",
      "query": {
        "term": { "author": "Alice" }
      }
    }
  }
}
```

Returns the **parent** documents that match the child condition.

---

# has_parent Query

Find comments whose parent post contains "ES":

```json
GET /blog-join/_search
{
  "query": {
    "has_parent": {
      "parent_type": "post",
      "query": {
        "match": { "title": "ES" }
      }
    }
  }
}
```

Returns the **child** documents whose parent matches the condition.

---

# When to Use What

| Approach | Best For | Trade-offs |
|----------|----------|------------|
| **Flat / denormalized** | Most cases | Data duplication, simple queries |
| **Nested** | Small arrays that change together | Extra hidden docs, nested query syntax |
| **Parent-child (join)** | Large child sets, independent updates | Slower queries, routing required |

> **Default choice:** Denormalize. Use nested/join only when you have a clear need.

---

<!-- _class: exercise -->

# Practice 3D

## Nested & Join Types

`day3-exercises.md` — Part D (3 tasks) | ~15 min

---

<!-- _class: divider -->

# Summary

---

# Day 3 Recap

| Topic | Key Concepts |
|-------|-------------|
| **Index API** | Bulk operations, settings, refresh/translog/flush |
| **Reindex & Aliases** | Zero-downtime reindexing, alias swaps |
| **Templates** | Auto-apply settings to matching indices |
| **Text Analysis** | Char filters → Tokenizer → Token filters |
| **Analyzers** | standard, english, custom, synonyms, edge_ngram |
| **Mappings** | Dynamic vs explicit, text vs keyword, multi-fields |
| **Aggregations** | Metric, bucket, sub-aggregations, sibling & parent pipelines |
| **Nested/Join** | Nested objects, parent-child relations |

---

# Day 4 Preview — Semantic Search

Tomorrow (3-hour session):

- **Vector Search** — dense_vector, kNN queries, in-cluster E5 embeddings
- **ELSER** — Elastic's sparse model, the `semantic_text` field
- **Hybrid Search** — combining BM25 + vectors with RRF
- **Advanced** — quantization, chunking, production tips

> **Important:** Switch to the ML stack **before** class tomorrow — see the next slide.

---

<!-- _class: small -->

# Day 4 Setup: Switch to the ML Stack

The ML stack uses the same ports, so stop today's stack first (`down` keeps its data):

```bash
docker compose -f docker/elk-single/docker-compose.yml --env-file .env down

# Two nodes, trial licence (for ELSER and RRF)
docker compose -f docker/elk-ml/docker-compose.yml --env-file .env up -d --wait
```

- On the 9.5 track: stop `elk-9`, start `elk-ml-9`
- Needs 8 GB+ RAM for Docker; first start takes a few minutes
- Linux only: `sudo sysctl -w vm.max_map_count=262144` first

---

<!-- _class: title -->

# Thank You!

## Questions?

Day 3 — Indexing, Text Analysis & Aggregations
