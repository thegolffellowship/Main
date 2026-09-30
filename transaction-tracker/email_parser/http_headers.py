"""Download headers that survive any event name (Kerry 2026-09-29: "I just
got an Internal Server Error when I tried to download the PDF for the
Scorecards").

HTTP header values must be latin-1. The scorecards and print-pack file
names carry an em dash ("s9.25 — scorecards.pdf"), and the ASGI bridge
(a2wsgi) raised UnicodeEncodeError while writing the header — a 500 with
the PDF already built. Every Content-Disposition goes through
`content_disposition`: an ASCII `filename=` fallback (dashes → "-",
accents folded, anything else dropped) plus the exact name as RFC 5987
`filename*=UTF-8''…`, which every current browser prefers.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import quote

_DASHES = {"‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
           "‘": "'", "’": "'", "“": "", "”": "", "·": "-"}


def ascii_filename(name: str) -> str:
    s = "".join(_DASHES.get(ch, ch) for ch in str(name or "download"))
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r'["\\\r\n]', "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or "download"


def content_disposition(filename: str, inline: bool = False) -> str:
    """A latin-1-safe Content-Disposition value for any file name."""
    kind = "inline" if inline else "attachment"
    fallback = ascii_filename(filename)
    value = f'{kind}; filename="{fallback}"'
    if fallback != filename:
        value += f"; filename*=UTF-8''{quote(str(filename), safe='')}"
    return value
