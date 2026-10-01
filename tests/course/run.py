"""Run the course snippets of one day against a stack.

    python -m scripts.with_stack elk-single -- python -m tests.course.run --day 2
    python -m tests.course.run --day 2 --stack elk-single      # attach to your running stack
    python -m tests.course.run --day 2 --list                  # what would run (no stack needed)

Known failures are listed in tests/course/baseline.yml (a ratchet): they are
reported as expected failures, a new failure fails the run, and a baseline entry
that now passes fails the run too - remove it, the content got fixed.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

import yaml

from tests.course.markdown import extract_blocks
from tests.course.runner import REPO_ROOT, context_from_env, run_day

HERE = Path(__file__).resolve().parent


def load_yaml(name: str) -> dict:
    path = HERE / name
    return (
        (yaml.safe_load(path.read_text(encoding="utf-8")) or {})
        if path.exists()
        else {}
    )


def classify(results, baseline: dict, track: str):
    """Mark failures listed in the baseline for this track as xfail; listed passes as XPASS."""
    rows = []
    for result in results:
        entry = baseline.get(result.block.id)
        known = isinstance(entry, dict) and track in {
            str(t) for t in entry.get("tracks", [])
        }
        if result.status == "fail":
            status = "xfail" if known else "FAIL"
        elif result.status == "pass" and known:
            status = "XPASS"
        else:
            status = result.status
        rows.append((status, result))
    return rows


def update_baseline(baseline: dict, results, track: str) -> dict:
    """Record this track's failures; drop this track from entries that no longer fail."""
    track_id = int(track)
    updated = {}
    failing = {r.block.id: r.message[:100] for r in results if r.status == "fail"}
    for block_id, entry in baseline.items():
        tracks = set(entry.get("tracks", [])) - {track_id}
        if block_id in failing:
            tracks.add(track_id)
        if tracks:
            updated[block_id] = {
                "reason": entry.get("reason", ""),
                "tracks": sorted(tracks),
            }
    for block_id, reason in failing.items():
        updated.setdefault(block_id, {"reason": reason, "tracks": [track_id]})
    return dict(sorted(updated.items()))


def write_junit(path: Path, rows, day: int) -> None:
    cases = []
    for status, result in rows:
        block = result.block
        name = escape(f"{block.id} ({block.file}:{block.line})")
        body = ""
        if status in ("FAIL", "XPASS"):
            body = f'<failure message="{escape(result.message[:500], {chr(34): "&quot;"})}"/>'
        elif status in ("skip", "xfail"):
            body = f'<skipped message="{escape((status + ": " + result.message)[:500], {chr(34): "&quot;"})}"/>'
        cases.append(
            f'  <testcase classname="course.day{day}" name="{name}">{body}</testcase>'
        )
    failures = sum(status in ("FAIL", "XPASS") for status, _ in rows)
    path.write_text(
        f'<?xml version="1.0" encoding="utf-8"?>\n<testsuite name="course-day{day}" tests="{len(rows)}" '
        f'failures="{failures}">\n' + "\n".join(cases) + "\n</testsuite>\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the course snippets of one day")
    parser.add_argument("--day", type=int, required=True, choices=[1, 2, 3, 4])
    parser.add_argument(
        "--stack", help="attach to this running stack when no connection env is set"
    )
    parser.add_argument(
        "--list", action="store_true", help="list the blocks and exit (no stack needed)"
    )
    parser.add_argument("--junit", type=Path)
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="record today's failures as known",
    )
    args = parser.parse_args(argv)

    day = load_yaml("manifest.yml")["days"][args.day]
    if args.list:
        for name in day["files"]:
            for block in extract_blocks(REPO_ROOT / name, REPO_ROOT):
                print(f"{block.kind:8s} {block.file}:{block.line:<5d} {block.id}")
        return 0
    if not day.get("enabled", True):
        print(
            f"Day {args.day} is not enabled in tests/course/manifest.yml - nothing to run."
        )
        return 0

    if "ELASTICSEARCH_URL" not in os.environ:
        if not args.stack:
            parser.error(
                "no ELASTICSEARCH_URL in the environment: pass --stack or use scripts.with_stack"
            )
        from scripts.stacks import attach

        os.environ.update(attach(args.stack).export_env())
    ctx = context_from_env()
    track = str(ctx.major)
    results = run_day(ctx, day["files"], day.get("setup", []))

    baseline_all = load_yaml("baseline.yml")
    key = f"day{args.day}"
    baseline = baseline_all.get(key) or {}
    if args.update_baseline:
        baseline_all[key] = update_baseline(baseline, results, track)
        header = "# Known course-snippet failures per track (a ratchet): content fixes remove entries.\n"
        body = yaml.safe_dump(
            baseline_all, sort_keys=True, allow_unicode=True, width=120
        )
        (HERE / "baseline.yml").write_text(header + body, encoding="utf-8")
        baseline = baseline_all[key]
        print(
            f"recorded {sum(track in map(str, e['tracks']) for e in baseline.values())} known failure(s) for {key}"
        )

    rows = classify(results, baseline, track)
    counts = Counter(status for status, _ in rows)
    for status, result in rows:
        if status in ("FAIL", "XPASS", "xfail"):
            block = result.block
            note = (
                "now passes - remove it from tests/course/baseline.yml"
                if status == "XPASS"
                else result.message
            )
            print(f"{status:5s} {block.file}:{block.line} [{block.id}] {note}")
    summary = ", ".join(
        f"{counts[s]} {s}"
        for s in ("pass", "FAIL", "xfail", "XPASS", "skip")
        if counts[s]
    )
    print(f"\nDay {args.day} on Elasticsearch {track}.x: {summary}")
    if args.junit:
        write_junit(args.junit, rows, args.day)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
            handle.write(f"### Course day {args.day} on {track}.x\n\n{summary}\n\n")
            for status, result in rows:
                if status in ("FAIL", "XPASS"):
                    handle.write(
                        f"- **{status}** `{result.block.file}:{result.block.line}` {result.message[:300]}\n"
                    )
    return 1 if counts["FAIL"] or counts["XPASS"] else 0


if __name__ == "__main__":
    sys.exit(main())
