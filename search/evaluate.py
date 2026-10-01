#!/usr/bin/env python3
"""Evaluate search modes against hand-labeled movie queries.

    python search/evaluate.py --mode bm25,dense,hybrid_rrf
    python search/evaluate.py --stack elk-ml --fail-under evaluation/floors.yml --output report.json

Each mode is evaluated on its own: a mode the cluster can't run (dense on
Elasticsearch OSS, an index that was never loaded) is reported as an error
without hiding the others. Exit code 1 when a mode errors or falls below
its floor in `--fail-under`.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from search.client import INDICES, PortfolioSearchClient  # noqa: E402
from search.config import resolve  # noqa: E402

METRICS = ("ndcg", "mrr", "recall")


def dcg(relevances: Iterable[int]) -> float:
    return sum(
        (2**rel - 1) / math.log2(rank + 1)
        for rank, rel in enumerate(relevances, start=1)
    )


def ndcg_at_k(result_ids: list[int], relevance: dict[int, int], k: int) -> float:
    actual = [relevance.get(doc_id, 0) for doc_id in result_ids[:k]]
    ideal = sorted(relevance.values(), reverse=True)[:k]
    ideal_score = dcg(ideal)
    if ideal_score == 0:
        return 0.0
    return dcg(actual) / ideal_score


def reciprocal_rank(result_ids: list[int], relevant_ids: set) -> float:
    for rank, doc_id in enumerate(result_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def recall_at_k(result_ids: list[int], relevant_ids: set, k: int) -> float:
    if not relevant_ids:
        return 0.0
    return len(set(result_ids[:k]) & relevant_ids) / len(relevant_ids)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil((pct / 100) * len(ordered)) - 1))
    return ordered[index]


def relevance_map(query_def: dict) -> dict[int, int]:
    if "relevance" in query_def:
        return {
            int(doc_id): int(score) for doc_id, score in query_def["relevance"].items()
        }
    return {int(doc_id): 1 for doc_id in query_def.get("relevant_ids", [])}


def load_yaml(path: Path):
    try:
        import yaml
    except ImportError:
        print("Error: PyYAML required. Install with: pip install -r requirements.txt")
        sys.exit(1)

    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_queries(path: Path) -> list[dict]:
    return load_yaml(path)["queries"]


def evaluate_mode(
    client: PortfolioSearchClient,
    mode: str,
    queries: list[dict],
    k: int,
    num_candidates: int,
    rank_constant: int,
):
    rows = []
    for query_def in queries:
        relevance = relevance_map(query_def)
        relevant_ids = set(relevance)
        response = client.search(
            query_def["text"],
            mode=mode,
            k=k,
            num_candidates=num_candidates,
            rank_constant=rank_constant,
        )
        result_ids = [hit["id"] for hit in response.hits]
        rows.append(
            {
                "query_id": query_def["id"],
                "query": query_def["text"],
                "mode": mode,
                "ndcg": ndcg_at_k(result_ids, relevance, k),
                "mrr": reciprocal_rank(result_ids[:k], relevant_ids),
                "recall": recall_at_k(result_ids, relevant_ids, k),
                "latency_ms": response.took_ms,
                "engine_took_ms": response.engine_took_ms,
                "fusion": response.fusion,
                "embedding": response.embedding,
                "top_results": result_ids[: min(5, k)],
            }
        )
    return rows


def summarize(rows: list[dict], k: int) -> dict:
    summary = {"queries": len(rows), "k": k}
    for metric in METRICS:
        summary[metric] = sum(row[metric] for row in rows) / len(rows)
    summary["p50_latency_ms"] = percentile([row["latency_ms"] for row in rows], 50)
    summary["p95_latency_ms"] = percentile([row["latency_ms"] for row in rows], 95)
    for key in ("fusion", "embedding"):
        values = {row[key] for row in rows if row[key]}
        if values:
            summary[key] = ",".join(sorted(values))
    return summary


def judged_ids(queries: list[dict]) -> list[int]:
    return sorted({doc_id for query in queries for doc_id in relevance_map(query)})


def evaluate(client, modes, queries, args) -> dict:
    output: dict[str, dict] = {}
    judged = judged_ids(queries)
    for mode in modes:
        try:
            index = INDICES.get(mode)
            missing = (
                sorted(set(judged) - client.ids_present(index, judged)) if index else []
            )
            rows = evaluate_mode(
                client, mode, queries, args.k, args.num_candidates, args.rank_constant
            )
        except Exception as exc:  # noqa: BLE001 - one mode failing must not hide the others
            output[mode] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        output[mode] = {"summary": summarize(rows, args.k), "rows": rows}
        if missing:
            output[mode]["missing_judged_ids"] = missing
    return output


def below_floors(output: dict, floors: dict) -> list[str]:
    """Floors are keyed by mode, or by `mode@embedding` (e.g. `dense@e5`), which wins."""
    failures, table = [], floors.get("modes") or {}
    for mode, result in output.items():
        summary = result.get("summary")
        if summary is None:
            continue  # errored, which is reported separately
        key = f"{mode}@{summary['embedding']}" if "embedding" in summary else mode
        minimums = table.get(key) if key in table else table.get(mode)
        for metric, minimum in (minimums or {}).items():
            if summary[metric] < minimum:
                failures.append(
                    f"{key} {metric}@{summary['k']} {summary[metric]:.3f} < floor {minimum}"
                )
    return failures


def parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(
        description="Evaluate search quality per retrieval mode"
    )
    parser.add_argument("--mode", default="bm25,dense,hybrid_rrf")
    parser.add_argument("--queries", default="evaluation/movie_queries.yml")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--num-candidates", type=int, default=50)
    parser.add_argument("--rank-constant", type=int, default=60)
    parser.add_argument(
        "--stack",
        help="a stack from scripts/stacks.py (default: environment, then auto-detect)",
    )
    parser.add_argument(
        "--json", action="store_true", help="Print machine-readable JSON"
    )
    parser.add_argument("--output", help="also write the JSON report to this file")
    parser.add_argument(
        "--fail-under", help="YAML file with per-mode metric floors (exit 1 below them)"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    queries = load_queries(Path(args.queries))
    client = PortfolioSearchClient(target=resolve(stack=args.stack))
    modes = [mode.strip() for mode in args.mode.split(",") if mode.strip()]
    output = evaluate(client, modes, queries, args)
    failures = (
        below_floors(output, load_yaml(Path(args.fail_under)))
        if args.fail_under
        else []
    )
    errors = [
        f"{mode}: {result['error']}"
        for mode, result in output.items()
        if "error" in result
    ]

    if args.output:
        Path(args.output).write_text(
            json.dumps(output, indent=2) + "\n", encoding="utf-8"
        )
    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print_table(output, args.k)
    for problem in errors + failures:
        print(f"FAIL {problem}", file=sys.stderr)
    return 1 if errors or failures else 0


def print_table(output: dict, k: int) -> None:
    print(f"| Mode | Queries | NDCG@{k} | MRR@{k} | Recall@{k} | p50 ms | p95 ms |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for mode, result in output.items():
        if "error" in result:
            print(f"| {mode} | error | | | | | |")
            continue
        summary = result["summary"]
        details = [summary[key] for key in ("embedding",) if key in summary]
        details += [f"{summary['fusion']} fusion"] if "fusion" in summary else []
        label = f"{mode} ({', '.join(details)})" if details else mode
        print(
            f"| {label} | {summary['queries']} | {summary['ndcg']:.3f} | "
            f"{summary['mrr']:.3f} | {summary['recall']:.3f} | "
            f"{summary['p50_latency_ms']:.1f} | {summary['p95_latency_ms']:.1f} |"
        )
    for mode, result in output.items():
        if result.get("missing_judged_ids"):
            print(
                f"\nnote: {mode}: judged movies missing from the index: {result['missing_judged_ids']}"
            )


if __name__ == "__main__":
    sys.exit(main())
