"""Plain text from cached EDGAR HTML. Stdlib only."""
from __future__ import annotations

import html
import pathlib
import re
from html.parser import HTMLParser

from .fetch import RAW

BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table", "td", "th"}


class _P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in BLOCK:
            self.out.append("\n" if tag not in ("td", "th") else " | ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def to_text(raw: str) -> str:
    p = _P()
    p.feed(raw)
    t = html.unescape("".join(p.out)).replace("\xa0", " ").replace("​", "")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\s*\n\s*", "\n", t)
    return t.strip()


def doc_text(name: str) -> str:
    """Text of a cached document under data/raw/edgar."""
    return to_text((RAW / "edgar" / name).read_text(errors="replace"))


def edgar_url(name: str) -> str:
    import json
    return json.loads((RAW / "edgar" / (name + ".meta.json")).read_text())["url"]


def cached(pattern: str = "*.htm") -> list[pathlib.Path]:
    return sorted((RAW / "edgar").glob(pattern))
