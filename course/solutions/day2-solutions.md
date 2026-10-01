---
marp: true
theme: epam
paginate: true
---

<!-- _class: title -->

# Day 2 Solutions

## Instructor answer key — checked in CI on Elasticsearch 8.19 and 9.5

---

## Task 1 — match Query

```json min=5
GET /movies/_search
{ "query": { "match": { "overview": "adventure" } } }
```

```json contains=1198
GET /movies/_search
{ "query": { "match": { "overview": { "query": "adventure journey", "operator": "and" } } } }
```

`operator: and` leaves two films (Raiders of the Lost Ark, Joe Dirt) instead of every film mentioning either word.

---

## Task 2 — multi_match with Boosting

```json top=260
GET /movies/_search
{
  "query": { "multi_match": { "query": "star wars", "fields": ["title^3", "overview"] } }
}
```

The top hit is *Star Wars: Episode IV - A New Hope*. Films like *The War of the Worlds* also match: `match`
uses OR, so `war` in a title or overview is enough (the english analyzer stems `wars` to `war`).

---

## Task 3 — match_phrase with Slop

```json contains=858
GET /movies/_search
{ "query": { "match_phrase": { "overview": "organized crime" } } }
```

```json contains=858
GET /movies/_search
{ "query": { "match_phrase": { "overview": { "query": "crime family", "slop": 3 } } } }
```

Yes — The Godfather's overview reads *"the Corleone crime family"*: the phrase even matches with `slop: 0`.

---

## Task 4 — bool Query: Filters and Scoring

```json min=3
GET /movies/_search
{
  "query": {
    "bool": {
      "must": { "match": { "overview": "love" } },
      "should": [
        { "term": { "genres": "Romance" } },
        { "term": { "genres": "Drama" } }
      ],
      "minimum_should_match": 1,
      "filter": { "range": { "vote_average": { "gte": 7.0 } } },
      "must_not": { "term": { "genres": "Horror" } }
    }
  }
}
```

---

## Task 5 — Date Range + bool

```json contains=6,2571
GET /movies/_search
{
  "query": {
    "bool": {
      "filter": [
        { "range": { "release_date": { "gte": "1990-01-01", "lt": "2000-01-01" } } },
        { "term": { "genres": "Action" } },
        { "range": { "vote_average": { "gt": 7.5 } } }
      ]
    }
  },
  "sort": [{ "release_date": "asc" }],
  "_source": ["title", "release_date", "vote_average"]
}
```

*Heat* (1995) and *The Matrix* (1999).

---

## Task 6 — Highlighting

```json min=3
GET /movies/_search
{
  "query": { "match": { "overview": "prison escape freedom" } },
  "highlight": {
    "pre_tags": ["<mark>"],
    "post_tags": ["</mark>"],
    "fields": { "overview": {} }
  }
}
```

```json
GET movies/_analyze
{ "field": "overview", "text": "prison escape freedom imprisoned escaped" }
// → {"tokens": [{"token": "prison"}, {"token": "escap"}, {"token": "freedom"}, {"token": "imprison"}, {"token": "escap"}]}
```

Inflections share a stem (`escape`, `escaped` → `escap`), derivations do not (`prison` ≠ `imprison`).

---

## Task 7 — Complex Search Scenario

```json contains=32,2571
GET /movies/_search
{
  "size": 5,
  "query": {
    "bool": {
      "must": {
        "multi_match": { "query": "future reality", "fields": ["title^3", "overview"], "type": "best_fields" }
      },
      "should": [{ "term": { "genres": "Sci-Fi" } }],
      "filter": [
        { "range": { "vote_average": { "gte": 7.0 } } },
        { "range": { "release_date": { "gte": "1990-01-01" } } }
      ],
      "must_not": [{ "term": { "genres": "Animation" } }]
    }
  },
  "highlight": { "fields": { "overview": {} } },
  "_source": ["title", "genres", "vote_average", "release_date"]
}
```

*Twelve Monkeys*, *Dark City* and *The Matrix* — all Sci-Fi, so the `should` boost reorders but does not filter.

---

## Task 8 — ES|QL Basic Filtering

```sql min=5
FROM movies
| WHERE vote_average >= 8.5
| SORT vote_average DESC, title ASC
| LIMIT 10
| KEEP title, vote_average, genres
```

---

## Task 9 — EVAL: Computed Columns

```sql
FROM movies
| EVAL year = DATE_EXTRACT("year", release_date)
| EVAL rating_tier = CASE(
    vote_average >= 8.5, "Masterpiece",
    vote_average >= 7.5, "Great",
    vote_average >= 6.0, "Good",
    "Okay")
| KEEP title, year, vote_average, rating_tier
| SORT vote_average DESC, title ASC
| LIMIT 15
```

---

## Task 10 — STATS...BY: Genre Analysis

```sql
FROM movies
| STATS count = COUNT(*), avg_rating = AVG(vote_average), max_rating = MAX(vote_average) BY genres
| SORT count DESC
| LIMIT 20
```

Drama has the most movies. Adding `MV_EXPAND genres` first gives the **same** counts: grouping by a
multi-valued field already puts a movie into every one of its genres. Sort by `avg_rating DESC` for the
best-rated genre (it changes as the sample changes — small genres such as Film-Noir tend to win).

---

## Task 11 — Decade Analysis

```sql
FROM movies
| EVAL decade = FLOOR(year / 10) * 10
| STATS count = COUNT(*), avg_rating = AVG(vote_average),
        min_rating = MIN(vote_average), max_rating = MAX(vote_average) BY decade
| SORT decade
| LIMIT 20
```

`DATE_EXTRACT("year", release_date)` gives the same `year`. Older decades usually average higher: the
films from the 1920s-1950s that people still rate on MovieLens are the classics.

---

## Task 12 — eCommerce Data Exploration

```sql min=7
FROM kibana_sample_data_ecommerce
| EVAL day_of_week = DATE_EXTRACT("day_of_week", order_date)
| STATS avg_order = AVG(taxful_total_price), total = SUM(taxful_total_price) BY day_of_week
| SORT avg_order DESC
| LIMIT 7
```

`day_of_week` runs from 1 (Monday) to 7 (Sunday); wrap it in `CASE(...)` to show day names.

---

## Task 13 — ES|QL vs Query DSL

```sql min=5
FROM movies
| WHERE MATCH(genres, "Drama") AND year >= 2000
| SORT vote_average DESC, title ASC
| LIMIT 5
| KEEP title, year, vote_average
```

```json min=5
GET /movies/_search
{
  "size": 5,
  "query": {
    "bool": {
      "filter": [
        { "term": { "genres": "Drama" } },
        { "range": { "year": { "gte": 2000 } } }
      ]
    }
  },
  "sort": [{ "vote_average": "desc" }, { "title.keyword": "asc" }],
  "_source": ["title", "year", "vote_average"]
}
```

ES|QL reads more like the question; neither version scores here (filters only). For a search box use Query
DSL (or ES|QL with `METADATA _score` + `MATCH`); for a dashboard ES|QL's `STATS` is the natural fit.
