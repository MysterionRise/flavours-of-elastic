"""Prompt construction and a groundedness check for movie RAG.

Each retrieved movie enters the context with its id, `[318]`, and the model
is told to cite those ids. `check_citations` then flags answers that cite
nothing, or cite a movie that was never retrieved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CITATION = re.compile(r"\[(\d+)\]")

SYSTEM_PROMPT = (
    "You are a movie expert. Answer ONLY from the movies in the context. Cite every movie you mention"
    " with its id in square brackets, e.g. [318]. If the context does not answer the question, say so"
    " and do not invent movies. Be concise."
)


def format_context(hits: list[dict], max_chars: int = 400) -> str:
    if not hits:
        return "No movies were retrieved."
    lines = []
    for hit in hits:
        genres = ", ".join(hit.get("genres") or [])
        year = hit.get("year") or "n/a"
        text = (hit.get("overview") or hit.get("description_en") or "")[:max_chars]
        lines.append(f"[{hit['id']}] {hit['title']} ({year}; {genres})\n{text}")
    return "\n\n".join(lines)


def messages(question: str, hits: list[dict]) -> list[dict]:
    context = format_context(hits)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
    ]


@dataclass
class Citations:
    cited: list[int]
    unknown: list[int]  # cited but not retrieved: a hallucination signal

    @property
    def grounded(self) -> bool:
        return bool(self.cited) and not self.unknown


def check_citations(answer: str, hits: list[dict]) -> Citations:
    retrieved = {int(hit["id"]) for hit in hits}
    cited = sorted({int(match) for match in CITATION.findall(answer or "")})
    return Citations(cited, [doc_id for doc_id in cited if doc_id not in retrieved])
