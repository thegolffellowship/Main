"""Winnings by Game on the Player Spotlight (Kerry ratified 2026-09-11).

Option A: bundle-first rows (NET / GROSS / Included / Season Contests)
that expand to per-game rows, scoped by a page-level SEASON-per-year |
ALL-TIME toggle. Bundle membership is rules-as-data (app_settings
`spotlight_winnings_bundles`, seeded by SEED_WINNINGS_BUNDLES).

Covers the pure aggregation `_winnings_by_game`:
  - production category spellings map to the ratified bundles
    (rows use `ctp`; label maps also carry `closest_to_pin` — both
    must land in Included, merged as ONE game row);
  - an unknown category lands in the catch_all bundle, never vanishes;
  - per-year scoping + all_time, years discovered from the data;
  - every bundle renders even at $0 (Kerry: a zero GROSS row
    advertises the games you're not in);
  - buy-in counters resolve per scope;
  - bundle totals sum exactly to the payout total (page self-audits
    against the Won tile).

Run: python3 test_spotlight_winnings.py
"""

import os

os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


PAYOUTS = [
    # 2026 event games — production spellings + real description shapes
    # from the 2026-09-11 audit (s9.22, s18.10)
    {"category": "team_net", "amount": 12.0, "event_date": "2026-09-08",
     "event_name": "s9.22 Silverhorn",
     "description": "TEAM Net 1st (T) (team split)"},
    # two CTP spellings, SAME event — one game row, bits accumulate
    {"category": "ctp", "amount": 24.0, "event_date": "2026-09-08",
     "event_name": "s9.22 Silverhorn",
     "description": "CTP Closest to Pin #13"},
    {"category": "closest_to_pin", "amount": 19.0,
     "event_date": "2026-09-08", "event_name": "s9.22 Silverhorn",
     "description": "CTP Closest to Pin #16"},
    {"category": "skins", "amount": 39.0, "event_date": "2026-09-08",
     "event_name": "s9.22 Silverhorn",
     "description": "Skins Par on 17 (GG $)"},
    {"category": "skins", "amount": 15.6, "event_date": "2026-08-29",
     "event_name": "s18.10 FALL KICKOFF | Landa Park",
     "description": "Skins HIGH Flight ×2 holes 2, 18"},
    {"category": "individual_net", "amount": 67.5,
     "event_date": "2026-09-08", "event_name": "s9.22 Silverhorn",
     "description": "Ind Net LOW Flight 1st (T) (GG $)"},
    {"category": "individual_gross", "amount": 36.0,
     "event_date": "2026-08-29",
     "event_name": "s18.10 FALL KICKOFF | Landa Park",
     "description": "Ind Gross FLIGHT 3 | HDCP 12+ 1st (GG $)"},
    {"category": "mvp", "amount": 30.0, "event_date": "2026-09-08",
     "event_name": "s9.22 Silverhorn", "description": "City MVP"},
    {"category": "tgf_mvp", "amount": 50.0, "event_date": "2026-09-08",
     "event_name": "s9.22 Silverhorn",
     "description": "TGF MVP (combined same-day pot)"},
    # season rows store display-string categories
    {"category": "City Net", "amount": 200.0, "event_date": "2026-08-01",
     "event_name": "SAN ANTONIO Net 2026",
     "description": "SAN ANTONIO Net 2026 final standings — 2 place"},
    {"category": "Match Play", "amount": 100.0, "event_date": "2026-08-01",
     "event_name": "SAN ANTONIO MATCH PLAY 2026"},
    {"category": "monthly_points", "amount": 70.0,
     "event_date": "2026-06-30", "event_name": "JUNE Points 2026"},
    # a category nobody declared — must land in the catch_all bundle
    {"category": "mystery_game", "amount": 5.0, "event_date": "2026-05-01"},
    # a prior-year row (synthetic) — drives the per-year scoping
    {"category": "skins", "amount": 10.0, "event_date": "2025-06-01"},
]

BUYINS = {
    "all_time": {"net": 9, "gross": 7, "events": 15, "contests": 3},
    "years": {"2026": {"net": 8, "gross": 6, "events": 14, "contests": 3},
              "2025": {"net": 1, "gross": 1, "events": 1, "contests": 0}},
}

out = db._winnings_by_game(PAYOUTS, db.SEED_WINNINGS_BUNDLES, 2026, BUYINS)

check("years discovered from data, newest first",
      out["years"] == ["2026", "2025"], repr(out["years"]))
check("current_year rides along", out["current_year"] == 2026)

y26 = {b["key"]: b for b in out["by_year"]["2026"]}
y25 = {b["key"]: b for b in out["by_year"]["2025"]}
allt = {b["key"]: b for b in out["all_time"]}

check("all four bundles present even when empty",
      set(y25) == {"net", "gross", "included", "season"}, repr(set(y25)))
check("2025 NET bundle shows $0 (zero rows still render)",
      y25["net"]["total"] == 0 and y25["net"]["games"] == [])

check("NET 2026 = Ind Net + City MVP + TGF MVP",
      y26["net"]["total"] == 147.5, y26["net"]["total"])
check("GROSS 2026 = Skins + Ind Gross",
      y26["gross"]["total"] == 90.6, y26["gross"]["total"])
inc = y26["included"]
check("Included 2026 = Team Net + both CTP spellings",
      inc["total"] == 55.0, inc["total"])
ctp_rows = [g for g in inc["games"] if g["label"] == "Closest to Pin"]
check("ctp + closest_to_pin merge into ONE game row",
      len(ctp_rows) == 1 and ctp_rows[0]["count"] == 2
      and ctp_rows[0]["total"] == 43.0,
      repr(inc["games"]))
sea = y26["season"]
check("Season Contests 2026 collects display-string categories",
      sea["total"] == 375.0, sea["total"])
check("unknown category lands in catch_all, not dropped",
      any(g["category"] == "mystery_game" for g in sea["games"]),
      repr([g["category"] for g in sea["games"]]))
check("City Net shows its member-facing label",
      any(g["label"] == "City Points Race" for g in sea["games"]))

check("2025 skins scoped to 2025",
      y25["gross"]["total"] == 10.0 and allt["gross"]["total"] == 100.6,
      (y25["gross"]["total"], allt["gross"]["total"]))

total_payouts = round(sum(p["amount"] for p in PAYOUTS), 2)
check("all_time bundle totals sum exactly to the payout total",
      round(sum(b["total"] for b in out["all_time"]), 2) == total_payouts,
      (round(sum(b["total"] for b in out["all_time"]), 2), total_payouts))
per_year_sum = round(sum(b["total"] for y in out["years"]
                         for b in out["by_year"][y]), 2)
check("per-year totals partition the all-time total",
      per_year_sum == total_payouts, (per_year_sum, total_payouts))

check("buy-ins resolve per scope (2026 NET)",
      y26["net"]["buyins"] == 8, y26["net"]["buyins"])
check("buy-ins resolve per scope (all-time events)",
      allt["included"]["buyins"] == 15, allt["included"]["buyins"])
check("buyin noun rides on the bundle",
      y26["included"]["buyin_noun"] == "event")

# games sorted biggest first inside a bundle
g_order = [g["total"] for g in y26["net"]["games"]]
check("games sorted by total desc", g_order == sorted(g_order, reverse=True),
      g_order)

# no buy-in counts supplied -> buyins stays None (payload shows nothing)
out2 = db._winnings_by_game(PAYOUTS, db.SEED_WINNINGS_BUNDLES, 2026, None)
check("missing buy-in counts degrade to None, not 0",
      all(b["buyins"] is None for b in out2["all_time"]))

# empty payouts: current year still present so the toggle renders
out3 = db._winnings_by_game([], db.SEED_WINNINGS_BUNDLES, 2026, None)
check("no payouts still yields the current season at $0",
      out3["years"] == ["2026"]
      and all(b["total"] == 0 for b in out3["by_year"]["2026"]))

# ── per-event drill-down (Kerry 2026-09-11 follow-up): each game row
#    carries the events it was won in, with flight/place + amount ──
ctp_g = ctp_rows[0]
check("CTP: two rows in one event fold to ONE event line",
      len(ctp_g["events"]) == 1 and ctp_g["events"][0]["total"] == 43.0,
      repr(ctp_g["events"]))
check("CTP event line accumulates both holes",
      ctp_g["events"][0]["detail"] == "Hole 13 · Hole 16",
      repr(ctp_g["events"][0]["detail"]))
ind_net = next(g for g in y26["net"]["games"] if g["label"] == "Individual Net")
check("Ind Net event carries tied place + flight",
      ind_net["events"][0]["detail"] == "T1st Place · Low Flight",
      repr(ind_net["events"][0]["detail"]))
ind_gr = next(g for g in y26["gross"]["games"]
              if g["label"] == "Individual Gross")
check("Ind Gross event carries place + numeric flight",
      ind_gr["events"][0]["detail"] == "1st Place · Flight 3",
      repr(ind_gr["events"][0]["detail"]))
sk = next(g for g in y26["gross"]["games"] if g["label"] == "Skins")
check("Skins events sorted newest first",
      [e["event_date"] for e in sk["events"]] == ["2026-09-08", "2026-08-29"],
      repr([e["event_date"] for e in sk["events"]]))
check("Skins flighted event carries holes + flight",
      sk["events"][1]["detail"] == "Holes 2 & 18 · High Flight",
      repr(sk["events"][1]["detail"]))
cn = next(g for g in sea["games"] if g["label"] == "City Points Race")
check("Season standings row carries the standings place",
      cn["events"][0]["detail"] == "2nd Place | Season Standings",
      repr(cn["events"][0]["detail"]))
check("event names ride on the drill-down lines",
      sk["events"][0]["event_name"] == "s9.22 Silverhorn")
check("a row with no description still yields an event line",
      next(g for g in sea["games"] if g["category"] == "mystery_game")
      ["events"][0]["detail"] == "")

# ── ordinal-flight descriptions (Kerry 2026-09-11: Jeff Young's
#    "Players Cup — 1st Flight 2nd place" rendered as 1st Place ·
#    Flight 2 — the flight ordinal comes FIRST in cup rows) ──
BITS = db._payout_detail_bits
check("cup: '1st Flight 2nd place' = 2nd place IN flight 1",
      BITS("Players Cup", "Players Cup — 1st Flight 2nd place")
      == ["2nd Place", "Flight 1"],
      repr(BITS("Players Cup", "Players Cup — 1st Flight 2nd place")))
check("cup: '2nd Flight winner' = 1st place in flight 2",
      BITS("Players Cup", "Players Cup — 2nd Flight winner")
      == ["1st Place", "Flight 2"],
      repr(BITS("Players Cup", "Players Cup — 2nd Flight winner")))
check("cup: champion row keeps the Champion bit",
      BITS("Players Cup", "Players Cup — Champion & 1st Flight winner")
      == ["Champion", "1st Place", "Flight 1"],
      repr(BITS("Players Cup", "Players Cup — Champion & 1st Flight winner")))
check("championship-close: '4th Flight 2nd' (no 'place') parses too",
      BITS("individual_gross", "Combined Ind Gross 4th Flight 2nd")
      == ["2nd Place", "Flight 4"],
      repr(BITS("individual_gross", "Combined Ind Gross 4th Flight 2nd")))
check("generic 'FLIGHT 3' descriptions untouched by the ordinal branch",
      BITS("individual_gross", "Ind Gross FLIGHT 3 | HDCP 12+ 1st (GG $)")
      == ["1st Place", "Flight 3"],
      repr(BITS("individual_gross", "Ind Gross FLIGHT 3 | HDCP 12+ 1st (GG $)")))

# ── concluded races LOCK to recorded payouts (Kerry ruling 2026-09-11:
#    "freeze concluded races to recorded payouts... it should lock") ──
import sqlite3
import tempfile

with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as _tf:
    _dbp = _tf.name
_c = sqlite3.connect(_dbp)
_c.executescript("""
CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE tgf_events (id INTEGER PRIMARY KEY, code TEXT, name TEXT);
CREATE TABLE tgf_payouts (id INTEGER PRIMARY KEY, event_id INT,
  customer_id INT, category TEXT, amount REAL, description TEXT);
INSERT INTO tgf_events VALUES (1, '2026 PLAYERS CUP', '2026 PLAYERS CUP'),
                              (2, 'SAN ANTONIO Net 2026', 'SAN ANTONIO Net 2026');
INSERT INTO tgf_payouts VALUES
 (1,1,31,'Players Cup',230.69,'auto: Players Cup — Champion & 1st Flight winner'),
 (2,1,88,'Players Cup', 68.31,'auto: Players Cup — 1st Flight 2nd place'),
 (3,1,39,'Players Cup',138.69,'auto: Players Cup — 2nd Flight winner'),
 (4,1,37,'Players Cup', 68.31,'auto: Players Cup — 2nd Flight 2nd place'),
 (5,1,35,'Players Cup',138.69,'auto: Players Cup — 3rd Flight winner'),
 (6,1,23,'Players Cup', 68.31,'auto: Players Cup — 3rd Flight 2nd place'),
 (7,1, 1,'Players Cup',138.69,'auto: Players Cup — 4th Flight winner'),
 (8,1, 6,'Players Cup', 68.31,'auto: Players Cup — 4th Flight 2nd place'),
 (9,2,18,'City Net',400.0,'SAN ANTONIO Net 2026 final standings — 1 place'),
 (10,2,24,'City Net',300.0,'SAN ANTONIO Net 2026 final standings — 2 place'),
 (11,2,82,'City Net',220.0,'SAN ANTONIO Net 2026 final standings — 3 place');
""")
_c.commit(); _c.close()

pc = db._recorded_payout_strip(
    "players_cup_gross", {"label": "THE PLAYERS CUP 2026",
                          "flights": (("1st Flight", None, 6.0),)}, _dbp)
check("locked cup strip built from recorded rows",
      pc is not None and pc["locked"] and pc["kind"] == "flights", repr(pc))
check("locked cup: pot/champion/first/second from what was PAID",
      (pc["pot_cents"], pc["champion_cents"], pc["flight_first_cents"],
       pc["flight_second_cents"]) == (92000, 9200, 13869, 6831),
      repr(pc))
check("locked cup: n_basis is the pool's real entry count",
      pc["n_basis"] == 23, pc["n_basis"])
check("locked cup: recorded recipients ride along (8 customers)",
      len(pc["recorded_rows"]) == 8
      and {"customer_id": 88, "amount_cents": 6831} in pc["recorded_rows"])

cn = db._recorded_payout_strip(
    "san_antonio_net", {"label": "SAN ANTONIO Net 2026"}, _dbp)
check("locked city strip is a ladder of recorded amounts",
      cn["kind"] == "ladder" and cn["amounts_cents"] == [40000, 30000, 22000]
      and cn["pot_cents"] == 92000, repr(cn))
check("race with no recorded payouts returns None (strip recomputes)",
      db._recorded_payout_strip("austin_net",
                                {"label": "AUSTIN Net 2026"}, _dbp) is None)
os.unlink(_dbp)

# ── EVENTS LEADERBOARD (Kerry 2026-09-11, admin pilot): flight-
#    sectioned boards; non-buyers PLACED into the flight their handicap
#    would have flighted them; buyers highlighted; skins buyers-only ──
with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as _tf2:
    _db2 = _tf2.name
_c = sqlite3.connect(_db2)
_c.executescript("""
CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT, event_date TEXT,
  course TEXT, chapter TEXT, format TEXT);
CREATE TABLE event_aliases (alias_name TEXT, canonical_event_name TEXT);
CREATE TABLE items (id INTEGER PRIMARY KEY, item_name TEXT, customer_id INT,
  customer TEXT, parent_item_id INT, side_games TEXT, transaction_status TEXT,
  wd_credits TEXT, event_id INT);
CREATE TABLE tgf_events (id INTEGER PRIMARY KEY, code TEXT, name TEXT);
CREATE TABLE tgf_payouts (id INTEGER PRIMARY KEY, event_id INT, customer_id INT,
  category TEXT, amount REAL, description TEXT);
INSERT INTO events VALUES (50, 's9.99 Testhorn', '2026-09-08', 'Testhorn', 'San Antonio', '9-hole');
-- NET buyers: cid 1 (hcp 5, Flight 1), cid 2 (hcp 20, Flight 2);
-- cid 3 non-buyer hcp 14 -> placed Flight 2; guest (no cid) hcp NULL -> UNFLIGHTED
INSERT INTO items VALUES
 (1,'s9.99 Testhorn',1,'Low Buyer',NULL,'NET','active',NULL,50),
 (2,'s9.99 Testhorn',2,'High Buyer',NULL,'BOTH','active',NULL,50),
 (3,'s9.99 Testhorn',3,'Mid Nonbuyer',NULL,'NONE','active',NULL,50);
INSERT INTO tgf_events VALUES (9, 's9.99 Testhorn', 's9.99 Testhorn');
INSERT INTO tgf_payouts VALUES
 (1,9,1,'individual_net',63.0,'auto: Ind Net Flight 1 (HCP <12.0) 1st (GG $)'),
 (2,9,2,'skins',19.5,'auto: Skins Par on 4 (GG $)'),
 (3,9,1,'mvp',30.0,'auto: City MVP');
""")
_c.close()
with db._connect(_db2) as _cn:
    db._ensure_scoring_tables(_cn)
    db._ensure_gg_game_results_tables(_cn)
    db._ensure_gg_game_flights_tables(_cn)
    _cn.executescript("""
CREATE TABLE IF NOT EXISTS event_pairings (id INTEGER PRIMARY KEY, event_id INT,
  holes TEXT, group_num INT, slot_label TEXT, player_name TEXT, cart_pos INT);
INSERT INTO event_pairings (event_id, holes, group_num, slot_label, player_name, cart_pos) VALUES
 (50,'9',1,'A','Low Buyer',1),(50,'9',1,'B','High Buyer',2),
 (50,'9',2,'A','Mid Nonbuyer',1),(50,'9',2,'B','Someone Guest',2);
INSERT INTO course_tee_holes (tee_id, hole_number, par) VALUES (7,10,4),(7,11,4);
INSERT INTO scoring_rounds (id, customer_id, player_name, event_id, playing_handicap, gross, net, tee_id)
VALUES (101, 1, 'BUYER, Low', 50, 5, 40, 35, 7),
       (102, 2, 'BUYER, High', 50, 20, 55, 35, 7),
       (103, 3, 'NONBUYER, Mid', 50, 14, 50, 36, 7),
       (104, NULL, 'GUEST, Someone', 50, NULL, 48, NULL, 7);
-- two holes of data: hole 10 (Low 4, High 6-1dot, Mid 5, Guest 5),
-- hole 11 (Low 5, High 5-1dot, Mid 4, Guest 6)
INSERT INTO scoring_holes (scoring_round_id, hole_number, strokes, strokes_received) VALUES
 (101,10,4,0),(101,11,5,0),(102,10,6,1),(102,11,5,1),
 (103,10,5,0),(103,11,4,0),(104,10,5,0),(104,11,6,0),
 (101,12,NULL,0);  -- GG's empty row for an unplayed hole: must NOT become a column
INSERT INTO gg_game_flights (event_id, gg_tournament_id, game, flight_label, customer_id, player_name)
VALUES (50, 't1', 'individual_net', 'Flight 1 (HCP <12.0)', 1, 'BUYER, Low'),
       (50, 't2', 'individual_net', 'Flight 2 (HCP 12.0+)', 2, 'BUYER, High'),
       (50, 't3', 'skins', 'ALL', 2, 'BUYER, High');
INSERT INTO gg_game_results (event_id, gg_tournament_id, game, game_label, player_name, is_team, position, detail, purse)
VALUES (50, 't4', 'team_net', 'TEAM Net $', 'BUYER, Low + BUYER, High TGF San Antonio', 1, 'T1', 'total:7', 128),
       (50, 't4', 'team_net_board', 'TEAM Net $', 'NONBUYER, Mid + GUEST, Someone TGF San Antonio', 1, '2', 'total:9', 0),
       (50, 't5', 'ctp', 'CTP', 'BUYER, Low', 0, '1', '#7', 26);
""")
    _cn.commit()

evd = db.get_event_leaderboard("s9.99 Testhorn", db_path=_db2)
check("event leaderboard assembles", evd is not None and evd["field"] == 4)
_nb = evd["net_board"]
check("net board flight-sectioned, low flight first",
      [s["label"] for s in _nb][:2] == ["Flight 1 (HCP <12.0)",
                                        "Flight 2 (HCP 12.0+)"],
      repr([s["label"] for s in _nb]))
f2 = next(s for s in _nb if s["label"] == "Flight 2 (HCP 12.0+)")
placed = [r for r in f2["rows"] if r.get("assigned")]
check("non-buyer hcp 14 PLACED into Flight 2",
      any(r["customer_id"] == 3 for r in placed), repr(f2["rows"]))
check("guest with no handicap lands in UNFLIGHTED",
      _nb[-1]["label"] == "UNFLIGHTED"
      and _nb[-1]["rows"][0]["player_name"] == "GUEST, Someone")
f1 = next(s for s in _nb if s["label"] == "Flight 1 (HCP <12.0)")
w = next(r for r in f1["rows"] if r["customer_id"] == 1)
check("net board: buyer flagged + Ind Net money badged (MVP kept for Points)",
      w["buyer"] and [x["category"] for x in w["won"]] == ["individual_net"],
      repr(w["won"]))
sk = evd["skins_board"]
check("skins board: whole field, winners among buyers, non-buyers present",
      any(r["buyer"] and any(x["category"] == "skins" for x in r["won"])
          for s in sk for r in s["rows"])
      and any(not r["buyer"] for s in sk for r in s["rows"]),
      repr(sk))
for _s in sk:
    _order = [r["buyer"] for r in _s["rows"]]
    check(f"skins section keeps buyers ABOVE placed non-buyers ({_s['label']})",
          _order == sorted(_order, reverse=True), repr(_order))
pb = evd["points_board"]
check("points board carries MVP money on the winner's row",
      any(r["customer_id"] == 1 and
          any(x["category"] == "mvp" for x in r["won"]) for r in pb))
# MVP tiebreak (Kerry: chain is Net → Gross → split; points stay tied):
# cids 1+2 tie on net pts AND net stroke (35) — gross 40 vs 55 decides
check("tied top group orders by the MVP chain (gross decides)",
      pb[0]["customer_id"] == 1 and pb[1]["customer_id"] == 2,
      repr([(r["customer_id"], r["net_pts"]) for r in pb[:3]]))
check("MVP winner notes the deciding tiebreaker",
      pb[0].get("mvp_note") == "MVP tiebreak 2 — low Gross (40)",
      repr(pb[0].get("mvp_note")))
check("tied loser carries their chain values",
      "Net 35" in (pb[1].get("mvp_note") or "")
      and "Gross 55" in (pb[1].get("mvp_note") or ""),
      repr(pb[1].get("mvp_note")))
check("team + proxies ride on their own boards",
      evd["team_board"][0]["team"].startswith("BUYER, Low + BUYER, High")
      and evd["proxies"][0]["detail"] == "#7")
check("team_board carries GG posted totals (winner + board rows)",
      sorted(t["gg_total"] for t in evd["team_board"]) == [7, 9],
      repr(evd["team_board"]))
# ── iteration 2 (Kerry 2026-09-11 feedback): all teams w/ best-ball
#    totals, skins grid winners, index columns, inactive-game notice ──
tm = evd["teams"]
check("all teams built from the pairing groups (2 teams)",
      len(tm) == 2, repr([(t["team_num"], t["total_net"]) for t in tm]))
t1 = next(t for t in tm if t["team_num"] == 1)
# team 1 best ball: hole 10 min(4, 6-1=5)=4; hole 11 min(5, 5-1=4)=4 → 8
check("team best-ball net total (dots applied)",
      t1["total_net"] == 8, t1["total_net"])
t2 = next(t for t in tm if t["team_num"] == 2)
# GG's board rows (winner T1 + team_net_board 2) rank the board and
# carry the posted totals — the score of record (v2.381.0)
check("teams ranked by GG's recorded positions",
      t1["position"] == "T1" and t2["position"] == "2",
      (t1["position"], t2["position"]))
check("both teams official (full board recorded)",
      t1["official"] and t2["official"])
check("GG posted totals thread through (winner via detail, board row too)",
      t1["gg_total"] == 7 and t2["gg_total"] == 9,
      (t1["gg_total"], t2["gg_total"]))
check("winner purse survives the board-row match (never clobbered to None)",
      t1["purse"] == 128 and t2["purse"] is None,
      (t1["purse"], t2["purse"]))
# the raw parser: winners_only=False returns the whole standings with
# totals parsed from GG's "TotalNet" column ("30 (-/30)")
_gg_tbl = [["Pos.", "Foursome", "To ParNet", "TotalNet", "Purse"],
           ["T1", "X, A + Y, B TGF San Antonio", "-6", "30 (-/30)", "$48.00"],
           [""],
           ["3", "Z, C + W, D TGF San Antonio", "-4", "32 (-/32)", "$0.00"]]
_win = db._game_winners_from_table(_gg_tbl)
check("board parser: winners-only keeps the paid row w/ total",
      len(_win) == 1 and _win[0]["total"] == 30 and _win[0]["is_team"] == 1,
      repr(_win))
_all = db._game_winners_from_table(_gg_tbl, winners_only=False)
check("board parser: winners_only=False returns the full standings",
      [(r["position"], r["total"], r["purse"]) for r in _all]
      == [("T1", 30, 48.0), ("3", 32, 0.0)], repr(_all))
# skins (GROSS buyers only = cid 2): winner of both holes unopposed
check("skin cells mark the buyer's winning holes",
      evd["skin_cells"].get("102") == [10, 11], repr(evd["skin_cells"]))
check("everyone NOT in skins is placed on the board (grey rows)",
      {r["player_name"] for s in sk for r in s["rows"] if not r["buyer"]}
      == {"BUYER, Low", "NONBUYER, Mid", "GUEST, Someone"})
check("cards + hole_cols feed the grids",
      evd["hole_cols"] == [10, 11] and "101" in evd["cards"])
check("Individual Gross inactive notice from the live matrix (16 on 9h)",
      evd["games_off"] and evd["games_off"][0]["needed"] == 16
      and "rolled into Skins" in evd["games_off"][0]["note"],
      repr(evd["games_off"]))
# ── OVERALL view (Kerry 2026-09-11): whole field, one table, win flags
#    by category, Won = ALL event money, NO buy-in identification ──
ovr = evd["overall_board"]
check("overall board carries the whole field", len(ovr) == 4, len(ovr))
check("overall sorted by net (no-net guests last)",
      [r["player_name"] for r in ovr][:2] == ["BUYER, Low", "BUYER, High"]
      and ovr[-1]["player_name"] == "GUEST, Someone",
      repr([r["player_name"] for r in ovr]))
o1 = next(r for r in ovr if r["customer_id"] == 1)
o2 = next(r for r in ovr if r["customer_id"] == 2)
check("win flags: cid1 won Ind Net + MVP, not skins/gross",
      o1["win_net"] and o1["win_mvp"] and not o1["win_skins"]
      and not o1["win_gross"], repr(o1))
check("win flags: cid2 won skins only", o2["win_skins"]
      and not o2["win_net"] and not o2["win_mvp"], repr(o2))
check("Won column = total event money across ALL categories",
      o1["won_total"] == 93.0 and o2["won_total"] == 19.5,
      (o1["won_total"], o2["won_total"]))
check("overall rows do NOT identify buy-ins",
      all("buyer" not in r and "won" not in r for r in ovr),
      repr(sorted(ovr[0].keys())))
check("overall rows carry hcp/pts for the table (index None w/o links)",
      "index" in o1 and o1["hcp"] == 5
      and o1["net_pts"] is not None, repr(o1))
# flight ordinals for the per-flight win colors (Kerry 2026-09-11):
# 1 = low flight in board order — cid1 sits in Flight 1 (HCP <12.0),
# cid2 in Flight 2; the skins board has one labeled section (ALL) so
# every placed player is ordinal 1
check("flight ordinals ride on overall rows (net 1/2, skins 1)",
      o1["net_flight"] == 1 and o2["net_flight"] == 2
      and o2["skins_flight"] == 1,
      (o1["net_flight"], o2["net_flight"], o2["skins_flight"]))

lst = db.get_events_leaderboard(db_path=_db2)
check("pilot dial gates the event list (s9.99 not in seed)",
      lst["pilot"] and all(not e["item_name"].startswith("s9.99")
                           for e in lst["events"]))
with db._connect(_db2) as _cn:
    _cn.execute("INSERT INTO app_settings VALUES ('events_leaderboard_events', '[\"s9.99\"]')")
    _cn.commit()
lst2 = db.get_events_leaderboard(db_path=_db2)
check("dial change admits the event, pot from payouts",
      len(lst2["events"]) == 1 and lst2["events"][0]["pot"] == 112.5,
      repr(lst2["events"]))
os.unlink(_db2)

# dial fallback: malformed JSON must fall back to the seed, not blank
check("seed bundles well-formed",
      db.get_winnings_bundles.__doc__ is not None
      and all(b.get("key") and isinstance(b.get("categories"), list)
              for b in db.SEED_WINNINGS_BUNDLES))

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
    raise SystemExit(1)
print("ALL PASS")
