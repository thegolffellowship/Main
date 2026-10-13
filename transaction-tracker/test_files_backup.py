"""Files behind the database go off-site (CoS #1604): player photos and card
photos live as files beside the DB, which Litestream cannot replicate.
backups.run_files_backup archives them as one tar.gz to OneDrive (Graph),
once per CHANGE. The network is stubbed; archive, read-back, change
detection, retention and the digest's finding are real."""
import os, sys, tarfile, tempfile, logging, hashlib

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
root = tempfile.mkdtemp(prefix="tgf-files-")
live = os.path.join(root, "transactions.db")
os.environ["DATABASE_PATH"] = live
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ["PERF_SAMPLES"] = "0"
logging.disable(logging.CRITICAL)
F = []
def check(label, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + label + ("" if ok else f"  {str(detail)[:500]}"))
    if not ok: F.append(label)

from email_parser import backups as bk, database as db, health
db.init_db(live) if hasattr(db, "init_db") else None

print("== nothing to back up yet ==")
r = bk.run_files_backup(live, dry_run=True)
check("no files -> ok, skipped, nothing built", r["ok"] and "no files" in r.get("skipped", "") and r["files"] == 0, r)
check("status with no files is in sync", bk.files_backup_status(live)["in_sync"] is True)

print("\n== the manifest sees both stores ==")
os.makedirs(os.path.join(root, "player_photos")); os.makedirs(os.path.join(root, "se_photos", "g12"))
open(os.path.join(root, "player_photos", "h-42.jpg"), "wb").write(b"\xff\xd8headshot")
open(os.path.join(root, "player_photos", "t-42-77.jpg"), "wb").write(b"\xff\xd8team")
open(os.path.join(root, "se_photos", "g12", "card.jpg"), "wb").write(b"\xff\xd8card")
m = bk.file_store_manifest(live)
check("3 files over two stores, one hash", m["files"] == 3 and m["stores"]["player_photos"]["files"] == 2 and m["stores"]["se_photos"]["files"] == 1 and len(m["hash"]) == 32, m["stores"])
check("a store that does not exist is reported, not an error", bk.file_store_manifest(os.path.join(root, "x", "t.db"))["stores"]["player_photos"]["exists"] is False)

print("\n== the archive is built and read back ==")
dst = os.path.join(root, "out.tar.gz")
a = bk.build_files_archive(dst, live)
with tarfile.open(dst) as t:
    names = sorted(x.name for x in t.getmembers())
check("archive holds the volume-relative paths", names == ["player_photos/h-42.jpg", "player_photos/t-42-77.jpg", "se_photos/g12/card.jpg"], names)
check("archive carries the bytes (restore = extract into the volume)", tarfile.open(dst).extractfile("player_photos/h-42.jpg").read() == b"\xff\xd8headshot")

print("\n== upload only on change, retention, failure ==")
up, deleted, remote = [], [], []
bk._graph_creds = lambda: {"user": "u@x"}; bk._token = lambda c: "tok"; bk._ensure_folder = lambda *a: True
def _up(token, user, folder, name, path): up.append((folder, name)); remote.append(name)
bk._upload = _up
bk.list_remote_file_backups = lambda *a: [{"name": n} for n in remote]
bk._delete_remote = lambda token, user, folder, name: (deleted.append(name), remote.remove(name))[0] is None or True
r = bk.run_files_backup(live)
check("first run uploads into <folder>/files", r["ok"] and r["uploaded"] and up[0][0].endswith("/files") and up[0][1].startswith("trackerfiles_"), (r, up))
check("status: now in sync", bk.files_backup_status(live)["in_sync"] is True)
r = bk.run_files_backup(live)
check("unchanged content uploads nothing", r["ok"] and r.get("skipped") and len(up) == 1, (r, up))
open(os.path.join(root, "player_photos", "h-99.jpg"), "wb").write(b"\xff\xd8new")
check("a new photo makes the status out of sync until the next run", bk.files_backup_status(live)["in_sync"] is False)
r = bk.run_files_backup(live)
check("changed content uploads again", r["uploaded"] and len(up) == 2, r)
for i in range(10):
    open(os.path.join(root, "player_photos", f"h-{200+i}.jpg"), "wb").write(b"\xff\xd8x%d" % i)
    import time; time.sleep(1.01)
    bk.run_files_backup(live)
check("retention keeps the newest %d" % bk.KEEP_FILES_BACKUPS, len(remote) == bk.KEEP_FILES_BACKUPS and len(deleted) >= 4, (len(remote), len(deleted)))
def _boom(*a): raise RuntimeError("graph 503")
bk._upload = _boom
open(os.path.join(root, "player_photos", "h-300.jpg"), "wb").write(b"\xff\xd8y")
r = bk.run_files_backup(live)
check("an upload failure is reported, never raised, and the hash is NOT advanced", r["ok"] is False and "503" in r["error"] and bk.files_backup_status(live)["in_sync"] is False, r)

print("\n== the digest names it only when the scheduled run finds it out of sync ==")
rep = health.build_health_report(1, db_path=live, record_size=True)
f = [x for x in rep["findings"] if x["key"] == "files_backup_stale"]
check("scheduled digest + out of sync -> MEDIUM files_backup_stale", len(f) == 1 and f[0]["severity"] == "medium", rep["findings"])
check("...and the markdown carries a FILES BACKUP line", "**FILES BACKUP**" in health.render_markdown(rep))
rep2 = health.build_health_report(1, db_path=live)
check("an on-demand read does not raise it (the backup may simply not have run yet)", not [x for x in rep2["findings"] if x["key"] == "files_backup_stale"])
print(); print("ALL PASS" if not F else f"FAILED ({len(F)}): {F}"); sys.exit(1 if F else 0)
