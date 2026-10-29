"""REFUND MEMOS (Kerry 2026-10-28, Event Ops #2475-2 corrected by #2476-4).

Kerry, verbatim: "Memo would say Refund for San Antonio Fall Points Race in
that particular situation. It's the [What] for [Event or Season Contest
name]".

Every refund the Tracker starts pre-fills the Venmo / PayPal / Cash App note
as "<What> for <Event or Season Contest name>":
    Refund for San Antonio Fall Points Race
    Refund for a9.29 Teravista
Not all caps, not pipe-separated, no player-name prefix. One helper here
for the server (get_refunds_overview) and its twin `refundMemo` in
static/js/refund-memo.js for the pages that build the note in the browser
(customers.html Refund modal + apply-credit excess, events.html excess,
tgf.html Refunds console fallback). Guard: test_refund_memo.py.
"""
from __future__ import annotations

import re

_CODE = re.compile(r"^[a-z]+\d+(?:\.\d+)?$", re.I)


def display_name(name) -> str:
    """The event or contest name as a person writes it: spaces collapsed,
    and an ALL-CAPS name ("SAN ANTONIO FALL POINTS RACE") title-cased with
    event codes ("A9.29") lower-cased. A mixed-case name is left alone."""
    s = " ".join(str(name or "").split())
    if not s or not any(ch.isalpha() for ch in s) or s != s.upper():
        return s
    out = []
    for w in s.split(" "):
        if _CODE.match(w):
            out.append(w.lower())
        elif any(ch.isdigit() for ch in w):
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:].lower())
    return " ".join(out)


def refund_memo(what: str = "Refund", name: str = "") -> str:
    """"<What> for <name>", e.g. refund_memo("Refund", "a9.29 Teravista")."""
    w = " ".join(str(what or "").split()) or "Refund"
    n = display_name(name)
    return f"{w} for {n}" if n else w


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
