"""Player score entry (Track A) — the rules that must never break.

- Idempotent replay: a queued op sent twice applies once, and an OLD op
  replayed after a newer write never overwrites the newer value.
- Lock: a second device is refused until it takes over explicitly; the
  first device's later writes are refused AND kept (se_audit), never lost.
- Foursomes team row: one gross per hole, both customer_ids recorded.
- The read is event-scoped, rounds plural, one version per event (CA #661).
- Links: a group link verifies; a revoked link or a closed round does not.
- customer_id on every person column (guiding principle 6).
- GG stays the money record: no payout / GG / season path reads se_*.
- Seeding from PAIRINGS carries customer_id and the starter sheet's PH.

Run: python3 test_score_entry.py
"""
import io
import json
import contextlib
import logging
import os
import re
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db  # noqa: E402
    db.init_db(DB)
from email_parser import score_entry as se  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
for cid, fn, ln in [(101, "Kerry", "Niester"), (102, "Adam", "Baker"),
                    (103, "Chris", "Best"), (104, "Robert", "Hogue")]:
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)",
                 (cid, fn, ln))
conn.execute("INSERT INTO events (id, item_name, event_date, start_type, start_time) "
             "VALUES (900, 's9.25 Canyon Springs', '2026-09-29', 'Shotgun', '17:30')")
conn.commit()

NINE = [{"hole": h, "par": p, "stroke_index": si} for h, p, si in
        [(1, 4, 3), (2, 3, 9), (3, 5, 1), (4, 4, 5), (5, 4, 7), (6, 3, 8),
         (7, 4, 2), (8, 4, 6), (9, 5, 4)]]

print("round + group")
rid = se.create_round(900, 9, round_date="2026-09-29", label="s9.25", course_holes=NINE)["round_id"]
g = se.upsert_group(rid, 1, label="Hole 1", start_hole=1, players=[
    {"customer_id": 101, "display_name": "Kerry Niester", "playing_handicap": 2, "seat": 1},
    {"customer_id": 102, "display_name": "Adam Baker", "playing_handicap": 7, "seat": 2},
    {"customer_id": 103, "display_name": "Chris Best", "playing_handicap": 0, "seat": 3},
    {"display_name": "Guest With No Id", "seat": 4}])
gid = g["group_id"]
check("a seat with no customer_id is reported, not scored",
      g.get("skipped_no_customer_id") == ["Guest With No Id"], g)
v0 = se.event_version(900)

check("the lazy DDL runs once per database, not on every connection",
      any(k[0] == "_ensure_score_entry_tables" for k in db._ENSURED), sorted(db._ENSURED)[:3])

print("lock / take-over")
a = se.claim_group(gid, "phone-A", 101)
check("first device is granted", a.get("granted") and a["kind"] == "claim", a)
b = se.claim_group(gid, "phone-B", 102)
check("second device is refused without take-over",
      b.get("granted") is False and b["lock"]["state"] == "held"
      and b["lock"]["holder_name"] == "Kerry Niester", b)
check("a person outside the group cannot claim",
      "error" in se.claim_group(gid, "phone-C", 104))

print("writes + idempotency")
w = se.write_scores(gid, "phone-A", 101, [
    {"op_id": "A1", "customer_id": 101, "hole": 1, "gross": 4},
    {"op_id": "A2", "customer_id": 102, "hole": 1, "gross": 5}])
check("holder's writes apply", [r["result"] for r in w["results"]] == ["ok", "ok"], w)
check("version bumps on accepted writes", se.event_version(900) > v0)
w = se.write_scores(gid, "phone-A", 101, [
    {"op_id": "A3", "customer_id": 101, "hole": 1, "gross": 3}])
w = se.write_scores(gid, "phone-A", 101, [
    {"op_id": "A1", "customer_id": 101, "hole": 1, "gross": 4}])
check("replayed op is a dup", w["results"][0]["result"] == "dup", w)
card = se.get_group_card(gid, "phone-A")
check("an old replay never overwrites a newer value", card["scores"]["c:101"]["1"] == 3,
      card["scores"])
check("screen sees its own lock as mine", card["lock"]["state"] == "mine")
bad = se.write_scores(gid, "phone-A", 101, [
    {"op_id": "X1", "customer_id": 101, "hole": 12, "gross": 4},
    {"op_id": "X2", "customer_id": 101, "hole": 2, "gross": 0},
    {"op_id": "X3", "customer_id": 104, "hole": 2, "gross": 4},
    {"op_id": "X4", "customer_id": 101, "hole": 2, "gross": 21}])
check("bad hole / range / outsider are invalid",
      [r["result"] for r in bad["results"]] == ["invalid"] * 4, bad)
clr = se.write_scores(gid, "phone-A", 101, [
    {"op_id": "A4", "customer_id": 102, "hole": 1, "gross": None}])
check("a hole can be cleared", "1" not in se.get_group_card(gid)["scores"].get("c:102", {}))

print("max triple + no ace on a par 5 (Kerry 2026-09-25)")
check("bounds: par 3 is 1-6, par 4 is 1-7, par 5 is 2-8",
      [se.gross_bounds(3), se.gross_bounds(4), se.gross_bounds(5)] == [(1, 6), (1, 7), (2, 8)])
check("no par on the card falls back to 1-20", se.gross_bounds(None) == (1, 20))
mt = se.write_scores(gid, "phone-A", 101, [
    {"op_id": "MT1", "customer_id": 102, "hole": 2, "gross": 7},   # par 3: triple is 6
    {"op_id": "MT2", "customer_id": 102, "hole": 2, "gross": 6},
    {"op_id": "MT3", "customer_id": 102, "hole": 3, "gross": 1},   # par 5: no ace
    {"op_id": "MT4", "customer_id": 102, "hole": 3, "gross": 9},   # par 5: triple is 8
    {"op_id": "MT5", "customer_id": 102, "hole": 3, "gross": 8},
    {"op_id": "MT6", "customer_id": 102, "hole": 1, "gross": 1}])  # par 4: an ace is real
check("the server refuses a score above triple and a 1 on a par 5",
      [r["result"] for r in mt["results"]] == ["invalid", "ok", "invalid", "invalid", "ok", "ok"], mt)
check("the refusal says why", "max triple" in (mt["results"][0].get("why") or ""), mt["results"][0])
check("a 1 on a par 4 opens a hole-in-one claim",
      any(h["customer_id"] == 102 and h["hole"] == 1 for h in se.get_group_card(gid)["hio"]))
se.write_scores(gid, "phone-A", 101, [{"op_id": "MT7", "customer_id": 102, "hole": 1, "gross": None},
                                      {"op_id": "MT8", "customer_id": 102, "hole": 2, "gross": None},
                                      {"op_id": "MT9", "customer_id": 102, "hole": 3, "gross": None}])

print("take-over")
t = se.claim_group(gid, "phone-B", 102, takeover=True)
check("take-over moves the lock", t.get("granted") and t["kind"] == "takeover", t)
late = se.write_scores(gid, "phone-A", 101, [
    {"op_id": "A5", "customer_id": 101, "hole": 2, "gross": 6}])
check("old device is refused after take-over",
      late["results"][0]["result"] == "refused_lock" and late["holds_lock"] is False, late)
kept = conn.execute("SELECT detail FROM se_audit WHERE op_id = 'A5'").fetchone()
check("the refused hole is kept, not lost", kept and '"gross": 6' in kept[0], kept)
check("the refused hole did not land",
      "2" not in se.get_group_card(gid)["scores"]["c:101"])
aud = conn.execute("SELECT device_id, prev_device_id, customer_id FROM se_audit "
                   "WHERE kind = 'takeover'").fetchone()
check("take-over audit keeps both devices",
      tuple(aud) == ("phone-B", "phone-A", 102), tuple(aud) if aud else None)
check("old device now sees the lock as held",
      se.get_group_card(gid, "phone-A")["lock"]["state"] == "held")

print("foursomes team row")
bad_team = se.add_team(rid, gid, 101, 104)
check("a team member must be in the group", "error" in bad_team, bad_team)
tid = se.add_team(rid, gid, 103, 101, label="Best / Niester")["team_id"]
tw = se.write_scores(gid, "phone-B", 102, [
    {"op_id": "B1", "team_id": tid, "hole": 1, "gross": 4}])
check("team row applies", tw["results"][0]["result"] == "ok", tw)
row = conn.execute("SELECT customer_id, team_customer_id_a, team_customer_id_b, "
                   "entered_by_customer_id FROM se_hole_scores WHERE subject_key = ?",
                   (f"t:{tid}",)).fetchone()
check("team row records both people and who entered it",
      tuple(row) == (None, 101, 103, 102), tuple(row))

print("the read (CA #661)")
rid2 = se.create_round(900, 18, round_date="2026-09-30", label="second round")["round_id"]
out = se.get_entered_scores(900)
check("rounds plural, event-scoped", [r["round_id"] for r in out["rounds"]] == [rid, rid2])
check("one version for the event", out["version"] == se.event_version(900))
check("not official", out["official"] is False and out["source"] == "tgf-entry")
r1 = out["rounds"][0]
k = {p["customer_id"]: p for p in r1["players"]}
check("gross only, keyed by customer_id",
      k[101]["scores"] == {"1": 3} and k[101]["thru"] == 1 and k[101]["playing_handicap"] == 2)
check("missing holes are absent, not zero", k[102]["scores"] == {} and k[102]["thru"] == 0)
check("group shows scorer and lock", r1["groups"][0]["scorer_customer_id"] == 102
      and r1["groups"][0]["lock_state"] == "held")
check("team present with both ids",
      r1["teams"][0]["customer_ids"] == [101, 103] and r1["teams"][0]["scores"] == {"1": 4})
check("round_id filter", [r["round_id"] for r in se.get_entered_scores(900, rid2)["rounds"]] == [rid2])
check("course carried", len(r1["course"]) == 9 and r1["course"][2]["par"] == 5)

print("links")
tok = se.make_group_token(gid)
check("a group link verifies", se.verify_group_token(tok) == gid)
check("a tampered link fails", se.verify_group_token(tok[:-1] + ("0" if tok[-1] != "0" else "1")) is None)
se.revoke_group_links(gid)
check("a revoked link fails", se.verify_group_token(tok) is None)
tok2 = se.make_group_token(gid)
conn.execute("UPDATE se_rounds SET status = 'closed' WHERE id = ?", (rid,))
conn.commit()
check("a closed round's link fails", se.verify_group_token(tok2) is None)

print("identity (principle 6)")
PERSONISH = re.compile(r"(name|customer|player|scorer|holder|entered_by)", re.I)
for tname in [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'se\\_%' ESCAPE '\\'")]:
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tname})")]
    for c in cols:
        if c.endswith("_name") or c == "display_name":
            # The repo rule (test_customer_id_everywhere.py): <prefix>_name
            # sits beside <prefix>_customer_id (or the row's customer_id).
            pre = c[:-5]
            check(f"{tname}.{c} has customer_id beside it",
                  "customer_id" in cols or f"{pre}_customer_id" in cols)
        if PERSONISH.search(c) and c.endswith("_id") and "customer" not in c:
            check(f"{tname}.{c} is not a person key without customer_id", False)

print("portable-SQL rule (CA #682) on the score-entry module")
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "email_parser", "score_entry.py")).read()
for pat, why in [(r"\bNOCASE\b", "COLLATE NOCASE"), (r"INSERT\s+OR\s+(REPLACE|IGNORE)", "INSERT OR ..."),
                 (r"\blastrowid\b", "lastrowid"), (r"ALTER\s+TABLE", "try-ALTER")]:
    check(f"no {why}", not re.search(pat, _src, re.I))

print("GG stays the money record")
ROOT = os.path.dirname(os.path.abspath(__file__))
readers = []
for dirpath, _, files in os.walk(ROOT):
    if any(p in dirpath for p in ("/.git", "/node_modules", "/docs")):
        continue
    for f in files:
        if not f.endswith(".py") or f.startswith("test_"):
            continue
        path = os.path.join(dirpath, f)
        if path.endswith(os.path.join("email_parser", "score_entry.py")):
            continue
        src = open(path, encoding="utf-8", errors="ignore").read()
        if re.search(r"\bse_(hole_scores|players|rounds|teams|groups)\b", src):
            readers.append(os.path.relpath(path, ROOT))
check("only score_entry.py touches se_* tables", readers == [], readers)
for f in ("season_payouts.py", "gg_match_play.py", "match_play.py", "flighting.py"):
    src = open(os.path.join(ROOT, "email_parser", f), encoding="utf-8").read()
    check(f"{f} does not import score_entry", "score_entry" not in src)

print("seed from PAIRINGS")
db._ensure_pairing_tables(conn)
for pos, (cid, nm) in enumerate([(101, "Kerry Niester"), (102, "Adam Baker")], 1):
    conn.execute("INSERT INTO event_pairings (event_id, holes, group_num, slot_label, "
                 "player_name, cart_pos, customer_id) VALUES (900, '9', 3, 'HOLE 4', ?, ?, ?)",
                 (nm, pos, cid))
conn.commit()
with contextlib.redirect_stdout(io.StringIO()):
    s = se.seed_round_from_pairings(900, "9")
check("seeded a round from PAIRINGS", "round_id" in s and s["groups"] == 1, s)
check("no course card is said out loud", "warning" in s, s)
gp = [x for x in se.get_entered_scores(900, s["round_id"])["rounds"][0]["players"]]
check("seeded players carry customer_id", sorted(p["customer_id"] for p in gp) == [101, 102], gp)
grp = se.get_entered_scores(900, s["round_id"])["rounds"][0]["groups"][0]
check("shotgun: start hole read from the sheet's hole label", grp["start_hole"] == 4, grp)
check("shotgun: tee time is the one start clock", grp["tee_time"] == "5:30 PM", grp)
with contextlib.redirect_stdout(io.StringIO()):
    s2 = se.seed_round_from_pairings(900, "9")
check("re-seed reuses the round", s2["round_id"] == s["round_id"], s2)

print("sign-off, flags, CTP, HIO (Kerry #666, ratified #667)")
conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (105, 'Mark', 'Stich')")
conn.execute("INSERT INTO customer_memberships (customer_id, started_at, expires_at) "
             "VALUES (101, '2026-01-01', '2026-12-31')") if conn.execute(
    "SELECT name FROM sqlite_master WHERE name='customer_memberships'").fetchone() else None
conn.commit()
sr = se.create_round(900, 9, round_date="2026-09-29", label="signoff", course_holes=NINE)["round_id"]
sg = se.upsert_group(sr, 1, players=[{"customer_id": c, "display_name": n, "playing_handicap": ph}
                                     for c, n, ph in [(101, "Kerry Niester", 2), (102, "Adam Baker", 7),
                                                      (105, "Mark Stich", 11)]])["group_id"]
se.claim_group(sg, "sk", 101)
ops = [{"op_id": f"S{c}-{h}", "customer_id": c, "hole": h, "gross": 4}
       for c in (101, 102, 105) for h in range(1, 9)]
se.write_scores(sg, "sk", 101, ops)
check("an incomplete card cannot be signed", "error" in se.sign_card(sg, "p2", 102))
se.write_scores(sg, "sk", 101, [{"op_id": f"S{c}-9", "customer_id": c, "hole": 9, "gross": 5}
                                for c in (101, 102, 105)])
check("a complete card signs", se.sign_card(sg, "p2", 102).get("signed"))
check("a non-scorekeeper phone cannot attest the group",
      "error" in se.sign_card(sg, "p2", 102, kind="scorekeeper"))
check("the scorekeeper attests", se.sign_card(sg, "sk", 101, kind="scorekeeper").get("signed"))
se.sign_card(sg, "p5", 105)
se.write_scores(sg, "sk", 101, [{"op_id": "S102-3b", "customer_id": 102, "hole": 3, "gross": 5}])
live = {(x["customer_id"], x["kind"]) for x in se.get_group_card(sg)["signoffs"]}
check("an edit voids that player's signature only",
      (102, "player") not in live and (105, "player") in live, live)
check("an edit voids the scorekeeper's attestation", (101, "scorekeeper") not in live, live)
se.write_scores(sg, "sk", 101, [{"op_id": "S102-3c", "customer_id": 102, "hole": 3, "gross": 5}])
check("re-writing the same value voids nothing",
      (105, "player") in {(x["customer_id"], x["kind"]) for x in se.get_group_card(sg)["signoffs"]})
fl = se.flag_hole(sg, "p5", 105, 6, "I had a 5")
live = {(x["customer_id"], x["kind"]) for x in se.get_group_card(sg)["signoffs"]}
check("a flag reopens only that player's card", (105, "player") not in live, live)
check("a flagged card cannot be signed", "error" in se.sign_card(sg, "p5", 105))
se.write_scores(sg, "sk", 101, [{"op_id": "S105-6b", "customer_id": 105, "hole": 6, "gross": 5}])
check("fixing the hole resolves the flag", se.get_group_card(sg)["flags"] == [])
check("then the card signs again", se.sign_card(sg, "p5", 105).get("signed"))
check("a manager signature needs a note", "error" in se.sign_card(sg, "admin", 101, kind="manager"))

print("match play: pickup marks (Kerry 2026-09-25)")
# sg's course is NINE; hole 1 is a par 4 -> triple is 7
mk = lambda op_id, cid, hole, gross, **kw: {"op_id": op_id, "customer_id": cid, "hole": hole, "gross": gross, **kw}
r = se.write_scores(sg, "sk", 101, [mk("MK1", 102, 1, 6, mark="picked_up")])["results"][0]
check("a pickup mark only goes on the triple", r["result"] == "invalid" and "triple" in r["why"], r)
r = se.write_scores(sg, "sk", 101, [mk("MK2", 102, 1, 7, mark="gimme")])["results"][0]
check("a mark is holed or picked_up, nothing else", r["result"] == "invalid", r)
se.write_scores(sg, "sk", 101, [mk("MK3", 102, 1, 7, mark="picked_up")])
check("the triple + picked up is stored beside the score",
      se.get_group_card(sg)["marks"].get("c:102") == {"1": "picked_up"}
      and se.get_group_card(sg)["scores"]["c:102"]["1"] == 7)
se.write_scores(sg, "sk", 101, [mk("MK4", 102, 1, 7)])
check("re-writing the triple without a mark keeps the mark",
      se.get_group_card(sg)["marks"].get("c:102") == {"1": "picked_up"})
se.write_scores(sg, "sk", 101, [mk("MK5", 102, 1, 7, mark="holed")])
check("ball in hole replaces picked up", se.get_group_card(sg)["marks"].get("c:102") == {"1": "holed"})
se.write_scores(sg, "sk", 101, [mk("MK6", 102, 1, 6)])
check("moving off the triple clears the mark", "c:102" not in se.get_group_card(sg)["marks"])
se.write_scores(sg, "sk", 101, [mk("MK7", 102, 1, 7, mark="picked_up")])
rd = {p["customer_id"]: p for p in se.get_entered_scores(900, sr)["rounds"][0]["players"]}
check("the read carries marks per player (Track B's shape)", rd[102]["marks"] == {"1": "picked_up"}
      and rd[101]["marks"] == {}, rd[102])
check("no match bound: the card says so", se.get_group_card(sg)["matches"] == {})
db.set_app_setting("lsc_matches", json.dumps({"event_id": 900, "sessions": [
    {"id": "s1", "format": "singles", "se_round": sr,
     "matches": [{"id": "M1", "austin": [101], "sa": [102]}]}]}))
mt = se.get_group_card(sg)["matches"]
check("a bound cup session tells the card who has a match, and against whom",
      mt.get("101", {}).get("opponents") == [102] and mt.get("102", {}).get("side") == "sa"
      and "105" not in mt, mt)
from email_parser.lsc_cup import lsc_board_payload
se.write_scores(sg, "sk", 101, [mk("MK9", 101, 1, 7, mark="holed")])
h1 = lambda: next(h for h in lsc_board_payload()["sessions"][0]["matches"][0]["holes"] if h["hole"] == 1)
x = h1()
check("end to end: Kerry holed 7, Adam picked up 7 -> Kerry (Austin) wins hole 1 on the cup board",
      x["winner"] == 1 and x["p2_picked_up"] and not x["p1_picked_up"], x)
se.write_scores(sg, "sk", 101, [mk("MK10", 101, 1, 7, mark="picked_up")])
x = h1()
check("...both picked up -> the hole is a push, both cards still 7",
      x["winner"] == 0 and x["p1_gross"] == 7 and x["p2_gross"] == 7, x)
ms = se.get_group_card(sg)["match_status"]
bd = lsc_board_payload()["sessions"][0]["matches"][0]
check("the phone's match standing is the cup board's (same engine, same numbers)",
      len(ms) == 1 and ms[0]["margin"] == bd["gg_margin"] and ms[0]["thru"] == bd["thru"]
      and ms[0]["holes"].get("1") == 0 and ms[0]["names"] == ["Kerry", "Adam"], (ms, bd.get("gg_margin")))
db.set_app_setting("lsc_matches", "")
se.write_scores(sg, "sk", 101, [mk("MK8", 102, 1, 5), mk("MK11", 101, 1, 4)])
check("a round-level match must use players in the round",
      "error" in se.set_round_matches(sr, [{"id": "X", "sides": [[101], [999]]}]))
se.set_round_matches(sr, [{"id": "DEMO-1", "format": "singles", "sides": [[102], [105]]}])
mt = se.get_group_card(sg)["matches"]
check("a round-level match (the preview's demo) also marks who has a match",
      mt.get("102", {}).get("opponents") == [105] and "101" not in mt, mt)
st = se.round_status(900)
rs = next(r for r in st["rounds"] if r["round_id"] == sr)
check("round_status reads holes in, signatures and matches",
      rs["holes"] == 9 and any(p["customer_id"] == 102 and p["thru"] == 9 for p in rs["players"])
      and "102" in {str(k) for k in rs["matches"]}, rs["players"][:2])
se.set_round_matches(sr, None)
check("the round-level match clears", se.get_group_card(sg)["matches"] == {})

print("card check + submit + photo (Kerry 2026-09-25)")
check("only the scorekeeper's phone submits",
      "error" in se.submit_card(sg, "p2", 101, print_scorer_customer_id=102))
check("submit needs who kept the paper card", "error" in se.submit_card(sg, "sk", 101))
check("a print scorer given by id must be in the group",
      "error" in se.submit_card(sg, "sk", 101, print_scorer_customer_id=104))
check("the keeper-signs dial is off by default", not se.keeper_signs(900))
r = se.submit_card(sg, "sk", 101, print_scorer_customer_id=102, photo_op_id="PH-1")
live = {(x["customer_id"], x["kind"]): x for x in se.get_group_card(sg)["signoffs"]}
check("dial off: submit attests, signs nobody's card", r.get("submitted") and r["signed_for"] == []
      and (101, "scorekeeper") in live and (102, "player") not in live, (r, live))
se.set_keeper_signs(900, True)
se.flag_hole(sg, "p2", 102, 4)
r = se.submit_card(sg, "sk", 101, print_scorer_name="  Joe Caddie  ", photo_op_id="PH-2")
live = {(x["customer_id"], x["kind"]): x for x in se.get_group_card(sg)["signoffs"]}
check("dial on: the scorekeeper's own card is signed", 101 in r["signed_for"], r)
check("...a flagged card is left alone", {"customer_id": 102, "why": "flagged"} in r["skipped"], r)
check("...a card the player signed himself is left alone",
      {"customer_id": 105, "why": "signed it himself"} in r["skipped"]
      and live[(105, "player")]["signed_by_customer_id"] == 105, (r, live))
cc = se.get_group_card(sg)["card_check"]
check("the check row keeps a name only when the scorer is not a player",
      cc["print_scorer_name"] == "Joe Caddie" and cc["print_scorer_customer_id"] is None
      and cc["signed_for_group"] == 1, cc)
se.write_scores(sg, "sk", 101, [{"op_id": "S101-2x", "customer_id": 101, "hole": 2, "gross": 3}])
live = {(x["customer_id"], x["kind"]) for x in se.get_group_card(sg)["signoffs"]}
check("an edit voids a signature the scorekeeper made for you, like your own",
      (101, "player") not in live and (101, "scorekeeper") not in live, live)
se.write_scores(sg, "sk", 101, [{"op_id": "S102-4x", "customer_id": 102, "hole": 4, "gross": 6}])
from PIL import Image as _Im
import io as _io
_buf = _io.BytesIO(); _Im.new("RGB", (40, 30), (200, 200, 200)).save(_buf, "JPEG"); JPG = _buf.getvalue()
check("a photo before its submit is refused", "error" in se.attach_card_photo(sg, "sk", "PH-none", JPG))
check("a photo must be a JPEG", "error" in se.attach_card_photo(sg, "sk", "PH-2", b"GIF89a....."))
check("a photo over 3 MB is refused",
      "error" in se.attach_card_photo(sg, "sk", "PH-2", b"\xff\xd8\xff" + b"0" * (3 * 1024 * 1024)))
ph = se.attach_card_photo(sg, "sk", "PH-2", JPG)
check("the photo lands on its check row", ph.get("saved") and ph["check_id"] == cc["id"], ph)
check("a retry of the same photo is a no-op", se.attach_card_photo(sg, "sk", "PH-2", JPG).get("dup"))
pp = se.card_photo_path(cc["id"])
check("the photo is a file beside the database, not a blob in it",
      pp is not None and pp.read_bytes() == JPG and "se_photos" in str(pp), pp)
rd = se.get_entered_scores(900, sr)["rounds"][0]
check("the read carries the card checks with has_photo",
      any(x["check_id"] == cc["id"] and x["has_photo"] for x in rd["card_checks"]), rd["card_checks"])
check("the read says who signed each card",
      all("signed_by_customer_id" in x for x in rd["signoffs"]), rd["signoffs"][:2])
se.set_keeper_signs(900, False)
check("the dial turns off again", not se.keeper_signs(900))

# CTP: hole 2 is the par 3 in NINE
sg2 = se.upsert_group(sr, 2, players=[{"customer_id": 103, "display_name": "Chris Best"},
                                      {"customer_id": 104, "display_name": "Robert Hogue"}])["group_id"]
se.claim_group(sg2, "sk2", 103)
check("CTP is par 3s only", "error" in se.claim_ctp(sg, "sk", 1, 102))
check("only the scorekeeper answers CTP", "error" in se.claim_ctp(sg, "p2", 2, 102))
se.claim_ctp(sg, "sk", 2, 102, claimed_by=101)
c2 = se.get_group_card(sg2)["ctp"]["2"]
check("the next group sees the current holder",
      c2["holder_customer_id"] == 102 and c2["holder_group_num"] == 1 and not c2["answered"], c2)
se.claim_ctp(sg2, "sk2", 2, None)
check("'No one closer' keeps the holder", se.get_group_card(sg2)["ctp"]["2"]["holder_customer_id"] == 102)
se.claim_ctp(sg2, "sk2", 2, 104)
check("a closer claim takes over", se.get_group_card(sg)["ctp"]["2"]["holder_customer_id"] == 104)
se.rule_ctp(sr, 2, 102)
check("a manager ruling settles it", se.get_group_card(sg)["ctp"]["2"]["holder_customer_id"] == 102)

# HIO on hole 2
se.write_scores(sg, "sk", 101, [{"op_id": "H101", "customer_id": 101, "hole": 2, "gross": 1},
                                {"op_id": "H102", "customer_id": 102, "hole": 2, "gross": 1}])
hio = {h["customer_id"]: h for h in se.get_group_card(sg)["hio"]}
check("a raw 1 opens a claim", 101 in hio and hio[101]["status"] == "pending", hio)
has_mem = conn.execute("SELECT name FROM sqlite_master WHERE name='customer_memberships'").fetchone()
if has_mem:
    check("a non-member's 1 is a score only", hio[102]["eligible"] == 0, hio)
    check("...and cannot be confirmed", "error" in se.confirm_hio(sg, "sk", hio[102]["id"], 101))
hid = hio[101]["id"]
check("the scorekeeper confirms first", "error" in se.confirm_hio(sg, "p5", hid, 105))
check("scorekeeper confirms", se.confirm_hio(sg, "sk", hid, 101).get("ok"))
check("the ace-maker cannot be the witness", "error" in se.confirm_hio(sg, "p1", hid, 101))
check("the manager cannot verify before a witness", "error" in se.verify_hio(hid, "admin"))
check("another player witnesses", se.confirm_hio(sg, "p5", hid, 105).get("ok"))
check("the manager verifies", se.verify_hio(hid, "admin").get("ok"))
check("verified", {h["id"]: h for h in se.get_group_card(sg)["hio"]}[hid]["status"] == "verified")
se.write_scores(sg, "sk", 101, [{"op_id": "H102b", "customer_id": 102, "hole": 2, "gross": 3}])
check("changing a 1 withdraws an unverified claim",
      102 not in {h["customer_id"] for h in se.get_group_card(sg)["hio"]})
st = se.get_group_card(sg)["strokes"]
check("strokes per hole come off the locked PH", st.get("102") == {str(h): 1 for h in (3, 7, 1, 9, 4, 8, 5)}, st)
check("a PH the card's indexes can't carry is reported, not guessed", st.get("_unresolved") == [105], st)
check("a nine carries the GG-convention note",
      se.get_group_card(sg)["strokes_note"] == "strokes per GG convention")

print("cart-sign QR (Kerry #666 B), behind the score_entry_qr dial")
pack = db.get_event_print_pack(900)
res = se.attach_cart_sign_qr(pack)
check("no dial, no code", res["groups"] == 0 and not any(g.get("score_qr") for g in pack["groups"]), res)
db.set_app_setting("score_entry_qr", '{"900": [3]}')
pack = db.get_event_print_pack(900)
res = se.attach_cart_sign_qr(pack, base_url="https://x.test")
qg = [g for g in pack["groups"] if g.get("score_qr")]
check("the dial's group gets a code", res["groups"] == 1 and qg and qg[0]["group_num"] == 3, res)
check("the code is inline SVG pointing at the group's link",
      qg and qg[0]["score_qr"]["svg"].startswith("<svg") and "/member/score?t=" in qg[0]["score_qr"]["url"])
tokq = qg[0]["score_qr"]["url"].split("t=", 1)[1] if qg else ""
check("the printed link opens that group", se.verify_group_token(tokq) is not None)
db.set_app_setting("score_entry_qr", "not json")
check("a bad dial prints the old sign", se.attach_cart_sign_qr(db.get_event_print_pack(900))["groups"] == 0)
db.set_app_setting("score_entry_qr", "")

print("PREVIEW round + links + close")
pv = se.create_preview_round(900, [101, 102])
check("preview round is created", "round_id" in pv and not pv["reused"], pv)
pv2 = se.create_preview_round(900, [101, 102, 103])
check("a second call reuses the preview round", pv2["round_id"] == pv["round_id"] and pv2["reused"], pv2)
check("the preview is never the PAIRINGS round",
      se.seed_round_from_pairings(900, "9")["round_id"] != pv["round_id"])
lk = se.round_links(pv["round_id"], base_url="https://x.test")
check("one link per group with its players",
      len(lk) == 1 and lk[0]["players"] == ["Kerry Niester", "Adam Baker", "Chris Best"], lk)
ptok = lk[0]["url"].split("t=", 1)[1]
check("the preview link opens", se.verify_group_token(ptok) == pv["group_id"])
check("unknown people are refused", "error" in se.create_preview_round(900, [424242]))
se.close_round(pv["round_id"])
check("closing kills the link", se.verify_group_token(ptok) is None)
check("closed round's rows are kept", any(r["round_id"] == pv["round_id"]
                                          for r in se.get_entered_scores(900)["rounds"]))

print("tee colour bar (Kerry 2026-09-25): the tee sheet's own legend")
cc = sqlite3.connect(DB); cc.row_factory = sqlite3.Row
db._ensure_scoring_tables(cc)
cc.execute("INSERT INTO courses (course_id, name) VALUES (7700, 'Tee Test GC')")
for tid, nm, gen, bands in [(77001, "Blue", "M", "<50"), (77002, "White", "M", "50-64,65+"),
                            (77003, "Red (L)", "F", "Forward")]:
    cc.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, gender, holes, rating, slope, "
               "yardage_total, tgf_bands) VALUES (?,?,?,?,18,70.1,125,6400,?)", (tid, 7700, nm, gen, bands))
cc.execute("INSERT INTO events (id, item_name, event_date, course_id) VALUES (901, 'Tee test', '2026-09-29', 7700)")
cc.commit()
legend = {t_["band"]: t_ for t_ in db.event_tee_legend(cc, 901, dict(cc.execute("SELECT * FROM events WHERE id=901").fetchone()))}
cc.close()
tr = se.create_round(901, 9, course_holes=NINE)["round_id"]
tg = se.upsert_group(tr, 1, players=[
    {"customer_id": 101, "display_name": "Kerry Niester", "tee": "<50"},
    {"customer_id": 102, "display_name": "Adam Baker", "tee": "50-64"},
    {"customer_id": 103, "display_name": "Chris Best", "tee": "Forward"},
    {"customer_id": 104, "display_name": "Robert Hogue"}])["group_id"]
tees = se.get_group_card(tg)["tees"]
check("the card carries the tee sheet's legend, colour for colour",
      set(tees) == set(legend) and all(tees[b]["color"] == legend[b]["color"] for b in legend), (tees, legend))
check("the women's tee is marked as an outline, as on the sheet", tees.get("Forward", {}).get("ring") is True, tees)
check("a player with no tee has no colour here (the screen shows grey, never a guess)",
      not se.get_group_card(tg)["players"][3]["tee"])
check("an event with no course card gives no colours, not an error", se.get_group_card(gid)["tees"] == {})

print("HTTP (admin builds, scorer by link, flag off until Kerry OKs)")
os.environ.setdefault("SECRET_KEY", "test-secret")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as appmod
client = appmod.app.test_client()
check("anonymous cannot read the board",
      client.get("/api/score-entry/events/900/scores").status_code in (401, 403, 302))
check("anonymous cannot open the Live Scoring page",
      client.get("/events/900/live-scoring").status_code in (401, 403, 302))
check("anonymous cannot read the Live Scoring overview",
      client.get("/api/score-entry/events/900/admin").status_code in (401, 403, 302))
check("anonymous cannot build a round",
      client.post("/api/score-entry/rounds", json={"event_id": 900, "holes": 9}).status_code
      in (401, 403, 302))
with client.session_transaction() as sess:
    sess["role"] = "admin"; sess["authenticated"] = True
r = client.post("/api/score-entry/rounds", json={"event_id": 900, "holes": 9,
                                                 "course": NINE, "label": "http"})
check("admin builds a round", r.status_code == 201, r.get_data(as_text=True))
hrid = r.get_json()["round_id"]
r = client.post(f"/api/score-entry/rounds/{hrid}/groups", json={
    "group_num": 1, "players": [{"customer_id": 104, "display_name": "Robert Hogue"}]})
hgid = r.get_json()["group_id"]
links = client.get(f"/api/score-entry/rounds/{hrid}/links").get_json()
check("one link per group, with its players",
      len(links) == 1 and links[0]["players"] == ["Robert Hogue"] and "/member/score?t=" in links[0]["url"],
      links)
htok = links[0]["url"].split("t=", 1)[1]
full = client.get("/api/score-entry/events/900/scores").get_json()
r304 = client.get(f"/api/score-entry/events/900/scores?since_version={full['version']}")
check("unchanged version is a 304", r304.status_code == 304, r304.status_code)
check("stale version returns the body",
      client.get("/api/score-entry/events/900/scores?since_version=0").status_code == 200)
anon = appmod.app.test_client()
check("scorer routes are OFF for a member until the flag is set",
      anon.get(f"/api/score-entry/card?t={htok}").status_code == 404)
db.set_app_setting("score_entry_live", "1")
check("a bad link is refused", anon.get("/api/score-entry/card?t=nope.nope").status_code == 401)
c = anon.post("/api/score-entry/claim", json={"t": htok, "device_id": "d1", "customer_id": 104})
check("scorer claims by link", c.status_code == 200 and c.get_json()["granted"], c.get_json())
w = anon.post("/api/score-entry/write", json={"t": htok, "device_id": "d1", "entered_by": 104,
                                              "ops": [{"op_id": "H1", "customer_id": 104,
                                                       "hole": 1, "gross": 5}]})
check("scorer writes by link", w.get_json()["results"][0]["result"] == "ok", w.get_json())
card = anon.get(f"/api/score-entry/card?t={htok}&device_id=d1").get_json()
check("card shows the hole", card["scores"]["c:104"]["1"] == 5 and card["lock"]["state"] == "mine")
check("the scoring page renders", anon.get(f"/member/score?t={htok}").status_code == 200)
pg = client.get("/events/900/live-scoring")
check("admin: the Live Scoring page renders", pg.status_code == 200 and b"LIVE SCORING" in pg.data)
ov = client.get("/api/score-entry/events/900/admin").get_json()
g0 = [g for r in ov["rounds"] for g in r["groups"]]
check("admin: the overview lists every round's groups with a working link and holes in",
      ov["rounds"] and all(g["url"] and "/member/score?t=" in g["url"] for g in g0)
      and all("holes_in" in g and "players" in g for g in g0), ov["rounds"][:1])
check("admin: the overview carries the dials", {"live_for_members", "keeper_signs", "qr"} <= set(ov))
pv = se.create_preview_round(900, [101, 102], holes=18, tees={101: "<50", 102: "65+"})
se.set_round_matches(pv["round_id"], [{"id": "P-1", "format": "singles", "sides": [[101], [102]]}])
check("only a PREVIEW round can be started over",
      "error" in client.post(f"/api/score-entry/rounds/{sr}/restart-preview").get_json())
rs = client.post(f"/api/score-entry/rounds/{pv['round_id']}/restart-preview").get_json()
old = se.get_entered_scores(900, pv["round_id"])["rounds"][0]
check("starting a preview over closes the old one (kept, not deleted) and opens a fresh one",
      rs.get("round_id") and rs["round_id"] != pv["round_id"] and old["status"] == "closed"
      and rs["links"] and rs["holes"] == 18, rs)
check("...with the same players and the demo match moved across",
      se.round_matches(rs["round_id"]).get(101, {}).get("opponents") == [102]
      and not se.round_matches(pv["round_id"]), se.round_matches(rs["round_id"]))
tz = {p["customer_id"]: p["tee"] for p in se.get_entered_scores(900, rs["round_id"])["rounds"][0]["players"]}
check("...and each player's tee", tz == {101: "<50", 102: "65+"}, tz)

conn.close()
try:
    os.unlink(DB)
except OSError:
    pass
print("ALL PASS" if not FAILURES else f"{len(FAILURES)} FAILURE(S): {FAILURES}")
sys.exit(1 if FAILURES else 0)
