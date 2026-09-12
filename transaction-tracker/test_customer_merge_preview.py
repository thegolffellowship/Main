import os, sys, tempfile
os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db
tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False); tmp.close(); p = tmp.name
with db._connect(p) as conn:
    conn.executescript("""
        CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, chapter TEXT,
            current_player_status TEXT, created_at TEXT);
        CREATE TABLE customer_emails (email_id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, email TEXT);
        CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, customer TEXT);
        CREATE TABLE tgf_payouts (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER);
        INSERT INTO customers VALUES (818,'Geoff','Hightower','Austin','guest',NULL),(823,'Geoffery','Hightower',NULL,NULL,NULL);
        INSERT INTO items (customer_id, customer) VALUES (818,'Geoff Hightower');
        INSERT INTO tgf_payouts (customer_id) VALUES (823);
    """); conn.commit()
pv = db.customer_merge_preview(823, 818, db_path=p)
ok = pv["ok"] and pv["source"]["name"] == "Geoffery Hightower" and pv["target"]["items"] == 1 \
     and pv["source_refs"].get("tgf_payouts.customer_id") == 1
print("  PASS  preview names both profiles and the refs to move" if ok else f"  FAIL  {pv}")
bad = db.customer_merge_preview(823, 823, db_path=p)
print("  PASS  same id refused" if not bad["ok"] else "  FAIL")
print("ALL PASSED" if ok and not bad["ok"] else "FAILED"); sys.exit(0 if ok and not bad["ok"] else 1)
