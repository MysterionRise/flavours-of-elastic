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
from pathlib import Path
from typing import Dict, Iterable, List, Optional

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


def ndcg_at_k(result_ids: List[int], relevance: Dict[int, int], k: int) -> float:
    actual = [relevance.get(doc_id, 0) for doc_id in result_ids[:k]]
    ideal = sorted(relevance.values(), reverse=True)[:k]
    ideal_score = dcg(ideal)
    if ideal_score == 0:
        return 0.0
    return dcg(actual) / ideal_score


def reciprocal_rank(result_ids: List[int], relevant_ids: set) -> float:
    for rank, doc_id in enumerate(result_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def recall_at_k(result_ids: List[int], relevant_ids: set, k: int) -> float:
    if not relevant_ids:
        return 0.0
    return len(set(result_ids[:k]) & relevant_ids) / len(relevant_ids)


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil((pct / 100) * len(ordered)) - 1))
    return ordered[index]


def relevance_map(query_def: Dict) -> Dict[int, int]:
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


def load_queries(path: Path) -> List[Dict]:
    return load_yaml(path)["queries"]


def evaluate_mode(
    client: PortfolioSearchClient,
    mode: str,
    queries: List[Dict],
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
                "top_results": result_ids[: min(5, k)],
            }
        )
    return rows


def summarize(rows: List[Dict], k: int) -> Dict:
    summary = {"queries": len(rows), "k": k}
    for metric in METRICS:
        summary[metric] = sum(row[metric] for row in rows) / len(rows)
    summary["p50_latency_ms"] = percentile([row["latency_ms"] for row in rows], 50)
    summary["p95_latency_ms"] = percentile([row["latency_ms"] for row in rows], 95)
    fusion = {row["fusion"] for row in rows if row["fusion"]}
    if fusion:
        summary["fusion"] = ",".join(sorted(fusion))
    return summary


def judged_ids(queries: List[Dict]) -> List[int]:
    return sorted({doc_id for query in queries for doc_id in relevance_map(query)})


def evaluate(client, modes, queries, args) -> Dict:
    output: Dict[str, Dict] = {}
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


def below_floors(output: Dict, floors: Dict) -> List[str]:
    failures = []
    for mode, minimums in (floors.get("modes") or {}).items():
        summary = output.get(mode, {}).get("summary")
        if summary is None:
            continue  # not evaluated (or errored, which is reported separately)
        for metric, minimum in minimums.items():
            if summary[metric] < minimum:
                failures.append(
                    f"{mode} {metric}@{summary['k']} {summary[metric]:.3f} < floor {minimum}"
                )
    return failures


def parse_args(argv: Optional[List[str]] = None):
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


def main(argv: Optional[List[str]] = None) -> int:
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


def print_table(output: Dict, k: int) -> None:
    print(f"| Mode | Queries | NDCG@{k} | MRR@{k} | Recall@{k} | p50 ms | p95 ms |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for mode, result in output.items():
        if "error" in result:
            print(f"| {mode} | error | | | | | |")
            continue
        summary = result["summary"]
        label = f"{mode} ({summary['fusion']} fusion)" if "fusion" in summary else mode
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
