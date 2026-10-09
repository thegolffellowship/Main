"""Lone Star Cup RECAP drafts, written from the Cup board (Kerry 10/9).

Kerry, verbatim: "Would be nice to auto-generate an end of day Saturday
recap for what happened and where the cup stands after team sessions.
Then a final recap"

Two recaps, both DRAFTS to Kerry (staff only, the recap_mail.py door):

- **saturday**, once both Saturday sessions (Fourball AM, Foursomes PM)
  are final: the session scores, every match in match order on one line,
  the standouts the cards show (biggest margin, comebacks, matches that
  went the distance, a session sweep), and where the Cup stands: the
  points and what each side needs Sunday, from `cup_status` (the defending
  champion keeps the Cup on a tie, so SA needs half and Austin half + ½).
- **final**, once every session is final: the result, the session
  scores, the Sunday singles, the clinching match ONLY when the matches
  carry their finish times (the board does not today, so no clinch line
  is written), and the players who won every match they played.

Rules:
- Every number and name comes from the board payload
  (`lsc_cup.lsc_board_payload()`; the frozen `lsc_results` snapshot once
  it is stored). Nothing is invented: the fellowship line is a highlighted
  blank for Kerry, not a guess.
- No dollars anywhere (CA #726: members never see money on the Cup). The
  skins are left out, and an output carrying a "$" is refused at the
  boundary.
- House style (docs/claude/event-recaps.md): "TGF Results |" subject, the
  merge-tag greeting, CAPS section heads ending in a period, members'
  names with the surname in CAPS (the board's `lines`, Kerry's member
  ruling) and a Spotlight link on every name (`[[Name|customer_id]]`,
  lesson 67), a lean draft, a fellowship close, Kerry's signature. The
  HTML is recap_mail.py's renderer (Kerry's sent layout) passed through
  `fetcher.normalize_email_html`.
- The guard refuses (with the reason) while a session it needs is not
  final, part-drawn, or scored from anything but entered cards.

Delivery: `send_recap(kind, send=True)` mails the draft to Kerry
(`lsc_recap_to`, default kerry@thegolffellowship.com; staff addresses
only), ONCE per kind, recorded in the app setting `lsc_recap_sent`;
`force` re-runs it. `lsc_recap_auto_check()` is the 10-minute scheduler
job (app.py) during the Cup's dates, behind the app setting
`lsc_recap_auto` (ON unless set to 0/off: it only ever emails Kerry).
Bridge: `scoring-lsc-recap:<saturday|final>[|send[|force]]`.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, timedelta

logger = logging.getLogger(__name__)

KINDS = ("saturday", "final")
TEAM = {"austin": "Austin", "sa": "San Antonio"}
TAG = {"austin": "AUS", "sa": "SA"}
SIDE_KEY = {1: "austin", 2: "sa"}
DEFAULT_TO = "kerry@thegolffellowship.com"     # Kerry only (staff draft)
SENT_KEY = "lsc_recap_sent"
AUTO_KEY = "lsc_recap_auto"
TO_KEY = "lsc_recap_to"
COMEBACK_MIN = 2          # a winner who was this many down (or more) came back
MAX_AUTO_ATTEMPTS = 3     # a failed auto send retries this many times, no more
SIGNATURE = ["Kerry Niester", "The Golf Fellowship", "210.838.3948"]
FELLOWSHIP_BLANK = "[__ who gathered after golf, and where (yours to fill, or cut) __]"


# ---------------------------------------------------------------------------
# Small formatters
# ---------------------------------------------------------------------------

def fmt_pts(x) -> str:
    """4.5 -> '4½', 0.5 -> '½', 7.0 -> '7'."""
    x = float(x or 0)
    whole = int(x)
    frac = round(x - whole, 2)
    if frac == 0.5:
        return ("" if whole == 0 else str(whole)) + "½"
    if frac == 0:
        return str(whole)
    return f"{x:g}"


def _plural(n: int, one: str, many: str | None = None) -> str:
    return one if n == 1 else (many or one + "s")


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _day_label(iso) -> str | None:
    try:
        d = date.fromisoformat(str(iso)[:10])
    except (TypeError, ValueError):
        return None
    return d.strftime("%a, %b ") + str(d.day)


def _number_word(n: int) -> str:
    words = ["zero", "one", "two", "three", "four", "five", "six", "seven",
             "eight", "nine", "ten"]
    return words[n] if 0 <= n < len(words) else str(n)


# ---------------------------------------------------------------------------
# Names (house style: CAPS surname for members, a Spotlight link on each)
# ---------------------------------------------------------------------------

def _player_displays(board: dict) -> dict[int, str]:
    """cid -> the board's display line ("First LAST" for members/alumni,
    from lsc_cup._attach_display_lines), else the roster name."""
    out: dict[int, str] = {}
    for sess in board.get("sessions") or []:
        for m in sess.get("matches") or []:
            for p in m.get("players") or []:
                cids = [int(c) for c in p.get("customer_ids") or []]
                lines = p.get("lines") or []
                names = [n.strip() for n in str(p.get("name") or "").split(" & ")]
                for i, c in enumerate(cids):
                    nm = (lines[i] if i < len(lines) and lines[i] else
                          names[i] if len(names) == len(cids) and names[i] else
                          f"#{c}")
                    out.setdefault(c, nm)
    return out


def _surname(display: str) -> str:
    """The CAPS word(s) of a member's display line, else the last word
    (a generational suffix is skipped)."""
    words = display.split()
    caps = [w for w in words if len(w) > 1 and re.fullmatch(r"[A-Z][A-Z'\-]+", w)]
    if caps:
        return " ".join(caps)
    i = len(words) - 1
    if i > 0 and words[i].rstrip(".").lower() in ("jr", "sr", "ii", "iii", "iv"):
        i -= 1
    return words[i] if words else display


class Names:
    """Short names for the match lines: the surname, or the full name when
    two players on the board share it (Event Info's rule: "a last name
    shared on the roster shows the first name too")."""

    def __init__(self, board: dict):
        self.display = _player_displays(board)
        counts: dict[str, int] = {}
        for d in self.display.values():
            k = _surname(d).lower()
            counts[k] = counts.get(k, 0) + 1
        self.shared = {k for k, n in counts.items() if n > 1}

    def short(self, cid: int) -> str:
        d = self.display.get(int(cid)) or f"#{cid}"
        s = _surname(d)
        return d if s.lower() in self.shared else s

    def link(self, cid: int, full: bool = False) -> str:
        nm = (self.display.get(int(cid)) or f"#{cid}") if full else self.short(cid)
        return f"[[{nm}|{int(cid)}]]"

    def side(self, cids, full: bool = False) -> str:
        return " & ".join(self.link(c, full) for c in cids)


# ---------------------------------------------------------------------------
# Facts from the board
# ---------------------------------------------------------------------------

def _match_winner(m: dict) -> str | None:
    """'austin' | 'sa' | 'halved' for a final match, from the points the
    board paid (the same numbers that built the team totals)."""
    pts = m.get("points") or {}
    a, s = float(pts.get("austin") or 0), float(pts.get("sa") or 0)
    if a > s:
        return "austin"
    if s > a:
        return "sa"
    return "halved" if a > 0 else None


def _side_cids(m: dict, key: str) -> list[int]:
    idx = 0 if key == "austin" else 1
    ps = m.get("players") or []
    return [int(c) for c in (ps[idx].get("customer_ids") if len(ps) > idx else []) or []]


def _parse_margin(margin) -> tuple[int, int] | None:
    t = str(margin or "").strip().upper()
    mm = re.fullmatch(r"(\d+)\s*&\s*(\d+)", t)
    if mm:
        return int(mm.group(1)), int(mm.group(2))
    mm = re.fullmatch(r"(\d+)\s*UP", t)
    if mm:
        return int(mm.group(1)), 0
    return None


def _walk(m: dict) -> list[tuple[int, int]]:
    """[(hole number, lead after it)] in play order up to the close-out;
    lead > 0 = Austin up. Holes played after a close-out count for skins
    only and are not part of the match."""
    closed = m.get("closed_at_order")
    out, lead = [], 0
    for h in sorted(m.get("holes") or [], key=lambda h: h.get("order") or 0):
        if h.get("winner") is None:
            continue
        if closed and (h.get("order") or 0) > closed:
            break
        lead += 1 if h["winner"] == 1 else (-1 if h["winner"] == 2 else 0)
        out.append((h.get("hole"), lead))
    return out


def _deficit(walk, key: str) -> tuple[int, int | None]:
    """The most a side was down in the match, and the LAST hole it was that
    far down. (0, None) when it never trailed."""
    sign = 1 if key == "austin" else -1
    worst, at = 0, None
    for hole, lead in walk:
        down = -lead * sign
        if down > 0 and down >= worst:
            worst, at = down, hole
    return worst, at


def _numbered(board: dict) -> list[tuple[dict, dict, int]]:
    """(session, match, match number) over the whole board, numbered 1..N
    across sessions in the dial's order (the board's and THE DRAW's 1-28)."""
    out, n = [], 0
    for sess in board.get("sessions") or []:
        for m in sess.get("matches") or []:
            n += 1
            out.append((sess, m, n))
    return out


def _session_points(sess: dict) -> dict:
    tot = {"austin": 0.0, "sa": 0.0}
    for m in sess.get("matches") or []:
        for k in tot:
            tot[k] += float((m.get("points") or {}).get(k) or 0)
    return tot


def _overridden(m: dict) -> bool:
    return isinstance(m.get("result_override"), dict)


def match_line(names: Names, m: dict, n: int) -> str:
    """'Match 3: CLOER & John WADE (AUS) def. BAKER & MAZANEC 3&2'."""
    w = _match_winner(m)
    a, s = _side_cids(m, "austin"), _side_cids(m, "sa")
    ov = m.get("result_override") if _overridden(m) else None
    if w == "halved":
        return f"Match {n}: {names.side(a)} (AUS) halved with {names.side(s)} (SA)"
    if w not in ("austin", "sa"):
        return f"Match {n}: {names.side(a)} (AUS) v {names.side(s)} (SA)"
    win, lose = (a, s) if w == "austin" else (s, a)
    margin = (ov or {}).get("margin") or m.get("gg_margin") or ""
    tail = f" ({margin.lower()})" if margin in ("Conceded",) else (f" {margin}" if margin else "")
    return f"Match {n}: {names.side(win)} ({TAG[w]}) def. {names.side(lose)}{tail}"


def standouts(board: dict, names: Names, session_ids: list[str]) -> list[str]:
    """Sentences the cards back, for the named sessions: the biggest margin,
    comebacks (a winner who was COMEBACK_MIN or more down; a halve from that
    far down), the matches that went the distance, and any session sweep."""
    rows = [(s, m, n) for s, m, n in _numbered(board) if s.get("id") in session_ids]
    out: list[str] = []

    # biggest margin (a close-out, ranked by lead then holes to play)
    best, best_rows = None, []
    for s, m, n in rows:
        if _overridden(m) or m.get("state") != "final":
            continue
        pm = _parse_margin(m.get("gg_margin"))
        if not pm or not m.get("closed_at_order") or pm[1] == 0:
            continue
        if best is None or pm > best:
            best, best_rows = pm, [(s, m, n)]
        elif pm == best:
            best_rows.append((s, m, n))
    if best and len(best_rows) <= 2:
        bits = []
        for s, m, n in best_rows:
            w = _match_winner(m)
            win, lose = _side_cids(m, w), _side_cids(m, "sa" if w == "austin" else "austin")
            bits.append(f"{names.side(win)} ({TAG[w]}) closed out {names.side(lose)} "
                        f"{best[0]}&{best[1]} in Match {n}")
        lead = "The biggest margin" if len(bits) == 1 else "The biggest margins"
        out.append(f"{lead}: {_join(bits)}.")
    elif best:
        nums = [str(n) for _, _, n in best_rows]
        out.append(f"The biggest margin, {best[0]}&{best[1]}, came in "
                   f"{_number_word(len(nums))} matches: Matches {_join(nums)}.")

    # comebacks
    for s, m, n in rows:
        if _overridden(m) or m.get("state") != "final":
            continue
        walk = _walk(m)
        w = _match_winner(m)
        if w in ("austin", "sa"):
            down, at = _deficit(walk, w)
            if down >= COMEBACK_MIN and at is not None:
                verb = "were" if len(_side_cids(m, w)) > 1 else "was"
                out.append(f"Comeback in Match {n}: {names.side(_side_cids(m, w))} ({TAG[w]}) "
                           f"{verb} {down} down through {at} and won {m.get('gg_margin')}.")
        elif w == "halved":
            for k in ("austin", "sa"):
                down, at = _deficit(walk, k)
                if down >= COMEBACK_MIN and at is not None:
                    out.append(f"Comeback in Match {n}: {names.side(_side_cids(m, k))} ({TAG[k]}) "
                               f"came back from {down} down through {at} to halve it.")

    # matches that went the distance: decided on the last hole (the close-out
    # walk marks a 1 UP finish as closed AT the last hole) or level after it
    full = [(n, int(m.get("n_holes") or 18)) for s, m, n in rows
            if not _overridden(m) and m.get("state") == "final"
            and (not m.get("closed_at_order")
                 or int(m["closed_at_order"]) >= int(m.get("n_holes") or 18))
            and len(_walk(m)) >= int(m.get("n_holes") or 18)]
    if full:
        holes = full[0][1]
        nums = [str(n) for n, _ in full]
        if len(full) == 1:
            out.append(f"Match {nums[0]} went all {holes} holes.")
        else:
            out.append(f"{_number_word(len(full)).capitalize()} matches went all {holes} holes: "
                       f"Matches {_join(nums)}.")

    # a session sweep
    for sess in board.get("sessions") or []:
        if sess.get("id") not in session_ids:
            continue
        ms = sess.get("matches") or []
        if not ms:
            continue
        sp = _session_points(sess)
        per = float(sess.get("points_per_match") or 1)
        for k in ("austin", "sa"):
            if sp[k] >= per * len(ms) - 1e-9:
                out.append(f"{TEAM[k]} swept the {_session_name(sess)}, "
                           f"{fmt_pts(sp[k])}–{fmt_pts(sp['sa' if k == 'austin' else 'austin'])}.")
    return out


def _session_name(sess: dict) -> str:
    t = (sess.get("title") or sess.get("label") or sess.get("id") or "").strip()
    return t.title() if t.isupper() else t


def records(board: dict) -> dict[int, dict]:
    """cid -> {"w", "l", "h", "played"} over every final match."""
    out: dict[int, dict] = {}
    for s, m, n in _numbered(board):
        if m.get("state") != "final":
            continue
        w = _match_winner(m)
        for k in ("austin", "sa"):
            for c in _side_cids(m, k):
                r = out.setdefault(c, {"w": 0, "l": 0, "h": 0, "played": 0, "team": k})
                r["played"] += 1
                if w == "halved":
                    r["h"] += 1
                elif w == k:
                    r["w"] += 1
                elif w:
                    r["l"] += 1
    return out


def clinch(board: dict) -> dict | None:
    """The match whose result first took the winning side to its target, in
    FINISHING order. Only when the order is in the data: every match of the
    session the clinch falls in must carry `decided_at` (or `finished_at`);
    sessions are played in date order, so earlier sessions are whole. None
    otherwise (and the recap then says nothing about clinching)."""
    cup = board.get("cup") or {}
    winner = cup.get("winner")
    if cup.get("status") not in ("won", "retained") or winner not in TEAM:
        return None
    half = float(cup.get("half") or 0)
    # cup_status: the defending champion clinches at exactly half, the
    # challenger has to pass half (the next half point)
    target = half if winner == cup.get("defending_champion") else half + 0.5
    running = 0.0
    numbered = {id(m): n for _, m, n in _numbered(board)}
    for sess in sorted(board.get("sessions") or [], key=lambda s: str(s.get("date") or "")):
        ms = sess.get("matches") or []
        gained = sum(float((m.get("points") or {}).get(winner) or 0) for m in ms)
        if running + gained < target - 1e-9:
            running += gained
            continue
        stamps = [m.get("decided_at") or m.get("finished_at") for m in ms]
        if not all(stamps):
            return None
        for m, ts in sorted(zip(ms, stamps), key=lambda x: str(x[1])):
            running += float((m.get("points") or {}).get(winner) or 0)
            if running >= target - 1e-9:
                return {"match": m, "number": numbered.get(id(m)), "session": sess,
                        "at": ts, "points": running}
        return None
    return None


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------

def _sessions_for(board: dict, kind: str) -> list[dict]:
    sess = board.get("sessions") or []
    if kind == "final":
        return list(sess)
    dates = sorted({str(s.get("date"))[:10] for s in sess if s.get("date")})
    if dates:
        return [s for s in sess if str(s.get("date") or "")[:10] == dates[0]]
    return [s for s in sess if str(s.get("id") or "").lower().startswith("sat")]


def guard(board: dict, kind: str) -> dict:
    """{"ok": bool, "reason": str|None, "blockers": [...], "sessions": [ids]}.
    Refuses while any session the recap covers is missing, part-drawn, not
    final, or scored from anything but entered cards."""
    if kind not in KINDS:
        return {"ok": False, "reason": f"kind must be one of {', '.join(KINDS)}",
                "blockers": [], "sessions": []}
    if not board or not board.get("configured", True) or not board.get("sessions"):
        return {"ok": False, "reason": "the Cup board is not configured (no lsc_matches dial)",
                "blockers": [], "sessions": []}
    sessions = _sessions_for(board, kind)
    blockers: list[str] = []
    if not sessions:
        blockers.append("no Saturday sessions on the board")
    src = board.get("source")
    if src in ("mock", "none", "preview"):
        blockers.append(f"the board is not scored from entered cards (source {src})")
    entry = set(board.get("entry_sessions") or [])
    for s in sessions:
        sid = s.get("id")
        ms = s.get("matches") or []
        if not ms:
            blockers.append(f"{sid}: no matches drawn")
            continue
        want = s.get("n_matches")
        if want and len(ms) < int(want):
            blockers.append(f"{sid}: only {len(ms)} of {int(want)} matches drawn")
        for m in ms:
            if m.get("state") != "final":
                thru = m.get("thru")
                blockers.append(f"{sid} {m.get('match_id')} is {m.get('state') or 'not started'}"
                                + (f" (thru {thru})" if thru and m.get("state") == "live" else ""))
        if src == "entry" and sid not in entry and not all(_overridden(m) for m in ms):
            blockers.append(f"{sid}: not scored from entered cards")
    if kind == "final":
        cup = board.get("cup") or {}
        if cup.get("status") not in ("won", "retained", "tied_pending"):
            blockers.append(f"the Cup isn't decided (status {cup.get('status')})")
        per = float(board.get("points_win") or 1)
        drawn = sum(len(s.get("matches") or []) for s in board.get("sessions") or [])
        if cup.get("total") and drawn * per < float(cup["total"]) - 1e-9:
            blockers.append(f"only {drawn} matches are on the board for "
                            f"{fmt_pts(cup['total'])} points")
    ok = not blockers
    label = "Saturday" if kind == "saturday" else "the whole Cup"
    return {"ok": ok,
            "reason": None if ok else f"{label} is not final yet: " + "; ".join(blockers[:6])
                      + (f" (+{len(blockers) - 6} more)" if len(blockers) > 6 else ""),
            "blockers": blockers, "sessions": [s.get("id") for s in sessions]}


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def _score_line(sp: dict) -> str:
    return f"Austin {fmt_pts(sp['austin'])} – San Antonio {fmt_pts(sp['sa'])}"


def _session_block(sess: dict, names: Names, numbers: dict) -> list[str]:
    sp = _session_points(sess)
    out = [f"{(sess.get('title') or _session_name(sess)).upper()}.", "",
           _score_line(sp) + ".", ""]
    for m in sess.get("matches") or []:
        out.append("- " + match_line(names, m, numbers[id(m)]))
    out.append("")
    return out


def _cup_lines(board: dict) -> list[str]:
    cup = board.get("cup") or {}
    pts = {k: float(((board.get("teams") or {}).get(k) or {}).get("points") or 0)
           for k in TEAM}
    total = float(cup.get("total") or 0)
    half = float(cup.get("half") or total / 2)
    champ = cup.get("defending_champion")
    remaining = round(total - pts["austin"] - pts["sa"], 2)
    a, s = pts["austin"], pts["sa"]
    if a == s:
        first = f"After Saturday the Cup is all square, {fmt_pts(a)}–{fmt_pts(s)}."
    else:
        lead_k = "austin" if a > s else "sa"
        other = "sa" if lead_k == "austin" else "austin"
        first = (f"After Saturday {TEAM[lead_k]} leads {TEAM[other]} "
                 f"{fmt_pts(pts[lead_k])} to {fmt_pts(pts[other])}.")
    out = [first]
    if cup.get("status") in ("won", "retained") and cup.get("winner") in TEAM:
        w = cup["winner"]
        out.append(f"{TEAM[w]} has already clinched the Cup with {fmt_pts(pts[w])} points.")
        return out
    out.append(f"{fmt_pts(remaining)} {'point is' if remaining == 1 else 'points are'} "
               f"left in Sunday's singles.")
    needs = cup.get("needs") or {}
    if champ in TEAM:
        ch = TEAM[champ]
        other = "sa" if champ == "austin" else "austin"
        out.append(f"{ch}, the defending champion, needs {fmt_pts(needs.get(champ))} "
                   f"to retain the Cup ({fmt_pts(half)} of {fmt_pts(total)} keeps it); "
                   f"{TEAM[other]} needs {fmt_pts(needs.get(other))} to win it "
                   f"({fmt_pts(half + 0.5)}).")
    else:
        out.append(f"Austin needs {fmt_pts(needs.get('austin'))} and San Antonio "
                   f"{fmt_pts(needs.get('sa'))} to win the Cup ({fmt_pts(half + 0.5)} of "
                   f"{fmt_pts(total)}).")
    return out


def _sunday_teaser(board: dict, sat_ids: list[str]) -> list[str]:
    rest = [s for s in board.get("sessions") or [] if s.get("id") not in sat_ids]
    lines = []
    for s in rest:
        ms = s.get("matches") or []
        n = len(ms) or int(s.get("n_matches") or 0)
        if not n:
            continue
        day = _day_label(s.get("date"))
        tee = next((m.get("tee_time") for m in ms if m.get("tee_time")), None)
        per = float(s.get("points_per_match") or 1)
        bits = [f"**{day}**" if day else None,
                f"first tee time {tee}" if tee else None,
                f"**{(s.get('title') or _session_name(s)).upper()}**",
                f"{n} {_plural(n, 'match', 'matches')}, {fmt_pts(n * per)} points"]
        lines.append("- " + " | ".join(b for b in bits if b))
    return lines


def _compose_saturday(board: dict, ctx: dict) -> tuple[str, str]:
    names = Names(board)
    numbers = {id(m): n for _, m, n in _numbered(board)}
    sat = _sessions_for(board, "saturday")
    sat_ids = [s.get("id") for s in sat]
    pts = {k: float(((board.get("teams") or {}).get(k) or {}).get("points") or 0)
           for k in TEAM}
    a, s = pts["austin"], pts["sa"]
    if a == s:
        subject = f"TGF Results | The Lone Star Cup Is All Square, {fmt_pts(a)}–{fmt_pts(s)}"
    else:
        lk = "austin" if a > s else "sa"
        ok = "sa" if lk == "austin" else "austin"
        subject = (f"TGF Results | {TEAM[lk].upper()} Leads the Lone Star Cup "
                   f"{fmt_pts(pts[lk])}–{fmt_pts(pts[ok])}")
    where = f" at {ctx['course']}" if ctx.get("course") else ""
    titles = [(x.get("title") or _session_name(x)).title() for x in sat]
    day_pts = {"austin": 0.0, "sa": 0.0}
    for x in sat:
        sp = _session_points(x)
        for k in day_pts:
            day_pts[k] += sp[k]
    lede = (f"Saturday of the Lone Star Cup{where} is in the books: "
            f"{_join(titles)}, {sum(len(x.get('matches') or []) for x in sat)} matches.")
    if day_pts["austin"] != day_pts["sa"]:
        dk = "austin" if day_pts["austin"] > day_pts["sa"] else "sa"
        lede += (f" {TEAM[dk]} won the day "
                 f"{fmt_pts(day_pts[dk])}–{fmt_pts(day_pts['sa' if dk == 'austin' else 'austin'])}.")
    else:
        lede += f" The day finished level, {fmt_pts(day_pts['austin'])}–{fmt_pts(day_pts['sa'])}."

    L = [f"**Subject:** {subject}", "", "Good Evening, %first_name%!", "", lede, ""]
    for x in sat:
        L += _session_block(x, names, numbers)
    so = standouts(board, names, sat_ids)
    if so:
        L += ["THE STANDOUTS.", ""] + [f"- {t}" for t in so] + [""]
    L += ["WHERE THE CUP STANDS.", "", " ".join(_cup_lines(board)), ""]
    teaser = _sunday_teaser(board, sat_ids)
    if teaser:
        L += ["UP NEXT.", ""] + teaser + [""]
    L += ["FELLOWSHIP.", "", FELLOWSHIP_BLANK, "", "See you Sunday!"] + SIGNATURE
    return subject, "\n".join(L)


def _compose_final(board: dict, ctx: dict) -> tuple[str, str]:
    names = Names(board)
    numbers = {id(m): n for _, m, n in _numbered(board)}
    cup = board.get("cup") or {}
    pts = {k: float(((board.get("teams") or {}).get(k) or {}).get("points") or 0)
           for k in TEAM}
    champ = cup.get("defending_champion")
    st, w = cup.get("status"), cup.get("winner")
    score = lambda k: f"{fmt_pts(pts[k])} to {fmt_pts(pts['sa' if k == 'austin' else 'austin'])}"
    dash = lambda k: f"{fmt_pts(pts[k])}–{fmt_pts(pts['sa' if k == 'austin' else 'austin'])}"
    where = f" at {ctx['course']}" if ctx.get("course") else ""
    if st == "retained" and w in TEAM:
        subject = f"TGF Results | {TEAM[w].upper()} Retains the Lone Star Cup"
        lede = (f"{TEAM[w]} retains the Lone Star Cup{where}. The weekend finished "
                f"level, {score(w)}, and the defending champion keeps the Cup on a tie.")
    elif st == "won" and w in TEAM and w == champ:
        subject = f"TGF Results | {TEAM[w].upper()} Defends the Lone Star Cup, {dash(w)}"
        lede = f"{TEAM[w]} defends the Lone Star Cup{where}, {score(w)}."
    elif st == "won" and w in TEAM and champ in TEAM:
        subject = f"TGF Results | {TEAM[w].upper()} Takes the Lone Star Cup, {dash(w)}"
        lede = f"{TEAM[w]} takes the Lone Star Cup from {TEAM[champ]}{where}, {score(w)}."
    elif st == "won" and w in TEAM:
        subject = f"TGF Results | {TEAM[w].upper()} Wins the Lone Star Cup, {dash(w)}"
        lede = f"{TEAM[w]} wins the Lone Star Cup{where}, {score(w)}."
    else:
        subject = f"TGF Results | The Lone Star Cup Finishes Level, {dash('austin')}"
        lede = f"The Lone Star Cup{where} finished level, {score('austin')}."

    L = [f"**Subject:** {subject}", "", "Good Afternoon, %first_name%!", "", lede, ""]
    L += ["THE FINAL SCORE.", ""]
    for x in board.get("sessions") or []:
        L.append(f"- {(x.get('title') or _session_name(x)).upper()}: {_score_line(_session_points(x))}")
    L.append(f"- TOTAL: Austin {fmt_pts(pts['austin'])} – San Antonio {fmt_pts(pts['sa'])}")
    L.append("")

    sat_ids = [s.get("id") for s in _sessions_for(board, "saturday")]
    sun = [s for s in board.get("sessions") or [] if s.get("id") not in sat_ids]
    for x in sun:
        L += _session_block(x, names, numbers)

    so = standouts(board, names, [s.get("id") for s in sun])
    cl = clinch(board)
    if cl:
        m = cl["match"]
        mw = _match_winner(m)
        verb = "retain" if (w == champ) else "win"
        so.insert(0, f"The clincher: Match {cl['number']}, {names.side(_side_cids(m, mw), True)} "
                     f"({TAG[mw]}) {'halved' if mw == 'halved' else 'won'}"
                     f"{' ' + m.get('gg_margin') if mw != 'halved' and m.get('gg_margin') else ''}, "
                     f"the point that took {TEAM[w]} to {fmt_pts(cl['points'])} to {verb} the Cup.")
    if so:
        L += ["THE STANDOUTS.", ""] + [f"- {t}" for t in so] + [""]

    recs = records(board)
    perfect = sorted((c for c, r in recs.items() if r["played"] >= 3 and r["w"] == r["played"]),
                     key=lambda c: (recs[c]["team"], names.short(c)))
    unbeaten = sorted((c for c, r in recs.items()
                       if r["played"] >= 3 and r["l"] == 0 and 0 < r["h"] and r["w"] > 0),
                      key=lambda c: (recs[c]["team"], names.short(c)))
    rec_lines = []
    if perfect:
        by_n: dict[int, list[int]] = {}
        for c in perfect:
            by_n.setdefault(recs[c]["played"], []).append(c)
        for n_, cs in sorted(by_n.items(), reverse=True):
            who = _join([f"{names.link(c, True)} ({TAG[recs[c]['team']]})" for c in cs])
            rec_lines.append(f"- {who} won all {_number_word(n_)} matches.")
    if unbeaten:
        who = _join([f"{names.link(c, True)} ({TAG[recs[c]['team']]}, "
                     f"{recs[c]['w']}-0-{recs[c]['h']})" for c in unbeaten])
        rec_lines.append(f"- Unbeaten: {who}.")
    if rec_lines:
        L += ["PERFECT WEEKENDS." if perfect else "UNBEATEN.", ""] + rec_lines + [""]

    n_players = len(names.display)
    L += [f"Thank you to all {n_players} players, Austin and San Antonio, for a "
          f"weekend of match play.", ""]
    L += ["FELLOWSHIP.", "", FELLOWSHIP_BLANK, "", "See you soon!"] + SIGNATURE
    return subject, "\n".join(L)


def plain_text(markup: str) -> str:
    t = re.sub(r"\[\[([^\]|]+)\|\d+\]\]", r"\1", markup)
    t = re.sub(r"\[([^\]]+)\]\((https?:[^)\s]+)\)", r"\1", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"\{/?green\}", "", t)
    t = re.sub(r"^Subject: .*\n\n?", "", t)
    return t.strip() + "\n"


def render_html(markup: str) -> str:
    from email_parser import recap_mail as rm
    from email_parser.fetcher import normalize_email_html
    _subj, html = rm.render_recap_html(rm._signature_breaks(markup))
    return normalize_email_html(html.replace(" ", "<br>"))


def _event_context(event_id, db_path=None) -> dict:
    if not event_id:
        return {}
    try:
        from email_parser.database import _connect
        with _connect(db_path) as conn:
            r = conn.execute("SELECT item_name, course, event_date FROM events WHERE id = ?",
                             (int(event_id),)).fetchone()
        return {"event_name": r[0], "course": r[1], "event_date": r[2]} if r else {}
    except Exception:
        logger.exception("lsc_recap: event context read failed")
        return {}


def build_recap(kind: str, board: dict | None = None, db_path=None,
                context: dict | None = None) -> dict:
    """The recap for `kind` ('saturday' | 'final') from the Cup board.

    Returns {"kind", "ok", "reason", "blockers", "subject", "markup",
    "text", "html", "source"}; ok False (with the reason, and no text) while
    the guard refuses. `board` defaults to lsc_cup.lsc_board_payload()
    (the frozen snapshot once stored); `context` may carry {"course"}."""
    kind = (kind or "").strip().lower()
    if board is None:
        from email_parser.lsc_cup import lsc_board_payload
        board = lsc_board_payload(db_path=db_path)
    g = guard(board, kind)
    out = {"kind": kind, "ok": g["ok"], "reason": g["reason"],
           "blockers": g["blockers"], "sessions": g["sessions"],
           "source": board.get("source") if board else None,
           "event_id": (board or {}).get("event_id")}
    if not g["ok"]:
        return out
    ctx = dict(context) if context is not None else _event_context(board.get("event_id"), db_path)
    subject, markup = (_compose_saturday if kind == "saturday" else _compose_final)(board, ctx)
    text = plain_text(markup)
    html = render_html(markup)
    # Check at the boundary (CLAUDE.md): no dollar figure leaves this module.
    if "$" in markup or "$" in text or "$" in html:
        return {**out, "ok": False, "reason": "a dollar sign reached the recap; refused (CA #726)"}
    out.update({"subject": subject, "markup": markup, "text": text, "html": html})
    return out


# ---------------------------------------------------------------------------
# Delivery: a DRAFT to Kerry, once per kind
# ---------------------------------------------------------------------------

def _gs(key, db_path=None):
    try:
        from email_parser.database import get_app_setting
        return get_app_setting(key, db_path=db_path)
    except Exception:
        return None


def _sent_map(db_path=None) -> dict:
    try:
        return json.loads(_gs(SENT_KEY, db_path) or "{}") or {}
    except Exception:
        return {}


def _record(event_id, kind: str, entry: dict, db_path=None) -> None:
    from email_parser.database import set_app_setting
    m = _sent_map(db_path)
    m.setdefault(str(event_id), {})[kind] = entry
    set_app_setting(SENT_KEY, json.dumps(m, default=str), db_path=db_path)


def sent_state(event_id, kind: str, db_path=None) -> dict | None:
    return (_sent_map(db_path).get(str(event_id)) or {}).get(kind)


def recipients(db_path=None) -> list[str]:
    raw = _gs(TO_KEY, db_path) or DEFAULT_TO
    return [a.strip() for a in str(raw).split(",") if a.strip()]


def _cover(r: dict) -> str:
    import html as _h
    kind = "Saturday" if r["kind"] == "saturday" else "Final"
    bits = [f"<p>Lone Star Cup recap draft (<strong>{kind}</strong>), written from the "
            f"Cup board (source: {_h.escape(str(r.get('source')))}). Every number and "
            "name comes from the board; nothing else was added. "
            "<strong>Copy the recap from this email</strong> (below the orange line).</p>",
            "<p>Yours to check before it goes out: the greeting follows the send time "
            "(draft says " + ("Good Evening" if r["kind"] == "saturday" else "Good Afternoon")
            + "), and the FELLOWSHIP line is a highlighted blank to fill or cut. "
            "No dollars and no skins money, by rule (CA #726).</p>"]
    if r["kind"] == "final" and "The clincher" not in (r.get("markup") or ""):
        bits.append("<p>No clinching match is named: the board does not record when "
                    "each match finished, so the clinch can't be told from the data.</p>")
    bits.append(f"<p><strong>Subject:</strong> {_h.escape(r['subject'])}</p>")
    bits.append('<hr style="border:0;border-top:2px solid #E87C3E">')
    return "".join(bits)


def send_recap(kind: str, send: bool = False, force: bool = False, db_path=None,
               board: dict | None = None, auto: bool = False) -> dict:
    """Dry run (default): the recap text + the guard result, nothing sent.
    send=True mails the DRAFT to Kerry (staff addresses only), once per
    kind per event (`lsc_recap_sent`); force re-sends. A refused guard
    never sends, forced or not."""
    from email_parser.recap_mail import staff_only
    r = build_recap(kind, board=board, db_path=db_path)
    to = recipients(db_path)
    out = {k: r.get(k) for k in ("kind", "ok", "reason", "blockers", "sessions",
                                 "source", "event_id", "subject", "text")}
    out["to"] = to
    prior = sent_state(r.get("event_id"), r.get("kind"), db_path) if r.get("event_id") else None
    out["already"] = prior
    if not send:
        out["status"] = "dry_run" if r["ok"] else "refused"
        if r["ok"]:
            out["html"] = r["html"]
        return out
    if not r["ok"]:
        out["status"] = "refused"
        return out
    bad = staff_only(to, lambda k: _gs(k, db_path))
    if bad:
        out.update(status="refused", reason=f"recap drafts go to TGF staff only; refused {bad}")
        return out
    if prior and not force:
        st = prior.get("status")
        if st in ("sent", "sending") or (auto and st == "failed"
                                         and int(prior.get("attempts") or 0) >= MAX_AUTO_ATTEMPTS):
            out["status"] = "skipped_already_" + st
            return out
    attempts = int((prior or {}).get("attempts") or 0) + 1
    from email_parser.timezone_utils import now_central
    stamp = now_central().strftime("%Y-%m-%d %H:%M:%S")
    entry = {"status": "sending", "at": stamp, "to": to, "subject": r["subject"],
             "attempts": attempts, "auto": bool(auto), "forced": bool(force)}
    _record(r["event_id"], r["kind"], entry, db_path)
    creds = [os.getenv(k) for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID",
                                     "AZURE_CLIENT_SECRET", "EMAIL_ADDRESS")]
    ok = False
    if all(creds):
        from email_parser.fetcher import send_mail_graph, normalize_email_html
        ok = send_mail_graph(tenant_id=creds[0], client_id=creds[1], client_secret=creds[2],
                             from_address=creds[3], to_address=",".join(to),
                             subject=f"Lone Star Cup recap draft — "
                                     f"{'Saturday' if r['kind'] == 'saturday' else 'Final'}",
                             html_body=normalize_email_html(_cover(r)) + r["html"])
    else:
        out["error"] = "Email credentials not configured on server"
    entry["status"] = "sent" if ok else "failed"
    _record(r["event_id"], r["kind"], entry, db_path)
    try:
        from email_parser import database as db
        db.log_message({"event_name": "lsc-recap-draft", "channel": "email",
                        "recipient_name": f"LSC recap {r['kind']}",
                        "recipient_address": ",".join(to), "subject": r["subject"],
                        "body_preview": f"{r['event_id']}|{r['kind']}",
                        "status": entry["status"],
                        "sent_by": "lsc-recap-auto" if auto else "lsc-recap"}, db_path=db_path)
        db.log_agent_action("tracker", "lsc_recap_draft",
                            f"{r['kind']} → {','.join(to)}: {entry['status']}"
                            + (" (forced)" if force else ""), db_path=db_path)
    except Exception:
        logger.debug("lsc_recap: log failed", exc_info=True)
    out["status"] = entry["status"]
    return out


def auto_enabled(db_path=None) -> bool:
    """`lsc_recap_auto` is ON unless set to 0 / off / false / no (Kerry's
    ask; it only ever emails Kerry)."""
    v = (_gs(AUTO_KEY, db_path) or "").strip().lower()
    return v not in ("0", "off", "false", "no")


def cup_window(board: dict) -> tuple[date, date] | None:
    """First session date .. the day after the last (10/10 - 10/12)."""
    ds = []
    for s in board.get("sessions") or []:
        try:
            ds.append(date.fromisoformat(str(s.get("date"))[:10]))
        except (TypeError, ValueError):
            continue
    if not ds:
        return None
    return min(ds), max(ds) + timedelta(days=1)


def lsc_recap_auto_check(db_path=None, today: date | None = None,
                         board: dict | None = None) -> dict:
    """The 10-minute scheduler job. During the Cup's dates, when the setting
    is on: the whole Cup final -> mail the FINAL draft once; else Saturday
    final -> mail the SATURDAY draft once. (When the whole Cup is already
    final the Saturday draft is not sent: the final supersedes it.)"""
    if not auto_enabled(db_path):
        return {"skipped": "lsc_recap_auto is off"}
    if board is None:
        from email_parser.lsc_cup import lsc_board_payload
        board = lsc_board_payload(db_path=db_path)
    if not board or not board.get("configured"):
        return {"skipped": "no Cup dial"}
    win = cup_window(board)
    if today is None:
        from email_parser.timezone_utils import today_central
        today = today_central()
    if not win or not (win[0] <= today <= win[1]):
        return {"skipped": f"outside the Cup's dates {win}"}
    for kind in ("final", "saturday"):
        g = guard(board, kind)
        if not g["ok"]:
            continue
        prior = sent_state(board.get("event_id"), kind, db_path)
        if prior and (prior.get("status") in ("sent", "sending")
                      or int(prior.get("attempts") or 0) >= MAX_AUTO_ATTEMPTS):
            return {"kind": kind, "status": "already " + str(prior.get("status"))}
        res = send_recap(kind, send=True, db_path=db_path, board=board, auto=True)
        logger.info("LSC recap auto: %s -> %s", kind, res.get("status"))
        return {"kind": kind, "status": res.get("status"), "to": res.get("to")}
    return {"skipped": "nothing final yet"}
