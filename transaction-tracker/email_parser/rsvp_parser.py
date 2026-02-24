"""
Golf Genius RSVP email parser — extracts player confirmations/cancellations
from "Round Signup Confirmation" emails.

These emails follow a consistent format:
  Subject: "Round Signup Confirmation for Tue, March 17"
  From: noreply@golfgenius.com
  Body: "Hi Joe, You just confirmed for TGF San Antonio 2026 - s9.1 The Quarry (Tue, March 17)."
  Or:   "Hi Tony, You just cancelled for TGF San Antonio 2026 - LaCANTERA (Sun, February 22)."

No AI parsing needed — pure regex extraction.
"""

import html
import logging
import os
import re
from datetime import datetime, timedelta

import msal
import requests

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_RSVP_PATTERN = re.compile(
    r"You just\s+(confirmed|cancelled)\s+for\s+(.+?)\s*\(([^)]+)\)",
    re.IGNORECASE,
)

_GREETING_PATTERN = re.compile(r"Hi\s+(\w+)", re.IGNORECASE)


def _strip_html(raw_html: str) -> str:
    """Remove HTML tags and decode entities to plain text."""
    text = re.sub(r"<style[^>]*>.*?</style>", " ", raw_html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Graph API fetch — specifically for RSVP emails
# ---------------------------------------------------------------------------

def _get_graph_token(tenant_id: str, client_id: str, client_secret: str) -> str | None:
    """Acquire an access token for Microsoft Graph."""
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" in result:
        return result["access_token"]
    logger.error("Failed to acquire Graph token for RSVP: %s", result.get("error_description", result))
    return None


def fetch_rsvp_emails(since_date: datetime | None = None) -> list[dict]:
    """
    Fetch RSVP confirmation emails from the configured RSVP mailbox.

    Uses RSVP_EMAIL_ADDRESS (kerry@thegolffellowship.com) and falls back
    to main Azure credentials if RSVP-specific ones aren't set.

    Returns list of dicts with: uid, subject, from, to_emails, date, text, html
    """
    tenant_id = os.getenv("RSVP_AZURE_TENANT_ID") or os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("RSVP_AZURE_CLIENT_ID") or os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("RSVP_AZURE_CLIENT_SECRET") or os.getenv("AZURE_CLIENT_SECRET")
    address = os.getenv("RSVP_EMAIL_ADDRESS")

    if not all([tenant_id, client_id, client_secret, address]):
        logger.warning("RSVP email credentials not configured — skipping RSVP check")
        return []

    if since_date is None:
        since_date = datetime.now() - timedelta(days=90)

    token = _get_graph_token(tenant_id, client_id, client_secret)
    if not token:
        raise RuntimeError("Could not acquire Graph API token for RSVP inbox")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    since_str = since_date.strftime("%Y-%m-%dT00:00:00Z")

    results = []
    base_url = f"{GRAPH_BASE}/users/{address}/messages"
    params = {
        "$filter": (
            f"receivedDateTime ge {since_str}"
            " and from/emailAddress/address eq 'noreply@golfgenius.com'"
        ),
        "$select": "id,subject,from,toRecipients,receivedDateTime,body",
        "$top": "100",
        "$orderby": "receivedDateTime desc",
    }

    next_link = None
    first_page = True

    while first_page or next_link:
        if first_page:
            resp = requests.get(base_url, headers=headers, params=params, timeout=30)
            first_page = False
        else:
            resp = requests.get(next_link, headers=headers, timeout=30)

        logger.info("RSVP Graph API response status: %s", resp.status_code)
        resp.raise_for_status()
        data = resp.json()

        messages = data.get("value", [])
        logger.info("RSVP page returned %d messages", len(messages))

        for msg in messages:
            subject = msg.get("subject", "")
            # Only process Round Signup Confirmation emails
            if "round signup confirmation" not in subject.lower():
                continue

            body = msg.get("body", {})
            body_content = body.get("content", "")
            content_type = body.get("contentType", "text")

            # Extract To: recipients — the player's email
            to_recipients = msg.get("toRecipients", [])
            to_emails = [
                r.get("emailAddress", {}).get("address", "").lower()
                for r in to_recipients
            ]
            # Filter out the RSVP mailbox itself
            rsvp_addr = address.lower()
            player_emails = [e for e in to_emails if e and e != rsvp_addr]

            results.append({
                "uid": msg["id"],
                "subject": subject,
                "from": msg.get("from", {}).get("emailAddress", {}).get("address", ""),
                "to_emails": player_emails,
                "date": msg.get("receivedDateTime"),
                "text": body_content if content_type == "text" else "",
                "html": body_content if content_type == "html" else "",
            })

        next_link = data.get("@odata.nextLink")

    logger.info("Fetched %d RSVP emails since %s", len(results), since_date.date())
    return results


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_event_date(date_str: str) -> str | None:
    """Parse event date from RSVP to YYYY-MM-DD.

    Input: "Tue, March 17", "Sun, February 22", etc.
    """
    cleaned = re.sub(r"^[A-Za-z]+,\s*", "", date_str.strip())
    current_year = datetime.now().year

    for fmt in ("%B %d", "%b %d"):
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.replace(year=current_year).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _extract_event_identifier(full_event_text: str) -> str:
    """Extract event identifier from the full GG event string.

    "TGF San Antonio 2026 - s9.1 The Quarry" → "s9.1 The Quarry"
    "TGF San Antonio 2026 - LaCANTERA"       → "LaCANTERA"
    """
    parts = full_event_text.split(" - ", 1)
    if len(parts) == 2:
        return parts[1].strip()
    return full_event_text.strip()


def parse_rsvp_email(email_data: dict) -> dict | None:
    """
    Parse a single RSVP email and return structured data.

    Returns dict with keys:
        email_uid, player_name, player_email, gg_event_name,
        event_identifier, event_date, response, received_at
    Or None if parsing fails.
    """
    body = email_data.get("text", "")
    if not body and email_data.get("html"):
        body = _strip_html(email_data["html"])
    if not body:
        return None

    match = _RSVP_PATTERN.search(body)
    if not match:
        logger.warning("RSVP pattern not found in email uid=%s subject=%s",
                        email_data.get("uid", "?"), email_data.get("subject", "?"))
        return None

    action = match.group(1).lower()
    full_event = match.group(2).strip()
    date_str = match.group(3).strip()

    response = "PLAYING" if action == "confirmed" else "NOT PLAYING"
    event_identifier = _extract_event_identifier(full_event)
    event_date = _parse_event_date(date_str)

    # Player name from greeting
    greeting_match = _GREETING_PATTERN.search(body)
    player_first_name = greeting_match.group(1) if greeting_match else None

    # Player email from To: field
    player_emails = email_data.get("to_emails", [])
    player_email = player_emails[0] if player_emails else None

    return {
        "email_uid": email_data.get("uid", ""),
        "player_name": player_first_name,
        "player_email": player_email,
        "gg_event_name": full_event,
        "event_identifier": event_identifier,
        "event_date": event_date,
        "response": response,
        "received_at": email_data.get("date"),
    }


def parse_rsvp_emails(email_list: list[dict]) -> list[dict]:
    """Parse a batch of RSVP emails. Returns list of parsed RSVP dicts."""
    results = []
    for email_data in email_list:
        try:
            parsed = parse_rsvp_email(email_data)
            if parsed:
                results.append(parsed)
        except Exception:
            logger.exception("Failed to parse RSVP email uid=%s", email_data.get("uid"))
    logger.info("Parsed %d RSVPs from %d emails", len(results), len(email_list))
    return results
