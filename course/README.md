# Elasticsearch Course Materials

4-day Elasticsearch course built with [Marp](https://marp.app/) for slide generation.

## Course Schedule

| Day | Topic | Duration | Stack |
|-----|-------|----------|-------|
| 1 | Elasticsearch Fundamentals | 2h | `elk-single` |
| 2 | Query DSL & ES\|QL | 2h | `elk-single` |
| 3 | Indexing, Text Analysis & Aggregations | 3h | `elk-single` or `elastic` |
| 4 | Vector Search, Semantic Search & Hybrid Search | 3h | `elk-ml` |

## Downloading the PDFs

Rendered slides and exercises are attached to every
[course release](https://github.com/MysterionRise/flavours-of-elastic/releases/latest) (they are no longer committed):

| Day | Slides | Exercises |
|-----|--------|-----------|
| 1 | [day1-slides.pdf](https://github.com/MysterionRise/flavours-of-elastic/releases/latest/download/day1-slides.pdf) | [day1-exercises.pdf](https://github.com/MysterionRise/flavours-of-elastic/releases/latest/download/day1-exercises.pdf) |
| 2 | [day2-slides.pdf](https://github.com/MysterionRise/flavours-of-elastic/releases/latest/download/day2-slides.pdf) | [day2-exercises.pdf](https://github.com/MysterionRise/flavours-of-elastic/releases/latest/download/day2-exercises.pdf) |
| 3 | [day3-slides.pdf](https://github.com/MysterionRise/flavours-of-elastic/releases/latest/download/day3-slides.pdf) | [day3-exercises.pdf](https://github.com/MysterionRise/flavours-of-elastic/releases/latest/download/day3-exercises.pdf) |
| 4 | [day4-slides.pdf](https://github.com/MysterionRise/flavours-of-elastic/releases/latest/download/day4-slides.pdf) | [day4-exercises.pdf](https://github.com/MysterionRise/flavours-of-elastic/releases/latest/download/day4-exercises.pdf) |

Every pull request that touches `course/` also renders them as a downloadable workflow artifact (`course-slides`).

## Building Slides

The decks are [Marp](https://marp.app/) Markdown. Rendering uses the pinned Marp CLI Docker image, so no
Node.js install is needed:

```bash
make slides          # all 8 decks -> dist/slides/*.pdf
make slides-serve    # live preview with reload on http://localhost:8080
make slides-clean
```

Without make: `docker run --rm --init -v "$PWD":/home/marp/app marpteam/marp-cli:v4.5.1 --config-file .marprc.yml
--pdf course/day1-fundamentals/day1-slides.md -o dist/slides/day1-slides.pdf`. With a local Node.js LTS,
`npx @marp-team/marp-cli@4.5.1 --config-file .marprc.yml ...` works too. `.marprc.yml` registers the theme
(`course/theme/epam.css`), so no `--theme` flag is needed.

Publishing: push a tag `course-vX.Y.Z`; the "Course slides" workflow attaches the PDFs to that release.

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

- Docker 20.10+ with the Compose v2 plugin (`docker compose`)
- 4GB RAM minimum (8GB+ for Day 4)
- Clone this repository: `git clone https://github.com/MysterionRise/flavours-of-elastic.git`
- Create your env file: `cp .env.example .env`
- Verify: `docker compose version`

## Instructor Notes

- Content is ~2.5h buffer over session time for flexibility
- Exercises are tiered: Basic / Intermediate / Bonus
- Each exercise has hints (expandable) but no full solutions
- Day 4 requires `elk-ml` stack started ~15 min before class (ELSER download)
- Kibana sample datasets (ecommerce, flights) used in Day 2-3 exercises
