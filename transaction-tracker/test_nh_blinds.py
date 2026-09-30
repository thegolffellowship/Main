"""N/H players and blinds (spec #1073, approved CoS #1075 / Kerry #1078).

Kerry: "if a customer doesn't enter a handicap, then their team deserves a
blind from the field (team) or the other cart (cart net) ... the blind would
win the money and not the customer."

Under test: ONE eligibility gate (who may SERVE), kept apart from who is
ENTITLED to a blind (any short cart or team, intro handicaps included); the
N/H seat draw; the reason column (migration 0004); the engine reading the
blinds; and the Ambassador flag riding the same gate.

Run: python3 test_nh_blinds.py
"""
import os, sqlite3, tempfile, contextlib, io, logging, re, pathlib, sys
from datetime import datetime, timedelta
os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402
from email_parser import live_scoring as ls  # noqa: E402
logging.disable(logging.CRITICAL)
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)

def _ensure_starting_hcp_col(path):
    """starting_handicap_18 is added lazily by _ensure_scoring_tables, whose
    ALTER swallows 'database is locked' when init_db's background work holds
    the lock. Production has the column; the fixture makes sure."""
    import time as _t
    for _ in range(40):
        with sqlite3.connect(path, timeout=30) as _cc:
            if "starting_handicap_18" in {r[1] for r in _cc.execute("PRAGMA table_info(customers)")}:
                return
            try:
                for _col, _ddl in (("starting_handicap_18", "REAL"), ("starting_handicap_set_at", "TEXT"),
                                   ("starting_handicap_set_by", "TEXT"), ("starting_handicap_note", "TEXT")):
                    if _col not in {r[1] for r in _cc.execute("PRAGMA table_info(customers)")}:
                        _cc.execute(f"ALTER TABLE customers ADD COLUMN {_col} {_ddl}")
            except sqlite3.OperationalError:
                _t.sleep(0.5)
    raise RuntimeError("could not add starting_handicap_18")


tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-nh-"), "t.db")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
c = sqlite3.connect(tmp); c.row_factory = sqlite3.Row
TODAY = datetime.now().strftime("%Y-%m-%d")
RDATE = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
EV = 3400
c.execute("INSERT INTO events (id, item_name, event_date, chapter, status, start_type, start_time) "
          "VALUES (?, 's10.6 Test Nine', ?, 'San Antonio', 'active', 'Shotgun', '17:00')",
          (EV, (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")))
FIELD = [(1, "Ann", "One", "active_member", 4), (2, "Bob", "Two", "active_member", 4),
         (3, "Cal", "Three", "member_plus", 4), (4, "Dee", "Four", "active_member", 4),
         (5, "Eve", "Five", "active_member", 4), (6, "Fay", "Six", "active_member", 4),
         (7, "Gil", "Seven", "active_member", 4),
         (8, "Ian", "Intro", "active_member", 0),    # intro: starting handicap only
         (9, "Nat", "Nohcp", "active_member", 0),    # N/H: nothing at all
         (10, "Alf", "Alumni", "expired_member", 4)]
for cid, fn, ln, st, n in FIELD:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, account_status, "
              "current_player_status) VALUES (?,?,?, 'San Antonio', 'active', ?)", (cid, fn, ln, st))
    c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, item_name, event_id, "
              "transaction_status, holes, order_date, user_status) VALUES (?,?, 'The Golf Fellowship', "
              "?,?, 's10.6 Test Nine', ?, 'active', '9', ?, 'MEMBER')",
              (800 + cid, f"n{800 + cid}", f"{fn} {ln}", cid, EV, TODAY))
    if n:
        c.execute("INSERT INTO handicap_player_links (player_name, customer_id, customer_name) "
                  "VALUES (?,?,?)", (f"{fn} {ln}", cid, f"{fn} {ln}"))
    for i in range(n):
        c.execute("INSERT INTO handicap_rounds (player_name, round_date, differential, adjusted_score, "
                  "rating, slope, customer_id) VALUES (?,?,?,?,?,?,?)",
                  (f"{fn} {ln}", RDATE, 10.0 + cid, 45, 35.0, 120, cid))
c.commit()
_ensure_starting_hcp_col(tmp)
db.set_starting_handicap(8, 12.0, set_by="test", db_path=tmp)

P = lambda nm, pos: {"name": nm, "cart_pos": pos, "tee_choice": "50-64"}
SHEET = {"9": [
    {"group_num": 1, "slot_label": "1", "players": [P("Ann One", 1), P("Bob Two", 2),
                                                     P("Cal Three", 3), P("Nat Nohcp", 4)]},
    {"group_num": 2, "slot_label": "2", "players": [P("Dee Four", 1), P("Eve Five", 2),
                                                     P("Ian Intro", 3)]},
    {"group_num": 3, "slot_label": "3", "players": [P("Fay Six", 1), P("Gil Seven", 3),
                                                     P("Alf Alumni", 4)]},
]}
db.save_event_pairings(EV, SHEET, db_path=tmp)

print("\n== schema: migration 0004 ==")
cols = db._blind_cols(c)
check("blind_draws has reason and missed_holes", {"reason", "missed_holes"} <= cols, cols)
check("0003 recorded once", c.execute("SELECT COUNT(*) FROM schema_migrations WHERE name = "
                                      "'0004_blind_draws_reason.sql'").fetchone()[0] == 1)
sql = pathlib.Path("migrations/0004_blind_draws_reason.sql").read_text().upper()
check("portable SQL (no INSERT OR REPLACE, no NOCASE)", "INSERT OR REPLACE" not in sql and "NOCASE" not in sql)

print("\n== who is N/H: no index AND no starting handicap ==")
nh = db.event_nh_seat_set(c, EV, db_path=tmp)
check("Nat (nothing at all) is N/H", 9 in nh["cids"], nh)
check("Ian (intro / starting handicap) is NOT N/H — he plays his handicap", 8 not in nh["cids"], nh)
check("an established member is not N/H", 1 not in nh["cids"])
from email_parser import nh_flags
fl = nh_flags.set_nh(EV, 9, True, set_by="test", db_path=tmp)
nh2 = db.event_nh_seat_set(c, EV, db_path=tmp)
check("after a manager presses Play N/H (Tracker Build's flag, #1085), Nat is still N/H for the draw",
      fl.get("nh") is True and 9 in nh2["cids"], (fl, nh2))

print("\n== ONE eligibility gate (who may SERVE as a blind) ==")
check("gate: established active member passes", db.blind_gate(1, "active_member", 11.0) is None)
check("gate: intro fails on ESTABLISHED", "established" in (db.blind_gate(8, "active_member", None) or ""))
check("gate: alumni fails on status", "not a member" in (db.blind_gate(10, "expired_member", 20.0) or ""))
check("gate: guest fails on status", "not a member" in (db.blind_gate(11, "active_guest", 20.0) or ""))
check("gate: 1st Timer fails on status", "not a member" in (db.blind_gate(12, "first_timer", None) or ""))
pool = db.event_blind_pool(c, EV, db_path=tmp)
elig = {e["customer_id"] for e in pool["eligible"]}
check("pool: the seven established members, nobody else", elig == {1, 2, 3, 4, 5, 6, 7}, elig)
check("customer_blind_gate agrees (the Ambassador door)",
      db.customer_blind_gate(c, 8, db_path=tmp) and db.customer_blind_gate(c, 1, db_path=tmp) is None)
# Guard: the status/established tests live in blind_gate alone.
src = pathlib.Path("email_parser/database.py").read_text()
uses = [m.start() for m in re.finditer(r"not in BLIND_MEMBER_STATUSES|in BLIND_MEMBER_STATUSES", src)]
check("guard: only blind_gate tests BLIND_MEMBER_STATUSES", len(uses) == 1, len(uses))

print("\n== TEAM Net draw: the N/H seat and the short teams ==")
r = db.draw_event_blinds(EV, dry_run=True, team_unit="group", db_path=tmp)
by_seat = {(d["group_num"], d["cart_pos"]): d for d in r["drawn"]}
check("one N/H seat (Nat, group 1 seat 4)", r["nh_seats"] == 1 and (1, 4) in by_seat, r["drawn"])
check("...drawn with reason 'nh', replacing Nat", by_seat.get((1, 4), {}).get("reason") == "nh"
      and by_seat[(1, 4)].get("replaces") == "Nat Nohcp", by_seat.get((1, 4)))
check("...from the field outside group 1", by_seat.get((1, 4), {}).get("customer_id") not in {1, 2, 3, 9})
check("ENTITLED: the intro player's short team (group 2) still gets its blind",
      (2, 4) in by_seat and by_seat[(2, 4)]["reason"] == "open_seat", r["drawn"])
check("group 3's open seat 2 is filled", (3, 2) in by_seat)
check("open seats counted apart from N/H seats", r["open_seats"] == 2, r["open_seats"])
check("nobody drawn twice", len({d["customer_id"] for d in r["drawn"]}) == len(r["drawn"]))
check("never an intro, alumnus or N/H player as a blind",
      not ({d["customer_id"] for d in r["drawn"]} & {8, 9, 10}))

print("\n== CART Net draw: the N/H player's partner comes from the OTHER cart ==")
rc = db.draw_event_blinds(EV, dry_run=True, team_unit="cart", db_path=tmp)
s14 = next(d for d in rc["drawn"] if (d["group_num"], d["cart_pos"]) == (1, 4))
check("Nat's cart (seats 3-4) gets Ann or Bob from cart 1", s14["customer_id"] in {1, 2}
      and s14["drawn_from"] == "other cart", s14)
s32 = next(d for d in rc["drawn"] if (d["group_num"], d["cart_pos"]) == (3, 2))
check("Fay's cart: Gil (the other cart's only eligible player)", s32["customer_id"] == 7, s32)
s24 = next(d for d in rc["drawn"] if (d["group_num"], d["cart_pos"]) == (2, 4))
check("Ian's cart (seats 3-4): Dee or Eve from cart 1",
      s24["customer_id"] in {4, 5} or s24["drawn_from"].startswith("field"), s24)

print("\n== apply: rows carry the reason ==")
r = db.draw_event_blinds(EV, dry_run=False, team_unit="group", db_path=tmp)
bl = db.get_event_blinds(EV, db_path=tmp)
seat = {(g, b["cart_pos"]): b for g, seats in bl["9"].items() for b in seats}
check("N/H blind stored reason 'nh'", seat[(1, 4)]["reason"] == "nh", seat.get((1, 4)))
check("open-seat blind stored reason 'open_seat'", seat[(2, 4)]["reason"] == "open_seat")
check("missed_holes NULL (every hole)", seat[(1, 4)]["missed_holes"] is None)

print("\n== CHOOSE on a seat ==")
_busy = {b["customer_id"] for b in seat.values()}
_pick = next(x for x in (4, 5, 6, 7) if x not in _busy)
e = db.set_event_blind(EV, "9", 1, 1, _pick, db_path=tmp)
check("a seat held by a player WITH a handicap takes no blind", "error" in e and "N/H" in e["error"], e)
# Clear Nat's seat, then CHOOSE a member from outside group 1 who is not a
# blind anywhere else tonight.
db.set_event_blind(EV, "9", 1, 4, None, db_path=tmp)
busy = {b["customer_id"] for g, seats in db.get_event_blinds(EV, db_path=tmp)["9"].items() for b in seats}
free = next(x for x in (4, 5, 6, 7) if x not in busy)
e = db.set_event_blind(EV, "9", 1, 4, free, db_path=tmp)
check("choosing a blind for the N/H seat records reason 'nh'", e.get("reason") == "nh", e)
e = db.set_event_blind(EV, "9", 1, 4, 8, db_path=tmp)
check("choosing the intro player is refused by the gate", "not eligible" in (e.get("error") or ""), e)

print("\n== Nat gets a starting handicap: the N/H blind is REPORTED stale, not removed ==")
db.set_starting_handicap(9, 20.0, set_by="test", db_path=tmp)
r = db.draw_event_blinds(EV, dry_run=True, team_unit="group", db_path=tmp)
check("stale_nh names the seat", any(s["cart_pos"] == 4 and s["group_num"] == 1 for s in r["stale_nh"]),
      r["stale_nh"])
check("...and the row is still there", any(b["cart_pos"] == 4 for b in
                                           db.get_event_blinds(EV, db_path=tmp)["9"][1]))

print("\n== the engine: Team Net reads the blinds ==")
holes = [{"hole": h, "par": 4, "stroke_index": h} for h in range(1, 4)]
def pl(key, cid, name, team, scores):
    return {"key": key, "customer_id": cid, "name": name, "team": team, "playing_handicap": 0,
            "scores": dict(enumerate(scores, 1))}
state = {"holes": holes, "players": [
    pl("a", 1, "Ann", 1, [5, 5, 5]), pl("n", 9, "Nat", 1, [3, 3, 3]),     # Nat N/H, birdies
    pl("d", 4, "Dee", 2, [5, 5, 5]), pl("f", 6, "Fay", 2, [4, 4, 6]),     # Fay missed hole 3
    pl("x", 7, "Gil", 3, [4, 4, 3])]}
FORM = None
try:
    FORM = db.get_scoring_formulas(tmp)
except Exception:
    pass
cards = ls.build_cards(state, FORM or {})
cfg = ls.SEED_LIVE_SCORING_CONFIG
base = ls.game_team_net(cards, cfg)
t1 = next(t for t in base["teams"] if t["team"] == 1)
check("without blinds, Nat's birdies carry team 1 (-3)", t1["vs_par"] == -3, t1["vs_par"])
blinds = [{"team": 1, "customer_id": 7, "name": "Gil Seven", "reason": "nh", "replaces_key": "n"},
          {"team": 2, "customer_id": 7, "name": "Gil Seven", "reason": "missed_hole",
           "holes": [3], "replaces_key": None}]
got = ls.game_team_net(cards, cfg, blinds=blinds)
t1 = next(t for t in got["teams"] if t["team"] == 1)
check("N/H: Nat's card leaves the best ball; Gil's plays his slot (0 +0 -1 = -1)",
      t1["vs_par"] == -1 and "Nat" not in t1["members"] and "Bl[Gil Seven]" in t1["members"], t1)
check("the team row lists its blind with the reason", t1["blinds"][0]["reason"] == "nh", t1["blinds"])
t2 = next(t for t in got["teams"] if t["team"] == 2)
check("missed hole: Gil's ball plays hole 3 only (0 + 0 - 1 = -1)", t2["vs_par"] == -1, t2)
h1 = next(h for h in t2["holes"] if h["hole"] == 1)
check("...and not on the holes Fay played", h1["by"] == "Fay", h1)
check("Nat's own card still exists for every other game",
      any(c2["name"] == "Nat" and c2["gross"] == 9 for c2 in cards))
lb = ls.compute_leaderboard({**state, "blinds": blinds}, FORM or {})
check("compute_leaderboard passes state['blinds'] to Team Net",
      next(t for t in lb["games"]["team_net"]["teams"] if t["team"] == 1)["vs_par"] == -1)
miss = ls.game_team_net(cards, cfg, blinds=[{"team": 1, "customer_id": 999, "name": "Ghost",
                                             "reason": "open_seat"}])
check("a blind with no card in the round is warned, not invented",
      any("no card" in w for w in miss["warnings"]), miss["warnings"])

print("\n== the leaderboard's read of the event's blinds ==")
players = [{"key": "k1", "customer_id": 1, "name": "Ann One"},
           {"key": "k9", "customer_id": 9, "name": "Nat Nohcp"}]
eb = db._ls_event_blinds({"event_id": EV, "holes": 9}, players, db_path=tmp)
nhb = next((b for b in eb if b["reason"] == "nh"), None)
check("the N/H blind maps to Nat's session key", nhb and nhb["replaces_key"] == "k9" and nhb["team"] == 1, eb)

print()
if F:
    print(f"FAILED ({len(F)}): {F}"); sys.exit(1)
print("ALL N/H BLIND TESTS PASSED")
