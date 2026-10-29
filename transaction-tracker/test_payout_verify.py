"""VERIFY BEFORE PAY (Kerry 2026-10-28, Event Ops #2460-B): "That verification
needs to happen before I make payouts, and raise any flags stopping me from
running payouts before I make them."

auto_payouts records -> VERIFYING; Pay stays locked (Payouts page, Mark Paid,
the admin payout report) until recorded = the GAMES re-derivation, card
parity is clean and every winner has a customer; a failure keeps it locked
and raises ONE "PAYOUTS HELD" COO item. Dial payout_verify_gate, default OFF.
The engine pieces (parity, the GAMES assembly, the entered scores) are
stubbed here.

Run: python3 test_payout_verify.py
"""
import os, sys, io, json, contextlib, logging, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-pv-"), "t.db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import payout_verify as pv
    from email_parser import card_parity as cp
    from email_parser import score_entry as se
    from email_parser import admin_payout_report as apr
    from email_parser import closeout_checks as cc
    db.init_db(DB)

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

EV, TID = 9801, 41
with db._connect(DB) as c:
    c.execute("INSERT INTO events (id, item_name, event_date, chapter, status) VALUES "
              "(?, 's9.30 The Quarry', '2099-10-28', 'San Antonio', 'active')", (EV,))
    for cid, fn in ((990101, "Ann"), (990102, "Bob")):
        c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?, ?, 'Test')", (cid, fn))
    c.execute("INSERT INTO tgf_events (id, code, name, event_date, events_id) VALUES "
              "(?, 's9.30 The Quarry', 's9.30 The Quarry', '2099-10-28', ?)", (TID, EV))
    c.execute("INSERT INTO tgf_payouts (event_id, customer_id, category, amount, description) VALUES "
              "(?, 990101, 'Individual Net', 25.50, 'auto: 1st'), (?, 990102, 'Skins', 10.00, 'auto: skin')",
              (TID, TID))
    c.commit()

GAMES = [{"golferName": "Ann Test", "customer_id": 990101, "category": "Individual Net", "amount": 25.50},
         {"golferName": "Bob Test", "customer_id": 990102, "category": "Skins", "amount": 10.00}]
PARITY = {"ok": True}
cp.engine_card_parity = lambda ev, db_path=None, state=None: (
    {"event": {"id": EV, "name": "s9.30 The Quarry"}, "ok": True, "mismatches": []} if PARITY["ok"] else
    {"event": {"id": EV, "name": "s9.30 The Quarry"}, "ok": False,
     "mismatches": [{"name": "Bob Test", "detail": "hole 3"}]})
db.assemble_event_game_payouts = lambda name, db_path=None, **k: {"rows": [dict(r) for r in GAMES],
                                                                  "total": sum(r["amount"] for r in GAMES)}
se.get_entered_scores = lambda eid, db_path=None, **k: {"rounds": []}

def items():
    with db._connect(DB) as c:
        return [dict(r) for r in c.execute(
            "SELECT subject, summary FROM action_items WHERE subject LIKE 'PAYOUTS HELD%'").fetchall()]

# 1. Dial OFF (the default): nothing is marked, nothing is locked.
check("dial defaults off", not pv.gate_on(DB))
check("off: no lock even with a state on file",
      (pv._set_state(EV, {"state": "failed", "reasons": ["x"]}, DB) or True) and pv.lock_for(EV, DB) is None)
data = pv.annotate({"events": [{"id": TID, "events_id": EV, "payouts": []}]}, DB)
check("off: /api/tgf events carry pay_locked = null", data["events"][0]["pay_locked"] is None)
with db._connect(DB) as c:
    c.execute("DELETE FROM app_settings WHERE key = ?", (f"payout_verify:{EV}",)); c.commit()

# 2. Dial ON. An event never marked by auto_payouts is never locked.
db.set_app_setting("payout_verify_gate", "on", DB)
check("an event auto_payouts never recorded is not locked", pv.lock_for(EV, DB) is None)

# 3. Recorded -> verifying -> locked.
pv.mark_verifying(EV, DB)
lk = pv.lock_for(EV, DB)
check("just recorded: Pay locked as verifying", lk and lk.startswith("Verifying"), lk)
check("Mark Paid's lookup from the Payouts-page id sees the same lock",
      pv.lock_for_tgf_event(TID, DB) == lk)

# 4. Check passes -> verified -> unlocked, no COO item.
r = pv.verify(EV, DB)
check("recorded = GAMES, parity clean: verified", r.get("state") == "verified", r)
check("verified: Pay open", pv.lock_for(EV, DB) is None)
check("verified: no PAYOUTS HELD item", not items())

# 5. Recorded rows change after the pass -> locked again, the sweep re-checks.
with db._connect(DB) as c:
    c.execute("UPDATE tgf_payouts SET amount = 12.00 WHERE customer_id = 990102"); c.commit()
lk = pv.lock_for(EV, DB)
check("rows changed since the check: locked as verifying", lk and "changed" in lk, lk)
out = pv.sweep(DB)
st = pv.get_state(EV, DB)
check("the sweep re-checks it and it fails (recorded $12 vs GAMES $10)",
      out and st["state"] == "failed" and any("Bob Test Skins $12.00" in x for x in st["reasons"]), st)
lk = pv.lock_for(EV, DB)
check("failed: Pay locked, the reason names the player and amounts",
      lk and lk.startswith("Verification failed") and "$10.00" in lk, lk)
it = items()
check("failed: ONE COO item 'PAYOUTS HELD: <event>'",
      len(it) == 1 and it[0]["subject"] == "PAYOUTS HELD: s9.30 The Quarry", it)
pv.verify(EV, DB)
check("a second failed check does not add a second item", len(items()) == 1)

# 6. Card parity failing also fails the check.
with db._connect(DB) as c:
    c.execute("UPDATE tgf_payouts SET amount = 10.00 WHERE customer_id = 990102"); c.commit()
PARITY["ok"] = False
r = pv.verify(EV, DB)
check("card parity off: failed", r["state"] == "failed" and any("disagree" in x for x in r["reasons"]), r)
PARITY["ok"] = True
check("fixed: verified again", pv.verify(EV, DB)["state"] == "verified")

# 7. A winner the re-derivation finds but nobody recorded.
GAMES.append({"golferName": "Ann Test", "customer_id": 990101, "category": "CTP", "amount": 5.0})
r = pv.verify(EV, DB)
check("won on GAMES but not recorded: failed",
      r["state"] == "failed" and any("not recorded" in x and "CTP" in x for x in r["reasons"]), r)

# 8. The Payouts page API and the admin report read the lock.
data = pv.annotate({"events": [{"id": TID, "events_id": EV, "payouts": [
    {"id": 1, "customer_id": 990101, "category": "Individual Net", "amount": 25.5},
    {"id": 2, "customer_id": 990102, "category": "Skins", "amount": 10.0}]}]}, DB)
check("/api/tgf event carries pay_locked + payout_verify",
      data["events"][0]["pay_locked"] and data["events"][0]["payout_verify"]["state"] == "failed")
cc.closeout_final_check = lambda eid, db_path=None, _read=None: {"final": True, "blocking": []}
db._event_roster_rows = lambda conn, eid: [{"customer_id": 990101}]
p = apr.plan("2099-10-28", DB)
check("admin report plan carries the lock", p["events"] and p["events"][0]["pay_locked"], p)
html = apr.build(p)["html"]
check("admin report: the PAYMENTS button is replaced by the lock", "Pay is locked" in html
      and "Open PAYMENTS" not in html)
pv.mark_verifying(EV, DB)
r = apr.run(day="2099-10-28", confirm=False, db_path=DB)
check("admin report waits while an event is still verifying", r.get("status") == "waiting", r)

# 9. Wiring.
src = open("app.py").read()
check("Mark Paid refuses a locked event (409)", "lock_for_tgf_event(event_id)" in src and "409" in src)
check("/api/tgf is annotated", "_pv_annotate(get_tgf_data())" in src)
ap = open("email_parser/auto_payouts.py").read()
check("auto_payouts marks + verifies after recording, sweeps each run",
      "mark_verifying(eid" in ap and "_pv.sweep(" in ap)
tg = open("templates/tgf.html").read()
check("tgf.html Pay cell locks on ev.pay_locked with the reason as tooltip",
      "ev.pay_locked" in tg and 'title="${escR(ev.pay_locked)}"' in tg)
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
