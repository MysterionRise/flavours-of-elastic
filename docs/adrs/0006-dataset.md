# ADR 0006: One Real, Curated Movie Dataset

Status: accepted
Date: 2026-10

## Decision

The course and the demo use one dataset: `data/movies_enriched.csv`, 5,100 MovieLens ml-32m movies (up to 2002)
with real ratings (`vote_average` = mean × 2, `vote_count`; blank below 10 votes), readable titles
(`title`, `title_aka`, `title_raw`) and LLM-generated multilingual descriptions (en/kk/fr). `--size small` is a
deterministic, curated 200-movie sample (`data/build_sample.py`, `data/sample.yml`).

## Rationale

- The course used fields that did not exist (`vote_average`) and named films that were not in the data; the
  small set covered three years only.
- A curated sample that always contains every film the course names (`course/movies.yml`) and every judged movie
  of the evaluation keeps examples, exercises and metrics stable; quotas cover every decade and genre.
- Real ratings make range queries and aggregations meaningful.

## Consequences

- MovieLens terms apply to the data (non-commercial, attribution; `data/LICENSE-DATA.md`); paid courses need
  GroupLens permission.
- Films after 2002 do not exist: the course uses stand-ins (`course/movies.yml`).
- Changing the sample changes course numbers; `tests/test_sample.py` and the course harness catch it.
