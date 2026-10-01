#!/usr/bin/env python3
"""Build the curated `--size small` movie sample (data/movies_small_ids.txt).

    python data/build_sample.py build    # write data/movies_small_ids.txt
    python data/build_sample.py check    # fail if the committed list is stale or breaks a rule
    python data/build_sample.py report   # counts the course can quote (decades, genres, ratings)

Selection (deterministic - ordered by sha256(seed:movieId), never `random`):
1. every film named by the course (course/movies.yml) and every film the
   evaluation queries judge (evaluation/movie_queries.yml);
2. per-genre floors, then per-decade floors;
3. the invariants from data/sample.yml (e.g. enough films rated >= 8.5);
4. filled up to `size`, spread over decades in proportion to sqrt(films per decade)
   so the 1990s (half the data) do not crowd out older decades.
Fill films need `min_votes` MovieLens votes and a vote_average.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = REPO_ROOT / "data" / "movies_enriched.csv"
CONFIG_PATH = REPO_ROOT / "data" / "sample.yml"
OUTPUT_PATH = REPO_ROOT / "data" / "movies_small_ids.txt"
YEAR = re.compile(r"\((\d{4})\)\s*$")


class Movie:
    def __init__(self, row: dict[str, str]):
        self.id = int(row["movieId"])
        self.title = row["title"]
        match = YEAR.search(row["title"])
        self.year = int(match.group(1)) if match else 0
        self.decade = self.year // 10 * 10
        self.genres = [
            g for g in row["genres"].split("|") if g and g != "(no genres listed)"
        ]
        self.votes = int(row.get("vote_count") or 0)
        self.rating = float(row["vote_average"]) if row.get("vote_average") else None


def load_movies(path: Path = CSV_PATH) -> dict[int, Movie]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {movie.id: movie for movie in map(Movie, csv.DictReader(handle))}


def must_include(config: dict) -> set[int]:
    ids: set[int] = set()
    for source in config["must_include_from"]:
        data = yaml.safe_load((REPO_ROOT / source).read_text(encoding="utf-8"))
        if "movies" in data:
            ids |= {int(movie["id"]) for movie in data["movies"]}
        for query in data.get("queries", []):
            ids |= {int(i) for i in query.get("relevant_ids", [])}
    return ids


def matches(movie: Movie, rule: dict) -> bool:
    if "genre" in rule and rule["genre"] not in movie.genres:
        return False
    if "year_gte" in rule and movie.year < rule["year_gte"]:
        return False
    if "vote_average_gte" in rule and (
        movie.rating is None or movie.rating < rule["vote_average_gte"]
    ):
        return False
    if "vote_average_lt" in rule and (
        movie.rating is None or movie.rating >= rule["vote_average_lt"]
    ):
        return False
    return True


def selectable(movies: dict[int, Movie], config: dict, must: set[int]) -> list[Movie]:
    """Films the sample may contain: the must-include list plus well-rated fill candidates."""
    exclude = set(config.get("exclude") or [])
    return [
        m
        for m in movies.values()
        if m.id in must
        or (
            m.id not in exclude
            and m.votes >= config["min_votes"]
            and m.rating is not None
        )
    ]


def select(movies: dict[int, Movie], config: dict, must: set[int]) -> list[int]:
    missing = sorted(must - movies.keys())
    if missing:
        raise SystemExit(f"must-include ids not in the dataset: {missing}")
    seed, size = config["seed"], config["size"]
    order = lambda movie: hashlib.sha256(f"{seed}:{movie.id}".encode()).hexdigest()  # noqa: E731
    exclude = set(config.get("exclude") or [])
    eligible = sorted(
        (
            m
            for m in movies.values()
            if m.id not in must
            and m.id not in exclude
            and m.votes >= config["min_votes"]
            and m.rating is not None
        ),
        key=order,
    )
    selected = set(must)

    def add_until(predicate, count: int) -> None:
        have = sum(predicate(movies[i]) for i in selected)
        for movie in eligible:
            if have >= count:
                return
            if movie.id not in selected and predicate(movie):
                selected.add(movie.id)
                have += 1

    for genre in sorted({g for m in movies.values() for g in m.genres}):
        add_until(lambda m, g=genre: g in m.genres, config["min_per_genre"])
    decades = sorted({m.decade for m in movies.values()})
    for decade in decades:
        add_until(lambda m, d=decade: m.decade == d, config["min_per_decade"])
    for rule in config.get("invariants", []):
        add_until(lambda m, r=rule: matches(m, r), rule["min"])
    if len(selected) > size:
        raise SystemExit(
            f"must-include films and floors need {len(selected)} slots, more than size={size}"
        )

    # Spread the remaining slots over decades in proportion to sqrt(films per decade).
    weight = {
        d: math.sqrt(sum(m.decade == d for m in movies.values())) for d in decades
    }
    share = {d: size * weight[d] / sum(weight.values()) for d in decades}
    target = {d: math.floor(share[d]) for d in decades}
    for d in sorted(decades, key=lambda d: share[d] - target[d], reverse=True)[
        : size - sum(target.values())
    ]:
        target[d] += 1
    for decade in decades:
        add_until(lambda m, d=decade: m.decade == d, target[decade])
    for movie in eligible:  # top up if a decade ran out of eligible films
        if len(selected) >= size:
            break
        selected.add(movie.id)
    return sorted(selected)


def violations(
    ids: list[int], movies: dict[int, Movie], config: dict, must: set[int]
) -> list[str]:
    chosen = [movies[i] for i in ids if i in movies]
    pool = selectable(movies, config, must)
    problems = []
    if len(set(ids)) != config["size"]:
        problems.append(f"{len(set(ids))} unique ids, expected {config['size']}")
    if not must <= set(ids):
        problems.append(f"missing must-include ids: {sorted(must - set(ids))}")
    for genre in sorted({g for m in movies.values() for g in m.genres}):
        available = sum(genre in m.genres for m in pool)
        if sum(genre in m.genres for m in chosen) < min(
            config["min_per_genre"], available
        ):
            problems.append(f"genre {genre} below its floor")
    for decade in sorted({m.decade for m in movies.values()}):
        available = sum(m.decade == decade for m in pool)
        if sum(m.decade == decade for m in chosen) < min(
            config["min_per_decade"], available
        ):
            problems.append(f"decade {decade}s below its floor")
    for rule in config.get("invariants", []):
        if sum(matches(m, rule) for m in chosen) < rule["min"]:
            problems.append(f"invariant not met: {rule}")
    return problems


def render(ids: list[int], config: dict) -> str:
    header = (
        "# Curated `--size small` sample - generated by data/build_sample.py from data/sample.yml; do not edit.\n"
        f"# seed={config['seed']} size={config['size']} must_include_from={','.join(config['must_include_from'])}\n"
    )
    return header + "".join(f"{i}\n" for i in ids)


def report(ids: list[int], movies: dict[int, Movie]) -> None:
    chosen = [movies[i] for i in ids]
    print(
        f"{len(chosen)} movies, {min(m.year for m in chosen)}-{max(m.year for m in chosen)}"
    )
    print("decades:", dict(sorted(Counter(f"{m.decade}s" for m in chosen).items())))
    print("genres:", dict(Counter(g for m in chosen for g in m.genres).most_common()))
    for threshold in (8.5, 8.0, 7.5, 7.0, 6.0):
        print(
            f"vote_average >= {threshold}: {sum(1 for m in chosen if m.rating and m.rating >= threshold)}"
        )
    print("without vote_average:", sum(1 for m in chosen if m.rating is None))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["build", "check", "report"])
    args = parser.parse_args(argv)
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    movies = load_movies()
    must = must_include(config)
    ids = select(movies, config, must)
    if args.command == "build":
        OUTPUT_PATH.write_text(render(ids, config), encoding="utf-8")
        print(f"wrote {len(ids)} ids to {OUTPUT_PATH.relative_to(REPO_ROOT)}")
        report(ids, movies)
        return 0
    if args.command == "report":
        report(ids, movies)
        return 0
    committed = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else ""
    problems = violations(ids, movies, config, must)
    if committed != render(ids, config):
        problems.append(
            f"{OUTPUT_PATH.name} is out of date - run `python data/build_sample.py build`"
        )
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
