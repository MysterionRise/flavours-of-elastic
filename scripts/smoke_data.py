"""Data + search smoke test against a running stack.

Loads the small movies dataset with data/load_data.py (which checks that
every document is indexed), and runs search/evaluate.py with every mode the stack supports
(bm25 everywhere; dense and hybrid_rrf with vector support; E5, ELSER and
three-way hybrid on the ML stacks), and fails when a mode errors or scores
below evaluation/floors.yml.
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
    if "ml" in capabilities:
        # In-cluster E5 vectors and ELSER (downloads and deploys both models).
        run(
            "data/load_data.py", "--size", "small", "--embeddings", "e5", "--with-elser"
        )
        modes += ["dense", "hybrid_rrf", "elser", "hybrid_all"]
    elif capabilities & {"dense_vector", "os_knn"}:
        run("data/load_data.py", "--size", "small", "--embeddings", "hash")
        # hybrid_rrf: the rrf retriever on a trial licence, client-side fusion otherwise.
        modes += ["dense", "hybrid_rrf"]
    run(
        "search/evaluate.py",
        "--mode",
        ",".join(modes),
        "--queries",
        "evaluation/movie_queries.yml",
        "--fail-under",
        "evaluation/floors.yml",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
