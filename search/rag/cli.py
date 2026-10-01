"""Ask questions about the movies, answered by an LLM from retrieved context.

    python -m search.rag --stage hybrid --question "films about escaping from prison"
    python -m search.rag --stage bm25 --retrieve-only --question "space adventure" --json
    python -m search.rag --stack elk-ml --stage hybrid      # interactive

Stages are the retrieval modes of search/client.py: `bm25` (keywords), `knn`
(vectors) and `hybrid` (both, fused with RRF); `elser` and `hybrid_all` on an
ML stack loaded with `--embeddings e5 --with-elser`. Generation needs
OPENROUTER_API_KEY; `--retrieve-only` shows what would be sent, without it.
"""

from __future__ import annotations

import argparse
import json
import sys

from search.client import EMBEDDINGS_INDEX, PortfolioSearchClient
from search.config import resolve
from search.connection import ConnectionFailed, EsError
from search.embedders import EmbedderMismatch
from search.rag.llm import DEFAULT_MODEL, LlmError, OpenRouter
from search.rag.prompts import check_citations, format_context, messages

STAGES = {
    "bm25": "bm25",
    "knn": "dense",
    "hybrid": "hybrid_rrf",
    "elser": "elser",
    "hybrid_all": "hybrid_all",
}


def retrieve(
    client: PortfolioSearchClient, stage: str, question: str, k: int
) -> list[dict]:
    index = None  # each mode's default index
    if stage == "bm25" and client.http.exists(f"/{EMBEDDINGS_INDEX}"):
        index = EMBEDDINGS_INDEX  # the same movies as the other stages, if it is loaded
    return client.search(question, mode=STAGES[stage], index=index, k=k).hits


def answer(llm: OpenRouter | None, client, stage: str, question: str, k: int) -> dict:
    hits = retrieve(client, stage, question, k)
    result: dict = {
        "question": question,
        "stage": stage,
        "retrieved": [
            {"id": hit["id"], "title": hit["title"], "year": hit["year"]}
            for hit in hits
        ],
    }
    if llm is None:
        result["context"] = format_context(hits)
        return result
    text = llm.chat(messages(question, hits))
    citations = check_citations(text, hits)
    result.update(
        answer=text,
        model=llm.model,
        cited=citations.cited,
        unknown_citations=citations.unknown,
        grounded=citations.grounded,
    )
    return result


def emit(result: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        show(result)


def show(result: dict) -> None:
    titles = (
        ", ".join(f"{m['title']} [{m['id']}]" for m in result["retrieved"]) or "nothing"
    )
    print(f"\n  retrieved ({result['stage']}): {titles}")
    if "answer" not in result:
        print(f"\n{result['context']}\n")
        return
    print(f"\n{result['answer']}\n")
    if result["unknown_citations"]:
        print(
            f"  warning: cites movies that were not retrieved: {result['unknown_citations']}"
        )
    elif not result["cited"]:
        print("  warning: the answer cites no retrieved movie")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m search.rag",
        description="Movie question answering: retrieval from Elasticsearch + an LLM via OpenRouter",
        epilog=__doc__.split("\n\n")[1],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--stage", choices=list(STAGES), default="hybrid")
    parser.add_argument(
        "--question", help="ask one question and exit (default: interactive)"
    )
    parser.add_argument(
        "--k", type=int, default=5, help="movies to retrieve (default: 5)"
    )
    parser.add_argument(
        "--stack",
        help="a stack from scripts/stacks.py (default: environment, then auto-detect)",
    )
    parser.add_argument(
        "--model",
        help=f"OpenRouter model id (default: $OPENROUTER_MODEL or {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--retrieve-only",
        action="store_true",
        help="skip the LLM: print the retrieved context",
    )
    parser.add_argument("--json", action="store_true", help="print results as JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        client = PortfolioSearchClient(target=resolve(stack=args.stack))
        llm = None
        if not args.retrieve_only:
            llm = OpenRouter(model=args.model)
            llm.check()
        if args.question:
            result = answer(llm, client, args.stage, args.question, args.k)
            emit(result, args.json)
            return 0
        print(
            f"Movie RAG ({args.stage}{', retrieve only' if llm is None else ', ' + llm.model}). Empty line to quit."
        )
        while True:
            try:
                question = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                return 0
            if not question or question.lower() in ("quit", "exit", "q"):
                return 0
            result = answer(llm, client, args.stage, question, args.k)
            emit(result, args.json)
    except (LlmError, ConnectionFailed, EsError, EmbedderMismatch) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
