#!/usr/bin/env python3
"""Validate the flavours-of-elastic docker compose stacks.

Each stack is started in its own compose project (`foe-validate-<stack>`), so a
student's stack started from the same compose file and its data volumes are
never touched. The stack is torn down afterwards (also on failure or Ctrl-C).

Checks: version and distribution match the env file, cluster health and node
count, license, index/search round trip, vector search, ML (ML stack), the RRF
retriever (trial license) and the UI (Kibana / OpenSearch Dashboards).

    python validate.py --stack elk-single
    python validate.py --stack all
    python validate.py --list --json        # the registry, as used by CI
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from scripts.stacks import (
    STACKS,
    Connection,
    StackError,
    default_env_file,
    get_stack,
    load_env,
    running_stack,
)

GIB = 1024**3


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""


class CheckFailed(Exception):
    pass


def _json(response) -> dict:
    try:
        return response.json()
    except ValueError:
        return {}


def _expect(response, *ok_codes: int) -> dict:
    if response.status_code not in ok_codes:
        reason = _json(response).get("error", response.text[:200])
        raise CheckFailed(
            f"{response.request.method} {response.request.path_url} -> {response.status_code}: {reason}"
        )
    return _json(response)


def check_identity(conn: Connection, http) -> str:
    info = _expect(http.get(conn.url, timeout=10), 200)
    version = info.get("version", {})
    if version.get("number") != conn.version:
        raise CheckFailed(
            f"version {version.get('number')}, expected {conn.version} ({conn.stack.version_var})"
        )
    distribution = conn.stack.distribution
    if distribution == "opensearch" and version.get("distribution") != "opensearch":
        raise CheckFailed(f"expected an OpenSearch distribution, got {version}")
    if distribution == "elasticsearch" and (
        version.get("build_flavor") != "default" or "distribution" in version
    ):
        raise CheckFailed(
            f"expected the default Elasticsearch distribution, got {version}"
        )
    if distribution == "elasticsearch-oss" and version.get("build_flavor") != "oss":
        raise CheckFailed(
            f"expected the OSS build flavor, got {version.get('build_flavor')}"
        )
    return f"{distribution} {version['number']}"


def check_cluster(conn: Connection, http) -> str:
    nodes = conn.stack.nodes
    url = f"{conn.url}/_cluster/health?wait_for_status=yellow&wait_for_nodes={nodes}&timeout=120s"
    health = _expect(http.get(url, timeout=130), 200)
    if health.get("timed_out") or health.get("status") == "red":
        raise CheckFailed(
            f"status {health.get('status')}, {health.get('number_of_nodes')}/{nodes} nodes"
        )
    if health.get("number_of_nodes") != nodes:
        raise CheckFailed(f"{health.get('number_of_nodes')} nodes, expected {nodes}")
    return f"{health['status']}, {nodes} node(s)"


def check_licence(conn: Connection, http) -> str:
    licence = _expect(http.get(f"{conn.url}/_license", timeout=10), 200).get(
        "license", {}
    )
    if licence.get("type") != conn.licence or licence.get("status") != "active":
        hint = (
            " (a trial lasts 30 days; `down -v` starts a fresh cluster)"
            if conn.licence == "trial"
            else ""
        )
        raise CheckFailed(
            f"license {licence.get('type')}/{licence.get('status')}, expected {conn.licence}/active{hint}"
        )
    return f"{licence['type']} active"


def _scratch_index(http, conn: Connection, body: dict) -> str:
    index = f"foe-validate-{uuid.uuid4().hex[:8]}"
    _expect(http.put(f"{conn.url}/{index}", json=body, timeout=30), 200)
    return index


def check_crud(conn: Connection, http) -> str:
    index = _scratch_index(http, conn, {"settings": {"number_of_replicas": 0}})
    try:
        doc = {"title": "Validation Test"}
        _expect(
            http.put(
                f"{conn.url}/{index}/_doc/1?refresh=wait_for", json=doc, timeout=30
            ),
            200,
            201,
        )
        hits = _expect(
            http.get(f"{conn.url}/{index}/_search?q=title:validation", timeout=30), 200
        )["hits"]["hits"]
        if [hit["_id"] for hit in hits] != ["1"]:
            raise CheckFailed(
                f"search returned {[hit['_id'] for hit in hits]}, expected ['1']"
            )
    finally:
        http.delete(f"{conn.url}/{index}", timeout=30)
    return "index, search, delete"


def check_vectors(conn: Connection, http) -> str:
    docs = {"a": [1.0, 0.0, 0.0], "b": [0.0, 1.0, 0.0], "c": [0.7, 0.7, 0.0]}
    if conn.stack.distribution == "opensearch":
        body = {
            "settings": {"index.knn": True, "number_of_replicas": 0},
            "mappings": {
                "properties": {
                    "v": {"type": "knn_vector", "dimension": 3, "space_type": "l2"}
                }
            },
        }
        query = {
            "size": 1,
            "query": {"knn": {"v": {"vector": [0.9, 0.1, 0.0], "k": 1}}},
        }
    else:
        body = {
            "settings": {"number_of_replicas": 0},
            "mappings": {
                "properties": {
                    "v": {"type": "dense_vector", "dims": 3, "similarity": "l2_norm"}
                }
            },
        }
        query = {
            "knn": {
                "field": "v",
                "query_vector": [0.9, 0.1, 0.0],
                "k": 1,
                "num_candidates": 10,
            }
        }
    index = _scratch_index(http, conn, body)
    try:
        bulk = "".join(
            f'{{"index":{{"_id":"{doc_id}"}}}}\n{json.dumps({"v": vec})}\n'
            for doc_id, vec in docs.items()
        )
        response = http.post(
            f"{conn.url}/{index}/_bulk?refresh=wait_for",
            data=bulk,
            headers={"Content-Type": "application/x-ndjson"},
            timeout=30,
        )
        if _expect(response, 200).get("errors"):
            raise CheckFailed("bulk indexing reported errors")
        hits = _expect(
            http.post(f"{conn.url}/{index}/_search", json=query, timeout=30), 200
        )["hits"]["hits"]
        if not hits or hits[0]["_id"] != "a":
            raise CheckFailed(
                f"nearest neighbour was {[hit['_id'] for hit in hits]}, expected ['a']"
            )
    finally:
        http.delete(f"{conn.url}/{index}", timeout=30)
    return "kNN nearest neighbour correct"


def check_ml(conn: Connection, http) -> str:
    _expect(http.get(f"{conn.url}/_ml/info", timeout=30), 200)
    nodes = _expect(
        http.get(
            f"{conn.url}/_nodes?filter_path=nodes.*.name,nodes.*.roles", timeout=30
        ),
        200,
    )
    missing = [
        node["name"]
        for node in nodes.get("nodes", {}).values()
        if not {"ml", "transform"} <= set(node.get("roles", []))
    ]
    if missing:
        raise CheckFailed(f"nodes without ml/transform roles: {missing}")
    summary = "ml + transform roles"
    if conn.stack.min_ml_memory_gib:
        stats = _expect(http.get(f"{conn.url}/_ml/memory/_stats", timeout=30), 200)[
            "nodes"
        ].values()
        per_node = {n["name"]: n["mem"]["ml"]["max_in_bytes"] / GIB for n in stats}
        too_low = {
            name: round(gib, 2)
            for name, gib in per_node.items()
            if gib < conn.stack.min_ml_memory_gib
        }
        if too_low:
            raise CheckFailed(
                f"ML memory per node (GiB) {too_low} is below {conn.stack.min_ml_memory_gib}: raise ML_NODE_MEM_LIMIT"
            )
        summary += f", ML memory {min(per_node.values()):.2f} GiB/node"
    return summary


def check_rrf(conn: Connection, http) -> str:
    body = {
        "settings": {"number_of_replicas": 0},
        "mappings": {
            "properties": {
                "t": {"type": "text"},
                "v": {"type": "dense_vector", "dims": 2},
            }
        },
    }
    index = _scratch_index(http, conn, body)
    try:
        doc = {"t": "hello world", "v": [1.0, 0.0]}
        _expect(
            http.put(
                f"{conn.url}/{index}/_doc/1?refresh=wait_for", json=doc, timeout=30
            ),
            200,
            201,
        )
        retriever = {
            "rrf": {
                "retrievers": [
                    {"standard": {"query": {"match": {"t": "hello"}}}},
                    {
                        "knn": {
                            "field": "v",
                            "query_vector": [1.0, 0.0],
                            "k": 1,
                            "num_candidates": 5,
                        }
                    },
                ]
            }
        }
        hits = _expect(
            http.post(
                f"{conn.url}/{index}/_search", json={"retriever": retriever}, timeout=30
            ),
            200,
        )
        if not hits["hits"]["hits"]:
            raise CheckFailed("RRF retriever returned no hits")
    finally:
        http.delete(f"{conn.url}/{index}", timeout=30)
    return "rrf retriever works"


def check_ui(conn: Connection, http, timeout: int = 240) -> str:
    """Kibana: overall level `available`; Dashboards / Kibana OSS: overall state `green`."""
    import requests

    deadline = time.monotonic() + timeout
    last = "no response"
    while time.monotonic() < deadline:
        try:
            response = http.get(f"{conn.ui_url}/api/status", timeout=10)
            overall = _json(response).get("status", {}).get("overall", {})
            level = overall.get("level") or overall.get("state") or ""
            if response.status_code == 200 and level in ("available", "green"):
                return f"{conn.stack.ui_kind} {level}"
            last = f"HTTP {response.status_code} {level}".strip()
        except requests.RequestException as exc:
            last = type(exc).__name__
        time.sleep(5)
    raise CheckFailed(f"{conn.stack.ui_kind} not available after {timeout}s: {last}")


Check = Callable[[Connection, object], str]


def plan_checks(conn: Connection, skip_ui: bool = False) -> list[tuple[str, Check]]:
    checks: list[tuple[str, Check]] = [
        ("identity", check_identity),
        ("cluster", check_cluster),
    ]
    if conn.stack.licence_var:
        checks.append(("license", check_licence))
    checks.append(("crud", check_crud))
    if conn.capabilities & {"dense_vector", "os_knn"}:
        checks.append(("vectors", check_vectors))
    if "ml" in conn.capabilities:
        checks.append(("ml", check_ml))
    if "rrf" in conn.capabilities:
        checks.append(("rrf", check_rrf))
    if not skip_ui:
        checks.append(("ui", check_ui))
    return checks


def validate_stack(name: str, args) -> list[Result]:
    stack = get_stack(name)
    print(f"\n{'=' * 60}\n{stack.title} ({stack.name})\n{'=' * 60}", flush=True)
    results: list[Result] = []
    try:
        with running_stack(
            stack.name,
            keep=args.keep,
            keep_volumes=args.no_cleanup,
            env_file=args.env_file,
            port_offset=args.port_offset,
            timeout=args.timeout,
            logs_dir=args.logs_dir,
        ) as conn:
            http = conn.session()
            for check_name, check in plan_checks(conn, args.skip_ui):
                try:
                    detail = check(conn, http)
                    results.append(Result(check_name, True, detail))
                    print(f"  PASS {check_name:9s} {detail}", flush=True)
                except Exception as exc:  # noqa: BLE001 - every failure is reported, not raised
                    results.append(Result(check_name, False, str(exc)))
                    print(f"  FAIL {check_name:9s} {exc}", flush=True)
            if not all(result.ok for result in results):
                raise CheckFailed(
                    "one or more checks failed"
                )  # dumps container logs before teardown
    except CheckFailed:
        pass
    except StackError as exc:
        results.append(Result("startup", False, str(exc)))
        print(f"  FAIL startup    {exc}", flush=True)
    return results


def write_step_summary(report: dict[str, list[Result]]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = ["| Stack | Check | Result | Detail |", "|---|---|---|---|"]
    for stack, results in report.items():
        for result in results:
            detail = result.detail.replace("|", "\\|").replace("\n", " ")[:300]
            lines.append(
                f"| {stack} | {result.name} | {'✅' if result.ok else '❌'} | {detail} |"
            )
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate flavours-of-elastic stacks")
    names = list(STACKS) + [
        alias for stack in STACKS.values() for alias in stack.aliases
    ]
    parser.add_argument(
        "--stack",
        default="all",
        help=f"comma-separated names or 'all' ({', '.join(names)})",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="default: .env, falling back to .env.example",
    )
    parser.add_argument(
        "--keep", action="store_true", help="leave the stack running afterwards"
    )
    parser.add_argument(
        "--no-cleanup", action="store_true", help="stop the stack but keep its volumes"
    )
    parser.add_argument(
        "--port-offset", type=int, default=0, help="publish on 9200+N / 5601+N"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="seconds to wait for healthy containers",
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=None,
        help="write container logs here on failure",
    )
    parser.add_argument("--report-json", type=Path, default=None)
    parser.add_argument("--skip-ui", action="store_true")
    parser.add_argument(
        "--list", action="store_true", help="list the registered stacks and exit"
    )
    parser.add_argument(
        "--json", action="store_true", help="with --list: machine-readable output"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        env = load_env(args.env_file or default_env_file())
        described = [stack.describe(env) for stack in STACKS.values()]
        if args.json:
            print(json.dumps(described, indent=2))
        else:
            for item in described:
                print(
                    f"{item['name']:13s} {item['version']:8s} {item['url']:24s} {item['title']}"
                )
        return 0

    try:
        requested = (
            list(STACKS)
            if args.stack == "all"
            else [get_stack(n.strip()).name for n in args.stack.split(",")]
        )
    except StackError as exc:
        parser.error(str(exc))
    try:
        import requests  # noqa: F401
    except ImportError:
        print(
            "The requests library is required: pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 2

    report: dict[str, list[Result]] = {}
    try:
        for name in requested:
            report[name] = validate_stack(name, args)
    except KeyboardInterrupt:
        print("\nInterrupted - stacks were torn down.", file=sys.stderr)
        return 130

    print(f"\n{'=' * 60}\nVALIDATION SUMMARY\n{'=' * 60}")
    failed = []
    for name, results in report.items():
        ok = bool(results) and all(result.ok for result in results)
        if not ok:
            failed.append(name)
        print(f"{name:13s}: {'PASSED' if ok else 'FAILED'}")
    write_step_summary(report)
    if args.report_json:
        args.report_json.write_text(
            json.dumps({k: [asdict(r) for r in v] for k, v in report.items()}, indent=2)
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
