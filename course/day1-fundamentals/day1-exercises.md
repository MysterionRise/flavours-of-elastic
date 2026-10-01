---
marp: true
theme: epam
paginate: true
---

<!-- _class: title -->

# Day 1 Exercises: Cluster Exploration & CRUD Operations

**Stack:** `elk-single` (8.19) or `elk-9` (9.5) | **Duration:** ~30 minutes total | **Kibana Dev Tools:** `http://localhost:5601`

---

## Setup

```bash test=manual
# One-time: Python dependencies and your env file
pip install -r requirements.txt
cp .env.example .env

# Start Elasticsearch + Kibana and wait until both are healthy
docker compose -f docker/elk-single/docker-compose.yml --env-file .env up -d --wait
```

Then open Kibana at **http://localhost:5601** (login: `elastic` / `elastic`).

---

## Part A: Cluster Exploration & Setup

---


## Task 1: Cluster Inspection (Basic)

**Goal:** Get familiar with `_cat` APIs and understand your cluster state.

Run the following commands in Kibana Dev Tools and answer the questions:

```json
GET _cluster/health

GET _cat/nodes?v

GET _cat/indices?v
```

**Questions:**
1. What is the cluster health status? (Check it again after Task 2 — does it change, and why?)
2. How many nodes are in the cluster?
3. What system indices (starting with `.`) already exist?

---

## Task 1: Cluster Inspection (continued)

> **Hint:** Health is about shard copies. Which shards could be unassigned on a single node — and does the
> `movies` index (1 replica by default) change the answer? `GET _cat/shards?v` shows every shard and its state.

---


## Task 2: Load Sample Data (Basic)

**Goal:** Load the movies dataset and Kibana sample data.

### 2a. Load movies dataset

```bash
python data/load_data.py --dataset movies --size small
```

Verify in Dev Tools:
```json
GET movies/_count

GET movies/_search
{
  "size": 3
}
```

---


## Task 2: Load Sample Data (continued)

### 2b. Load Kibana sample data

1. Open Kibana → Home → **Try sample data**
2. Load **Sample eCommerce orders** (used again on Days 2 and 3)

Verify:
```json
GET _cat/indices?v&s=index
```

**Questions:**
1. How many documents are in the `movies` index?
2. What is the index name of the Kibana sample dataset?
3. How many shards does each index have?

---

## Task 2: Load Sample Data (hint)

> **Hint:** Kibana sample indices start with `kibana_sample_data_`. `GET _cat/shards/<index>?v` shows the
> shard details of one index.

---

## Part B: CRUD, Mappings & Shards

---


## Task 3: CRUD Operations (Basic)

**Goal:** Practice creating, reading, updating, and deleting documents.

### 3a. Create a new movie with explicit ID

Create a document in a new scratch index `my-movies` with `_id` = `demo-1` (so the `movies` dataset stays intact):

| Field | Value |
|-------|-------|
| title | "My Favorite Movie" |
| overview | "An amazing story about..." |
| genres | ["Drama", "Adventure"] |
| vote_average | 9.5 |
| release_date | "2024-01-15" |

### 3b. Read it back

Retrieve the document you just created.

---


## Task 3: CRUD Operations (continued)

### 3c. Update the vote_average to 9.0

Use a partial update (not a full replace).

### 3d. Delete the document

Remove the document and verify it's gone.

> **Hint:** Creating with your own id uses `PUT /<index>/_doc/<id>`. A partial update goes to the `_update`
> endpoint with the changed fields inside `"doc"`. After a delete, a `GET` of the same id returns `404`.

---


## Task 4: Understanding Mappings (Intermediate)

**Goal:** Compare the explicit mapping the loader created for `movies` with a dynamic one.

```json
GET movies/_mapping
```

**Questions:**
1. What **type** is the `title` field? What analyzer does it use?
2. What **type** is the `genres` field? Why keyword instead of text?
3. What **type** is the `vote_average` field?
4. Index a document with a new field `"director": "Nolan"` into `my-movies`, then compare
   `GET my-movies/_mapping` with `GET movies/_mapping`. How did Elasticsearch map the new field?

---

## Task 4: Understanding Mappings (continued)

> **Hint:** `text` fields are analyzed for full-text search; `keyword` fields are stored as-is for exact
> matches, sorting and aggregations. Look for `fields` inside a mapping — what does dynamic mapping do with
> a new string value?

---


## Task 5: Shard Allocation (Intermediate)

**Goal:** Understand how shards are distributed and what affects cluster health.

```json
GET _cat/shards/movies?v

GET _cluster/allocation/explain
{
  "index": "movies",
  "shard": 0,
  "primary": false
}
```

**Questions:**
1. Are there any UNASSIGNED shards? Why?
2. What does the allocation explain API tell you about why a replica can't be assigned?
3. If you added a second node, what would happen to cluster health?

---

## Task 5: Shard Allocation (continued)

> **Hint:** In a single-node cluster, replica shards remain UNASSIGNED because Elasticsearch never places a replica on the same node as its primary (otherwise a node failure would lose both copies). Adding a second node would allow replicas to be assigned, turning the cluster **green**.

---


## Task 6: Search Preview (Bonus)

**Goal:** Try a few search queries to get a taste of what's coming on Day 2.

### 6a. Find movies with "war" in the title

```json
GET /movies/_search
{
  "query": {
    "match": {
      "title": "war"
    }
  }
}
```

---


## Task 6: Search Preview (continued)

### 6b. Find highly-rated dramas

```json
GET /movies/_search
{
  "query": {
    "bool": {
      "must": {
        "term": { "genres": "Drama" }
      },
      "filter": {
        "range": { "vote_average": { "gte": 8.5 } }
      }
    }
  }
}
```

---

### 6c. Experiment

Try modifying these queries:
- Search for your favorite genre
- Change the vote_average threshold
- Search in the `overview` field instead of `title`

---

## Task 6: Search Preview (questions)

**Questions:**
1. Which query (6a or 6b) produces results with higher `_score` values?
2. Why does the `filter` clause in 6b not contribute to the `_score`?

> **Hint:** `filter` context does not calculate relevance scores -- it only includes/excludes documents (yes/no). This makes filters faster and cacheable. The `must` clause calculates BM25 scores, which is why it contributes to `_score`. We'll cover this in detail on Day 2.

---

## Cleanup (Optional)

Only clean up if you're done for the day:

```bash test=manual
# Stop the stack but keep your data (start it again tomorrow with `up -d --wait`)
docker compose -f docker/elk-single/docker-compose.yml --env-file .env down
```

> Keep the stack running if you're continuing to Day 2! `down -v` would also delete all data.
