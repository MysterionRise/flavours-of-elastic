"""Data + search smoke test against a running stack.

Loads the small movies dataset with data/load_data.py, checks the document
count, and runs search/evaluate.py with every mode the stack supports
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
    shown = [
        "***" if prev == "--password" else arg for prev, arg in zip(("",) + args, args)
    ]
    print(f"$ python {' '.join(shown)}", flush=True)
    subprocess.run([sys.executable, *args], cwd=REPO_ROOT, check=True)


def main() -> int:
    url = os.environ["ELASTICSEARCH_URL"]
    capabilities = set(filter(None, os.environ.get("FOE_CAPABILITIES", "").split(",")))
    connect = ["--url", url]
    if os.environ.get("ELASTIC_NO_AUTH", "false").lower() != "true":
        connect += [
            "--user",
            os.environ["ELASTIC_USER"],
            "--password",
            os.environ["ELASTIC_PASSWORD"],
        ]
    if url.startswith("https://"):
        connect.append("--insecure")

    run("data/load_data.py", "--dataset", "movies", "--size", "small", *connect)

    import requests
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    auth = (
        None
        if "--user" not in connect
        else (os.environ["ELASTIC_USER"], os.environ["ELASTIC_PASSWORD"])
    )
    response = requests.get(f"{url}/movies/_count", auth=auth, verify=False, timeout=30)
    response.raise_for_status()
    count = response.json()["count"]
    print(f"movies indexed: {count}", flush=True)
    if count <= 0:
        print("no movies were indexed", file=sys.stderr)
        return 1

    modes = ["bm25"]
    if "dense_vector" in capabilities:
        run(
            "data/load_data.py",
            "--dataset",
            "movies",
            "--size",
            "small",
            "--with-embeddings",
            *connect,
        )
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
