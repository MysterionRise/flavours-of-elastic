# Elasticsearch Course Materials

4-day Elasticsearch course built with [Marp](https://marp.app/) for slide generation.

## Course Schedule

| Day | Topic | Duration | Stack |
|-----|-------|----------|-------|
| 1 | Elasticsearch Fundamentals | 2h | `elk-single` / `elk-9` |
| 2 | Query DSL & ES\|QL | 2h | `elk-single` / `elk-9` |
| 3 | Indexing, Text Analysis & Aggregations | 3h | `elk-single` / `elk-9` |
| 4 | Vector Search, Semantic Search & Hybrid Search | 3h | `elk-ml` / `elk-ml-9` |

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

## Testing the Course

Every Dev Tools snippet in the slides and exercises is executable and checked in CI on both tracks
(Days 1-3: `elk-single` 8.19 and `elk-9` 9.5; Day 4: `elk-ml` / `elk-ml-9` once its rewrite lands):

```bash
make course-test DAY=2 STACK=elk-9                        # fresh isolated stack, torn down afterwards
python -m tests.course.run --day 2 --stack elk-single     # against the stack you already run
python -m tests.course.run --day 2 --list                 # what runs, no stack needed
```

By default each request must return 2xx, searches / counts / ES|QL must return results, aggregations must
have buckets, `_bulk` must report no item errors, and responses must carry no deprecation or ES|QL warnings.
Annotate a fence after the language word (Marp and GitHub ignore the rest of the info string):

| Annotation | Meaning |
|---|---|
| `test=skip` / `test=manual` | illustrative snippet or UI step; not executed |
| `expect=empty` | succeeds with zero hits/rows (e.g. a "wrong way" example) |
| `expect=404`, `expect=4xx`, `expect=any`, `expect=warning` | intended error / any 2xx / warning allowed |
| `min=N`, `top=ID`, `contains=ID,ID` | at least N hits / first hit / these hits present |
| `track=8`, `track=9` | runs only on that major version (dual-track differences) |
| `requires=trial`, `requires=ml` | skipped on stacks without that capability |
| `// → {...}` after a request | the response must contain this JSON |

Every snippet passes on both tracks. While a change is in progress (e.g. a version bump whose behaviour the
decks don't cover yet), `python -m tests.course.run --update-baseline` records the failures in
`tests/course/baseline.yml`, a per-track ratchet: listed failures are expected, new ones fail the run, and a fixed
snippet still listed there fails the run too. The file does not exist while the course is clean.

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
- 4GB RAM minimum (~10GB Docker memory for Day 4)
- Clone this repository: `git clone https://github.com/MysterionRise/flavours-of-elastic.git`
- Create your env file: `cp .env.example .env`
- Verify: `docker compose version`

## Instructor Notes

- Content is ~2.5h buffer over session time for flexibility
- Exercises are tiered: Basic / Intermediate / Bonus
- Exercise slides carry hints; full answers are in `course/solutions/dayN-solutions.md` (instructor key, run in
  CI on both tracks, so its numbers match the data)
- Day 4 needs `elk-ml` / `elk-ml-9` and `movies-embeddings` loaded before class: the first
  `python data/load_data.py --dataset movies --size small --embeddings e5 --with-elser` downloads and deploys E5 and
  ELSER (~0.9 GB, ~5 minutes); `--warm-only` just deploys the models
- The ML stacks run a 30-day trial licence (needed for E5, ELSER and the `rrf` retriever); `make reset-elk-ml`
  starts a fresh trial and deletes the data
- The Kibana eCommerce sample dataset is used in the Day 1-3 exercises
