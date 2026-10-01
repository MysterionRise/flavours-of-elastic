"""Movie title normalisation for the MovieLens-based dataset (standard library only).

MovieLens writes titles as "Godfather, The (1972)" and appends alternate or
original-language titles in parentheses:
"City of Lost Children, The (Cité des enfants perdus, La) (1995)". The loader
indexes the readable form ("The Godfather") as `title`, keeps alternate titles
in `title_aka` and the untouched MovieLens string in `title_raw`.
"""

from __future__ import annotations

import re

YEAR_SUFFIX = re.compile(r"\s*\((\d{4})\)\s*$")
# Trailing articles MovieLens moves to the end, in the languages present in the data.
ARTICLES = "The A An La Le Les L' Il I Gli Lo Der Die Das Den Det El Los Las Un Une O Os Het De".split()
TRAILING_ARTICLE = re.compile(
    r"^(?P<body>.+), (?P<article>" + "|".join(re.escape(a) for a in ARTICLES) + r")$"
)
AKA_PREFIX = re.compile(r"^a\.k\.a\.\s+", re.IGNORECASE)


def move_article(title: str) -> str:
    """'Godfather, The' -> 'The Godfather'; "Enfer, L'" -> "L'Enfer"; other titles unchanged."""
    match = TRAILING_ARTICLE.match(title.strip())
    if not match:
        return title.strip()
    article, body = match["article"], match["body"]
    return f"{article}{'' if article.endswith(chr(39)) else ' '}{body}"


def _peel_parentheticals(text: str) -> tuple[str, list[str]]:
    """Split trailing '(...)' groups (balanced) off the end of `text`."""
    groups: list[str] = []
    text = text.rstrip()
    while text.endswith(")"):
        depth = 0
        for index in range(len(text) - 1, -1, -1):
            if text[index] == ")":
                depth += 1
            elif text[index] == "(":
                depth -= 1
                if depth == 0:
                    break
        else:
            break  # unbalanced: keep as part of the title
        group = text[index + 1 : -1].strip()
        if index == 0:
            break  # the whole title is parenthesised: keep it
        groups.insert(0, group)
        text = text[:index].rstrip()
    return text, groups


def normalize_title(raw: str) -> tuple[str, list[str]]:
    """Return (title, alternate_titles) for a MovieLens title string. Idempotent."""
    base = YEAR_SUFFIX.sub("", raw).strip()
    main, groups = _peel_parentheticals(base)
    title = move_article(main)
    aka: list[str] = []
    for group in groups:
        alternate = move_article(AKA_PREFIX.sub("", group))
        if alternate and alternate != title and alternate not in aka:
            aka.append(alternate)
    return title, aka
