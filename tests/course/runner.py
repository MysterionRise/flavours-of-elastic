"""Execute the course snippets of one day against a running stack and check them.

Default checks (overridable with fence annotations):
- every request returns 2xx (`expect=404`, `expect=4xx`, `expect=any`);
- searches, counts and ES|QL queries return something (`expect=empty`, `min=N`);
- aggregations produce buckets / values; `_bulk` reports no item errors;
- no deprecation warnings and no ES|QL warnings (`expect=warning` tolerates them);
- `top=ID` / `contains=ID,ID` check specific hits; a `// → <json>` comment after a
  request asserts that the response contains that JSON (subset match).
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from tests.course.console import ConsoleError, Request, esql_request, parse_requests
from tests.course.markdown import Block, extract_blocks

REPO_ROOT = Path(__file__).resolve().parents[2]
# Kibana Dev Tools sends these itself; Kibana 9 rejects internal APIs (e.g. sample data) without the origin.
KIBANA_HEADERS = {"kbn-xsrf": "course-harness", "x-elastic-internal-origin": "Kibana"}
# Searches see only refreshed data; the harness refreshes before them after any write.
SEARCH_ENDPOINTS = (
    "_search",
    "_count",
    "_query",
    "_msearch",
    "_explain",
    "_validate",
    "_termvectors",
)


@dataclass
class Context:
    url: str
    kibana_url: str
    auth: tuple[str, str] | None
    major: int
    capabilities: set[str]
    session: object = None
    dirty: bool = False  # a write happened since the last refresh


@dataclass
class Result:
    block: Block
    status: str  # pass | fail | skip
    message: str = ""


def context_from_env() -> Context:
    import requests
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    url = os.environ["ELASTICSEARCH_URL"].rstrip("/")
    auth = None
    if os.environ.get("ELASTIC_NO_AUTH", "false").lower() != "true":
        auth = (
            os.environ.get("ELASTIC_USER", "elastic"),
            os.environ.get("ELASTIC_PASSWORD", "elastic"),
        )
    session = requests.Session()
    session.auth, session.verify = auth, False
    version = session.get(url, timeout=30).json()["version"]["number"]
    capabilities = set(filter(None, os.environ.get("FOE_CAPABILITIES", "").split(",")))
    return Context(
        url=url,
        kibana_url=os.environ.get("KIBANA_URL", "http://localhost:5601").rstrip("/"),
        auth=auth,
        major=int(version.split(".")[0]),
        capabilities=capabilities,
        session=session,
    )


def subset(expected, actual) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            k in actual and subset(v, actual[k]) for k, v in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(expected) == len(actual)
            and all(map(subset, expected, actual))
        )
    return expected == actual


def send(ctx: Context, request: Request, timeout: int):
    base = ctx.kibana_url if request.kibana else ctx.url
    headers = KIBANA_HEADERS if request.kibana else {}
    path = request.path.split("?")[0]
    is_search = any(part in path for part in SEARCH_ENDPOINTS)
    if not request.kibana and ctx.dirty and is_search:
        ctx.session.post(f"{ctx.url}/_refresh", timeout=60)
        ctx.dirty = False
    kwargs = {"headers": headers, "timeout": timeout}
    if request.ndjson:
        kwargs["data"] = request.body.encode("utf-8")
        kwargs["headers"] = {**headers, "Content-Type": "application/x-ndjson"}
    elif request.body is not None:
        kwargs["json"] = request.body
    for attempt in range(4):
        response = ctx.session.request(request.method, base + request.path, **kwargs)
        if response.status_code not in (429, 503) or attempt == 3:
            break
        time.sleep(5 * (attempt + 1))
    if (
        request.method in ("PUT", "POST", "DELETE")
        and not is_search
        and not request.kibana
    ):
        ctx.dirty = True
    return response


def check(block: Block, request: Request, response) -> str | None:
    """Return an error message, or None when the response matches the expectations."""
    expect = block.attrs.get("expect", "ok")
    code = response.status_code
    try:
        payload = response.json()
    except ValueError:
        payload = None
    reason = ""
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        reason = f": {payload['error'].get('type')}: {payload['error'].get('reason', '')[:200]}"
    if expect.isdigit():
        return (
            None
            if code == int(expect)
            else f"expected HTTP {expect}, got {code}{reason}"
        )
    if expect == "4xx":
        return None if 400 <= code < 500 else f"expected a 4xx error, got {code}"
    if not 200 <= code < 300:
        return f"HTTP {code}{reason}"
    if expect == "any":
        return None
    warnings = response.headers.get("Warning", "")
    if warnings and expect != "warning":
        return f"warning header: {warnings[:200]}"
    path = request.path.split("?")[0]
    if isinstance(payload, dict):
        if path.endswith("_bulk") and payload.get("errors"):
            first = next(
                (
                    item
                    for item in payload.get("items", [])
                    if list(item.values())[0].get("error")
                ),
                {},
            )
            return f"bulk item errors: {str(first)[:200]}"
        if "hits" in payload and isinstance(payload["hits"], dict):
            total = payload["hits"].get("total")
            count = (
                total.get("value", 0)
                if isinstance(total, dict)
                else (total or len(payload["hits"].get("hits", [])))
            )
            hits = [hit.get("_id") for hit in payload["hits"].get("hits", [])]
            if expect == "empty":
                if count:
                    return f"expected no hits, got {count}"
            elif (
                count < int(block.attrs.get("min", 1)) and "aggregations" not in payload
            ):
                return (
                    f"expected at least {block.attrs.get('min', 1)} hit(s), got {count}"
                )
            if "top" in block.attrs and (
                not hits or str(hits[0]) != block.attrs["top"]
            ):
                return f"expected top hit {block.attrs['top']}, got {hits[:3]}"
            missing = [
                i
                for i in block.attrs.get("contains", "").split(",")
                if i and i not in map(str, hits)
            ]
            if missing:
                return f"expected hits {missing} among {hits[:10]}"
            for name, agg in (payload.get("aggregations") or {}).items():
                if (
                    isinstance(agg, dict)
                    and "buckets" in agg
                    and not agg["buckets"]
                    and expect != "empty"
                ):
                    return f"aggregation `{name}` returned no buckets"
                if (
                    isinstance(agg, dict)
                    and "value" in agg
                    and agg["value"] is None
                    and expect != "empty"
                ):
                    return f"aggregation `{name}` returned null"
        if (
            path.endswith("_count")
            and expect != "empty"
            and payload.get("count", 1) == 0
        ):
            return "count is 0"
        if path.endswith("_query"):
            if payload.get("is_partial"):
                return "ES|QL returned partial results"
            if not payload.get("values") and expect != "empty":
                return "ES|QL returned no rows"
    if request.expectation is not None and not (
        isinstance(request.expectation, str) or subset(request.expectation, payload)
    ):
        return f"response does not contain {str(request.expectation)[:200]}"
    return None


def run_shell(ctx: Context, block: Block) -> str | None:
    """Run the `python data/load_data.py ...` lines of a shell block against the stack."""
    text = block.text.replace("\\\n", " ")
    for line in text.splitlines():
        line = line.strip()
        if not re.match(r"^python3?\s+data/load_data\.py\b", line):
            continue
        args = shlex.split(line.split("#")[0])[1:]
        args += ["--url", ctx.url]
        if ctx.auth:
            args += ["--user", ctx.auth[0], "--password", ctx.auth[1]]
        if ctx.url.startswith("https://"):
            args.append("--insecure")
        result = subprocess.run(
            [sys.executable, *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        if result.returncode != 0:
            return f"`{line}` failed: {(result.stdout + result.stderr)[-300:]}"
        ctx.dirty = True
    return None


def setup_day(ctx: Context, steps: list[dict]) -> None:
    for step in steps:
        if "load" in step:
            block = Block(
                "setup",
                0,
                0,
                "setup",
                None,
                "bash",
                {},
                f"python data/load_data.py --dataset movies --size {step['load']}",
            )
            error = run_shell(ctx, block)
            if error:
                raise RuntimeError(error)
        if "kibana_sample" in step:
            url = f"{ctx.kibana_url}/api/sample_data/{step['kibana_sample']}"
            response = ctx.session.post(url, headers=KIBANA_HEADERS, timeout=300)
            if response.status_code not in (200, 409):
                raise RuntimeError(
                    f"loading Kibana sample data failed: {response.status_code} {response.text[:200]}"
                )


def run_block(ctx: Context, block: Block) -> Result:
    if block.attrs.get("test") in ("skip", "manual") or block.kind == "other":
        return Result(block, "skip", block.attrs.get("test", "not executable"))
    if "track" in block.attrs and str(ctx.major) != block.attrs["track"]:
        return Result(block, "skip", f"track {block.attrs['track']} only")
    needs = set(filter(None, block.attrs.get("requires", "").split(",")))
    if needs - ctx.capabilities - {"kibana"}:
        return Result(
            block, "skip", f"requires {','.join(sorted(needs - ctx.capabilities))}"
        )
    if block.errors:
        return Result(block, "fail", "; ".join(block.errors))
    if block.kind == "shell":
        error = run_shell(ctx, block)
        return Result(block, "fail" if error else "pass", error or "")
    try:
        requests = (
            parse_requests(block.text)
            if block.kind == "request"
            else [esql_request(block.text)]
        )
    except ConsoleError as exc:
        return Result(block, "fail", f"unparseable: {exc}")
    timeout = int(block.attrs.get("timeout", 120))
    for request in requests:
        try:
            response = send(ctx, request, timeout)
        except Exception as exc:  # noqa: BLE001 - network errors are test failures
            return Result(
                block,
                "fail",
                f"{request.method} {request.path}: {type(exc).__name__}: {exc}",
            )
        error = check(block, request, response)
        if error:
            return Result(block, "fail", f"{request.method} {request.path}: {error}")
    return Result(block, "pass")


def run_day(ctx: Context, files: list[str], setup: list[dict]) -> list[Result]:
    setup_day(ctx, setup)
    results = []
    for name in files:
        for block in extract_blocks(REPO_ROOT / name, REPO_ROOT):
            results.append(run_block(ctx, block))
    return results
