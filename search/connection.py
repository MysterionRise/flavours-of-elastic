"""A small requests-based client: retries, timeouts and readable errors.

Every caller (loader, search client, evaluation) talks to Elasticsearch or
OpenSearch through `Client`, so retry/backoff and error reporting live in one
place. Errors keep the engine's own reason (`index_not_found_exception: no
such index [movies]`) instead of a bare HTTP status.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

RETRY_STATUSES = (429, 502, 503, 504)


class ConnectionFailed(RuntimeError):
    """The cluster could not be reached, or it rejected the credentials."""


class EsError(RuntimeError):
    """An error response from the cluster, with the engine's own reason."""

    def __init__(self, status: int, method: str, path: str, payload) -> None:
        self.status, self.method, self.path, self.payload = (
            status,
            method,
            path,
            payload,
        )
        self.error_type, self.reason = error_details(payload)
        super().__init__(f"{method} {path}: HTTP {status}: {self.describe()}")

    def describe(self) -> str:
        if self.error_type or self.reason:
            return ": ".join(part for part in (self.error_type, self.reason) if part)
        return str(self.payload)[:300]


def error_details(payload) -> tuple[str, str]:
    """(type, reason) of an error body, preferring the root cause."""
    if not isinstance(payload, dict):
        return "", str(payload or "")[:300]
    error = payload.get("error")
    if isinstance(error, str):
        return "", error
    if not isinstance(error, dict):
        return "", ""
    causes = error.get("root_cause") or []
    cause = causes[0] if causes and isinstance(causes[0], dict) else error
    return str(cause.get("type", "")), str(cause.get("reason", ""))


@dataclass
class Client:
    url: str
    auth: tuple[str, str] | None = None
    verify: bool = True
    timeout: float = 30
    retries: int = 4
    backoff: float = 1.0
    _session: object = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.url = self.url.rstrip("/")

    @property
    def session(self):
        if self._session is None:
            import requests
            import urllib3

            if not self.verify:
                # The TLS stacks use a self-signed CA that lives inside a Docker volume.
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            session = requests.Session()
            session.auth = self.auth
            session.verify = self.verify
            self._session = session
        return self._session

    def request(
        self,
        method: str,
        path: str,
        body=None,
        *,
        ndjson: str | None = None,
        params: dict | None = None,
        ok: tuple[int, ...] = (),
        timeout: float | None = None,
    ):
        """Send a request and return the decoded JSON body.

        Retries 429/5xx and connection errors with exponential backoff. Statuses
        listed in `ok` (e.g. 404 for an existence check) are returned instead of
        raised; any other non-2xx status raises `EsError`.
        """
        import requests

        kwargs: dict = {"params": params, "timeout": timeout or self.timeout}
        if ndjson is not None:
            kwargs["data"] = ndjson.encode("utf-8")
            kwargs["headers"] = {"Content-Type": "application/x-ndjson"}
        elif body is not None:
            kwargs["json"] = body
        target = f"{self.url}/{path.lstrip('/')}"
        for attempt in range(self.retries + 1):
            try:
                response = self.session.request(method, target, **kwargs)
            except requests.exceptions.SSLError as exc:
                raise ConnectionFailed(
                    f"TLS verification failed for {self.url} (self-signed CA?):"
                    " pass --insecure or set ELASTIC_VERIFY_SSL=false"
                ) from exc
            except requests.ConnectionError as exc:
                if attempt == self.retries:
                    raise ConnectionFailed(f"cannot reach {self.url}: {exc}") from exc
            else:
                if (
                    response.status_code not in RETRY_STATUSES
                    or attempt == self.retries
                ):
                    break
            time.sleep(self.backoff * 2**attempt)
        payload = decode(response)
        if response.status_code == 401:
            raise ConnectionFailed(
                f"{self.url} rejected the credentials"
                f" (user {self.auth[0] if self.auth else 'none'}): {error_details(payload)[1]}"
            )
        if response.status_code >= 300 and response.status_code not in ok:
            raise EsError(response.status_code, method, path, payload)
        return payload

    def get(self, path: str, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path: str, body=None, **kwargs):
        return self.request("POST", path, body, **kwargs)

    def put(self, path: str, body=None, **kwargs):
        return self.request("PUT", path, body, **kwargs)

    def delete(self, path: str, **kwargs):
        return self.request("DELETE", path, **kwargs)

    def exists(self, path: str) -> bool:
        return self.request("HEAD", path, ok=(404,)) is not None


def decode(response):
    """JSON body, raw text for non-JSON bodies, None for empty or 404 HEAD bodies."""
    if response.request.method == "HEAD":
        return None if response.status_code == 404 else {}
    if not response.content:
        return {}
    try:
        return response.json()
    except (ValueError, json.JSONDecodeError):
        return response.text
