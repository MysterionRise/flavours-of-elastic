"""Data + search smoke test against a running stack.

Loads the small movies dataset with data/load_data.py (which checks that
every document is indexed), and runs search/evaluate.py with every mode the stack supports
(bm25 everywhere; dense with vector support; hybrid_rrf with a trial licence).
Connection details come from the environment exported by scripts.with_stack:

    python -m scripts.with_stack elk-single -- python -m scripts.smoke_data
"""

from __future__ import annotations

import os
import subprocess
import sys

from scripts.stacks import REPO_ROOT


def run(*args: str) -> None:
    print(f"$ python {' '.join(args)}", flush=True)
    subprocess.run([sys.executable, *args], cwd=REPO_ROOT, check=True)


def main() -> int:
    # The loader exits non-zero unless every document is indexed and searchable.
    capabilities = set(filter(None, os.environ.get("FOE_CAPABILITIES", "").split(",")))
    run("data/load_data.py", "--dataset", "movies", "--size", "small")
    modes = ["bm25"]
    if "dense_vector" in capabilities:
        run("data/load_data.py", "--size", "small", "--embeddings", "hash")
        modes.append("dense")
        if "rrf" in capabilities:
            modes.append("hybrid_rrf")
    run(
        "search/evaluate.py",
        "--mode",
        ",".join(modes),
        "--queries",
        "evaluation/movie_queries.yml",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
