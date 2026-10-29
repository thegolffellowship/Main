"""PAID-AT TIMES (Kerry 2026-10-28, Event Ops #2460-D): "timestamp each payment
... there could be a big gap between a batch and one other or multiple other
batches. Looking for total time taken as a value to track over time".

Each paid payout row gets a Central date AND time: the receipt's arrival when
the matcher marks it paid, the moment Mark Paid is pressed otherwise.
`paid_at` keeps the date. `payout_timing(event_id)` -> first / last paid,
batches (a gap over 30 minutes starts one), minutes spent.

Run: python3 test_payout_timing.py
"""
import os, sys, io, json, contextlib, logging, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-pt-"), "t.db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import payout_timing as pt
    from email_parser.timezone_utils import today_central_str
    db.init_db(DB)

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

EV, TID = 9811, 51
with db._connect(DB) as c:
    c.execute("INSERT INTO events (id, item_name, event_date, chapter, status) VALUES "
              "(?, 's9.30 The Quarry', '2026-10-27', 'San Antonio', 'active')", (EV,))
    for cid, fn in ((990201, "Ann"), (990202, "Bob"), (990203, "Cal")):
        c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?, ?, 'Timer')", (cid, fn))
    c.execute("INSERT INTO tgf_events (id, code, name, event_date, events_id) VALUES "
              "(?, 's9.30 The Quarry', 's9.30 The Quarry', '2026-10-27', ?)", (TID, EV))
    c.execute("INSERT INTO tgf_payouts (event_id, customer_id, category, amount, description) VALUES "
              "(?, 990201, 'Individual Net', 25.50, 'auto: 1st'), (?, 990201, 'Skins', 10.00, 'auto: skin'), "
              "(?, 990202, 'Skins', 10.00, 'auto: skin'), (?, 990203, 'CTP', 15.00, 'auto: ctp')",
              (TID, TID, TID, TID))
    # Two receipts: Ann at 8:02 PM Central (01:02 UTC next day), Bob 8:10 PM.
    for uid, cid, amt, utc in (("r1", 990201, 35.50, "2026-10-28T01:02:30Z"),
                               ("r2", 990202, 10.00, "2026-10-28T01:10:05Z")):
        c.execute("INSERT INTO expense_transactions (email_uid, source_type, merchant, amount, transaction_date, "
                  "transaction_type, customer_id, review_status, notes, raw_extract) VALUES "
                  "(?, 'venmo', ?, ?, '2026-10-27', 'payout', ?, 'approved', ?, ?)",
                  (uid, f"P{cid}", amt, cid, f"X Timer - Winnings for s9.30 The Quarry",
                   json.dumps({"email_received_at": utc})))
    c.commit()

# Pure pieces.
check("receipt time: UTC email arrival read as Central wall clock",
      pt.receipt_time({"raw_extract": json.dumps({"email_received_at": "2026-10-28T01:02:30Z"})})
      == "2026-10-27 20:02")
check("receipt time falls back to the ingest time (UTC) when the email time is missing",
      pt.receipt_time({"raw_extract": "{}", "created_at": "2026-10-28 01:15:00"}) == "2026-10-27 20:15")
b = pt.batches(["2026-10-27 20:02", "2026-10-27 20:10", "2026-10-27 21:30", "2026-10-27 21:31",
                "2026-10-28 07:00"])
check("batches: a gap over 30 minutes starts a new batch",
      [(x["start"], x["end"], x["payments"], x["minutes"]) for x in b] ==
      [("2026-10-27 20:02", "2026-10-27 20:10", 2, 8), ("2026-10-27 21:30", "2026-10-27 21:31", 2, 1),
       ("2026-10-28 07:00", "2026-10-28 07:00", 1, 0)], b)
check("batches: exactly 30 minutes stays in the same batch",
      len(pt.batches(["2026-10-27 20:00", "2026-10-27 20:30"])) == 1)

# The receipt matcher stamps the receipt's time.
res = db.auto_match_venmo_payouts_to_tgf(db_path=DB)
check("matcher marked both receipts paid", res.get("matched") == 2, res)
times = pt.paid_times(TID, DB)
with db._connect(DB) as c:
    rows = {r["id"]: dict(r) for r in c.execute("SELECT id, customer_id, paid_at FROM tgf_payouts").fetchall()}
ann = [i for i, r in rows.items() if r["customer_id"] == 990201]
check("each of Ann's rows carries the receipt's Central time",
      all((times.get(str(i)) or {}).get("at") == "2026-10-27 20:02" for i in ann)
      and all((times.get(str(i)) or {}).get("src") == "receipt" for i in ann), times)
check("paid_at keeps the DATE readers slice", all(rows[i]["paid_at"] == "2026-10-27" for i in ann))

# Mark Paid stamps the moment it was pressed (today's date only).
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as appmod
cl = appmod.app.test_client()
with cl.session_transaction() as s_:
    s_["role"] = "admin"; s_["authenticated"] = True
r = cl.post("/api/tgf/mark-paid", json={"event_id": TID, "customer_id": 990203, "payment_method": "zelle"})
check("Mark Paid ok", r.status_code == 200, r.get_data(as_text=True)[:200])
cal = [i for i, r_ in rows.items() if r_["customer_id"] == 990203]
st = (pt.paid_times(TID, DB).get(str(cal[0])) or {})
check("Mark Paid stamps the pressed time, today Central",
      st.get("src") == "pressed" and (st.get("at") or "")[:10] == today_central_str(), st)
with db._connect(DB) as c:
    pa = c.execute("SELECT paid_at FROM tgf_payouts WHERE id = ?", (cal[0],)).fetchone()[0]
check("Mark Paid's default date is the Central day", pa == today_central_str(), pa)
with db._connect(DB) as c:
    n = pt.stamp_conn(c, TID, ann, "2030-01-01 00:00", "pressed"); c.commit()
check("stamp_conn never overwrites a recorded time", n == 0
      and pt.paid_times(TID, DB)[str(ann[0])]["at"] == "2026-10-27 20:02")

# The reader.
t = pt.payout_timing(EV, DB)
check("timing: 3 payments (Ann's two rows are one payment)", t["payments"] == 3, t)
check("timing: first paid 8:02 PM, Ann + Bob one batch of 8 minutes",
      t["first_paid"] == "2026-10-27 20:02" and t["batches"][0]["minutes"] == 8
      and t["batches"][0]["payments"] == 2, t)
check("timing: the pressed payment is its own batch, minutes = sum of spans",
      t["batch_count"] == 2 and t["minutes_spent"] == 8, t)
check("timing: Central named", t["timezone"] == "America/Chicago")
check("an unknown event errors", "error" in pt.payout_timing(1, DB))

# /api/tgf carries the time on each paid row.
r = cl.get("/api/tgf")
evj = next(e for e in r.get_json()["events"] if e["id"] == TID)
check("/api/tgf rows carry paid_time", any(p.get("paid_time") == "2026-10-27 20:02" for p in evj["payouts"]))

src = open("mcp_server.py").read()
check("bridge scoring-payout-timing registered", 'cmd == "scoring-payout-timing"' in src
      and "scoring-payout-timing:<event_id>" in src)
check("the receipt handler keeps the email's arrival time",
      'extracted["email_received_at"] = email_data.get("date")' in open("app.py").read())
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
