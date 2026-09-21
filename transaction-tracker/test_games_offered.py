"""GAMES OFFERED in Event Setup — the Platform's commerce entities in the
Tracker (Kerry 2026-09-21: "Yes, add a Games Offered setting to Event
Setup … There's schema for each bundle and each game within the bundles
for full allocation and tracking purposes").

Run: python3 test_games_offered.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import database as db                          # noqa: E402
DB = os.environ["DATABASE_PATH"]
db.init_db(DB)
F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond: F.append(label)

print("1. The library and the bundles (seeded from side-games.md)")
cat = db.get_bundle_catalog(DB)
b = {x["bundle_key"]: x for x in cat["bundles"]}
check("seven games in the library, three bundles", len(cat["games"]) == 7 and set(b) == {"NET", "GROSS", "BOTH"}, (len(cat["games"]), list(b)))
check("NET = Individual Net + MVP, sells at $16 (9h) / $30 (18h) — buy-ins + markup, never stored",
      b["NET"]["games"] == ["ind_net", "mvp"] and b["NET"]["price_9"] == 16 and b["NET"]["price_18"] == 30, b["NET"])
check("GROSS = Skins + Individual Gross, $16 / $30", b["GROSS"]["games"] == ["skins", "ind_gross"] and b["GROSS"]["price_9"] == 16 and b["GROSS"]["price_18"] == 30, b["GROSS"])
check("BOTH = all four, $32 / $60, members only", b["BOTH"]["games"] == ["ind_net", "mvp", "skins", "ind_gross"] and b["BOTH"]["price_9"] == 32 and b["BOTH"]["price_18"] == 60 and b["BOTH"]["members_only"] == 1, b["BOTH"])

print("2. The setting per event")
with db._connect(DB) as conn:
    conn.executemany("INSERT INTO events (id, item_name, event_date, chapter, status, format, side_game_fee) VALUES (?,?,?,?,?,?,?)", [
        (9301, "s9.25 Canyon Springs", "2026-09-29", "San Antonio", "active", "9 Holes", 7.0),
        (9302, "SOCIAL | Range Night", "2026-10-10", "San Antonio", "active", "9 Holes", None)])
    conn.commit()
    n = db._backfill_event_bundle_offers(conn); conn.commit()
check("backfill gives every event explicit rows — offered when its setup carries a games fee",
      n == 2 and db.get_event_bundle_offers(9301, DB) == {"offered": ["NET", "GROSS", "BOTH"], "source": "setup"}
      and db.get_event_bundle_offers(9302, DB) == {"offered": [], "source": "setup"})
with db._connect(DB) as conn:
    check("…and is idempotent", db._backfill_event_bundle_offers(conn) == 0)
res = db.set_event_bundle_offers(9301, ["NET"], DB)
check("setting NET only: BOTH follows NET + GROSS, so it drops", res["offered"] == ["NET"], res)
res = db.set_event_bundle_offers(9301, ["gross", "NET", "junk"], DB)
check("setting both (any case, unknown keys ignored) brings BOTH back", res["offered"] == ["NET", "GROSS", "BOTH"], res)
evs = {e["id"]: e for e in db.get_all_events(DB)}
check("the events list carries games_offered", evs[9301]["games_offered"] == ["NET", "GROSS", "BOTH"] and evs[9302]["games_offered"] == [], (evs[9301].get("games_offered"), evs[9302].get("games_offered")))

print("3. Add Player follows the setting")
db.set_event_bundle_offers(9301, ["GROSS"], DB)
o = db.add_player_options(9301, DB)
check("GROSS only → Gross / None", o["side_games"] == ["Gross", "None"] and o["sources"]["side_games"] == "event setup: games offered GROSS", o)
db.set_event_bundle_offers(9301, ["NET", "GROSS"], DB)
check("NET + GROSS → Net / Gross / Both / None", db.add_player_options(9301, DB)["side_games"] == ["Net", "Gross", "Both", "None"])
check("nothing offered → None only", db.add_player_options(9302, DB)["side_games"] == ["None"])

print("4. The routes")
import app as appmod                                              # noqa: E402
c = appmod.app.test_client()
with c.session_transaction() as s_:
    s_["role"] = "manager"; s_["authenticated"] = True
r = c.patch("/api/events/9301", json={"games_offered": ["NET"]})
check("PATCH /api/events/<id> with games_offered writes the junction", r.status_code == 200 and db.get_event_bundle_offers(9301, DB)["offered"] == ["NET"], (r.status_code, r.get_data()[:120]))
r = c.patch("/api/events/9301", json={"games_offered": "NET"})
check("…and rejects a non-list", r.status_code == 400)
r = c.post("/api/events", json={"item_name": "s9.26 New Night", "event_date": "2026-10-06", "chapter": "San Antonio", "format": "9 Holes", "games_offered": ["GROSS"]})
new_id = ((r.get_json() or {}).get("event") or {}).get("id") or (r.get_json() or {}).get("id")
check("POST /api/events with games_offered sets it on the new event", r.status_code in (200, 201) and new_id and db.get_event_bundle_offers(new_id, DB)["offered"] == ["GROSS"], (r.status_code, r.get_data()[:160]))
r = c.get("/api/games/bundles")
check("GET /api/games/bundles serves the catalog", r.status_code == 200 and len(r.get_json()["bundles"]) == 3)

print("5. Event Setup UI")
html = open("templates/events.html").read()
check("both modals carry the NET / GROSS checkboxes with the bundle's games beside them",
      all(f'id="{p}-event-offer-{k}"' in html for p in ("edit", "add") for k in ("NET", "GROSS")) and 'class="offer-desc"' in html)
check("edit sends games_offered only when it changed; add always sends it",
      'changes.games_offered = offersFromForm("edit")' in html and 'games_offered: offersFromForm("add")' in html)
check("pricing tiers carry the bundle names and follow what is offered",
      "With NET or GROSS (+$" in html and "With BOTH (+$" in html and "With ${offered[0]} (+$" in html
      and "offered: offersFromForm(prefix)" in html)
try: os.unlink(DB)
except OSError: pass
print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
