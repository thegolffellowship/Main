"""sales_tax_filings (Kerry 2026-09-30 #1047): FILED only from the table.
Run: python3 test_sales_tax_filings.py"""
import os, sys, json, sqlite3, tempfile, contextlib, io, logging
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-stf-"), "t.db")
os.environ["DATABASE_PATH"] = DB; os.environ.setdefault("SECRET_KEY", "x")
logging.disable(logging.CRITICAL)
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    db.init_db(DB)
    import mcp_server
from email_parser import sales_tax as st, margin_ledger as ml
c = sqlite3.connect(DB)
check("migration applied once and recorded", c.execute(
    "SELECT COUNT(*) FROM schema_migrations WHERE name = '0001_sales_tax_filings.sql'").fetchone()[0] == 1)
from email_parser.migrations import apply_migrations
check("re-running migrations applies nothing", apply_migrations(c) == [])
check("status: past due with no row = LATE; future = OPEN; row = FILED",
      st.status_for("2026-08", None, "2026-09-30") == "LATE" and st.status_for("2026-09", None, "2026-09-30") == "OPEN"
      and st.status_for("2026-08", {"period": "2026-08"}, "2026-09-30") == "FILED")
check("due dates: the 20th of the next month; December rolls the year",
      st.due_date_for("2026-08") == "2026-09-20" and st.due_date_for("2025-12") == "2026-01-20")
d = st.backfill(apply=False, db_path=DB)
check("backfill dry run: 6 confirmed + 13 Kerry's-word months, nothing written",
      d["rows"] == 19 and not d["errors"] and c.execute("SELECT COUNT(*) FROM sales_tax_filings").fetchone()[0] == 0, d)
a = st.backfill(apply=True, db_path=DB)
with db._connect(DB) as cc:
    rows = st.filings(cc)
check("backfill applied: 19 rows, 2026-08 absent", len(rows) == 19 and "2026-08" not in rows, sorted(rows))
check("a confirmed month carries the paid amount and WebFile ref", rows["2026-03"]["amount_paid"] == 288.54
      and rows["2026-03"]["webfile_ref"] == "9426022559" and rows["2026-03"]["evidence"] == "confirmation")
check("a Kerry's-word month has no amounts, says why", rows["2025-04"]["evidence"] == "kerry_word"
      and rows["2025-04"]["amount_paid"] is None and "iCloud" in rows["2025-04"]["note"])
check("confirmation row without a ref or path is refused",
      "error" in st.record_filing({"period": "2026-08", "evidence": "confirmation", "entered_by": "x"}, db_path=DB))
# liabilities: August 2026 is LATE (not "filed") until a row lands
c.execute("INSERT INTO acct_allocations (order_id, allocation_date, tax_reserve, tgf_operating) VALUES ('T1', '2026-08-15', 10, 100)")
c.execute("INSERT INTO acct_allocations (order_id, allocation_date, tax_reserve, tgf_operating) VALUES ('T2', '2026-03-15', 5, 50)")
c.commit()
lb = ml.liability_buckets(db_path=DB)["sales_tax_reserve"]
bm = lb["by_month"]
check("liabilities: 2026-08 reads LATE (no filing row), 2026-03 FILED (row)", bm["2026-08"]["status"] == "late"
      and bm["2026-03"]["status"] == "filed" and "2026-08" in lb["late"], {k: v["status"] for k, v in bm.items()})
r = json.loads(mcp_server._scoring_dispatch("", 'scoring-sales-tax-filing:{"period":"2026-08","evidence":"confirmation","webfile_ref":"X1","amount_paid":229.75,"entered_by":"test"}'))
check("bridge record is a dry run by default", r.get("dry_run") is True)
r = json.loads(mcp_server._scoring_dispatch("", 'scoring-sales-tax-filing:{"period":"2026-08","evidence":"confirmation","webfile_ref":"X1","amount_paid":229.75,"entered_by":"test"}|apply'))
check("bridge |apply records it; August now FILED", r.get("applied") and
      ml.liability_buckets(db_path=DB)["sales_tax_reserve"]["by_month"]["2026-08"]["status"] == "filed", r)
check("the write is action-logged", c.execute("SELECT COUNT(*) FROM agent_action_log WHERE action_type = 'sales_tax_filing'").fetchone()[0] == 20)
print(f"\n{len(F)} FAILURE(S): {F}" if F else "\nALL PASS")
sys.exit(1 if F else 0)
