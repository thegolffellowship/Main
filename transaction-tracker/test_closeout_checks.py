"""Closeout off GG: pairing history from entered groups + "results are final"
(v2.511.0, CA #829 item 3). Run: python test_closeout_checks.py
"""
import json, os, sqlite3, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from email_parser import database as db  # noqa: E402
from email_parser import closeout_checks as cc  # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

tmp = tempfile.mktemp(suffix=".db"); db.init_db(tmp)
c = sqlite3.connect(tmp)
people = {401: ("Ann", "Able"), 402: ("Bob", "Baker"), 403: ("Cal", "Cole"), 404: ("Dee", "Dunn"),
          405: ("Eve", "Esch"), 406: ("Fay", "Frye")}
for cid, (f, l) in people.items():
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, account_status) "
              "VALUES (?, ?, ?, 'San Antonio', 'active')", (cid, f, l))
c.execute("INSERT INTO events (id, item_name, event_date, chapter, status) VALUES (771, 's9.40 Future Links', '2026-10-13', 'San Antonio', 'active')")
c.execute("INSERT INTO events (id, item_name, event_date, chapter, status) VALUES (772, 's9.39 Shadow Links', '2026-09-29', 'San Antonio', 'active')")
c.commit(); c.close()

def card(cid, group, holes=9, played=True):
    return {"customer_id": cid, "name": " ".join(people[cid]), "group_id": group,
            "scores": ({str(h): 4 for h in range(1, holes + 1)} if played else {})}

def read(event_id, status="closed", players=None, sign=True, hio=None, ctp=None):
    players = players if players is not None else [card(401, 1), card(402, 1), card(403, 1), card(404, 1),
                                                    card(405, 2), card(406, 2, played=False)]
    return {"event_id": event_id, "rounds": [{
        "round_id": 55, "label": "s9.40", "holes": 9, "status": status,
        "course": [{"hole": h, "par": 4} for h in range(1, 10)],
        "players": players, "teams": [], "card_checks": [{"group_id": 1}, {"group_id": 2}],
        "signoffs": ([{"customer_id": p["customer_id"], "kind": "player"} for p in players] if sign else []),
        "ctp": ctp or {}, "hio": hio or []}]}

print("Pairing history from entered groups")
r = cc.pairing_history_from_entry(771, apply=False, db_path=tmp, _read=read(771))
check("after the cutover with no GG pairs the mode is authoritative", r.get("mode") == "authoritative", r)
check("group of 4 gives 6 pairs, 2 of them cart partners; group 2's lone player pairs with nobody",
      r.get("pairs") == 6 and r.get("rode_pairs") == 2, r)
check("a seeded player with no entered hole is named, not paired", r.get("not_paired_no_score") == ["Fay Frye"], r)
check("dry run writes nothing", not r.get("applied"))
r = cc.pairing_history_from_entry(771, apply=True, db_path=tmp, _read=read(771))
c = sqlite3.connect(tmp)
rows = c.execute("SELECT player_a, player_b, customer_a_id, customer_b_id, rode, source, round_id FROM pairing_history WHERE event_id = 771").fetchall()
check("apply writes 6 rows, source entry, round se:55, every row carries both customer_ids",
      len(rows) == 6 and all(x[5] == "entry" and x[6] == "se:55" and x[2] and x[3] for x in rows), rows)
check("Ann+Bob rode together (seats 1&2), Ann+Cal did not",
      any(set(x[2:4]) == {401, 402} and x[4] == 1 for x in rows) and any(set(x[2:4]) == {401, 403} and x[4] == 0 for x in rows), rows)
cc.pairing_history_from_entry(771, apply=True, db_path=tmp, _read=read(771))
n = c.execute("SELECT COUNT(*) FROM pairing_history WHERE event_id = 771").fetchone()[0]
check("re-applying replaces, never doubles", n == 6, n)
c.execute("INSERT INTO pairing_history (player_a, player_b, event_id, event_date, customer_a_id, customer_b_id, rode, source) "
          "VALUES ('Ann Able', 'Eve Esch', 772, '2026-09-29', 401, 405, 0, 'gg_teamnet')")
c.commit(); c.close()
r = cc.pairing_history_from_entry(772, apply=True, db_path=tmp, _read=read(772))
check("an event with GG pairs runs in shadow and writes nothing", r.get("mode") == "shadow" and not r.get("applied"), r)
check("shadow names the pairs each side has alone",
      "Ann Able + Eve Esch" in r["parity"]["gg_only"] and "Ann Able + Bob Baker" in r["parity"]["entered_only"], r.get("parity"))

print("\nResults are final: entry era")
c = sqlite3.connect(tmp)
for cid in (401, 402, 403, 404, 405):
    c.execute("INSERT INTO scoring_rounds (customer_id, player_name, event_id, round_date, holes_played, gross, source) "
              "VALUES (?, ?, 771, '2026-10-13', 9, 36, 'entry')", (cid, " ".join(people[cid])))
c.execute("INSERT INTO tgf_events (id, code, name, event_date, events_id) VALUES (91, 's9.40', 's9.40 Future Links', '2026-10-13', 771)")
c.execute("INSERT INTO tgf_payouts (event_id, customer_id, category, amount, description) VALUES (91, 401, 'Individual Net', 20, 'x')")
c.commit(); c.close()
f = cc.closeout_final_check(771, db_path=tmp, _read=read(771))
check("closed, signed, published, paid: FINAL", f.get("era") == "entry" and f.get("final") is True, f)
f = cc.closeout_final_check(771, db_path=tmp, _read=read(771, status="open", sign=False))
check("unsigned cards block, each player named", not f["final"] and any("Ann Able: card not signed" in b for b in f["blocking"]), f.get("blocking"))
f = cc.closeout_final_check(771, db_path=tmp, _read=read(771, hio=[{"hole": 3, "status": "witnessed"}]))
check("a hole-in-one claim still in flight blocks", not f["final"] and any("hole-in-one" in b for b in f["blocking"]), f.get("blocking"))
f = cc.closeout_final_check(771, db_path=tmp, _read=read(771, ctp={"3": None}))
check("an unanswered CTP hole is a warning, not a blocker", f["final"] and any("CTP" in w for w in f["warnings"]), f)
c = sqlite3.connect(tmp); c.execute("DELETE FROM scoring_rounds WHERE customer_id = 405 AND event_id = 771"); c.commit(); c.close()
f = cc.closeout_final_check(771, db_path=tmp, _read=read(771))
check("a signed card not yet published blocks and names the publish step",
      not f["final"] and any("Eve Esch" in b and "scoring-entry-publish:771|apply" in b for b in f["blocking"]), f.get("blocking"))

print("\nResults are final: GG era")
c = sqlite3.connect(tmp)
c.execute("INSERT INTO events (id, item_name, event_date, chapter, status) VALUES (773, 's9.38 Old Links', '2026-09-22', 'San Antonio', 'active')")
for cid in (401, 402):
    c.execute("INSERT INTO items (email_uid, item_index, merchant, customer, customer_id, item_name, event_id, transaction_status, chapter, order_date, item_price) "
              "VALUES (?, 0, 'Manual Entry', ?, ?, 's9.38 Old Links', 773, 'active', 'San Antonio', '2026-09-20', '$50.00')",
              (f"manual-cc-{cid}", " ".join(people[cid]), cid))
c.execute("INSERT INTO scoring_rounds (customer_id, player_name, event_id, round_date, holes_played, gross, source) VALUES (401, 'ABLE, Ann', 773, '2026-09-22', 9, 40, 'gg')")
c.commit(); c.close()
f = cc.closeout_final_check(773, db_path=tmp, _read={"rounds": []})
check("GG era: a missing card, no boards and no payouts all block, by name",
      f["era"] == "gg" and not f["final"] and any("Bob Baker" in b for b in f["blocking"])
      and any("results boards" in b for b in f["blocking"]) and any("payouts" in b for b in f["blocking"]), f)
c = sqlite3.connect(tmp)
c.execute("DELETE FROM items WHERE customer_id = 402 AND event_id = 773")
db._ensure_gg_game_results_tables(c) if hasattr(db, "_ensure_gg_game_results_tables") else None
for game, label, purse in (("team_net", "TEAM Net $", 44.0), ("team_net_board", "TEAM Net $", 0.0),
                           ("skins", "SKINS Gross $", 0.0)):
    c.execute("INSERT INTO gg_game_results (event_id, game, game_label, player_name, purse) VALUES (773, ?, ?, 'x', ?)",
              (game, label, purse))
c.execute("INSERT INTO tgf_events (id, code, name, event_date, events_id) VALUES (92, 's9.38', 's9.38 Old Links', '2026-09-22', 773)")
c.execute("INSERT INTO tgf_payouts (event_id, customer_id, category, amount, description) VALUES (92, 401, 'Team Net', 11, 'auto: x')")
c.commit(); c.close()
f = cc.closeout_final_check(773, db_path=tmp, _read={"rounds": []})
check("a full-standings '_board' row at $0 never blocks; a game with no purse at all does",
      not f["final"] and any("SKINS" in b for b in f["blocking"]) and not any("team_net" in b for b in f["blocking"]), f.get("blocking"))
c = sqlite3.connect(tmp); c.execute("UPDATE gg_game_results SET purse = 26 WHERE event_id = 773 AND game = 'skins'"); c.commit(); c.close()
f = cc.closeout_final_check(773, db_path=tmp, _read={"rounds": []})
check("with every paying game purse-entered, cards = field and payouts recorded: FINAL", f["final"] is True, f)
check("an unknown event is refused", "error" in cc.closeout_final_check("nope", db_path=tmp, _read={"rounds": []}))

src = open(os.path.join(os.path.dirname(__file__), "email_parser", "closeout_checks.py"), encoding="utf-8").read()
import re
check("entered scores are read only through score_entry (no se_* table names here)",
      not re.search(r"\bse_(hole_scores|players|rounds|teams|groups)\b", src))
m = open(os.path.join(os.path.dirname(__file__), "mcp_server.py"), encoding="utf-8").read()
check("both bridges exist", 'cmd == "scoring-closeout-final"' in m and 'cmd == "scoring-pairings-entry"' in m)
print("\nALL PASS" if not F else f"\\nFAILED: {F}")
sys.exit(1 if F else 0)
