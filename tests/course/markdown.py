"""Extract fenced code blocks from the Marp course decks.

Each block keeps its file, line, slide number, nearest heading, exercise task
and fence attributes. Annotations live in the fence info-string, which Marp
and GitHub ignore after the first word:

    ```json expect=404 track=9 requires=trial test=skip
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

FENCE = re.compile(r"^(?P<quote>(?:>\s?)*)(?P<fence>`{3,})(?P<info>[^`]*)$")
HEADING = re.compile(r"^#{1,6}\s+(?P<text>.+?)\s*#*\s*$")
TASK = re.compile(r"\bTask\s+(?P<n>\d+)\b", re.IGNORECASE)
METHOD = re.compile(r"^(GET|POST|PUT|DELETE|HEAD|PATCH)\s+\S+")
ESQL_START = re.compile(r"^(FROM|ROW|SHOW|TS)\b")
KNOWN_KEYS = {
    "test",
    "expect",
    "min",
    "top",
    "contains",
    "track",
    "requires",
    "timeout",
    "id",
}


@dataclass
class Block:
    file: str
    line: int  # 1-based line of the opening fence
    slide: int
    heading: str
    task: str | None
    lang: str
    attrs: dict[str, str]
    text: str
    index: int = 0  # position among the blocks under the same heading
    errors: list[str] = field(default_factory=list)

    @property
    def deck(self) -> str:
        return Path(self.file).stem

    @property
    def id(self) -> str:
        if "id" in self.attrs:
            return f"{self.deck}/{self.attrs['id']}"
        return f"{self.deck}/{slug(self.heading)}/{self.index}"

    @property
    def kind(self) -> str:
        lines = [line.strip() for line in self.text.splitlines()]
        first = next(
            (line for line in lines if line and not line.startswith(("#", "//"))), ""
        )
        if self.lang in ("bash", "sh", "shell", "console"):
            return "shell"
        if METHOD.match(first):
            return "request"
        if self.lang in ("sql", "esql") or ESQL_START.match(first):
            return "esql"
        return "other"


def slug(text: str) -> str:
    text = re.sub(r"[`*_]", "", text.lower())
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "untitled"


def parse_info(info: str) -> tuple[str, dict[str, str], list[str]]:
    words = info.split()
    lang = words[0] if words and "=" not in words[0] else ""
    attrs, errors = {}, []
    for word in words[1 if lang else 0 :]:
        key, sep, value = word.partition("=")
        if not sep or key not in KNOWN_KEYS:
            errors.append(f"unknown fence annotation `{word}`")
            continue
        attrs[key] = value
    return lang, attrs, errors


def extract_blocks(path: Path, root: Path | None = None) -> list[Block]:
    lines = path.read_text(encoding="utf-8").splitlines()
    name = str(path.relative_to(root)) if root else str(path)
    blocks: list[Block] = []
    slide, heading, task = 1, "", None
    i = 0
    if lines and lines[0].strip() == "---":  # Marp front matter
        i = next((n for n in range(1, len(lines)) if lines[n].strip() == "---"), 0) + 1
    seen: dict[str, int] = {}
    while i < len(lines):
        line = lines[i]
        match = FENCE.match(line)
        if match:
            quote, fence = match["quote"], match["fence"]
            lang, attrs, errors = parse_info(match["info"])
            body, j = [], i + 1
            while j < len(lines):
                inner = lines[j]
                if quote and inner.startswith(quote.rstrip()):
                    inner = inner[len(quote.rstrip()) :]
                    inner = inner[1:] if inner.startswith(" ") else inner
                if inner.strip().startswith(fence) and inner.strip().strip("`") == "":
                    break
                body.append(inner)
                j += 1
            key = slug(heading)
            block = Block(
                name,
                i + 1,
                slide,
                heading,
                task,
                lang,
                attrs,
                "\n".join(body),
                seen.get(key, 0),
                errors,
            )
            seen[key] = block.index + 1
            blocks.append(block)
            i = j + 1
            continue
        stripped = line.strip()
        if stripped == "---":
            slide += 1
        elif heading_match := HEADING.match(stripped):
            heading = heading_match["text"]
            task_match = TASK.search(heading)
            if task_match:
                task = task_match["n"]
            elif re.match(r"^(cleanup|clean up)\b", heading, re.IGNORECASE):
                task = "cleanup"
        i += 1
    return blocks
