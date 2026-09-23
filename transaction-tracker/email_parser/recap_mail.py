"""Recap DRAFTS by email to the people who send them (v2.488.0).

Kerry 2026-09-23: "Automatically send Austin Recap drafts to Robert
Straiton. I'd also like to schedule these drafts for 9pm the night of
event." And: "Copy me on the email you send to Robert."

The closeout routine writes each chapter's recap draft under
docs/claude/recaps/ (house style: docs/claude/event-recaps.md) and
renders the Word file beside it. This module mails ONE chapter's section
of that file to its sender, as a paste-ready HTML body with the .docx
attached. It is a STAFF path, never a member path:

- every recipient must be an @thegolffellowship.com address, or be
  named in the `recap_draft_allow` app setting — a recap draft can
  never reach a member through this door;
- the file must live inside docs/claude/recaps/;
- the same file + section + recipients is sent once; a re-send needs
  `force`;
- `dry_run` (the default) renders and reports and sends nothing.

Recipients are rules-as-data: `recap_draft_to_<chapter slug>` (defaults
below), cc `recap_draft_cc` (default Kerry).
"""
from __future__ import annotations

import html as _html
import os
import re
from pathlib import Path

RECAPS_DIR = Path(__file__).resolve().parent.parent / "docs" / "claude" / "recaps"
STAFF_DOMAIN = "@thegolffellowship.com"
DEFAULT_TO = {
    "austin": "Robert@thegolffellowship.com",       # Kerry 2026-09-23
    "san_antonio": "kerry@thegolffellowship.com",
}
DEFAULT_CC = "kerry@thegolffellowship.com"            # "Copy me", 2026-09-23
BLANK_RE = re.compile(r"\[(__[^\]]*__)\]")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").strip().lower()).strip("_")


def _addrs(v) -> list:
    if not v:
        return []
    if isinstance(v, (list, tuple)):
        v = ",".join(v)
    return [a.strip() for a in str(v).split(",") if a.strip()]


def extract_section(md_text: str, section: str) -> tuple[str, str]:
    """(heading, body) of the '## <SECTION>…' block, body cut at the
    first '---' rule. Raises ValueError when the section is absent."""
    pat = re.compile(r"^## (" + re.escape(section) + r"[^\n]*)\n([\s\S]*?)(?=^## |\Z)",
                     re.M | re.I)
    m = pat.search(md_text)
    if not m:
        raise ValueError(f"section {section!r} not found")
    body = re.split(r"^---\s*$", m.group(2), maxsplit=1, flags=re.M)[0]
    return m.group(1).strip(), body


def _inline(s: str) -> str:
    s = _html.escape(s, quote=False)
    s = re.sub(r"\[([^\]]+)\]\((https?:[^)\s]+)\)",
               r'<a href="\2"><strong>\1</strong></a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = BLANK_RE.sub(lambda m: f'<strong style="background:#fff59d">[{m.group(1)}]</strong>', s)
    return s


def _is_head(line: str) -> bool:
    t = line.strip()
    return bool(re.fullmatch(r"[A-Z0-9 .&'\-]+\.", t)) and len(t) <= 40


def render_recap_html(body: str) -> tuple[str | None, str]:
    """The recap markup (the same rules as tools/recap_docx.js) as HTML.
    Returns (member subject line or None, html)."""
    out, para, bullets = [], [], []
    subject = None

    def flush():
        nonlocal para, bullets
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
            para = []
        if bullets:
            out.append("<ul>" + "".join(f"<li>{_inline(b)}</li>" for b in bullets) + "</ul>")
            bullets = []

    for raw in body.replace("\r", "").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            flush()
            continue
        if line.startswith("**Subject:**"):
            subject = re.sub(r"^\*\*Subject:\*\*\s*", "", line).strip()
            continue
        if _is_head(line):
            flush()
            out.append('<hr style="border:0;border-top:1px solid #d9d9d9">'
                       f"<p><strong>{_html.escape(line.strip())}</strong></p>")
            continue
        if re.match(r"^\s*[-•]\s+", line):
            if para:
                flush()
            bullets.append(re.sub(r"^\s*[-•]\s+", "", line))
            continue
        if bullets:
            flush()
        para.append(line.strip())
    flush()
    return subject, "\n".join(out)


def _signature_breaks(body: str) -> str:
    """Keep the signature block's line breaks: the lines after the last
    'See you…' line are joined with <br> in one paragraph."""
    lines = body.rstrip().split("\n")
    idx = max((i for i, l in enumerate(lines) if l.strip().lower().startswith("see you")),
              default=None)
    if idx is None:
        return body
    tail = [l.strip() for l in lines[idx + 1:] if l.strip()]
    if not tail:
        return body
    head = "\n".join(lines[:idx + 1])
    return head + "\n\n" + "\u2028".join(tail)


def resolve_file(file_name: str) -> Path:
    p = (RECAPS_DIR / file_name).resolve()
    if RECAPS_DIR.resolve() not in p.parents:
        raise ValueError("recap files live in docs/claude/recaps/ only")
    if not p.is_file():
        raise ValueError(f"no recap file {file_name!r} in docs/claude/recaps/")
    return p


def recipients_for(chapter_slug: str, get_setting=None) -> tuple[list, list]:
    gs = get_setting or (lambda k: None)
    to = _addrs(gs(f"recap_draft_to_{chapter_slug}") or DEFAULT_TO.get(chapter_slug) or DEFAULT_CC)
    cc = _addrs(gs("recap_draft_cc") or DEFAULT_CC)
    cc = [a for a in cc if a.lower() not in {t.lower() for t in to}]
    return to, cc


def staff_only(addrs: list, get_setting=None) -> list:
    """The addresses that are NOT allowed (empty list = all allowed)."""
    gs = get_setting or (lambda k: None)
    allow = {a.lower() for a in _addrs(gs("recap_draft_allow"))}
    return [a for a in addrs
            if not a.lower().endswith(STAFF_DOMAIN) and a.lower() not in allow]


def send_recap_draft(file_name: str, section: str, to=None, cc=None,
                     docx: str | None = None, dry_run: bool = True,
                     force: bool = False, db_path=None) -> dict:
    from email_parser import database as db

    def gs(k):
        try:
            return db.get_app_setting(k, db_path=db_path)
        except Exception:
            return None

    try:
        path = resolve_file(file_name)
        heading, body = extract_section(path.read_text(encoding="utf-8"), section)
    except ValueError as exc:
        return {"error": str(exc)}

    slug = _slug(section)
    d_to, d_cc = recipients_for(slug, gs)
    to_l = _addrs(to) or d_to
    cc_l = _addrs(cc) if cc is not None else d_cc
    cc_l = [a for a in cc_l if a.lower() not in {t.lower() for t in to_l}]
    bad = staff_only(to_l + cc_l, gs)
    if bad:
        return {"error": f"recap drafts go to TGF staff only; refused {bad} "
                         f"(add to app setting recap_draft_allow to permit)"}

    attach = None
    if docx:
        try:
            dp = resolve_file(docx)
        except ValueError as exc:
            return {"error": str(exc)}
        attach = (dp.name, dp.read_bytes(),
                  "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    member_subject, recap_html = render_recap_html(_signature_breaks(body))
    recap_html = recap_html.replace("\u2028", "<br>")
    blanks = sorted(set(BLANK_RE.findall(body)))
    title = re.sub(r"\s*\((?:DRAFT|SENT)[^)]*\)\s*$", "", heading).strip()
    cover = [f"<p>Recap draft for <strong>{_html.escape(title)}</strong>, ready to paste "
             "into Golf Genius.</p>"]
    if blanks:
        cover.append("<p>Yours to fill (highlighted below): "
                     + ", ".join(_html.escape(f"[{b}]") for b in blanks) + ".</p>")
    else:
        cover.append("<p>No blanks left to fill.</p>")
    if attach:
        cover.append(f"<p>The Word version is attached ({_html.escape(attach[0])}).</p>")
    if member_subject:
        cover.append(f"<p><strong>Subject:</strong> {_html.escape(member_subject)}</p>")
    cover.append('<hr style="border:0;border-top:2px solid #E87C3E">')
    html_body = "".join(cover) + recap_html
    subject = f"Recap draft — {title}"

    out = {"dry_run": bool(dry_run), "file": path.name, "section": heading,
           "to": to_l, "cc": cc_l, "subject": subject,
           "member_subject": member_subject, "blanks": blanks,
           "attachment": attach[0] if attach else None,
           "html_chars": len(html_body)}

    # Once per file + section + recipients unless forced.
    key = f"{path.name}|{slug}|{','.join(sorted(a.lower() for a in to_l))}"
    conn = db.get_connection(db_path)
    try:
        prior = conn.execute(
            "SELECT sent_at FROM message_log WHERE event_name = 'recap-draft' "
            "AND body_preview = ? AND status = 'sent' ORDER BY id DESC LIMIT 1",
            (key,)).fetchone()
    finally:
        conn.close()
    if prior and not force:
        out["already_sent_at"] = prior["sent_at"]
        if not dry_run:
            out["status"] = "skipped_already_sent"
            return out

    if dry_run:
        out["status"] = "dry_run"
        out["html"] = html_body
        return out

    creds = [os.getenv(k) for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID",
                                     "AZURE_CLIENT_SECRET", "EMAIL_ADDRESS")]
    if not all(creds):
        return {**out, "error": "Email credentials not configured on server"}
    from email_parser.fetcher import send_mail_graph
    ok = send_mail_graph(tenant_id=creds[0], client_id=creds[1],
                         client_secret=creds[2], from_address=creds[3],
                         to_address=",".join(to_l), subject=subject,
                         html_body=html_body,
                         cc_address=",".join(cc_l) or None,
                         attachments=[attach] if attach else None)
    status = "sent" if ok else "failed"
    try:
        db.log_message({"event_name": "recap-draft", "channel": "email",
                        "recipient_name": section,
                        "recipient_address": ",".join(to_l + cc_l),
                        "subject": subject, "body_preview": key,
                        "status": status, "sent_by": "closeout"}, db_path=db_path)
        db.log_agent_action("mcp-claude", "send_recap_draft",
                            f"{path.name} {section} → {','.join(to_l)} cc {','.join(cc_l)}: {status}")
    except Exception:
        pass
    out["status"] = status
    return out
