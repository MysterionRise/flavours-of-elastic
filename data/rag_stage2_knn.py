#!/usr/bin/env python3
"""
RAG Stage 2: kNN Vector Search + OpenRouter LLM

Builds on Stage 1 by adding semantic vector search using sentence-transformers
to encode user queries at runtime, then kNN search against pre-indexed embeddings.

Prerequisites:
    pip install requests sentence-transformers
    export OPENROUTER_API_KEY="sk-or-..."
    python data/load_data.py --dataset movies --with-embeddings

Usage:
    python data/rag_stage2_knn.py
"""

import json
import os
import sys

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# --- Configuration ---
ES_URL = os.getenv("ELASTICSEARCH_URL", "https://localhost:9200")
ES_AUTH = ("elastic", "elastic")
ES_INDEX = "movies-hybrid"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")
LLM_MODEL = os.getenv("LLM_MODEL", "google/gemini-2.0-flash-001")
EMBEDDING_MODEL = "google/embeddinggemma-300m"
TOP_K = 5

# --- Embedding Model (loaded once) ---
_encoder = None


def get_encoder():
    """Lazy-load the sentence-transformers model."""
    global _encoder
    if _encoder is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            print("[!] sentence-transformers required: pip install sentence-transformers")
            sys.exit(1)
        print(f"  Loading embedding model: {EMBEDDING_MODEL}...")
        _encoder = SentenceTransformer(EMBEDDING_MODEL)
        print("  Model loaded!\n")
    return _encoder


def encode_query(text):
    """Encode a text query into a 768-dim embedding vector."""
    model = get_encoder()
    embedding = model.encode(text)
    return embedding.tolist()


def search_movies_knn(query_text, top_k=TOP_K):
    """Retrieve movies using kNN vector search."""
    query_vector = encode_query(query_text)

    body = {
        "knn": {
            "field": "overview_embedding",
            "query_vector": query_vector,
            "k": top_k,
            "num_candidates": top_k * 10,
        },
        "_source": ["title", "overview", "genres", "vote_average"],
    }
    resp = requests.post(
        f"{ES_URL}/{ES_INDEX}/_search",
        json=body,
        auth=ES_AUTH,
        verify=False,
        timeout=10,
    )
    resp.raise_for_status()
    hits = resp.json().get("hits", {}).get("hits", [])
    return [
        {
            "title": h["_source"]["title"],
            "overview": h["_source"].get("overview", ""),
            "genres": h["_source"].get("genres", []),
            "rating": h["_source"].get("vote_average", []),
            "score": h["_score"],
        }
        for h in hits
    ]


def format_context(movies):
    """Format retrieved movies into context string for the LLM."""
    if not movies:
        return "No relevant movies found."
    parts = []
    for i, m in enumerate(movies, 1):
        genres = ", ".join(m["genres"]) if isinstance(m["genres"], list) else m["genres"]
        parts.append(
            f"{i}. **{m['title']}** ({genres})\n   {m['overview'][:300]}"
        )
        parts.append(m["overview"][:500])
    return "\n\n".join(parts)


def ask_llm(question, context):
    """Send question + context to OpenRouter LLM."""
    if not OPENROUTER_API_KEY:
        return "[Error] Set OPENROUTER_API_KEY environment variable."

    print(context)
    system_prompt = (
        "You are a movie expert chatbot. Use ONLY the provided movie context "
        "to answer questions. If the context doesn't contain relevant information, "
        "say so. Be concise and helpful. Mention specific movie titles when relevant."
    )
    user_prompt = (
        f"Context (retrieved movies via semantic vector search):\n{context}\n\n"
        f"User question: {question}"
    )

    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 2000,
            "temperature": 0.5,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def main():
    print("=" * 60)
    print("  Movie Chatbot — RAG Stage 2 (kNN Vector + OpenRouter)")
    print("=" * 60)
    print(f"  ES: {ES_URL}/{ES_INDEX}")
    print(f"  LLM: {LLM_MODEL}")
    print(f"  Embeddings: {EMBEDDING_MODEL} (768-dim)")
    print(f"  Retrieval: kNN vector search (top {TOP_K})")
    print("  Type 'quit' to exit\n")

    if not OPENROUTER_API_KEY:
        print("[!] Warning: OPENROUTER_API_KEY not set. LLM calls will fail.")
        print("    export OPENROUTER_API_KEY='sk-or-...'\n")

    # Pre-load embedding model
    get_encoder()

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break

        # Step 1: Encode query + kNN retrieve
        movies = search_movies_knn(question)
        context = format_context(movies)

        # Step 2: Generate
        print(f"\n  [Retrieved {len(movies)} movies via kNN vector search]")
        answer = ask_llm(question, context)
        print(f"\nBot: {answer}\n")


if __name__ == "__main__":
    main()
