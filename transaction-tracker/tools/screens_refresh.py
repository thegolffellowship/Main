"""Retake a sequence's screenshots from the code and stamp its watch_hash.

Kerry 2026-10-26: "When we make an update to anything, the screenshots are
set to update too ... that's an absolute requirement." test_screens.py
fails when a sequence's watched files change and this was not run.

    python3 tools/screens_refresh.py                 # every sequence with recipes
    python3 tools/screens_refresh.py invitations     # one sequence
    python3 tools/screens_refresh.py --hash-only X   # stamp only (no recipe can show the change)

Renders run on a throwaway database with a demo event (never production);
URL recipes load the live public pages from PUBLIC_BASE_URL (default the
Railway site); demo recipes run tools/screens_demo.py (the Tracker's own
pages on a throwaway database with made-up people, no credentials).
"""
import io, json, os, sys, tempfile, contextlib, logging
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.chdir(HERE)
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "screens-refresh")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import screens_capture as sc
    db.init_db()
sc.ALLOW_DEMO = True      # this run's database is a throwaway temp file
from email_parser.score_entry import _base_url

args = [a for a in sys.argv[1:] if not a.startswith("--")]
hash_only = "--hash-only" in sys.argv
cat_path = os.path.join(HERE, "docs/claude/screenshots/catalog.json")
cat = json.load(open(cat_path))
ids = args or [s["id"] for s in cat["sequences"] if any(st.get("capture") for st in s["steps"]) or s.get("watch")]
for sid in ids:
    seq = next((s for s in cat["sequences"] if s["id"] == sid), None)
    if not seq:
        sys.exit(f"no sequence {sid}")
    if not hash_only and any(st.get("capture") for st in seq["steps"]):
        res = sc.capture_all(lambda s: os.path.join(HERE, "docs/claude/screenshots", s["folder"]),
                             _base_url(), only=sid)
        # Demo recipes: the Tracker's own pages served from a throwaway
        # database by tools/screens_demo.py in its own process.
        dres = sc.capture_demos("", live=False, only=sid)
        res["captured"] = list(res.get("captured") or []) + list(dres.get("captured") or [])
        res["errors"] = list(res.get("errors") or []) + list(dres.get("errors") or [])
        if dres.get("error"):
            res["errors"].append({"error": f"demo runner: {dres['error']}"})
        print(sid, json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in res.items()}))
        for e in res.get("errors") or []:
            print("  error:", e)
        if res.get("error") or res.get("errors"):
            sys.exit(1)
    if seq.get("watch"):
        seq["watch_hash"] = sc.watch_hash(seq["watch"])
        print(sid, "watch_hash", seq["watch_hash"])
json.dump(cat, open(cat_path, "w"), indent=1, ensure_ascii=False)
