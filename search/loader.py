"""Load the checked-in movie data into Elasticsearch or OpenSearch.

    python data/load_data.py --size small                    # movies (200 curated films)
    python data/load_data.py --size full                     # movies (all 5,100)
    python data/load_data.py --size small --embeddings hash  # movies-embeddings (+ 384-d vectors)
    python data/load_data.py --stack elk-ml --size full --json

The target cluster comes from --stack, --url, the environment or
auto-detection (see search/config.py). Exit codes: 0 ok, 2 usage,
3 connection/credentials, 4 refused (the cluster lacks a capability),
5 partial load (some documents failed or the count does not match).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from search.capabilities import Capabilities, detect
from search.config import Target, resolve
from search.connection import Client, ConnectionFailed, EsError
from search.embeddings import (
    DEFAULT_EMBEDDING_DIMS,
    HASH_MODEL,
    deterministic_text_embedding,
    embedding_text,
)
from search.mappings import MOVIES_MAPPING, VECTOR_FIELD, index_body
from search.movies import normalize_title

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"

EXIT_OK, EXIT_FAILED, EXIT_USAGE, EXIT_CONNECTION, EXIT_REFUSED, EXIT_PARTIAL = (
    0,
    1,
    2,
    3,
    4,
    5,
)

DATASETS = {
    "movies": {
        "small": {
            # Curated 200-movie sample (data/build_sample.py): every film the course
            # names, all decades 1910s-2000s and all genres.
            "path": DATA_DIR / "movies_enriched.csv",
            "limit": None,
            "ids": DATA_DIR / "movies_small_ids.txt",
        },
        "full": {
            "path": DATA_DIR / "movies_enriched.csv",
            "limit": None,
        },
        "index_name": "movies",
        "mapping": MOVIES_MAPPING,
    }
}

# Embedding backends: name -> (model id recorded in `_meta`, dims, function).
EMBEDDERS: Dict[str, tuple] = {
    "hash": (HASH_MODEL, DEFAULT_EMBEDDING_DIMS, deterministic_text_embedding),
}

YEAR_RE = re.compile(r"\((\d{4})\)\s*$")


# -- Documents -----------------------------------------------------------------


def parse_year(title: str) -> Optional[int]:
    """Extract a trailing release year from titles like 'Toy Story (1995)'."""
    match = YEAR_RE.search(title or "")
    if not match:
        return None
    return int(match.group(1))


def strip_year(title: str) -> str:
    """Remove a trailing release year while preserving the original title elsewhere."""
    return YEAR_RE.sub("", title or "").strip()


def split_genres(value: str) -> List[str]:
    """Normalize MovieLens genre strings into keyword arrays."""
    if not value or value == "(no genres listed)":
        return []
    return [genre for genre in value.split("|") if genre]


def normalize_movie(
    row: Dict[str, str],
    with_embeddings: bool = False,
    embed: Optional[Callable[[str], List[float]]] = None,
) -> Dict:
    """Normalize enriched CSV rows into the document shape used by the course."""
    movie_id = int(row["movieId"])
    genres = split_genres(row.get("genres", ""))
    title_raw = row.get("title", "")
    # "Godfather, The (1972)" -> "The Godfather"; alternate titles go to title_aka.
    title, title_aka = normalize_title(title_raw)
    overview = row.get("abstract_en") or row.get("description_en") or title
    year = parse_year(title_raw)
    searchable_text = embedding_text(
        [
            title,
            " ".join(title_aka),
            " ".join(genres),
            row.get("abstract_en", ""),
            row.get("description_en", ""),
        ]
    )

    doc = {
        "id": movie_id,
        "movieId": row["movieId"],
        "title": title,
        "title_aka": title_aka,
        "title_raw": title_raw,
        "year": year,
        "release_date": f"{year}-01-01" if year else None,
        "genres": genres,
        "vote_count": int(row.get("vote_count") or 0),
        "overview": overview,
        "abstract_en": row.get("abstract_en", ""),
        "abstract_kk": row.get("abstract_kk", ""),
        "abstract_fr": row.get("abstract_fr", ""),
        "description_en": row.get("description_en", ""),
        "description_kk": row.get("description_kk", ""),
        "description_fr": row.get("description_fr", ""),
        "searchable_text": searchable_text,
    }

    if row.get("vote_average"):
        doc["vote_average"] = float(row["vote_average"])

    if with_embeddings or embed:
        doc[VECTOR_FIELD] = (embed or deterministic_text_embedding)(searchable_text)

    return doc


def read_ids(path: Path) -> set:
    """Read a movieId list (one per line, `#` comments allowed)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


def read_movies(
    path: Path,
    limit: Optional[int],
    with_embeddings: bool = False,
    ids: Optional[Path] = None,
    embed: Optional[Callable[[str], List[float]]] = None,
) -> List[Dict]:
    """Read and normalize checked-in CSV movie data (optionally only the given ids)."""
    wanted = read_ids(ids) if ids else None
    documents = []
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            if wanted is not None and row["movieId"] not in wanted:
                continue
            documents.append(normalize_movie(row, with_embeddings, embed))
            if limit and len(documents) >= limit:
                break
    return documents


def source_checksum(*paths: Optional[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        if path:
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


# -- Loading -------------------------------------------------------------------


class Refused(RuntimeError):
    """The cluster cannot do what was asked (e.g. vectors on Elasticsearch OSS)."""


@dataclass
class LoadResult:
    index: str
    documents: int
    indexed: int = 0
    count: int = 0
    errors: Dict[str, int] = field(default_factory=dict)
    skipped: bool = False
    seconds: float = 0.0

    @property
    def complete(self) -> bool:
        return not self.errors and self.indexed == self.documents == self.count


def bulk_index(
    client: Client,
    index: str,
    documents: List[Dict],
    batch_size: int = 500,
    retries: int = 5,
    backoff: float = 1.0,
    progress: Callable[[str], None] = print,
) -> tuple:
    """Index documents with `_bulk`; resend items rejected with 429. Returns (indexed, errors by type)."""
    indexed, errors = 0, Counter()
    for start in range(0, len(documents), batch_size):
        pending = documents[start : start + batch_size]
        for attempt in range(retries + 1):
            lines = []
            for doc in pending:
                lines.append(json.dumps({"index": {"_index": index, "_id": doc["id"]}}))
                lines.append(json.dumps(doc, ensure_ascii=False))
            result = client.post("/_bulk", ndjson="\n".join(lines) + "\n", timeout=120)
            rejected = []
            for doc, item in zip(pending, result.get("items", [])):
                outcome = next(iter(item.values()), {})
                error = outcome.get("error")
                if not error:
                    indexed += 1
                elif outcome.get("status") == 429 and attempt < retries:
                    rejected.append(doc)
                else:
                    errors[
                        error.get("type", "unknown")
                        if isinstance(error, dict)
                        else "unknown"
                    ] += 1
            if not rejected:
                break
            pending = rejected
            time.sleep(backoff * 2**attempt)
        progress(f"Indexed {indexed}/{len(documents)} documents...")
    return indexed, dict(errors)


def current_meta(client: Client, index: str) -> Optional[dict]:
    if not client.exists(f"/{index}"):
        return None
    mapping = client.get(f"/{index}/_mapping")
    return next(iter(mapping.values()), {}).get("mappings", {}).get("_meta")


def load(
    client: Client,
    caps: Capabilities,
    size: str = "small",
    embeddings: str = "none",
    skip_if_current: bool = False,
    progress: Callable[[str], None] = print,
) -> LoadResult:
    config = DATASETS["movies"]
    sized = config[size]
    embedder = EMBEDDERS.get(embeddings)
    if embeddings != "none":
        if embedder is None:
            raise Refused(f"unknown embedding backend '{embeddings}'")
        if not caps.vectors:
            raise Refused(
                f"{caps.describe()} has no vector field type: use an Elasticsearch 8+/9+"
                " or OpenSearch stack for --embeddings"
            )
    index = "movies-embeddings" if embedder else config["index_name"]
    meta = {
        "foe": {
            "dataset": "movies",
            "size": size,
            "source": source_checksum(sized["path"], sized.get("ids")),
        }
    }
    if embedder:
        meta["foe"]["embedding"] = {
            "backend": embeddings,
            "model": embedder[0],
            "dims": embedder[1],
        }
    started = time.perf_counter()
    documents = read_movies(
        sized["path"],
        sized["limit"],
        ids=sized.get("ids"),
        embed=embedder[2] if embedder else None,
    )
    result = LoadResult(index, len(documents))
    progress(f"Read {len(documents)} movies from {sized['path'].name} ({size})")

    if skip_if_current and current_meta(client, index) == meta:
        result.count = client.get(f"/{index}/_count")["count"]
        if result.count == len(documents):
            result.indexed, result.skipped = result.count, True
            progress(
                f"'{index}' is already current ({result.count} documents): skipped"
            )
            return result

    client.delete(f"/{index}", ok=(404,))
    client.put(
        f"/{index}",
        index_body(caps, meta, embedder[1] if embedder else None),
    )
    progress(f"Created index '{index}'")
    result.indexed, result.errors = bulk_index(
        client, index, documents, progress=progress
    )
    client.post(f"/{index}/_refresh")
    result.count = client.get(f"/{index}/_count")["count"]
    result.seconds = round(time.perf_counter() - started, 1)
    return result


# -- CLI -----------------------------------------------------------------------


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="data/load_data.py",
        description="Load the movie dataset into Elasticsearch or OpenSearch.",
        epilog=__doc__.split("\n\n")[1],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dataset", choices=list(DATASETS), default="movies")
    parser.add_argument("--size", choices=["small", "full"], default="small")
    parser.add_argument(
        "--embeddings",
        choices=["none", *EMBEDDERS],
        default=None,
        help="add a 384-d vector per movie and load movies-embeddings (default: none)",
    )
    parser.add_argument(
        "--with-embeddings",
        action="store_true",
        help="deprecated: same as --embeddings hash",
    )
    where = parser.add_mutually_exclusive_group()
    where.add_argument("--stack", help="a stack from scripts/stacks.py, e.g. elk-ml")
    where.add_argument(
        "--url", help="cluster URL (default: environment, then auto-detect)"
    )
    parser.add_argument("--user")
    parser.add_argument("--password")
    parser.add_argument("--no-auth", action="store_true")
    parser.add_argument("--insecure", action="store_true", help="skip TLS verification")
    parser.add_argument(
        "--skip-if-current",
        action="store_true",
        help="do nothing when the index already holds exactly this data",
    )
    parser.add_argument("--json", action="store_true", help="print a JSON summary")
    args = parser.parse_args(argv)
    if args.with_embeddings:
        if args.embeddings not in (None, "hash"):
            parser.error("--with-embeddings conflicts with --embeddings")
        args.embeddings = "hash"
        print(
            "note: --with-embeddings is deprecated, use --embeddings hash",
            file=sys.stderr,
        )
    args.embeddings = args.embeddings or "none"
    return args


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    out = sys.stderr if args.json else sys.stdout

    def progress(message: str) -> None:
        print(message, file=out, flush=True)

    summary: dict = {"ok": False}
    try:
        target: Target = resolve(
            stack=args.stack,
            url=args.url,
            user=args.user,
            password=args.password,
            no_auth=args.no_auth,
            insecure=args.insecure,
        )
        client = target.client()
        caps = detect(client)
        progress(f"Connected to {caps.describe()} at {target.describe()}")
        summary.update(url=target.url, cluster=caps.describe())
        result = load(
            client, caps, args.size, args.embeddings, args.skip_if_current, progress
        )
    except ConnectionFailed as exc:
        return finish(args, summary, f"Error: {exc}", EXIT_CONNECTION)
    except Refused as exc:
        return finish(args, summary, f"Refused: {exc}", EXIT_REFUSED)
    except EsError as exc:
        return finish(args, summary, f"Error: {exc}", EXIT_FAILED)

    summary.update(asdict(result), ok=result.complete)
    if not result.complete:
        problem = (
            f"{result.indexed}/{result.documents} indexed, {result.count} searchable"
        )
        if result.errors:
            problem += f"; errors: {result.errors}"
        return finish(
            args,
            summary,
            f"Partial load into '{result.index}': {problem}",
            EXIT_PARTIAL,
        )
    if not args.json:
        verb = "Already loaded" if result.skipped else "Loaded"
        print(f"\n{verb} {result.count} documents into '{result.index}'.")
        print("\nTry these queries in Kibana Dev Tools:")
        print(f"  GET /{result.index}/_search")
        print(f"  GET /{result.index}/_search?q=title:toy")
    return finish(args, summary, None, EXIT_OK)


def finish(
    args: argparse.Namespace, summary: dict, error: Optional[str], code: int
) -> int:
    if error:
        summary["error"] = error
        print(error, file=sys.stderr)
    if args.json:
        print(json.dumps(summary, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
