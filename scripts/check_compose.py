#!/usr/bin/env python3
"""Policy checks for the docker compose stacks under docker/.

Renders every docker/<stack>/docker-compose.yml with `docker compose config` and
checks the rules the stacks are expected to follow:

- no obsolete top-level `version:` key and no fixed `container_name`
  (fixed names break running a second, isolated copy of a stack);
- ports are published on 127.0.0.1 by default and follow ES_PORT /
  KIBANA_PORT / BIND_ADDRESS overrides;
- long-running services have a memory limit and a healthcheck;
- one-shot services (`setup`) have a dependent waiting for
  `service_completed_successfully`, so `docker compose up --wait` works;
- password values never appear in a rendered command, entrypoint or
  healthcheck (they must be expanded at runtime from the environment).

Usage: python -m scripts.check_compose [--env-file .env.example]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ONESHOT_SERVICES = {"setup"}
PUBLIC_TARGETS = {9200, 5601}
# Rendered with unique sentinel passwords so a leak is unambiguous to detect.
SENTINELS = {
    "ELASTIC_PASSWORD": "Sentinel-Elastic-Pw-1!",
    "KIBANA_PASSWORD": "Sentinel-Kibana-Pw-2!",
    "OPENSEARCH_INITIAL_ADMIN_PASSWORD": "Sentinel-OpenSearch-Pw-3!",
}
OVERRIDES = {"BIND_ADDRESS": "0.0.0.0", "ES_PORT": "19200", "KIBANA_PORT": "15601"}


def check_raw(text: str) -> list[str]:
    """Checks on the unrendered file."""
    problems = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.startswith("version:"):
            problems.append(f"line {lineno}: obsolete top-level `version:` key")
        if line.strip().startswith("container_name:"):
            problems.append(f"line {lineno}: fixed container_name prevents isolated runs")
    return problems


def check_rendered(config: dict, secrets: list[str], expect_host_ip: str, ports: dict[int, str]) -> list[str]:
    """Checks on the output of `docker compose config --format json`.

    `ports` maps container port -> expected published host port.
    """
    problems = []
    services = config.get("services", {})
    dependents = {name: set() for name in services}
    for name, svc in services.items():
        for dep, cond in (svc.get("depends_on") or {}).items():
            if dep in dependents and cond.get("condition") == "service_completed_successfully":
                dependents[dep].add(name)

    for name, svc in services.items():
        where = f"service `{name}`"
        if name in ONESHOT_SERVICES:
            if not dependents[name]:
                problems.append(f"{where}: one-shot service has no dependent waiting for completion")
        else:
            if not svc.get("mem_limit"):
                problems.append(f"{where}: missing mem_limit")
            if not svc.get("healthcheck", {}).get("test"):
                problems.append(f"{where}: missing healthcheck")

        for port in svc.get("ports") or []:
            target = int(port.get("target", 0))
            if target not in PUBLIC_TARGETS:
                problems.append(f"{where}: unexpected published port {target}")
                continue
            if port.get("host_ip") != expect_host_ip:
                problems.append(f"{where}: port {target} bound to {port.get('host_ip') or '0.0.0.0'}")
            if str(port.get("published")) != ports[target]:
                problems.append(f"{where}: port {target} published on {port.get('published')}, expected {ports[target]}")

        rendered = json.dumps([svc.get("command"), svc.get("entrypoint"), svc.get("healthcheck")])
        for secret in secrets:
            if secret and secret in rendered:
                problems.append(f"{where}: a password value appears in command/entrypoint/healthcheck")
                break

        image = svc.get("image", "")
        if ":" not in image.rsplit("/", 1)[-1] or image.endswith(":latest"):
            problems.append(f"{where}: image `{image}` must use an explicit version tag")
    return problems


def render(compose_file: Path, env_file: Path, extra_env: dict[str, str] | None = None) -> dict:
    cmd = ["docker", "compose", "-f", str(compose_file), "--env-file", str(env_file), "config", "--format", "json"]
    # Process environment takes precedence over --env-file in docker compose.
    env = {**os.environ, **SENTINELS, **(extra_env or {})}
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return json.loads(result.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env.example"))
    args = parser.parse_args(argv)

    if not shutil.which("docker"):
        print("docker is not installed or not on PATH", file=sys.stderr)
        return 2
    env_file = Path(args.env_file).resolve()
    secrets = list(SENTINELS.values())

    failures = 0
    for compose_file in sorted(REPO_ROOT.glob("docker/*/docker-compose.yml")):
        stack = compose_file.parent.name
        try:
            problems = check_raw(compose_file.read_text())
            problems += check_rendered(render(compose_file, env_file), secrets, "127.0.0.1", {9200: "9200", 5601: "5601"})
            overridden = render(compose_file, env_file, OVERRIDES)
            problems += [
                f"with overrides: {p}"
                for p in check_rendered(overridden, secrets, "0.0.0.0", {9200: "19200", 5601: "15601"})
            ]
        except RuntimeError as exc:
            problems = [f"docker compose config failed: {exc}"]
        status = "ok" if not problems else "FAIL"
        print(f"{status:4s} {stack}")
        for problem in problems:
            print(f"     - {problem}")
        failures += bool(problems)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
