"""Search client for the demo and the evaluation: BM25, dense, hybrid and ELSER.

The connection comes from search/config.py (environment from
`scripts.with_stack`, or auto-detection). Hybrid search uses the
server-side `rrf` retriever where the licence allows it and fuses the BM25
and kNN rankings client-side otherwise, so it also works on a basic licence
and on OpenSearch. Query vectors use the embedder recorded in the index
`_meta` (search/embedders.py).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from search import queries
from search.capabilities import Capabilities, detect
from search.config import Target, resolve
from search.connection import Client
from search.embedders import Embedder, for_index

INDICES = {
    "bm25": "movies",
    "dense": "movies-embeddings",
    "hybrid_rrf": "movies-embeddings",
    "elser": "movies-semantic",
}


@dataclass
class SearchResponse:
    mode: str
    query: str
    hits: List[Dict]
    took_ms: float
    engine_took_ms: Optional[int] = None
    fusion: Optional[str] = None  # hybrid only: "server" (rrf retriever) or "client"


class PortfolioSearchClient:
    """Query BM25, dense vector, hybrid and ELSER search modes."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        auth: Optional[Tuple[str, str]] = None,
        verify_ssl: Optional[bool] = None,
        target: Optional[Target] = None,
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
        self._caps: Optional[Capabilities] = None
        self._embedders: Dict[str, Embedder] = {}

    @property
    def caps(self) -> Capabilities:
        if self._caps is None:
            self._caps = detect(self.http)
        return self._caps

    def modes(self) -> List[str]:
        """The modes this cluster supports (ELSER only when its index exists)."""
        available = ["bm25"]
        if self.caps.vectors:
            available += ["dense", "hybrid_rrf"]
        if self.caps.ml and self.http.exists(f"/{INDICES['elser']}"):
            available.append("elser")
        return available

    def embedder(self, index: str) -> Embedder:
        if index not in self._embedders:
            self._embedders[index] = for_index(self.http, index)
        return self._embedders[index]

    def search(
        self,
        query: str,
        mode: str = "bm25",
        index: Optional[str] = None,
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
        if mode == "dense":
            return self.search_dense(query, index, k, num_candidates)
        if mode == "hybrid_rrf":
            return self.search_hybrid_rrf(
                query, index, k, num_candidates, rank_constant
            )
        return self._run(index, queries.semantic(query, k), mode, query)

    def search_bm25(
        self, query: str, index: str = "movies", k: int = 10
    ) -> SearchResponse:
        return self.search(query, "bm25", index, k)

    def search_dense(
        self,
        query: str,
        index: str = "movies-embeddings",
        k: int = 10,
        num_candidates: int = 50,
    ) -> SearchResponse:
        vector = self.embedder(index).embed(query)
        body = queries.dense(vector, k, num_candidates, self.caps.distribution)
        return self._run(index, body, "dense", query)

    def search_hybrid_rrf(
        self,
        query: str,
        index: str = "movies-embeddings",
        k: int = 10,
        num_candidates: int = 50,
        rank_constant: int = 60,
    ) -> SearchResponse:
        vector = self.embedder(index).embed(query)
        if self.caps.rrf:
            body = queries.rrf(query, vector, k, num_candidates, rank_constant)
            response = self._run(index, body, "hybrid_rrf", query)
            response.fusion = "server"
            return response
        return self._client_rrf(query, vector, index, k, num_candidates, rank_constant)

    def search_elser(
        self, query: str, index: str = "movies-semantic", k: int = 10
    ) -> SearchResponse:
        return self.search(query, "elser", index, k)

    def _client_rrf(
        self,
        query: str,
        vector: List[float],
        index: str,
        k: int,
        num_candidates: int,
        rank_constant: int,
    ) -> SearchResponse:
        window = max(num_candidates, k)
        start = time.perf_counter()
        lexical = self.http.post(f"/{index}/_search", queries.bm25(query, window))
        semantic = self.http.post(
            f"/{index}/_search",
            queries.dense(vector, window, window, self.caps.distribution),
        )
        rankings, sources = [], {}
        for payload in (lexical, semantic):
            hits = payload.get("hits", {}).get("hits", [])
            rankings.append([hit["_id"] for hit in hits])
            for hit in hits:
                sources.setdefault(hit["_id"], hit)
        fused = queries.rrf_fuse(rankings, rank_constant, k)
        hits = [{**sources[doc_id], "_score": score} for doc_id, score in fused]
        return SearchResponse(
            mode="hybrid_rrf",
            query=query,
            hits=to_hits(hits),
            took_ms=(time.perf_counter() - start) * 1000,
            engine_took_ms=lexical.get("took", 0) + semantic.get("took", 0),
            fusion="client",
        )

    def cluster_info(self) -> Dict:
        return self.http.get("/")

    def count(self, index: str) -> int:
        return self.http.get(f"/{index}/_count")["count"]

    def ids_present(self, index: str, ids: List[int]) -> set:
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

    def _run(self, index: str, body: Dict, mode: str, query: str) -> SearchResponse:
        start = time.perf_counter()
        payload = self.http.post(f"/{index}/_search", body)
        return SearchResponse(
            mode=mode,
            query=query,
            hits=to_hits(payload.get("hits", {}).get("hits", [])),
            took_ms=(time.perf_counter() - start) * 1000,
            engine_took_ms=payload.get("took"),
        )


def to_hits(raw_hits: List[Dict]) -> List[Dict]:
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
