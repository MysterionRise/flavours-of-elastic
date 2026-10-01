"""Check that docs reference the stack versions pinned in .env.example.

Docs name minor versions only (`8.19.x`, `9.5.x`, `2.19.x`, `3.9.x`); exact
patch versions live only in .env.example. So a Renovate patch bump changes
nothing here, while a minor bump (e.g. 9.5 -> 9.6) fails this check until the
docs - and the course content for that release - have been reviewed.

Rules (the major version selects the track; the tracks have distinct majors):
  A  `X.Y.x` tokens must use the minor from .env.example;
  B  no exact `X.Y.Z` versions next to a product name (write `X.Y.x`);
     the frozen OSS release 7.10.2 is the only exception;
  C  `Elasticsearch|Kibana|OpenSearch X.Y` must use the current minor, unless
     it is clearly historical ("since 8.14", "8.14+", ...).

    python -m scripts.check_doc_versions          # report
    python -m scripts.check_doc_versions --fix    # rewrite minors / exact versions in place
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from scripts.stacks import REPO_ROOT, load_env

TRACKS = {
    8: "ELK_VERSION",
    9: "ELK9_VERSION",
    2: "OPENSEARCH_VERSION",
    3: "OPENSEARCH3_VERSION",
}
FROZEN = {7: "ELK_OSS_VERSION"}
DOC_GLOBS = (
    "README.md",
    "CLAUDE.md",
    "data/README.md",
    "course/**/*.md",
    "docs/**/*.md",
)
PRODUCT = r"(?:Elasticsearch|Kibana|Elastic|ELK|OpenSearch|Dashboards)"
HISTORICAL = re.compile(
    r"(since|from|in|before|until|introduced|added|deprecated|removed|as of)\s*$", re.I
)

RULE_A = re.compile(r"\b(\d+)\.(\d+)\.x\b")
RULE_B = re.compile(PRODUCT + r"[^\n]{0,25}?\b(\d+)\.(\d+)\.(\d+)\b")
RULE_C = re.compile(r"\b(?:Elasticsearch|Kibana|OpenSearch)\s+v?(\d+)\.(\d+)(?![.\d+])")


def minors(env: dict[str, str]) -> dict[int, str]:
    """major -> current minor, e.g. {8: "19", 9: "5", ...}."""
    result = {}
    for major, var in TRACKS.items():
        parts = env.get(var, "").split(".")
        if len(parts) >= 2 and parts[0] == str(major):
            result[major] = parts[1]
    return result


def check_text(
    text: str, current: dict[int, str], frozen: dict[int, str]
) -> list[tuple[int, str, str, str]]:
    """Return (line, message, old, new) for every violation; `new` is the --fix replacement."""
    problems = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for match in RULE_A.finditer(line):
            major, minor = int(match.group(1)), match.group(2)
            if major in current and minor != current[major]:
                expected = f"{major}.{current[major]}.x"
                problems.append(
                    (
                        lineno,
                        f"`{match.group(0)}` should be `{expected}`",
                        match.group(0),
                        expected,
                    )
                )
        for match in RULE_B.finditer(line):
            major = int(match.group(1))
            version = ".".join(match.group(i) for i in (1, 2, 3))
            if major in frozen and version == frozen[major]:
                continue
            if major in current:
                expected = f"{major}.{current[major]}.x"
                problems.append(
                    (
                        lineno,
                        f"exact version `{version}`: write `{expected}`",
                        version,
                        expected,
                    )
                )
        for match in RULE_C.finditer(line):
            major, minor = int(match.group(1)), match.group(2)
            if major not in current or minor == current[major]:
                continue
            if HISTORICAL.search(line[: match.start()]):
                continue
            old = f"{major}.{minor}"
            expected = f"{major}.{current[major]}"
            text_old = match.group(0)
            message = f"`{text_old}` should mention {expected}"
            problems.append(
                (lineno, message, text_old, text_old.replace(old, expected))
            )
    return problems


def doc_files() -> list[Path]:
    files = set()
    for pattern in DOC_GLOBS:
        files.update(p for p in REPO_ROOT.glob(pattern) if p.is_file())
    return sorted(files)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check doc version references against .env.example"
    )
    parser.add_argument(
        "--fix", action="store_true", help="rewrite offending versions in place"
    )
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env.example")
    args = parser.parse_args(argv)

    env = load_env(args.env_file)
    current = minors(env)
    frozen = {major: env.get(var, "") for major, var in FROZEN.items()}
    in_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    total = 0
    for path in doc_files():
        text = path.read_text(encoding="utf-8")
        problems = check_text(text, current, frozen)
        if not problems:
            continue
        rel = path.relative_to(REPO_ROOT)
        if args.fix:
            lines = text.splitlines(keepends=True)
            for lineno, _, old, new in problems:
                lines[lineno - 1] = lines[lineno - 1].replace(old, new, 1)
            path.write_text("".join(lines), encoding="utf-8")
            print(f"fixed {len(problems)} reference(s) in {rel}")
            continue
        for lineno, message, _, _ in problems:
            total += 1
            print(
                f"::error file={rel},line={lineno}::{message}"
                if in_ci
                else f"{rel}:{lineno}: {message}"
            )
    if total:
        print(
            f"\n{total} outdated version reference(s); run `python -m scripts.check_doc_versions --fix`"
        )
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
