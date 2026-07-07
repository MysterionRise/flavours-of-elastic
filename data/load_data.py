#!/usr/bin/env python3
"""
Load checked-in movie data into Elasticsearch for course and portfolio demos.

Usage:
    python data/load_data.py --dataset movies --size small
    python data/load_data.py --dataset movies --size full
    python data/load_data.py --dataset movies --with-embeddings
"""

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

try:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning

    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

from search.embeddings import DEFAULT_EMBEDDING_DIMS  # noqa: E402
from search.embeddings import deterministic_text_embedding, embedding_text  # noqa: E402

YEAR_RE = re.compile(r"\((\d{4})\)\s*$")


MOVIES_MAPPING = {
    "properties": {
        "id": {"type": "integer"},
        "movieId": {"type": "keyword"},
        "title": {
            "type": "text",
            "analyzer": "english",
            "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
        },
        "title_raw": {"type": "keyword", "ignore_above": 256},
        "year": {"type": "integer"},
        "release_date": {"type": "date"},
        "genres": {"type": "keyword"},
        "overview": {
            "type": "text",
            "analyzer": "english",
            "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
        },
        "abstract_en": {"type": "text", "analyzer": "english"},
        "abstract_kk": {"type": "text"},
        "abstract_fr": {"type": "text", "analyzer": "french"},
        "description_en": {"type": "text", "analyzer": "english"},
        "description_kk": {"type": "text"},
        "description_fr": {"type": "text", "analyzer": "french"},
        "searchable_text": {"type": "text", "analyzer": "english"},
    }
}


MOVIES_MAPPING_WITH_EMBEDDINGS = {
    "properties": {
        **MOVIES_MAPPING["properties"],
        "overview_embedding": {
            "type": "dense_vector",
            "dims": DEFAULT_EMBEDDING_DIMS,
            "index": True,
            "similarity": "cosine",
        },
    }
}


DATASETS = {
    "movies": {
        "small": {
            "path": SCRIPT_DIR / "movies_enriched_1000.csv",
            "limit": 100,
        },
        "full": {
            "path": SCRIPT_DIR / "movies_enriched.csv",
            "limit": None,
        },
        "index_name": "movies",
        "mapping": MOVIES_MAPPING,
        "mapping_with_embeddings": MOVIES_MAPPING_WITH_EMBEDDINGS,
    }
}


def env(name: str, default: str) -> str:
    """Read an environment value with a local-development default."""
    return os.getenv(name, default)


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


def normalize_movie(row: Dict[str, str], with_embeddings: bool = False) -> Dict:
    """Normalize enriched CSV rows into the document shape used by the course."""
    movie_id = int(row["movieId"])
    genres = split_genres(row.get("genres", ""))
    title_raw = row.get("title", "")
    title = strip_year(title_raw)
    overview = row.get("abstract_en") or row.get("description_en") or title
    year = parse_year(title_raw)
    searchable_text = embedding_text(
        [
            title,
            " ".join(genres),
            row.get("abstract_en", ""),
            row.get("description_en", ""),
        ]
    )

    doc = {
        "id": movie_id,
        "movieId": row["movieId"],
        "title": title,
        "title_raw": title_raw,
        "year": year,
        "release_date": f"{year}-01-01" if year else None,
        "genres": genres,
        "overview": overview,
        "abstract_en": row.get("abstract_en", ""),
        "abstract_kk": row.get("abstract_kk", ""),
        "abstract_fr": row.get("abstract_fr", ""),
        "description_en": row.get("description_en", ""),
        "description_kk": row.get("description_kk", ""),
        "description_fr": row.get("description_fr", ""),
        "searchable_text": searchable_text,
    }

    if with_embeddings:
        doc["overview_embedding"] = deterministic_text_embedding(searchable_text)

    return doc


def read_movies(path: Path, limit: Optional[int], with_embeddings: bool) -> List[Dict]:
    """Read and normalize checked-in CSV movie data."""
    documents = []
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            documents.append(normalize_movie(row, with_embeddings=with_embeddings))
            if limit and len(documents) >= limit:
                break
    return documents


class DataLoader:
    """Load data into Elasticsearch-compatible search engines."""

    def __init__(
        self,
        base_url: str,
        auth: Optional[Tuple[str, str]] = None,
        verify_ssl: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self.verify_ssl = verify_ssl

    def check_connection(self) -> bool:
        """Verify Elasticsearch is accessible."""
        try:
            response = requests.get(
                f"{self.base_url}/_cluster/health",
                auth=self.auth,
                verify=self.verify_ssl,
                timeout=10,
            )
            if response.status_code == 200:
                health = response.json()
                print(f"Connected to cluster: {health.get('cluster_name')}")
                print(f"Cluster status: {health.get('status')}")
                return True
            print(f"Connection failed: {response.status_code}")
            print(response.text[:500])
            return False
        except Exception as exc:
            print(f"Connection error: {exc}")
            return False

    def create_index(
        self, index_name: str, mapping: Dict, delete_existing: bool = True
    ) -> bool:
        """Create an index with mapping."""
        url = f"{self.base_url}/{index_name}"

        if delete_existing:
            try:
                response = requests.delete(
                    url, auth=self.auth, verify=self.verify_ssl, timeout=10
                )
                if response.status_code in [200, 202]:
                    print(f"Deleted existing index '{index_name}'")
            except Exception:
                pass

        try:
            response = requests.put(
                url,
                json={"mappings": mapping},
                auth=self.auth,
                verify=self.verify_ssl,
                timeout=30,
                headers={"Content-Type": "application/json"},
            )
            if response.status_code in [200, 201]:
                print(f"Created index '{index_name}'")
                return True
            print(f"Failed to create index: {response.status_code}")
            print(response.text)
            return False
        except Exception as exc:
            print(f"Error creating index: {exc}")
            return False

    def bulk_load(
        self, index_name: str, documents: List[Dict], batch_size: int = 500
    ) -> int:
        """Load documents using the bulk API."""
        url = f"{self.base_url}/_bulk"
        loaded = 0

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            lines = []

            for doc in batch:
                lines.append(
                    json.dumps({"index": {"_index": index_name, "_id": doc["id"]}})
                )
                lines.append(json.dumps(doc, ensure_ascii=False))

            bulk_body = ("\n".join(lines) + "\n").encode("utf-8")

            try:
                response = requests.post(
                    url,
                    data=bulk_body,
                    auth=self.auth,
                    verify=self.verify_ssl,
                    timeout=60,
                    headers={"Content-Type": "application/x-ndjson"},
                )
                if response.status_code not in [200, 201]:
                    print(f"Bulk load failed: {response.status_code}")
                    print(response.text[:500])
                    continue

                result = response.json()
                errors = [
                    item
                    for item in result.get("items", [])
                    if item.get("index", {}).get("error")
                ]
                if errors:
                    print(
                        f"Warning: {len(errors)} documents had errors in batch {i // batch_size + 1}"
                    )
                    print(json.dumps(errors[:3], indent=2)[:1000])

                loaded += len(batch) - len(errors)
                print(f"Loaded {loaded}/{len(documents)} documents...")
            except Exception as exc:
                print(f"Bulk load error: {exc}")

        return loaded

    def refresh(self, index_name: str) -> None:
        """Refresh index to make documents searchable."""
        requests.post(
            f"{self.base_url}/{index_name}/_refresh",
            auth=self.auth,
            verify=self.verify_ssl,
            timeout=30,
        )

    def load_dataset(
        self, dataset_name: str, size: str = "small", with_embeddings: bool = False
    ) -> bool:
        """Load a checked-in dataset into Elasticsearch."""
        if dataset_name not in DATASETS:
            print(f"Unknown dataset: {dataset_name}")
            print(f"Available datasets: {list(DATASETS.keys())}")
            return False

        config = DATASETS[dataset_name]
        size_config = config[size]
        mapping = (
            config["mapping_with_embeddings"] if with_embeddings else config["mapping"]
        )
        index_name = (
            f"{config['index_name']}-embeddings"
            if with_embeddings
            else config["index_name"]
        )

        print(f"\nLoading data from: {size_config['path']}")
        documents = read_movies(
            size_config["path"], size_config["limit"], with_embeddings=with_embeddings
        )
        print(f"Loaded {len(documents)} normalized documents from file")

        if not self.create_index(index_name, mapping):
            return False

        loaded = self.bulk_load(index_name, documents)
        self.refresh(index_name)

        print(f"\nSuccessfully loaded {loaded} documents into '{index_name}'")
        return loaded == len(documents)


def detect_stack():
    """Detect which local search stack is running."""
    stacks = [
        {
            "name": "Elastic Stack (HTTPS)",
            "url": "https://localhost:9200",
            "auth": (
                env("ELASTIC_USER", "elastic"),
                env("ELASTIC_PASSWORD", "elastic"),
            ),
            "verify": False,
        },
        {
            "name": "Elastic Single (HTTP)",
            "url": "http://localhost:9200",
            "auth": (
                env("ELASTIC_USER", "elastic"),
                env("ELASTIC_PASSWORD", "elastic"),
            ),
            "verify": True,
        },
        {
            "name": "OpenSearch",
            "url": "https://localhost:9200",
            "auth": (
                "admin",
                env("OPENSEARCH_INITIAL_ADMIN_PASSWORD", "MyStrongPassword123!"),
            ),
            "verify": False,
        },
        {
            "name": "Elastic OSS",
            "url": "http://localhost:9200",
            "auth": None,
            "verify": True,
        },
    ]

    for stack in stacks:
        try:
            response = requests.get(
                stack["url"],
                auth=stack["auth"],
                verify=stack["verify"],
                timeout=5,
            )
            if response.status_code in [200, 401]:
                return stack
        except Exception:
            pass

    return None


def parse_args(argv: Optional[Iterable[str]] = None):
    parser = argparse.ArgumentParser(
        description="Load sample movie data into Elasticsearch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python data/load_data.py --dataset movies --size small
  python data/load_data.py --dataset movies --size full
  python data/load_data.py --dataset movies --with-embeddings
  python data/load_data.py --dataset movies --url http://localhost:9200 --user elastic --password elastic
        """,
    )
    parser.add_argument("--dataset", choices=list(DATASETS.keys()), default="movies")
    parser.add_argument("--size", choices=["small", "full"], default="small")
    parser.add_argument("--with-embeddings", action="store_true")
    parser.add_argument(
        "--url", default=None, help="Elasticsearch URL; auto-detected if omitted"
    )
    parser.add_argument("--user", default=os.getenv("ELASTIC_USER"))
    parser.add_argument("--password", default=os.getenv("ELASTIC_PASSWORD"))
    parser.add_argument("--no-auth", action="store_true")
    parser.add_argument("--insecure", action="store_true", help="Skip SSL verification")
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)

    if args.url:
        auth = (args.user, args.password) if args.user and args.password else None
        if args.no_auth:
            auth = None
        base_url = args.url
        verify = not args.insecure
    else:
        print("Auto-detecting Elasticsearch stack...")
        stack = detect_stack()
        if not stack:
            print("Error: No Elasticsearch stack detected.")
            print("Please start one of the stacks or specify --url manually.")
            return 1
        print(f"Detected: {stack['name']}")
        base_url = stack["url"]
        auth = stack["auth"]
        verify = stack["verify"]

    loader = DataLoader(base_url, auth, verify)
    if not loader.check_connection():
        return 1

    success = loader.load_dataset(args.dataset, args.size, args.with_embeddings)

    if not success:
        print("\nData loading failed!")
        return 1

    index_name = "movies-embeddings" if args.with_embeddings else args.dataset
    print("\nData loaded successfully!")
    print("\nTry these queries in Kibana Dev Tools:")
    print(f"  GET /{index_name}/_search")
    print(f"  GET /{index_name}/_search?q=title:toy")
    if args.with_embeddings:
        print("  GET /movies-embeddings/_search  # use kNN over overview_embedding")
    return 0


if __name__ == "__main__":
    sys.exit(main())
