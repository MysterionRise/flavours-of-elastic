#!/usr/bin/env python3
"""
RAG Stage 3: Hybrid Search (BM25 + kNN via RRF) + Chat History

The full-featured RAG chatbot combining:
- BM25 text search for keyword matching
- kNN vector search for semantic matching
- RRF (Reciprocal Rank Fusion) to merge results
- Conversation history for multi-turn chat

Prerequisites:
    pip install requests sentence-transformers
    export OPENROUTER_API_KEY="sk-or-..."
    python data/load_data.py --dataset movies --with-embeddings

Usage:
    python data/rag_stage3_hybrid.py
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
OPENROUTER_API_KEY = os.getenv(
    "OPENROUTER_API_KEY",
    "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",
)
LLM_MODEL = os.getenv("LLM_MODEL", "google/gemini-2.0-flash-001")
EMBEDDING_MODEL = "google/embeddinggemma-300m"
TOP_K = 10
MAX_HISTORY = 6  # Keep last N messages in conversation

# --- Embedding Model ---
_encoder = None


def get_encoder():
    """Lazy-load the sentence-transformers model."""
    global _encoder
    if _encoder is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            print(
                "[!] sentence-transformers required: pip install sentence-transformers"
            )
            sys.exit(1)
        print(f"  Loading embedding model: {EMBEDDING_MODEL}...")
        _encoder = SentenceTransformer(EMBEDDING_MODEL)
        print("  Model loaded!\n")
    return _encoder


def encode_query(text):
    """Encode a text query into a 768-dim embedding vector."""
    model = get_encoder()
    return model.encode(text).tolist()


def search_movies_hybrid(query_text, top_k=TOP_K):
    """Retrieve movies using hybrid BM25 + kNN with RRF."""
    query_vector = encode_query(query_text)

    body = {
        "retriever": {
            "rrf": {
                "retrievers": [
                    {
                        "standard": {
                            "query": {
                                "multi_match": {
                                    "query": query_text,
                                    "fields": ["title", "overview", "genres"],
                                }
                            }
                        }
                    },
                    {
                        "knn": {
                            "field": "overview_embedding",
                            "query_vector": query_vector,
                            "k": top_k,
                            "num_candidates": top_k * 10,
                        }
                    },
                    {
                        "standard": {
                            "query": {
                                "semantic": {
                                    "field": "overview_semantic",
                                    "query": query_text,
                                }
                            }
                        }
                    },
                ],
                "rank_window_size": 50,
                "rank_constant": 60,
            }
        },
        "_source": ["title", "overview", "genres", "vote_average"],
        "size": top_k,
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
            "vote_average": h["_source"].get("vote_average", 0),
            "score": h.get("_score", 0),
        }
        for h in hits
    ]


def format_context(movies):
    """Format retrieved movies into context string for the LLM."""
    if not movies:
        return "No relevant movies found."
    parts = []
    for i, m in enumerate(movies, 1):
        genres = (
            ", ".join(m["genres"]) if isinstance(m["genres"], list) else m["genres"]
        )
        rating = m.get("vote_average", "N/A")
        parts.append(
            f"{i}. **{m['title']}** ({genres}, rating: {rating})\n"
            f"   {m['overview'][:400]}"
        )
    return "\n\n".join(parts)


def ask_llm(question, context, history):
    """Send question + context + history to OpenRouter LLM."""
    if not OPENROUTER_API_KEY:
        return "[Error] Set OPENROUTER_API_KEY environment variable."

    system_prompt = (
        "You are a movie expert chatbot powered by a hybrid search engine. "
        "Use the provided movie context to answer questions. "
        "If the context doesn't contain relevant information, say so. "
        "Be concise, helpful, and conversational. "
        "Mention specific movie titles and details when relevant. "
        "You can reference previous messages in the conversation."
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history
    for msg in history:
        messages.append(msg)

    # Add current turn with context
    user_prompt = (
        f"[Retrieved movies via hybrid search (BM25 + kNN + RRF)]:\n{context}\n\n"
        f"User question: {question}"
    )
    messages.append({"role": "user", "content": user_prompt})

    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": LLM_MODEL,
            "messages": messages,
            "max_tokens": 600,
            "temperature": 0.7,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def main():
    print("=" * 60)
    print("  Movie Chatbot — RAG Stage 3 (Hybrid RRF + Chat History)")
    print("=" * 60)
    print(f"  ES: {ES_URL}/{ES_INDEX}")
    print(f"  LLM: {LLM_MODEL}")
    print(f"  Embeddings: {EMBEDDING_MODEL} (768-dim)")
    print(f"  Retrieval: Hybrid BM25 + kNN via RRF (top {TOP_K})")
    print(f"  History: last {MAX_HISTORY} messages")
    print("  Type 'quit' to exit, 'clear' to reset history\n")

    if not OPENROUTER_API_KEY:
        print("[!] Warning: OPENROUTER_API_KEY not set. LLM calls will fail.")
        print("    export OPENROUTER_API_KEY='sk-or-...'\n")

    # Pre-load embedding model
    get_encoder()

    history = []

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
        if question.lower() == "clear":
            history.clear()
            print("  [History cleared]\n")
            continue

        # Step 1: Hybrid retrieve
        movies = search_movies_hybrid(question)
        context = format_context(movies)
        print(context)

        # Step 2: Generate with history
        print(f"\n  [Hybrid search: {len(movies)} movies retrieved]")
        answer = ask_llm(question, context, history)
        print(f"\nBot: {answer}\n")

        # Step 3: Update history (keep it bounded)
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})
        if len(history) > MAX_HISTORY:
            history = history[-MAX_HISTORY:]


if __name__ == "__main__":
    main()
