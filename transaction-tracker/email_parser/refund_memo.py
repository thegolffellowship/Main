"""REFUND MEMOS (Kerry 2026-10-28, Event Ops #2475-2 corrected by #2476-4).

Kerry, verbatim: "Memo would say Refund for San Antonio Fall Points Race in
that particular situation. It's the [What] for [Event or Season Contest
name]".

Every refund the Tracker starts pre-fills the Venmo / PayPal / Cash App note
as "<What> for <Event or Season Contest name>":
    Refund for San Antonio Fall Points Race
    Refund for a9.29 Teravista
Not all caps, not pipe-separated. Kerry 10/30 put the player's name back in
front: "Jeff Young - Refund for s9.28 TPC Canyons". One helper here
for the server (get_refunds_overview) and its twin `refundMemo` in
static/js/refund-memo.js for the pages that build the note in the browser
(customers.html Refund modal + apply-credit excess, events.html excess,
tgf.html Refunds console fallback). Guard: test_refund_memo.py.
"""
from __future__ import annotations

import re

_CODE = re.compile(r"^[a-z]+\d+(?:\.\d+)?$", re.I)
# Kept upper case when an ALL-CAPS name is cased ("TPC Canyons", "TGF Championship")
_ACRONYMS = {"TPC", "TGF", "LSC", "MVP", "CC", "GC", "HIO", "PGA"}


def display_name(name) -> str:
    """The event or contest name as a person writes it: spaces collapsed,
    and an ALL-CAPS name ("SAN ANTONIO FALL POINTS RACE") title-cased with
    event codes ("A9.29") lower-cased. A mixed-case name is left alone."""
    s = " ".join(str(name or "").split())
    # A leading event code ("s9.28") is lower case by design and must not
    # stop an ALL-CAPS name after it from being cased: "s9.28 TPC CANYONS"
    # reads "s9.28 TPC Canyons" (Kerry 10/30, the TPC member credits).
    words = s.split(" ")
    if len(words) > 1 and _CODE.match(words[0]):
        rest = " ".join(words[1:])
        return words[0].lower() + " " + display_name(rest)
    if not s or not any(ch.isalpha() for ch in s) or s != s.upper():
        return s
    out = []
    for w in s.split(" "):
        if _CODE.match(w):
            out.append(w.lower())
        elif w in _ACRONYMS:
            out.append(w)
        elif any(ch.isdigit() for ch in w):
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:].lower())
    return " ".join(out)


def refund_memo(what: str = "Refund", name: str = "", player: str = "") -> str:
    """"<First> <Last> - <What> for <name>", e.g. refund_memo("Refund",
    "s9.28 TPC CANYONS", "Jeff Young") -> "Jeff Young - Refund for s9.28 TPC
    Canyons" (Kerry 10/30: "They all should be including the [First Name]
    [Last Name] - [What]..."). Without a player it is "<What> for <name>"."""
    w = " ".join(str(what or "").split()) or "Refund"
    n = display_name(name)
    body = f"{w} for {n}" if n else w
    p = player_name(player)
    return f"{p} - {body}" if p else body


def player_name(name) -> str:
    """"First Last": a stored "YOUNG, Jeff" is turned round; spaces collapsed."""
    s = " ".join(str(name or "").split())
    if "," in s:
        last, first = (x.strip() for x in s.split(",", 1))
        s = f"{first} {last.title() if last.isupper() else last}".strip()
    return s


def contest_name(contest_type: str = "", chapter: str = "", season: str = "",
                 item_name: str = "") -> str:
    """A season contest's name for a memo: the product the player bought
    (e.g. "San Antonio Fall Points Race") when known, else chapter +
    contest + season ("San Antonio NET Points Race 2026"); a leading "City"
    is dropped as the old removal memo did."""
    if (item_name or "").strip():
        return display_name(item_name)
    ct = re.sub(r"^City\s+", "", (contest_type or "").strip(), flags=re.I)
    return display_name(" ".join(x for x in ((chapter or "").strip(), ct,
                                              str(season or "").strip()) if x))
