#!/usr/bin/env python3
"""
Generate embeddings for multilingual movie text fields using EmbeddingGemma-300M.

Reads data/movies_enriched.csv and produces data/movies_enriched_with_embeddings.json
with 768-dim embeddings for each of the 6 text fields.

Requires:
    pip install sentence-transformers
    export HF_TOKEN="hf_..."  (must accept license at huggingface.co/google/embeddinggemma-300m)

Usage:
    python data/generate_embeddings.py [OPTIONS]

Options:
    --input       Input CSV path   (default: data/movies_enriched.csv)
    --output      Output JSON path (default: data/movies_enriched_with_embeddings.json)
    --batch-size  Encoding batch   (default: 64)
"""

import argparse
import csv
import json
import sys
import time

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print(
        "Error: sentence-transformers required. Install with: pip install sentence-transformers"
    )
    sys.exit(1)


TEXT_FIELDS = [
    "abstract_en",
    "abstract_kk",
    "abstract_fr",
    "description_en",
    "description_kk",
    "description_fr",
]

CSV_FIELDS = ["movieId", "title", "genres"] + TEXT_FIELDS


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate embeddings for movie text fields"
    )
    parser.add_argument(
        "--input",
        default="data/movies_enriched.csv",
        help="Input CSV path (default: data/movies_enriched.csv)",
    )
    parser.add_argument(
        "--output",
        default="data/movies_enriched_with_embeddings.json",
        help="Output JSON path (default: data/movies_enriched_with_embeddings.json)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Batch size for encoding (default: 64)",
    )
    return parser.parse_args()


def read_movies(path):
    movies = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            movies.append(row)
    return movies


def main():
    args = parse_args()

    print(f"Reading {args.input}...")
    movies = read_movies(args.input)
    print(f"  Loaded {len(movies)} movies")

    print("Loading EmbeddingGemma-300M model...")
    model = SentenceTransformer("google/embeddinggemma-300m")
    print("  Model loaded")

    start = time.time()

    for field in TEXT_FIELDS:
        print(f"Encoding {field}...")
        texts = [m.get(field, "") or "" for m in movies]
        embeddings = model.encode(
            texts, batch_size=args.batch_size, show_progress_bar=True
        )
        for i, emb in enumerate(embeddings):
            movies[i][f"{field}_embedding"] = emb.tolist()
        elapsed = time.time() - start
        print(f"  {field} done ({elapsed:.1f}s elapsed)")

    # Build output docs
    docs = []
    for m in movies:
        doc = {}
        for f in CSV_FIELDS:
            doc[f] = m.get(f, "")
        for f in TEXT_FIELDS:
            doc[f"{f}_embedding"] = m[f"{f}_embedding"]
        docs.append(doc)

    print(f"Writing {args.output}...")
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False)

    elapsed = time.time() - start
    print(f"Done! {len(docs)} movies with embeddings in {elapsed:.1f}s")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
