"""What a running cluster can do, read from the cluster itself.

`GET /` gives the distribution and version, `GET /_license` the licence
(Elasticsearch only) and `GET /_nodes` the node roles. The loader and the
search client use this to pick mappings and query types, and to refuse
features the cluster lacks with a clear message instead of an HTTP 400.
"""

from __future__ import annotations

from dataclasses import dataclass

from search.connection import Client, EsError

# Licences that unlock ML inference, the rrf/linear retrievers and semantic_text.
PAID_LICENCES = ("trial", "platinum", "enterprise")


@dataclass(frozen=True)
class Capabilities:
    distribution: str  # "elasticsearch" | "opensearch" | "elasticsearch-oss"
    version: str
    licence: str | None  # None when the cluster has no licensing (OpenSearch, OSS)
    ml_nodes: int = 0

    @property
    def major(self) -> int:
        return int(self.version.split(".")[0] or 0)

    @property
    def minor(self) -> tuple[int, int]:
        parts = (self.version.split(".") + ["0", "0"])[:2]
        return int(parts[0] or 0), int(parts[1] or 0)

    @property
    def vectors(self) -> str | None:
        """Vector field type: `dense_vector` (Elasticsearch), `knn_vector` (OpenSearch) or None."""
        if self.distribution == "opensearch":
            return "knn_vector"
        if self.distribution == "elasticsearch" and self.major >= 8:
            return "dense_vector"
        return None

    @property
    def rrf(self) -> bool:
        """Server-side `rrf` retriever (Elasticsearch 8.14+, enterprise or trial licence)."""
        return (
            self.distribution == "elasticsearch"
            and self.minor >= (8, 14)
            and self.licence in ("trial", "enterprise")
        )

    @property
    def ml(self) -> bool:
        """In-cluster inference (E5, ELSER): a paid/trial licence and at least one ML node."""
        return (
            self.distribution == "elasticsearch"
            and self.licence in PAID_LICENCES
            and self.ml_nodes > 0
        )

    def features(self) -> list[str]:
        names = [self.vectors] if self.vectors else []
        names += [name for name in ("rrf", "ml") if getattr(self, name)]
        return names

    def describe(self) -> str:
        licence = f", {self.licence} licence" if self.licence else ""
        return f"{self.distribution} {self.version}{licence}"


def detect(client: Client) -> Capabilities:
    root = client.get("/")
    version = root.get("version", {}) if isinstance(root, dict) else {}
    number = str(version.get("number", "0.0.0"))
    if version.get("distribution") == "opensearch":
        return Capabilities("opensearch", number, None)
    if version.get("build_flavor") == "oss":
        return Capabilities("elasticsearch-oss", number, None)
    try:
        licence = client.get("/_license").get("license", {})
        licence_type = (
            licence.get("type") if licence.get("status") == "active" else None
        )
    except EsError:
        licence_type = None
    try:
        nodes = client.get("/_nodes", params={"filter_path": "nodes.*.roles"})
        roles = [node.get("roles", []) for node in nodes.get("nodes", {}).values()]
        ml_nodes = sum("ml" in node_roles for node_roles in roles)
    except EsError:
        ml_nodes = 0
    return Capabilities("elasticsearch", number, licence_type, ml_nodes)
