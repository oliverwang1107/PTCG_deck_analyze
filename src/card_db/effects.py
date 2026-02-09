from __future__ import annotations

import re
from typing import Iterable


def normalize_text(text: str | None) -> str | None:
    """Normalize effect text for easier parsing."""
    if text is None:
        return None
    t = text.replace("\r", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    t = t.strip()
    return t or None


def split_into_instructions(text: str | None) -> list[str]:
    """
    Heuristic to split a skill/ability text into actionable instructions.
    Not perfect, but creates smaller units for downstream LLM/refinement.
    """
    t = normalize_text(text)
    if not t:
        return []

    # Split by strong punctuation first.
    parts: list[str] = re.split(r"[。；;]\s*|\n+", t)

    # Further split on connective phrases that often join two actions.
    refined: list[str] = []
    connectors = ["若", "如果", "則", "接著", "然後", "此外"]
    for p in parts:
        p = p.strip(" 。；;")
        if not p:
            continue
        # If very short or already simple, keep as is.
        if len(p) <= 12:
            refined.append(p)
            continue
        # Try to split on "，" when followed by a connector.
        chunks = re.split(r"，(?=(?:若|如果|則|接著|然後|此外))", p)
        for c in chunks:
            c = c.strip(" ，")
            if c:
                refined.append(c)

    # Clean leftovers and deduplicate consecutive duplicates.
    cleaned: list[str] = []
    last = None
    for r in refined:
        r = r.strip()
        if not r:
            continue
        if r == last:
            continue
        cleaned.append(r)
        last = r
    return cleaned

