"""Add Player → RSVP Only checks for credit (Kerry 2026-09-23): the credit
info a new RSVP row gets pre-selects the player's USUAL choices, and the
Add Player modal's hint endpoint says whether the player holds credit.
Run: python3 test_rsvp_add_credit.py"""
import os, sys, sqlite3, tempfile, contextlib, io, logging, json
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-rsvpcredit-"), "t.db")
os.environ["DATABASE_PATH"] = tmp
os.environ.setdefault("ADMIN_PIN", "1234"); os.environ.setdefault("SECRET_KEY", "x")
os.environ["SCHEDULER_DISABLED"] = "1"
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as A
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)

c = sqlite3.connect(tmp); c.row_factory = sqlite3.Row
c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter) VALUES (501, 'Eduardo', 'Melchor', 'Austin')")
c.execute("INSERT INTO events (id, item_name, event_date, format, chapter) VALUES (77, 'a9.25 Star Ranch', '2026-09-29', '9 Holes', 'Austin')")
def item(i, name, status, **kw):
    cols = dict(id=i, email_uid=f"u{i}", merchant="The Golf Fellowship", customer="Eduardo Melchor", customer_id=501,
                item_name=name, item_price="$72.00", order_date=f"2026-08-{i:02d}", transaction_status=status,
                holes="9", side_games="BOTH", tee_choice="<50", user_status="MEMBER")
    cols.update(kw)
    c.execute(f"INSERT INTO items ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", list(cols.values()))
# history: three BOTH / <50 registrations, one NET
item(1, "a9.20 Avery", "active"); item(2, "a9.21 Falconhead", "active"); item(3, "a9.22 Teravista", "active")
item(4, "a9.19 Star Ranch", "active", side_games="NET")
# +PAY children and RSVP rows must not vote
for i in (5, 6, 7, 8, 9):
    item(i, "a9.22 Teravista", "active", side_games="GROSS", parent_item_id=3, item_price="$11.00")
item(10, "a9.23 Kissing Tree", "rsvp_only", side_games="GROSS", item_price=None)
# the credit: a credited row that carried NONE
item(20, "a9.23 Avery Ranch", "credited", side_games="NONE", tee_choice="", item_price="$50.00", credit_amount=50.0)
# the new RSVP-only row for the target event
item(900, "a9.25 Star Ranch", "rsvp_only", side_games=None, tee_choice=None, user_status=None, item_price=None, order_date="2026-09-23")
c.commit()

print("\n== usual selections ==")
usual = A._player_usual_selections(c, 501, "Eduardo Melchor")
check("the most common choices over real registrations win (BOTH, <50, MEMBER, 9)",
      usual == {"holes": "9", "side_games": "BOTH", "tee_choice": "<50", "user_status": "MEMBER"}, str(usual))
check("+PAY children and RSVP rows do not vote (five GROSS children, one GROSS RSVP, still BOTH)", usual["side_games"] == "BOTH")
check("an unknown player yields nothing", A._player_usual_selections(c, None, "Nobody Here") == {})
c.close()

print("\n== the routes ==")
tc = A.app.test_client()
with tc.session_transaction() as s:
    s["role"] = "admin"; s["authenticated"] = True; s["logged_in"] = True
r = tc.get("/api/rsvps/900/credit-info")
d = r.get_json() or {}
check("credit-info answers for the RSVP row", r.status_code == 200, f"{r.status_code} {d}")
check("...with the one credit and its amount", len(d.get("credits") or []) == 1 and abs(float(d.get("total_credit") or 0) - 50.0) < 0.01, str(d.get("credits")))
ps = d.get("previous_selections") or {}
check("...pre-selecting the player's USUAL games and tee, not the credited row's NONE / blank",
      ps.get("side_games") == "BOTH" and ps.get("tee_choice") == "<50" and ps.get("user_status") == "MEMBER", str(ps))
check("...holes locked to the event format (9 Holes)", ps.get("holes") == "9", str(ps))
r = tc.get("/api/customers/credit-check?name=Eduardo%20Melchor")
d = r.get_json() or {}
check("credit-check says the player holds $50 credit (1 row)", r.status_code == 200 and d.get("has_credit") is True and abs(d["total"] - 50.0) < 0.01 and d["count"] == 1, str(d))
d = tc.get("/api/customers/credit-check?name=Nobody%20Here").get_json() or {}
check("...and no credit for an unknown name", d.get("has_credit") is False and d.get("count") == 0, str(d))
d = tc.get("/api/customers/credit-check").get_json() or {}
check("...and nothing for an empty name", d.get("has_credit") is False, str(d))

print()
if F:
    print(f"{len(F)} FAILED: " + "; ".join(F)); sys.exit(1)
print("ALL PASS")
