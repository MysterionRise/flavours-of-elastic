---
marp: true
theme: epam
paginate: true
---

<!-- _class: title -->

# Query DSL & ES|QL

## Day 2 — 4-Day Elasticsearch Course

Elasticsearch 8.19 / 9.5 | Full-text · Term-level · Bool · ES|QL

---

# Agenda

1. Query DSL Overview
2. Full-text Queries
3. Term-level & Compound Queries
4. Pagination, Sorting, Highlighting
5. **Practice 2A** — Query DSL
6. ES|QL
7. **Practice 2B** — ES|QL
8. Summary

---

<!-- _class: divider -->

# Query DSL Overview

## The JSON-based query language

---

# The Search Request Envelope

Every search follows the same structure:

```json test=skip
GET /<index>/_search
{
  "query": { ... },          // What to search for
  "_source": [...],          // Which fields to return
  "size": 10,                // Number of results (default: 10)
  "from": 0,                 // Offset for pagination
  "sort": [...],             // Custom sort order
  "highlight": { ... }       // Highlight matching terms
}
```

Only `query` is required — everything else is optional.

---

# Query Context vs Filter Context

| | Query Context | Filter Context |
|--|--------------|----------------|
| **Purpose** | "How well does this match?" | "Does this match? Yes/No" |
| **Scoring** | Calculates `_score` | No scoring |
| **Performance** | Slower (scoring overhead) | Faster + cacheable |
| **Use for** | Full-text search | Exact filters (dates, status, ranges) |

---

# Query Context vs Filter Context: Example

```json
{
  "query": {
    "bool": {
      "must": { ... },    // ← Query context (scored)
      "filter": { ... }   // ← Filter context (not scored, cached)
    }
  }
}
```

> **Rule of thumb:** Use `filter` for anything that doesn't need relevance scoring.

---

# Search Response Anatomy

```json
{
  "took": 5,                          // Time in milliseconds
  "timed_out": false,
  "hits": {
    "total": { "value": 42 },         // Total matching documents
    "max_score": 8.23,                // Highest relevance score
    "hits": [                          // The actual results
      {
        "_index": "movies",
        "_id": "1",
        "_score": 8.23,               // This document's score
        "_source": { ... }            // The document fields
      }
    ]
  }
}
```

---

<!-- _class: divider -->

# Full-text Queries

## match · multi_match · match_phrase

---

# match Query

The **most common** search query — analyzes the input and finds matching documents.

```json
GET /movies/_search
{
  "query": {
    "match": {
      "overview": "space exploration"
    }
  }
}
```

What happens:
1. `"space exploration"` → analyzer → `["space", "exploration"]`
2. Finds documents containing **space** OR **exploration** (default: `or`)
3. Results scored by BM25

---

# match: operator

### Require ALL terms

```json
GET /movies/_search
{
  "query": {
    "match": {
      "overview": {
        "query": "space mission",
        "operator": "and"
      }
    }
  }
}
```

- Default operator is `or` — any term matches
- `"operator": "and"` — all terms must be present

---

# match: minimum_should_match

### Require at least N terms

```json contains=150
GET /movies/_search
{
  "query": {
    "match": {
      "overview": {
        "query": "astronauts lunar mission explosion",
        "minimum_should_match": "75%"
      }
    }
  }
}
```

- `"75%"` of 4 terms = at least 3 must match (Apollo 13 has all four)
- Useful for longer queries where exact match is too strict

---

# multi_match Query

Search across **multiple fields** at once:

```json top=260
GET /movies/_search
{
  "query": {
    "multi_match": {
      "query": "star wars",
      "fields": ["title^3", "overview"]
    }
  }
}
```

- `title^3` — boost title matches by 3x
- Matches in `title` are weighted more heavily than `overview`
- Great for search boxes where users don't specify a field

---

# multi_match: Types

| Type | Behavior |
|------|----------|
| `best_fields` (default) | Score from the single best matching field |
| `most_fields` | Sum scores from all matching fields |
| `cross_fields` | Treat all fields as one combined field |
| `phrase` | Run match_phrase on each field |

---

# multi_match: cross_fields

```json top=858
GET /movies/_search
{
  "query": {
    "multi_match": {
      "query": "godfather corleone",
      "fields": ["title^2", "overview"],
      "type": "cross_fields",
      "operator": "and"
    }
  }
}
```

> `godfather` is only in the title, `corleone` only in the overview: `cross_fields` treats the fields as one
> big field, so `"operator": "and"` still matches. With `best_fields` it would need both terms in one field.

---

# match_phrase Query

Finds documents where terms appear **in the exact order**, adjacent to each other:

```json contains=858
GET /movies/_search
{
  "query": {
    "match_phrase": {
      "overview": "organized crime"
    }
  }
}
```

- `"organized crime"` matches *"...influence in the world of organized crime"* (The Godfather)
- Does NOT match `"...crime was organized..."`

---

# match_phrase: slop

Allow terms to be **N positions apart**:

```json contains=318
GET /movies/_search
{
  "query": {
    "match_phrase": {
      "overview": {
        "query": "prisoner hope",
        "slop": 3
      }
    }
  }
}
```

- Shawshank: *"...a fellow **prisoner** and finding **hope**..."* — the terms are 3 positions apart
- `slop: 0` → terms must be adjacent (default); `slop: 3` → up to 3 positions apart
- Higher slop = more flexible but less precise

---

<!-- _class: divider -->

# Term-level Queries

## Exact matching without analysis

---

# term vs match

| | `match` | `term` |
|--|---------|--------|
| **Analyzes** query? | Yes | No |
| **Use for** | `text` fields | `keyword`, `integer`, `date` fields |
| **Example** | "The Godfather" → searches for `godfath` (english analyzer) | "Drama" → searches for exact `Drama` |

```json
// CORRECT: term on keyword field
GET /movies/_search
{ "query": { "term": { "genres": "Drama" } } }
```

```json expect=empty
// WRONG: term on text field (analyzed text won't match)
GET /movies/_search
{ "query": { "term": { "title": "The Godfather" } } }
```

> **Common mistake:** Using `term` on a `text` field. The indexed tokens are lowercase, but `term` searches for the exact value.

---

# terms Query

Match any of several values (like SQL `IN`):

```json
GET /movies/_search
{
  "query": {
    "terms": {
      "genres": ["Action", "Thriller", "Horror"]
    }
  }
}
```

Returns documents where `genres` contains **at least one** of the listed values.

---

# range Query

Numeric ranges, date ranges, and more:

```json
GET /movies/_search
{
  "query": {
    "range": {
      "vote_average": {
        "gte": 8.0,
        "lt": 9.0
      }
    }
  }
}
```

Operators: `gt`, `gte`, `lt`, `lte`

---

# range: Date Ranges

```json
GET /movies/_search
{
  "query": {
    "range": {
      "release_date": {
        "gte": "2000-01-01",
        "lt": "2010-01-01"
      }
    }
  }
}
```

- Dates support ISO 8601 format and date math: `"now-1d"`, `"2024-01||/M"`
- Range queries are commonly used in `filter` context (no scoring needed)

---

# exists Query

### Check if a field has a value

```json
GET /movies/_search
{
  "query": {
    "exists": {
      "field": "title_aka"
    }
  }
}
```

- Movies that have at least one alternate title (`title_aka`, e.g. *Seven* a.k.a. *Se7en*)
- `null`, `[]` and a missing field don't count as existing; an empty string `""` in a `keyword` field **does**

---

# prefix Query

### Prefix search on keyword fields

```json
GET /movies/_search
{
  "query": {
    "prefix": {
      "title.keyword": {
        "value": "The"
      }
    }
  }
}
```

> For autocomplete, prefer edge n-gram analyzers (Day 3) over prefix queries — they're faster at scale.

---

<!-- _class: divider -->

# Compound Queries

## bool — the Swiss army knife

---

# bool Query Structure

Combine multiple clauses with different logic:

```json test=skip
GET /movies/_search
{
  "query": {
    "bool": {
      "must": [...],          // AND — scored
      "filter": [...],        // AND — not scored (fast, cached)
      "should": [...],        // OR — scored (boosts matching docs)
      "must_not": [...]       // NOT — excludes, not scored
    }
  }
}
```

---

# bool: Clause Summary

| Clause | Logic | Scored? | Cached? |
|--------|-------|---------|---------|
| `must` | AND | Yes | No |
| `filter` | AND | No | Yes |
| `should` | OR | Yes | No |
| `must_not` | NOT | No | Yes |

> `filter` and `must_not` are faster because they skip scoring and can be cached.

---

# bool: Practical Example

"Find highly-rated sci-fi movies about space, excluding horror"

```json top=924
GET /movies/_search
{
  "query": {
    "bool": {
      "must": { "match": { "overview": "space voyage mission" } },
      "filter": [
        { "term": { "genres": "Sci-Fi" } },
        { "range": { "vote_average": { "gte": 7.5 } } }
      ],
      "must_not": { "term": { "genres": "Horror" } }
    }
  }
}
```

---

# bool: How Clauses Work Together

| Clause | Role in the example |
|--------|-----------|
| `must` | Contributes to `_score` (relevance for "space voyage mission") |
| `filter` | Exact criteria, fast, no scoring overhead |
| `must_not` | Hard exclusion (removes Horror) |

> **Rule of thumb:** Put full-text search in `must`, everything else in `filter`.

---

# Nested bool Queries

*"Drama OR Crime movies with rating 8+ that mention 'family' or 'power'"*

```json
GET /movies/_search
{
  "query": {
    "bool": {
      "must": { "match": { "overview": "family power" } },
      "filter": { "range": { "vote_average": { "gte": 8.0 } } },
      "should": [
        { "term": { "genres": "Drama" } },
        { "term": { "genres": "Crime" } }
      ],
      "minimum_should_match": 1
    }
  }
}
```

---

# should as Boost

When `must` or `filter` is present, `should` becomes a **boost** — matching docs rank higher but non-matching docs aren't excluded:

```json
GET /movies/_search
{
  "query": {
    "bool": {
      "must": { "match": { "overview": "war" } },
      "should": [
        { "match": { "title": "war" } },
        { "range": { "vote_average": { "gte": 8.5 } } }
      ]
    }
  }
}
```

Documents matching `should` clauses get a **score boost**.

---

<!-- _class: divider -->

# Pagination, Sorting & Highlighting

## Controlling search output

---

# Pagination: from + size

```json
GET /movies/_search
{
  "query": { "match_all": {} },
  "from": 0,
  "size": 10
}
```

| Page | from | size |
|------|------|------|
| 1 | 0 | 10 |
| 2 | 10 | 10 |
| 3 | 20 | 10 |

> **Limitation:** `from + size` cannot exceed **10,000**. For deep pagination use `search_after` (next slide);
> the Scroll API is no longer recommended for that.

---

# Deep Pagination: search_after

Sort by a unique combination, then pass the last hit's `sort` values to get the next page:

```json
GET /movies/_search
{ "size": 3, "sort": [{ "year": "asc" }, { "id": "asc" }], "_source": ["title", "year"] }
```

```json contains=1348
GET /movies/_search
{
  "size": 3,
  "sort": [{ "year": "asc" }, { "id": "asc" }],
  "search_after": [1921, 3310],
  "_source": ["title", "year"]
}
```

> For a consistent view while paging, open a **point in time** (`POST /movies/_pit?keep_alive=1m`) and pass
> its `id` in `"pit"` instead of the index name.

---

# Sorting

### Sort by field

```json
GET /movies/_search
{
  "query": { "match_all": {} },
  "sort": [
    { "vote_average": "desc" },
    { "release_date": "asc" }
  ]
}
```

### Sort by relevance (default)

```json
"sort": ["_score"]
```

> When you sort by a field other than `_score`, relevance scoring is **disabled** (faster).

---

# _source Filtering

Control which fields are returned:

```json
GET /movies/_search
{
  "query": { "match": { "overview": "adventure" } },
  "_source": ["title", "vote_average", "genres"]
}
```

### Exclude fields

```json
"_source": {
  "excludes": ["overview"]
}
```

> Returning fewer fields = smaller response = faster network transfer.

---

# Highlighting

Show which parts of the text matched:

```json
GET /movies/_search
{
  "query": {
    "match": { "overview": "prisoner hope" }
  },
  "highlight": {
    "fields": {
      "overview": {}
    }
  }
}
```

---

# Highlighting: Response

```json
"highlight": {
  "overview": [
    "...forming an unlikely friendship with a fellow <em>prisoner</em> and finding <em>hope</em> amidst despair."
  ]
}
```

- Matching terms are wrapped in `<em>` tags by default
- Customize tags: `"pre_tags": ["<b>"], "post_tags": ["</b>"]`

---

<!-- _class: exercise -->

# Practice 2A

## Query DSL

`day2-exercises.md` — Part A (7 tasks) | ~25 min

---

<!-- _class: divider -->

# ES|QL

## Elasticsearch Query Language

---

# What is ES|QL?

A **pipe-based query language** for Elasticsearch (preview in 8.11, GA since 8.14):

```sql
FROM movies
| WHERE vote_average >= 8.0
| SORT vote_average DESC
| LIMIT 10
| KEEP title, vote_average, genres
```

**Key differences from Query DSL:**
- SQL-like syntax with **pipe** (`|`) chaining
- Built-in aggregations without nesting
- Returns **columnar** data (not JSON documents)
- Own compute engine; `WHERE` filters and full-text functions are pushed down to Lucene

---

# ES|QL: Core Commands

| Command | Purpose | Example |
|---------|---------|---------|
| `FROM` | Source index | `FROM movies` |
| `WHERE` | Filter rows | `WHERE vote_average > 8` |
| `EVAL` | Compute new columns | `EVAL decade = FLOOR(year / 10) * 10` |
| `STATS...BY` | Aggregate + group | `STATS avg(vote_average) BY genres` |
| `SORT` | Order results | `SORT vote_average DESC` |
| `LIMIT` | Limit rows | `LIMIT 20` |
| `KEEP` | Select columns | `KEEP title, genres` |
| `DROP` | Remove columns | `DROP overview` |
| `RENAME` | Rename columns | `RENAME vote_average AS rating` |

---

# ES|QL: Filtering

```sql
FROM movies
| WHERE vote_average >= 8.0 AND MATCH(genres, "Drama")
| SORT vote_average DESC
| LIMIT 5
| KEEP title, vote_average
```

### Operators

| Operator | Example |
|----------|---------|
| `==`, `!=` | `title == "The Godfather"` |
| `>`, `>=`, `<`, `<=` | `vote_average >= 8.0` |
| `AND`, `OR`, `NOT` | `year >= 1990 AND vote_average > 7` |
| `LIKE` | `title LIKE "The *"` |
| `IN` | `year IN (1994, 1995)` |

---

# ES|QL Pitfall: Multi-valued Fields

`genres` holds several values. Comparisons on a multi-valued field evaluate to **null** (with a warning), so most movies silently disappear:

```sql expect=warning
FROM movies
| WHERE genres == "Drama"
| LIMIT 5
```

Filter with `MATCH(genres, "Drama")` — or the `:` operator, `WHERE genres : "Drama"` — or `MV_EXPAND` first:

```sql
FROM movies
| WHERE MATCH(genres, "Drama")
| KEEP title, genres
| LIMIT 5
```

---

# ES|QL: EVAL (Computed Columns)

Create new columns from expressions:

```sql
FROM movies
| EVAL rating_category = CASE(
    vote_average >= 8.0, "Excellent",
    vote_average >= 6.0, "Good",
    "Average"
  )
| STATS count = COUNT(*) BY rating_category
| SORT count DESC
| LIMIT 10
```

> Without `LIMIT`, ES|QL warns "No limit defined" and caps results at 1,000 rows.

---

# ES|QL: EVAL with Dates

```sql
FROM movies
| EVAL year = DATE_EXTRACT("year", release_date)
| EVAL decade = FLOOR(year / 10) * 10
| STATS count = COUNT(*), avg_rating = AVG(vote_average) BY decade
| SORT decade
| LIMIT 20
```

- `DATE_EXTRACT` takes Java `ChronoField` names: `"year"`, `"month_of_year"`, `"day_of_month"`, `"day_of_week"`
- `FLOOR` rounds down for grouping into decades (our data also has a ready-made `year` field)

---

# ES|QL: STATS...BY (Aggregations)

```sql
FROM movies
| STATS
    count = COUNT(*),
    avg_rating = AVG(vote_average),
    max_rating = MAX(vote_average),
    min_rating = MIN(vote_average)
  BY genres
| SORT count DESC
| LIMIT 10
```

### Available functions (selection)

`COUNT`, `COUNT_DISTINCT`, `AVG`, `SUM`, `MIN`, `MAX`, `MEDIAN`, `MEDIAN_ABSOLUTE_DEVIATION`, `PERCENTILE`,
`TOP`, `VALUES`, `WEIGHTED_AVG` — e.g. `STATS best = TOP(vote_average, 3, "desc"), wavg = WEIGHTED_AVG(vote_average, vote_count)`

---

# ES|QL: Multi-value Fields

Genres is an array — use `MV_EXPAND` to unnest:

```sql
FROM movies
| MV_EXPAND genres
| WHERE genres != "Drama"
| STATS count = COUNT(*), avg_rating = AVG(vote_average) BY genres
| SORT count DESC
| LIMIT 10
```

- `STATS ... BY genres` already counts a movie once per genre — no expansion needed for grouping
- `MV_EXPAND` turns each value into its own row, which you need to `WHERE`, `SORT` or `KEEP` per value

---

# ES|QL in Kibana: Dev Tools

```json
POST /_query
{
  "query": """
    FROM movies
    | WHERE vote_average >= 8.0
    | SORT vote_average DESC
    | LIMIT 10
    | KEEP title, vote_average, genres
  """
}
```

> Wrap ES|QL in triple-quotes inside the JSON body.

---

# ES|QL in Kibana: Discover

1. Open **Discover**
2. Click **Try ES|QL** (or pick ES|QL in the query-language menu)
3. Type your ES|QL query directly

- Discover renders ES|QL results as a **table** (columnar)
- Great for quick data exploration without writing JSON

---

# ES|QL vs Query DSL

| Aspect | Query DSL | ES\|QL |
|--------|-----------|-------|
| **Syntax** | JSON | Pipe-based text |
| **Scoring** | BM25 relevance | BM25 via `METADATA _score` + `MATCH` / `QSTR` |
| **Aggregations** | Nested JSON | `STATS...BY` |
| **Pagination** | `from`/`size`, `search_after` | `LIMIT` |
| **Use case** | Search UIs, relevance tuning | Analytics, exploration — and growing search support |
| **Maturity** | Since 1.0 | GA since 8.14 |

> **Query DSL** remains the tool for tuned search experiences; **ES|QL** shines for exploration and analytics.

---

# ES|QL Full-Text Search and Scoring

```sql
FROM movies METADATA _score
| WHERE MATCH(overview, "prison escape")
| SORT _score DESC
| KEEP title, _score
| LIMIT 5
```

- `METADATA _score` exposes the BM25 relevance score, like Query DSL's `_score`
- `MATCH`, `QSTR` (query string) and the `:` operator run full-text queries inside ES|QL

---

<!-- _class: exercise -->

# Practice 2B

## ES|QL

`day2-exercises.md` — Part B (6 tasks) | ~20 min

---

<!-- _class: divider -->

# Summary

---

# Day 2 Recap

| Topic | Key Queries |
|-------|------------|
| **Full-text** | `match`, `multi_match` (types, boosting), `match_phrase` (slop) |
| **Term-level** | `term`, `terms`, `range`, `exists`, `prefix` |
| **Compound** | `bool`: must / filter / should / must_not |
| **Output** | `from`/`size`, `sort`, `_source`, `highlight` |
| **ES\|QL** | `FROM` \| `WHERE` \| `EVAL` \| `STATS...BY` \| `SORT` \| `LIMIT` |

---

# Day 3 Preview

Tomorrow (3-hour session) we'll cover:

- **Index API** — bulk operations, reindex, aliases, templates
- **Text Analysis** — analyzers, tokenizers, custom analyzers, autocomplete
- **Mappings** — dynamic vs explicit, field types, multi-fields
- **Aggregations** — metric, bucket, nested, pipeline aggs
- **Nested & Join** — nested objects, parent-child relationships

> Keep `elk-single` running!

---

<!-- _class: title -->

# Thank You!

## Questions?

Day 2 — Query DSL & ES|QL
