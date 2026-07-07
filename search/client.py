"""Small requests-based Elasticsearch client for the portfolio demo."""

import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests

from search.embeddings import deterministic_text_embedding

DEFAULT_SOURCE_FIELDS = [
    "id",
    "title",
    "title_raw",
    "year",
    "release_date",
    "genres",
    "overview",
    "description_en",
]


@dataclass
class SearchResponse:
    mode: str
    query: str
    hits: List[Dict]
    took_ms: float
    engine_took_ms: Optional[int] = None


def auth_from_env() -> Optional[Tuple[str, str]]:
    """Return basic auth credentials from local environment."""
    user = os.getenv("ELASTIC_USER", "elastic")
    password = os.getenv("ELASTIC_PASSWORD", "elastic")
    if os.getenv("ELASTIC_NO_AUTH", "").lower() in ["1", "true", "yes"]:
        return None
    return user, password


class PortfolioSearchClient:
    """Query BM25, dense vector, and hybrid search modes."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        auth: Optional[Tuple[str, str]] = None,
        verify_ssl: Optional[bool] = None,
    ):
        self.base_url = (
            base_url or os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
        ).rstrip("/")
        self.auth = auth if auth is not None else auth_from_env()
        self.verify_ssl = (
            verify_ssl
            if verify_ssl is not None
            else os.getenv("ELASTIC_VERIFY_SSL", "false").lower() == "true"
        )

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
        if mode == "bm25":
            return self.search_bm25(query, index or "movies", k)
        if mode == "dense":
            return self.search_dense(
                query, index or "movies-embeddings", k, num_candidates
            )
        if mode == "hybrid_rrf":
            return self.search_hybrid_rrf(
                query, index or "movies-embeddings", k, num_candidates, rank_constant
            )
        if mode == "elser":
            return self.search_elser(query, index or "movies-semantic", k)
        raise ValueError(f"Unsupported search mode: {mode}")

    def search_bm25(
        self, query: str, index: str = "movies", k: int = 10
    ) -> SearchResponse:
        body = {
            "size": k,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title^4", "overview^3", "description_en^2", "genres"],
                }
            },
            "_source": DEFAULT_SOURCE_FIELDS,
        }
        return self._post_search(index, body, "bm25", query)

    def search_dense(
        self,
        query: str,
        index: str = "movies-embeddings",
        k: int = 10,
        num_candidates: int = 50,
    ) -> SearchResponse:
        body = {
            "knn": {
                "field": "overview_embedding",
                "query_vector": deterministic_text_embedding(query),
                "k": k,
                "num_candidates": max(num_candidates, k),
            },
            "_source": DEFAULT_SOURCE_FIELDS,
        }
        return self._post_search(index, body, "dense", query)

    def search_hybrid_rrf(
        self,
        query: str,
        index: str = "movies-embeddings",
        k: int = 10,
        num_candidates: int = 50,
        rank_constant: int = 60,
    ) -> SearchResponse:
        body = {
            "size": k,
            "retriever": {
                "rrf": {
                    "rank_constant": rank_constant,
                    "rank_window_size": max(num_candidates, k),
                    "retrievers": [
                        {
                            "standard": {
                                "query": {
                                    "multi_match": {
                                        "query": query,
                                        "fields": [
                                            "title^4",
                                            "overview^3",
                                            "description_en^2",
                                            "genres",
                                        ],
                                    }
                                }
                            }
                        },
                        {
                            "knn": {
                                "field": "overview_embedding",
                                "query_vector": deterministic_text_embedding(query),
                                "k": k,
                                "num_candidates": max(num_candidates, k),
                            }
                        },
                    ],
                }
            },
            "_source": DEFAULT_SOURCE_FIELDS,
        }
        return self._post_search(index, body, "hybrid_rrf", query)

    def search_elser(
        self, query: str, index: str = "movies-semantic", k: int = 10
    ) -> SearchResponse:
        body = {
            "size": k,
            "query": {
                "semantic": {
                    "field": "overview_semantic",
                    "query": query,
                }
            },
            "_source": DEFAULT_SOURCE_FIELDS,
        }
        return self._post_search(index, body, "elser", query)

    def cluster_info(self) -> Dict:
        response = requests.get(
            self.base_url,
            auth=self.auth,
            verify=self.verify_ssl,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def count(self, index: str) -> int:
        response = requests.get(
            f"{self.base_url}/{index}/_count",
            auth=self.auth,
            verify=self.verify_ssl,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["count"]

    def index_size_bytes(self, index: str) -> int:
        response = requests.get(
            f"{self.base_url}/{index}/_stats/store",
            auth=self.auth,
            verify=self.verify_ssl,
            timeout=10,
        )
        response.raise_for_status()
        stats = response.json()
        return int(stats["indices"][index]["total"]["store"]["size_in_bytes"])

    def _post_search(
        self, index: str, body: Dict, mode: str, query: str
    ) -> SearchResponse:
        start = time.perf_counter()
        response = requests.post(
            f"{self.base_url}/{index}/_search",
            json=body,
            auth=self.auth,
            verify=self.verify_ssl,
            timeout=30,
            headers={"Content-Type": "application/json"},
        )
        took_ms = (time.perf_counter() - start) * 1000
        response.raise_for_status()
        payload = response.json()
        hits = []
        for rank, hit in enumerate(payload.get("hits", {}).get("hits", []), start=1):
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
        return SearchResponse(
            mode=mode,
            query=query,
            hits=hits,
            took_ms=took_ms,
            engine_took_ms=payload.get("took"),
        )
