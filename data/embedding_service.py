#!/usr/bin/env python3
"""
Embedding Service — FastAPI wrapper around EmbeddingGemma-300M.

Provides a simple HTTP API for generating 768-dim embeddings at query time.
Run this on the instructor machine so students can encode arbitrary text
without installing sentence-transformers locally.

Prerequisites:
    pip install fastapi uvicorn sentence-transformers

Usage:
    python data/embedding_service.py
    # or with custom port:
    EMBED_PORT=8080 python data/embedding_service.py

API:
    GET  /embed?text=space+adventure
    POST /embed  {"text": "space adventure"}
    POST /embed  {"texts": ["space adventure", "romantic comedy"]}
    GET  /health
"""

import os
import sys
import time

from fastapi import FastAPI, Query
from pydantic import BaseModel

EMBEDDING_MODEL = "google/embeddinggemma-300m"
app = FastAPI(title="Embedding Service", version="1.0")

_encoder = None


def get_encoder():
    global _encoder
    if _encoder is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            print("[!] pip install sentence-transformers")
            sys.exit(1)
        print(f"Loading {EMBEDDING_MODEL}...")
        _encoder = SentenceTransformer(EMBEDDING_MODEL)
        print("Model ready!")
    return _encoder


class EmbedRequest(BaseModel):
    text: str | None = None
    texts: list[str] | None = None


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    dims: int
    model: str
    took_ms: int


@app.on_event("startup")
async def startup():
    get_encoder()


@app.get("/health")
def health():
    return {"status": "ok", "model": EMBEDDING_MODEL, "dims": 768}


@app.get("/embed")
def embed_get(text: str = Query(..., description="Text to encode")):
    start = time.time()
    vec = get_encoder().encode(text).tolist()
    took = int((time.time() - start) * 1000)
    return EmbedResponse(
        embeddings=[vec], dims=len(vec), model=EMBEDDING_MODEL, took_ms=took
    )


@app.post("/embed")
def embed_post(req: EmbedRequest):
    if req.texts:
        inputs = req.texts
    elif req.text:
        inputs = [req.text]
    else:
        return {"error": "Provide 'text' or 'texts'"}

    start = time.time()
    vecs = get_encoder().encode(inputs)
    took = int((time.time() - start) * 1000)
    return EmbedResponse(
        embeddings=[v.tolist() for v in vecs],
        dims=len(vecs[0]),
        model=EMBEDDING_MODEL,
        took_ms=took,
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("EMBED_PORT", "8000"))
    print(f"Starting embedding service on http://0.0.0.0:{port}")
    print(f"  GET  http://localhost:{port}/embed?text=space+adventure")
    print(f"  POST http://localhost:{port}/embed")
    print(f"  GET  http://localhost:{port}/health")
    uvicorn.run(app, host="0.0.0.0", port=port)
