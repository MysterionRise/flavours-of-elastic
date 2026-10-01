#!/usr/bin/env python3
"""Add MovieLens-derived `vote_average` / `vote_count` columns to movies_enriched.csv.

Maintainer tool - run once and commit the result; students never need ml-32m.

    curl -LO https://files.grouplens.org/datasets/movielens/ml-32m.zip && unzip ml-32m.zip
    python data/add_ratings.py --ratings ml-32m/ratings.csv --movies ml-32m/movies.csv
    python data/add_ratings.py --ratings ml-32m/ratings.csv --movies ml-32m/movies.csv --check

- vote_count   = number of ml-32m ratings for the movie (0 when unrated);
- vote_average = mean rating x 2 (MovieLens 0.5-5 stars -> 1-10), rounded half-up
                 to one decimal with integer arithmetic; left empty below
                 --min-votes so a handful of ratings cannot top the charts.

Every movieId must exist in ml-32m movies.csv with the same title and genres,
which guards against mixing MovieLens releases. The CSV is rewritten atomically
with the csv module defaults (byte-for-byte identical apart from the new columns).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = SCRIPT_DIR / "movies_enriched.csv"
DEFAULT_META = SCRIPT_DIR / "movies_enriched.meta.json"
NEW_COLUMNS = ("vote_average", "vote_count")
ML_32M_URL = "https://files.grouplens.org/datasets/movielens/ml-32m.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def format_average(half_star_sum: int, count: int, min_votes: int) -> str:
    """Mean of half-star ratings (1..10) rounded half-up to one decimal, as text.

    tenths = round_half_up(10 * S / n) = floor((20 * S + n) / (2 * n)) with S the sum
    of ratings expressed in half stars (rating x 2) - no floating point involved.
    """
    if count < min_votes or count == 0:
        return ""
    tenths = (20 * half_star_sum + count) // (2 * count)
    return f"{tenths // 10}.{tenths % 10}"


def read_csv(path: Path) -> tuple[list[str], list[list[str]], str]:
    raw = path.read_bytes().decode("utf-8")  # keep the CRLF line endings for --check
    rows = list(csv.reader(io.StringIO(raw, newline="")))
    return rows[0], rows[1:], raw


def load_movielens_movies(path: Path) -> dict[str, tuple[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        if header != ["movieId", "title", "genres"]:
            raise SystemExit(f"unexpected header in {path}: {header}")
        return {row[0]: (row[1], row[2]) for row in reader}


def aggregate_ratings(
    path: Path, wanted: set[str]
) -> tuple[dict[str, int], dict[str, int], int]:
    """Stream ratings.csv (no quoted fields) and sum half-star ratings per wanted movie."""
    sums: dict[str, int] = dict.fromkeys(wanted, 0)
    counts: dict[str, int] = dict.fromkeys(wanted, 0)
    total = 0
    with path.open(encoding="utf-8") as handle:
        header = handle.readline().strip()
        if header != "userId,movieId,rating,timestamp":
            raise SystemExit(f"unexpected header in {path}: {header}")
        for line in handle:
            total += 1
            _, movie_id, rating, _ = line.split(",", 3)
            if movie_id in sums:
                whole, _, frac = rating.partition(".")
                sums[movie_id] += int(whole) * 2 + (1 if frac.startswith("5") else 0)
                counts[movie_id] += 1
    return sums, counts, total


def build(
    header: list[str], rows: list[list[str]], sums, counts, min_votes: int
) -> tuple[list[str], list[list[str]]]:
    base = [name for name in header if name not in NEW_COLUMNS]
    position = base.index("genres") + 1
    new_header = base[:position] + list(NEW_COLUMNS) + base[position:]
    index = {name: i for i, name in enumerate(header)}
    new_rows = []
    for row in rows:
        values = {name: row[i] for name, i in index.items()}
        movie_id = values["movieId"]
        values["vote_count"] = str(counts[movie_id])
        values["vote_average"] = format_average(
            sums[movie_id], counts[movie_id], min_votes
        )
        new_rows.append([values[name] for name in new_header])
    return new_header, new_rows


def render(header: list[str], rows: list[list[str]]) -> str:
    out = io.StringIO(newline="")
    csv.writer(out).writerows([header, *rows])
    return out.getvalue()


def report(header: list[str], rows: list[list[str]]) -> None:
    col = {name: i for i, name in enumerate(header)}
    rated = [
        (float(r[col["vote_average"]]), int(r[col["vote_count"]]), r[col["title"]])
        for r in rows
        if r[col["vote_average"]]
    ]
    unrated = sum(1 for r in rows if r[col["vote_count"]] == "0")
    sparse = sum(
        1 for r in rows if r[col["vote_count"]] != "0" and not r[col["vote_average"]]
    )
    print(
        f"movies: {len(rows)}  with vote_average: {len(rated)}  below min votes: {sparse}  unrated: {unrated}"
    )
    buckets = Counter(int(avg) for avg, _, _ in rated)
    print(
        "vote_average histogram:",
        " ".join(f"{b}:{buckets[b]}" for b in sorted(buckets)),
    )
    popular = sorted((r for r in rated if r[1] >= 1000), reverse=True)
    for label, chunk in (("top", popular[:5]), ("bottom", popular[-5:])):
        print(
            f"{label} (>= 1000 votes): "
            + "; ".join(f"{t} {a} ({n})" for a, n, t in chunk)
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--ratings", type=Path, required=True, help="ml-32m/ratings.csv"
    )
    parser.add_argument("--movies", type=Path, required=True, help="ml-32m/movies.csv")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--meta", type=Path, default=DEFAULT_META)
    parser.add_argument("--min-votes", type=int, default=10)
    parser.add_argument(
        "--check",
        action="store_true",
        help="recompute and compare; exit 1 on any difference",
    )
    args = parser.parse_args(argv)

    header, rows, raw = read_csv(args.csv)
    col = {name: i for i, name in enumerate(header)}
    movielens = load_movielens_movies(args.movies)
    mismatches = [
        row[col["movieId"]]
        for row in rows
        if movielens.get(row[col["movieId"]]) != (row[col["title"]], row[col["genres"]])
    ]
    if mismatches:
        print(
            f"{len(mismatches)} movies differ from ml-32m movies.csv (first: {mismatches[:5]})",
            file=sys.stderr,
        )
        return 1

    wanted = {row[col["movieId"]] for row in rows}
    sums, counts, total = aggregate_ratings(args.ratings, wanted)
    new_header, new_rows = build(header, rows, sums, counts, args.min_votes)
    rendered = render(new_header, new_rows)

    if args.check:
        if rendered != raw:
            print(f"{args.csv} is out of date - rerun without --check", file=sys.stderr)
            return 1
        print(f"{args.csv.name} matches ml-32m ({total} ratings scanned)")
        return 0

    tmp = args.csv.with_suffix(".csv.tmp")
    tmp.write_text(rendered, encoding="utf-8", newline="")
    os.replace(tmp, args.csv)
    meta = json.loads(args.meta.read_text()) if args.meta.exists() else {}
    meta["ratings"] = {
        "source": ML_32M_URL,
        "ratings_csv_sha256": sha256(args.ratings),
        "movies_csv_sha256": sha256(args.movies),
        "ratings_scanned": total,
        "vote_average": "mean MovieLens rating x 2 (scale 1-10), round half-up to 0.1",
        "min_votes": args.min_votes,
        "generated_by": "data/add_ratings.py",
    }
    meta["rows"] = len(new_rows)
    meta["csv_sha256"] = sha256(args.csv)
    args.meta.write_text(json.dumps(meta, indent=2) + "\n")
    report(new_header, new_rows)
    print(f"wrote {args.csv} and {args.meta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
