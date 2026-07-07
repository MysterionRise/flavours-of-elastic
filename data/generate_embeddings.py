#!/usr/bin/env python3
"""
Generate model-backed movie embeddings for the portfolio search demo.

Default path:
    all-MiniLM-L6-v2 -> 384-dim overview_embedding

Advanced path:
    --advanced-multilingual with a 768-dim-capable model can generate embeddings
    for all multilingual abstract/description fields.
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from data.load_data import normalize_movie  # noqa: E402

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MULTILINGUAL_FIELDS = [
    "abstract_en",
    "abstract_kk",
    "abstract_fr",
    "description_en",
    "description_kk",
    "description_fr",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Generate movie embeddings")
    parser.add_argument("--input", default="data/movies_enriched.csv")
    parser.add_argument("--output", default="data/movies_enriched_with_embeddings.json")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--limit", type=int, default=0, help="Limit rows, 0 means all")
    parser.add_argument(
        "--advanced-multilingual",
        action="store_true",
        help="Generate embeddings for all multilingual text fields instead of only overview_embedding",
    )
    return parser.parse_args()


def read_rows(path, limit):
    rows = []
    with open(path, newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            rows.append(row)
            if limit and len(rows) >= limit:
                break
    return rows


def load_model(model_name):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print(
            "Error: sentence-transformers required for model-backed embeddings. "
            "Install ML extras with: pip install -r requirements-ml.txt"
        )
        sys.exit(1)
    return SentenceTransformer(model_name)


def encode(model, texts, batch_size):
    embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=True)
    return [embedding.tolist() for embedding in embeddings]


def main():
    args = parse_args()
    start = time.time()

    print(f"Reading {args.input}...")
    rows = read_rows(args.input, args.limit)
    print(f"  Loaded {len(rows)} movies")

    print(f"Loading model: {args.model}")
    model = load_model(args.model)

    docs = [normalize_movie(row, with_embeddings=False) for row in rows]

    if args.advanced_multilingual:
        for field in MULTILINGUAL_FIELDS:
            print(f"Encoding {field}...")
            values = [doc.get(field, "") for doc in docs]
            embeddings = encode(model, values, args.batch_size)
            for doc, embedding in zip(docs, embeddings):
                doc[f"{field}_embedding"] = embedding
    else:
        print("Encoding overview_embedding...")
        values = [doc["searchable_text"] for doc in docs]
        embeddings = encode(model, values, args.batch_size)
        for doc, embedding in zip(docs, embeddings):
            doc["overview_embedding"] = embedding

    print(f"Writing {args.output}...")
    with open(args.output, "w", encoding="utf-8") as output_file:
        json.dump(docs, output_file, ensure_ascii=False)

    print(f"Done in {time.time() - start:.1f}s")


if __name__ == "__main__":
    main()
