"""Embed queries with the same model as the documents of an index.

The loader records the embedding backend, model and dims in the index
`_meta` (search/mappings.py). Queries must be embedded the same way, or kNN
silently returns nonsense; so the embedder is chosen from that record, and
an index without it, or embedded with another model, is refused.

`hash` vectors are computed by the client; `e5` vectors by the cluster, so
the query carries a `query_vector_builder` instead of a vector.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Union

from search.connection import Client
from search.embeddings import (
    DEFAULT_EMBEDDING_DIMS,
    HASH_MODEL,
    deterministic_text_embedding,
)
from search.inference import E5, E5_DIMS

RELOAD = "reload it with `python data/load_data.py --embeddings hash` (or `e5`)"


class EmbedderMismatch(RuntimeError):
    """No query embedder matches how the index was embedded."""


@dataclass(frozen=True)
class Embedder:
    backend: str
    model: str
    dims: int
    embed: Optional[Callable[[str], List[float]]]  # None: embedded in the cluster

    def query_vector(self, text: str) -> Union[List[float], Dict]:
        """A vector, or a `query_vector_builder` that lets the cluster embed the text."""
        if self.embed is None:
            return {"text_embedding": {"model_id": self.model, "model_text": text}}
        return self.embed(text)


HASH = Embedder(
    "hash", HASH_MODEL, DEFAULT_EMBEDDING_DIMS, deterministic_text_embedding
)
E5_IN_CLUSTER = Embedder("e5", E5, E5_DIMS, None)
KNOWN = {embedder.backend: embedder for embedder in (HASH, E5_IN_CLUSTER)}


def index_meta(client: Client, index: str) -> dict:
    """The loader's `_meta.foe` record of an index ({} when there is none)."""
    mapping = client.get(f"/{index}/_mapping")
    meta = next(iter(mapping.values()), {}).get("mappings", {}).get("_meta") or {}
    return meta.get("foe") or {}


def for_meta(meta: dict | None, index: str) -> Embedder:
    if not meta:
        raise EmbedderMismatch(f"'{index}' has no embedding metadata: {RELOAD}")
    known = KNOWN.get(meta.get("backend"))
    if known is None:
        raise EmbedderMismatch(
            f"'{index}' was embedded with {meta.get('backend')}/{meta.get('model')},"
            " which this client cannot embed queries with"
        )
    if (meta.get("model"), meta.get("dims")) != (known.model, known.dims):
        raise EmbedderMismatch(
            f"'{index}' was embedded with {meta.get('model')} ({meta.get('dims')} dims),"
            f" but queries are embedded with {known.model} ({known.dims} dims): {RELOAD}"
        )
    return known


def for_index(client: Client, index: str) -> Embedder:
    return for_meta(index_meta(client, index).get("embedding"), index)
