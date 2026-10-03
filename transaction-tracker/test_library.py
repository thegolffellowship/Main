"""THE TGF LIBRARY (spec librarian-claude #1114, table 0008 db-claude #1124,
Kerry "Ok yes" #1117). Run: python3 test_library.py

Refusals, never-overwrite, supersede, the standards/ guard both ways, the
credential scan, the in-code reference checks (#1124-f: FKs are not
enforced on production), drift between the table and the repo copy."""
import contextlib
import io
import logging
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="tgf-lib-"))
os.environ["DATABASE_PATH"] = str(tmp / "t.db")
logging.disable(logging.CRITICAL)
from email_parser import database as db
from email_parser import library as L
from email_parser.migrations import apply_migrations

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


DB = str(tmp / "t.db")
with contextlib.redirect_stdout(io.StringIO()):
    db.init_db(DB)
with db._connect(DB) as c:
    apply_migrations(c)
    c.execute("INSERT INTO platform_dialogue (id, author, topic, body) VALUES (1099, 'platform-claude', 'library', "
              "'KERRY DIRECTIVE. Verbatim: Kerry \"I want that up immediately\"')")
    c.execute("INSERT INTO platform_dialogue (id, author, topic, body) VALUES (2001, 'kerry', 'library', "
              "'Handicap Standard v1.1 is approved.')")
    c.execute("INSERT INTO platform_dialogue (id, author, topic, body) VALUES (2002, 'tracker-claude', 'library', "
              "'I think Kerry would like this.')")
    c.commit()

LOGS = []
cfg = L.tgf_config(DB)
cfg.repo_root = tmp
cfg.log = lambda a, t, d: LOGS.append((a, t, d))

META = {"doc_id": "TGF_Handicap_Standard", "title": "TGF Handicap Standard", "version": "1.0",
        "status": "ratified", "ratified_by": "Kerry", "ratified_date": "2026-09-15",
        "owner": "platform-claude", "onedrive_path": "01_STANDARDS/TGF_Handicap_Standard_v1_0.md",
        "project_files": True, "reads": ["tracker-claude", "skill:event-closeout"]}
BODY = "# Handicap Standard\n\n## 1. Index\nThe index is the TGF index.\n\n## 2. Intro rule\n75% of the current index.\n"
P10 = "standards/TGF_Handicap_Standard_v1_0.md"


def put(**kw):
    a = dict(path=P10, content=BODY, meta=META, author="platform-claude", kerry_ok_post=1099, cfg=cfg)
    a.update(kw)
    return L.library_put(**a)


def count():
    with db._connect(DB) as c:
        return c.execute("SELECT COUNT(*) FROM library_documents").fetchone()[0]


print("== migration 0008 ==")
with db._connect(DB) as c:
    secs = [r[0] for r in c.execute("SELECT code FROM library_sections ORDER BY code")]
check("six sections seeded", secs == ["audits", "context", "decisions", "specs", "standards", "strategy"], str(secs))

print("== refusals ==")
check("unknown author", "refused" in put(author="somebody"))
check("bad path", "refused" in put(path="TGF_Handicap_Standard_v1_0.md"))
check("archive/ is never written directly", "archive" in put(path="archive/TGF_Handicap_Standard_v1_0.md").get("refused", ""))
check("context/ needs a lane", "refused" in put(path="context/TGF_X_v1_0.md"))
check("filename pattern", "refused" in put(path="standards/handicap.md"))
check("filename version must equal meta.version", "differs" in put(meta=META | {"version": "1.1"}).get("refused", ""))
r = put(meta={k: v for k, v in META.items() if k not in ("owner", "reads")})
check("missing front-matter listed", sorted(r.get("missing", [])) == ["owner", "reads"], str(r))
check("ratified needs ratified_by/date", "ratified_by" in put(meta=META | {"ratified_by": ""}).get("refused", ""))
check("status cannot be filed as superseded", "refused" in put(meta=META | {"status": "superseded"}))
check("unknown section (in code: FKs are not enforced)", "unknown section" in put(path="recipes/TGF_X_v1_0.md", meta=META | {"doc_id": "TGF_X"}).get("refused", ""))
check("unknown reader refused", put(meta=META | {"reads": ["nobody"]}).get("unknown") == ["nobody"])
check("empty body", "empty" in put(content="   ").get("refused", ""))
check("over 1 MB", "1 MB" in put(content="x" * 1_000_001).get("refused", ""))
for cred in ("-----BEGIN RSA PRIVATE KEY-----", "token sk-abcdefghijklmnopqrstuv", "ghp_abcdefghijklmnopqrstuvwx",
             "xoxb-1234567890-abc", "password = hunter2", "API_KEY=abc"):
    check(f"credential scan: {cred[:18]}", "credential" in put(content=BODY + cred).get("refused", ""))

print("== the standards/ guard ==")
check("standards/ without kerry_ok_post", "kerry_ok_post" in put(kerry_ok_post=0).get("refused", ""))
check("standards/ citing a post that does not carry Kerry's word", "3b" in put(kerry_ok_post=2002).get("refused", ""))
check("nothing written by any refusal", count() == 0)

print("== first filing ==")
r = put()
check("dry run by default: nothing written, the row shown", r.get("dry_run") is True and count() == 0 and r["row"]["section"] == "standards", str(r)[:200])
check("first filing of a ratified standard may cite the backfill directive #1099", r.get("authority", "").startswith("#1099"))
r = put(apply=True)
check("apply writes one row + its readers", count() == 1 and r.get("id"), str(r)[:200])
with db._connect(DB) as c:
    rd = [x[0] for x in c.execute("SELECT reader FROM library_document_reads WHERE document_id = ?", (r["id"],))]
check("readers stored", rd == ["skill:event-closeout", "tracker-claude"], str(rd))
check("action logged with path, version, sha, authority",
      LOGS and LOGS[-1][1] == "library_put" and "v1.0" in LOGS[-1][2] and "#1099" in LOGS[-1][2], str(LOGS[-1:]))

print("== never overwrites ==")
r = put(apply=True)
check("the same version again is refused, same body visible", "never overwritten" in r.get("refused", "") and r.get("same_body") is True, str(r))
r = put(content=BODY + "changed", apply=True)
check("…and a different body says so", r.get("same_body") is False)
r = put(path="standards/TGF_Handicap_Standard_v1_1.md", meta=META | {"version": "1.1"}, apply=True)
check("a new version without supersedes is a version conflict", "supersedes=" in r.get("refused", ""), str(r))
check("still one row", count() == 1)

print("== supersede ==")
P11 = "standards/TGF_Handicap_Standard_v1_1.md"
M11 = META | {"version": "1.1"}
r = put(path=P11, meta=M11, supersedes="TGF_Handicap_Standard@1.0", kerry_ok_post=1099)
check("a supersede under standards/ may NOT cite #1099", "#1099" in r.get("refused", ""), str(r))
r = put(path=P11, meta=M11, supersedes="TGF_Handicap_Standard@0.9", kerry_ok_post=2001)
check("supersedes must name the live version", "not the live version" in r.get("refused", ""), str(r))
r = put(path="standards/TGF_Handicap_Standard_v0_9.md", meta=META | {"version": "0.9"},
        supersedes="TGF_Handicap_Standard@1.0", kerry_ok_post=2001)
check("the new version must be higher", "higher" in r.get("refused", ""), str(r))
r = put(path=P11, meta=M11, content=BODY + "\n## 3. New\nAdded.\n", supersedes="TGF_Handicap_Standard@1.0",
        kerry_ok_post=2001, apply=True)
check("supersede with Kerry's own post applies", r.get("id") and r.get("archive_move", "").endswith("superseded"), str(r))
with db._connect(DB) as c:
    old = c.execute("SELECT status, superseded_by_id, body FROM library_documents WHERE version_minor = 0").fetchone()
check("the old row: status superseded, pointed at the new one, body untouched",
      old["status"] == "superseded" and old["superseded_by_id"] == r["id"] and old["body"] == BODY)
check("two rows, none deleted", count() == 2)

print("== other sections ==")
r = L.library_put("context/front-desk/FD_Session_Summary_v1_0.md", "# FD\nnotes\n",
                  {"doc_id": "FD_Session_Summary", "title": "FD summary", "version": "1.0", "status": "living",
                   "owner": "front-desk", "onedrive_path": "06_STRATEGY/Session_Summaries/x.md",
                   "project_files": False, "reads": "front-desk"},
                  author="front-desk", apply=True, cfg=cfg)
check("context/<lane>/ needs no Kerry post and stores the lane", r.get("id") and r["row"]["lane"] == "front-desk", str(r))

print("== library_get ==")
g = L.library_get("TGF_Handicap_Standard", cfg=cfg)
check("latest live by default (1.1)", g.get("meta", {}).get("version") == "1.1" and "## 3. New" in g["body"], str(g)[:200])
g = L.library_get("tgf_handicap_standard", version="v1_0", cfg=cfg)
check("a superseded version by number, case-insensitive", g["meta"]["version"] == "1.0" and g["meta"]["status"] == "superseded")
g = L.library_get("TGF_Handicap_Standard_v1_0.md", cfg=cfg)
check("by filename", g["meta"]["version"] == "1.0")
g = L.library_get("standards/TGF_Handicap_Standard_v1_1.md", section="intro rule", cfg=cfg)
check("section slice", g["body"].startswith("## 2. Intro rule") and "## 3" not in g["body"], g.get("body"))
check("source + readers", g["source"] == "table" and g["meta"]["reads"] == ["skill:event-closeout", "tracker-claude"])
check("no drift without a repo copy", "drift" not in g)
f = tmp / "docs/library/standards/TGF_Handicap_Standard_v1_1.md"
f.parent.mkdir(parents=True, exist_ok=True)
f.write_text("an edited copy", encoding="utf-8")
check("drift: the repo copy differs, the table is served", L.library_get("TGF_Handicap_Standard", cfg=cfg).get("drift") is True)
check("unknown name", "error" in L.library_get("Nope", cfg=cfg))

print("== bridges ==")
import json
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import mcp_server
g = json.loads(mcp_server._scoring_dispatch("", "scoring-library-get:TGF_Handicap_Standard|1.0|index"))
check("scoring-library-get:<name>|<version>|<heading>", g.get("meta", {}).get("version") == "1.0"
      and g.get("body", "").startswith("## 1. Index"), str(g)[:200])
r = json.loads(mcp_server._scoring_dispatch("", "scoring-library-put:" + json.dumps(
    {"path": "specs/TGF_Library_Spec_v0_1.md", "content": "# spec\n", "author": "librarian-claude",
     "meta": {"doc_id": "TGF_Library_Spec", "title": "Library spec", "version": "0.1", "status": "proposed",
              "owner": "librarian-claude", "onedrive_path": "07_TECHNOLOGY/Specs/x.md",
              "project_files": False, "reads": ["tracker-claude"]}})))
check("scoring-library-put is a dry run unless apply", r.get("dry_run") is True and count() == 3, str(r)[:200])
check("scoring-library-put bad JSON", "error" in json.loads(mcp_server._scoring_dispatch("", "scoring-library-put:{nope")))

print()
if F:
    print(f"{len(F)} FAILED")
    sys.exit(1)
print("ALL PASS")
