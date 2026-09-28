"""G-0 keystone: publishing entered scores (CA #786 GO 1).

- Dry run writes nothing; apply writes one scoring_rounds row per eligible
  player (source='entry', customer_id, gross, holes) + its scoring_holes.
- Unsigned / not-submitted / incomplete players are HELD, never written.
- Re-publishing is idempotent; an edit voids the signature (held, stale
  reported), and a re-sign updates the same row.
- Shadow mode (event with GG rows, or before the cutover) writes nothing
  and returns a per-hole diff against the GG cards.
- The GG import refuses to add rows to an event whose record is entered.
- Tee resolution by band (via the event tee legend) and by name; an
  unknown tee is published with tee_id NULL and reported.

Fixtures are built through score_entry's public functions only.

Run: python3 test_entry_publish.py
"""
import contextlib
import io
import logging
import os
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
from email_parser import entry_publish as ep  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)


def q(sql, args=()):
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(sql, args).fetchall()]
    finally:
        c.close()


conn = sqlite3.connect(DB)
for cid, fn, ln in [(201, "Kerry", "Niester"), (202, "Adam", "Baker"), (203, "Chris", "Best"),
                    (204, "Robert", "Hogue"), (205, "Luke", "Youngs"), (206, "Neal", "Cloer")]:
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)",
                 (cid, fn, ln))
course_id = conn.execute("INSERT INTO courses (name, status) VALUES ('Test Links', 'active') "
                         "RETURNING course_id").fetchone()[0]
TEES = [  # name, gender, holes, nine, rating, slope, bands
    ("White", "M", 18, "full", 68.1, 121, "50-64,65+"),
    ("White", "M", 9, "front", 34.0, 120, None),
    ("White", "M", 9, "back", 34.1, 122, None),
    ("Blue", "M", 18, "full", 71.0, 128, "<50"),
    ("Blue", "M", 9, "front", 35.5, 125, None),
    ("Red", "F", 9, "front", 35.0, 118, "Forward"),
]
tee_ids = {}
for nm, g, holes, nine, rating, slope, bands in TEES:
    tee_ids[(nm, holes, nine)] = conn.execute(
        "INSERT INTO course_tees (course_id, tee_name, gender, holes, nine, rating, slope, "
        "tgf_bands, source) VALUES (?,?,?,?,?,?,?,?, 'admin') RETURNING tee_id",
        (course_id, nm, g, holes, nine, rating, slope, bands)).fetchone()[0]
EV_A, EV_B, EV_C = 910, 911, 912
conn.execute("INSERT INTO events (id, item_name, event_date, course_id) VALUES (?,?,?,?)",
             (EV_A, "s10.13 Test Links", "2026-10-13", course_id))
conn.execute("INSERT INTO events (id, item_name, event_date, course_id) VALUES (?,?,?,?)",
             (EV_B, "s9.29 Test Links", "2026-09-29", course_id))
conn.execute("INSERT INTO events (id, item_name, event_date, course_id) VALUES (?,?,?,?)",
             (EV_C, "s10.1 Test Links", "2026-10-01", course_id))
conn.commit()
conn.close()

NINE = [{"hole": h, "par": p, "stroke_index": si} for h, p, si in
        [(1, 4, 3), (2, 3, 9), (3, 5, 1), (4, 4, 5), (5, 4, 7), (6, 3, 8),
         (7, 4, 2), (8, 4, 6), (9, 5, 4)]]
CARD = {1: 5, 2: 3, 3: 6, 4: 4, 5: 5, 6: 3, 7: 4, 8: 5, 9: 6}   # 41
_op = [0]


def write(gid, dev, cid, card, holes=None):
    ops = []
    for h in (holes or card):
        _op[0] += 1
        ops.append({"op_id": f"op{_op[0]}", "hole": h, "gross": card[h], "customer_id": cid})
    r = se.write_scores(gid, dev, cid, ops, db_path=DB)
    assert all(x["result"] == "ok" for x in r["results"]), r


print("fixture: event A (10/13, no GG) — round, two groups")
rid = se.create_round(EV_A, 9, round_date="2026-10-13", label="s10.13", course_holes=NINE,
                      course_id=course_id, db_path=DB)["round_id"]
g1 = se.upsert_group(rid, 1, players=[
    {"customer_id": 201, "display_name": "Kerry N", "tee": "50-64", "playing_handicap": 5},
    {"customer_id": 202, "display_name": "Adam B", "tee": "Blue", "playing_handicap": 3},
    {"customer_id": 203, "display_name": "Chris B", "tee": "Gold", "playing_handicap": None},
    {"customer_id": 204, "display_name": "Robert H", "tee": "50-64", "playing_handicap": 8},
], db_path=DB)["group_id"]
g2 = se.upsert_group(rid, 2, players=[
    {"customer_id": 205, "display_name": "Luke Y", "tee": "<50", "playing_handicap": 1}],
    db_path=DB)["group_id"]
se.claim_group(g1, "dev1", 201, db_path=DB)
se.claim_group(g2, "dev2", 205, db_path=DB)
for c in (201, 202, 203, 204):
    write(g1, "dev1", c, CARD)
write(g2, "dev2", 205, CARD, holes=[1, 2, 3, 4, 5, 6, 7, 8])      # 8 of 9: incomplete
for c in (201, 202, 203):
    check(f"player {c} signs", se.sign_card(g1, "dev1", c, "player", db_path=DB).get("signed"))

print("eligibility: round open, card not submitted")
dry = ep.publish_event(EV_A, db_path=DB)
check("event A is authoritative", dry["mode"] == "authoritative", dry["mode_reason"])
r0 = dry["rounds"][0]
check("nothing eligible while the round is open and unsubmitted",
      r0["would_write"] == [] and len(r0["held"]) == 5, r0)

print("submit group 1's card")
sub = se.submit_card(g1, "dev1", 201, print_scorer_name="Paper Guy", db_path=DB)
check("submit ok", sub.get("submitted"), sub)
dry = ep.publish_event(EV_A, db_path=DB)
r0 = dry["rounds"][0]
would = {w["customer_id"]: w for w in r0["would_write"]}
held = {h["customer_id"]: h["reason"] for h in r0["held"]}
check("dry run would write the three signed players", sorted(would) == [201, 202, 203], r0)
check("unsigned player is held", "signed" in (held.get(204) or ""), held)
check("group 2 (not submitted, incomplete) is held", 205 in held, held)
check("dry run writes nothing",
      q("SELECT COUNT(*) AS n FROM scoring_rounds")[0]["n"] == 0)
check("dry-run gross is the card total", would[201]["gross"] == 41, would[201])
check("net = gross - PH", would[201]["net"] == 36, would[201])

print("tee resolution")
check("band 50-64 -> the legend's White, nine-hole front row",
      would[201]["tee_id"] == tee_ids[("White", 9, "front")], would[201])
check("name Blue -> Blue nine-hole front row",
      would[202]["tee_id"] == tee_ids[("Blue", 9, "front")], would[202])
unres = {u["customer_id"]: u for u in r0["tee_unresolved"]}
check("unknown tee Gold is published with tee_id NULL and reported",
      would[203]["tee_id"] is None and 203 in unres, r0["tee_unresolved"])

print("close the round: group 2's incomplete card stays held")
se.close_round(rid, db_path=DB)
dry = ep.publish_event(EV_A, db_path=DB)
held = {h["customer_id"]: h["reason"] for h in dry["rounds"][0]["held"]}
check("incomplete/unsigned group-2 player still held after close", 205 in held, held)

print("apply (authoritative)")
app = ep.publish_event(EV_A, apply=True, db_path=DB)
check("applied", app["applied"] is True, app)
rows = q("SELECT * FROM scoring_rounds WHERE event_id = ? ORDER BY customer_id", (EV_A,))
check("one row per eligible player", [r["customer_id"] for r in rows] == [201, 202, 203], rows)
check("source='entry' on every row", all(r["source"] == "entry" for r in rows))
check("gg_aggregate_id is entry:<round>", all(r["gg_aggregate_id"] == f"entry:{rid}" for r in rows))
check("gross / holes_played / PH", rows[0]["gross"] == 41 and rows[0]["holes_played"] == 9
      and rows[0]["playing_handicap"] == 5, rows[0])
check("player_name from customers", rows[0]["player_name"] == "Kerry Niester", rows[0])
check("course_id from the round", rows[0]["course_id"] == course_id, rows[0])
check("round_date", rows[0]["round_date"] == "2026-10-13", rows[0])
hs = q("SELECT hole_number, strokes, strokes_received FROM scoring_holes WHERE scoring_round_id = ? "
       "ORDER BY hole_number", (rows[0]["id"],))
# PH 5 on a nine: the ruled allocation collapses the nine's SI to 1-9 and
# gives one stroke to SI 1-5 = holes 3, 7, 1, 9, 4 (CA #865/#866/#868:
# a stored 0 made every reader that trusts pops read net = gross).
check("nine scoring_holes, strokes = gross",
      len(hs) == 9 and all(h["strokes"] == CARD[h["hole_number"]] for h in hs), hs)
check("strokes_received = the ruled allocation of PH 5 (holes 1, 3, 4, 7, 9)",
      {h["hole_number"] for h in hs if h["strokes_received"] == 1} == {1, 3, 4, 7, 9}
      and sum(h["strokes_received"] for h in hs) == 5, hs)

print("idempotent re-publish")
ep.publish_event(EV_A, apply=True, db_path=DB)
check("no duplicate rows", q("SELECT COUNT(*) AS n FROM scoring_rounds")[0]["n"] == 3)
check("no duplicate holes", q("SELECT COUNT(*) AS n FROM scoring_holes")[0]["n"] == 27)

print("edit + re-sign")
se.claim_group(g1, "dev1", 201, db_path=DB)
_op[0] += 1
se.write_scores(g1, "dev1", 201, [{"op_id": f"op{_op[0]}", "hole": 1, "gross": 4,
                                   "customer_id": 201}], db_path=DB)
mid = ep.publish_event(EV_A, apply=True, db_path=DB)
r0 = mid["rounds"][0]
check("the edit voids his signature: held", any(h["customer_id"] == 201 for h in r0["held"]), r0)
check("his earlier row is reported stale, not deleted",
      any(s["customer_id"] == 201 for s in r0["stale"])
      and q("SELECT gross FROM scoring_rounds WHERE customer_id = 201")[0]["gross"] == 41, r0)
se.sign_card(g1, "dev1", 201, "player", db_path=DB)
ep.publish_event(EV_A, apply=True, db_path=DB)
r201 = q("SELECT id, gross, net FROM scoring_rounds WHERE customer_id = 201")
check("re-sign updates the same row (one row, gross 40)",
      len(r201) == 1 and r201[0]["gross"] == 40 and r201[0]["net"] == 35, r201)
check("hole 1 updated", q("SELECT strokes FROM scoring_holes WHERE scoring_round_id = ? "
                          "AND hole_number = 1", (r201[0]["id"],))[0]["strokes"] == 4)
check("still three rows", q("SELECT COUNT(*) AS n FROM scoring_rounds")[0]["n"] == 3)
one = ep.publish_entered_round(round_id=rid, db_path=DB)
check("publish_entered_round(round_id) dry run works", one.get("mode") == "authoritative"
      and len(one["rounds"]) == 1, one)

print("shadow mode: event B has a GG card")
c = sqlite3.connect(DB)
srid = c.execute("INSERT INTO scoring_rounds (customer_id, player_name, event_id, gg_aggregate_id, "
                 "round_date, holes_played, gross, source) VALUES (201, 'NIESTER, Kerry', ?, "
                 "'GG1', '2026-09-29', 9, 41, 'gg') RETURNING id", (EV_B,)).fetchone()[0]
for h, v in CARD.items():
    c.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, strokes) VALUES (?,?,?)",
              (srid, h, v))
srid2 = c.execute("INSERT INTO scoring_rounds (customer_id, player_name, event_id, gg_aggregate_id, "
                  "round_date, holes_played, gross, source) VALUES (206, 'CLOER, Neal', ?, "
                  "'GG2', '2026-09-29', 9, 44, 'gg') RETURNING id", (EV_B,)).fetchone()[0]
c.commit()
c.close()
rb = se.create_round(EV_B, 9, round_date="2026-09-29", course_holes=NINE, db_path=DB)["round_id"]
gb = se.upsert_group(rb, 1, players=[
    {"customer_id": 201, "tee": "50-64", "playing_handicap": 5},
    {"customer_id": 202, "tee": "Blue", "playing_handicap": 3}], db_path=DB)["group_id"]
se.claim_group(gb, "devB", 201, db_path=DB)
diff_card = dict(CARD)
diff_card[7] = 5
write(gb, "devB", 201, diff_card)
write(gb, "devB", 202, CARD)
se.sign_card(gb, "devB", 201, "player", db_path=DB)
se.close_round(rb, db_path=DB)
before = q("SELECT COUNT(*) AS n FROM scoring_rounds")[0]["n"]
sh = ep.publish_event(EV_B, apply=True, db_path=DB)
check("event B is shadow", sh["mode"] == "shadow", sh["mode_reason"])
check("shadow apply writes nothing", not sh["applied"]
      and q("SELECT COUNT(*) AS n FROM scoring_rounds")[0]["n"] == before)
par = ep.entry_parity(EV_B, db_path=DB)
pr = par["rounds"][0]
k = {p["customer_id"]: p for p in pr["players"]}
check("the differing hole is flagged",
      k.get(201) and k[201]["holes_differ"] == [{"hole": 7, "entered": 5, "gg": 4}], pr)
check("totals on both sides", k[201]["entered_total"] == 42 and k[201]["gg_total"] == 41, k.get(201))
check("entered-only player listed", [p["customer_id"] for p in pr["only_entered"]] == [202], pr)
check("GG-only player listed", [p["customer_id"] for p in pr["only_gg"]] == [206], pr)
check("shadow publish carries the parity diff", sh.get("parity", {}).get("summary", {})
      .get("holes_differing") == 1, sh.get("parity"))

print("cutover")
m = ep.publish_event(EV_C, db_path=DB)
check("event before the cutover with no GG rows is shadow",
      m["mode"] == "shadow" and "cutover" in m["mode_reason"], m["mode_reason"])
db.set_app_setting("entry_record_from", "2026-09-30", DB)
m = ep.publish_event(EV_C, db_path=DB)
check("moving the cutover setting makes it authoritative", m["mode"] == "authoritative", m)
db.set_app_setting("entry_record_from", "2026-10-10", DB)

print("GG import never doubles an entered record")
import golf_genius_sync  # noqa: E402
CIDS = {"NIESTER, Kerry": 201, "STRANGER, Sam": None}
db._resolve_scoring_player = lambda conn, name: CIDS.get(name)
db._bridge_handicap_records = lambda *a, **k: 0
db.verify_scoring_round = lambda srid, db_path=None: {"all_ok": True}
db.recompute_computed_mvps = lambda *a, **k: None


def gg_card(name, agg):
    return {"player_name": name, "gg_aggregate_id": agg, "gg_event_id": "1",
            "gg_profile_id": None, "playing_handicap": 5, "gross": 41, "net": 36,
            "flight": None, "tee": None,
            "holes": {h: {"strokes": v, "dots": 0, "result": None} for h, v in CARD.items()}}


golf_genius_sync.fetch_tournament_scorecards = \
    lambda url: {"players": [gg_card("NIESTER, Kerry", "X1"), gg_card("STRANGER, Sam", "X2")],
                 "raw": []}
n0 = q("SELECT COUNT(*) AS n FROM scoring_rounds")[0]["n"]
gi = db.import_gg_scorecards("https://x/t/9", event_code="s10.13 Test Links",
                             round_date="2026-10-13", db_path=DB)
check("event-level gate: nothing imported, reason given",
      gi.get("skipped_entry_record") and gi.get("imported") == 0
      and "entered scores are the record" in gi.get("reason", ""), gi)
check("no GG rows added to the entered event",
      q("SELECT COUNT(*) AS n FROM scoring_rounds")[0]["n"] == n0)
gi2 = db.import_gg_scorecards("https://x/t/10", round_date="2026-10-13", db_path=DB)
check("per-player gate: a keyless import skips the entered player",
      gi2.get("skipped_entry_record_players") == 1 and gi2.get("imported") == 1, gi2)
check("…and the entered player's row is untouched",
      q("SELECT COUNT(*) AS n FROM scoring_rounds WHERE customer_id = 201 AND event_id = ?",
        (EV_A,))[0]["n"] == 1
      and q("SELECT COUNT(*) AS n FROM scoring_rounds WHERE customer_id = 201 "
            "AND round_date = '2026-10-13'")[0]["n"] == 1)

print("this module stays off the score-entry tables")
# PREVIEW rounds are never published, in BOTH label forms score_entry uses
# (the plain label and "<label> · 18 holes"). The exact-match version let
# the 18-hole previews on s9.25 through as "would write" (live, 2026-09-28).
from email_parser import entry_publish as _ep  # noqa: E402
from email_parser import score_entry as _se  # noqa: E402
check("plain preview label is a preview", _ep._is_preview({"label": _se.PREVIEW_LABEL}))
check("18-hole preview label is a preview",
      _ep._is_preview({"label": f"{_se.PREVIEW_LABEL} · 18 holes"}))
check("a real round is not a preview", not _ep._is_preview({"label": "s9.25 Canyon Springs"}))
check("no label is not a preview", not _ep._is_preview({}))
_prev = _ep._publish_round(None, {"id": 1}, {"round_id": 99, "label": f"{_se.PREVIEW_LABEL} · 18 holes",
                                              "players": [{"customer_id": 5, "name": "X"}]},
                           "authoritative", True)
check("an 18-hole preview round is held, never written",
      not _prev.get("written") and _prev["held"] and "preview" in _prev["held"][0]["reason"], _prev)

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "email_parser", "entry_publish.py")).read()
import re  # noqa: E402
check("entry_publish.py never names a score-entry table",
      not re.search(r"\bse_(hole_scores|players|rounds|teams|groups|signoffs|card_checks)\b", src))
for pat, why in [(r"\bNOCASE\b", "COLLATE NOCASE"), (r"INSERT\s+OR\s+(REPLACE|IGNORE)", "INSERT OR"),
                 (r"\blastrowid\b", "lastrowid"), (r"ALTER\s+TABLE", "ALTER")]:
    check(f"portable SQL: no {why}", not re.search(pat, src, re.I))

print("tee: a bare name falls back to the other gender's row of the right length (3309 Red)")
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
bc = c.execute("INSERT INTO courses (name, status) VALUES ('Brack Test', 'active') "
               "RETURNING course_id").fetchone()[0]
ids = {}
for nm, g, holes, nine, rating, slope, bands in [
        ("Red", "F", 9, "front", 34.7, 120, "Forward"),     # GG 557
        ("Red", "F", 9, "back", 33.2, 120, "Forward"),      # GG 2894
        ("Red", "M", 18, "full", 64.0, 117, "Forward"),     # USGA 14679
        ("White", "M", 9, "front", 34.5, 124, "50-64"),
        ("White", "F", 9, "front", 36.0, 125, None)]:
    ids[(nm, g, nine)] = c.execute(
        "INSERT INTO course_tees (course_id, tee_name, gender, holes, nine, rating, slope, "
        "tgf_bands, source) VALUES (?,?,?,?,?,?,?,?, 'import') RETURNING tee_id",
        (bc, nm, g, holes, nine, rating, slope, bands)).fetchone()[0]
c.commit()
evb = {"id": None, "course_id": bc}
r = ep._resolve_tee(c, evb, bc, "Red", False, "front")
check("bare 'Red' on the front nine resolves to the women's front Red row",
      r["tee_id"] == ids[("Red", "F", "front")], r)
r = ep._resolve_tee(c, evb, bc, "Red", False, "back")
check("…and on the back nine to the women's back Red row", r["tee_id"] == ids[("Red", "F", "back")], r)
r = ep._resolve_tee(c, evb, bc, "Red", True, "full")
check("bare 'Red' for 18 holes still prefers the men's 18-hole row", r["tee_id"] == ids[("Red", "M", "full")], r)
r = ep._resolve_tee(c, evb, bc, "White", False, "front")
check("bare 'White' keeps the men's row when one exists (no gender swap)",
      r["tee_id"] == ids[("White", "M", "front")], r)
r = ep._resolve_tee(c, evb, bc, "White (L)", False, "front")
check("'White (L)' pins the women's row", r["tee_id"] == ids[("White", "F", "front")], r)
c.close()

try:
    os.remove(DB)
except OSError:
    pass
print(f"\n{'ALL PASS' if not FAILURES else f'{len(FAILURES)} FAILURE(S)'}")
sys.exit(1 if FAILURES else 0)
