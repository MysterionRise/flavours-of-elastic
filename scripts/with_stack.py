"""Run a command against a stack with its connection details in the environment.

    python -m scripts.with_stack elk-ml -- python search/evaluate.py --mode bm25
    python -m scripts.with_stack --attach elk-single -- python data/load_data.py --size small

Without --attach the stack is started in an isolated compose project, the
command runs once it is healthy, and the stack is torn down afterwards. With
--attach it connects to an already running stack (e.g. a student's) instead.

The command sees ELASTICSEARCH_URL, ELASTIC_USER, ELASTIC_PASSWORD,
ELASTIC_VERIFY_SSL, ELASTIC_NO_AUTH, KIBANA_URL and FOE_STACK / FOE_TRACK /
FOE_LICENSE / FOE_CAPABILITIES. Exit code: the command's, or 2 if the stack
could not be started or reached.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from scripts.stacks import StackError, attach, running_stack


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" not in argv:
        print(
            "usage: python -m scripts.with_stack [options] STACK -- COMMAND...",
            file=sys.stderr,
        )
        return 2
    split = argv.index("--")
    own, command = argv[:split], argv[split + 1 :]
    parser = argparse.ArgumentParser(prog="python -m scripts.with_stack")
    parser.add_argument("stack")
    parser.add_argument(
        "--attach", action="store_true", help="use an already running stack"
    )
    parser.add_argument(
        "--keep", action="store_true", help="leave the started stack running"
    )
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--port-offset", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=None)
    parser.add_argument("--logs-dir", type=Path, default=None)
    args = parser.parse_args(own)
    if not command:
        parser.error("no command given after --")

    def run(conn) -> int:
        print(f"[{conn.stack.name}] {conn.url} -> {' '.join(command)}", flush=True)
        return subprocess.call(command, env={**os.environ, **conn.export_env()})

    try:
        if args.attach:
            return run(
                attach(args.stack, env_file=args.env_file, port_offset=args.port_offset)
            )
        with running_stack(
            args.stack,
            keep=args.keep,
            env_file=args.env_file,
            port_offset=args.port_offset,
            timeout=args.timeout,
            logs_dir=args.logs_dir,
        ) as conn:
            return run(conn)
    except StackError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
