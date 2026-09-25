"""Bounce intake: read Exchange non-delivery reports and stop mailing dead
addresses (CA directive #688, Kerry 2026-09-25: "Deal with this.").

The 9 AM lapsed-member notice to Hayden Cooper bounced 550 5.1.2 "domain
not found", and nobody would have known unless a person spotted the NDR in
the admin mailbox. This module is the class fix:

- ``parse_ndr`` recognises a non-delivery report and pulls the rejected
  address and the SMTP status (basic ``550`` and enhanced ``5.1.2``).
- ``process_bounces`` marks a PERMANENT failure (5.x.x) undeliverable on
  every ``customer_emails`` row carrying that address, with the code and
  date as the reason, through ``set_email_undeliverable``: the one helper
  that bars an address from every send path while keeping it for matching.
  It then raises ONE COO action item per bounce naming the customer and
  what bounced. TRANSIENT failures (4.x.x) are only logged: a full mailbox
  or a greylist delay is not a dead address.

Every NDR it looks at is recorded in ``expense_seen_emails`` (classified as
``ndr``), so it is handled once, and the expense classifier (which reads
the same table) never bills Anthropic to classify it.

Portable-SQL rule (#682): this module writes no SQL of its own beyond one
case-insensitive lookup written with ``lower()`` on both sides; all writes
go through existing helpers.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Subjects Exchange / Outlook / common MTAs give a bounce.
_NDR_SUBJECT_RE = re.compile(
    r"^\s*(undeliverable|undelivered mail|delivery has failed|"
    r"delivery status notification \(failure\)|mail delivery failed|"
    r"returned mail|failure notice|delivery failure)\b",
    re.IGNORECASE)
_NDR_FROM_RE = re.compile(r"(microsoftexchange|postmaster|mailer-daemon)",
                          re.IGNORECASE)

_EMAIL_RE = r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
# "Your message to X couldn't be delivered." (Exchange Online), then the
# older / generic shapes.
_RECIPIENT_PATTERNS = (
    re.compile(r"your message to\s*<?(" + _EMAIL_RE + r")>?\s*couldn'?t be delivered",
               re.IGNORECASE),
    re.compile(r"delivery has failed to these recipients or groups:\s*"
               r"(?:[^<\n]*<)?(" + _EMAIL_RE + r")", re.IGNORECASE),
    re.compile(r"original recipient:\s*(?:rfc822;\s*)?(" + _EMAIL_RE + r")",
               re.IGNORECASE),
    re.compile(r"final-recipient:\s*(?:rfc822;\s*)?(" + _EMAIL_RE + r")",
               re.IGNORECASE),
    re.compile(r"recipient address:\s*(" + _EMAIL_RE + r")", re.IGNORECASE),
)
_ENHANCED_RE = re.compile(r"(?<![\d.])([245])\.(\d{1,3})\.(\d{1,3})(?![\d.])")
_BASIC_RE = re.compile(r"(?<![\d.])([45]\d\d)(?=[\s-])")
_DETAIL_RE = re.compile(
    r"(?:remote server returned|status code|diagnostic-code:[^\n]*?)\s*'?\s*"
    r"(?:[45]\d\d[\s-])?(?:[245]\.\d{1,3}\.\d{1,3})?\s*[-:]?\s*([^'\n]{3,160})",
    re.IGNORECASE)

# Our own senders never count as the bounced recipient.
_OWN_DOMAINS = ("thegolffellowship.com", "microsoft.com", "outlook.com",
                "protection.outlook.com")


def is_ndr(subject: str, from_addr: str) -> bool:
    return bool(_NDR_SUBJECT_RE.search(subject or "")
                or _NDR_FROM_RE.search(from_addr or ""))


def _strip_html(text: str) -> str:
    # "Pat Guy <pat@x.com>" is an address, not a tag: keep it.
    text = re.sub(r"<(" + _EMAIL_RE + r")>", r" \1 ", text or "")
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&nbsp;", " ").replace("&lt;", "<")
            .replace("&gt;", ">").replace("&#39;", "'").replace("&amp;", "&"))
    return re.sub(r"[ \t]+", " ", text)


def parse_ndr(subject: str, from_addr: str, body: str) -> dict | None:
    """Return {recipient, code, enhanced, permanent, detail} for a
    non-delivery report, or None when the email is not one (or names no
    recipient we can act on)."""
    if not is_ndr(subject, from_addr):
        return None
    text = _strip_html(body or "")
    recipient = None
    for pat in _RECIPIENT_PATTERNS:
        m = pat.search(text)
        if m:
            recipient = m.group(1)
            break
    if not recipient:
        # Last resort: the first address in the report that is not ours.
        for cand in re.findall(_EMAIL_RE, text):
            if not cand.lower().endswith(_OWN_DOMAINS):
                recipient = cand
                break
    if not recipient or recipient.lower().endswith(_OWN_DOMAINS):
        return None
    recipient = recipient.strip().strip(".").lower()

    enh = _ENHANCED_RE.search(text)
    basic = _BASIC_RE.search(text)
    enhanced = ".".join(enh.groups()) if enh else None
    code = basic.group(1) if basic else None
    # The enhanced class is authoritative (RFC 3463): 5 = permanent,
    # 4 = transient. Fall back to the basic reply code, then to the
    # subject ("Undeliverable" with no code at all is treated as
    # permanent only when Exchange says it could not be delivered).
    if enhanced:
        permanent = enhanced.startswith("5")
    elif code:
        permanent = code.startswith("5")
    else:
        permanent = bool(re.search(r"couldn'?t be delivered|could not be delivered",
                                   text, re.IGNORECASE))
    dm = _DETAIL_RE.search(text)
    detail = (dm.group(1).strip().rstrip("'").strip() if dm else "")[:160]
    if not detail:
        low = text.lower()
        for phrase in ("domain not found", "user unknown", "mailbox unavailable",
                       "recipient not found", "address rejected",
                       "does not exist", "mailbox full"):
            if phrase in low:
                detail = phrase
                break
    return {"recipient": recipient, "code": code, "enhanced": enhanced,
            "permanent": permanent, "detail": detail}


def _reason(ndr: dict, when: str) -> str:
    code = " ".join(x for x in (ndr.get("code"), ndr.get("enhanced")) if x) or "no code"
    detail = f" {ndr['detail']}" if ndr.get("detail") else ""
    return f"{code}{detail}, NDR {when}"


def process_bounces(emails: list[dict], db_path=None, seen: set | None = None) -> dict:
    """Handle every NDR in ``emails`` (dicts shaped like fetch_all_emails
    output: uid, subject, from, date, text/html). Idempotent through the
    seen-email table."""
    from . import database as db

    if seen is None:
        seen = db.get_expense_seen_uids(db_path)
    out = {"ndrs": 0, "permanent": 0, "transient": 0, "marked": [],
           "already_marked": [], "unmatched": [], "action_items": []}
    for e in emails:
        uid = e.get("uid") or ""
        if not uid or uid in seen:
            continue
        ndr = parse_ndr(e.get("subject", ""), e.get("from", ""),
                        e.get("html") or e.get("text") or "")
        if ndr is None:
            continue
        out["ndrs"] += 1
        when = (e.get("date") or "")[:10] or "unknown date"
        if not ndr["permanent"]:
            out["transient"] += 1
            logger.info("Bounce intake: transient failure for %s (%s %s) — logged only",
                        ndr["recipient"], ndr.get("code"), ndr.get("enhanced"))
            db.mark_expense_email_seen(uid, "ndr", db_path=db_path)
            seen.add(uid)
            continue
        out["permanent"] += 1
        with db._connect(db_path) as conn:
            rows = conn.execute(
                "SELECT ce.customer_id, ce.email, COALESCE(ce.undeliverable, 0) AS bad, "
                "  TRIM(COALESCE(c.first_name, '') || ' ' || COALESCE(c.last_name, '')) AS name "
                "FROM customer_emails ce LEFT JOIN customers c ON c.customer_id = ce.customer_id "
                "WHERE lower(ce.email) = lower(?)", (ndr["recipient"],)).fetchall()
        if not rows:
            out["unmatched"].append(ndr["recipient"])
            logger.info("Bounce intake: %s bounced (%s) but is on no customer — logged only",
                        ndr["recipient"], _reason(ndr, when))
        reason = _reason(ndr, when)
        for r in rows:
            cid, name = r["customer_id"], (r["name"] or "").strip() or "unknown"
            if r["bad"]:
                out["already_marked"].append({"customer_id": cid, "email": r["email"]})
                continue
            res = db.set_email_undeliverable(cid, r["email"], reason=reason,
                                             db_path=db_path)
            if res.get("error"):
                logger.warning("Bounce intake: could not mark %s on %s: %s",
                               r["email"], cid, res["error"])
                continue
            out["marked"].append({"customer_id": cid, "email": r["email"],
                                  "no_deliverable_address": res.get("no_deliverable_address")})
            left = ("No other deliverable email is on file."
                    if res.get("no_deliverable_address")
                    else f"Mail now goes to {res.get('now_primary')}.")
            item = db.save_action_item({
                "email_uid": f"{uid}#{cid}",
                "subject": f"Email bounced: {name} <{r['email']}>",
                "from_name": "Bounce intake",
                "from_email": e.get("from", ""),
                "summary": (f"{name} (customer {cid}): mail to {r['email']} bounced "
                            f"permanently ({reason}). The Tracker marked the address "
                            f"undeliverable and will not send to it again. {left} "
                            f"Find a working address or leave it."),
                "urgency": "medium",
                "category": "member_inquiry",
                "email_date": e.get("date"),
                "confidence": 100,
            }, db_path=db_path)
            if item.get("id"):
                out["action_items"].append(item["id"])
            try:
                db.log_agent_action("bounce-intake", "email-undeliverable",
                                    f"cid={cid} {r['email']} {reason}",
                                    db_path=db_path)
            except Exception:
                pass
        db.mark_expense_email_seen(uid, "ndr", db_path=db_path)
        seen.add(uid)
    return out
