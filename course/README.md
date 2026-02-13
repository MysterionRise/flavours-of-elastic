# Elasticsearch Course Materials

4-day Elasticsearch course built with [Marp](https://marp.app/) for slide generation.

## Course Schedule

| Day | Topic | Duration | Stack |
|-----|-------|----------|-------|
| 1 | Elasticsearch Fundamentals | 2h | `elk-single` |
| 2 | Query DSL & ES\|QL | 2h | `elk-single` |
| 3 | Indexing, Text Analysis & Aggregations | 3h | `elk-single` or `elastic` |
| 4 | Vector Search, Semantic Search & Hybrid Search | 3h | `elk-ml` |

## Building Slides

### Install Marp CLI

```bash
npm install -g @marp-team/marp-cli
```

### Generate PDF

```bash
# Single day
marp course/day1-fundamentals/day1-slides.md \
  --theme course/theme/epam.css \
  --allow-local-files \
  -o course/day1-fundamentals/day1-slides.pdf

# All days
for day in day1-fundamentals day2-query-dsl day3-indexing-analysis day4-semantic-search; do
  marp "course/${day}/${day%%-*}-slides.md" \
    --theme course/theme/epam.css \
    --allow-local-files \
    -o "course/${day}/${day%%-*}-slides.pdf"
done
```

### Generate PPTX

```bash
marp course/day1-fundamentals/day1-slides.md \
  --theme course/theme/epam.css \
  --allow-local-files \
  --pptx \
  -o course/day1-fundamentals/day1-slides.pptx
```

### Live Preview (for editing)

```bash
marp --server --theme course/theme/epam.css course/day1-fundamentals/day1-slides.md
```

## File Structure

```
course/
  README.md                           # This file
  theme/
    epam.css                          # Custom Marp theme
  day1-fundamentals/
    day1-slides.md                    # Slides (~50)
    day1-exercises.md                 # 6 exercises
  day2-query-dsl/
    day2-slides.md                    # Slides (~55)
    day2-exercises.md                 # Part A: Query DSL (7), Part B: ES|QL (6)
  day3-indexing-analysis/
    day3-slides.md                    # Slides (~65)
    day3-exercises.md                 # Part A-D: Indexing, Analyzers, Aggs, Nested/Join
  day4-semantic-search/
    day4-slides.md                    # Slides (~55)
    day4-exercises.md                 # Part A-D: Vector, ELSER, RRF, Advanced
```

## Prerequisites for Students

- Docker 20.10+ and Docker Compose 1.29+
- 4GB RAM minimum (8GB+ for Day 4)
- Clone this repository: `git clone <repo-url>`
- Verify: `docker compose version`

## Instructor Notes

- Content is ~2.5h buffer over session time for flexibility
- Exercises are tiered: Basic / Intermediate / Bonus
- Each exercise has hints (expandable) but no full solutions
- Day 4 requires `elk-ml` stack started ~15 min before class (ELSER download)
- Kibana sample datasets (ecommerce, flights) used in Day 2-3 exercises
