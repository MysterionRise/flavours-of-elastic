"""Search client for the demo and the evaluation.

Modes:
- `bm25`: multi_match on `movies`;
- `dense`: kNN on `movies-embeddings` (hash vectors from the client, or E5
  vectors embedded by the cluster through `query_vector_builder`);
- `hybrid_rrf`: BM25 + kNN fused with Reciprocal Rank Fusion;
- `elser`: the `semantic` query on `overview_semantic` (ELSER);
- `hybrid_all`: BM25 + kNN + ELSER fused with RRF.

The connection comes from search/config.py (environment from
`scripts.with_stack`, or auto-detection). Fusion uses the server-side `rrf`
retriever where the licence allows it and is done client-side otherwise, so
hybrid search also works on a basic licence and on OpenSearch. Query vectors
use the embedder recorded in the index `_meta` (search/embedders.py).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from search import queries
from search.capabilities import Capabilities, detect
from search.config import Target, resolve
from search.connection import Client
from search.embedders import Embedder, for_index, index_meta

EMBEDDINGS_INDEX = "movies-embeddings"
INDICES = {
    "bm25": "movies",
    "dense": EMBEDDINGS_INDEX,
    "hybrid_rrf": EMBEDDINGS_INDEX,
    "elser": EMBEDDINGS_INDEX,
    "hybrid_all": EMBEDDINGS_INDEX,
}
VECTOR_MODES = ("dense", "hybrid_rrf", "hybrid_all")


@dataclass
class SearchResponse:
    mode: str
    query: str
    hits: list[dict]
    took_ms: float
    engine_took_ms: int | None = None
    fusion: str | None = None  # hybrid only: "server" (rrf retriever) or "client"
    embedding: str | None = None  # vector modes: the embedding backend (hash, e5)


class PortfolioSearchClient:
    """Query BM25, dense vector, hybrid and ELSER search modes."""

    def __init__(
        self,
        base_url: str | None = None,
        auth: tuple[str, str] | None = None,
        verify_ssl: bool | None = None,
        target: Target | None = None,
    ):
        if target is None:
            if base_url:
                target = Target(
                    base_url.rstrip("/"),
                    auth,
                    True if verify_ssl is None else verify_ssl,
                    "argument",
                )
            else:
                target = resolve()
        self.target = target
        self.http: Client = target.client()
        self._caps: Capabilities | None = None
        self._embedders: dict[str, Embedder] = {}
        self._meta: dict[str, dict] = {}

    @property
    def caps(self) -> Capabilities:
        if self._caps is None:
            self._caps = detect(self.http)
        return self._caps

    def meta(self, index: str) -> dict:
        if index not in self._meta:
            self._meta[index] = (
                index_meta(self.http, index) if self.http.exists(f"/{index}") else {}
            )
        return self._meta[index]

    def modes(self) -> list[str]:
        """The modes this cluster and the loaded indices support."""
        available = ["bm25"]
        if self.caps.vectors:
            available += ["dense", "hybrid_rrf"]
        if self.caps.ml and self.meta(EMBEDDINGS_INDEX).get("semantic"):
            available.append("elser")
            if self.meta(EMBEDDINGS_INDEX).get("embedding"):
                available.append("hybrid_all")
        return available

    def embedder(self, index: str) -> Embedder:
        if index not in self._embedders:
            self._embedders[index] = for_index(self.http, index)
        return self._embedders[index]

    def search(
        self,
        query: str,
        mode: str = "bm25",
        index: str | None = None,
        k: int = 10,
        num_candidates: int = 50,
        rank_constant: int = 60,
    ) -> SearchResponse:
        """Run a search in one of the supported modes."""
        if mode not in INDICES:
            raise ValueError(f"Unsupported search mode: {mode}")
        index = index or INDICES[mode]
        if mode == "bm25":
            return self._run(index, queries.bm25(query, k), mode, query)
        if mode == "elser":
            return self._run(index, queries.semantic(query, k), mode, query)
        embedder = self.embedder(index)
        vector = embedder.query_vector(query)
        if mode == "dense":
            body = queries.dense(vector, k, num_candidates, self.caps.distribution)
            response = self._run(index, body, mode, query)
        elif self.caps.rrf:
            body = queries.rrf(
                query, vector, k, num_candidates, rank_constant, mode == "hybrid_all"
            )
            response = self._run(index, body, mode, query)
            response.fusion = "server"
        else:
            window = max(num_candidates, k)
            legs = [
                queries.bm25(query, window),
                queries.dense(vector, window, window, self.caps.distribution),
            ]
            if mode == "hybrid_all":
                legs.append(queries.semantic(query, window))
            response = self._client_rrf(index, legs, mode, query, k, rank_constant)
        response.embedding = embedder.backend
        return response

    def search_bm25(
        self, query: str, index: str = "movies", k: int = 10
    ) -> SearchResponse:
        return self.search(query, "bm25", index, k)

    def search_dense(
        self,
        query: str,
        index: str = EMBEDDINGS_INDEX,
        k: int = 10,
        num_candidates: int = 50,
    ) -> SearchResponse:
        return self.search(query, "dense", index, k, num_candidates)

    def search_hybrid_rrf(
        self,
        query: str,
        index: str = EMBEDDINGS_INDEX,
        k: int = 10,
        num_candidates: int = 50,
        rank_constant: int = 60,
    ) -> SearchResponse:
        return self.search(query, "hybrid_rrf", index, k, num_candidates, rank_constant)

    def search_elser(
        self, query: str, index: str = EMBEDDINGS_INDEX, k: int = 10
    ) -> SearchResponse:
        return self.search(query, "elser", index, k)

    def _client_rrf(
        self,
        index: str,
        legs: list[dict],
        mode: str,
        query: str,
        k: int,
        rank_constant: int,
    ) -> SearchResponse:
        start = time.perf_counter()
        rankings, sources, took = [], {}, 0
        for body in legs:
            payload = self.http.post(f"/{index}/_search", body)
            took += payload.get("took", 0)
            hits = payload.get("hits", {}).get("hits", [])
            rankings.append([hit["_id"] for hit in hits])
            for hit in hits:
                sources.setdefault(hit["_id"], hit)
        fused = queries.rrf_fuse(rankings, rank_constant, k)
        hits = [{**sources[doc_id], "_score": score} for doc_id, score in fused]
        return SearchResponse(
            mode=mode,
            query=query,
            hits=to_hits(hits),
            took_ms=(time.perf_counter() - start) * 1000,
            engine_took_ms=took,
            fusion="client",
        )

    def cluster_info(self) -> dict:
        return self.http.get("/")

    def count(self, index: str) -> int:
        return self.http.get(f"/{index}/_count")["count"]

    def ids_present(self, index: str, ids: list[int]) -> set:
        """Which of these movie ids the index holds."""
        found = self.http.post(
            f"/{index}/_mget",
            {"ids": [str(i) for i in ids]},
            params={"_source": "false"},
        )
        return {int(doc["_id"]) for doc in found.get("docs", []) if doc.get("found")}

    def index_size_bytes(self, index: str) -> int:
        stats = self.http.get(f"/{index}/_stats/store")
        return int(stats["indices"][index]["total"]["store"]["size_in_bytes"])

    def _run(self, index: str, body: dict, mode: str, query: str) -> SearchResponse:
        start = time.perf_counter()
        payload = self.http.post(f"/{index}/_search", body)
        return SearchResponse(
            mode=mode,
            query=query,
            hits=to_hits(payload.get("hits", {}).get("hits", [])),
            took_ms=(time.perf_counter() - start) * 1000,
            engine_took_ms=payload.get("took"),
        )


def to_hits(raw_hits: list[dict]) -> list[dict]:
    hits = []
    for rank, hit in enumerate(raw_hits, start=1):
        source = hit.get("_source", {})
        hits.append(
            {
                "rank": rank,
                "id": int(source.get("id", hit.get("_id"))),
                "score": hit.get("_score"),
                "title": source.get("title") or source.get("title_raw"),
                "year": source.get("year"),
                "genres": source.get("genres", []),
                "overview": source.get("overview", ""),
                "description_en": source.get("description_en", ""),
            }
        )
    return hits
