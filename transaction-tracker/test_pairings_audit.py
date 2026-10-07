"""PAIRINGS AUDIT (read-only), Kerry 2026-10-06 via Front Desk: "you
mentioned some things you couldn't see. Create tools for you to see them".

The audit reads a saved sheet and reports flags and rule results; it must
write nothing. Kerry's rulings checked here: a REQUESTED partner rides in
the SAME cart, and a repeat pair is out of sequence while a lower-count
partner exists in the field.

Run: python3 test_pairings_audit.py
"""
import os, sys, tempfile, logging, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import database as db                          # noqa: E402
from email_parser.pairings_audit import event_pairing_audit       # noqa: E402
DB = os.environ["DATABASE_PATH"]
db.init_db(DB)
F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


EV, OLD = 9301, 9300
people = [  # cid, first, last, tee, request
    (810001, "Ann", "Able", "<50", "Bob Baker"),
    (810002, "Bob", "Baker", "<50", None),
    (810003, "Cy", "Cole", "50-64", None),
    (810004, "Di", "Dunn", "50-64", None),
    (810005, "Ed", "Eck", "50-64", None),
    (810006, "Fay", "Fox", "50-64", None),
    (810007, "Gus", "Gray", "<50", None),
    (810008, "Hal", "Hunt", "50-64", None),
]
with db._connect(DB) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, course) "
                 "VALUES (?,?,?,?,?,?,?)", (EV, "s10.6 Test", "2026-12-15", "San Antonio", "active", "9 Holes", "X"))
    for _id, _d in ((OLD, "2026-09-01"), (OLD - 1, "2026-08-01")):
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status) VALUES (?,?,?,?,?)",
                     (_id, f"old {_id}", _d, "San Antonio", "active"))
    for i, (cid, fn, ln, tee, req) in enumerate(people):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
                     "VALUES (?,?,?,'active_member')", (cid, fn, ln))
        conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, tee_choice, "
                     "transaction_status, order_date, order_id, email_uid, merchant, user_status, partner_request) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (f"{fn} {ln}", cid, "s10.6 Test", EV, "9", tee, "active", "2026-10-01",
                      f"R{cid}", f"manual-{cid}", "GoDaddy", "MEMBER", req))
    # Cy + Di have played together twice; Cy has never played with Ed, Fay, Gus, Hal.
    db._ensure_pairing_tables(conn)
    for _id, d in ((OLD - 1, "2026-08-01"), (OLD, "2026-09-01")):
        conn.execute("INSERT INTO pairing_history (player_a, player_b, event_id, event_date, rode, source) "
                     "VALUES ('Cy Cole', 'Di Dunn', ?, ?, 1, 'gg_teesheet')", (_id, d))
    conn.commit()

# Group 1: the request pair split across carts (rule 5 must flag).
# Group 2: Cy + Di together again in ONE cart (repeat out of sequence + R-G).
db.save_event_pairings(EV, {"9": [
    {"group_num": 1, "slot_label": "5:00 PM", "players": [
        {"name": "Ann Able", "cart_pos": 1, "customer_id": 810001, "tee_choice": "<50"},
        {"name": "Gus Gray", "cart_pos": 2, "customer_id": 810007, "tee_choice": "<50"},
        {"name": "Bob Baker", "cart_pos": 3, "customer_id": 810002, "tee_choice": "<50"},
        {"name": "Hal Hunt", "cart_pos": 4, "customer_id": 810008, "tee_choice": "50-64"}]},
    {"group_num": 2, "slot_label": "5:08 PM", "players": [
        {"name": "Cy Cole", "cart_pos": 1, "customer_id": 810003, "tee_choice": "50-64"},
        {"name": "Di Dunn", "cart_pos": 2, "customer_id": 810004, "tee_choice": "50-64"},
        {"name": "Ed Eck", "cart_pos": 3, "customer_id": 810005, "tee_choice": "50-64"},
        {"name": "Fay Fox", "cart_pos": 4, "customer_id": 810006, "tee_choice": "50-64"}]}]})


def snapshot():
    with db._connect(DB) as c:
        return {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("event_pairings", "pairing_history", "items", "customers")}, \
            [tuple(r) for r in c.execute("SELECT group_num, player_name, cart_pos FROM event_pairings "
                                         "WHERE event_id = ? ORDER BY group_num, cart_pos", (EV,))]


before = snapshot()
a = event_pairing_audit(EV, db_path=DB)
after = snapshot()
check("audit returns without error", "error" not in a, a.get("error"))
check("audit writes nothing (counts and the saved sheet unchanged)", before == after, f"{before} -> {after}")
check("two groups, eight players", a["summary"]["groups"] == 2 and a["summary"]["players"] == 8, a["summary"])
check("the response is JSON-serialisable (MCP + bridge)", bool(json.dumps(a, default=str)))

r5 = [f for f in a["flags"] if f["rule"].startswith("rule 5")]
check("rule 5: requested partners in different carts is flagged (Kerry 10/6: same cart)",
      len(r5) == 1 and "different carts" in r5[0]["detail"], r5)

rep = {(r["a"], r["b"]): r for r in a["repeats"]}
cd = rep.get(("Cy Cole", "Di Dunn"))
check("repeat table: Cy + Di at season count 2", cd and cd["season_count"] == 2, a["repeats"])
check("repeat out of sequence while lower-count partners exist", cd and cd["out_of_sequence"], cd)
check("alternatives list a zero-count partner for Cy",
      cd and cd["alternatives"]["Cy Cole"]["lowest_available"] == 0
      and "Ed Eck" in cd["alternatives"]["Cy Cole"]["partners_at_lowest"], cd)
rg = [f for f in a["flags"] if f["rule"].startswith("R-G")]
check("R-G: repeat cart pair without a request is flagged", any("Cy Cole" in f["detail"] for f in rg), rg)

# A requested pair in the SAME cart passes and is not counted as an R-G or repeat violation.
db.save_event_pairings(EV, {"9": [
    {"group_num": 1, "slot_label": "5:00 PM", "players": [
        {"name": "Ann Able", "cart_pos": 1, "customer_id": 810001, "tee_choice": "<50"},
        {"name": "Bob Baker", "cart_pos": 2, "customer_id": 810002, "tee_choice": "<50"},
        {"name": "Gus Gray", "cart_pos": 3, "customer_id": 810007, "tee_choice": "<50"},
        {"name": "Hal Hunt", "cart_pos": 4, "customer_id": 810008, "tee_choice": "50-64"}]}]})
b = event_pairing_audit(EV, db_path=DB)
r5b = [x for g in b["groups"] for x in g["rules"] if x["rule"].startswith("rule 5")]
check("rule 5: same cart passes", r5b and all(x["ok"] for x in r5b), r5b)
pl = {p["name"]: p for p in b["players"]}
check("per-player flags carry blind gate, index source and events played",
      all(k in pl["Ann Able"] for k in ("blind_gate", "index_source", "events_played_before",
                                        "solo_history", "first_three", "ambassador")), pl["Ann Able"])
check("generator alternative is reported (never saved)",
      "generator_alternative" in b and "summary" in b)
check("unknown event returns an error, not a crash", "error" in event_pairing_audit(999999, db_path=DB))

print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED'}")
sys.exit(1 if F else 0)
