#!/usr/bin/env python3
"""
Create a combined index with both dense_vector + semantic_text (ELSER).

Indexes a subset of movies into 'movies-hybrid' with:
  - overview: text (for BM25 full-text search)
  - overview_semantic: semantic_text (ELSER sparse embeddings, auto-generated at ingest)
  - overview_embedding: dense_vector 768-dim (pre-computed, EmbeddingGemma-300M)
  - title, genres, vote_average, release_date: standard fields

Usage:
    source .venv/bin/activate
    python data/load_hybrid_index.py              # default 100 docs
    python data/load_hybrid_index.py --limit 200  # custom limit
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

ES_URL = "https://localhost:9200"
ES_AUTH = ("elastic", "elastic")
INDEX = "movies-hybrid"
ELSER_ENDPOINT = "my-elser-endpoint"
SCRIPT_DIR = Path(__file__).parent

MAPPING = {
    "mappings": {
        "properties": {
            "id": {"type": "integer"},
            "title": {"type": "text", "analyzer": "english"},
            "overview": {
                "type": "text",
                "analyzer": "english",
            },
            "overview_semantic": {
                "type": "semantic_text",
                "inference_id": ELSER_ENDPOINT,
            },
            "overview_embedding": {
                "type": "dense_vector",
                "dims": 768,
                "index": True,
                "similarity": "cosine",
            },
            "genres": {"type": "keyword"},
            "vote_average": {"type": "float"},
            "release_date": {"type": "date"},
        }
    }
}


def ensure_elser_endpoint():
    """Create ELSER inference endpoint if it doesn't exist."""
    r = requests.get(
        f"{ES_URL}/_inference/{ELSER_ENDPOINT}",
        auth=ES_AUTH, verify=False, timeout=10,
    )
    if r.status_code == 200:
        print(f"  ELSER endpoint '{ELSER_ENDPOINT}' already exists")
        return True

    print(f"  Creating ELSER endpoint '{ELSER_ENDPOINT}'...")
    r = requests.put(
        f"{ES_URL}/_inference/sparse_embedding/{ELSER_ENDPOINT}",
        json={
            "service": "elser",
            "service_settings": {
                "num_allocations": 1,
                "num_threads": 1,
            },
        },
        auth=ES_AUTH, verify=False, timeout=60,
    )
    if r.status_code in (200, 201):
        print("  ELSER endpoint created, waiting for model to load...")
        for _ in range(30):
            time.sleep(10)
            check = requests.post(
                f"{ES_URL}/_inference/sparse_embedding/{ELSER_ENDPOINT}",
                json={"input": ["test"]},
                auth=ES_AUTH, verify=False, timeout=30,
            )
            if check.status_code == 200:
                print("  ELSER model ready!")
                return True
            print("  Still loading...")
        print("  [!] ELSER model took too long to load")
        return False
    else:
        print(f"  [!] Failed to create endpoint: {r.status_code} {r.text[:300]}")
        return False


def load_embeddings_data(limit):
    """Load movies with pre-computed embeddings from JSON + CSV."""
    emb_path = SCRIPT_DIR / "movies_enriched_with_embeddings.json"
    print(f"  Loading embeddings from: {emb_path}")
    with open(emb_path, encoding="utf-8") as f:
        data = json.load(f)

    docs = []
    for item in data[:limit]:
        emb = item.get("description_en_embedding")
        if not emb:
            continue
        overview_text = item.get("description_en", "")
        doc = {
            "id": int(item["movieId"]),
            "title": item["title"],
            "overview": overview_text,
            "overview_semantic": overview_text,
            "overview_embedding": emb,
            "genres": item["genres"].split("|") if item.get("genres") else [],
            "vote_average": float(item.get("vote_average", 0)) if item.get("vote_average") else 6.0,
        }
        docs.append(doc)

    print(f"  Prepared {len(docs)} documents")
    return docs


def create_index():
    """Delete and recreate the index."""
    requests.delete(f"{ES_URL}/{INDEX}", auth=ES_AUTH, verify=False, timeout=10)
    r = requests.put(
        f"{ES_URL}/{INDEX}",
        json=MAPPING,
        auth=ES_AUTH, verify=False, timeout=30,
    )
    if r.status_code in (200, 201):
        print(f"  Created index '{INDEX}'")
        return True
    print(f"  [!] Failed: {r.status_code} {r.text[:300]}")
    return False


def index_docs(docs, batch_size=5):
    """Index documents one-by-one or in small batches.

    semantic_text fields are processed at ingest, so we use small batches
    and allow longer timeouts.
    """
    loaded = 0
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        bulk_body = ""
        for doc in batch:
            bulk_body += json.dumps({"index": {"_index": INDEX, "_id": doc["id"]}}) + "\n"
            bulk_body += json.dumps(doc) + "\n"

        r = requests.post(
            f"{ES_URL}/_bulk",
            data=bulk_body,
            headers={"Content-Type": "application/x-ndjson"},
            auth=ES_AUTH, verify=False, timeout=120,
        )
        if r.status_code in (200, 201):
            result = r.json()
            if result.get("errors"):
                for item in result["items"]:
                    err = item.get("index", {}).get("error")
                    if err:
                        print(f"    Error: {err.get('reason', '')[:120]}")
            loaded += len(batch)
            print(f"  {loaded}/{len(docs)} indexed...")
        else:
            print(f"  [!] Bulk failed: {r.status_code}")

    requests.post(f"{ES_URL}/{INDEX}/_refresh", auth=ES_AUTH, verify=False)
    return loaded


def main():
    parser = argparse.ArgumentParser(description="Load movies-hybrid index")
    parser.add_argument("--limit", type=int, default=100, help="Number of docs (default: 100)")
    args = parser.parse_args()

    print(f"\n=== Creating '{INDEX}' index ({args.limit} docs) ===")
    print(f"  Dense vectors: EmbeddingGemma-300M (768-dim)")
    print(f"  Sparse vectors: ELSER via semantic_text\n")

    print("[1/4] Checking ELSER endpoint...")
    if not ensure_elser_endpoint():
        sys.exit(1)

    print("\n[2/4] Loading data...")
    docs = load_embeddings_data(args.limit)

    print("\n[3/4] Creating index...")
    if not create_index():
        sys.exit(1)

    print(f"\n[4/4] Indexing {len(docs)} docs (ELSER ingest — may take a minute)...")
    t0 = time.time()
    loaded = index_docs(docs)
    elapsed = time.time() - t0

    print(f"\n  Done! {loaded} docs in {elapsed:.0f}s")
    print(f"\nTry in Kibana Dev Tools:")
    print(f"  GET /{INDEX}/_count")
    print(f"  # BM25 (text search)")
    print(f"  GET /{INDEX}/_search")
    print(f'  {{ "query": {{ "multi_match": {{ "query": "space adventure", "fields": ["title^3","overview"] }} }} }}')
    print(f"  # Semantic (ELSER)")
    print(f"  GET /{INDEX}/_search")
    print(f'  {{ "query": {{ "semantic": {{ "field": "overview_semantic", "query": "animated kids adventure" }} }} }}')
    print(f"  # kNN (dense vector)")
    print(f"  # Use overview_embedding field with knn query")
    print(f"  # Three-way hybrid RRF: combines all three retrievers")


if __name__ == "__main__":
    main()
