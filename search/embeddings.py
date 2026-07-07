"""Embedding helpers for local demos and optional model-backed generation."""

import hashlib
import math
import re
from collections import Counter
from typing import Iterable, List

DEFAULT_EMBEDDING_DIMS = 384
TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> List[str]:
    """Tokenize text into stable lowercase terms."""
    return TOKEN_RE.findall((text or "").lower())


def deterministic_text_embedding(
    text: str, dims: int = DEFAULT_EMBEDDING_DIMS
) -> List[float]:
    """Create a deterministic unit vector without external model downloads.

    This is intentionally simple: it hashes lexical tokens into a fixed-size vector
    so local kNN and hybrid demos work from a fresh clone. Production-quality demos
    can replace this with the optional sentence-transformers pipeline.
    """
    vector = [0.0] * dims
    counts = Counter(tokenize(text))

    for token, count in counts.items():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dims
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        weight = 1.0 + math.log(count)
        vector[index] += sign * weight

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [round(value / norm, 6) for value in vector]


def embedding_text(fields: Iterable[str]) -> str:
    """Join fields into the text used for dense retrieval."""
    return " ".join(value for value in fields if value)
