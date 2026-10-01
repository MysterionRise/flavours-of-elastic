"""Embed queries with the same model as the documents of an index.

The loader records the embedding backend, model and dims in the index
`_meta` (search/mappings.py). Queries must be embedded the same way, or kNN
silently returns nonsense; so the embedder is chosen from that record, and
an index without it, or embedded with another model, is refused.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

from search.connection import Client
from search.embeddings import (
    DEFAULT_EMBEDDING_DIMS,
    HASH_MODEL,
    deterministic_text_embedding,
)

RELOAD = "reload it with `python data/load_data.py --embeddings hash`"


class EmbedderMismatch(RuntimeError):
    """No query embedder matches how the index was embedded."""


@dataclass(frozen=True)
class Embedder:
    backend: str
    model: str
    dims: int
    embed: Callable[[str], List[float]]


HASH = Embedder(
    "hash", HASH_MODEL, DEFAULT_EMBEDDING_DIMS, deterministic_text_embedding
)


def embedding_meta(client: Client, index: str) -> dict | None:
    mapping = client.get(f"/{index}/_mapping")
    meta = next(iter(mapping.values()), {}).get("mappings", {}).get("_meta") or {}
    return (meta.get("foe") or {}).get("embedding")


def for_meta(meta: dict | None, index: str) -> Embedder:
    if not meta:
        raise EmbedderMismatch(f"'{index}' has no embedding metadata: {RELOAD}")
    if meta.get("backend") == "hash":
        if (meta.get("model"), meta.get("dims")) != (HASH.model, HASH.dims):
            raise EmbedderMismatch(
                f"'{index}' was embedded with {meta.get('model')} ({meta.get('dims')} dims),"
                f" but queries are embedded with {HASH.model} ({HASH.dims} dims): {RELOAD}"
            )
        return HASH
    raise EmbedderMismatch(
        f"'{index}' was embedded with {meta.get('backend')}/{meta.get('model')},"
        " which this client cannot embed queries with"
    )


def for_index(client: Client, index: str) -> Embedder:
    return for_meta(embedding_meta(client, index), index)
