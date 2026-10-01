"""Search request bodies for each retrieval mode (pure functions, no I/O).

- `bm25`: multi_match over the English fields plus the French and Kazakh
  abstracts/descriptions, so non-English queries find their movie too.
- `dense`: approximate kNN on `overview_embedding` — the top-level `knn`
  option on Elasticsearch, the `knn` query on OpenSearch. `size` is always
  set: without it Elasticsearch returns 10 hits whatever `k` is.
- `rrf`: the server-side `rrf` retriever (Elasticsearch 8.14+, enterprise or
  trial licence). Both legs look at `rank_window_size` candidates.
- `rrf_all`: three-way rrf — BM25, kNN and ELSER (`semantic` query).
- `rrf_fuse`: the same Reciprocal Rank Fusion done client-side, for clusters
  without the retriever (basic licence, OpenSearch).

A query vector is either a list of floats (embedded by the client) or a
`query_vector_builder` dict (embedded in the cluster, e.g. by E5).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from search.mappings import SEMANTIC_FIELD, VECTOR_FIELD

QueryVector = list[float] | dict  # a vector, or a query_vector_builder

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


def multi_match(query: str) -> dict:
    return {"multi_match": {"query": query, "fields": BM25_FIELDS}}


def bm25(query: str, size: int) -> dict:
    return {"size": size, "query": multi_match(query), "_source": SOURCE_FIELDS}


def knn_clause(vector: QueryVector, k: int, num_candidates: int) -> dict:
    key = "query_vector_builder" if isinstance(vector, dict) else "query_vector"
    return {
        "field": VECTOR_FIELD,
        key: vector,
        "k": k,
        "num_candidates": num_candidates,
    }


def dense(vector: QueryVector, k: int, num_candidates: int, distribution: str) -> dict:
    candidates = max(num_candidates, k)
    if distribution == "opensearch":
        query = {"knn": {VECTOR_FIELD: {"vector": vector, "k": candidates}}}
        return {"size": k, "query": query, "_source": SOURCE_FIELDS}
    knn = knn_clause(vector, k, candidates)
    return {"size": k, "knn": knn, "_source": SOURCE_FIELDS}


def rrf(
    query: str,
    vector: QueryVector,
    k: int,
    num_candidates: int,
    rank_constant: int,
    with_semantic: bool = False,
) -> dict:
    window = max(num_candidates, k)
    retrievers = [
        {"standard": {"query": multi_match(query)}},
        {"knn": knn_clause(vector, window, window)},
    ]
    if with_semantic:
        retrievers.append({"standard": {"query": semantic_query(query)}})
    retriever = {
        "rrf": {
            "rank_constant": rank_constant,
            "rank_window_size": window,
            "retrievers": retrievers,
        }
    }
    return {"size": k, "retriever": retriever, "_source": SOURCE_FIELDS}


def rrf_all(
    query: str, vector: QueryVector, k: int, num_candidates: int, rank_constant: int
) -> dict:
    return rrf(query, vector, k, num_candidates, rank_constant, with_semantic=True)


def semantic_query(query: str, field: str = SEMANTIC_FIELD) -> dict:
    return {"semantic": {"field": field, "query": query}}


def semantic(query: str, size: int, field: str = SEMANTIC_FIELD) -> dict:
    return {
        "size": size,
        "query": semantic_query(query, field),
        "_source": SOURCE_FIELDS,
    }


def rrf_fuse(
    rankings: Iterable[Sequence[str]], rank_constant: int, size: int
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: score(d) = sum over rankings of 1 / (rank_constant + rank)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (rank_constant + rank)
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return ordered[:size]
