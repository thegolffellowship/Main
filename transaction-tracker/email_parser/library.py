"""THE TGF LIBRARY (Kerry 2026-09-30 #1099; storage option A, Kerry "Ok yes"
#1117; spec librarian-claude #1114; table migration 0008, db-claude #1124).

Governing documents live as APPEND-ONLY rows in `library_documents`. A row
is never deleted or edited in place: a supersede inserts the new version
and marks the old one `status='superseded'` + `superseded_by_id`, the only
UPDATE this module issues. The Librarian exports rows to `docs/library/`
once a day, so the repo is the readable third copy.

PORTABLE (spec §6, Horizon Open Queue B6): no TGF imports at module level.
Everything site-specific comes in through `LibraryConfig`: the connection
factory, the Kerry-OK check, the lane list, the guarded sections, the
backfill directive post, the repo root and the action logger. `tgf_config()`
builds the Tracker's.

Production does not enforce foreign keys (foreign_keys = 0, #1124-f), so
every reference (section, supersedes target, readers) is checked here.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

FILENAME_RE = re.compile(r"^[A-Za-z0-9_\-]+_v(\d+)_(\d+)\.md$")
STATUSES = ("draft", "proposed", "ratified", "living", "superseded")
REQUIRED_META = ("doc_id", "title", "version", "status", "owner", "onedrive_path",
                 "project_files", "reads")
MAX_BODY = 1_000_000
# Spec §1: a body that looks like it carries a credential is refused.
CREDENTIAL_RES = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"\bpassword\s*=", re.I),
    re.compile(r"\bapi_key\s*=", re.I),
)


@dataclass
class LibraryConfig:
    connect: Callable                       # () -> context manager yielding a DB-API connection
    kerry_ok: Callable                      # (conn, post_id) -> (ok: bool, why: str)
    lanes: tuple                            # authors allowed to file; also valid `reads` names
    guarded_sections: tuple = ("standards",)
    backfill_post: int | None = None        # the directive a FIRST filing of a ratified standard may cite
    repo_root: Path | None = None           # docs/library/ lives under it
    log: Callable | None = None             # (author, action_type, description) -> None


def tgf_config(db_path=None) -> LibraryConfig:
    from email_parser import database as db
    from email_parser.customer_query import _kerry_ok
    return LibraryConfig(
        connect=lambda: db._connect(db_path),
        kerry_ok=_kerry_ok,
        lanes=("kerry", "platform-claude", "front-desk", "librarian-claude", "tracker-claude",
               "db-claude", "design-claude", "tracker-build", "track-a", "track-b",
               "side-games", "cfo", "health", "closeout", "cmo"),
        guarded_sections=("standards",),
        backfill_post=1099,                 # Kerry's backfill directive (#1114 §1 a)
        repo_root=Path(__file__).resolve().parent.parent,
        log=lambda a, t, d: db.log_agent_action(a, t, d, db_path=db_path),
    )


def _sha(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _parse_version(v) -> tuple[int, int] | None:
    m = re.fullmatch(r"v?(\d+)[._](\d+)", str(v or "").strip().lower())
    return (int(m.group(1)), int(m.group(2))) if m else None


def _parse_path(path: str):
    """'<section>/<file>' or 'context/<lane>/<file>' -> (section, lane, filename)."""
    parts = [p for p in (path or "").strip().strip("/").split("/") if p]
    if len(parts) == 2:
        return parts[0].lower(), None, parts[1]
    if len(parts) == 3 and parts[0].lower() == "context":
        return "context", parts[1].lower(), parts[2]
    return None, None, None


def _live_row(conn, doc_id: str):
    return conn.execute(
        """SELECT * FROM library_documents
           WHERE lower(doc_id) = lower(?) AND status <> 'superseded'
           ORDER BY version_major DESC, version_minor DESC LIMIT 1""", (doc_id,)).fetchone()


def _row_dict(r) -> dict:
    return {k: r[k] for k in r.keys()}


def library_put(path: str, content: str, meta: dict, supersedes: str = "", author: str = "",
                kerry_ok_post=0, apply: bool = False, cfg: LibraryConfig | None = None) -> dict:
    """File one document version (spec #1114 §1). Dry run unless apply.
    Refusals come back as {"refused": ..., ...}; nothing is written then."""
    cfg = cfg or tgf_config()
    meta = dict(meta or {})
    author = (author or "").strip().lower()
    if author not in cfg.lanes:
        return {"refused": f"author {author!r} is not a known lane", "lanes": list(cfg.lanes)}
    section, lane, filename = _parse_path(path)
    if not section:
        return {"refused": "path must be <section>/<filename> or context/<lane>/<filename>"}
    if section == "archive":
        return {"refused": "archive/ is never written directly; a supersede moves the old version there"}
    if section == "context" and not lane:
        return {"refused": "context/ needs a lane folder: context/<lane>/<filename>"}
    fm = FILENAME_RE.match(filename or "")
    if not fm:
        return {"refused": f"filename {filename!r} must match <Name>_v<major>_<minor>.md"}
    missing = [k for k in REQUIRED_META if meta.get(k) in (None, "")]
    if missing:
        return {"refused": "front-matter fields missing", "missing": missing}
    ver = _parse_version(meta.get("version"))
    if not ver:
        return {"refused": f"meta.version {meta.get('version')!r} must look like 1.0"}
    if ver != (int(fm.group(1)), int(fm.group(2))):
        return {"refused": f"filename version v{fm.group(1)}_{fm.group(2)} differs from meta.version {meta['version']}"}
    status = str(meta.get("status")).strip().lower()
    if status not in STATUSES or status == "superseded":
        return {"refused": f"status must be one of {', '.join(s for s in STATUSES if s != 'superseded')}"}
    if status == "ratified" and not (meta.get("ratified_by") and meta.get("ratified_date")):
        return {"refused": "status=ratified needs ratified_by and ratified_date"}
    if str(meta.get("project_files")).strip().lower() not in ("0", "1", "true", "false", "yes", "no"):
        return {"refused": "project_files must be true/false"}
    project_files = 1 if str(meta.get("project_files")).strip().lower() in ("1", "true", "yes") else 0
    reads = meta.get("reads")
    reads = [reads] if isinstance(reads, str) else list(reads or [])
    reads = sorted({str(r).strip().lower() for r in reads if str(r).strip()})
    bad_readers = [r for r in reads if r not in cfg.lanes and not r.startswith("skill:")]
    if bad_readers:
        return {"refused": "unknown readers (a lane name, or skill:<name>)", "unknown": bad_readers,
                "lanes": list(cfg.lanes)}
    body = content if isinstance(content, str) else ""
    if not body.strip():
        return {"refused": "content is empty"}
    if len(body.encode("utf-8")) > MAX_BODY:
        return {"refused": "content is over 1 MB"}
    hits = [r.pattern for r in CREDENTIAL_RES if r.search(body)]
    if hits:
        return {"refused": "content looks like it carries a credential; remove it first", "patterns": hits}
    sha = _sha(body)
    doc_id = str(meta["doc_id"]).strip()

    with cfg.connect() as conn:
        if not conn.execute("SELECT 1 FROM library_sections WHERE code = ?", (section,)).fetchone():
            return {"refused": f"unknown section {section!r}",
                    "sections": [r[0] for r in conn.execute("SELECT code FROM library_sections ORDER BY code")]}
        same = conn.execute(
            """SELECT id, body_sha256 FROM library_documents WHERE lower(doc_id) = lower(?)
               AND version_major = ? AND version_minor = ?""", (doc_id, ver[0], ver[1])).fetchone()
        if same:
            return {"refused": f"{doc_id} v{ver[0]}.{ver[1]} is already filed (never overwritten)",
                    "existing_id": same[0], "same_body": same[1] == sha, "sha": same[1][:8]}
        live = _live_row(conn, doc_id)
        prev = None
        if supersedes:
            s_doc, _, s_ver = supersedes.partition("@")
            s_v = _parse_version(s_ver)
            if not s_v or s_doc.strip().lower() != doc_id.lower():
                return {"refused": "supersedes must name this document's live version as <doc_id>@<major>.<minor>"}
            if not live or (live["version_major"], live["version_minor"]) != s_v:
                cur = f"{live['version_major']}.{live['version_minor']}" if live else "none"
                return {"refused": f"supersedes {supersedes} is not the live version (live: {cur})"}
            if ver <= s_v:
                return {"refused": f"the new version {ver[0]}.{ver[1]} must be higher than {s_v[0]}.{s_v[1]}"}
            prev = live
        elif live:
            return {"refused": f"{doc_id} already has a live version {live['version_major']}.{live['version_minor']}; "
                               f"pass supersedes='{doc_id}@{live['version_major']}.{live['version_minor']}'"}
        authority = None
        if section in cfg.guarded_sections:
            if not kerry_ok_post:
                return {"refused": f"{section}/ needs kerry_ok_post: a mailbox post carrying Kerry's word"}
            try:
                post = int(kerry_ok_post)
            except (TypeError, ValueError):
                return {"refused": "kerry_ok_post must be a mailbox post id"}
            if prev is not None and cfg.backfill_post and post == cfg.backfill_post:
                return {"refused": f"a supersede under {section}/ may not cite the backfill directive "
                                   f"#{cfg.backfill_post}; it needs a post that names this document"}
            ok, why = cfg.kerry_ok(conn, post)
            if not ok:
                return {"refused": f"rule 3b: {why}"}
            authority = why
        row = {"doc_id": doc_id, "section": section, "lane": lane, "filename": filename,
               "version_major": ver[0], "version_minor": ver[1], "title": str(meta["title"]).strip(),
               "status": status, "owner": str(meta["owner"]).strip().lower(),
               "ratified_by": meta.get("ratified_by") or None, "ratified_date": meta.get("ratified_date") or None,
               "authority_post": int(kerry_ok_post) if kerry_ok_post else (meta.get("authority_post") or None),
               "onedrive_path": str(meta["onedrive_path"]).strip(), "project_files": project_files,
               "body_sha256": sha, "supersedes_id": prev["id"] if prev is not None else None,
               "filed_by": author}
        out = {"dry_run": not apply, "path": f"{section}/{lane + '/' if lane else ''}{filename}",
               "row": row, "reads": reads, "chars": len(body), "sha": sha[:8],
               "authority": authority,
               "archive_move": (f"{doc_id} v{prev['version_major']}.{prev['version_minor']} -> superseded"
                                if prev is not None else None)}
        if not apply:
            return out
        cols = list(row) + ["body"]
        new_id = conn.execute(
            f"INSERT INTO library_documents ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) RETURNING id",
            [row[c] for c in row] + [body]).fetchone()[0]
        for r in reads:
            conn.execute("INSERT INTO library_document_reads (document_id, reader) VALUES (?, ?)", (new_id, r))
        if prev is not None:
            conn.execute("UPDATE library_documents SET status = 'superseded', superseded_by_id = ? WHERE id = ?",
                         (new_id, prev["id"]))
        conn.commit()
        out["id"] = new_id
    if cfg.log:
        try:
            cfg.log(author, "library_put",
                    f"{out['path']} v{ver[0]}.{ver[1]} sha={sha[:8]} supersedes="
                    f"{supersedes or '-'} authority={authority or '-'}")
        except Exception:
            pass
    return out


def _repo_copy(cfg: LibraryConfig, row) -> str | None:
    """The exported copy under docs/library/ (live) or docs/library/archive/."""
    if not cfg.repo_root:
        return None
    rel = Path(row["section"]) / (row["lane"] or "") / row["filename"]
    for base in (Path("docs/library"), Path("docs/library/archive")):
        f = cfg.repo_root / base / rel
        if f.is_file():
            return f.read_text(encoding="utf-8")
    return None


def _section(text: str, want: str) -> str | None:
    """The heading slice: the first heading containing `want` through the
    next heading of the same or higher level (same rule as cos_reads)."""
    want = want.strip().lower()
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m and want in m.group(2).lower():
            level = len(m.group(1))
            out = [line]
            for nxt in lines[i + 1:]:
                n = re.match(r"^(#{1,6})\s", nxt)
                if n and len(n.group(1)) <= level:
                    break
                out.append(nxt)
            return "\n".join(out)
    return None


def library_get(name: str, version: str = "", section: str = "",
                cfg: LibraryConfig | None = None) -> dict:
    """Read one document (spec #1114 §2): latest live version by default."""
    cfg = cfg or tgf_config()
    key = (name or "").strip().strip("/")
    if not key:
        return {"error": "name is required (a doc_id, filename or path)"}
    key = key.rsplit("/", 1)[-1]
    fm = FILENAME_RE.match(key)
    want = _parse_version(version) if version else (
        (int(fm.group(1)), int(fm.group(2))) if fm else None)
    base = re.sub(r"_v\d+_\d+\.md$", "", key, flags=re.I).removesuffix(".md")
    with cfg.connect() as conn:
        q = """SELECT * FROM library_documents
               WHERE (lower(doc_id) = lower(?) OR lower(filename) = lower(?)
                      OR lower(filename) LIKE lower(?) || '\\_v%' ESCAPE '\\')"""
        args = [base, key, base]
        if want:
            q += " AND version_major = ? AND version_minor = ?"
            args += [want[0], want[1]]
        else:
            q += " AND status <> 'superseded'"
        q += " ORDER BY version_major DESC, version_minor DESC LIMIT 1"
        r = conn.execute(q, args).fetchone()
        if not r:
            return {"error": f"no document {name!r}" + (f" v{want[0]}.{want[1]}" if want else "")}
        reads = [x[0] for x in conn.execute(
            "SELECT reader FROM library_document_reads WHERE document_id = ? ORDER BY reader", (r["id"],))]
    d = _row_dict(r)
    body = d.pop("body")
    out = {"meta": d | {"version": f"{d['version_major']}.{d['version_minor']}", "reads": reads},
           "source": "table"}
    repo = _repo_copy(cfg, r)
    if repo is not None and _sha(repo) != d["body_sha256"]:
        out["drift"] = True
    if section:
        part = _section(body, section)
        if part is None:
            out["error"] = f"no heading matching {section!r}"
            return out
        body = part
    out["body"] = body
    out["chars"] = len(body)
    return out


def library_list(section: str = "", status: str = "", include_archive: bool = False,
                 cfg: LibraryConfig | None = None) -> dict:
    """The INDEX rows (spec #1114 §3): every live version, newest filing
    first within a section. include_archive adds the superseded ones."""
    cfg = cfg or tgf_config()
    q = """SELECT id, doc_id, section, lane, filename, version_major, version_minor, title, status,
                  owner, ratified_by, ratified_date, onedrive_path, project_files, supersedes_id,
                  superseded_by_id, filed_by, filed_at
           FROM library_documents WHERE 1 = 1"""
    args = []
    if section:
        q += " AND lower(section) = lower(?)"
        args.append(section.strip())
    if status:
        q += " AND lower(status) = lower(?)"
        args.append(status.strip())
    elif not include_archive:
        q += " AND status <> 'superseded'"
    q += " ORDER BY section, lower(doc_id), version_major DESC, version_minor DESC"
    with cfg.connect() as conn:
        rows = [_row_dict(r) for r in conn.execute(q, args).fetchall()]
        reads = {}
        for r in conn.execute("SELECT document_id, reader FROM library_document_reads ORDER BY reader"):
            reads.setdefault(r[0], []).append(r[1])
        sup = {r[0]: f"{r[1]}@{r[2]}.{r[3]}" for r in conn.execute(
            "SELECT id, doc_id, version_major, version_minor FROM library_documents")}
    for r in rows:
        r["version"] = f"{r.pop('version_major')}.{r.pop('version_minor')}"
        r["reads"] = reads.get(r["id"], [])
        r["supersedes"] = sup.get(r.pop("supersedes_id"))
        r["project_files"] = bool(r["project_files"])
    counts = {}
    for r in rows:
        counts[r["section"]] = counts.get(r["section"], 0) + 1
    return {"count": len(rows), "by_section": counts, "documents": rows,
            "include_archive": bool(include_archive or status == "superseded")}


def library_search(text: str, section: str = "", include_archive: bool = False,
                   limit: int = 20, max_chars: int = 600, cfg: LibraryConfig | None = None) -> dict:
    """Every word of `text` must appear in the title or body (lower() both
    sides), newest filing first, with a snippet around the first hit
    (spec #1114 §4; the same all-words rule as search_platform_dialogue)."""
    cfg = cfg or tgf_config()
    words = [w for w in re.split(r"\s+", (text or "").strip()) if w]
    if not words:
        return {"error": "text is required"}
    limit = max(1, min(int(limit or 20), 100))
    max_chars = max(80, min(int(max_chars or 600), 5000))
    q = "SELECT * FROM library_documents WHERE 1 = 1"
    args = []
    for w in words:
        q += " AND instr(lower(title || ' ' || body), lower(?)) > 0"
        args.append(w)
    if section:
        q += " AND lower(section) = lower(?)"
        args.append(section.strip())
    if not include_archive:
        q += " AND status <> 'superseded'"
    q += " ORDER BY filed_at DESC, id DESC LIMIT ?"
    args.append(limit)
    with cfg.connect() as conn:
        rows = conn.execute(q, args).fetchall()
    hits = []
    for r in rows:
        body = r["body"]
        at = body.lower().find(words[0].lower())
        start = max(0, at - max_chars // 3) if at >= 0 else 0
        snip = body[start:start + max_chars]
        hits.append({"doc_id": r["doc_id"], "version": f"{r['version_major']}.{r['version_minor']}",
                     "section": r["section"], "title": r["title"], "status": r["status"],
                     "filed_at": r["filed_at"],
                     "snippet": ("…" if start else "") + snip + ("…" if start + max_chars < len(body) else "")})
    return {"text": text, "count": len(hits), "results": hits}
