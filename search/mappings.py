"""Index bodies for the movie indices, per distribution.

- `movies`: the Days 1-3 index (BM25 fields only).
- `movies-embeddings`: the same fields plus `overview_embedding`. On
  Elasticsearch it is a `dense_vector` with explicit `int8_hnsw`, so 8.19 and
  9.x (whose default for 384+ dims is `bbq_hnsw`) behave the same; on
  OpenSearch it is a `knn_vector` (Lucene HNSW, cosine).

`_meta` records what produced the index (dataset size, source checksum,
embedding backend/model/dims). The loader uses it for `--skip-if-current`, and
the search client to embed queries with the same model as the documents.
"""

from __future__ import annotations

import copy

from search.capabilities import Capabilities

MOVIES_PROPERTIES = {
    "id": {"type": "integer"},
    "movieId": {"type": "keyword"},
    "title": {
        "type": "text",
        "analyzer": "english",
        "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
    },
    "title_aka": {
        "type": "text",
        "analyzer": "english",
        "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
    },
    "title_raw": {"type": "keyword", "ignore_above": 512},
    "year": {"type": "integer"},
    "release_date": {"type": "date"},
    "genres": {"type": "keyword"},
    # MovieLens ml-32m: mean rating x 2 (1-10); absent when there are fewer than 10 votes.
    "vote_average": {"type": "float"},
    "vote_count": {"type": "integer"},
    "overview": {
        "type": "text",
        "analyzer": "english",
        "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
    },
    "abstract_en": {"type": "text", "analyzer": "english"},
    "abstract_kk": {"type": "text"},
    "abstract_fr": {"type": "text", "analyzer": "french"},
    "description_en": {"type": "text", "analyzer": "english"},
    "description_kk": {"type": "text"},
    "description_fr": {"type": "text", "analyzer": "french"},
    "searchable_text": {"type": "text", "analyzer": "english"},
}

MOVIES_MAPPING = {"properties": MOVIES_PROPERTIES}
VECTOR_FIELD = "overview_embedding"
SEMANTIC_FIELD = "overview_semantic"


def vector_property(caps: Capabilities, dims: int) -> dict:
    if caps.vectors == "knn_vector":
        return {
            "type": "knn_vector",
            "dimension": dims,
            "method": {"name": "hnsw", "engine": "lucene", "space_type": "cosinesimil"},
        }
    if caps.vectors == "dense_vector":
        return {
            "type": "dense_vector",
            "dims": dims,
            "index": True,
            "similarity": "cosine",
            "index_options": {"type": "int8_hnsw"},
        }
    raise ValueError(f"{caps.describe()} has no vector field type")


def index_body(
    caps: Capabilities,
    meta: dict,
    embedding_dims: int | None = None,
    semantic_inference: str | None = None,
    default_pipeline: str | None = None,
) -> dict:
    """Settings + mappings for a movie index.

    `embedding_dims` adds the vector field, `semantic_inference` a `semantic_text`
    field bound to that inference endpoint, and `default_pipeline` runs every write
    through an ingest pipeline (the in-cluster E5 embeddings).
    """
    mappings = copy.deepcopy(MOVIES_MAPPING)
    settings: dict = {}
    if embedding_dims:
        mappings["properties"][VECTOR_FIELD] = vector_property(caps, embedding_dims)
        if caps.vectors == "knn_vector":
            settings["index"] = {"knn": True}
    if semantic_inference:
        mappings["properties"][SEMANTIC_FIELD] = {
            "type": "semantic_text",
            "inference_id": semantic_inference,
        }
    if default_pipeline:
        settings.setdefault("index", {})["default_pipeline"] = default_pipeline
    mappings["_meta"] = meta
    body = {"mappings": mappings}
    if settings:
        body["settings"] = settings
    return body
