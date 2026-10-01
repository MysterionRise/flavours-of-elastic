"""Registry of the docker compose stacks and helpers to run them in isolation.

Single source of truth for validate.py, CI, the data loaders and the course
snippet runner. Importing this module needs only the standard library;
`requests` is imported lazily by the functions that talk to a cluster.

    python -m scripts.stacks list [--json]       # what CI builds its matrix from
    python -m scripts.stacks env elk-ml           # connection variables for a stack
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_ES_PORT = 9200
BASE_UI_PORT = 5601


class StackError(RuntimeError):
    """A stack could not be started, reached or authenticated."""


def default_env_file() -> Path:
    """`.env` when present, otherwise the committed `.env.example` defaults."""
    env_file = REPO_ROOT / ".env"
    return env_file if env_file.exists() else REPO_ROOT / ".env.example"


def load_env(path: Path | None = None) -> dict[str, str]:
    """Parse a docker-compose style env file; the process environment wins.

    Mirrors compose's precedence: for keys present in the file, a value in
    os.environ overrides it. Comments, blank lines and `export ` are handled;
    no variable interpolation is performed.
    """
    path = Path(path) if path else default_env_file()
    values: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[key] = value
    return {key: os.environ.get(key, value) for key, value in values.items()}


@dataclass(frozen=True)
class Stack:
    name: str  # == docker/<name>
    title: str
    distribution: str  # "elasticsearch" | "opensearch" | "elasticsearch-oss"
    version_var: str
    nodes: int
    scheme: str  # "http" | "https"
    user: str | None  # None: no authentication
    password_var: str | None
    licence_var: str | None  # None: no _license API
    licence_default: str | None
    ui_kind: str  # "kibana" | "dashboards" | "kibana-oss"
    course_days: tuple[int, ...] = ()
    aliases: tuple[str, ...] = ()
    oneshot_services: tuple[str, ...] = ()
    min_ml_memory_gib: float = 0.0
    startup_timeout: int = 600
    frozen: bool = False
    ci: bool = True

    @property
    def compose_file(self) -> Path:
        return REPO_ROOT / "docker" / self.name / "docker-compose.yml"

    def project(self, purpose: str = "validate") -> str:
        return f"foe-{purpose}-{self.name}"

    def licence(self, env: Mapping[str, str]) -> str | None:
        if not self.licence_var:
            return None
        return env.get(self.licence_var) or self.licence_default

    def capabilities(self, env: Mapping[str, str]) -> frozenset[str]:
        if self.distribution == "opensearch":
            return frozenset({"os_knn"})
        if self.distribution == "elasticsearch-oss":
            return frozenset()
        caps = {"esql", "dense_vector"}
        if self.licence(env) in ("trial", "platinum", "enterprise"):
            caps |= {"ml", "rrf", "semantic_text"}
        return frozenset(caps)

    def describe(self, env: Mapping[str, str], port_offset: int = 0) -> dict:
        """JSON-safe description (never contains password values)."""
        version = env.get(self.version_var, "")
        return {
            "name": self.name,
            "title": self.title,
            "compose_file": str(self.compose_file.relative_to(REPO_ROOT)),
            "project": self.project(),
            "distribution": self.distribution,
            "version_var": self.version_var,
            "version": version,
            "track": ".".join(version.split(".")[:2]),
            "nodes": self.nodes,
            "url": f"{self.scheme}://localhost:{BASE_ES_PORT + port_offset}",
            "verify_tls": False,
            "auth": {"user": self.user, "password_var": self.password_var}
            if self.user
            else None,
            "licence": self.licence(env),
            "licence_var": self.licence_var,
            "capabilities": sorted(self.capabilities(env)),
            "ui": {
                "kind": self.ui_kind,
                "url": f"http://localhost:{BASE_UI_PORT + port_offset}",
            },
            "course_days": list(self.course_days),
            "ci": self.ci,
            "frozen": self.frozen,
            "aliases": list(self.aliases),
        }


_ELASTIC = dict(
    user="elastic",
    password_var="ELASTIC_PASSWORD",
    ui_kind="kibana",
    oneshot_services=("setup",),
)
_OPENSEARCH = dict(
    distribution="opensearch",
    nodes=2,
    scheme="https",
    user="admin",
    password_var="OPENSEARCH_INITIAL_ADMIN_PASSWORD",
    licence_var=None,
    licence_default=None,
    ui_kind="dashboards",
)

STACKS: dict[str, Stack] = {
    stack.name: stack
    for stack in (
        Stack(
            name="elk-single",
            title="Elastic Single",
            distribution="elasticsearch",
            version_var="ELK_VERSION",
            nodes=1,
            scheme="http",
            licence_var="LICENSE",
            licence_default="basic",
            course_days=(1, 2, 3),
            **_ELASTIC,
        ),
        Stack(
            name="elk-9",
            title="Elastic 9",
            distribution="elasticsearch",
            version_var="ELK9_VERSION",
            nodes=1,
            scheme="http",
            licence_var="LICENSE",
            licence_default="basic",
            course_days=(1, 2, 3),
            **_ELASTIC,
        ),
        Stack(
            name="elk",
            title="Elastic Stack",
            distribution="elasticsearch",
            version_var="ELK_VERSION",
            nodes=2,
            scheme="https",
            licence_var="LICENSE",
            licence_default="basic",
            aliases=("elastic",),
            **_ELASTIC,
        ),
        Stack(
            name="elk-ml",
            title="Elastic ML",
            distribution="elasticsearch",
            version_var="ELK_VERSION",
            nodes=2,
            scheme="https",
            licence_var="ELK_ML_LICENSE",
            licence_default="trial",
            course_days=(4,),
            min_ml_memory_gib=1.5,
            **_ELASTIC,
        ),
        Stack(
            name="elk-ml-9",
            title="Elastic ML 9",
            distribution="elasticsearch",
            version_var="ELK9_VERSION",
            nodes=2,
            scheme="https",
            licence_var="ELK_ML_LICENSE",
            licence_default="trial",
            course_days=(4,),
            min_ml_memory_gib=1.5,
            **_ELASTIC,
        ),
        Stack(
            name="opensearch",
            title="OpenSearch",
            version_var="OPENSEARCH_VERSION",
            **_OPENSEARCH,
        ),
        Stack(
            name="opensearch-3",
            title="OpenSearch 3",
            version_var="OPENSEARCH3_VERSION",
            **_OPENSEARCH,
        ),
        Stack(
            name="elk-oss",
            title="Elasticsearch OSS",
            distribution="elasticsearch-oss",
            version_var="ELK_OSS_VERSION",
            nodes=2,
            scheme="http",
            user=None,
            password_var=None,
            licence_var=None,
            licence_default=None,
            ui_kind="kibana-oss",
            frozen=True,
        ),
    )
}


def get_stack(name: str) -> Stack:
    """Look a stack up by name or alias (e.g. `elastic` -> `elk`)."""
    if name in STACKS:
        return STACKS[name]
    for stack in STACKS.values():
        if name in stack.aliases:
            return stack
    raise StackError(f"Unknown stack '{name}'. Known: {', '.join(STACKS)}")


@dataclass
class Connection:
    """How to reach a running stack."""

    stack: Stack
    url: str
    ui_url: str
    auth: tuple[str, str] | None
    verify: bool
    version: str
    licence: str | None
    capabilities: frozenset[str]
    project: str | None
    env: dict[str, str] = field(repr=False)

    def session(self):
        import requests
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        session = requests.Session()
        session.auth = self.auth
        session.verify = self.verify
        return session

    def export_env(self) -> dict[str, str]:
        """Variables understood by the data loaders, the search client and the course runner."""
        exported = {
            "ELASTICSEARCH_URL": self.url,
            "ELASTIC_VERIFY_SSL": "true" if self.verify else "false",
            "KIBANA_URL": self.ui_url,
            "FOE_STACK": self.stack.name,
            "FOE_STACK_VERSION": self.version,
            "FOE_TRACK": ".".join(self.version.split(".")[:2]),
            "FOE_LICENSE": self.licence or "",
            "FOE_CAPABILITIES": ",".join(sorted(self.capabilities)),
        }
        if self.auth:
            exported.update(
                ELASTIC_USER=self.auth[0],
                ELASTIC_PASSWORD=self.auth[1],
                ELASTIC_NO_AUTH="false",
            )
        else:
            exported["ELASTIC_NO_AUTH"] = "true"
        return exported


def connection(
    stack: Stack,
    env: Mapping[str, str],
    port_offset: int = 0,
    project: str | None = None,
) -> Connection:
    auth = (stack.user, env.get(stack.password_var or "", "")) if stack.user else None
    return Connection(
        stack=stack,
        url=f"{stack.scheme}://localhost:{BASE_ES_PORT + port_offset}",
        ui_url=f"http://localhost:{BASE_UI_PORT + port_offset}",
        auth=auth,
        verify=False,  # the TLS stacks use a self-signed CA that lives inside a Docker volume
        version=env.get(stack.version_var, ""),
        licence=stack.licence(env),
        capabilities=stack.capabilities(env),
        project=project,
        env=dict(env),
    )


def compose_cmd(stack: Stack, *args: str, env_file: Path, project: str) -> list[str]:
    return [
        "docker",
        "compose",
        "-p",
        project,
        "-f",
        str(stack.compose_file),
        "--env-file",
        str(env_file),
        *args,
    ]


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _child_env(port_offset: int) -> dict[str, str]:
    env = dict(os.environ)
    if port_offset:
        env["ES_PORT"] = str(BASE_ES_PORT + port_offset)
        env["KIBANA_PORT"] = str(BASE_UI_PORT + port_offset)
    return env


def _run(
    cmd: list[str], env: dict[str, str], timeout: int | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, capture_output=True, text=True, env=env, timeout=timeout, check=False
    )


def preflight(stack: Stack, env_file: Path, port_offset: int = 0) -> None:
    if not shutil.which("docker"):
        raise StackError("docker is not installed or not on PATH")
    if _run(["docker", "compose", "version"], dict(os.environ)).returncode != 0:
        raise StackError("`docker compose` (the Compose v2 plugin) is not available")
    if not env_file.exists():
        raise StackError(f"env file not found: {env_file}")
    ports = (BASE_ES_PORT + port_offset, BASE_UI_PORT + port_offset)
    deadline = (
        time.monotonic() + 30
    )  # Docker port forwarders release ports asynchronously after `down`
    while busy := [port for port in ports if _port_in_use(port)]:
        if time.monotonic() > deadline:
            raise StackError(
                f"port {busy[0]} is already in use - stop the stack that holds it, or pass --port-offset 10000"
            )
        time.sleep(2)
    if sys.platform.startswith("linux") and stack.nodes > 1:
        try:
            if int(Path("/proc/sys/vm/max_map_count").read_text()) < 262144:
                raise StackError(
                    "vm.max_map_count is below 262144: sudo sysctl -w vm.max_map_count=262144"
                )
        except (OSError, ValueError):
            pass


def _only_oneshots_exited_cleanly(stack: Stack, ps_json: str) -> bool:
    """Fallback for compose versions where `up --wait` fails on an exited one-shot service."""
    rows = []
    for line in ps_json.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parsed = json.loads(line)
        rows.extend(parsed if isinstance(parsed, list) else [parsed])
    if not rows:
        return False
    for row in rows:
        if row.get("Service") in stack.oneshot_services:
            if row.get("State") != "exited" or int(row.get("ExitCode", 1)) != 0:
                return False
        elif row.get("State") != "running" or row.get("Health") not in ("", "healthy"):
            return False
    return True


def dump_logs(
    stack: Stack, env_file: Path, project: str, logs_dir: Path | None = None
) -> None:
    child = dict(os.environ)
    ps = _run(compose_cmd(stack, "ps", "-a", env_file=env_file, project=project), child)
    logs = _run(
        compose_cmd(
            stack,
            "logs",
            "--no-color",
            "--tail",
            "300",
            env_file=env_file,
            project=project,
        ),
        child,
    )
    text = (
        f"$ docker compose ps -a\n{ps.stdout}{ps.stderr}\n"
        f"$ docker compose logs --tail 300\n{logs.stdout}{logs.stderr}"
    )
    print(text[-20000:])
    if logs_dir:
        logs_dir.mkdir(parents=True, exist_ok=True)
        (logs_dir / f"{stack.name}.log").write_text(text)


def wait_until_ready(conn: Connection, timeout: int = 120) -> None:
    """Poll GET / with the stack's credentials. A 401 is never treated as ready."""
    import requests

    session = conn.session()
    deadline = time.monotonic() + timeout
    last = "no response"
    while time.monotonic() < deadline:
        try:
            response = session.get(conn.url, timeout=10)
            if response.status_code == 200:
                return
            last = f"HTTP {response.status_code}"
        except requests.RequestException as exc:
            last = type(exc).__name__
        time.sleep(3)
    hint = (
        " (credentials rejected - check the password in your env file)"
        if last == "HTTP 401"
        else ""
    )
    raise StackError(
        f"{conn.stack.name} not ready at {conn.url} after {timeout}s: {last}{hint}"
    )


@contextmanager
def running_stack(
    name: str,
    *,
    keep: bool = False,
    keep_volumes: bool = False,
    env_file: Path | None = None,
    project: str | None = None,
    port_offset: int = 0,
    timeout: int | None = None,
    logs_dir: Path | None = None,
) -> Iterator[Connection]:
    """Start a stack in its own compose project, wait until healthy, always tear down.

    The project defaults to `foe-validate-<stack>`, so a student's stack started
    from the same compose file (project `<stack>`) and its volumes are never touched.
    """
    stack = get_stack(name)
    env_file = Path(env_file) if env_file else default_env_file()
    project = project or stack.project()
    timeout = timeout or stack.startup_timeout
    child = _child_env(port_offset)
    env = load_env(env_file)
    preflight(stack, env_file, port_offset)

    def compose(*args: str, limit: int | None = None) -> subprocess.CompletedProcess:
        return _run(
            compose_cmd(stack, *args, env_file=env_file, project=project), child, limit
        )

    compose(
        "down", "-v", "--remove-orphans"
    )  # leftovers from a crashed run of this tool
    started = False
    try:
        print(f"[{stack.name}] starting (project {project})...", flush=True)
        try:
            up = compose(
                "up",
                "-d",
                "--wait",
                "--wait-timeout",
                str(timeout),
                limit=timeout + 300,
            )
        except subprocess.TimeoutExpired as exc:
            raise StackError(
                f"{stack.name}: `docker compose up` did not return within {timeout + 300}s"
            ) from exc
        started = True
        if up.returncode != 0:
            ps = compose("ps", "-a", "--format", "json")
            if not _only_oneshots_exited_cleanly(stack, ps.stdout):
                raise StackError(
                    f"{stack.name}: `docker compose up --wait` failed:\n{(up.stdout + up.stderr)[-3000:]}"
                )
        conn = connection(stack, env, port_offset, project)
        wait_until_ready(conn)
        yield conn
    except BaseException:
        if started:
            dump_logs(stack, env_file, project, logs_dir)
        raise
    finally:
        if not keep:
            args = ["down", "--remove-orphans"] + ([] if keep_volumes else ["-v"])
            compose(*args, limit=300)


def attach(
    name: str, *, env_file: Path | None = None, port_offset: int = 0
) -> Connection:
    """Connect to a stack that is already running (e.g. a student's); no lifecycle management."""
    stack = get_stack(name)
    env_file = Path(env_file) if env_file else default_env_file()
    conn = connection(stack, load_env(env_file), port_offset)
    wait_until_ready(conn, timeout=60)
    return conn


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stack registry for flavours-of-elastic"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    list_cmd = sub.add_parser("list", help="list the registered stacks")
    list_cmd.add_argument("--json", action="store_true")
    env_cmd = sub.add_parser(
        "env", help="print connection variables for a stack (passwords omitted)"
    )
    env_cmd.add_argument("stack")
    for cmd in (list_cmd, env_cmd):
        cmd.add_argument("--env-file", type=Path, default=None)
    args = parser.parse_args(argv)
    env = load_env(args.env_file)

    if args.cmd == "list":
        described = [stack.describe(env) for stack in STACKS.values()]
        if args.json:
            print(json.dumps(described, indent=2))
        else:
            for item in described:
                print(
                    f"{item['name']:13s} {item['distribution']:18s} {item['version']:8s} {item['url']}"
                )
        return 0
    exported = connection(get_stack(args.stack), env).export_env()
    exported.pop("ELASTIC_PASSWORD", None)
    for key, value in exported.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
