#!/usr/bin/env python3
"""Evaluate portfolio search modes against hand-labeled movie queries."""

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, Iterable, List

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from search.client import PortfolioSearchClient  # noqa: E402


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


def load_queries(path: Path) -> List[Dict]:
    try:
        import yaml
    except ImportError:
        print("Error: PyYAML required. Install with: pip install -r requirements.txt")
        sys.exit(1)

    with path.open(encoding="utf-8") as query_file:
        payload = yaml.safe_load(query_file)
    return payload["queries"]


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
                "ndcg_at_10": ndcg_at_k(result_ids, relevance, k),
                "mrr_at_10": reciprocal_rank(result_ids, relevant_ids),
                "recall_at_10": recall_at_k(result_ids, relevant_ids, k),
                "latency_ms": response.took_ms,
                "engine_took_ms": response.engine_took_ms,
                "top_results": result_ids[: min(5, k)],
            }
        )
    return rows


def summarize(rows: List[Dict]) -> Dict:
    return {
        "queries": len(rows),
        "ndcg_at_10": sum(row["ndcg_at_10"] for row in rows) / len(rows),
        "mrr_at_10": sum(row["mrr_at_10"] for row in rows) / len(rows),
        "recall_at_10": sum(row["recall_at_10"] for row in rows) / len(rows),
        "p50_latency_ms": percentile([row["latency_ms"] for row in rows], 50),
        "p95_latency_ms": percentile([row["latency_ms"] for row in rows], 95),
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate portfolio search quality")
    parser.add_argument("--mode", default="bm25,dense,hybrid_rrf")
    parser.add_argument("--queries", default="evaluation/movie_queries.yml")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--num-candidates", type=int, default=50)
    parser.add_argument("--rank-constant", type=int, default=60)
    parser.add_argument(
        "--json", action="store_true", help="Print machine-readable JSON"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    queries = load_queries(Path(args.queries))
    client = PortfolioSearchClient()
    modes = [mode.strip() for mode in args.mode.split(",") if mode.strip()]

    output = {}
    for mode in modes:
        rows = evaluate_mode(
            client, mode, queries, args.k, args.num_candidates, args.rank_constant
        )
        output[mode] = {
            "summary": summarize(rows),
            "rows": rows,
        }

    if args.json:
        print(json.dumps(output, indent=2))
        return 0

    print("| Mode | Queries | NDCG@10 | MRR@10 | Recall@10 | p50 ms | p95 ms |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for mode, result in output.items():
        summary = result["summary"]
        print(
            f"| {mode} | {summary['queries']} | {summary['ndcg_at_10']:.3f} | "
            f"{summary['mrr_at_10']:.3f} | {summary['recall_at_10']:.3f} | "
            f"{summary['p50_latency_ms']:.1f} | {summary['p95_latency_ms']:.1f} |"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
