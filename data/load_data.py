#!/usr/bin/env python3
"""
Unified data loader for flavours-of-elastic.

This script loads sample datasets into Elasticsearch for course exercises.
Reads directly from movies_enriched.csv files.

Usage:
    python data/load_data.py --dataset movies --size small
    python data/load_data.py --dataset movies --size full
    python data/load_data.py --dataset movies --with-embeddings

Requirements:
    pip install requests
"""

import argparse
import csv
import json
import random
import re
import sys
from pathlib import Path

try:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning

    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent

# Mapping for standard movies index
MOVIES_MAPPING = {
    "properties": {
        "id": {"type": "integer"},
        "title": {"type": "text", "analyzer": "english"},
        "overview": {
            "type": "text",
            "analyzer": "english",
            "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
        },
        "genres": {"type": "keyword"},
        "vote_average": {"type": "float"},
        "release_date": {"type": "date"},
    }
}

# Mapping with dense_vector for embeddings index
MOVIES_EMBEDDING_MAPPING = {
    "properties": {
        "id": {"type": "integer"},
        "title": {"type": "text", "analyzer": "english"},
        "overview": {
            "type": "text",
            "analyzer": "english",
            "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
        },
        "genres": {"type": "keyword"},
        "vote_average": {"type": "float"},
        "release_date": {"type": "date"},
        "overview_embedding": {
            "type": "dense_vector",
            "dims": 768,
            "index": True,
            "similarity": "cosine",
        },
    }
}


def extract_year(title):
    """Extract year from title like 'Toy Story (1995)'."""
    match = re.search(r"\((\d{4})\)", title)
    return int(match.group(1)) if match else None


def generate_vote_average(movie_id):
    """Generate a reproducible vote_average based on movieId."""
    rng = random.Random(movie_id)
    val = rng.gauss(6.5, 1.5)
    return round(max(1.0, min(10.0, val)), 1)


def load_movies_from_csv(csv_path, limit=None):
    """Load movies from enriched CSV and transform to ES document format."""
    documents = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if limit and i >= limit:
                break
            movie_id = int(row["movieId"])
            title = row["title"]
            year = extract_year(title)

            doc = {
                "id": movie_id,
                "title": title,
                "overview": row.get("abstract_en", ""),
                "abstract_en": row["abstract_en"],
                "abstract_fr": row["abstract_fr"],
                "abstract_kk": row["abstract_kk"],
                "genres": row["genres"].split("|") if row["genres"] else [],
                "vote_average": generate_vote_average(movie_id),
            }
            if year:
                doc["release_date"] = f"{year}-01-01"

            documents.append(doc)
    return documents


def load_movies_with_embeddings(csv_path, embeddings_path, limit=None):
    """Load movies from CSV and merge with pre-computed embeddings."""
    documents = load_movies_from_csv(csv_path, limit=limit)

    print(f"Loading embeddings from: {embeddings_path}")
    with open(embeddings_path, encoding="utf-8") as f:
        embeddings_data = json.load(f)

    # Build lookups by movieId
    emb_lookup = {}
    desc_lookup = {}
    for item in embeddings_data:
        mid = int(item.get("movieId", 0))
        # Use description_en embedding as overview_embedding
        emb = item.get("description_en_embedding")
        desc = item.get("description_en", "")
        if emb:
            emb_lookup[mid] = emb
        if desc:
            desc_lookup[mid] = desc

    matched = 0
    for doc in documents:
        emb = emb_lookup.get(doc["id"])
        if emb:
            doc["overview_embedding"] = emb
            # Use description_en as overview to match embedding source
            doc["overview"] = desc_lookup.get(doc["id"], doc.get("overview", ""))
            matched += 1

    print(f"  Matched {matched}/{len(documents)} movies with embeddings")

    # Only keep documents that have embeddings
    documents = [d for d in documents if "overview_embedding" in d]
    return documents


class DataLoader:
    """Load data into Elasticsearch."""

    def __init__(self, base_url: str, auth: tuple = None, verify_ssl: bool = True):
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
            else:
                print(f"Connection failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def create_index(
        self, index_name: str, mapping: dict, delete_existing: bool = True
    ) -> bool:
        """Create an index with mapping."""
        url = f"{self.base_url}/{index_name}"

        if delete_existing:
            try:
                requests.delete(url, auth=self.auth, verify=self.verify_ssl, timeout=10)
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
            else:
                print(f"Failed to create index: {response.status_code}")
                print(response.text)
                return False
        except Exception as e:
            print(f"Error creating index: {e}")
            return False

    def bulk_load(self, index_name: str, documents: list, batch_size: int = 100) -> int:
        """Load documents using bulk API."""
        url = f"{self.base_url}/_bulk"
        loaded = 0

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            bulk_body = ""

            for doc in batch:
                action = {"index": {"_index": index_name, "_id": doc.get("id")}}
                bulk_body += json.dumps(action) + "\n"
                bulk_body += json.dumps(doc) + "\n"

            try:
                response = requests.post(
                    url,
                    data=bulk_body,
                    auth=self.auth,
                    verify=self.verify_ssl,
                    timeout=60,
                    headers={"Content-Type": "application/x-ndjson"},
                )
                if response.status_code in [200, 201]:
                    result = response.json()
                    if result.get("errors"):
                        print(
                            f"Warning: Some documents had errors in batch {i // batch_size + 1}"
                        )
                    loaded += len(batch)
                    print(f"Loaded {loaded}/{len(documents)} documents...")
                else:
                    print(f"Bulk load failed: {response.status_code}")
                    print(response.text[:500])
            except Exception as e:
                print(f"Bulk load error: {e}")

        return loaded

    def load_movies(self, size="small", with_embeddings=False) -> bool:
        """Load movies dataset into Elasticsearch."""
        if with_embeddings:
            csv_path = SCRIPT_DIR / "movies_enriched.csv"
            emb_path = SCRIPT_DIR / "movies_enriched_with_embeddings.json"
            if not emb_path.exists():
                print(f"Error: Embeddings file not found: {emb_path}")
                print("Run: python data/generate_embeddings.py")
                return False
            mapping = MOVIES_EMBEDDING_MAPPING
            index_name = "movies-embeddings"
            print(f"\nLoading movies with embeddings from: {csv_path}")
            documents = load_movies_with_embeddings(csv_path, emb_path)
        else:
            if size == "small":
                csv_path = SCRIPT_DIR / "movies_enriched_1000.csv"
                limit = 100
            else:
                csv_path = SCRIPT_DIR / "movies_enriched.csv"
                limit = 5000
            mapping = MOVIES_MAPPING
            index_name = "movies"
            print(f"\nLoading {size} movies dataset from: {csv_path}")
            documents = load_movies_from_csv(csv_path, limit=limit)

        print(f"Prepared {len(documents)} documents")

        if not self.create_index(index_name, mapping):
            return False

        loaded = self.bulk_load(index_name, documents)

        requests.post(
            f"{self.base_url}/{index_name}/_refresh",
            auth=self.auth,
            verify=self.verify_ssl,
        )

        print(f"\nSuccessfully loaded {loaded} documents into '{index_name}'")
        return True


def detect_stack():
    """Detect which Elasticsearch stack is running."""
    stacks = [
        {
            "name": "Elastic Stack (HTTPS)",
            "url": "https://localhost:9200",
            "auth": ("elastic", "elastic"),
            "verify": False,
        },
        {
            "name": "Elastic Single (HTTP)",
            "url": "http://localhost:9200",
            "auth": ("elastic", "elastic"),
            "verify": True,
        },
        {
            "name": "OpenSearch",
            "url": "https://localhost:9200",
            "auth": ("admin", "MyStrongPassword123!"),
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


def main():
    parser = argparse.ArgumentParser(
        description="Load sample data into Elasticsearch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Load small movies dataset (100 docs)
  python data/load_data.py --dataset movies --size small

  # Load full movies dataset (5000 docs)
  python data/load_data.py --dataset movies --size full

  # Load movies with pre-computed embeddings (768-dim)
  python data/load_data.py --dataset movies --with-embeddings

  # Specify custom Elasticsearch URL
  python data/load_data.py --dataset movies --url http://localhost:9200 --no-auth
        """,
    )
    parser.add_argument(
        "--dataset",
        choices=["movies"],
        default="movies",
        help="Dataset to load (default: movies)",
    )
    parser.add_argument(
        "--size",
        choices=["small", "full"],
        default="small",
        help="Dataset size: small=100, full=5000 (default: small)",
    )
    parser.add_argument(
        "--with-embeddings",
        action="store_true",
        help="Load dataset with pre-computed 768-dim embeddings (for vector search)",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Elasticsearch URL (auto-detected if not specified)",
    )
    parser.add_argument(
        "--user",
        default=None,
        help="Elasticsearch username",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Elasticsearch password",
    )
    parser.add_argument(
        "--no-auth",
        action="store_true",
        help="Connect without authentication",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Skip SSL verification",
    )

    args = parser.parse_args()

    # Determine connection settings
    if args.url:
        base_url = args.url
        auth = (args.user, args.password) if args.user and args.password else None
        if args.no_auth:
            auth = None
        verify = not args.insecure
    else:
        print("Auto-detecting Elasticsearch stack...")
        stack = detect_stack()
        if not stack:
            print("Error: No Elasticsearch stack detected.")
            print("Please start one of the stacks or specify --url manually.")
            sys.exit(1)
        print(f"Detected: {stack['name']}")
        base_url = stack["url"]
        auth = stack["auth"]
        verify = stack["verify"]

    loader = DataLoader(base_url, auth, verify)
    if not loader.check_connection():
        sys.exit(1)

    success = loader.load_movies(args.size, args.with_embeddings)

    if success:
        print("\nData loaded successfully!")
        print("\nTry these queries in Kibana Dev Tools:")
        index_name = "movies-embeddings" if args.with_embeddings else "movies"
        print(f"  GET /{index_name}/_search")
        print(f"  GET /{index_name}/_count")
        if args.with_embeddings:
            print("\nFor vector search, use a kNN query in the API.")
    else:
        print("\nData loading failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
