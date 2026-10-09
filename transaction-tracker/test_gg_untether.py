"""UNTETHERED FROM GOLF GENIUS (Kerry 2026-10-08: "Golf Genius is not the
ruler on this or from now on. We need to untether for this event and all
future events unless I say."). Events dated on/after gg_untether_from
(default 2026-10-07) get nothing from Golf Genius; events before it keep
their walks (last Tuesday's points still post).

Run: python3 test_gg_untether.py
"""
import os, sys, json, tempfile, contextlib, io, logging, sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-untether-"), "t.db")
os.environ["DATABASE_PATH"] = tmp
logging.disable(logging.ERROR)
from email_parser import database as db                          # noqa: E402
from email_parser import gg_untether as gu                       # noqa: E402
from email_parser.timezone_utils import today_central_str       # noqa: E402
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
F = []


def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c:
        F.append(l)


print("the rule")
check("default date is 2026-10-07", gu.untether_from(tmp) == "2026-10-07")
check("Tue 10/6 is Golf Genius's (last Tuesday's points)", gu.gg_allowed("2026-10-06", tmp))
check("the Cup weekend is not", not gu.gg_allowed("2026-10-10", tmp) and not gu.gg_allowed("2026-10-09", tmp))
check("future Tuesdays are not", not gu.gg_allowed("2026-10-13", tmp))
check("an undated event is not", not gu.gg_allowed(None, tmp))
check("September money is GG's, October's is not", gu.gg_allowed_month("2026-09", tmp) and not gu.gg_allowed_month("2026-10", tmp))
db.set_app_setting("gg_untether_from", "2026-10-14", db_path=tmp)
check("the date moves only through the setting", gu.gg_allowed("2026-10-13", tmp))
db.set_app_setting("gg_untether_from", "", db_path=tmp)

TODAY = today_central_str()
c = sqlite3.connect(tmp)
for eid, name, d, ch in ((501, "s10.6 Past Tuesday", "2026-10-06", "San Antonio"),
                         (502, "s10.13 Next Tuesday", "2026-10-13", "San Antonio"),
                         (503, "s10.6 Last Year", "2025-10-06", "San Antonio"),
                         (504, f"s{int(TODAY[5:7])}.{int(TODAY[8:])} Today", TODAY, "San Antonio")):
    c.execute("INSERT INTO events (id, item_name, event_date, chapter, format) VALUES (?,?,?,?,?)",
              (eid, name, d, ch, "9 Holes"))
for i, (who, ev) in enumerate((("Ann", "s10.13 Next Tuesday"), ("Bob", "s10.6 Past Tuesday"))):
    c.execute("INSERT INTO rsvps (email_uid, player_name, player_email, response, received_at, matched_event) "
              "VALUES (?,?,?,?,?,?)", (f"u{i}", who, f"{who.lower()}@x.com", "PLAYING", "2026-10-01 10:00:00", ev))
c.commit()

print("Golf Genius walks drop untethered codes")
conn = sqlite3.connect(tmp)
codes = db._gg_untethered_codes(conn, tmp)
check("s10.13 dropped (and with it any fallback to last year)", "s10.13" in codes)
check("s10.6 kept for last Tuesday", "s10.6" not in codes)
conn.close()

print("live poll")
res = db.poll_live_events(db_path=tmp)
st = next((x for x in res["checked"] if x["event_id"] == 504), {})
check("today's coded event is not polled from Golf Genius", "untethered" in (st.get("skipped") or ""), st)

print("automatic payouts")
pay = db.record_all_event_game_payouts(db_path=tmp, time_budget=20)
skipped = {x.get("event") for x in pay["skipped"] if isinstance(x, dict) and "untethered" in (x.get("why") or "")}
check("today's event is left to the Tracker", any("Today" in (n or "") for n in skipped), pay["skipped"])

print("Golf Genius RSVPs: still ON (Kerry 10/8: \"Still using actively\")")
check("by default an upcoming event keeps its GG RSVPs",
      len(db.get_rsvps_for_event("s10.13 Next Tuesday", db_path=tmp)) == 1)
conn = sqlite3.connect(tmp); conn.row_factory = sqlite3.Row
check("...and they still join its roster", len(db._event_rsvp_only_players(conn, 502)) == 1)
conn.close()
db.set_app_setting("gg_rsvps_off", "1", db_path=tmp)
print("Golf Genius RSVPs switched off (gg_rsvps_off = 1)")
check("no GG RSVPs on an untethered event", db.get_rsvps_for_event("s10.13 Next Tuesday", db_path=tmp) == [])
check("past event keeps its GG RSVPs", len(db.get_rsvps_for_event("s10.6 Past Tuesday", db_path=tmp)) == 1)
bulk = db.get_all_rsvps_bulk(db_path=tmp)
check("bulk read leaves out the untethered event", "s10.13 Next Tuesday" not in bulk["rsvps"]
      and "s10.6 Past Tuesday" in bulk["rsvps"], list(bulk["rsvps"]))
conn = sqlite3.connect(tmp); conn.row_factory = sqlite3.Row
check("no GG RSVP joins an untethered roster", db._event_rsvp_only_players(conn, 502) == [])
conn.close()
c = sqlite3.connect(tmp)
check("nothing was deleted (reversible)", c.execute("SELECT COUNT(*) FROM rsvps").fetchone()[0] == 2)
c.close()

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILED: {F}"))
sys.exit(1 if F else 0)
