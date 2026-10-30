"""THE DEMO RUNNER for Screens (Kerry 2026-10-26: "want updated screens to be
automated to mirror with what's live").

Some member pages need an event, a round or a signed link before they show
anything: score entry, the member tee sheet. They are captured from the
Tracker's OWN code, served by this process from a THROWAWAY database seeded
with made-up people below. Never production data, never a real link.

Run only through email_parser/screens_capture.capture_demos, which starts
this as its own process with DATABASE_PATH set to a temp file and every
credential stripped (no mail, no money, no member can be reached):

    python3 tools/screens_demo.py --repo [<sequence>]        # repo folders
    python3 tools/screens_demo.py --live <root> [<sequence>]  # production screens_live

Prints one JSON line: {"captured": [...], "errors": [...]}.
"""
import io, json, os, sys, threading, contextlib, logging
from datetime import date, timedelta

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.chdir(HERE)

if os.getenv("SCREENS_DEMO") != "1" or not os.getenv("DATABASE_PATH", "").endswith(".db"):
    sys.exit("run through screens_capture.capture_demos (throwaway database only)")
for k in list(os.environ):
    if k.startswith(("AZURE_", "EMAIL_", "ANTHROPIC")):
        del os.environ[k]
os.environ.setdefault("SECRET_KEY", "screens-demo")
logging.disable(logging.CRITICAL)

with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    db.init_db()
    import app as _app
    from email_parser import score_entry as se
    from email_parser import screens_capture as sc

# Made-up people. Obviously not members.
PEOPLE = [(990001, "Sam", "Carter", 8.4), (990002, "Alex", "Rivera", 14.2),
          (990003, "Jordan", "Blake", 5.1), (990004, "Casey", "Morgan", 19.7),
          (990005, "Riley", "Brooks", 11.3), (990006, "Drew", "Hayes", 22.0),
          (990007, "Taylor", "Reed", 3.9), (990008, "Morgan", "Ellis", 16.5)]
NINE = [{"hole": h, "par": p, "stroke_index": si} for h, p, si in
        [(1, 4, 3), (2, 3, 9), (3, 5, 1), (4, 4, 5), (5, 4, 7), (6, 3, 8),
         (7, 4, 2), (8, 4, 6), (9, 5, 4)]]


def seed() -> dict:
    """One demo event today: two foursomes on a 4:30 PM shotgun, a live-scoring
    round, and the first group's signed link."""
    from email_parser.timezone_utils import today_central_str
    today = today_central_str()
    with db._connect() as c:
        # Tables production made long ago, lazily; the board reads them.
        db._ensure_gg_game_results_tables(c)
        db._ensure_gg_game_flights_tables(c)
        c.execute("INSERT INTO events (item_name, event_date, chapter, status, format, start_type, start_time, "
                  "course) VALUES ('s9.99 Demo Links', ?, 'San Antonio', 'active', '9-hole', 'Shotgun', '16:30', "
                  "'Demo Golf Club')", (today,))
        eid = c.execute("SELECT id FROM events WHERE item_name = 's9.99 Demo Links'").fetchone()[0]
        for i, (cid, fn, ln, _) in enumerate(PEOPLE):
            c.execute("INSERT OR IGNORE INTO customers (customer_id, first_name, last_name, current_player_status, "
                      "chapter) VALUES (?, ?, ?, 'active_member', 'San Antonio')", (cid, fn, ln))
            c.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, tee_choice, side_games, "
                      "transaction_status, order_date, order_id, email_uid, merchant) VALUES (?, ?, 's9.99 Demo Links', "
                      "?, '9', '50-64', 'NET', 'active', ?, ?, ?, 'GoDaddy')",
                      (f"{fn} {ln}", cid, eid, today, f"RDEMO{i}", f"manual-demo-{i}"))
        c.commit()
    groups = []
    for g in range(2):
        groups.append({"group_num": g + 1, "slot_label": f"{g + 1}A", "players": [
            {"name": f"{fn} {ln}", "customer_id": cid, "cart_pos": j + 1, "tee_choice": "50-64",
             "handicap_index": hi} for j, (cid, fn, ln, hi) in enumerate(PEOPLE[g * 4:(g + 1) * 4])]})
    db.save_event_pairings(eid, {"9": groups})
    db.set_app_setting("score_entry_live", "1")
    # The demo shows scoring as it is during play, whatever the clock says:
    # the scoring window would otherwise put "SCORING OPENS" on the landing.
    db.set_app_setting("scoring_window_auto", "off")
    db.set_app_setting(se.EVENTS_SETTING, json.dumps([eid]))
    rid = se.create_round(eid, 9, round_date=today, label="s9.99", course_holes=NINE)["round_id"]
    gids = []
    for g in range(2):
        r = se.upsert_group(rid, g + 1, label=f"Hole {g + 1}", start_hole=g + 1, players=[
            {"customer_id": cid, "display_name": f"{fn} {ln}", "playing_handicap": round(hi * 0.4), "seat": j + 1}
            for j, (cid, fn, ln, hi) in enumerate(PEOPLE[g * 4:(g + 1) * 4])])
        gids.append(r["group_id"])
    return {"event": eid, "t": se.make_group_token(gids[0]), "t2": se.make_group_token(gids[1])}


def main():
    args = sys.argv[1:]
    live_root = args[args.index("--live") + 1] if "--live" in args else None
    only = next((a for a in args if not a.startswith("--") and a != live_root), "")
    v = seed()
    from werkzeug.serving import make_server
    srv = make_server("127.0.0.1", 0, _app.app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    cat_dir = os.path.join(HERE, "docs/claude/screenshots")
    out_for = ((lambda s: os.path.join(live_root, s["id"])) if live_root
               else (lambda s: os.path.join(cat_dir, s["folder"])))
    try:
        res = sc.capture_all(out_for, base, only=only, demo={"base": base, "vars": v})
    finally:
        srv.shutdown()
    print(json.dumps({"captured": res.get("captured") or [], "errors": res.get("errors") or []}))


if __name__ == "__main__":
    main()
