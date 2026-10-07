"""MAIL TO KERRY through the Tracker's own Graph mailer (Kerry 2026-09-30,
#1050: "Go with the Tracker mailer. I believe that's standard now for our
other emails, and should be standard when I request that moving forward.").

Any lane that emails Kerry (the sales-tax obligation routine, the monthly
snapshot, reports) sends here, never through a Claude connector (the
Microsoft 365 connector is read-only: no Mail.Send).

- The recipient is HARD-WIRED: KERRY. No argument, setting or caller can
  change it, so this path can never reach a member.
- DRY RUN by default: render and report, send nothing.
- The boundary guard holds a message with a leftover `{tag}` or a
  `[BRACKETED BLANK]`, the same rule every Tracker send path keeps.
- Every send is written to message_log and agent_action_log.
"""
from __future__ import annotations

import os
import re

KERRY = "kerry@thegolffellowship.com"
_TAG_RE = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")
_BLANK_RE = re.compile(r"\[[A-Z][A-Z0-9 _/\-]*\]")
MAX_HTML = 400_000


def mail_kerry(subject: str, html: str, send: bool = False, sent_by: str = "mcp-claude",
               db_path=None) -> dict:
    from email_parser import database as db
    from email_parser.fetcher import normalize_email_html
    subject = (subject or "").strip()
    html = html or ""
    out = {"to": KERRY, "subject": subject, "dry_run": not send, "html_chars": len(html)}
    problems = []
    if not subject:
        problems.append("empty subject")
    if not html.strip():
        problems.append("empty body")
    if len(html) > MAX_HTML:
        problems.append(f"body over {MAX_HTML} characters")
    left = sorted(set(_TAG_RE.findall(subject + html)) | set(_BLANK_RE.findall(subject + html)))
    if left:
        problems.append("unfilled blanks: " + ", ".join(left))
    body = normalize_email_html(html) if html.strip() else ""
    if problems:
        return {**out, "status": "held", "problems": problems}
    if not send:
        return {**out, "status": "dry_run", "html": body}
    creds = [os.getenv(k) for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID",
                                     "AZURE_CLIENT_SECRET", "EMAIL_ADDRESS")]
    if not all(creds):
        return {**out, "status": "failed", "error": "Email credentials not configured on server"}
    from email_parser.fetcher import send_mail_graph
    ok = False
    try:
        ok = send_mail_graph(tenant_id=creds[0], client_id=creds[1], client_secret=creds[2],
                             from_address=creds[3], to_address=KERRY, subject=subject,
                             html_body=body)
    except Exception as exc:                       # noqa: BLE001 — reported, not raised
        out["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    status = "sent" if ok else "failed"
    try:
        db.log_message({"event_name": "mail-kerry", "channel": "email",
                        "recipient_name": "Kerry Niester", "recipient_address": KERRY,
                        "subject": subject, "body_preview": re.sub(r"<[^>]+>", " ", body)[:200],
                        "status": status, "sent_by": sent_by}, db_path=db_path)
        db.log_agent_action(sent_by, "mail_kerry", f"{subject[:120]}: {status}")
    except Exception:
        pass
    return {**out, "status": status}
