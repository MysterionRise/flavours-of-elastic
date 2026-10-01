"""Which cluster to talk to, and with which credentials.

Resolution order (first match wins):

1. `--stack NAME`: the stack registry (scripts/stacks.py) plus `.env`
   (falling back to `.env.example`);
2. `--url` (with `--user`/`--password`/`--no-auth`/`--insecure`), completed
   from the environment exported by `scripts.with_stack`;
3. `ELASTICSEARCH_URL` and friends from the environment;
4. auto-detection: probe localhost with every stack's scheme and credentials
   and keep the first one that answers 200. A 401 is never a match: it only
   means the credentials are wrong.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from search.connection import Client, ConnectionFailed

TRUE = ("1", "true", "yes")


@dataclass(frozen=True)
class Target:
    url: str
    auth: tuple[str, str] | None
    verify: bool
    source: str  # how it was chosen, for messages: "--stack elk-ml", "detected", ...

    def client(self, **kwargs) -> Client:
        return Client(self.url, self.auth, self.verify, **kwargs)

    def describe(self) -> str:
        user = self.auth[0] if self.auth else "no auth"
        return f"{self.url} ({user}, {self.source})"


def resolve(
    *,
    stack: str | None = None,
    url: str | None = None,
    user: str | None = None,
    password: str | None = None,
    no_auth: bool = False,
    insecure: bool = False,
    environ: Mapping[str, str] | None = None,
) -> Target:
    environ = os.environ if environ is None else environ
    if stack:
        return from_stack(stack)
    source = "--url" if url else "environment"
    url = url or environ.get("ELASTICSEARCH_URL")
    if not url:
        return detect()
    if no_auth or environ.get("ELASTIC_NO_AUTH", "").lower() in TRUE:
        auth = None
    else:
        user = user or environ.get("ELASTIC_USER")
        password = password or environ.get("ELASTIC_PASSWORD")
        auth = (user or "elastic", password) if password else None
    verify = not insecure and environ.get("ELASTIC_VERIFY_SSL", "true").lower() in TRUE
    return Target(url.rstrip("/"), auth, verify, source)


def from_stack(name: str) -> Target:
    from scripts.stacks import BASE_ES_PORT, connection, get_stack, load_env

    env = load_env()
    offset = int(env.get("ES_PORT") or BASE_ES_PORT) - BASE_ES_PORT
    conn = connection(get_stack(name), env, port_offset=offset)
    return Target(conn.url, conn.auth, conn.verify, f"--stack {conn.stack.name}")


def candidates() -> list[Target]:
    """One probe per distinct (URL, credentials) pair of the registered stacks."""
    from scripts.stacks import BASE_ES_PORT, STACKS, connection, load_env

    env = load_env()
    offset = int(env.get("ES_PORT") or BASE_ES_PORT) - BASE_ES_PORT
    seen, found = set(), []
    for stack in STACKS.values():
        conn = connection(stack, env, port_offset=offset)
        if (conn.url, conn.auth) in seen:
            continue
        seen.add((conn.url, conn.auth))
        found.append(Target(conn.url, conn.auth, conn.verify, "detected"))
    return found


def detect() -> Target:
    reachable, rejected = set(), []
    for target in candidates():
        try:
            target.client(timeout=5, retries=0).get("/")
        except ConnectionFailed as exc:
            if "rejected the credentials" in str(exc):
                reachable.add(target.url)
                rejected.append(target.auth[0] if target.auth else "no auth")
            continue
        except Exception:  # noqa: BLE001 - any other answer means "not this one"
            reachable.add(target.url)
            continue
        return target
    if rejected:
        raise ConnectionFailed(
            f"{', '.join(sorted(reachable))} answers, but rejected every known login"
            f" ({', '.join(rejected)}). Check the passwords in .env, or pass --user/--password."
        )
    raise ConnectionFailed(
        "No cluster answers on localhost. Start a stack first (e.g. `make up-elk-single`),"
        " or pass --url / --stack."
    )
