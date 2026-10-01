"""Search request bodies for each retrieval mode (pure functions, no I/O).

- `bm25`: multi_match over the English fields plus the French and Kazakh
  abstracts/descriptions, so non-English queries find their movie too.
- `dense`: approximate kNN on `overview_embedding` — the top-level `knn`
  option on Elasticsearch, the `knn` query on OpenSearch. `size` is always
  set: without it Elasticsearch returns 10 hits whatever `k` is.
- `rrf`: the server-side `rrf` retriever (Elasticsearch 8.14+, enterprise or
  trial licence). Both legs look at `rank_window_size` candidates.
- `rrf_fuse`: the same Reciprocal Rank Fusion done client-side, for clusters
  without the retriever (basic licence, OpenSearch).
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Tuple

from search.mappings import VECTOR_FIELD

SOURCE_FIELDS = [
    "id",
    "title",
    "title_raw",
    "year",
    "release_date",
    "genres",
    "overview",
    "description_en",
]
BM25_FIELDS = [
    "title^4",
    "title_aka^2",
    "overview^3",
    "description_en^2",
    "genres",
    "abstract_fr",
    "description_fr",
    "abstract_kk",
    "description_kk",
]


def multi_match(query: str) -> Dict:
    return {"multi_match": {"query": query, "fields": BM25_FIELDS}}


def bm25(query: str, size: int) -> Dict:
    return {"size": size, "query": multi_match(query), "_source": SOURCE_FIELDS}


def dense(vector: List[float], k: int, num_candidates: int, distribution: str) -> Dict:
    candidates = max(num_candidates, k)
    if distribution == "opensearch":
        query = {"knn": {VECTOR_FIELD: {"vector": vector, "k": candidates}}}
        return {"size": k, "query": query, "_source": SOURCE_FIELDS}
    knn = {
        "field": VECTOR_FIELD,
        "query_vector": vector,
        "k": k,
        "num_candidates": candidates,
    }
    return {"size": k, "knn": knn, "_source": SOURCE_FIELDS}


def rrf(
    query: str,
    vector: List[float],
    k: int,
    num_candidates: int,
    rank_constant: int,
) -> Dict:
    window = max(num_candidates, k)
    knn = {
        "field": VECTOR_FIELD,
        "query_vector": vector,
        "k": window,
        "num_candidates": window,
    }
    retriever = {
        "rrf": {
            "rank_constant": rank_constant,
            "rank_window_size": window,
            "retrievers": [{"standard": {"query": multi_match(query)}}, {"knn": knn}],
        }
    }
    return {"size": k, "retriever": retriever, "_source": SOURCE_FIELDS}


def semantic(query: str, size: int, field: str = "overview_semantic") -> Dict:
    return {
        "size": size,
        "query": {"semantic": {"field": field, "query": query}},
        "_source": SOURCE_FIELDS,
    }


def rrf_fuse(
    rankings: Iterable[Sequence[str]], rank_constant: int, size: int
) -> List[Tuple[str, float]]:
    """Reciprocal Rank Fusion: score(d) = sum over rankings of 1 / (rank_constant + rank)."""
    scores: Dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (rank_constant + rank)
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return ordered[:size]
