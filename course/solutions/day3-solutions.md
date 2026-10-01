---
marp: true
theme: epam
paginate: true
class: small
---

<!-- _class: title -->

# Day 3 Solutions

## Instructor answer key — checked in CI on Elasticsearch 8.19 and 9.5

---

## Task 1 — Load Full Dataset

```json
GET /movies/_count
// → {"count": 5100}
```

```json
GET /movies/_search
{ "size": 0, "aggs": { "genre_counts": { "terms": { "field": "genres", "size": 5 } } } }
```

5,100 movies. Top 5 genres: Drama (2,447), Comedy (1,788), Romance (837), Thriller (827), Action (700). A movie
has several genres, so the bucket counts add up to more than 5,100.

---

## Task 2 — Bulk Operations

```json
POST /_bulk
{"index": {"_index": "my-movies", "_id": "demo-9001"}}
{"title": "Bulk Test Movie", "genres": ["Action"], "vote_average": 7.5}
{"index": {"_index": "my-movies", "_id": "demo-9002"}}
{"title": "Bulk Test Movie 2", "genres": ["Drama"], "vote_average": 8.0}
{"delete": {"_index": "my-movies", "_id": "demo-9001"}}
```

```json expect=404
GET /my-movies/_doc/demo-9001
```

```json
GET /my-movies/_doc/demo-9002
// → {"found": true}
```

The operations run in order, so `demo-9001` is created and deleted in the same request. Its `GET` returns
404 with `"found": false`.

---

## Task 3 — Script Update

```json
POST /my-movies/_update/demo-9002
{
  "script": {
    "source": "if (ctx._source.vote_average < params.max) { ctx._source.vote_average += params.boost } else { ctx.op = 'noop' }",
    "params": { "boost": 0.5, "max": 9.0 }
  }
}
// → {"result": "updated"}
```

```json
GET /my-movies/_doc/demo-9002
// → {"_source": {"vote_average": 8.5}}
```

8.0 → 8.5 → 9.0. From the third run on, the response says `"result": "noop"`: the condition is false, the document
is not rewritten, and `_version` stays the same. Without `ctx.op = 'noop'` it would still be re-indexed unchanged.

---

## Task 4 — Reindex with Filter + Alias

```json
POST /_reindex
{
  "source": { "index": "movies", "query": { "range": { "vote_average": { "gte": 8.0 } } } },
  "dest": { "index": "top-movies" }
}
// → {"total": 251}

POST /_aliases
{ "actions": [ { "add": { "index": "top-movies", "alias": "best-films" } } ] }

GET /best-films/_count
// → {"count": 251}
```

```json
GET /top-movies/_mapping/field/genres
// → {"top-movies": {"mappings": {"genres": {"mapping": {"genres": {"type": "text"}}}}}}
```

`top-movies` did not exist, so dynamic mapping made `genres` a `text` field with a `.keyword` sub-field. To keep
the original types, create the index first (with the mappings from `GET /movies/_mapping`), then reindex.

---

## Task 5 — Index Template

```json
PUT /_index_template/movies-template
{
  "index_patterns": ["movies-*"],
  "priority": 100,
  "template": {
    "settings": { "number_of_shards": 1, "number_of_replicas": 0 },
    "mappings": {
      "properties": {
        "title": { "type": "text", "analyzer": "english" },
        "genres": { "type": "keyword" },
        "vote_average": { "type": "float" },
        "release_date": { "type": "date" }
      }
    }
  }
}
```

---

## Task 5 — Index Template (continued)

```json
PUT /movies-test/_doc/1
{ "title": "Test", "genres": ["Drama"], "vote_average": 7.0, "release_date": "2001-05-01" }

GET /movies-test/_mapping
// → {"movies-test": {"mappings": {"properties": {"genres": {"type": "keyword"}, "vote_average": {"type": "float"}}}}}
```

Without the template, dynamic mapping would make `genres` a `text` field with a `.keyword` sub-field, and
`vote_average` a `long` if the first document had a whole number such as `7`.

---

## Task 6 — Compare Analyzers

```json
GET /_analyze
{ "analyzer": "standard", "text": "The runners were running quickly in 2024!" }
// → ["the", "runners", "were", "running", "quickly", "in", "2024"]

GET /_analyze
{ "analyzer": "english", "text": "The runners were running quickly in 2024!" }
// → ["runner", "were", "run", "quickli", "2024"]

GET /_analyze
{ "analyzer": "whitespace", "text": "The runners were running quickly in 2024!" }
// → ["The", "runners", "were", "running", "quickly", "in", "2024!"]

GET /_analyze
{ "analyzer": "keyword", "text": "The runners were running quickly in 2024!" }
// → ["The runners were running quickly in 2024!"]
```

---

## Task 6 — Compare Analyzers (answers)

1. `keyword` — one token, the whole string unchanged. Among the splitting analyzers, `english` (5) drops the stop
   words "the" and "in".
2. `whitespace` and `keyword` — neither lowercases (`whitespace` even keeps the `!`).
3. Stemming: "runners" → `runner`, "running" → `run`, "quickly" → `quickli`. "were" is not on the short English
   stop list, so it stays.

---

## Task 7 — Explicit Mapping

```json
PUT /movies-explicit
{
  "mappings": {
    "properties": {
      "title": { "type": "text", "analyzer": "english", "fields": { "keyword": { "type": "keyword" } } },
      "overview": { "type": "text", "analyzer": "english" },
      "genres": { "type": "keyword" },
      "vote_average": { "type": "float" },
      "release_date": { "type": "date" }
    }
  }
}

PUT /movies-explicit/_doc/1
{ "title": "Test Movie", "overview": "A test.", "genres": ["Drama"], "vote_average": 7.5, "release_date": "1999-01-01" }

GET /movies-explicit/_mapping
// → {"movies-explicit": {"mappings": {"properties": {"title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}}}}}}
```

`movies-explicit` also matches `movies-*`, so the Task 5 template applied as well (1 shard, 0 replicas); the
request's own mappings are merged on top.

---

## Task 8 — Custom Analyzer

```json
PUT /movies-analyzer
{
  "settings": {
    "analysis": {
      "filter": {
        "english_stop": { "type": "stop", "stopwords": "_english_" },
        "english_stemmer": { "type": "stemmer", "language": "english" }
      },
      "analyzer": {
        "movie_analyzer": {
          "type": "custom",
          "char_filter": ["html_strip"],
          "tokenizer": "standard",
          "filter": ["lowercase", "english_stop", "english_stemmer"]
        }
      }
    }
  }
}
```

---

## Task 8 — Custom Analyzer (continued)

```json
GET /movies-analyzer/_analyze
{ "analyzer": "movie_analyzer", "text": "<p>The Amazing Spider-Man was RUNNING through NYC!</p>" }
// → ["amaz", "spider", "man", "run", "through", "nyc"]
```

The `<p>` tags are gone; the standard tokenizer splits "Spider-Man" at the hyphen; "The" and "was" are stop words;
the stemmer turns "Amazing" into `amaz` and "RUNNING" (after lowercasing) into `run`.

---

## Task 9 — Autocomplete with Edge N-gram

```json
PUT /autocomplete-index
{
  "settings": {
    "analysis": {
      "filter": { "autocomplete_filter": { "type": "edge_ngram", "min_gram": 2, "max_gram": 10 } },
      "analyzer": {
        "autocomplete_analyzer": { "tokenizer": "standard", "filter": ["lowercase", "autocomplete_filter"] }
      }
    }
  },
  "mappings": {
    "properties": {
      "title": { "type": "text", "analyzer": "autocomplete_analyzer", "search_analyzer": "standard" }
    }
  }
}

POST /_bulk
{"index": {"_index": "autocomplete-index", "_id": "demo-1"}}
{"title": "Indiana Jones and the Last Crusade"}
{"index": {"_index": "autocomplete-index", "_id": "demo-2"}}
{"title": "Independence Day"}
{"index": {"_index": "autocomplete-index", "_id": "demo-3"}}
{"title": "The Iron Giant"}
{"index": {"_index": "autocomplete-index", "_id": "demo-4"}}
{"title": "Interview with the Vampire"}
{"index": {"_index": "autocomplete-index", "_id": "demo-5"}}
{"title": "A.I. Artificial Intelligence"}
```

---

## Task 9 — Autocomplete (continued)

```json contains=demo-4,demo-5
GET /autocomplete-index/_search
{ "query": { "match": { "title": "int" } } }
// → {"hits": {"total": {"value": 2}}}
```

*Interview with the Vampire* and *A.I. Artificial Intelligence*: every **word** is edge-n-grammed, so
"intelligence" produces `int` too. "Indiana" and "Independence" start with `ind`, "Iron" with `iro`.
The query itself stays one token, `int`, thanks to `search_analyzer: standard`.

---

## Task 10 — Synonym Analyzer

```json
PUT /movies-synonyms
{
  "settings": {
    "analysis": {
      "filter": {
        "movie_synonyms": {
          "type": "synonym_graph",
          "synonyms": [
            "film, movie, picture, flick",
            "scary, horror, frightening, spooky",
            "funny, comedy, humorous, hilarious"
          ]
        }
      },
      "analyzer": {
        "synonym_search": { "tokenizer": "standard", "filter": ["lowercase", "movie_synonyms"] }
      }
    }
  },
  "mappings": {
    "properties": {
      "overview": { "type": "text", "analyzer": "standard", "search_analyzer": "synonym_search" }
    }
  }
}
```

---

## Task 10 — Synonym Analyzer (continued)

```json top=demo-1
PUT /movies-synonyms/_doc/demo-1
{ "overview": "A scary flick about ghosts" }

GET /movies-synonyms/_search
{ "query": { "match": { "overview": "horror movie" } } }
```

Yes: at search time "horror" expands to scary/frightening/spooky and "movie" to film/picture/flick, so the
document matches on both words although it contains neither.

---

## Task 11 — Stats Aggregation

```json
GET /movies/_search
{
  "size": 0,
  "aggs": {
    "rating_stats": { "stats": { "field": "vote_average" } },
    "unique_genres": { "cardinality": { "field": "genres" } }
  }
}
// → {"aggregations": {"rating_stats": {"count": 5055}, "unique_genres": {"value": 19}}}
```

count 5,055 · min 2.3 · max 8.8 · avg ≈ 6.38 · 19 genres. The count is lower than 5,100 because 45 movies have
fewer than 10 ratings and therefore no `vote_average` — metric aggregations skip documents without the field.

---

## Task 12 — Genre Terms Aggregation

```json
GET /movies/_search
{
  "size": 0,
  "aggs": {
    "genres": {
      "terms": { "field": "genres", "size": 15 },
      "aggs": { "avg_rating": { "avg": { "field": "vote_average" } } }
    }
  }
}
```

---

## Task 12 — Genre Terms Aggregation (continued)

Sort the genres by their average rating:

```json
GET /movies/_search
{
  "size": 0,
  "aggs": {
    "genres": {
      "terms": { "field": "genres", "size": 3, "order": { "avg_rating": "desc" } },
      "aggs": { "avg_rating": { "avg": { "field": "vote_average" } } }
    }
  }
}
// → {"aggregations": {"genres": {"buckets": [{"key": "Film-Noir"}, {"key": "War"}, {"key": "Documentary"}]}}}
```

Among the 15 largest genres, War is best rated (≈ 7.0). With `size: 20` Film-Noir wins (≈ 7.41) — with only 59
movies it is the 18th genre by count, so `size: 15` never sees it.

---

## Task 13 — Date Histogram + Avg

```json
GET /movies/_search
{
  "size": 0,
  "aggs": {
    "per_year": {
      "date_histogram": { "field": "release_date", "calendar_interval": "year", "min_doc_count": 10 },
      "aggs": { "avg_rating": { "avg": { "field": "vote_average" } } }
    }
  }
}
```

67 years have at least 10 movies, from 1934 to 2002 (the dataset ends in 2002).

---

## Task 14 — Range Buckets

```json
GET /movies/_search
{
  "size": 0,
  "aggs": {
    "rating_buckets": {
      "range": {
        "field": "vote_average",
        "ranges": [
          { "key": "Poor", "to": 5.0 },
          { "key": "Average", "from": 5.0, "to": 6.5 },
          { "key": "Good", "from": 6.5, "to": 8.0 },
          { "key": "Excellent", "from": 8.0 }
        ]
      },
      "aggs": { "top_genres": { "terms": { "field": "genres", "size": 3 } } }
    }
  }
}
```

Poor 528 (Comedy, Horror, Action) · Average 1,916 (Comedy, Drama, Thriller) · Good 2,360 (Drama, Comedy, Romance) ·
Excellent 251 (Drama, Comedy, Crime). The buckets add up to 5,055 — movies without a rating fall in none.

---

## Task 15 — Pipeline Aggregation

```json
GET /movies/_search
{
  "size": 0,
  "aggs": {
    "by_year": {
      "date_histogram": { "field": "release_date", "calendar_interval": "year", "min_doc_count": 10 },
      "aggs": { "avg_rating": { "avg": { "field": "vote_average" } } }
    },
    "best_year": { "max_bucket": { "buckets_path": "by_year>avg_rating" } }
  }
}
// → {"aggregations": {"best_year": {"keys": ["1934-01-01T00:00:00.000Z"]}}}
```

Without `min_doc_count` the winner is 1921 (7.9) — a year with a single movie. With `min_doc_count: 10`, 1934 wins
(≈ 7.45 over 10 movies): `max_bucket` only sees the buckets the histogram returns.

---

## Task 16 — eCommerce Revenue Analysis

```json
GET /kibana_sample_data_ecommerce/_search
{
  "size": 0,
  "aggs": {
    "by_day": {
      "terms": { "field": "day_of_week_i", "size": 7, "order": { "revenue": "desc" } },
      "aggs": {
        "revenue": { "sum": { "field": "taxful_total_price" } },
        "avg_order": { "avg": { "field": "taxful_total_price" } },
        "top_categories": { "terms": { "field": "category.keyword", "size": 3 } }
      }
    }
  }
}
```

Friday (`day_of_week_i: 4`) earns the most: 770 orders, ≈ 58,216 in revenue, ≈ 75.60 per order; Thursday is close
behind (775 orders, ≈ 57,807). The order count is each bucket's `doc_count`. Men's and Women's Clothing lead every day.

---

## Task 17 — Object vs Nested

```json
PUT /movies-nested
{
  "mappings": {
    "properties": {
      "title": { "type": "text" },
      "cast": {
        "type": "nested",
        "properties": {
          "name": { "type": "keyword" },
          "role": { "type": "text" },
          "billing": { "type": "integer" }
        }
      }
    }
  }
}

POST /_bulk
{"index": {"_index": "movies-nested", "_id": "318"}}
{"title": "The Shawshank Redemption", "cast": [{"name": "Tim Robbins", "role": "Andy Dufresne", "billing": 1}, {"name": "Morgan Freeman", "role": "Red", "billing": 2}]}
{"index": {"_index": "movies-nested", "_id": "47"}}
{"title": "Seven", "cast": [{"name": "Brad Pitt", "role": "Detective Mills", "billing": 1}, {"name": "Morgan Freeman", "role": "Detective Somerset", "billing": 2}]}
{"index": {"_index": "movies-nested", "_id": "6"}}
{"title": "Heat", "cast": [{"name": "Al Pacino", "role": "Vincent Hanna", "billing": 1}, {"name": "Robert De Niro", "role": "Neil McCauley", "billing": 2}]}
```

---

## Task 17 — Object vs Nested (continued)

```json expect=empty
GET /movies-nested/_search
{
  "query": {
    "nested": {
      "path": "cast",
      "query": {
        "bool": {
          "must": [
            { "term": { "cast.name": "Morgan Freeman" } },
            { "term": { "cast.billing": 1 } }
          ]
        }
      }
    }
  }
}
```

No hits: name and billing must match **the same** cast member. With `"billing": 2` the query finds Shawshank and
Seven. Mapped as a plain `object`, the billing-1 query would match both films (a false positive).

---

## Task 18 — Nested Aggregation

```json
GET /movies-nested/_search
{
  "size": 0,
  "aggs": {
    "cast_nested": {
      "nested": { "path": "cast" },
      "aggs": {
        "top_actors": { "terms": { "field": "cast.name", "size": 10 } }
      }
    }
  }
}
```

Morgan Freeman leads with 2 movies; everyone else has 1. `cast_nested.doc_count` (6) counts the hidden cast
documents, not the 3 movies.

---

## Task 19 — Parent-Child Blog Model

```json
PUT /blog
{
  "mappings": {
    "properties": {
      "join_field": { "type": "join", "relations": { "post": "comment" } },
      "title": { "type": "text" },
      "body": { "type": "text" },
      "author": { "type": "keyword" }
    }
  }
}

POST /_bulk
{"index": {"_index": "blog", "_id": "p1"}}
{"title": "Getting started with Elasticsearch", "join_field": "post"}
{"index": {"_index": "blog", "_id": "p2"}}
{"title": "Building Kibana dashboards", "join_field": "post"}
{"index": {"_index": "blog", "_id": "c1", "routing": "p1"}}
{"author": "Alice", "body": "Very helpful, thanks!", "join_field": {"name": "comment", "parent": "p1"}}
{"index": {"_index": "blog", "_id": "c2", "routing": "p1"}}
{"author": "Bob", "body": "What about mappings?", "join_field": {"name": "comment", "parent": "p1"}}
{"index": {"_index": "blog", "_id": "c3", "routing": "p2"}}
{"author": "Carol", "body": "Lens is great.", "join_field": {"name": "comment", "parent": "p2"}}
```

---

## Task 19 — Parent-Child (continued)

```json contains=p1
GET /blog/_search
{ "query": { "has_child": { "type": "comment", "query": { "term": { "author": "Alice" } } } } }
// → {"hits": {"total": {"value": 1}}}
```

```json contains=c1,c2
GET /blog/_search
{ "query": { "has_parent": { "parent_type": "post", "query": { "match": { "title": "Elasticsearch" } } } } }
// → {"hits": {"total": {"value": 2}}}
```

`has_child` returns the post Alice commented on; `has_parent` returns both comments on the Elasticsearch post. In
`_bulk`, routing goes in the action line (`"routing": "p1"`) instead of the URL.

---

## Cleanup

```json
DELETE /my-movies,top-movies,movies-test,movies-explicit,movies-analyzer,autocomplete-index,movies-synonyms,movies-nested,blog?ignore_unavailable=true

DELETE /_index_template/movies-template
```
