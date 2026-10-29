"""HANDICAP LINK IDENTITY (Kerry 2026-10-29: "Paul Cleary!? Who's that? Why
would it be attached to it... Fix it now and run an audit on all other
handicaps... What do we need to do to make sure it doesn't happen again?").

A guest's GG name linked to Adam Baker's customer_id fed Baker's starter
sheet the guest's index. This proves: the name check, the audit, the unlink
(link + scorecard + handicap rounds + block list), that the index readers
and the resolver never follow a wrong link, and that the automatic writers
refuse one.

Run: python3 test_hcp_link_identity.py
"""
import os, sys, io, contextlib, logging, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-secret")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import hcp_link_identity as hli
    db.init_db(DB)

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

BAKER, LUKE, PAT, MATT = 990087, 990013, 990136, 990095
with db._connect(DB) as conn:
    for cid, fn, ln in ((BAKER, "Adam", "Baker"), (LUKE, "Luke", "Youngs"),
                        (PAT, "Pat", "Youngs"), (MATT, "Matthew", "Lawyer")):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?, ?, ?)",
                     (cid, fn, ln))
    conn.execute("INSERT INTO customer_aliases (customer_name, alias_type, alias_value, customer_id) "
                 "VALUES ('Adam Baker', 'name', 'James Baker', ?)", (BAKER,))
    for pn, cid in (("Adam Baker", BAKER), ("Paul Cleary", BAKER), ("Luke Youngs", LUKE),
                    ("Matt Lawyer", MATT)):
        conn.execute("INSERT INTO handicap_player_links (player_name, customer_id) VALUES (?, ?)", (pn, cid))
    # Baker's own rounds (low) and Cleary's three (high)
    for i in range(8):
        conn.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, "
                     "differential, customer_id) VALUES ('Adam Baker', ?, 40, 35.0, 120, 3.0, ?)",
                     (f"2026-09-{10 + i:02d}", BAKER))
    for i in range(3):
        conn.execute("INSERT INTO handicap_rounds (player_name, round_date, adjusted_score, rating, slope, "
                     "differential, customer_id) VALUES ('Paul Cleary', '2026-05-16', 42, 33.1, 109, 9.0, ?)",
                     (BAKER,))
    conn.execute("INSERT INTO scoring_rounds (customer_id, player_name, round_date, holes_played, source) "
                 "VALUES (?, 'Cleary, Paul', '2026-05-16', 9, 'gg')", (BAKER,))
    conn.execute("INSERT INTO scoring_rounds (customer_id, player_name, round_date, holes_played, source) "
                 "VALUES (?, 'BAKER, Adam', '2026-09-10', 9, 'gg')", (BAKER,))
    conn.commit()

print("1. The name check")
with db._connect(DB) as conn:
    check("'Paul Cleary' is not Adam Baker", hli.name_matches(conn, "Paul Cleary", BAKER) == "mismatch")
    check("'Cleary, Paul' (GG form) is not Adam Baker", hli.name_matches(conn, "Cleary, Paul", BAKER) == "mismatch")
    check("'BAKER, Adam' is Adam Baker", hli.name_matches(conn, "BAKER, Adam", BAKER) == "match")
    check("an alias full name ('James Baker') is Adam Baker", hli.name_matches(conn, "James Baker", BAKER) == "match")
    check("'Matt Lawyer' is likely Matthew Lawyer", hli.name_matches(conn, "Matt Lawyer", MATT) == "likely")
    check("family: 'Pat Youngs' is NOT Luke Youngs", hli.name_matches(conn, "Pat Youngs", LUKE) == "mismatch")
    check("suffix and digit noise ignored ('BAKER, Adam1 Jr')",
          hli.name_matches(conn, "BAKER, Adam1 Jr", BAKER) == "match")

print("2. The audit finds it")
with db._connect(DB) as conn:
    a = hli.audit(conn)
check("the Cleary link is listed", [r["player_name"] for r in a["links"]] == ["Paul Cleary"], a["links"])
check("Cleary's scorecard on Baker is listed", [r["player_name"] for r in a["scorecards"]] == ["Cleary, Paul"], a["scorecards"])
check("Cleary's handicap rounds on Baker are listed",
      [(r["player_name"], r["rounds"]) for r in a["handicap_rounds"]] == [("Paul Cleary", 3)], a["handicap_rounds"])
check("Matt Lawyer is 'likely', not a finding", [r["player_name"] for r in a["likely"]] == ["Matt Lawyer"])

print("3. Readers never follow the wrong link (before the unlink)")
with db._connect(DB) as conn:
    check("own name first, the wrong one never trusted",
          db._trusted_link_names(conn, BAKER) == ["Adam Baker"], db._trusted_link_names(conn, BAKER))
    check("the resolver does not send 'Cleary, Paul' to Baker", db._resolve_scoring_player(conn, "Cleary, Paul") is None)
    check("the resolver still sends 'BAKER, Adam' to Baker", db._resolve_scoring_player(conn, "BAKER, Adam") == BAKER)

print("4. Unlink: dry run, then apply")
with db._connect(DB) as conn:
    d = hli.unlink(conn, "Paul Cleary", BAKER)
    check("dry run names one link, one card, three rounds and writes nothing",
          d["links"] == ["Paul Cleary"] and len(d["scorecards"]) == 1 and d["handicap_rounds"] == 3
          and not d["applied"]
          and conn.execute("SELECT customer_id FROM handicap_player_links WHERE player_name='Paul Cleary'").fetchone()[0] == BAKER, d)
    hli.unlink(conn, "Paul Cleary", BAKER, apply=True, note="test")
    conn.commit()
    check("the link keeps its row with no customer",
          tuple(conn.execute("SELECT customer_id, customer_name FROM handicap_player_links "
                             "WHERE player_name='Paul Cleary'").fetchone()) == (None, None))
    check("Cleary's card is off Baker; Baker's own card stays",
          [r[0] for r in conn.execute("SELECT player_name FROM scoring_rounds WHERE customer_id = ?", (BAKER,))] == ["BAKER, Adam"])
    check("Cleary's handicap rounds are off Baker, still under his own name",
          conn.execute("SELECT COUNT(*) FROM handicap_rounds WHERE player_name='Paul Cleary' AND customer_id IS NULL").fetchone()[0] == 3)
    check("the pair is blocked from re-linking", hli.is_blocked(conn, "Cleary, Paul", BAKER))
    check("the writers' guard refuses the pair", not hli.link_cid_ok(conn, "Paul Cleary", BAKER))
    check("the audit is clean afterwards", hli.audit(conn)["clean"], hli.audit(conn))

print("5. Automatic writers refuse a wrong link")
with db._connect(DB) as conn:
    conn.execute("INSERT INTO handicap_player_links (player_name, customer_name) VALUES ('Zed Stranger', 'Adam Baker')")
    conn.commit()
    db._backfill_customer_id_on_player_links(conn)
    check("the customer_id backfill does not put 'Zed Stranger' on Baker",
          conn.execute("SELECT customer_id FROM handicap_player_links WHERE player_name='Zed Stranger'").fetchone()[0] is None)
with db._connect(DB) as conn:
    check("link_cid_ok allows 'Adam Baker' -> Baker", hli.link_cid_ok(conn, "Adam Baker", BAKER))

print("6. Wiring")
_a = open("app.py", encoding="utf-8").read()
_m = open("mcp_server.py", encoding="utf-8").read()
_h = open("email_parser/health.py", encoding="utf-8").read()
check("the Handicaps page Unlink clears the customer_id too",
      "_hcp_unlink(conn, player_name" in _a.split("def api_handicap_unlink_player")[1][:2000])
check("bridges scoring-hcp-link-identity and scoring-hcp-unlink exist",
      'cmd == "scoring-hcp-link-identity"' in _m and 'cmd == "scoring-hcp-unlink"' in _m)
check("the daily health digest raises a finding", '"key": "hcp_link_identity"' in _h)
_d = open("email_parser/database.py", encoding="utf-8").read()
check("no reader pools every linked name unchecked any more",
      'names.add(lk["player_name"])' not in _d and '_names.add(lk["player_name"])' not in _d)

try:
    os.remove(DB)
except OSError:
    pass
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
