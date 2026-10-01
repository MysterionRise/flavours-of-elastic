---
marp: true
theme: epam
paginate: true
---

<!-- _class: title -->

# Day 2 Exercises: Query DSL & ES|QL

**Stack:** `elk-single` (8.19) or `elk-9` (9.5) | **Duration:** ~45 minutes total | **Kibana Dev Tools:** `http://localhost:5601`

## Prerequisites

- Movies dataset loaded (`python data/load_data.py --dataset movies --size small` — 200 curated movies)
- Kibana sample data loaded (eCommerce orders)

---

<!-- _class: divider -->

# Part A: Query DSL (7 tasks, ~25 min)

---

## Task 1: match Query (Basic)

Find all movies with `"adventure"` in the `overview` field.

Then modify the query to require BOTH `"adventure"` AND `"journey"` in the overview. How many movies are left?

> **Hint:** The `match` query combines its terms with OR by default — look for the parameter that changes that.

---

## Task 2: multi_match with Boosting (Basic)

Search for `"star wars"` across both `title` and `overview` fields. Boost the `title` field by 3x so title matches rank higher.

How many results do you get? What is the top result? Why do films without "star" in the title show up?

> **Hint:** `multi_match` accepts per-field boosts with the `field^N` syntax.

---

## Task 3: match_phrase with Slop (Intermediate)

Find movies whose overview contains the exact phrase `"organized crime"`.

Then try the phrase `"crime family"` with `slop: 3`. Does "The Godfather" appear? Why or why not?

> **Hint:** `GET movies/_doc/858` shows The Godfather's overview. Slop is the number of position moves allowed.

---


## Task 4: bool Query -- Filters and Scoring (Intermediate)

Write a `bool` query that finds movies matching ALL of these criteria:

1. The `overview` must contain `"love"` (scored -- contributes to relevance)
2. The `genres` must be `"Romance"` OR `"Drama"` (at least one)
3. The `vote_average` must be >= 7.0 (use filter -- not scored)
4. Must NOT be in the `"Horror"` genre

> **Hint:** Each criterion maps to one `bool` clause; "at least one of" is a `should` with `minimum_should_match`.

---

## Task 5: Date Range + Bool Combo (Intermediate)

Find movies released in the **1990s** (1990-01-01 to 1999-12-31) that are in the `"Action"` genre and scored above 7.5.

Sort the results by `release_date` in ascending order and return only `title`, `release_date`, and `vote_average`.

> **Hint:** None of the criteria needs relevance scoring — which `bool` clause skips scoring? Sorting and field
> selection are top-level `sort` and `_source`.

---

## Task 6: Highlighting (Intermediate)

Search for `"prison escape freedom"` in the `overview` field. Enable highlighting on the `overview` field with custom tags `<mark>` and `</mark>`.

Examine the highlighted fragments -- which terms actually matched?

> **Hint:** `highlight` takes `pre_tags` / `post_tags`. The `english` analyzer stems *inflections*
> (escape / escaped / escaping) but not *derivations*: `prison` ≠ `imprisoned`, `freedom` ≠ `free` — try
> `GET movies/_analyze { "field": "overview", "text": "imprisoned freedom" }`. Synonyms (Day 3) and semantic
> search (Day 4) close that gap.

---


## Task 7: Complex Search Scenario (Bonus) -- Part 1

Build a search for a movie recommendation engine. The user types: `"future reality"`.

Your query should:

1. Search `title` (boosted 3x) and `overview` using `multi_match` with `type: "best_fields"`
2. Boost results in the `"Sci-Fi"` genre (should, not required)
3. Filter to movies rated >= 7.0
4. Filter to movies released after 1990-01-01

---


## Task 7: Complex Search Scenario (Bonus) -- Part 2

Your query should also:

5. Exclude `"Animation"` genre
6. Return 5 results with highlighting on `overview`
7. Return only `title`, `genres`, `vote_average`, `release_date`

> **Hint:** Full-text goes where it is scored, hard criteria where they are not, and the genre preference
> where it only boosts. `highlight`, `size` and `_source` live at the top level of the request.

---

<!-- _class: divider -->

# Part B: ES|QL (6 tasks, ~20 min)

---

## Part B: Getting Started

All ES|QL queries can be run in Kibana Discover (ES|QL mode) or via Dev Tools:

```json test=skip
POST /_query
{
  "query": """
    YOUR ESQL QUERY HERE
  """
}
```

---


## Task 8: Basic Filtering (Basic)

Write an ES|QL query to find all movies with `vote_average >= 8.5`, sorted by rating descending. Show only `title`, `vote_average`, and `genres`. Limit to 10 results.

> **Hint:**
> ```sql test=skip
> FROM movies
> | WHERE ...
> | SORT ...
> | LIMIT ...
> | KEEP ...
> ```

---


## Task 9: EVAL -- Computed Columns (Basic)

Write a query that:
1. Extracts the **year** from `release_date`
2. Creates a `rating_tier` column: "Masterpiece" (>= 8.5), "Great" (>= 7.5), "Good" (>= 6.0), "Okay" (< 6.0)
3. Shows `title`, `year`, `vote_average`, `rating_tier`
4. Sorts by `vote_average` DESC, limit 15

> **Hint:** `DATE_EXTRACT` takes a `ChronoField` name such as `"year"`; `CASE(condition, value, ..., default)`
> evaluates its conditions in order.

---


## Task 10: STATS...BY -- Genre Analysis (Intermediate)

Analyze movies by genre:
1. Expand the `genres` multi-value field
2. Group by genre
3. Calculate: count, average rating, max rating
4. Sort by count descending

Which genre has the most movies? Which has the highest average rating?

> **Hint:** `STATS ... BY genres` already groups a movie under each of its genres. Try it with and without
> `MV_EXPAND genres` first — do the counts change?

---


## Task 11: Decade Analysis (Intermediate)

Create a decade-based analysis:
1. Extract the year from `release_date`
2. Calculate the decade (1910, 1920, ... 2000 — the dataset ends in 2002)
3. Group by decade
4. Show count, average rating, and min/max rating per decade
5. Sort by decade

Which decade produced the highest-rated movies on average?

---

## Task 11: Decade Analysis (continued)

> **Hint:** Integer division doesn't round dates — extract the year first (or use the `year` field), then
> `FLOOR(year / 10) * 10`.

---


## Task 12: eCommerce Data Exploration (Intermediate)

Switch to the `kibana_sample_data_ecommerce` index.

Write an ES|QL query that answers: **What is the average order value by day of the week?**

1. Extract the day of week from `order_date`
2. Group by day name
3. Calculate average and total `taxful_total_price`
4. Sort by average descending

> **Hint:** `DATE_EXTRACT("day_of_week", order_date)` returns 1 (Monday) to 7 (Sunday). The price field is
> `taxful_total_price`.

---

## Task 13: ES|QL vs Query DSL Comparison (Bonus)

Write the **same query** in both ES|QL and Query DSL:

"Find the top 5 Drama movies released after 2000 with the highest vote_average"

Compare:
- Which is more readable?
- Which gives you relevance scoring?
- Which would you use for a search box? For a dashboard?

> **Hint:** Watch the multi-valued `genres` field in ES|QL (see the "Pitfall" slide). Compare the shape of the
> two responses: columns and rows vs hits with `_score`.

---

## Cleanup

No cleanup needed -- keep the data for Day 3!
