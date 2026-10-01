'''Turn Kibana Dev Tools (Console) text into HTTP requests.

Handles what the course uses: several requests per block, `#` / `//` / `/* */`
comments outside JSON strings, Console's triple-quoted strings ("""..."""),
NDJSON bodies (_bulk, _msearch or several JSON values), `kbn:` Kibana API
paths, and bare ES|QL blocks (sent as POST /_query).
'''

from __future__ import annotations

import json
import re
from dataclasses import dataclass

METHOD_LINE = re.compile(
    r"^(?P<method>GET|POST|PUT|DELETE|HEAD|PATCH)\s+(?P<path>\S+)\s*(?:(?:#|//).*)?$"
)
TRIPLE = re.compile(r'"""(.*?)"""', re.DOTALL)
EXPECT_COMMENT = re.compile(r"^\s*(?://|#)\s*→\s*(?P<value>.+)$")


class ConsoleError(ValueError):
    pass


@dataclass
class Request:
    method: str
    path: str
    body: object = None  # dict/list for JSON, str for NDJSON, None for no body
    ndjson: bool = False
    kibana: bool = False
    line: int = 0  # line offset inside the block
    expectation: object = None  # parsed `// → ...` comment, when present


def strip_comments(text: str) -> str:
    """Remove # and // line comments and /* */ blocks outside JSON strings."""
    out, i, in_string, n = [], 0, False, len(text)
    while i < n:
        char = text[i]
        if in_string:
            out.append(char)
            if char == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if char == '"':
                in_string = False
            i += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            i += 1
        elif char == "#" or text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
        else:
            out.append(char)
            i += 1
    return "".join(out)


def json_values(text: str) -> list:
    """Decode a sequence of JSON values (NDJSON or pretty-printed documents back to back)."""
    decoder, values, i = json.JSONDecoder(), [], 0
    text = text.strip()
    while i < len(text):
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        try:
            value, i = decoder.raw_decode(text, i)
        except json.JSONDecodeError as exc:
            snippet = text[max(0, exc.pos - 30) : exc.pos + 30].replace("\n", " ")
            raise ConsoleError(
                f"invalid JSON body near `{snippet}`: {exc.msg}"
            ) from None
        values.append(value)
    return values


def _build(method: str, path: str, raw_body: list[str], line: int) -> Request:
    expectation = None
    kept = []
    for body_line in raw_body:
        match = EXPECT_COMMENT.match(body_line)
        if match:
            value = match["value"].strip()
            try:
                expectation = json.loads(value)
            except json.JSONDecodeError:
                expectation = value
            continue
        kept.append(body_line)
    body_text = "\n".join(kept)
    body_text = TRIPLE.sub(lambda m: json.dumps(m.group(1)), body_text)
    values = json_values(strip_comments(body_text))
    kibana = path.startswith("kbn:")
    path = path[4:] if kibana else path
    path = path if path.startswith("/") else "/" + path
    ndjson = path.split("?")[0].endswith(("_bulk", "_msearch")) or len(values) > 1
    if ndjson:
        body = "".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values)
    else:
        body = values[0] if values else None
    return Request(method, path, body, ndjson, kibana, line, expectation)


def parse_requests(text: str) -> list[Request]:
    """Split a Console block into requests (a body runs until the next method line)."""
    requests, current, body, current_line = [], None, [], 0
    for number, line in enumerate(text.splitlines()):
        match = METHOD_LINE.match(line.strip())
        if match:
            if current:
                requests.append(_build(*current, body, current_line))
            current, body, current_line = (match["method"], match["path"]), [], number
        elif current:
            body.append(line)
    if current:
        requests.append(_build(*current, body, current_line))
    if not requests:
        raise ConsoleError("no request line found")
    return requests


def esql_request(text: str) -> Request:
    query = "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("//")
    ).strip()
    return Request("POST", "/_query", {"query": query})
