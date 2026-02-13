#!/usr/bin/env python3
"""
Unified data loader for flavours-of-elastic.

This script loads sample datasets into Elasticsearch for course exercises.

Usage:
    python data/load_data.py --dataset movies --size small
    python data/load_data.py --dataset movies --size full
    python data/load_data.py --dataset movies --with-embeddings

Requirements:
    pip install requests
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning

    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

# Dataset configurations
DATASETS = {
    "movies": {
        "small": "datasets/movies_100.json",
        "full": "datasets/movies_5000.json",
        "embeddings": "datasets/movies_embeddings.json",
        "index_name": "movies",
        "mapping": {
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
        },
        "mapping_with_embeddings": {
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
                    "dims": 384,
                    "index": True,
                    "similarity": "cosine",
                },
            }
        },
    }
}


class DataLoader:
    """Load data into Elasticsearch."""

    def __init__(self, base_url: str, auth: tuple = None, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self.verify_ssl = verify_ssl
        self.script_dir = Path(__file__).parent

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

        # Delete existing index if requested
        if delete_existing:
            try:
                requests.delete(url, auth=self.auth, verify=self.verify_ssl, timeout=10)
                print(f"Deleted existing index '{index_name}'")
            except Exception:
                pass

        # Create index with mapping
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

    def bulk_load(self, index_name: str, documents: list, batch_size: int = 500) -> int:
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

    def load_dataset(
        self, dataset_name: str, size: str = "small", with_embeddings: bool = False
    ) -> bool:
        """Load a dataset into Elasticsearch."""
        if dataset_name not in DATASETS:
            print(f"Unknown dataset: {dataset_name}")
            print(f"Available datasets: {list(DATASETS.keys())}")
            return False

        config = DATASETS[dataset_name]

        # Determine which file to load
        if with_embeddings:
            file_path = self.script_dir / config["embeddings"]
            mapping = config["mapping_with_embeddings"]
            index_name = f"{config['index_name']}-embeddings"
        else:
            file_path = self.script_dir / config[size]
            mapping = config["mapping"]
            index_name = config["index_name"]

        # Load JSON file
        print(f"\nLoading data from: {file_path}")
        try:
            with open(file_path) as f:
                documents = json.load(f)
            print(f"Loaded {len(documents)} documents from file")
        except FileNotFoundError:
            print(f"Error: File not found: {file_path}")
            return False
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON: {e}")
            return False

        # Create index
        if not self.create_index(index_name, mapping):
            return False

        # Load documents
        loaded = self.bulk_load(index_name, documents)

        # Refresh index to make documents searchable
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

  # Load movies with pre-computed embeddings
  python data/load_data.py --dataset movies --with-embeddings

  # Specify custom Elasticsearch URL
  python data/load_data.py --dataset movies --url http://localhost:9200 --no-auth
        """,
    )
    parser.add_argument(
        "--dataset",
        choices=list(DATASETS.keys()),
        default="movies",
        help="Dataset to load (default: movies)",
    )
    parser.add_argument(
        "--size",
        choices=["small", "full"],
        default="small",
        help="Dataset size (default: small)",
    )
    parser.add_argument(
        "--with-embeddings",
        action="store_true",
        help="Load dataset with pre-computed embeddings (for vector search)",
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
        # Auto-detect running stack
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

    # Create loader and verify connection
    loader = DataLoader(base_url, auth, verify)
    if not loader.check_connection():
        sys.exit(1)

    # Load the dataset
    success = loader.load_dataset(args.dataset, args.size, args.with_embeddings)

    if success:
        print("\nData loaded successfully!")
        print("\nTry these queries in Kibana Dev Tools:")
        print(f"  GET /{args.dataset}/_search")
        print(f"  GET /{args.dataset}/_search?q=title:*")
        if args.with_embeddings:
            print("\nFor vector search, use a kNN query in the API.")
    else:
        print("\nData loading failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
